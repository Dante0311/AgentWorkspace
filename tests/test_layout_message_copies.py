"""Local receive copies use real formal Message facts and the existing migration."""
import json
from pathlib import Path

import pytest

from agent_workspace import layout, message_store, migration
from agent_workspace.util import Conflict, Uncertain, encode, read_json, write_bytes
from test_layout_core import legacy_app


def copies(tmp_path, monkeypatch, *, completed=False, tracked=False, separate=False):
    app = legacy_app(tmp_path)
    store = app.store('sea'); root = app.root('sea', 'alice')
    address = {'workspace': 'local:sea', 'agent': 'alice'}
    message = {'id': 'received', 'from': address, 'to': address, 'created_at': '2020-01-01',
               'delivery': 'normal', 'content': 'Isolated fixture body'}
    store.change('main', {'messages/received.json': encode(message), 'acks/received.json': encode({'message_id': 'received'})},
                 {'messages/received.json': None, 'acks/received.json': None}, 'Original formal message and ACK')
    path = 'messages/received.json'
    data = (json.dumps({'message_id': 'received', 'message': message, 'ack': {'message_id': 'received'}}, indent=4) + '\r\n').encode()
    if tracked:
        store.change('instance/alice', {path: data}, {path: None}, 'Saved receive copy')
        app.sync_agent('sea', 'alice')
    else:
        write_bytes(root / path, data)
    old = None
    if completed:
        original = migration.owned_instance_files
        with monkeypatch.context() as omission:
            omission.setattr(migration, 'owned_instance_files',
                             lambda *args, **kwargs: {p for p in original(*args, **kwargs) if not p.startswith('messages/')})
            omission.setattr(migration, '_message_copy_files', lambda root: {})
            result = app.layout_migrate('sea', 'original-complete')
        old = Path(result['receipt']); old = (old, old.read_bytes())
    if separate:
        message_store.migrate(app, 'sea', 'separate-messages', compatible_writers=['message-v3'])
    return app, store, root, path, data, old


@pytest.mark.parametrize('completed,tracked,separate', [(False, False, False), (True, False, False),
                                                       (True, True, False), (True, False, True)])
def test_receive_copies_move_with_exact_bytes_without_repeating_protocol(tmp_path, monkeypatch, completed, tracked, separate):
    app, store, root, path, data, old = copies(tmp_path, monkeypatch, completed=completed, tracked=tracked, separate=separate)
    state = store.message_snapshot(); shared = state.main.all(); formal = state.messages.all()
    checkpoint = app.checkpoint_show('sea', 'alice', 'c-old')
    plan = app.layout_plan('sea')['instances'][0]
    assert path in plan['owned_records']
    assert plan['local_paths'][str(root)][path] == '.agentworkspace/' + path
    if old:
        app.layout_migrate('sea', 'original-complete')
        assert (root / path).read_bytes() == data and old[0].read_bytes() == old[1]
    result = app.layout_migrate('sea', 'copy-supplement')
    assert result['state'] == 'complete'
    assert not (root / path).exists() and (root / '.agentworkspace' / path).read_bytes() == data
    assert app.checkpoint_show('sea', 'alice', 'c-old') == checkpoint
    after = store.message_snapshot()
    assert after.main.all() == shared and after.messages.all() == formal
    if old:
        assert old[0].read_bytes() == old[1]
    backup = Path(result['receipt']).parent / 'backups' / migration.digest(str(root).encode()) / path
    assert backup.read_bytes() == data
    assert app.layout_migrate('sea', 'nothing-left')['directories'] == []


def test_unproven_copies_and_saved_copy_replaced_locally_stay_in_place(tmp_path, monkeypatch):
    app, store, root, path, data, old = copies(tmp_path, monkeypatch, completed=True, tracked=True)
    user = b'{"message_id":"received","message":{"note":"user replacement"}}'
    wrong = json.loads(data); wrong['message_id'] = 'other'
    wrong['message']['id'] = 'other'; wrong['message']['to']['agent'] = 'bob'
    store.change('main', {'messages/other.json': encode(wrong['message'])}, {'messages/other.json': None},
                 'Formal message to another Agent does not prove local ownership')
    files = {path: user, 'messages/other.json': encode(wrong), 'messages/user.json': b'{"notes":"user"}'}
    for name, content in files.items():
        write_bytes(root / name, content)
    assert set(files) <= set(app.layout_plan('sea')['instances'][0]['unclassified_local_files'][str(root)])
    result = app.layout_migrate('sea', 'keep-unproven')
    assert set(files) <= set(result['unclassified_local_files'][str(root)])
    for name, content in files.items():
        assert (root / name).read_bytes() == content and not (root / '.agentworkspace' / name).exists()
    assert store.snapshot('instance/alice').bytes('.agentworkspace/' + path) == data
    assert old[0].read_bytes() == old[1]


@pytest.mark.parametrize('same', [True, False])
def test_existing_target_is_reconciled_only_when_bytes_match(tmp_path, monkeypatch, same):
    app, store, root, path, data, old = copies(tmp_path, monkeypatch, completed=True)
    target = root / '.agentworkspace' / path
    content = data if same else b'{"user":"different target"}'
    write_bytes(target, content)
    if same:
        assert app.layout_migrate('sea', 'target-check')['state'] == 'complete'
        assert not (root / path).exists()
    else:
        with pytest.raises(Conflict):
            app.layout_migrate('sea', 'target-check')
        assert (root / path).read_bytes() == data
    assert target.read_bytes() == content and old[0].read_bytes() == old[1]


@pytest.mark.parametrize('failure', ['copy-interruption', 'source-changed', 'unknown-publication'])
def test_supplement_keeps_original_recovery_and_conflict_rules(tmp_path, monkeypatch, failure):
    app, store, root, path, data, old = copies(tmp_path, monkeypatch, completed=True, tracked=True)
    original = migration.write_bytes; failed = []
    def write(target, content):
        original(target, content)
        if target == root / '.agentworkspace' / path and not failed:
            failed.append(True)
            raise OSError('Fixture copy interruption')
    publish = migration._publish
    def change(*args):
        publish(*args)
        write_bytes(root / path, b'User changed source after planning')
    implementation = type(store).publish; calls = []
    def unknown(self, *args, **kwargs):
        calls.append(args)
        implementation(self, *args, **kwargs)
        raise Uncertain('Fixture publication reply lost')
    with monkeypatch.context() as fault:
        if failure == 'copy-interruption':
            fault.setattr(migration, 'write_bytes', write)
            error = OSError
        elif failure == 'source-changed':
            fault.setattr(migration, '_publish', change)
            error = Conflict
        else:
            fault.setattr(type(store), 'publish', unknown)
            error = Uncertain
        with pytest.raises(error):
            app.layout_migrate('sea', 'original-supplement')
    revision = store.head('instance/alice')
    if failure == 'source-changed':
        assert (root / path).read_bytes() == b'User changed source after planning'
        assert not (root / '.agentworkspace' / path).exists()
    else:
        assert app.layout_migrate('sea', 'original-supplement')['state'] == 'complete'
        assert store.head('instance/alice') == revision
        assert (root / '.agentworkspace' / path).read_bytes() == data
        if failure == 'unknown-publication':
            assert len(calls) == 1
    assert old[0].read_bytes() == old[1]
