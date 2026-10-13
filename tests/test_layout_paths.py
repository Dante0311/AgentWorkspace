import json

import pytest

from agent_workspace import layout
from agent_workspace.util import Error, write_bytes


def test_paths_choose_one_layout_without_missing_file_fallback(tmp_path):
    write_bytes(tmp_path / '.aw/identity.json', b'old')
    assert layout.instance_path(tmp_path, 'identity.json') == tmp_path / '.aw/identity.json'
    assert layout.instance_path(tmp_path, 'config.json') == tmp_path / 'runtime.json'
    write_bytes(tmp_path / layout.MARKER, layout.marker('instance'))
    assert layout.instance_path(tmp_path, 'identity.json') == tmp_path / '.agentworkspace/identity.json'
    assert not layout.instance_path(tmp_path, 'identity.json').exists()
    assert layout.instance_path(tmp_path, 'config.json') == tmp_path / '.agentworkspace/config.json'
    assert (tmp_path / '.aw/identity.json').read_bytes() == b'old'


def test_pinned_shared_and_instance_layouts_use_their_own_marker():
    assert layout.shared_path({}, 'agents/alice.json') == 'agents/alice.json'
    assert layout.shared_path({layout.MARKER: layout.marker('workspace')}, 'agents/alice.json') == '.agentworkspace/agents/alice.json'
    assert layout.instance_relpath({}, 'checkpoints/c1.json') == '.aw/checkpoints/c1.json'
    assert layout.instance_relpath({layout.MARKER: layout.marker('instance')}, 'checkpoints/c1.json') == '.agentworkspace/checkpoints/c1.json'
    with pytest.raises(Error):
        layout.shared_path({}, 'knowledge/user.md')


@pytest.mark.parametrize('name,new', [
    ('status.json', 'runtime/status.json'), ('runner.lock', 'runtime/runner.lock'),
    ('runtime.json', 'runtime/runtime.json'), ('context.json', 'operations/context.json'),
    ('inputs/unknown.json', 'operations/inputs/unknown.json'),
    ('skill-install/operation.json', 'operations/skill-install/operation.json'),
    ('runner.log', 'logs/runner.log'), ('cache/item.json', 'cache/item.json'),
    ('bridge-sends/unknown.json', 'operations/bridge-sends/unknown.json'),
    ('desktop-preparations/unknown.json', 'operations/desktop-preparations/unknown.json'),
])
def test_local_classification_keeps_unknown_operation_names(tmp_path, name, new):
    assert layout.local_path(tmp_path, name) == tmp_path / '.aw-local' / name
    write_bytes(tmp_path / layout.MARKER, layout.marker('instance'))
    assert layout.local_path(tmp_path, name) == tmp_path / '.agentworkspace/local' / new


@pytest.mark.parametrize('value', [
    {'version': 99, 'kind': 'instance'}, {'version': True, 'kind': 'instance'},
    {'version': 1, 'kind': 'workspace'}, [],
])
def test_invalid_or_future_layout_is_not_treated_as_legacy(tmp_path, value):
    write_bytes(tmp_path / layout.MARKER, json.dumps(value).encode())
    with pytest.raises(Error):
        layout.local_path(tmp_path, 'status.json')


def test_incomplete_migration_blocks_paths_and_legacy_resources_require_migration(tmp_path):
    with pytest.raises(layout.MigrationRequired):
        layout.require_current(tmp_path)
    write_bytes(tmp_path / layout.MARKER, layout.marker('instance', state='migrating'))
    with pytest.raises(layout.MigrationRequired):
        layout.local_path(tmp_path, 'status.json')


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'x\\secret', 'C:/secret', '.git/config'])
def test_platform_path_cannot_escape_root(tmp_path, name):
    with pytest.raises(Error):
        layout.local_path(tmp_path, name)


def test_resources_require_migration_and_keep_native_skill_location(tmp_path):
    with pytest.raises(layout.MigrationRequired):
        layout.resource_files(tmp_path)
    write_bytes(tmp_path / layout.MARKER, layout.marker('instance'))
    content = layout.resource_files(tmp_path)
    assert '.agents/skills/message/SKILL.md' in content
    assert '.agentworkspace/prompts/capabilities.md' in content
    assert not any(path.startswith('.aw/') for path in content)
    assert layout.MARKER not in content  # Software does not replace migration facts.
    software = json.loads(content['.agentworkspace/software.json'])
    from agent_workspace.util import digest
    assert software['files'] == {path: digest(data) for path, data in content.items()
                                 if path != '.agentworkspace/software.json'}


def test_channel_semantic_path_keeps_legacy_channels_at_the_root(tmp_path):
    assert layout.instance_path(tmp_path, 'records/channels') == tmp_path / 'channels'
    write_bytes(tmp_path / layout.MARKER, layout.marker('instance'))
    assert layout.instance_path(tmp_path, 'records/channels') == tmp_path / '.agentworkspace/records/channels'
