"""Real Git/local/CLI/MCP reads; these do not claim a real model read or comprehension."""
import io
import json
from pathlib import Path
import sys

import pytest

from agent_workspace import runtime, shared, server
from agent_workspace.app import App
from agent_workspace.cli import main
from agent_workspace.commands import execute
from agent_workspace.util import Conflict, Error


def setup_team(app):
    store = app.store('sea')
    rule = b'TEAM_RULE_001: inspect before editing.'
    text = '# Role\n\n@workspace-read knowledge/team.md\nOwn duty.'
    store.change('main', {'knowledge/team.md': rule,
                         'definitions/a/definition.md': text.encode(),
                         'definitions/b/definition.md': text.replace('Own duty.', 'Another duty.').encode()}, {}, 'team material')
    for name in ('a', 'b'):
        app.create('sea', name, definition=f'definitions/{name}')
    return store, text, rule


def test_two_agents_read_one_shared_file_and_new_entry_gets_new_revision(app):
    store, text, rule = setup_team(app)
    calls = []
    for name in ('a', 'b'):
        binding = app.reserve('sea', name)['binding']
        app.bind('sea', name, binding, f'session-{name}')
        prompt = runtime.entry_prompt(app, 'sea', name, binding, app.root('sea', name))
        call = json.loads(next(line.removeprefix('required_workspace_read: ') for line in prompt.splitlines()
                               if line.startswith('required_workspace_read: ')))
        result = execute(app, **call, actor=('sea', name, binding))
        assert result['complete'] and result['files'][0]['content'] == rule.decode()
        calls.append(call)
    before = (app.root('sea', 'a') / 'AGENTS.md').read_bytes()
    store.change('main', {'knowledge/team.md': b'TEAM_RULE_002'}, {}, 'one shared update')
    assert execute(app, **calls[0])['files'][0]['content'] == rule.decode()  # Pinned old entry.
    fresh = shared.requirements(app, 'sea', app.root('sea', 'a'))
    assert execute(app, **fresh)['files'][0]['content'] == 'TEAM_RULE_002'
    assert fresh['arguments']['revision'] != calls[0]['arguments']['revision']
    assert (app.root('sea', 'a') / 'AGENTS.md').read_bytes() == before
    assert not any(f['local_changed'] or f['upstream_changed'] for f in app.versions('sea', 'a')['files'])


def test_portable_connect_and_private_definition_changes_are_preserved(app, tmp_path):
    store, text, rule = setup_team(app)
    other = App(tmp_path / 'different-home')
    other.workspace_connect('moved', store.address)
    other.connect_agent('moved', 'a', str(tmp_path / 'new-root'))
    root = other.root('moved', 'a')
    assert (root / 'AGENTS.md').read_text() == text
    call = shared.requirements(other, 'moved', root)
    assert execute(other, **call)['files'][0]['content'] == rule.decode()
    (root / 'AGENTS.md').write_text(text + '\nPrivate boundary.', encoding='utf-8')
    store.change('main', {'definitions/a/definition.md': (text + '\nUpstream duty.').encode()}, {}, 'definition update')
    with pytest.raises(Conflict, match='Locally modified'):
        other.update('moved', 'a')
    assert (root / 'AGENTS.md').read_text().endswith('Private boundary.')
    assert execute(other, **shared.requirements(other, 'moved', root))['complete']


def test_missing_material_fails_before_binding_or_transfer(app):
    store, _, _ = setup_team(app)
    store.change('main', {'knowledge/team.md': None}, {}, 'remove shared file')
    with pytest.raises(Error, match='missing'):
        runtime.start(app, 'sea', 'a')
    assert app.agent('sea', 'a')['current'] is None
    assert not (app.root('sea', 'a') / '.aw-local/launch.json').exists()
    from agent_workspace.transfer import preflight
    with pytest.raises(Error, match='missing'):
        preflight(app, 'sea', 'a', {'kind': 'manual'}, app.root('sea', 'a'))


@pytest.mark.parametrize('path', ['../team.md', '/team.md', r'C:\team.md', 'bindings/test.json',
                                  'knowledge/../../secret', 'knowledge/.git/config', 'knowledge/a:stream',
                                  'knowledge/a.', 'knowledge/a\n.md'])
def test_shared_read_rejects_invalid_locations(app, path):
    with pytest.raises(Error):
        shared.read(app, 'sea', [path])


def test_missing_binary_and_oversized_reads_never_report_partial_success(app):
    store, _, _ = setup_team(app)
    store.change('main', {'knowledge/binary': b'\xff', 'knowledge/large': b'a' * (shared.MAX_READ_BYTES + 1)}, {}, 'invalid material')
    for paths in (['knowledge/team.md', 'knowledge/absent.md'], ['knowledge/binary'], ['knowledge/large']):
        with pytest.raises(Error):
            shared.read(app, 'sea', paths)


def test_only_explicit_directives_not_placeholders_or_code_examples():
    assert shared.required_paths('<workspace_shared_root>/knowledge/a.md\n<other>\n') == []
    assert shared.required_paths('```md\n@workspace-read missing.md\n```\n@workspace-read knowledge/a.md') == ['knowledge/a.md']
    for text in ('@workspace-read', '@workspace-reader knowledge/a.md'):
        with pytest.raises(Error):
            shared.required_paths(text)


def test_cli_and_model_mcp_use_same_shared_reader(app, monkeypatch, capsys):
    _, _, rule = setup_team(app)
    assert main(['--home', str(app.home), '-w', 'sea', 'workspace', 'read', '--path', 'knowledge/team.md']) == 0
    assert json.loads(capsys.readouterr().out)['result']['files'][0]['content'] == rule.decode()
    binding = app.reserve('sea', 'a')['binding']
    app.bind('sea', 'a', binding, 'mcp-reader')
    actor = ('sea', 'a', binding)
    with pytest.raises(Conflict):
        execute(app, 'workspace.read', {'workspace': 'foreign', 'paths': ['knowledge/team.md']}, actor=actor)
    request = {'id': 1, 'method': 'tools/call', 'params': {'name': 'aw_execute', 'arguments': {
        'command': 'workspace.read', 'arguments': {'paths': ['knowledge/team.md']}}}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(request) + '\n'))
    server.mcp(app, actor=actor)
    value = json.loads(json.loads(capsys.readouterr().out)['result']['content'][0]['text'])
    assert value['files'][0]['content'] == rule.decode()


def test_shared_http_read_and_install_use_real_git(app):
    import threading
    import urllib.request
    _, _, rule = setup_team(app)
    app.store('sea').change('main', {'skills/review/SKILL.md': b'read carefully'}, {}, 'shared Skill')
    http = server.make_server(app, 0, 'shared-http-fixture')
    thread = threading.Thread(target=http.serve_forever); thread.start()
    try:
        def call(command, arguments):
            request = urllib.request.Request(f'http://127.0.0.1:{http.server_port}/api/execute',
                data=json.dumps({'command': command, 'arguments': arguments}).encode(),
                headers={'Content-Type': 'application/json', 'Authorization': 'Bearer shared-http-fixture'})
            with urllib.request.urlopen(request, timeout=10) as response: return json.load(response)
        result = call('workspace.read', {'workspace': 'sea', 'paths': ['knowledge/team.md']})
        assert result['ok'] and result['result']['files'][0]['content'] == rule.decode()
        assert call('agent.skill-install', {'workspace': 'sea', 'agent_id': 'a', 'name': 'review'})['result']['state'] == 'installed'
        assert call('agent.skills', {'workspace': 'sea', 'agent_id': 'a'})['ok']
    finally:
        http.shutdown();http.server_close();thread.join(5)
        assert not thread.is_alive()
