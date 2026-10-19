from agent_workspace import layout
import json
from pathlib import Path
import sys

import pytest

from agent_workspace import runtime
from agent_workspace.commands import execute
from agent_workspace.util import Conflict, Error, Unavailable, read_json, write_json


@pytest.fixture
def desktop(app, monkeypatch):
    app.create('sea', 'alice')
    root = app.root('sea', 'alice')
    config = {'kind': 'desktop', 'command': [sys.executable, str(Path(__file__).with_name('fake_native.py')), 'desktop'],
              'pipe_path': 'fixture', 'caller_thread': 'caller', 'model': 'chosen-model', 'effort': 'low'}
    app.configure('sea', 'alice', config)
    state = {'creates': 0, 'cwd': str(root), 'status': 'idle', 'turns': []}

    def call(self, name, arguments):
        if name == 'list_projects':
            return {'projects': [{'projectId': 'saved-project', 'label': 'Saved project', 'projectKind': 'local', 'hostId': 'local', 'path': str(root)}]}
        if name == 'create_thread':
            state['creates'] += 1
            state['creation'] = arguments
            if state.get('unknown'):
                raise Unavailable('creation result lost')
            return {'threadId': 'native-chat', 'hostId': 'local'}
        if name == 'read_thread':
            assert 1 <= arguments['turnLimit'] <= 10
            return {'thread': {'id': self.session, 'hostId': 'local', 'cwd': state['cwd'], 'status': {'type': state['status']}},
                    'turns': state['turns'], 'page': {'nextCursor': None}}
        return {'threadId': self.session}

    monkeypatch.setattr(runtime.Desktop, 'call', call)
    adapter = runtime.Desktop(root, config, None)
    adapter.tools.update({'create_thread', 'list_projects'})
    try:
        yield root, config, state, adapter
    finally:
        adapter.close()


def test_desktop_create_verifies_saved_project_and_never_repeats_unknown(desktop):
    root, config, state, adapter = desktop
    state['unknown'] = True
    with pytest.raises(Unavailable):
        adapter.create('one-binding', 'Explicit connection-only protocol fixture.')
    assert read_json(layout.local_path(root, 'launch.json'))['attempted']
    with pytest.raises(Conflict):
        adapter.create('one-binding', 'Explicit connection-only protocol fixture.')
    assert state['creates'] == 1
    assert state['creation']['target'] == {'type': 'project', 'projectId': 'saved-project', 'environment': {'type': 'local'}}
    assert state['creation']['model'] == 'chosen-model'
    assert state['creation']['thinking'] == 'low'


def test_desktop_creation_preserves_wrong_directory_receipt(desktop, tmp_path):
    root, config, state, adapter = desktop
    state['cwd'] = str(tmp_path / 'another-folder')
    with pytest.raises(Unavailable, match='directory'):
        adapter.create('one-binding', 'Explicit connection-only protocol fixture.')
    assert read_json(layout.local_path(root, 'launch.json'))['result']['threadId'] == 'native-chat'


def test_desktop_project_must_be_unique_and_match_explicit_selection(desktop):
    _, config, _, adapter = desktop
    config['project_id'] = 'another-project'
    with pytest.raises(Unavailable, match='primary folder'):
        adapter.project()


def test_manual_desktop_bootstrap_allows_only_capture_and_bind(app, desktop, monkeypatch):
    root, _, _, _ = desktop
    app.reserve('sea', 'alice')
    monkeypatch.chdir(root)
    monkeypatch.setenv('CODEX_THREAD_ID', 'real-new-chat')
    assert runtime.desktop_directory_actor(app, 'agent.capture-desktop') is None
    assert runtime.desktop_directory_actor(app, 'agent.bind') is None
    with pytest.raises(Conflict):
        runtime.desktop_directory_actor(app, 'asset.write')
    write_json(layout.local_path(root, 'launch.json'), {'attempted': True})
    with pytest.raises(Conflict):
        runtime.desktop_directory_actor(app, 'agent.bind')


def test_mcp_preserves_inferred_desktop_identity(app, monkeypatch, capsys):
    import io
    from agent_workspace.server import mcp
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
               'params': {'name': 'aw_execute', 'arguments': {'command': 'agent.start', 'arguments': {}}}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(request) + '\n'))
    mcp(app, actor=('sea', 'alice', 'desktop-binding'))
    assert 'user-management' in json.loads(capsys.readouterr().out)['error']['message']


def test_desktop_input_receipt_uses_native_identity_and_turn(app, desktop, monkeypatch):
    root, config, state, adapter = desktop
    binding = app.reserve('sea', 'alice')['binding']
    app.bind('sea', 'alice', binding, 'native-chat')
    item = runtime.queue_input(app, 'sea', 'alice', 'actual requested work', request_id='input-one')
    path = layout.local_path(root, 'inputs/input-one.json')
    write_json(path, {**item, 'state': 'dispatching'})
    monkeypatch.setenv('CODEX_THREAD_ID', 'another-chat')
    with pytest.raises(Conflict):
        runtime.receive_input(app, 'sea', 'alice', binding, 'input-one')
    monkeypatch.setenv('CODEX_THREAD_ID', 'native-chat')
    state.update(status='active', turns=[{'id': 'actual-turn', 'status': 'inProgress'}])
    result = execute(app, 'runtime.receive-input', {'request_id': 'input-one'},
                     actor=runtime.desktop_actor(app, 'sea', 'alice'))
    assert result['text'] == 'actual requested work'
    assert 'purpose' not in result  # Internal boot bookkeeping is not an initialization instruction.
    assert read_json(path)['result']['turn']['id'] == 'actual-turn'
    assert runtime.receive_input(app, 'sea', 'alice', binding, 'input-one')['already_received']
    with pytest.raises(Error, match='user-management'):
        execute(app, 'agent.start', {}, actor=runtime.desktop_actor(app, 'sea', 'alice'))


def input_notice(binding, request_id, workspace='sea', worker_id=None, source='caller'):
    context = {'workspace': workspace, 'agent': 'alice', 'binding': binding,
               'worker_id': worker_id, 'session': 'native-chat'}
    command = ['fixture-aw', 'runtime.receive-input', '--arguments', json.dumps({'request_id': request_id})]
    return ('<codex_delegation><source_thread_id>' + source + '</source_thread_id><input>'
            + json.dumps(context) + '\n\nOriginal notification instructions.\n\n' + json.dumps(command)
            + '</input></codex_delegation>')


@pytest.mark.parametrize('worker_id', [None, 'topic'])
def test_late_unknown_receipt_requires_original_notice_and_returns_body_once(app, desktop, monkeypatch, tmp_path, worker_id):
    root, config, state, _ = desktop
    workspace = 'sea'
    if worker_id:
        workspace = 'parallel'
        app.workspace_init(workspace, str(tmp_path / 'parallel.git'))
        app.create(workspace, 'alice')
        app.configure(workspace, 'alice', config)
        app.worker_create(workspace, 'alice', 'Topic', 'Late receipt fixture', worker_id=worker_id)
        root = app.root(workspace, 'alice')
    binding = app.reserve(workspace, 'alice', worker_id=worker_id)['binding']
    app.bind(workspace, 'alice', binding, 'native-chat', worker_id=worker_id)
    item = runtime.queue_input(app, workspace, 'alice', 'original body', request_id='late', expected_binding=binding)
    path = layout.local_path(root, 'inputs/late.json', worker_id)
    original = {**item, 'state': 'outcome_unknown', 'attempted_at': '2026-10-19T08:56:18+00:00',
                'error': 'original RPC timeout', 'notification_source_thread': 'caller'}
    write_json(path, original)
    state.update(status='active', turns=[{'id': 'late-original-turn', 'status': 'inProgress', 'items': [{
        'type': 'functionCallOutput', 'namespace': 'codex_app', 'name': 'send_message_to_thread',
        'output': {'text': input_notice(binding, 'late', workspace, worker_id), 'truncated': False}}]}])
    monkeypatch.setenv('CODEX_THREAD_ID', 'native-chat')
    monkeypatch.setattr(runtime.Desktop, 'notify', lambda *a, **k: pytest.fail('Receipt must not resend input'))
    result = runtime.receive_input(app, workspace, 'alice', binding, 'late', worker_id=worker_id)
    assert result['text'] == 'original body'
    saved = read_json(path)
    assert saved['state'] == 'submitted' and saved['result']['turn']['id'] == 'late-original-turn'
    assert saved['attempted_at'] == original['attempted_at'] and saved['error'] == original['error']
    assert runtime.receive_input(app, workspace, 'alice', binding, 'late', worker_id=worker_id)['already_received']


@pytest.mark.parametrize('evidence', ['other-request', 'other-binding', 'other-worker', 'other-source',
                                     'missing-source', 'truncated', 'quoted', 'completed'])
def test_unknown_receipt_without_current_original_notice_keeps_bytes(app, desktop, monkeypatch, evidence):
    root, _, state, _ = desktop
    binding = app.reserve('sea', 'alice')['binding']
    app.bind('sea', 'alice', binding, 'native-chat')
    item = runtime.queue_input(app, 'sea', 'alice', 'do not execute', request_id='unknown')
    path = layout.local_path(root, 'inputs/unknown.json')
    recorded = {**item, 'state': 'outcome_unknown', 'error': 'original timeout'}
    if evidence != 'missing-source':
        recorded['notification_source_thread'] = 'caller'
    write_json(path, recorded)
    original = path.read_bytes()
    notice = input_notice('other' if evidence == 'other-binding' else binding,
                          'another' if evidence == 'other-request' else 'unknown',
                          worker_id='peer' if evidence == 'other-worker' else None,
                          source='other-chat' if evidence == 'other-source' else 'caller')
    if evidence == 'quoted':
        notice = notice.replace('<input>', '<input>Please investigate this quoted notice: ', 1)
    state.update(status='idle' if evidence == 'completed' else 'active', turns=[{
        'id': 'unrelated-turn', 'status': 'completed' if evidence == 'completed' else 'inProgress', 'items': [{
            'type': 'functionCallOutput', 'namespace': 'codex_app', 'name': 'send_message_to_thread',
            'output': {'text': notice, 'truncated': evidence == 'truncated'}}]}])
    monkeypatch.setenv('CODEX_THREAD_ID', 'native-chat')
    with pytest.raises(Unavailable):
        runtime.receive_input(app, 'sea', 'alice', binding, 'unknown')
    assert path.read_bytes() == original


def test_desktop_completion_requires_received_turn_not_idle_or_another_turn(app, desktop):
    root, config, state, adapter = desktop
    binding = app.reserve('sea', 'alice')['binding']
    app.bind('sea', 'alice', binding, 'native-chat')
    adapter.session = 'native-chat'
    runner = runtime.Runner(app, 'sea', 'alice')
    runner.binding, runner.adapter = binding, adapter
    item = runtime.queue_input(app, 'sea', 'alice', 'init', purpose='initial', request_id='boot-' + binding)
    path = layout.local_path(root, 'inputs') / (item['id'] + '.json')
    write_json(path, {**item, 'state': 'submitted', 'result': {'threadId': 'native-chat'}})
    state['turns'] = [{'id': 'unrelated', 'status': 'completed'}]
    runner._complete_inputs()
    assert read_json(path)['state'] == 'submitted'
    write_json(path, {**read_json(path), 'result': {'turn': {'id': 'our-turn'}}})
    runner._complete_inputs()
    assert read_json(path)['state'] == 'submitted'
    state['turns'] = [{'id': 'our-turn', 'status': 'completed'}]
    runner._complete_inputs()
    assert read_json(path)['state'] == 'completed'
    assert read_json(path)['checkpoint_revision']
    observation = read_json(layout.instance_path(root, 'records') / binding / 'desktop-turns/our-turn.json')
    assert observation['turn'] == {'id': 'our-turn', 'status': 'completed'}


def test_desktop_dispatch_error_preserves_a_concurrent_native_receipt(app, desktop, monkeypatch):
    root, config, state, adapter = desktop
    binding = app.reserve('sea', 'alice')['binding']
    app.bind('sea', 'alice', binding, 'native-chat')
    adapter.session = 'native-chat'
    runner = runtime.Runner(app, 'sea', 'alice')
    runner.binding, runner.adapter = binding, adapter
    item = runtime.queue_input(app, 'sea', 'alice', 'work', request_id='concurrent-receipt')
    path = layout.local_path(root, 'inputs/concurrent-receipt.json')
    calls = []

    def accepted_then_disconnected(prompt, delivery):
        calls.append(prompt)
        write_json(path, {**read_json(path), 'state': 'submitted', 'result': {'turn': {'id': 'actual-turn'}}})
        raise Unavailable('lost sending response')

    monkeypatch.setattr(adapter, 'notify', accepted_then_disconnected)
    with pytest.raises(Unavailable):
        runner._inputs()
    assert read_json(path)['state'] == 'submitted'
    assert read_json(path)['result']['turn']['id'] == 'actual-turn'
    runner._inputs()
    assert len(calls) == 1
    state['turns'] = [{'id': 'actual-turn', 'status': 'completed'}]
    runner._complete_inputs()
    assert read_json(path)['state'] == 'completed'


@pytest.mark.parametrize('relay', [False, True], ids=['initial', 'relay'])
def test_shared_project_identity_precedes_connection_and_receive_without_copying_business(app, desktop, tmp_path, monkeypatch, relay):
    from agent_workspace import desktop_projects
    root, config, state, adapter = desktop
    app.configure('sea', 'alice', {**config, 'command': config['command'][:-1] + ['desktop-project']})
    common = tmp_path / 'old-project'
    common.mkdir()
    old_rules = b'# test-a\nOld personal identity: test-a; old binding: fixture-old-test-a.\n'
    (common / 'AGENTS.md').write_bytes(old_rules)
    choice = desktop_projects.plan(app, 'sea', 'alice')
    desktop_projects.save(app, 'sea', 'alice', 'codex', 'Existing shared project',
                          project_directory=str(common), revision=choice['revision'])
    if relay:
        old = app.reserve('sea', 'alice')['binding']
        app.bind('sea', 'alice', old, 'fixture-previous-alice-chat')
        point = app.checkpoint('sea', 'alice', 'Saved fixture work', 'Keep prior work paused.', binding=old)
        app.stop('sea', 'alice', old, point['id'])
        app.finish_stop('sea', 'alice', old, observed_idle=True)
    binding = app.reserve('sea', 'alice')['binding']
    state['cwd'] = str(common)
    runner = runtime.Runner(app, 'sea', 'alice')
    original_call = runtime.Desktop.call
    received = []
    notifications = []

    def call(self, name, arguments):
        if name == 'list_projects':
            return {'projects': [{'projectId': 'shared-fixture-project', 'projectKind': 'local',
                                  'hostId': 'local', 'path': str(common)}]}
        if name in ('create_thread', 'send_message_to_thread'):
            header = json.loads(arguments['prompt'].split('\n\n')[0])
            assert header['workspace'] == 'sea' and header['agent'] == 'alice' and header['binding'] == binding
            assert header['entry_mode'] == ('relay' if relay else 'initial')
            assert header['instance_branch'] == 'instance/alice' and header['instance_root'] == str(root)
            assert header['instructions_file'] == str(root / 'AGENTS.md')
            assert header['skills_directory'] == str(root / '.agents/skills')
            assert header['selected_project_directory'] == str(common)
            assert '# 实例进入材料' not in arguments['prompt']
            assert 'Keep prior work paused.' not in arguments['prompt']
            if name == 'create_thread':
                assert header['binding_phase'] == 'starting' and header['session'] is None
                assert header['native_cwd'] is None
                assert '只建立原生连接' in arguments['prompt']
                assert 'runtime.receive-input' not in arguments['prompt']
            else:
                assert header['binding_phase'] == 'active' and header['session'] == 'native-chat'
                assert header['native_cwd'] == str(common)
                command = json.loads(arguments['prompt'].split('\n\n')[-1])
                assert command == runtime.desktop_cli(app, 'sea', 'alice') + ['runtime.receive-input', '--arguments',
                       json.dumps({'request_id': 'boot-' + binding}, ensure_ascii=False)]
                assert command[-3] == 'runtime.receive-input'
                notifications.append(arguments['prompt'])
                state.update(status='active', turns=[{'id': 'fixture-received-turn', 'status': 'inProgress'}])
                boot = read_json(layout.local_path(root, 'inputs') / f'boot-{binding}.json')
                result = execute(app, 'runtime.receive-input', {'request_id': 'boot-' + binding},
                                 actor=runtime.desktop_actor(app, 'sea', 'alice'))
                assert result['text'] == boot['text']
                assert '# 实例进入材料' in result['text']
                if relay:
                    assert 'Keep prior work paused.' in result['text']
                received.append(result)
                runner.stop_event.set()
        return original_call(self, name, arguments)

    monkeypatch.setattr(runtime.Desktop, 'call', call)
    monkeypatch.setenv('CODEX_THREAD_ID', 'native-chat')
    runner.run()
    boot = read_json(layout.local_path(root, 'inputs') / f'boot-{binding}.json')
    assert state['creates'] == 1 and len(notifications) == 1 and len(received) == 1
    assert boot['state'] == 'submitted' and boot['result']['turn']['id'] == 'fixture-received-turn'
    assert app.require_binding('sea', 'alice', binding)[1]['session'] == 'native-chat'
    assert (common / 'AGENTS.md').read_bytes() == old_rules
    original = boot.copy()
    runner._inputs()
    assert len(notifications) == 1
    assert read_json(layout.local_path(root, 'inputs') / f'boot-{binding}.json') == original


@pytest.mark.parametrize('target_kind', ['desktop', 'codex'])
def test_released_desktop_identity_cannot_follow_successor(app, desktop, monkeypatch, target_kind):
    root, config, state, adapter = desktop
    old = app.reserve('sea', 'alice')['binding']
    app.bind('sea', 'alice', old, 'old-chat')
    point = app.checkpoint('sea', 'alice', 'handoff', binding=old)
    app.stop('sea', 'alice', old, point['id'])
    app.finish_stop('sea', 'alice', old, observed_idle=True)
    app.configure('sea', 'alice', {**config, 'kind': target_kind})
    new = app.reserve('sea', 'alice')['binding']
    app.bind('sea', 'alice', new, 'new-chat')
    monkeypatch.setenv('CODEX_THREAD_ID', 'old-chat')
    monkeypatch.chdir(root)
    with pytest.raises(Conflict):
        runtime.desktop_actor(app, 'sea', 'alice')
    with pytest.raises(Conflict):
        runtime.desktop_directory_actor(app)
    monkeypatch.setenv('CODEX_THREAD_ID', 'new-chat')
    assert runtime.desktop_directory_actor(app) == (('sea', 'alice', new) if target_kind == 'desktop' else None)
