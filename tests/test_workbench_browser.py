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
    page.evaluate("Storage.prototype.setItem = function() { throw new Error('storage unavailable'); }")
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
