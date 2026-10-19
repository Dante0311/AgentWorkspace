"""Session and project protocol fixtures, not real shared Desktop acceptance."""
import json
from unittest.mock import Mock

import pytest

from agent_workspace import desktop_projects, runtime
from agent_workspace.commands import execute
from agent_workspace.util import Conflict, Error, read_json


@pytest.fixture
def peers(app):
    rows = {}
    for name in ('alice', 'bob'):
        app.create('sea', name)
        app.configure('sea', name, {'kind': 'desktop', 'model': 'fixture-model', 'effort': 'low'})
        binding = app.reserve('sea', name)['binding']
        app.bind('sea', name, binding, 'fixture-session-' + name)
        rows[name] = binding
    return app, rows


def test_session_identity_survives_shared_and_other_agents_command_cwd(peers, tmp_path, monkeypatch):
    app, rows = peers
    common = tmp_path / 'common-project'
    common.mkdir()
    monkeypatch.setenv('CODEX_THREAD_ID', 'fixture-session-alice')
    for index, directory in enumerate((common, app.root('sea', 'bob'))):
        monkeypatch.chdir(directory)
        actor = runtime.desktop_directory_actor(app, 'asset.write')
        assert actor == ('sea', 'alice', rows['alice'])
        with pytest.raises(Error):
            execute(app, 'agent.configure', {'agent_id': 'bob', 'value': {'kind': 'manual'}}, actor=actor)
        execute(app, 'asset.write', {'path': f'notes/owned-{index}.txt', 'content': 'alice'}, actor=actor)
    for index in (0, 1):
        assert (app.root('sea', 'alice') / f'notes/owned-{index}.txt').read_text() == 'alice'
        assert not (app.root('sea', 'bob') / f'notes/owned-{index}.txt').exists()
        assert not (common / f'notes/owned-{index}.txt').exists()


def test_released_session_cannot_become_management_by_leaving_personal_root(peers, tmp_path, monkeypatch):
    app, rows = peers
    cp = app.checkpoint('sea', 'alice', 'Fixture handoff', binding=rows['alice'])
    app.stop('sea', 'alice', rows['alice'], cp['id'])
    app.finish_stop('sea', 'alice', rows['alice'], observed_idle=True)
    common = tmp_path / 'common-project'
    common.mkdir()
    monkeypatch.chdir(common)
    monkeypatch.setenv('CODEX_THREAD_ID', 'fixture-session-alice')
    with pytest.raises(Conflict):
        runtime.desktop_directory_actor(app, 'agent.configure')
    assert app.agent('sea', 'alice')['current'] is None


def test_selected_shared_project_preserves_personal_roots_and_independent_defaults(peers, tmp_path):
    app, _ = peers
    common = tmp_path / 'common-project'
    common.mkdir()
    for name in ('alice', 'bob'):
        root = app.root('sea', name)
        initial = desktop_projects.plan(app, 'sea', name)
        assert initial['primary_folder'] == str(root) and initial['project_mode'] == 'independent'
        chosen = desktop_projects.save(app, 'sea', name, 'codex', 'Common project',
                                       project_directory=str(common), revision=initial['revision'])
        assert chosen['instance_root'] == str(root) and chosen['primary_folder'] == str(common)
        assert chosen['project_mode'] == 'shared'
        renamed = desktop_projects.save(app, 'sea', name, 'codex', 'Renamed common project', revision=chosen['revision'])
        assert renamed['primary_folder'] == str(common)
        adapter = runtime.Desktop.__new__(runtime.Desktop)
        adapter.root, adapter.config = root, {'project_id': 'shared-id'}
        adapter.worker_id = None
        adapter.tools = {'list_projects', 'create_thread'}
        adapter.call = lambda *args: {'projects': [{'projectId': 'shared-id', 'path': str(common),
                                                  'hostId': 'local', 'projectKind': 'local'}]}
        assert adapter.project()['projectId'] == 'shared-id'
        restored = desktop_projects.save(app, 'sea', name, 'codex', 'Independent project',
                                          project_directory=str(root), revision=renamed['revision'])
        assert restored['project_mode'] == 'independent' and restored['primary_folder'] == str(root)


def test_entry_prompt_names_personal_instructions_without_claiming_selected_project_is_cwd(peers, tmp_path):
    app, rows = peers
    common = tmp_path / 'common-project'
    common.mkdir()
    root = app.root('sea', 'alice')
    initial = desktop_projects.plan(app, 'sea', 'alice')
    desktop_projects.save(app, 'sea', 'alice', 'codex', 'Common project',
                          project_directory=str(common), revision=initial['revision'])
    context = json.loads(runtime.entry_prompt(app, 'sea', 'alice', rows['alice'], root).split('\n\n')[0])
    assert context['instance_root'] == str(root)
    assert context['instance_branch'] == 'instance/alice'
    assert context['instructions_file'] == str(root / 'AGENTS.md')
    assert context['skills_directory'] == str(root / '.agents/skills')
    assert context['selected_project_directory'] == str(common)
    assert context['native_cwd'] is None


def test_new_shared_chat_keeps_original_project_intent_in_launch_receipt(app, tmp_path):
    app.create('sea', 'alice')
    root = app.root('sea', 'alice')
    app.configure('sea', 'alice', {'kind': 'desktop', 'model': 'fixture-model', 'effort': 'low'})
    binding = app.reserve('sea', 'alice')['binding']
    common = tmp_path / 'common-project'
    common.mkdir()
    initial = desktop_projects.plan(app, 'sea', 'alice')
    desktop_projects.save(app, 'sea', 'alice', 'codex', 'Common project',
                          project_directory=str(common), revision=initial['revision'])
    adapter = runtime.Desktop.__new__(runtime.Desktop)
    adapter.root, adapter.config, adapter.session, adapter.read_only = root, {}, None, False
    adapter.worker_id = None
    adapter.requested_title, adapter.title_receipt = None, None
    adapter.tools = {'list_projects', 'create_thread', 'read_thread'}
    adapter.model_choice = lambda *args: ({'model': 'fixture-model', 'effort': 'low'},
                                         {'catalog': 'unconfirmed', 'effective': 'unconfirmed'})
    calls = []
    def call(name, arguments):
        calls.append(name)
        if name == 'list_projects':
            return {'projects': [{'projectId': 'shared-id', 'path': str(common),
                                  'hostId': 'local', 'projectKind': 'local'}]}
        if name == 'create_thread':
            assert arguments['target']['projectId'] == 'shared-id'
            return {'threadId': 'fixture-new-shared-chat', 'hostId': 'local'}
        return {'thread': {'id': 'fixture-new-shared-chat', 'cwd': str(common), 'hostId': 'local'}}
    adapter.call = call
    adapter.create(binding, 'Explicit connection-only protocol fixture.')
    from agent_workspace import layout
    receipt = read_json(layout.local_path(root, 'launch.json'))
    assert receipt['project_id'] == 'shared-id' and receipt['project_directory'] == str(common)
    assert receipt['result']['threadId'] == 'fixture-new-shared-chat'
    assert calls.count('create_thread') == 1


def test_user_opened_chat_relays_same_agent_and_saved_business_without_creating_a_chat(app, tmp_path, monkeypatch, capsys):
    from agent_workspace import cli, instance_worktrees, layout
    from agent_workspace.util import write_bytes
    app.create('sea', 'alice', description='Fixture role: maintain my own notes')
    root = app.root('sea', 'alice')
    app.configure('sea', 'alice', {'kind': 'desktop', 'command': ['fixture-mcp-command'],
                                 'model': 'fixture-model', 'effort': 'low'})
    old = app.reserve('sea', 'alice')['binding']
    app.bind('sea', 'alice', old, 'fixture-old-chat')
    write_bytes(root / 'notes/progress.md', b'Step one completed. Step two remains paused.')
    point = app.checkpoint('sea', 'alice', 'Step one done', 'Keep step two paused; next inspect existing results.', binding=old)
    app.stop('sea', 'alice', old, point['id'])
    handoff = app.finish_stop('sea', 'alice', old, observed_idle=True)
    common = tmp_path / 'common-project'
    common.mkdir()
    choice = desktop_projects.plan(app, 'sea', 'alice')
    desktop_projects.save(app, 'sea', 'alice', 'codex', 'Shared fixture',
                          project_directory=str(common), revision=choice['revision'])
    monkeypatch.chdir(root)  # A fresh chat may issue its command from the old personal root.
    monkeypatch.setenv('CODEX_THREAD_ID', 'fixture-user-opened-chat')
    monkeypatch.setenv('CODEX_APP_TOOLS_PIPE_PATH', 'fixture-current-pipe')
    native = {'thread': {'id': 'fixture-user-opened-chat', 'hostId': 'local', 'cwd': str(common),
                         'status': {'type': 'active'}, 'model': 'fixture-model', 'reasoningEffort': 'low'}}
    peer = Mock()
    peer.read.return_value = native
    peer.tools = {'read_thread', 'send_message_to_thread'}
    constructor = Mock(return_value=peer)
    monkeypatch.setattr(runtime, 'Desktop', constructor)
    attach = Mock(return_value={'state': 'starting_runner'})
    monkeypatch.setattr(runtime, 'spawn_runner', attach)
    monkeypatch.setattr(cli, 'App', lambda _: app)
    args = {'workspace': 'sea', 'agent_id': 'alice', 'here': True}
    assert cli.main(['call', 'agent.start', '--arguments', json.dumps(args)]) == 0
    result = json.loads(capsys.readouterr().out)['result']
    current = result['binding']
    assert current != old and result['session'] == 'fixture-user-opened-chat'
    assert result['state'] == 'bound_current_chat' and result['model_profile']['effective'] == 'native_reported'
    context = json.loads(result['prompt'].split('\n\n')[0])
    assert context['entry_mode'] == 'relay' and context['agent'] == 'alice'
    assert context['instance_root'] == str(root) and context['native_cwd'] == str(common)
    assert context['instance_branch'] == 'instance/alice'
    assert 'Keep step two paused; next inspect existing results.' in result['prompt']
    assert (root / 'notes/progress.md').read_text() == 'Step one completed. Step two remains paused.'
    assert (root / 'AGENTS.md').is_file() and (root / '.agents/skills/relay/SKILL.md').is_file()
    assert instance_worktrees.git(root, 'symbolic-ref', '--short', 'HEAD').stdout.decode().strip() == 'instance/alice'
    snap = app.store('sea').snapshot()
    assert snap.json(layout.shared_path(snap, f"handoffs/{handoff['id']}.json"))['consumed_by'] == current
    entry = app.require_binding('sea', 'alice', current)[1]
    assert entry['execution']['directory'] == str(root) and entry['execution']['cwd'] == str(common)
    assert read_json(layout.local_path(root, 'runtime.json'))['caller_thread'] == 'fixture-user-opened-chat'
    assert not list(layout.local_path(root, 'inputs').glob('boot-*.json'))
    peer.create.assert_not_called()
    peer.notify.assert_not_called()
    peer.call.assert_not_called()
    peer.close.assert_called_once()
    attach.assert_called_once_with(app, 'sea', 'alice', str(root), worker_id=None)
    monkeypatch.chdir(common)
    assert runtime.desktop_directory_actor(app) == ('sea', 'alice', current)
    observed = runtime.desktop_observe(app, 'sea', 'alice')
    assert observed['local_session_confirmed'] and observed['native_cwd'] == str(common)
    native['thread']['cwd'] = str(root)
    observed = runtime.desktop_observe(app, 'sea', 'alice')
    assert observed['local_session_confirmed'] and observed['native_cwd'] == str(root)
    native['thread']['cwd'] = str(tmp_path / 'unrelated-project')
    assert not runtime.desktop_observe(app, 'sea', 'alice')['local_session_confirmed']
    monkeypatch.setenv('CODEX_THREAD_ID', 'fixture-old-chat')
    assert cli.main(['-w', 'sea', 'asset', 'write', 'alice', '--path', 'notes/stale.txt', '--content', 'wrong']) == 2
    failure = json.loads(capsys.readouterr().err)
    assert failure['ok'] is False and failure['code'] == 'conflict'
    assert not (root / 'notes/stale.txt').exists()
    assert app.agent('sea', 'alice')['current'] == current


def test_here_rejects_model_mismatch_and_unknown_creation_before_reserving(app, tmp_path, monkeypatch):
    from agent_workspace import layout
    from agent_workspace.util import write_json
    app.create('sea', 'alice')
    root = app.root('sea', 'alice')
    app.configure('sea', 'alice', {'kind': 'desktop', 'command': ['fixture-command'],
                                 'model': 'chosen-model', 'effort': 'low'})
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('CODEX_THREAD_ID', 'fixture-new-chat')
    monkeypatch.setenv('CODEX_APP_TOOLS_PIPE_PATH', 'fixture-pipe')
    peer = Mock()
    peer.read.return_value = {'thread': {'id': 'fixture-new-chat', 'hostId': 'local', 'cwd': str(tmp_path),
                                       'status': {'type': 'idle'}, 'model': 'different-model'}}
    constructor = Mock(return_value=peer)
    monkeypatch.setattr(runtime, 'Desktop', constructor)
    with pytest.raises(Error, match='different model'):
        runtime.start(app, 'sea', 'alice', here=True)
    assert app.agent('sea', 'alice')['current'] is None
    peer.close.assert_called_once()
    binding = app.reserve('sea', 'alice')['binding']
    write_json(layout.local_path(root, 'launch.json'), {'binding': binding, 'attempted': True})
    constructor.reset_mock()
    with pytest.raises(Conflict, match='unresolved'):
        runtime.start(app, 'sea', 'alice', here=True)
    constructor.assert_not_called()
    assert app.agent('sea', 'alice')['current'] == binding


def test_missing_personal_directory_is_prepared_before_capture_and_here_binding(app, tmp_path, monkeypatch):
    import shutil
    from agent_workspace import instance_worktrees, layout
    from agent_workspace.util import write_bytes
    app.create('sea', 'alice')
    root = app.root('sea', 'alice')
    app.configure('sea', 'alice', {'kind': 'desktop', 'model': 'fixture-model', 'effort': 'low'})
    old = app.reserve('sea', 'alice')['binding']
    app.bind('sea', 'alice', old, 'fixture-before-directory-loss')
    write_bytes(root / 'notes/saved.md', b'Recover this saved result')
    point = app.checkpoint('sea', 'alice', 'Saved handoff', 'Next read saved.md', binding=old)
    app.stop('sea', 'alice', old, point['id'])
    app.finish_stop('sea', 'alice', old, observed_idle=True)
    write_bytes(root / 'notes/unsaved.md', b'Not in the saved branch')
    assert root.resolve().is_relative_to(tmp_path.resolve())
    shutil.rmtree(root)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('CODEX_THREAD_ID', 'fixture-user-replacement-chat')
    monkeypatch.setenv('CODEX_APP_TOOLS_PIPE_PATH', 'fixture-replacement-pipe')
    runtime.configure_desktop(app, 'sea', 'alice', command=['fixture-command'])
    assert root.is_dir() and (root / '.git').is_file()
    assert instance_worktrees.git(root, 'symbolic-ref', '--short', 'HEAD').stdout.decode().strip() == 'instance/alice'
    assert (root / 'notes/saved.md').read_bytes() == b'Recover this saved result'
    assert not (root / 'notes/unsaved.md').exists()
    assert app.agent('sea', 'alice')['current'] is None
    # Once restored, a new chat can capture from the old private path; the released one cannot.
    monkeypatch.chdir(root)
    assert runtime.desktop_directory_actor(app, 'agent.capture-desktop') is None
    peer = Mock()
    peer.read.return_value = {'thread': {'id': 'fixture-user-replacement-chat', 'hostId': 'local', 'cwd': str(tmp_path),
                                       'status': {'type': 'active'}}}
    monkeypatch.setattr(runtime, 'Desktop', Mock(return_value=peer))
    monkeypatch.setattr(runtime, 'spawn_runner', Mock(return_value={'state': 'starting_runner'}))
    result = runtime.start(app, 'sea', 'alice', here=True)
    assert result['state'] == 'bound_current_chat' and 'Next read saved.md' in result['prompt']
    assert result['model_profile']['effective'] == 'unconfirmed'
    assert app.require_binding('sea', 'alice', result['binding'])[1]['execution']['cwd'] == str(tmp_path)
    peer.create.assert_not_called()
    peer.notify.assert_not_called()
