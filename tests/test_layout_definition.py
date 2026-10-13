import re

import pytest

from agent_workspace import layout, model_profiles
from agent_workspace.app import App
from agent_workspace.util import Conflict, Error, encode, read_json, write_bytes, write_json
from test_layout_core import legacy_app


@pytest.mark.parametrize('legacy', [False, True])
def test_definition_target_and_source_update_use_the_instance_layout(tmp_path, legacy):
    if legacy:
        app = legacy_app(tmp_path)
        root = app.root('sea', 'alice')
    else:
        app = App(tmp_path / 'home')
        app.workspace_init('sea', str(tmp_path / 'sea.git'))
    store = app.store('sea')
    role = 'definitions/reviewer'
    template = role + '/runtime.json'
    data = {role + '/definition.md': b'Review only.\n', template: encode({'codex': {'model': 'first', 'effort': 'high'}})}
    initial = store.change('main', data, {path: None for path in data}, 'Seed template selection')
    if legacy:
        selected, source = app._definition('sea', role, initial, root=root)
        for path, content in selected.items():
            write_bytes(root / path, content)
        write_json(layout.instance_path(root, 'source.json'), source)
    else:
        app.create('sea', 'alice', definition=role)
        root = app.root('sea', 'alice')
    target = 'runtime.json' if legacy else '.agentworkspace/config.json'
    source = read_json(layout.instance_path(root, 'source.json'))
    assert source['files'][target]['path'] == template
    assert source['files'][target]['hash'] == model_profiles.selected(root)['source']['sha256']
    assert model_profiles.selected(root)['model'] == 'first'
    assert (root / 'runtime.json').exists() == legacy
    revision = store.change('main', {template: encode({'codex': {'model': 'second', 'effort': 'low'}})},
                            {template: store.snapshot().entries[template]}, 'New template selection')
    app.update('sea', 'alice', revision)
    assert model_profiles.selected(root)['model'] == 'second'
    source = read_json(layout.instance_path(root, 'source.json'))
    assert source['files'][target]['path'] == template
    write_json(layout.instance_path(root, 'config.json'), {'codex': {'model': 'private-edit', 'effort': 'none'}})
    revision = store.change('main', {template: encode({'codex': {'model': 'third', 'effort': 'high'}})},
                            {template: store.snapshot().entries[template]}, 'Another template selection')
    with pytest.raises(Conflict):
        app.update('sea', 'alice', revision)
    assert model_profiles.selected(root)['model'] == 'private-edit'
    assert read_json(layout.instance_path(root, 'source.json')) == source


@pytest.mark.parametrize('legacy', [False, True])
def test_missing_selection_names_the_actual_config_path(tmp_path, legacy):
    if not legacy:
        write_bytes(tmp_path / layout.MARKER, layout.marker('instance'))
    expected = 'runtime.json' if legacy else '.agentworkspace/config.json'
    with pytest.raises(Error, match=re.escape(expected)):
        model_profiles.selected(tmp_path)
