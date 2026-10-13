"""One installation updates registered material copies without business or Git operations."""
import json

import pytest

from agent_workspace import cli, layout, software
from agent_workspace.app import App
from agent_workspace.commands import execute
from agent_workspace.util import Conflict, digest, encode, read_json, write_bytes, write_json


SKILL = '.agents/skills/agent/SKILL.md'
PROMPT = '.agentworkspace/prompts/entry.md'


@pytest.fixture
def installation(tmp_path):
    app = App(tmp_path / 'home')
    app.change_local(lambda value: value['workspaces'].update({
        'sea': {'locator': 'local:sea', 'address': 'must-not-connect', 'instances': {}}
    }))
    return app


def copy(installation, name, *, old=True):
    root = installation.home / 'instances' / name
    write_bytes(root / layout.MARKER, layout.marker('instance'))
    write_json(layout.instance_path(root, 'identity.json'), {'workspace': 'local:sea', 'agent': name})
    write_json(layout.local_path(root, 'context.json'), {'locator': 'local:sea', 'agent': name})
    files = layout.resource_files()
    if old:
        files[SKILL], files[PROMPT] = b'previous skill', b'previous prompt'
        files[software.MANIFEST] = encode({'version': 'previous', 'files': {
            path: digest(data) for path, data in files.items() if path != software.MANIFEST
        }})
    for path, data in files.items():
        write_bytes(root / path, data)
    write_bytes(root / 'AGENTS.md', b'user role')
    write_bytes(root / 'notes/user.txt', b'user knowledge')
    installation.change_local(lambda value: value['workspaces']['sea']['instances'].update({name: [str(root)]}))
    return root


def test_one_update_covers_registered_copies_and_preserves_user_assets(installation):
    roots = [copy(installation, name) for name in ('alice', 'bob')]
    private = roots[0] / '.agents/skills/private/SKILL.md'
    write_bytes(private, b'private skill')
    before_registry = installation.registry.read_bytes()
    # No active Agent or accessible shared repository is needed for local software maintenance.
    result = execute(installation, 'software.update', {}, actor=('sea', 'offline', 'old-entry'))
    assert result['complete'] and len(result['instances']) == 2
    assert {item['state'] for item in result['instances']} == {'updated'}
    for root in roots:
        assert (root / SKILL).read_bytes() == layout.resource_files()[SKILL]
        assert (root / PROMPT).read_bytes() == layout.resource_files()[PROMPT]
        assert (root / 'AGENTS.md').read_bytes() == b'user role'
        assert (root / 'notes/user.txt').read_bytes() == b'user knowledge'
    assert private.read_bytes() == b'private skill'
    assert installation.registry.read_bytes() == before_registry
    assert not result['shared_data_changed'] and not result['snapshot_saved']
    again = software.update(installation)
    assert again['complete'] and {item['state'] for item in again['instances']} == {'current'}


def test_modified_copy_does_not_block_other_copies(installation):
    changed, normal = copy(installation, 'changed'), copy(installation, 'normal')
    write_bytes(changed / SKILL, b'user changed built-in skill')
    before = (changed / software.MANIFEST).read_bytes()
    result = software.update(installation)
    by_id = {item['agent_id']: item for item in result['instances']}
    assert not result['complete'] and by_id['changed']['state'] == 'conflict'
    assert by_id['normal']['state'] == 'updated'
    assert (changed / SKILL).read_bytes() == b'user changed built-in skill'
    assert (changed / PROMPT).read_bytes() == b'previous prompt'
    assert (changed / software.MANIFEST).read_bytes() == before
    assert (normal / SKILL).read_bytes() == layout.resource_files()[SKILL]


def test_legacy_missing_and_mismatched_directories_are_reported(installation):
    legacy, foreign = copy(installation, 'legacy'), copy(installation, 'foreign')
    (legacy / layout.MARKER).unlink()
    write_json(layout.instance_path(foreign, 'identity.json'), {'workspace': 'another', 'agent': 'foreign'})
    installation.change_local(lambda value: value['workspaces']['sea']['instances'].update({
        'missing': [str(installation.home / 'missing')]
    }))
    before = {root: (root / SKILL).read_bytes() for root in (legacy, foreign)}
    result = software.update(installation)
    assert {item['agent_id']: item['state'] for item in result['instances']} == {
        'legacy': 'migration_required', 'foreign': 'conflict', 'missing': 'unavailable'
    }
    assert all((root / SKILL).read_bytes() == data for root, data in before.items())
    assert not (installation.home / 'missing').exists()


def test_interrupted_update_keeps_original_plan_and_resumes(installation, monkeypatch):
    root = copy(installation, 'alice')
    original = software.write_bytes

    def fail_prompt(path, data):
        if path == root / PROMPT:
            raise OSError('injected disk interruption')
        original(path, data)

    with monkeypatch.context() as scoped:
        scoped.setattr(software, 'write_bytes', fail_prompt)
        result = software.update(installation)
    assert not result['complete'] and result['instances'][0]['state'] == 'unavailable'
    assert (root / SKILL).read_bytes() == layout.resource_files()[SKILL]
    assert (root / PROMPT).read_bytes() == b'previous prompt'
    assert read_json(root / software.MANIFEST)['version'] == 'previous'
    pending = read_json(layout.local_path(root, software.OPERATION))
    assert pending['state'] == 'pending' and pending['files'][PROMPT]['content']
    with pytest.raises(Conflict):
        software.require_ready(root)
    assert software.status(installation)['instances'][0]['state'] == 'pending'
    result = software.update(installation)
    assert result['complete'] and result['instances'][0]['original_update_completed']
    assert read_json(layout.local_path(root, software.OPERATION))['state'] == 'complete'
    software.require_ready(root)
    assert (root / PROMPT).read_bytes() == layout.resource_files()[PROMPT]


def test_pending_update_does_not_overwrite_later_user_changes(installation, monkeypatch):
    root = copy(installation, 'alice')
    original = software.write_bytes

    def fail_prompt(path, data):
        if path == root / PROMPT:
            raise OSError('injected disk interruption')
        original(path, data)

    with monkeypatch.context() as scoped:
        scoped.setattr(software, 'write_bytes', fail_prompt)
        assert not software.update(installation)['complete']
    write_bytes(root / PROMPT, b'later user change')
    result = software.update(installation)
    assert result['instances'][0]['state'] == 'conflict'
    assert (root / PROMPT).read_bytes() == b'later user change'
    assert read_json(layout.local_path(root, software.OPERATION))['state'] == 'pending'


def test_cli_software_commands_do_not_require_a_workspace_or_live_agent(installation, monkeypatch, capsys):
    copy(installation, 'alice')
    for key, value in {'AW_AGENT': 'old', 'AW_BINDING': 'old', 'AW_WORKSPACE': 'missing'}.items():
        monkeypatch.setenv(key, value)
    assert cli.main(['--home', str(installation.home), 'software', 'status']) == 0
    assert json.loads(capsys.readouterr().out)['result']['instances'][0]['state'] == 'update_available'
    assert cli.main(['--home', str(installation.home), 'software', 'update']) == 0
    assert json.loads(capsys.readouterr().out)['result']['complete']
