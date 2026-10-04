"""Chromium to real local HTTP and Git; only deliberate response loss is injected.

Run with Playwright installed and AW_TEST_BROWSER set to a Chromium executable,
or use Playwright's installed browser. No Harness/account/model is required.
"""
import json
import os
import threading

import pytest

from agent_workspace import maintenance
from agent_workspace.messages import Messages
from agent_workspace.server import make_server
from agent_workspace.util import encode, read_json, write_json


@pytest.fixture(scope='module')
def browser():
    if not (os.environ.get('AW_BROWSER_TESTS') == '1' or os.environ.get('AW_TEST_BROWSER')):
        pytest.skip('Set AW_BROWSER_TESTS=1 or AW_TEST_BROWSER to run real browser integration')
    playwright = pytest.importorskip('playwright.sync_api')
    with playwright.sync_playwright() as api:
        options = {'headless': True}
        if os.environ.get('AW_TEST_BROWSER'):
            options['executable_path'] = os.environ['AW_TEST_BROWSER']
        instance = api.chromium.launch(**options)
        yield instance
        instance.close()


@pytest.fixture
def ui(pair, browser):
    app, bindings = pair
    server = make_server(app, 0, 'browser-test-token')
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    context = browser.new_context(viewport={'width': 1440, 'height': 960})
    page = context.new_page()
    page.set_default_timeout(15000)
    failures = []
    page.on('pageerror', lambda error: failures.append(str(error)))
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        page.goto(base + '/#token=browser-test-token')
        page.wait_for_selector('#app:not(.hidden)')
        yield app, bindings, page
        assert not failures, failures
    finally:
        context.close()
        server.shutdown()
        server.server_close()
        thread.join(5)
        assert not thread.is_alive()


def compose(page, content='original message'):
    page.locator('[data-tab="collaboration"]').click()
    page.get_by_role('button', name='发送消息', exact=True).click()
    page.get_by_label('发送实例', exact=True).select_option('alice')
    page.get_by_label('接收者（实例 ID 或 好友/实例）', exact=True).fill('bob')
    page.get_by_label('正文', exact=True).fill(content)


def pending(page):
    return page.evaluate("JSON.parse(sessionStorage.getItem(messageKey()))")


@pytest.mark.parametrize('delivered', [False, True])
def test_response_loss_refresh_continues_only_original_message(ui, delivered):
    app, bindings, page = ui
    attempts = []

    def lose_response(route):
        body = route.request.post_data_json
        if body['command'] == 'message.send':
            attempts.append(body['arguments'])
            if delivered:
                response = route.fetch()
                assert response.json()['ok']
            route.abort()
        else:
            route.continue_()

    page.route('**/api/execute', lose_response)
    compose(page)
    # Two synchronous submit events must still create only one original request.
    page.locator('#form').evaluate('(form) => {form.requestSubmit(); form.requestSubmit();}')
    page.wait_for_function("!messageBusy && !!pendingMessage() && !!document.getElementById('error').textContent")
    assert len(attempts) == 1
    identifier = pending(page)['args']['request_id']
    assert attempts[0]['binding'] == bindings['alice']
    assert len(Messages(app).list('sea')) == int(delivered)
    page.unroute('**/api/execute', lose_response)
    page.reload()
    page.wait_for_selector('#pending-message:not(.hidden)')
    assert pending(page)['args']['request_id'] == identifier
    assert len(Messages(app).list('sea')) == int(delivered)  # Reload never sends.
    page.get_by_role('button', name='继续原请求', exact=True).click()
    page.wait_for_selector('#pending-message.hidden', state='attached')
    result = Messages(app).list('sea')
    assert len(result) == 1 and result[0]['id'] == identifier
    assert Messages(app).show('sea', identifier)['message']['content'] == 'original message'
    assert pending(page) is None


def test_second_deliberate_send_has_new_id(ui):
    app, _, page = ui
    compose(page)
    page.locator('#submit').click()
    page.wait_for_function("!messageBusy && !pendingMessage() && !document.getElementById('submit').disabled")
    first = Messages(app).list('sea')[0]['id']
    compose(page, 'a separate message')
    page.locator('#submit').click()
    page.wait_for_function("!messageBusy && !pendingMessage() && !document.getElementById('submit').disabled")
    assert len(Messages(app).list('sea')) == 2
    assert len({m['id'] for m in Messages(app).list('sea')}) == 2
    assert Messages(app).show('sea', first)['message']['content'] == 'original message'


def test_storage_failure_prevents_network_send(ui):
    app, _, page = ui
    compose(page)
    page.evaluate("() => { Storage.prototype.setItem = function() { throw new Error('storage unavailable'); }; }")
    page.locator('#submit').click()
    page.wait_for_function("document.getElementById('error').textContent.includes('storage unavailable')")
    assert not Messages(app).list('sea')
    assert page.locator('#dialog').is_visible()


def test_inspect_unrecorded_request_does_not_send_and_workspace_scope_is_fixed(ui):
    app, bindings, page = ui
    record = {'locator': app.workspace_show('sea')['locator'], 'args': {
        'workspace': 'sea', 'agent_id': 'alice', 'binding': bindings['alice'],
        'to': 'bob', 'content': 'inspect only', 'delivery': 'normal', 'request_id': 'inspect-only'}}
    page.evaluate('(record) => {sessionStorage.setItem(messageKey(), JSON.stringify(record)); renderPendingMessage();}', record)
    page.get_by_role('button', name='查看原请求', exact=True).click()
    page.wait_for_function("document.getElementById('output').textContent.includes('not_recorded')")
    assert not Messages(app).list('sea') and pending(page)
    record['locator'] = 'workspace:different'
    page.evaluate('(record) => sessionStorage.setItem(messageKey(), JSON.stringify(record))', record)
    page.get_by_role('button', name='继续原请求', exact=True).click()
    page.wait_for_function("document.getElementById('error').textContent.includes('地址已变化')")
    assert not Messages(app).list('sea')


def test_grants_are_explicit_checkboxes_and_revocable(ui):
    app, _, page = ui
    app.create('sea', 'steward')
    store = app.store('sea')
    snap = store.snapshot()
    meta = snap.json('workspace.json')
    meta['caretakers'] = {'steward': 'steward'}
    store.change('main', {'workspace.json': encode(meta)}, {'workspace.json': snap.entries['workspace.json']}, 'Test caretaker')
    page.locator('#refresh').click()
    page.wait_for_function("state.agents.some(a => a.id === 'steward')")
    page.locator('[data-tab="workspaces"]').click()
    page.get_by_role('button', name='管家授权', exact=True).click()
    action = page.locator('fieldset[data-key="commands"] input[value="agent.start"]')
    target = page.locator('fieldset[data-key="targets"] input[value="alice"]')
    action.check()
    target.check()
    assert not page.locator('fieldset[data-key="targets"] input[value="*"]').is_checked()
    page.locator('#submit').click()
    page.wait_for_selector('#dialog', state='hidden')
    grant = maintenance.status(app, 'sea')['grants']['steward']
    assert grant['commands'] == ['agent.start'] and grant['targets'] == ['alice']
    page.get_by_role('button', name='管家授权', exact=True).click()
    assert action.is_checked() and target.is_checked()
    action.uncheck()
    target.uncheck()
    page.locator('#submit').click()
    page.wait_for_selector('#dialog', state='hidden')
    assert maintenance.status(app, 'sea')['grants']['steward']['commands'] == []


def test_health_repair_prefills_observation_but_rejects_changed_generation(ui):
    app, bindings, page = ui
    root = app.root('sea', 'alice')
    config = root / '.aw-local/bridges/chat.json'
    status = root / '.aw-local/bridges/status/chat.json'
    write_json(config, {'enabled': True, 'generation': 'observed'})
    write_json(status, {'fatal': True})
    page.locator('[data-tab="workspaces"]').click()
    page.get_by_role('button', name='健康检查', exact=True).click()
    page.get_by_role('button', name='处理 alice / bridge_fault', exact=True).click()
    assert page.locator('#f-agent_id').input_value() == 'alice'
    assert page.locator('#f-expected_binding').input_value() == bindings['alice']
    assert page.locator('#f-expected_generation').input_value() == 'observed'
    write_json(config, {'enabled': True, 'generation': 'changed'})
    page.locator('#submit').click()
    page.wait_for_function("document.getElementById('form-description').textContent.includes('changed')")
    assert read_json(config)['generation'] == 'changed'
    assert not list((maintenance.folder(app, 'sea') / 'repairs').glob('*.json'))


@pytest.mark.parametrize('viewport', [{'width': 390, 'height': 844}, {'width': 1440, 'height': 960}])
def test_forms_and_recovery_fit_viewport(ui, viewport):
    _, _, page = ui
    page.set_viewport_size(viewport)
    compose(page)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert page.locator('#dialog').evaluate('(d) => d.scrollWidth <= d.clientWidth')
    page.locator('#cancel').click()
    page.locator('[data-tab="workspaces"]').click()
    page.get_by_role('button', name='限定维修', exact=True).click()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert page.locator('#dialog').evaluate('(d) => d.scrollWidth <= d.clientWidth')


def test_damaged_observation_keeps_workbench_and_diagnostics_usable(ui):
    app, bindings, page = ui
    damaged = app.root('sea', 'alice') / '.aw-local/status.json'
    damaged.write_bytes(b'{broken')
    page.locator('#refresh').click()
    broken = page.locator('article').filter(has=page.get_by_role('heading', name='alice', exact=True))
    broken.get_by_text('状态读取失败', exact=True).wait_for()
    assert broken.get_by_role('button').all_text_contents() == ['健康检查']
    assert page.locator('#auth').is_hidden()
    healthy = page.locator('article').filter(has=page.get_by_role('heading', name='bob', exact=True))
    assert healthy.get_by_role('button', name='详情', exact=True).is_visible()
    broken.get_by_role('button', name='健康检查', exact=True).click()
    page.wait_for_function("document.getElementById('output').textContent.includes('local_observation_failed')")
    assert damaged.read_bytes() == b'{broken'
    assert app.agent('sea', 'alice')['current'] == bindings['alice']


@pytest.mark.parametrize('setup_page', [False, True])
def test_http_profile_consent_is_explicit_and_resets_with_destination(ui, setup_page):
    import sys
    from playwright.sync_api import expect

    app, _, page = ui
    app.create('sea', 'http-profile')
    if setup_page:
        page.goto(page.url.split('/#')[0].rstrip('/') + '/setup')
        page.locator('#app:not([hidden])').wait_for()
        page.locator('#agent').select_option('http-profile')
        prefix = ''
        submit = page.get_by_role('button', name='只保存选中实例配置', exact=True)
    else:
        page.locator('#refresh').click()
        card = page.locator('article').filter(has=page.get_by_role('heading', name='http-profile', exact=True))
        card.get_by_role('button', name='配置', exact=True).click()
        prefix = 'f-'
        submit = page.locator('#submit')
    url = page.locator('#' + prefix + 'base_url')
    consent = page.locator('#' + prefix + 'allow_http')
    page.locator('#' + prefix + 'executable').fill(sys.executable)
    url.fill('http://192.0.2.75:4000/v1')
    expect(consent).not_to_be_checked()
    submit.click()
    expect(page.locator('#error')).to_contain_text('allow-http')
    path = app.root('sea', 'http-profile') / '.aw-local/runtime.json'
    assert not path.exists()
    consent.check()
    url.fill('http://models.internal:4000/v1')
    expect(consent).not_to_be_checked()
    consent.check()
    page.locator('#' + prefix + 'kind').select_option('claude')
    expect(consent).not_to_be_checked()
    page.locator('#' + prefix + 'kind').select_option('codex')
    consent.check()
    submit.click()
    if setup_page:
        expect(page.locator('#output')).to_contain_text('"configured": true')
    else:
        expect(page.locator('#dialog')).not_to_be_visible()
    assert read_json(path)['allow_http'] is True
    assert app.agent('sea', 'http-profile')['current'] is None


def test_desktop_project_form_preserves_user_names_without_native_changes(ui, tmp_path):
    from agent_workspace import desktop_projects
    app, bindings, page = ui
    product = tmp_path / 'product'
    product.mkdir()
    before = app.store('sea').head('main')
    page.get_by_role('button', name='桌面项目', exact=True).first.click()
    page.wait_for_selector('#f-project_name')
    name = page.locator('#f-project_name').input_value()
    agent = name.split(' · ')[-1]
    page.locator('#f-project_name').fill('My Existing Project')
    page.locator('#f-section_name').fill('My Existing Section')
    page.locator('#f-product_paths').fill(str(product))
    page.locator('#submit').click()
    page.wait_for_selector('#dialog', state='hidden')
    value = desktop_projects.plan(app, 'sea', agent)
    assert value['project']['project_name'] == 'My Existing Project'
    assert value['project']['section_name'] == 'My Existing Section'
    assert value['native_project_verified'] is False
    assert app.store('sea').head('main') == before and not list(product.iterdir())
    page.get_by_role('button', name='桌面项目', exact=True).first.click()
    assert page.locator('#f-project_name').input_value() == 'My Existing Project'
    page.locator('#f-harness').select_option('workbuddy')
    page.wait_for_function("document.getElementById('f-section_name').disabled")
    assert page.locator('#f-section_name').input_value() == ''


def test_ordinary_page_without_workspace_lost_response_does_not_open_twice(tmp_path, browser, monkeypatch):
    import sys
    from agent_workspace.app import App
    from agent_workspace import sessions
    app = App(tmp_path / 'empty-home')
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'AGENTS.md').write_text('unchanged project rules', encoding='utf-8')
    launches = []
    def terminal(argv):
        launches.append(argv)
        return [sys.executable, '-c', 'pass'], {}
    monkeypatch.setattr(sessions, '_terminal', terminal)
    server = make_server(app, 0, 'ordinary-browser-token')
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    try:
        page.goto(f'http://127.0.0.1:{server.server_port}/sessions#token=ordinary-browser-token')
        page.wait_for_selector('#app:not([hidden])')
        page.locator('#kind').select_option('claude')
        page.locator('#directory').fill(str(project))
        page.locator('#executable').fill(sys.executable)
        page.locator('#prompt').fill('Review only; no project file change.')
        def lose_response(route):
            if route.request.post_data_json['command'] == 'session.open':
                assert route.fetch().json()['ok']
                route.abort()
            else:
                route.continue_()
        page.route('**/api/execute', lose_response)
        page.locator('#form').evaluate('(f) => {f.requestSubmit();f.requestSubmit();}')
        page.wait_for_function("!busy && !!document.getElementById('error').textContent")
        assert len(launches) == 1
        page.unroute('**/api/execute', lose_response)
        page.reload()
        page.wait_for_selector('#pending:not([hidden])')
        page.wait_for_function("!busy")
        page.locator('#continue').click()
        page.wait_for_function("!busy")
        assert len(launches) == 1 and not app.registry.exists()
        assert len(list((app.home / 'ordinary-sessions').glob('*.json'))) == 1
        assert (project / 'AGENTS.md').read_text() == 'unchanged project rules'
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    finally:
        context.close()
        server.shutdown()
        server.server_close()
        thread.join(5)
