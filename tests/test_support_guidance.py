"""The user and the native session receive the same installed support limits."""
from importlib.resources import files
import json
import threading
from unittest.mock import Mock
import urllib.error
import urllib.request

import pytest

from agent_workspace import commands, runtime
from agent_workspace.messages import Messages
from agent_workspace.server import make_server
from agent_workspace.util import Conflict, digest, read_json, write_json


def guide():
    return (files('agent_workspace') / 'resources' / 'prompts' / 'capabilities.md').read_text(encoding='utf-8')


def test_new_instance_contains_versioned_guidance(app):
    app.create('sea', 'alice')
    root = app.root('sea', 'alice')
    content = (root / '.aw/prompts/capabilities.md').read_bytes()
    assert content == (files('agent_workspace') / 'resources/prompts/capabilities.md').read_bytes()
    manifest = read_json(root / '.aw/software.json')
    assert manifest['files']['.aw/prompts/capabilities.md'] == digest(content)
    for skill in ('message', 'relay'):
        assert 'capabilities.md' in (root / f'.agents/skills/{skill}/SKILL.md').read_text(encoding='utf-8')


@pytest.mark.parametrize('handoff', [False, True])
def test_entry_uses_installed_guidance_even_when_local_copy_is_stale(app, handoff):
    app.create('sea', 'alice')
    root = app.root('sea', 'alice')
    if handoff:
        old = app.reserve('sea', 'alice')['binding']
        app.bind('sea', 'alice', old, 'original-session')
        point = app.checkpoint('sea', 'alice', 'saved work', binding=old)
        app.stop('sea', 'alice', old, point['id'])
        app.finish_stop('sea', 'alice', old, observed_idle=True)
    app.configure('sea', 'alice', {'kind': 'claude'})
    binding = app.reserve('sea', 'alice')['binding']
    # Simulate an existing instance before the software was upgraded.
    local = root / '.aw/prompts/capabilities.md'
    local.write_text('obsolete capability claims', encoding='utf-8')
    (root / '.aw/prompts/entry.md').write_text('legacy entry instructions', encoding='utf-8')
    prompt = runtime.entry_prompt(app, 'sea', 'alice', binding, root)
    assert guide() in prompt and prompt.count(guide()) == 1
    assert 'obsolete capability claims' not in prompt
    assert '"runtime_kind": "claude"' in prompt
    assert json.loads(prompt.splitlines()[0])['entry_mode'] == ('relay' if handoff else 'initial')
    assert ('交接点与检查点' in prompt) == handoff
    assert local.read_text(encoding='utf-8') == 'obsolete capability claims'
    local.unlink()
    assert guide() in runtime.entry_prompt(app, 'sea', 'alice', binding, root)


def test_explicit_upgrade_adds_guidance_without_overwriting_user_assets(app):
    app.create('sea', 'alice')
    root = app.root('sea', 'alice')
    local = root / '.aw/prompts/capabilities.md'
    local.unlink()
    manifest_path = root / '.aw/software.json'
    manifest = read_json(manifest_path)
    manifest['files'].pop('.aw/prompts/capabilities.md')
    write_json(manifest_path, manifest)
    (root / 'AGENTS.md').write_text('user responsibilities', encoding='utf-8')
    commands.upgrade_tools(app, 'sea', 'alice')
    assert local.read_text(encoding='utf-8') == guide()
    assert (root / 'AGENTS.md').read_text(encoding='utf-8') == 'user responsibilities'
    local.write_text('locally edited guidance', encoding='utf-8')
    with pytest.raises(Conflict, match='Modified platform resource'):
        commands.upgrade_tools(app, 'sea', 'alice')
    assert local.read_text(encoding='utf-8') == 'locally edited guidance'


def test_public_guidance_does_not_read_accounts_or_workspace_state():
    app = Mock()
    server = make_server(app, 0, 'private-control-token')
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with urllib.request.urlopen(base + '/capabilities') as response:
            assert response.headers.get_content_type() == 'text/plain'
            assert response.headers['X-Content-Type-Options'] == 'nosniff'
            assert response.read() == (files('agent_workspace') / 'resources/prompts/capabilities.md').read_bytes()
        app.workspace_list.assert_not_called()
        app.local.assert_not_called()
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(base + '/api/state')
        assert error.value.code == 401
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize('page', ['index.html', 'setup.html'])
def test_user_pages_link_to_the_installed_guidance(page):
    content = (files('agent_workspace') / 'resources' / page).read_text(encoding='utf-8')
    assert 'href="/capabilities"' in content
    assert '当前版本支持范围与限制' in content


def test_unsupported_delivery_explains_next_step_without_changing_fifo_or_ack(pair):
    app, bindings = pair
    messages = Messages(app)
    messages.send('sea', 'alice', bindings['alice'], 'bob', 'first', delivery='insert', request_id='first')
    messages.send('sea', 'alice', bindings['alice'], 'bob', 'second', delivery='normal', request_id='second')
    before = app.store('sea').snapshot().revision
    adapter = Mock(supports_insert=False)
    result = messages.poll('sea', 'bob', bindings['bob'], adapter=adapter)
    assert result['state'] == 'delivery_unsupported'
    assert result['message_id'] == 'first'
    assert '用户' in result['instruction'] and '不要重发副本' in result['instruction']
    assert app.store('sea').snapshot().revision == before
    assert messages.show('sea', 'first')['ack'] is None
    adapter.notify.assert_not_called()
    adapter.status.assert_not_called()
