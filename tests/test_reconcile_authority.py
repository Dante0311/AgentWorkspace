"""A known operation ID is not authority to publish another Agent's receipt."""
from unittest.mock import Mock

import pytest

from agent_workspace import commands, maintenance
from agent_workspace.gitstore import GitStore
from agent_workspace.messages import Messages
from agent_workspace.util import Conflict, Error, encode, read_json


@pytest.fixture(params=['message', 'ack'])
def pending(pair, monkeypatch, request):
    app, bindings = pair
    messages = Messages(app)
    if request.param == 'ack':
        messages.send('sea', 'alice', bindings['alice'], 'bob', 'Fixture notification', request_id='original')
    with monkeypatch.context() as fault:
        fault.setattr(GitStore, 'publish', Mock(side_effect=Error('Fixture publication denied')))
        if request.param == 'message':
            receipt = messages.send('sea', 'alice', bindings['alice'], 'bob', 'Fixture notification', request_id='original')
            owner = 'alice'
        else:
            receipt = messages.receive('sea', 'bob', bindings['bob'], 'original')['publication']
            owner = 'bob'
    assert receipt['state'] == 'pending'
    return app, bindings, receipt['id'], owner


@pytest.mark.parametrize('other_workspace', [False, True])
def test_other_actor_cannot_reconcile_by_guessing_operation_id(pending, other_workspace, tmp_path):
    app, _, operation, _ = pending
    workspace = 'another' if other_workspace else 'sea'
    if other_workspace:
        app.workspace_init(workspace, str(tmp_path / 'another.git'))
    app.create(workspace, 'outsider')
    binding = app.reserve(workspace, 'outsider')['binding']
    app.bind(workspace, 'outsider', binding, 'outsider-session')
    receipt_path = app.home / 'operations' / (operation + '.json')
    before = receipt_path.read_bytes()
    head = app.store('sea').head('main')
    with pytest.raises(Conflict):
        commands.execute(app, 'message.reconcile', {'operation_id': operation},
                         actor=(workspace, 'outsider', binding))
    assert receipt_path.read_bytes() == before
    assert app.store('sea').head('main') == head


def test_owner_can_reconcile_and_repeat_without_new_publication(pending):
    app, bindings, operation, owner = pending
    actor = ('sea', owner, bindings[owner])
    result = commands.execute(app, 'message.reconcile', {'operation_id': operation}, actor=actor)
    assert result['state'] == 'published'
    head = app.store('sea').head('main')
    assert commands.execute(app, 'message.reconcile', {'operation_id': operation}, actor=actor) == result
    assert app.store('sea').head('main') == head


def test_user_management_can_reconcile_without_fabricating_an_actor(pending):
    app, _, operation, _ = pending
    assert commands.execute(app, 'message.reconcile', {'operation_id': operation})['state'] == 'published'


def test_caretaker_must_use_scoped_repair_not_direct_reconcile(pending):
    app, _, operation, owner = pending
    app.create('sea', 'maintainer')
    binding = app.reserve('sea', 'maintainer')['binding']
    app.bind('sea', 'maintainer', binding, 'maintenance-session')
    actor = ('sea', 'maintainer', binding)
    store = app.store('sea')
    snap = store.snapshot()
    meta = snap.json('workspace.json')
    meta['caretakers'] = {'maintainer': 'maintainer'}
    store.change('main', {'workspace.json': encode(meta)}, {'workspace.json': snap.entries['workspace.json']}, 'Test caretaker')
    args = {'agent_id': owner, 'action': 'publication-reconcile', 'operation_id': operation, 'request_id': 'repair-original'}
    with pytest.raises(Error):
        commands.execute(app, 'maintenance.repair', args, actor=actor)
    maintenance.grant(app, 'sea', 'maintainer', ['maintenance.repair'], [owner])
    # Even a scoped caretaker uses the audited repair path for another instance.
    with pytest.raises(Conflict):
        commands.execute(app, 'message.reconcile', {'operation_id': operation}, actor=actor)
    result = commands.execute(app, 'maintenance.repair', args, actor=actor)
    assert result['state'] == 'applied' and result['result']['state'] == 'published'
    head = store.head('main')
    assert commands.execute(app, 'maintenance.repair', args, actor=actor) == result
    assert store.head('main') == head
    maintenance.grant(app, 'sea', 'maintainer', [], [])
    with pytest.raises(Error):
        commands.execute(app, 'maintenance.repair', args, actor=actor)


def test_caller_cannot_supply_receipt_owners_identity(pending):
    app, bindings, operation, owner = pending
    other = 'bob' if owner == 'alice' else 'alice'
    path = app.home / 'operations' / (operation + '.json')
    before = path.read_bytes()
    for spoof in ({'agent_id': owner, 'binding': bindings[owner]}, {'binding': None}):
        with pytest.raises(Error):
            commands.execute(app, 'message.reconcile', {'operation_id': operation, **spoof},
                             actor=('sea', other, bindings[other]))
    assert path.read_bytes() == before


def test_new_entry_cannot_reconcile_old_entrys_receipt(pending):
    app, bindings, operation, owner = pending
    old = bindings[owner]
    point = app.checkpoint('sea', owner, 'Test handoff', binding=old)
    app.stop('sea', owner, old, point['id'])
    app.finish_stop('sea', owner, old, observed_idle=True)
    new = app.reserve('sea', owner)['binding']
    app.bind('sea', owner, new, 'new-' + owner)
    path = app.home / 'operations' / (operation + '.json')
    before = path.read_bytes()
    with pytest.raises(Conflict):
        commands.execute(app, 'message.reconcile', {'operation_id': operation}, actor=('sea', owner, new))
    assert path.read_bytes() == before
    assert read_json(path)['binding'] == old
