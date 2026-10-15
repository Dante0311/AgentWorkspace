from contextlib import ExitStack
import json
from pathlib import Path
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
        if name == 'runner.lock':
            migrated_head = store.head('instance/alice')
            with pytest.raises(Conflict):
                app.checkpoint('sea', 'alice', 'old copy must not append legacy data', checkpoint_id='c-stale-layout')
            assert store.head('instance/alice') == migrated_head
            assert not (root / '.aw/checkpoints/c-stale-layout.json').exists()
            with pytest.raises(layout.MigrationRequired):
                app.sync_agent('sea', 'alice')
            assert not (root / layout.MARKER).exists()
            assert (root / '.aw-local/context.json').exists()
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


def _desktop_binding(app, identifier='b-desktop', agent='alice', kind='desktop', session='native-original'):
    store = app.store('sea')
    value = {'id': identifier, 'agent': agent, 'kind': kind, 'session': session,
             'phase': 'released', 'created_at': '2020-01-01'}
    path = 'bindings/' + identifier + '.json'
    store.change('main', {path: encode(value)}, {path: None}, 'Recorded historic Binding')


def _desktop_record(turn='turn-original', session='native-original'):
    return {'source': 'Codex Desktop read_thread', 'thread_id': session, 'observed_at': '2020-01-01T00:00:00Z',
            'turn': {'id': turn, 'status': 'completed', 'error': None, 'startedAt': 1, 'completedAt': 2, 'durationMs': 1000},
            'scope': 'Native turn metadata only; message and tool bodies remain in Desktop.'}


@pytest.mark.parametrize('tracked', [True, False], ids=['saved-record', 'unsynchronized-local-record'])
@pytest.mark.parametrize('metadata', ['full', 'id-only'])
def test_legacy_desktop_record_is_planned_and_moved_without_rewriting_bytes(tmp_path, tracked, metadata):
    app = legacy_app(tmp_path); store = app.store('sea'); root = app.root('sea', 'alice')
    _desktop_binding(app)
    path = 'records/b-desktop/desktop-turns/turn-original.json'
    target = '.agentworkspace/' + path
    document = _desktop_record()
    if metadata == 'id-only':
        document['turn'] = {'id': 'turn-original'}
    raw = (json.dumps(document, indent=4) + '\r\n').encode()
    user_path = 'records/b-desktop/desktop-turns/user-notes.json'
    user = b'{"topic":"Private user material"}\n'
    if tracked:
        store.change('instance/alice', {path: raw, user_path: user}, {path: None, user_path: None}, 'Save original records')
        app.sync_agent('sea', 'alice')
        point = app.checkpoint('sea', 'alice', 'saved Desktop metadata', checkpoint_id='c-desktop', references=[path])
    else:
        write_bytes(root / path, raw); write_bytes(root / user_path, user)
        point = app.checkpoint_show('sea', 'alice', 'c-old')
    sealed = app.checkpoint_show('sea', 'alice', point['id'])
    planned = app.layout_plan('sea')['instances'][0]
    assert path in planned['owned_records']
    assert user_path not in planned['owned_records']
    assert planned['paths'].get(path) == (target if tracked else None)
    result = app.layout_migrate('sea', 'desktop-records')
    assert result['state'] == 'complete'
    assert (root / target).read_bytes() == raw
    assert not (root / path).exists()
    assert (root / user_path).read_bytes() == user
    current = store.snapshot('instance/alice')
    if tracked:
        assert current.bytes(target) == raw and path not in current.entries
        assert store.snapshot(revision=point['revision']).bytes(path) == raw
    else:
        assert target not in current.entries  # Local discovery is not a publication of unsaved data.
    assert app.checkpoint_show('sea', 'alice', point['id']) == sealed


def test_unmatched_desktop_json_and_unknown_fields_are_kept_in_place(tmp_path):
    app = legacy_app(tmp_path); root = app.root('sea', 'alice')
    _desktop_binding(app); _desktop_binding(app, 'b-other', agent='bob'); _desktop_binding(app, 'b-codex', kind='codex')
    store = app.store('sea')
    store.change('main', {'bindings/not-the-record-id.json': encode({
        'id': 'b-fake-registry', 'agent': 'alice', 'kind': 'desktop', 'session': 'native-original'})},
        {'bindings/not-the-record-id.json': None}, 'Unregistered copied Binding fields')
    changed = []
    for label, update in [('wrong-source', {'source': 'User note'}), ('wrong-session', {'thread_id': 'another-session'}),
                          ('wrong-scope', {'scope': 'Private user material'}), ('no-observation', {'observed_at': None}),
                          ('extra-user-content', {'user_note': 'mine'})]:
        doc = _desktop_record(label); doc.update(update)
        changed.append(('records/b-desktop/desktop-turns/' + label + '.json', doc))
    doc = _desktop_record('wrong-turn'); doc['turn']['id'] = 'different-id'
    changed.append(('records/b-desktop/desktop-turns/wrong-turn.json', doc))
    doc = _desktop_record('user-turn-field'); doc['turn']['user_note'] = 'mine'
    changed.append(('records/b-desktop/desktop-turns/user-turn-field.json', doc))
    changed.extend([('records/b-other/desktop-turns/foreign-agent.json', _desktop_record('foreign-agent')),
                    ('records/b-unknown/desktop-turns/no-binding.json', _desktop_record('no-binding')),
                    ('records/b-codex/desktop-turns/wrong-kind.json', _desktop_record('wrong-kind')),
                    ('records/b-fake-registry/desktop-turns/wrong-registration.json', _desktop_record('wrong-registration'))])
    original = {path: encode(doc) for path, doc in changed}
    for path, data in original.items():write_bytes(root / path, data)
    assert app.layout_migrate('sea', 'keep-user-json')['state'] == 'complete'
    for path, data in original.items():
        assert (root / path).read_bytes() == data
        assert not (root / '.agentworkspace' / path).exists()


def test_saved_desktop_record_does_not_claim_a_locally_replaced_user_json(tmp_path):
    app = legacy_app(tmp_path); store = app.store('sea'); root = app.root('sea', 'alice')
    _desktop_binding(app)
    path = 'records/b-desktop/desktop-turns/turn-original.json'
    original = encode(_desktop_record())
    store.change('instance/alice', {path: original}, {path: None}, 'Original saved platform record')
    app.sync_agent('sea', 'alice')
    user = b'{"topic":"User replaced this old record locally"}'
    write_bytes(root / path, user)
    result = app.layout_migrate('sea', 'preserve-local-user-edit')
    assert (root / path).read_bytes() == user
    assert not (root / '.agentworkspace' / path).exists()
    assert path in result['unclassified_local_files'][str(root)]
    assert store.snapshot('instance/alice').bytes('.agentworkspace/' + path) == original


def _completed_without_desktop(tmp_path, monkeypatch, *, tracked=True):
    app = legacy_app(tmp_path); store = app.store('sea'); root = app.root('sea', 'alice')
    _desktop_binding(app)
    records = {}
    for turn in ('full-turn', 'id-only-turn'):
        document = _desktop_record(turn)
        if turn == 'id-only-turn':
            document['turn'] = {'id': turn}
        records['records/b-desktop/desktop-turns/' + turn + '.json'] = (json.dumps(document, indent=4) + '\r\n').encode()
    if tracked:
        store.change('instance/alice', records, {path: None for path in records}, 'Original Desktop metadata')
        app.sync_agent('sea', 'alice')
    else:
        for path, data in records.items():
            write_bytes(root / path, data)
    original = migration.owned_instance_files
    with monkeypatch.context() as injection:
        # Reproduce the original recognizer's omission, only in this isolated fixture.
        injection.setattr(migration, 'owned_instance_files',
                          lambda *args, **kwargs: {path for path in original(*args, **kwargs) if '/desktop-turns/' not in path})
        result = app.layout_migrate('sea', 'original-completed-layout')
    old_receipt = Path(result['receipt'])
    return app, root, store, records, old_receipt, old_receipt.read_bytes()


@pytest.mark.parametrize('tracked', [True, False], ids=['saved-records', 'unsynchronized-records'])
def test_current_layout_supplements_only_proven_desktop_records(tmp_path, monkeypatch, tracked):
    app, root, store, records, old_receipt, old_bytes = _completed_without_desktop(tmp_path, monkeypatch, tracked=tracked)
    marker = (root / layout.MARKER).read_bytes(); shared_revision = store.head('main')
    old_checkpoint = app.checkpoint_show('sea', 'alice', 'c-old')
    untouched = {'records/user.json': b'{"private":"User document"}',
                 '.agentworkspace/local/runtime/runtime.json': b'{"native_result":"outcome_unknown"}',
                 '.gitignore': b'# User changed ignore after migration\n',
                 'notes/work.md': b'Unsaved user work'}
    for path, data in untouched.items():
        write_bytes(root / path, data)
    plan = app.layout_plan('sea')['instances'][0]
    assert plan['layout_version'] == 1
    assert plan['paths'] == ({path: '.agentworkspace/' + path for path in records} if tracked else {})
    assert set(records) <= set(plan['owned_records'])
    app.layout_migrate('sea', 'original-completed-layout')
    assert old_receipt.read_bytes() == old_bytes and all((root / path).exists() for path in records)
    result = app.layout_migrate('sea', 'desktop-supplement')
    assert result['state'] == 'complete' and result['directories'] == [str(root)]
    assert len(result['branches']) == (1 if tracked else 0)
    current = store.snapshot('instance/alice')
    for path, data in records.items():
        assert not (root / path).exists()
        assert (root / '.agentworkspace' / path).read_bytes() == data
        assert current.bytes('.agentworkspace/' + path) == (data if tracked else None)
        assert path not in current.entries
    assert (root / layout.MARKER).read_bytes() == marker
    assert current.bytes(layout.MARKER) == marker
    assert old_receipt.read_bytes() == old_bytes
    assert store.head('main') == shared_revision
    assert app.checkpoint_show('sea', 'alice', 'c-old') == old_checkpoint
    for path, data in untouched.items():
        assert (root / path).read_bytes() == data
    operation = read_json(Path(result['receipt']))
    assert operation['layout_sources'][0]['marker']['migration'] == 'original-completed-layout'
    assert operation['roots'][0]['marker_before'] == operation['roots'][0]['marker']
    context = read_json(layout.local_path(root, 'context.json'))
    assert context['revision'] == current.revision
    assert context['saved'] == {path: migration.digest(data) for path, data in current.all().items()}
    before = current.revision
    again = app.layout_migrate('sea', 'nothing-remains')
    assert again['branches'] == [] and again['directories'] == []
    assert store.head('instance/alice') == before
    assert old_receipt.read_bytes() == old_bytes


@pytest.mark.parametrize('same', [True, False], ids=['identical-target', 'different-target'])
def test_current_desktop_supplement_reconciles_identical_target_and_preserves_conflicts(tmp_path, monkeypatch, same):
    app, root, store, records, old_receipt, old_bytes = _completed_without_desktop(tmp_path, monkeypatch)
    path = next(iter(records)); target = '.agentworkspace/' + path
    data = records[path] if same else b'User owns this destination'
    write_bytes(root / target, data)
    before = store.head('instance/alice')
    if same:
        assert app.layout_migrate('sea', 'target-check')['state'] == 'complete'
        assert not (root / path).exists()
    else:
        with pytest.raises(Conflict):
            app.layout_migrate('sea', 'target-check')
        assert store.head('instance/alice') == before
        assert (root / path).read_bytes() == records[path]
    assert (root / target).read_bytes() == data
    assert old_receipt.read_bytes() == old_bytes


def test_current_supplement_does_not_move_user_replacement_or_unproven_runtime_record(tmp_path, monkeypatch):
    app, root, store, records, old_receipt, old_bytes = _completed_without_desktop(tmp_path, monkeypatch)
    path = next(iter(records)); user = b'{"topic":"User replaced the local JSON"}'
    write_bytes(root / path, user)
    runtime = 'records/b-desktop/runtime.jsonl'
    write_bytes(root / runtime, b'{"method":"turn/start"}\n')
    result = app.layout_migrate('sea', 'keep-user-record')
    assert (root / path).read_bytes() == user and not (root / '.agentworkspace' / path).exists()
    assert store.snapshot('instance/alice').bytes('.agentworkspace/' + path) == records[path]
    assert (root / runtime).exists() and not (root / '.agentworkspace' / runtime).exists()
    assert path in result['unclassified_local_files'][str(root)]
    assert old_receipt.read_bytes() == old_bytes


@pytest.mark.parametrize('failure', ['record', 'context'])
def test_current_supplement_copy_interruption_continues_new_original_request(tmp_path, monkeypatch, failure):
    app, root, store, records, old_receipt, old_bytes = _completed_without_desktop(tmp_path, monkeypatch)
    marker = (root / layout.MARKER).read_bytes()
    original = migration.write_bytes; failed = []
    fail_at = root / ('.agentworkspace/' + next(iter(records))) if failure == 'record' else layout.local_path(root, 'context.json')
    def write(path, data):
        original(path, data)
        if path == fail_at and not failed:
            failed.append(True)
            raise OSError('Fixture: durable write completed but process stopped before receipt')
    monkeypatch.setattr(migration, 'write_bytes', write)
    with pytest.raises(OSError):
        app.layout_migrate('sea', 'interrupted-supplement')
    published = store.head('instance/alice')
    assert app.layout_plan('sea')['pending_migrations'][0]['request_id'] == 'interrupted-supplement'
    with pytest.raises(Conflict):
        app.layout_migrate('sea', 'cannot-bypass-original')
    monkeypatch.setattr(migration, 'write_bytes', original)
    result = app.layout_migrate('sea', 'interrupted-supplement')
    assert result['state'] == 'complete' and store.head('instance/alice') == published
    for path, data in records.items():
        assert not (root / path).exists() and (root / '.agentworkspace' / path).read_bytes() == data
    write_bytes(root / 'notes/work.md', b'New user work after supplement')
    app.layout_migrate('sea', 'interrupted-supplement')
    assert (root / 'notes/work.md').read_bytes() == b'New user work after supplement'
    assert old_receipt.read_bytes() == old_bytes and (root / layout.MARKER).read_bytes() == marker
    backup = Path(result['receipt']).parent / 'backups' / migration.digest(str(root).encode())
    for path, data in records.items():
        assert (backup / path).read_bytes() == data


def test_current_supplement_reads_back_original_unknown_publication_without_replay(tmp_path, monkeypatch):
    app, root, store, records, old_receipt, old_bytes = _completed_without_desktop(tmp_path, monkeypatch)
    implementation = type(store).publish; calls = []
    def lost(self, *args, **kwargs):
        calls.append(args)
        implementation(self, *args, **kwargs)
        raise Uncertain('Fixture: original publication succeeded but reply was lost')
    monkeypatch.setattr(type(store), 'publish', lost)
    with pytest.raises(Uncertain):
        app.layout_migrate('sea', 'unknown-supplement')
    assert len(calls) == 1 and all((root / path).exists() for path in records)
    original_revision = store.head('instance/alice')
    monkeypatch.setattr(type(store), 'publish', implementation)
    assert app.layout_migrate('sea', 'unknown-supplement')['state'] == 'complete'
    assert store.head('instance/alice') == original_revision and len(calls) == 1
    assert old_receipt.read_bytes() == old_bytes


@pytest.mark.parametrize('interference', ['files-lock', 'changed-source'])
def test_current_supplement_rechecks_actual_copy_after_publication(tmp_path, monkeypatch, interference):
    app, root, store, records, old_receipt, old_bytes = _completed_without_desktop(tmp_path, monkeypatch)
    original = migration._publish; held = ExitStack(); path = next(iter(records))
    marker = (root / layout.MARKER).read_bytes()
    def publish(*args):
        original(*args)
        if interference == 'files-lock':
            held.enter_context(layout.lock(root, 'files.lock', wait=0))
        else:
            write_bytes(root / path, b'{"user":"changed after the plan"}')
    monkeypatch.setattr(migration, '_publish', publish)
    try:
        with pytest.raises(LockBusy if interference == 'files-lock' else Conflict):
            app.layout_migrate('sea', 'copy-interference')
        assert all((root / path).exists() for path in records)
        assert all(not (root / '.agentworkspace' / path).exists() for path in records)
        assert (root / layout.MARKER).read_bytes() == marker and old_receipt.read_bytes() == old_bytes
    finally:
        held.close()
    if interference == 'files-lock':
        monkeypatch.setattr(migration, '_publish', original)
        assert app.layout_migrate('sea', 'copy-interference')['state'] == 'complete'
    else:
        assert (root / path).read_bytes() == b'{"user":"changed after the plan"}'
        assert app.layout_plan('sea')['pending_migrations'][0]['request_id'] == 'copy-interference'
