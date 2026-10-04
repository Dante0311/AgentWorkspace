"""Cross-instance writes require a target-scoped grant, not just an active caller."""
import pytest

from agent_workspace import commands, maintenance
from agent_workspace.util import Error, encode


def test_agent_cannot_write_another_instances_assets(pair):
    app, bindings = pair
    target = app.root('sea', 'bob') / 'notes.md'
    with pytest.raises(Error, match='another instance'):
        commands.execute(app, 'asset.write', {
            'agent_id': 'bob', 'path': 'notes.md', 'content': 'unauthorized',
        }, actor=('sea', 'alice', bindings['alice']))
    assert not target.exists()


def test_agent_can_still_write_its_own_assets(pair):
    app, bindings = pair
    result = commands.execute(app, 'asset.write', {
        'path': 'notes.md', 'content': 'own note',
    }, actor=('sea', 'alice', bindings['alice']))
    assert result['saved'] == 'local'
    assert (app.root('sea', 'alice') / 'notes.md').read_text() == 'own note'


@pytest.mark.parametrize('command, arguments', [
    ('agent.connect', {'directory': '/unused-target'}),
    ('agent.promote', {'paths': ['notes.md'], 'destination': 'knowledge/unauthorized'}),
    ('agent.fork', {'checkpoint': 'unused', 'name': 'unauthorized'}),
])
def test_non_grantable_operations_cannot_target_another_instance(pair, command, arguments):
    app, bindings = pair
    with pytest.raises(Error, match='another instance'):
        commands.execute(app, command, {'agent_id': 'bob', **arguments},
                         actor=('sea', 'alice', bindings['alice']))


def test_asset_grant_is_scoped_and_revocable(pair):
    app, bindings = pair
    store = app.store('sea')
    snap = store.snapshot()
    meta = snap.json('workspace.json')
    meta['caretakers'] = {'steward': 'alice'}
    store.change('main', {'workspace.json': encode(meta)},
                 {'workspace.json': snap.entries['workspace.json']}, 'Register test caretaker')
    actor = ('sea', 'alice', bindings['alice'])
    arguments = {'agent_id': 'bob', 'path': 'notes.md', 'content': 'authorized note'}
    maintenance.grant(app, 'sea', 'alice', ['asset.write'], targets=['bob'])
    saved = commands.execute(app, 'asset.write', arguments, actor=actor)
    assert (app.root('sea', 'bob') / 'notes.md').read_text() == 'authorized note'
    with pytest.raises(Error, match='another instance'):
        commands.execute(app, 'asset.write', {**arguments, 'agent_id': 'not-granted'}, actor=actor)
    with pytest.raises(Error, match='another instance'):
        commands.execute(app, 'asset.write', {**arguments, 'workspace': 'other'}, actor=actor)
    maintenance.grant(app, 'sea', 'alice', [], targets=[])
    with pytest.raises(Error, match='another instance'):
        commands.execute(app, 'asset.write', {**arguments, 'revision': saved['revision'],
                                            'content': 'after revocation'}, actor=actor)
    assert (app.root('sea', 'bob') / 'notes.md').read_text() == 'authorized note'
