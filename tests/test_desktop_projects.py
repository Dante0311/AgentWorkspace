"""Desktop references never masquerade as native project or Binding changes."""
from pathlib import Path

import pytest

from agent_workspace import desktop_projects as dp
from agent_workspace.commands import execute
from agent_workspace.util import Conflict, Error


def test_plan_is_read_only_and_names_are_reused_per_agent(app):
    app.create('sea', 'reviewer')
    root = app.root('sea', 'reviewer')
    before = app.store('sea').head('main')
    first = dp.plan(app, 'sea', 'reviewer')
    assert first['primary_folder'] == str(root)
    assert first['project']['project_name'] == 'AW · sea · reviewer'
    assert first['project']['section_name'] == 'AW · sea'
    assert first['native_project_verified'] is False and first['revision'] is None
    assert first == dp.plan(app, 'sea', 'reviewer')
    assert not (root / '.aw-local/desktop-projects').exists()
    assert app.store('sea').head('main') == before


def test_custom_names_and_product_references_stay_local_without_copying(app, tmp_path):
    app.create('sea', 'reviewer')
    root = app.root('sea', 'reviewer')
    product = tmp_path / 'shop'
    product.mkdir()
    (product / 'AGENTS.md').write_text('project rules')
    original = (root / 'AGENTS.md').read_bytes()
    before = app.store('sea').head('main')
    result = dp.save(app, 'sea', 'reviewer', 'codex', 'Existing Reviewer', 'My Existing Section', [str(product)])
    assert result['saved'] == 'local_reference_only' and result['native_project_changed'] is False
    for _ in range(2):
        plan = dp.plan(app, 'sea', 'reviewer')
        assert plan['project']['project_name'] == 'Existing Reviewer'
        assert plan['project']['section_name'] == 'My Existing Section'
        assert plan['project']['product_paths'] == [str(product)]
    assert app.store('sea').head('main') == before
    assert (root / 'AGENTS.md').read_bytes() == original
    assert list(product.iterdir()) == [product / 'AGENTS.md']
    assert not any('.aw-local/desktop-projects' in p for p in app.collect(root)[0])
    assert app.agent('sea', 'reviewer')['current'] is None


def test_preference_update_requires_observed_revision(app):
    app.create('sea', 'reviewer')
    first = dp.save(app, 'sea', 'reviewer', 'codex', 'One')
    with pytest.raises(Conflict, match='preferences changed'):
        dp.save(app, 'sea', 'reviewer', 'codex', 'Two')
    value = dp.save(app, 'sea', 'reviewer', 'codex', 'Two', revision=first['revision'])
    assert value['project']['project_name'] == 'Two'


def test_other_desktops_do_not_claim_codex_sections_or_native_control(app):
    app.create('sea', 'reviewer')
    for harness in ('claude', 'workbuddy'):
        value = dp.plan(app, 'sea', 'reviewer', harness)
        assert value['project']['section_name'] == ''
        assert value['state'] == 'manual_setup_required'
        with pytest.raises(Error, match='sections'):
            dp.save(app, 'sea', 'reviewer', harness, 'User project', 'Not a supported section')


def test_bound_agent_can_read_guide_but_cannot_edit_desktop_preferences(app):
    app.create('sea', 'reviewer')
    actor = ('sea', 'reviewer', 'binding-placeholder')
    value = execute(app, 'agent.desktop-project', {}, actor=actor)
    assert value['agent_id'] == 'reviewer' and '手动准备' in value['instructions']
    with pytest.raises(Error, match='user-management'):
        execute(app, 'agent.desktop-project-save', {'harness': 'codex', 'project_name': 'Other'}, actor=actor)
