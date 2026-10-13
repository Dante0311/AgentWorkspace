"""Exercise real layout mutexes with a controlled old-to-ready path switch.

These tests make no native calls. The marker switch is a filesystem fixture;
Core's separate migration tests exercise actual migration publication/copy.
"""
from contextlib import ExitStack
from types import SimpleNamespace
import threading

import pytest

from agent_workspace import bridges, desktop_projects, layout, runtime, transfer
from agent_workspace.util import digest, encode, locked, read_json, write_bytes, write_json


@pytest.mark.parametrize('case', ['queue-new', 'queue-unknown', 'receive-existing',
                                  'bridge-unknown', 'bridge-config', 'desktop-save',
                                  'desktop-prepared', 'transfer-complete', 'watch-stop', 'native-record'])
def test_waiting_operation_joins_current_layout_and_retains_original_receipts(tmp_path, monkeypatch, case):
    root = tmp_path / 'instance'
    app = SimpleNamespace(home=tmp_path / 'home',
                          root=lambda *a, **k: root,
                          agent=lambda *a, **k: {'current': 'b-original'},
                          require_binding=lambda *a, **k: None)
    source = root / '.aw-local'
    lock_name = 'files.lock'
    unknown = {'id': 'i-original', 'binding': 'b-original', 'text': 'original input',
               'delivery': 'normal', 'purpose': 'user', 'sequence': 7,
               'state': 'outcome_unknown', 'native_result': None}
    write_json(source / 'inputs/i-original.json', unknown)
    original_bytes = (source / 'inputs/i-original.json').read_bytes()
    write_json(source / 'input-sequence.json', 7)
    if case.startswith('queue-'):
        lock_name = 'inputs.lock'
        request = 'i-original' if case == 'queue-unknown' else 'i-new'
        action = lambda: runtime.queue_input(app, 'sea', 'alice', 'original input', request_id=request)
    elif case == 'receive-existing':
        monkeypatch.setattr(runtime, 'desktop_actor', lambda *a: ('sea', 'alice', 'b-original'))
        item = {**unknown, 'state': 'submitted', 'result': {'turn': {'id': 'original-turn'}}}
        write_json(source / 'inputs/i-received.json', item)
        action = lambda: runtime.receive_input(app, 'sea', 'alice', 'b-original', 'i-received')
    elif case == 'bridge-unknown':
        write_json(source / 'bridges/team.json', {'enabled': True})
        record = {'id': 's-original', 'binding': 'b-original', 'bridge': 'team',
                  'target': 'original-target', 'text': 'original send', 'state': 'outcome_unknown'}
        write_json(source / 'bridge-sends/s-original.json', record)
        action = lambda: bridges.send(app, 'sea', 'alice', 'b-original', 'team',
                                     'original-target', 'original send', request_id='s-original')
    elif case == 'bridge-config':
        write_json(source / 'bridges/team.json', {'generation': 'g-original', 'enabled': True})
        action = lambda: bridges.configure(app, 'sea', 'alice', 'team', {'command': ['fixture'], 'enabled': False},
                                          expected_generation='g-original')
    elif case == 'desktop-save':
        prefs = encode({'project_name': 'original', 'section_name': 'sea', 'product_paths': [],
                        'native_project_id': 'original-project'})
        write_bytes(source / 'desktop-projects/codex.json', prefs)
        action = lambda: desktop_projects.save(app, 'sea', 'alice', 'codex', 'renamed', revision=digest(prefs))
    elif case == 'desktop-prepared':
        fingerprint = {'project_id': None, 'section_id': None, 'create_section': False, 'revision': None}
        write_json(source / 'desktop-preparations/p-original.json',
                   {'request': fingerprint, 'state': 'completed', 'result': {'native_project_id': 'original-project'}})
        action = lambda: desktop_projects.prepare(app, 'sea', 'alice', 'p-original')
    elif case == 'transfer-complete':
        lock_name = 'transfer.lock'
        write_json(source / 'transfer.json', {'id': 't-original', 'target_binding': 'b-original', 'state': 'starting'})
        write_json(source / 'inputs/boot-b-original.json',
                   {'binding': 'b-original', 'state': 'completed', 'checkpoint_revision': 'original-revision'})
        action = lambda: transfer.persist_completion(root, {'id': 'b-original', 'session': 'original-session', 'phase': 'active'})
    elif case == 'native-record':
        lock_name = 'records.lock'
        adapter = runtime.Codex.__new__(runtime.Codex)
        adapter.root, adapter.binding = root, 'b-original'
        adapter.record = root / 'records/b-original/runtime.jsonl'
        write_bytes(adapter.record, b'original-record\n')
        action = lambda: adapter.event({'method': 'fixture-record', 'params': {}})
    else:
        write_json(source / 'watch.json', {'enabled': True, 'binding': 'b-original'})
        action = lambda: runtime.watch(app, 'sea', 'alice', 'stop')

    attempted = threading.Event()
    finished = threading.Event()
    results, errors = [], []
    real_locked = layout.locked
    def observed(path, **kwargs):
        if threading.current_thread().name == 'waiting-operation':
            attempted.set()
        return real_locked(path, **kwargs)
    monkeypatch.setattr(layout, 'locked', observed)
    def operate():
        try:
            results.append(action())
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()

    old_mutex = ExitStack()
    old_mutex.enter_context(locked(source / lock_name))
    thread = threading.Thread(target=operate, name='waiting-operation', daemon=True)
    try:
        thread.start()
        assert attempted.wait(2)
        with locked(root / '.agentworkspace/local' / layout.local_relpath(lock_name)):
            for path in list(source.rglob('*.json')):
                write_bytes(root / '.agentworkspace/local' / layout.local_relpath(path.relative_to(source).as_posix()),
                            path.read_bytes())
                path.unlink()
            if case == 'native-record':
                write_bytes(root / '.agentworkspace/records/b-original/runtime.jsonl', adapter.record.read_bytes())
                adapter.record.unlink()
            write_bytes(root / layout.MARKER, layout.marker('instance'))
            old_mutex.close()
            assert not finished.wait(0.15), 'A stale waiter bypassed the current layout mutex.'
    finally:
        old_mutex.close()
        thread.join(5)
    assert finished.is_set() and not errors, errors
    assert not list(source.rglob('*.json')), 'Operation recreated state in the retired local layout.'
    assert layout.local_path(root, 'inputs/i-original.json').read_bytes() == original_bytes
    if case == 'queue-new':
        assert results[0]['sequence'] == 8
        assert read_json(layout.local_path(root, 'inputs/i-new.json'))['state'] == 'queued'
    elif case == 'queue-unknown':
        assert results[0] == unknown and read_json(layout.local_path(root, 'input-sequence.json')) == 7
    elif case == 'receive-existing':
        assert results[0]['already_received'] is True
        assert read_json(layout.local_path(root, 'inputs/i-received.json')) == item
    elif case == 'bridge-unknown':
        assert results[0] == record
        assert read_json(layout.local_path(root, 'bridge-sends/s-original.json')) == record
    elif case == 'bridge-config':
        assert read_json(layout.local_path(root, 'bridges/team.json'))['enabled'] is False
    elif case in ('desktop-save', 'desktop-prepared'):
        if case == 'desktop-save':
            prefs = read_json(layout.local_path(root, 'desktop-projects/codex.json'))
            assert prefs['project_name'] == 'renamed' and prefs['native_project_id'] == 'original-project'
        else:
            assert results[0] == {'native_project_id': 'original-project'}
    elif case == 'transfer-complete':
        result = read_json(layout.local_path(root, 'transfer.json'))
        assert result['state'] == 'completed' and result['id'] == 't-original'
        assert result['session'] == 'original-session'
    elif case == 'native-record':
        assert not (root / 'records/b-original/runtime.jsonl').exists()
        record = layout.instance_path(root, 'records/b-original/runtime.jsonl').read_bytes()
        assert record.startswith(b'original-record\n') and b'fixture-record' in record
    else:
        assert read_json(layout.local_path(root, 'watch.json'))['enabled'] is False


@pytest.mark.parametrize('operation', ['input', 'watch', 'bridge'])
def test_pending_migration_refuses_local_writes(tmp_path, operation):
    write_json(tmp_path / layout.MARKER, {'version': 1, 'kind': 'instance', 'state': 'pending'})
    app = SimpleNamespace(root=lambda *a, **k: tmp_path, agent=lambda *a, **k: {'current': 'b-original'},
                          require_binding=lambda *a, **k: None)
    with pytest.raises(layout.MigrationRequired):
        if operation == 'input':
            runtime.queue_input(app, 'sea', 'alice', 'original input', request_id='i-original')
        elif operation == 'watch':
            runtime.watch(app, 'sea', 'alice', 'stop')
        else:
            bridges.configure(app, 'sea', 'alice', 'team', {'command': ['fixture']})
    assert not (tmp_path / '.aw-local').exists()
    assert not (tmp_path / '.agentworkspace/local').exists()
