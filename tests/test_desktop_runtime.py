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
            return {'thread': {'id': self.session, 'cwd': state['cwd'], 'status': {'type': state['status']}},
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
        adapter.create('one-binding')
    assert read_json(root / '.aw-local/launch.json')['attempted']
    with pytest.raises(Conflict):
        adapter.create('one-binding')
    assert state['creates'] == 1
    assert state['creation']['target'] == {'type': 'project', 'projectId': 'saved-project', 'environment': {'type': 'local'}}
    assert state['creation']['model'] == 'chosen-model'
    assert state['creation']['thinking'] == 'low'


def test_desktop_creation_preserves_wrong_directory_receipt(desktop, tmp_path):
    root, config, state, adapter = desktop
    state['cwd'] = str(tmp_path / 'another-folder')
    with pytest.raises(Unavailable, match='directory'):
        adapter.create('one-binding')
    assert read_json(root / '.aw-local/launch.json')['result']['threadId'] == 'native-chat'


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
    write_json(root / '.aw-local/launch.json', {'attempted': True})
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
    path = root / '.aw-local/inputs/input-one.json'
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


def test_desktop_completion_requires_received_turn_not_idle_or_another_turn(app, desktop):
    root, config, state, adapter = desktop
    binding = app.reserve('sea', 'alice')['binding']
    app.bind('sea', 'alice', binding, 'native-chat')
    adapter.session = 'native-chat'
    runner = runtime.Runner(app, 'sea', 'alice')
    runner.binding, runner.adapter = binding, adapter
    item = runtime.queue_input(app, 'sea', 'alice', 'init', purpose='initial', request_id='boot-' + binding)
    path = root / '.aw-local/inputs' / (item['id'] + '.json')
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
    observation = read_json(root / 'records' / binding / 'desktop-turns/our-turn.json')
    assert observation['turn'] == {'id': 'our-turn', 'status': 'completed'}


def test_desktop_dispatch_error_preserves_a_concurrent_native_receipt(app, desktop, monkeypatch):
    root, config, state, adapter = desktop
    binding = app.reserve('sea', 'alice')['binding']
    app.bind('sea', 'alice', binding, 'native-chat')
    adapter.session = 'native-chat'
    runner = runtime.Runner(app, 'sea', 'alice')
    runner.binding, runner.adapter = binding, adapter
    item = runtime.queue_input(app, 'sea', 'alice', 'work', request_id='concurrent-receipt')
    path = root / '.aw-local/inputs/concurrent-receipt.json'
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
