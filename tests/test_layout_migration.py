from contextlib import ExitStack
import json
import threading

import pytest

from agent_workspace import layout, migration
from agent_workspace.util import Conflict, Error, LockBusy, Uncertain, encode, locked, read_json, write_bytes, write_json
from test_layout_core import legacy_app, publish_unchecked


def confirmation(app):
    planned = app.layout_plan('sea')
    return {'shared_revision': planned['shared_revision'], 'bindings': planned['current_writers'],
            'confirmed': True, 'evidence': 'Fixture: all old writers stopped, no native session launched'}


def receipt(app):
    paths = list((app.home / 'layout-migrations').glob('*/*/operation.json'))
    assert len(paths) == 1
    return paths[0], read_json(paths[0])


def test_migrate_keeps_sealed_facts_user_material_and_unresolved_local_receipts(tmp_path):
    app = legacy_app(tmp_path)
    root = app.root('sea', 'alice')
    sealed = app.checkpoint_show('sea', 'alice', 'c-old')
    store = app.store('sea')
    address = {'workspace': 'local:sea', 'agent': 'alice'}
    message = {'id': 'm-old', 'from': address, 'to': address, 'created_at': '2020-01-01',
               'delivery': 'normal', 'content': 'Original business message'}
    binding = {'id': 'b-old', 'agent': 'alice', 'kind': 'manual', 'phase': 'released',
               'session': 'native-original', 'created_at': '2020-01-01'}
    shared_bytes = {'bindings/b-old.json': encode(binding), 'messages/m-old.json': encode(message),
                    'message-index/m-old.json': encode({key: value for key, value in message.items() if key != 'content'}),
                    'acks/m-old.json': encode({'message_id': 'm-old'})}
    store.change('main', shared_bytes, {path: None for path in shared_bytes}, 'Seed original protocol facts')
    native_record = b'{"method":"turn/start","params":{"threadId":"native-original"}}\n'
    copies = {'records/b-old/runtime.jsonl': native_record,
              'messages/m-old.json': encode({'message_id': 'm-old', 'message': message})}
    store.change('instance/alice', copies, {path: None for path in copies}, 'Save original records')
    app.sync_agent('sea', 'alice')
    write_json(root / '.aw-local/inputs/i-pending.json', {'state': 'outcome_unknown', 'native_result': None})
    write_bytes(root / 'records/user.txt', b'User records')
    write_bytes(root / 'messages/user.txt', b'User messages')
    write_bytes(root / 'channels/user.txt', b'User channels')
    write_json(root / 'runtime.json', {'codex': {'model': 'explicit-model', 'effort': 'none'}})
    write_bytes(root / '.aw/prompts/custom.md', b'Modified platform material')
    result = app.layout_migrate('sea', 'move-all', migrate_shared=True, compatible_writers=confirmation(app))
    assert result['state'] == 'complete'
    assert layout.version(root, 'instance') == 1
    assert layout.version(app.store('sea').snapshot(), 'workspace') == 1
    migrated_shared = store.snapshot()
    for path, data in shared_bytes.items():
        assert migrated_shared.bytes('.agentworkspace/' + path) == data
        assert path not in migrated_shared.entries
    assert layout.instance_path(root, 'records/b-old/runtime.jsonl').read_bytes() == native_record
    assert read_json(layout.instance_path(root, 'messages/m-old.json'))['message'] == message
    for name in ('records', 'messages', 'channels'):
        assert (root / name / 'user.txt').read_bytes() == ('User ' + name).encode()
    assert (root / 'notes/work.md').read_bytes() == b'Original work\n'
    assert layout.instance_path(root, 'prompts/custom.md').read_bytes() == b'Modified platform material'
    assert read_json(layout.instance_path(root, 'config.json'))['codex']['effort'] == 'none'
    assert read_json(layout.local_path(root, 'inputs/i-pending.json'))['state'] == 'outcome_unknown'
    assert app.checkpoint_show('sea', 'alice', 'c-old') == sealed
    fork = app.fork('sea', 'alice', 'c-old', 'bob')
    forkroot = app.root('sea', fork['id'])
    assert layout.version(forkroot, 'instance') == 1
    assert read_json(layout.instance_path(forkroot, 'identity.json'))['forked_from']['revision'] == sealed['revision']
    assert not layout.local_path(forkroot, 'inputs/i-pending.json').exists()
    write_bytes(root / 'notes/work.md', b'New user work after migration')
    assert app.layout_migrate('sea', 'move-all', migrate_shared=True, compatible_writers=None)['state'] == 'complete'
    assert (root / 'notes/work.md').read_bytes() == b'New user work after migration'
    with pytest.raises(Conflict):
        app.layout_migrate('sea', 'move-all', agent_ids=['alice'], migrate_shared=True)


def test_shared_migration_requires_exact_writer_confirmation_before_side_effects(tmp_path):
    app = legacy_app(tmp_path)
    store = app.store('sea'); before = store.head('main')
    evidence = confirmation(app); evidence['shared_revision'] = 'stale'
    with pytest.raises(Conflict):
        app.layout_migrate('sea', 'wrong-writers', migrate_shared=True, compatible_writers=evidence)
    assert store.head('main') == before
    assert not (app.root('sea', 'alice') / layout.MARKER).exists()
    assert not list((app.home / 'layout-migrations').glob('*/*/operation.json'))


@pytest.mark.parametrize('name', ['runner.lock', 'files.lock'])
def test_real_lock_appears_after_plan_no_move_then_original_request_resumes(tmp_path, monkeypatch, name):
    app = legacy_app(tmp_path); root = app.root('sea', 'alice'); store = app.store('sea')
    original_head = store.head('instance/alice')
    original = migration._publish
    held = ExitStack()
    def publish(*args):
        original(*args)
        # The plan was made while idle. A real writer starts after actual Git publication.
        held.enter_context(locked(root / '.aw-local' / name, wait=0))
    monkeypatch.setattr(migration, '_publish', publish)
    try:
        with pytest.raises(LockBusy):
            app.layout_migrate('sea', 'lock-race')
        assert store.head('instance/alice') != original_head
        assert (root / '.aw/identity.json').exists()
        assert not (root / layout.MARKER).exists()
        assert not (root / '.agentworkspace/identity.json').exists()
        _, saved = receipt(app)
        assert saved['state'] == 'pending' and saved['tasks'][0]['published']
        pending = app.layout_plan('sea')['pending_migrations']
        assert pending[0]['request_id'] == 'lock-race' and pending[0]['branches'][0]['published']
        assert 'moves' not in pending[0]['directories'][0]
        with pytest.raises(Conflict):
            app.layout_migrate('sea', 'bypass-busy')
    finally:
        held.close()
    monkeypatch.setattr(migration, '_publish', original)
    assert app.layout_migrate('sea', 'lock-race')['state'] == 'complete'
    assert layout.version(root, 'instance') == 1


def test_waiting_old_writer_rechecks_layout_and_uses_new_mutex(tmp_path, monkeypatch):
    root = tmp_path / 'root'
    entered = threading.Event(); acquired = threading.Event(); finished = threading.Event(); errors = []
    original = layout.locked
    def observed(path, **kwargs):
        if threading.current_thread().name == 'old-writer':
            entered.set()
        return original(path, **kwargs)
    monkeypatch.setattr(layout, 'locked', observed)
    def writer():
        try:
            with layout.lock(root, 'files.lock', wait=3):
                acquired.set()
                write_bytes(layout.local_path(root, 'entry.json'), b'new-path')
        except Exception as exc:
            errors.append(exc)
        finally:
            finished.set()
    old_lock = ExitStack()
    old_lock.enter_context(locked(root / '.aw-local/files.lock'))
    try:
        thread = threading.Thread(target=writer, name='old-writer'); thread.start()
        assert entered.wait(2)
        write_bytes(root / layout.MARKER, layout.marker('instance'))
        with locked(root / '.agentworkspace/local/runtime/files.lock'):
            old_lock.close()
            assert not acquired.wait(0.15)
    finally:
        old_lock.close()
    thread.join(4)
    assert finished.is_set() and not errors and acquired.is_set()
    assert layout.local_path(root, 'entry.json').read_bytes() == b'new-path'
    assert not (root / '.aw-local/entry.json').exists()


def test_write_phase_holds_old_and_new_locks_and_blocks_marker_access(tmp_path, monkeypatch):
    app = legacy_app(tmp_path); root = app.root('sea', 'alice')
    original = migration.write_bytes; observed = []
    def write(path, data):
        if path == root / '.agentworkspace/identity.json':
            with pytest.raises(layout.MigrationRequired):
                layout.local_path(root, 'entry.json')
            for base in (root / '.aw-local', root / '.agentworkspace/local/runtime'):
                for name in ('runner.lock', 'files.lock'):
                    with pytest.raises(LockBusy):
                        with locked(base / name, wait=0):
                            pass
            observed.append(True)
        original(path, data)
    monkeypatch.setattr(migration, 'write_bytes', write)
    assert app.layout_migrate('sea', 'held-entire-copy')['state'] == 'complete'
    assert observed
    assert (root / '.aw-local/runner.lock').stat().st_size == 0
    assert not any(move['source'] and move['source'].endswith('.lock') for move in receipt(app)[1]['roots'][0]['moves'])


@pytest.mark.parametrize('published', [False, True])
def test_unknown_publication_is_never_replayed_and_real_commit_is_read_back(tmp_path, monkeypatch, published):
    app = legacy_app(tmp_path); store = app.store('sea'); original = store.publish; calls = []
    # App.store constructs stores, so instrument the shared implementation.
    implementation = type(store).publish
    def lost(self, *args, **kwargs):
        calls.append(args)
        if published:
            implementation(self, *args, **kwargs)
        raise Uncertain('Fixture: reply lost, original publication outcome unknown')
    monkeypatch.setattr(type(store), 'publish', lost)
    with pytest.raises(Uncertain):
        app.layout_migrate('sea', 'lost-reply')
    assert len(calls) == 1
    monkeypatch.setattr(type(store), 'publish', implementation)
    if published:
        later = store.change('instance/alice', {'later-user-work.md': b'Later legitimate change'},
                             {'later-user-work.md': None}, 'Later work after original publication')
        assert app.layout_migrate('sea', 'lost-reply')['state'] == 'complete'
        assert store.head('instance/alice') == later
    else:
        with pytest.raises(Uncertain):
            app.layout_migrate('sea', 'lost-reply')
        with pytest.raises(Conflict):
            app.layout_migrate('sea', 'another-request')
    assert len(calls) == 1


def test_file_copy_interruption_preserves_unknown_receipts_and_resumes_original(tmp_path, monkeypatch):
    app = legacy_app(tmp_path); root = app.root('sea', 'alice')
    write_json(root / '.aw-local/transfer.json', {'state': 'outcome_unknown', 'request_id': 'original-native-operation'})
    original = migration.write_bytes; failed = []
    def write(path, data):
        original(path, data)
        if path == root / '.agentworkspace/identity.json' and not failed:
            failed.append(True)
            raise OSError('Fixture: process failed after durable destination copy')
    monkeypatch.setattr(migration, 'write_bytes', write)
    with pytest.raises(OSError):
        app.layout_migrate('sea', 'copy-crash')
    assert (root / '.aw/identity.json').exists()
    assert (root / '.agentworkspace/identity.json').exists()
    with pytest.raises(layout.MigrationRequired):
        app.configure('sea', 'alice', {'kind': 'manual'})
    pending = app.layout_plan('sea')['pending_migrations']
    assert pending[0]['request_id'] == 'copy-crash' and not pending[0]['directories'][0]['complete']
    monkeypatch.setattr(migration, 'write_bytes', original)
    assert app.layout_migrate('sea', 'copy-crash')['state'] == 'complete'
    assert read_json(layout.local_path(root, 'transfer.json'))['request_id'] == 'original-native-operation'


def test_source_change_between_plan_and_copy_stops_before_first_move(tmp_path, monkeypatch):
    app = legacy_app(tmp_path); root = app.root('sea', 'alice'); original = migration._publish
    def publish(*args):
        original(*args)
        write_bytes(root / '.aw/prompts/user.md', b'late unplanned local platform write')
        write_bytes(root / '.aw/software.json', encode({'version': 'user-changed', 'files': {}}))
    monkeypatch.setattr(migration, '_publish', publish)
    with pytest.raises(Conflict):
        app.layout_migrate('sea', 'source-changed')
    assert not (root / layout.MARKER).exists()
    assert (root / '.aw/identity.json').exists()
    assert read_json(root / '.aw/software.json')['version'] == 'user-changed'


def test_accidentally_tracked_private_blob_is_archived_never_used_as_runtime_state(tmp_path):
    app = legacy_app(tmp_path); store = app.store('sea'); root = app.root('sea', 'alice')
    leaked = b'{"pipe_path":"foreign-machine","credential_ref":"fixture-only"}'
    publish_unchecked(store, 'instance/alice', {'.aw-local/runtime.json': leaked}, tmp_path)
    # The original local context still pins the same portable branch contents.
    assert app.layout_migrate('sea', 'remove-leaked-local')['state'] == 'complete'
    snap = store.snapshot('instance/alice')
    assert not any(path.startswith(('.aw-local/', '.agentworkspace/local/')) for path in snap.entries)
    assert not layout.local_path(root, 'runtime.json').exists()
    archived = root / '.agentworkspace/local/operations/legacy-tracked/.aw-local/runtime.json'
    assert archived.read_bytes() == leaked


def test_owned_records_need_real_shared_receipts_and_user_names_are_preserved(tmp_path):
    app = legacy_app(tmp_path); store = app.store('sea'); shared = store.snapshot()
    binding = {'id': 'b-old', 'agent': 'alice'}
    shared_change = {'bindings/b-old.json': encode(binding)}
    store.change('main', shared_change, {path: None for path in shared_change}, 'Seed recorded Binding')
    shared = store.snapshot()
    files = {'records/b-old/runtime.jsonl': b'{"method":"turn/start"}\n',
             'records/user/runtime.jsonl': b'{"method":"turn/start"}\n',
             'messages/business.json': b'{"message_id":"business","message":{"note":"user"}}',
             'channels/team/business.json': b'{"text":"user"}'}
    owned = migration.owned_instance_files(files, shared, 'alice')
    assert owned == {'records/b-old/runtime.jsonl'}
    projected, mapping, unknown = migration.instance_files(files, owned=owned)
    assert mapping == {'records/b-old/runtime.jsonl': '.agentworkspace/records/b-old/runtime.jsonl'}
    assert set(unknown) == set(files) - owned
    assert all(projected[path] == files[path] for path in unknown)


def test_ready_marker_reply_failure_does_not_restore_over_new_work(tmp_path, monkeypatch):
    app = legacy_app(tmp_path); root = app.root('sea', 'alice')
    original = migration.write_bytes; failed = []
    def write(path, data):
        original(path, data)
        if path == root / layout.MARKER and json.loads(data).get('state', 'ready') == 'ready' and not failed:
            failed.append(True)
            raise OSError('Fixture: ready marker persisted, reply lost')
    monkeypatch.setattr(migration, 'write_bytes', write)
    with pytest.raises(OSError):
        app.layout_migrate('sea', 'ready-reply-lost')
    assert layout.version(root, 'instance') == 1
    write_bytes(root / 'notes/work.md', b'User work after ready')
    app.configure('sea', 'alice', {'kind': 'manual', 'connection': 'new local choice'})
    monkeypatch.setattr(migration, 'write_bytes', original)
    assert app.layout_migrate('sea', 'ready-reply-lost')['state'] == 'complete'
    assert (root / 'notes/work.md').read_bytes() == b'User work after ready'
    assert read_json(layout.local_path(root, 'runtime.json'))['connection'] == 'new local choice'


def test_pending_software_operation_is_preserved_without_starting_migration(tmp_path):
    app = legacy_app(tmp_path); root = app.root('sea', 'alice'); store = app.store('sea')
    before = store.head('instance/alice')
    write_json(root / '.aw-local/software-update.json', {'state': 'pending', 'id': 'original-update'})
    with pytest.raises(Conflict):
        app.layout_migrate('sea', 'pending-software')
    assert store.head('instance/alice') == before
    assert read_json(root / '.aw-local/software-update.json')['id'] == 'original-update'
    assert not (root / layout.MARKER).exists()


def test_unknown_marker_after_plan_is_not_replaced_by_original_request(tmp_path, monkeypatch):
    app = legacy_app(tmp_path); root = app.root('sea', 'alice'); original = migration._publish
    marker = {'kind': 'instance', 'version': 99, 'migration': 'future-marker'}
    def publish(*args):
        original(*args)
        write_json(root / layout.MARKER, marker)
    monkeypatch.setattr(migration, '_publish', publish)
    with pytest.raises(Error):
        app.layout_migrate('sea', 'future-marker')
    assert read_json(root / layout.MARKER) == marker
    assert (root / '.aw/identity.json').exists()
    assert receipt(app)[1]['tasks'][0]['published']
