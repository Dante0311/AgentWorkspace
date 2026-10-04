"""Read-only recovery of the original publication, not a second message store."""
from unittest.mock import Mock

import pytest

from agent_workspace.commands import execute
from agent_workspace.messages import Messages
from agent_workspace.util import Conflict, Error, read_json, write_json


def test_missing_operation_does_not_create_or_read_git(app, monkeypatch):
    store = Mock(side_effect=AssertionError('receipt lookup must not contact Git'))
    monkeypatch.setattr(app, 'store', store)
    assert execute(app, 'message.operation', {'workspace': 'sea', 'operation_id': 'unknown'}) == {
        'id': 'unknown', 'state': 'not_recorded'}
    assert not (app.home / 'operations').exists()
    with pytest.raises(Error):
        Messages(app).operation('missing', 'unknown')


def test_read_receipt_and_retry_preserve_one_message(pair):
    app, bindings = pair
    messages = Messages(app)
    args = ('sea', 'alice', bindings['alice'], 'bob', 'one message')
    messages.send(*args, request_id='same-request')
    before = app.store('sea').snapshot().revision
    record = execute(app, 'message.operation', {'workspace': 'sea', 'operation_id': 'same-request'})
    assert record['state'] == 'published' and record['type'] == 'message'
    assert record['agent'] == 'alice' and record['binding'] == bindings['alice']
    assert 'destinations' not in record and 'completed' not in record
    assert app.store('sea').snapshot().revision == before
    assert messages.send(*args, request_id='same-request')['payload'] == record['payload']
    assert len(messages.list('sea')) == 1
    with pytest.raises(Conflict):
        messages.send(*args[:-1], 'changed', request_id='same-request')


def test_pending_receipt_remains_pending_when_only_inspected(pair):
    app, bindings = pair
    messages = Messages(app)
    messages.send('sea', 'alice', bindings['alice'], 'bob', 'saved', request_id='pending')
    path = app.home / 'operations/pending.json'
    receipt = read_json(path)
    receipt['state'] = 'pending'
    receipt['completed'] = []
    write_json(path, receipt)
    before = path.read_bytes()
    assert messages.operation('sea', 'pending')['state'] == 'pending'
    assert path.read_bytes() == before
    assert messages.reconcile('pending')['state'] == 'published'
    assert len(messages.list('sea')) == 1


def test_receipt_scope_and_stale_binding_are_not_rewritten(pair, tmp_path):
    app, bindings = pair
    messages = Messages(app)
    messages.send('sea', 'alice', bindings['alice'], 'bob', 'saved', request_id='original')
    app.workspace_init('other', str(tmp_path / 'other.git'))
    with pytest.raises(Conflict):
        messages.operation('other', 'original')
    point = app.checkpoint('sea', 'alice', 'handoff', binding=bindings['alice'])
    app.stop('sea', 'alice', bindings['alice'], point['id'])
    app.finish_stop('sea', 'alice', bindings['alice'], observed_idle=True)
    record = messages.operation('sea', 'original')
    assert record['binding'] == bindings['alice']
    assert messages.reconcile('original')['state'] == 'published'
    with pytest.raises(Conflict):
        messages.send('sea', 'alice', bindings['alice'], 'bob', 'old', request_id='another')
    assert len(messages.list('sea')) == 1
