import json
from pathlib import Path

import pytest

from agent_workspace import skills
from agent_workspace.commands import execute
from agent_workspace.util import Conflict, Error, read_json, write_json


def publish(app, text=b'first'):
    return app.store('sea').change('main', {
        'skills/review/SKILL.md': b'---\nname: review\ndescription: Shared review\n---\n' + text,
        'skills/review/scripts/check.py': b'print("test")',
        'skills/review/references/checklist.md': b'checklist',
        'definitions/helper/definition.md': b'# Reviewer',
        'definitions/helper/skills/special/SKILL.md': b'special duty'}, {}, 'materials')


def test_discovery_create_combines_definition_shared_and_platform_skills(app):
    revision = publish(app)
    found = skills.catalog(app, 'sea')
    assert found['skills'] == [{'name': 'review', 'path': 'skills/review', 'description': 'Shared review', 'available': True}]
    created = app.create('sea', 'a', definition='definitions/helper', skills=['review'])
    root = Path(created['directory'])
    assert (root / 'AGENTS.md').read_bytes() == b'# Reviewer'
    assert (root / '.agents/skills/special/SKILL.md').read_bytes() == b'special duty'
    assert (root / '.agents/skills/review/references/checklist.md').read_bytes() == b'checklist'
    assert len(list(root.glob('.agents/skills/*/SKILL.md'))) == 9
    assert read_json(root / skills.MANIFEST)['review']['revision'] == revision
    assert skills.MANIFEST in app.store('sea').snapshot('instance/a').entries
    assert app.agent('sea', 'a')['current'] is None


def test_add_update_only_selected_skill_and_preserve_unrelated_private_assets(app):
    publish(app)
    app.create('sea', 'a')
    root = app.root('sea', 'a')
    responsibility = (root / 'AGENTS.md').read_bytes()
    assert execute(app, 'agent.skill-install', {'workspace': 'sea', 'agent_id': 'a', 'name': 'review'})['state'] == 'installed'
    original = read_json(root / skills.MANIFEST)
    app.store('sea').change('main', {'unrelated.md': b'other'}, {}, 'not a Skill change')
    assert skills.apply(app, 'update', 'sea', 'a', 'review')['state'] == 'unchanged'
    assert read_json(root / skills.MANIFEST) == original
    (root / 'notes.md').write_bytes(b'private')
    publish(app, b'updated')
    row = next(v for v in skills.inspect(app, 'sea', 'a')['skills'] if v['name'] == 'review')
    assert row['state'] == 'update_available'
    assert skills.apply(app, 'update', 'sea', 'a', 'review')['state'] == 'updated'
    assert (root / '.agents/skills/review/SKILL.md').read_bytes().endswith(b'updated')
    assert (root / 'AGENTS.md').read_bytes() == responsibility and (root / 'notes.md').read_bytes() == b'private'
    assert not (root / 'source.json').exists()


@pytest.mark.parametrize('change', ['modified', 'extra', 'deleted'])
def test_user_modified_skill_is_not_overwritten(app, change):
    publish(app); app.create('sea', 'a', skills=['review'])
    root = app.root('sea', 'a'); target = root / '.agents/skills/review/SKILL.md'
    if change == 'modified': target.write_bytes(b'private')
    elif change == 'extra': (target.parent / 'own.md').write_bytes(b'private')
    else: target.unlink()
    before = skills.local_files(target.parent)
    publish(app, b'v2')
    with pytest.raises(Conflict, match='Locally modified'):
        skills.apply(app, 'update', 'sea', 'a', 'review')
    assert skills.local_files(target.parent) == before


def test_removed_upstream_is_retained_and_origin_collisions_are_rejected(app):
    publish(app); app.create('sea', 'a', definition='definitions/helper', skills=['review'])
    app.store('sea').change('main', {'skills/review/SKILL.md': None,
        'skills/message/SKILL.md': b'override', 'skills/special/SKILL.md': b'override'}, {}, 'source changes')
    rows = {r['name']: r for r in skills.inspect(app, 'sea', 'a')['skills']}
    assert rows['review']['state'] == 'source_missing'
    for name in ('message', 'special'):
        with pytest.raises(Conflict): skills.apply(app, 'install', 'sea', 'a', name)
    with pytest.raises(Conflict): app.create('sea', 'b', skills=['message'])
    assert app.root('sea', 'a').joinpath('.agents/skills/review/SKILL.md').exists()


def test_definition_update_cannot_claim_independent_shared_skill(app):
    publish(app); app.create('sea', 'a', definition='definitions/helper', skills=['review'])
    store = app.store('sea')
    store.change('main', {'definitions/helper/skills/review/SKILL.md': b'collision'}, {}, 'changed definition')
    with pytest.raises(Conflict, match='independently installed'):
        app.update('sea', 'a')
    assert (app.root('sea', 'a') / '.agents/skills/review/SKILL.md').read_bytes().endswith(b'first')


def test_interrupted_swap_finishes_only_original_receipt(app, monkeypatch):
    publish(app); app.create('sea', 'a', skills=['review'])
    root = app.root('sea', 'a'); publish(app, b'new')
    original = skills.write_json
    def fail_manifest(path, value):
        if path == root / skills.MANIFEST: raise OSError('disk unavailable')
        return original(path, value)
    monkeypatch.setattr(skills, 'write_json', fail_manifest)
    with pytest.raises(OSError): skills.apply(app, 'update', 'sea', 'a', 'review')
    assert (root / '.aw-local/skill-install/old/SKILL.md').exists()
    monkeypatch.setattr(skills, 'write_json', original)
    assert skills.apply(app, 'update', 'sea', 'a', 'review')['state'] == 'unchanged'
    assert not (root / '.aw-local/skill-install').exists()
    assert (root / '.agents/skills/review/SKILL.md').read_bytes().endswith(b'new')


def test_interrupted_update_never_overwrites_a_later_private_edit(app, monkeypatch):
    publish(app); app.create('sea', 'a', skills=['review']); publish(app, b'new')
    root = app.root('sea', 'a'); original = skills.write_json
    def fail_manifest(path, value):
        if path == root / skills.MANIFEST: raise OSError('disk unavailable')
        return original(path, value)
    monkeypatch.setattr(skills, 'write_json', fail_manifest)
    with pytest.raises(OSError): skills.apply(app, 'update', 'sea', 'a', 'review')
    monkeypatch.setattr(skills, 'write_json', original)
    target = root / '.agents/skills/review/SKILL.md'; target.write_bytes(b'private after failure')
    with pytest.raises(Conflict): skills.apply(app, 'update', 'sea', 'a', 'review')
    assert target.read_bytes() == b'private after failure'
    assert (root / '.aw-local/skill-install/old/SKILL.md').exists()


def test_resumable_create_preserves_selection_and_bytes(app):
    publish(app)
    app.create('sea', 'a', agent_id='a', request_id='same', skills=['review'])
    publish(app, b'new')
    app.create('sea', 'a', agent_id='a', request_id='same', skills=['review'])
    assert (app.root('sea', 'a') / '.agents/skills/review/SKILL.md').read_bytes().endswith(b'first')
    with pytest.raises(Conflict): app.create('sea', 'a', agent_id='a', request_id='same', skills=[])


def test_new_skill_requires_current_actor_or_scoped_cross_instance_grant(app):
    publish(app)
    for name in ('a', 'b'): app.create('sea', name)
    binding = app.reserve('sea', 'a')['binding']; app.bind('sea', 'a', binding, 'model')
    with pytest.raises(Error, match='grant'):
        execute(app, 'agent.skill-install', {'agent_id': 'b', 'name': 'review'}, actor=('sea', 'a', binding))
    assert execute(app, 'agent.skill-install', {'name': 'review'}, actor=('sea', 'a', binding))['state'] == 'installed'


def test_update_snapshot_and_start_wait_for_pending_recovery(app, monkeypatch):
    from agent_workspace import runtime
    publish(app); app.create('sea', 'a', skills=['review']); publish(app, b'new')
    root = app.root('sea', 'a'); original = skills.write_json
    def fail_manifest(path, value):
        if path == root / skills.MANIFEST: raise OSError('disk unavailable')
        return original(path, value)
    monkeypatch.setattr(skills, 'write_json', fail_manifest)
    with pytest.raises(OSError): skills.apply(app, 'update', 'sea', 'a', 'review')
    with pytest.raises(Conflict, match='Skill'): app.checkpoint('sea', 'a', 'not a complete asset version')
    with pytest.raises(Conflict, match='Skill'): runtime.start(app, 'sea', 'a')
    assert app.agent('sea', 'a')['current'] is None
    pending = skills.inspect(app, 'sea', 'a')['pending_skill']
    assert pending['name'] == 'review' and pending['operation'] == 'update'
    monkeypatch.setattr(skills, 'write_json', original)
    skills.apply(app, pending.pop('operation'), 'sea', 'a', **pending)
    assert app.checkpoint('sea', 'a', 'recovered assets')['revision']


def test_prepared_swap_before_new_directory_rename_recovers_old_files(app, monkeypatch):
    publish(app); app.create('sea', 'a', skills=['review']); publish(app, b'new')
    root = app.root('sea', 'a'); target = root / '.agents/skills/review'
    original = Path.rename
    def fail_new(path, dest):
        if path == root / '.aw-local/skill-install/new': raise OSError('rename interrupted')
        return original(path, dest)
    monkeypatch.setattr(Path, 'rename', fail_new)
    with pytest.raises(OSError): skills.apply(app, 'update', 'sea', 'a', 'review')
    assert not target.exists()
    monkeypatch.setattr(Path, 'rename', original)
    skills.recover(root)
    assert (target / 'SKILL.md').read_bytes().endswith(b'first')
    assert skills.apply(app, 'update', 'sea', 'a', 'review')['state'] == 'updated'


def test_case_conflict_and_invalid_skill_do_not_create_identity(app):
    publish(app)
    app.store('sea').change('main', {'skills/Review/SKILL.md': b'other', 'skills/invalid/SKILL.md': b'\xff'}, {}, 'invalid inputs')
    with pytest.raises(Conflict): app.create('sea', 'a', skills=['review', 'Review'])
    with pytest.raises(Error): app.create('sea', 'a', skills=['invalid'])
    assert not app.agents('sea')
