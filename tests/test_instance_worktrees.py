from pathlib import Path
import shutil

import pytest

from agent_workspace import instance_worktrees, layout
from agent_workspace.app import App
from agent_workspace.util import Conflict, read_json, write_bytes, write_json


def git(root, *args):
    return instance_worktrees.git(root, *args).stdout.decode().strip()


def test_create_and_reuse_real_worktrees_preserves_each_agents_materials(app):
    for name in ('alice', 'bob'):
        created = app.create('sea', name)
        root = Path(created['directory'])
        assert root.is_relative_to(Path(app.store('sea').address))
        assert (root / '.git').is_file() and created['worktree'] and created['prepared']
        assert git(root, 'symbolic-ref', '--short', 'HEAD') == 'instance/' + name
        assert git(root, 'rev-parse', 'HEAD') == created['revision']
        write_bytes(root / 'notes.md', (name + ' unsaved work').encode())
        reused = app.prepare_agent_directory('sea', name)
        assert reused['directory'] == str(root) and not reused['prepared']
        assert (root / 'notes.md').read_text() == name + ' unsaved work'
        assert read_json(layout.instance_path(root, 'identity.json'))['agent'] == name
        assert app.agent('sea', name)['current'] is None


def test_connect_prepares_missing_copy_and_recovers_registration_without_replacing_files(app, tmp_path):
    app.create('sea', 'alice')
    point = app.checkpoint('sea', 'alice', 'Saved facts', 'Original result unknown', checkpoint_id='c-saved')
    other = App(tmp_path / 'other-home')
    other.workspace_connect('sea', app.store('sea').address)
    copy = tmp_path / 'other-workspace' / 'worktrees' / 'alice'
    facts = other.prepare_agent_directory('sea', 'alice', copy)
    assert facts['prepared'] and facts['worktree'] and facts['revision'] == point['revision']
    assert git(copy, 'rev-parse', 'HEAD') == point['revision']
    write_bytes(copy / 'notes.md', b'Local work is preserved')
    layout.local_path(copy, 'context.json').unlink()
    repaired = other.prepare_agent_directory('sea', 'alice', copy)
    assert repaired['prepared'] and repaired['directory'] == str(copy)
    assert (copy / 'notes.md').read_bytes() == b'Local work is preserved'
    assert other.checkpoint_show('sea', 'alice', 'c-saved')['record']['content'] == 'Original result unknown'
    assert other.agent('sea', 'alice')['current'] is None


def test_missing_registered_worktree_restores_only_saved_materials(app, tmp_path):
    app.create('sea', 'alice'); root = app.root('sea', 'alice')
    write_bytes(root / 'notes.md', b'Saved material')
    point = app.checkpoint('sea', 'alice', 'saved before directory went missing')
    write_bytes(root / 'unsaved.md', b'Never published')
    assert root.resolve().is_relative_to(tmp_path.resolve())
    shutil.rmtree(root)
    restored = app.prepare_agent_directory('sea', 'alice')
    assert restored['prepared'] and restored['revision'] == point['revision']
    assert (root / 'notes.md').read_bytes() == b'Saved material'
    assert not (root / 'unsaved.md').exists()
    assert git(root, 'symbolic-ref', '--short', 'HEAD') == 'instance/alice'
    assert app.agent('sea', 'alice')['current'] is None


def test_prepare_preserves_wrong_branch_and_nonempty_user_directory(app, tmp_path):
    app.create('sea', 'alice'); root = app.root('sea', 'alice')
    git(root, 'switch', '-c', 'user-work')
    with pytest.raises(Conflict):
        app.prepare_agent_directory('sea', 'alice')
    assert git(root, 'symbolic-ref', '--short', 'HEAD') == 'user-work'
    directory = tmp_path / 'user-documents'
    write_bytes(directory / 'mine.md', b'User file')
    with pytest.raises(Conflict):
        app.prepare_agent_directory('sea', 'alice', directory)
    assert (directory / 'mine.md').read_bytes() == b'User file'
    assert not (directory / '.git').exists()


def test_checkpoint_keeps_local_git_commits_and_rejects_partial_staged_file(app):
    app.create('sea', 'alice'); root = app.root('sea', 'alice')
    write_bytes(root / 'notes.md', b'User Git commit')
    git(root, 'add', 'notes.md')
    git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test', 'commit', '-m', 'User saved work')
    original = git(root, 'rev-parse', 'HEAD')
    point = app.checkpoint('sea', 'alice', 'continues user commit')
    assert git(root, 'rev-parse', 'HEAD') == point['revision']
    assert git(root, 'rev-parse', 'HEAD^') == original
    assert not git(root, 'diff', '--cached', '--name-only')
    write_bytes(root / 'notes.md', b'Staged version')
    git(root, 'add', 'notes.md')
    write_bytes(root / 'notes.md', b'Different working version')
    before = app.store('sea').head('instance/alice')
    with pytest.raises(Conflict):
        app.checkpoint('sea', 'alice', 'must preserve the staged version')
    assert app.store('sea').head('instance/alice') == before
    assert git(root, 'show', ':notes.md') == 'Staged version'
    assert (root / 'notes.md').read_bytes() == b'Different working version'


def test_sync_advances_git_head_and_keeps_unrelated_staged_work(app, tmp_path):
    app.create('sea', 'alice'); root = app.root('sea', 'alice')
    write_bytes(root / 'remote.md', b'Previously saved remote material')
    app.checkpoint('sea', 'alice', 'initial common revision')
    other = App(tmp_path / 'other-home'); other.workspace_connect('sea', app.store('sea').address)
    other.connect_agent('sea', 'alice', tmp_path / 'second-copy')
    write_bytes(root / 'local.md', b'Unrelated staged work')
    git(root, 'add', 'local.md')
    write_bytes(other.root('sea', 'alice') / 'remote.md', b'Remote saved work')
    point = other.checkpoint('sea', 'alice', 'remote change')
    synced = app.sync_agent('sea', 'alice')
    assert synced['revision'] == point['revision'] == git(root, 'rev-parse', 'HEAD')
    assert (root / 'remote.md').read_bytes() == b'Remote saved work'
    assert (root / 'local.md').read_bytes() == b'Unrelated staged work'
    assert git(root, 'diff', '--cached', '--name-only') == 'local.md'
    final = app.checkpoint('sea', 'alice', 'save actual staged and working material')
    assert app.store('sea').snapshot(revision=final['revision']).bytes('local.md') == b'Unrelated staged work'
    assert not git(root, 'diff', '--cached', '--name-only')


def test_nested_worktree_and_private_data_are_excluded_even_without_optional_excludes(app):
    app.create('sea', 'alice'); root = app.root('sea', 'alice')
    app.create('sea', 'bob', directory=root / 'nested')
    write_bytes(root / 'nested/private.md', b'Other Agent work')
    context = read_json(layout.local_path(root, 'context.json')); context['exclude'] = []
    write_json(layout.local_path(root, 'context.json'), context)
    write_bytes(layout.local_path(root, 'transfer.json'), b'{"state":"outcome_unknown"}')
    point = app.checkpoint('sea', 'alice', 'only my actual material')
    snapshot = app.store('sea').snapshot(revision=point['revision'])
    assert '.git' not in snapshot.entries and not any(path.startswith('nested/') for path in snapshot.entries)
    assert not any(path.startswith('.agentworkspace/local/') for path in snapshot.entries)
    assert 'nested/' in point['excluded']
    assert (root / 'nested/private.md').read_bytes() == b'Other Agent work'


def test_existing_ordinary_copy_stays_ordinary_and_can_checkpoint_and_sync(app, tmp_path):
    app.create('sea', 'alice')
    source = app.root('sea', 'alice'); plain = tmp_path / 'old-ordinary-copy'
    snapshot = app.store('sea').snapshot('instance/alice')
    for path, data in snapshot.all().items():
        write_bytes(plain / path, data)
    write_json(layout.local_path(plain, 'context.json'), read_json(layout.local_path(source, 'context.json')))
    result = app.prepare_agent_directory('sea', 'alice', plain)
    assert not result['worktree'] and not result['prepared'] and not (plain / '.git').exists()
    write_bytes(plain / 'notes.md', b'Original plain copy continues')
    point = app.checkpoint('sea', 'alice', 'ordinary copy saved', directory=plain)
    assert app.store('sea').snapshot(revision=point['revision']).bytes('notes.md') == b'Original plain copy continues'
    app.sync_agent('sea', 'alice', source)
    assert (source / 'notes.md').read_bytes() == b'Original plain copy continues'


def test_native_cwd_is_optional_and_does_not_replace_personal_directory(app, tmp_path):
    shared = str(tmp_path / 'shared-project')
    for name, observed in [('alice', shared), ('bob', None)]:
        app.create('sea', name)
        root = app.root('sea', name)
        binding = app.reserve('sea', name)['binding']
        entry = app.bind('sea', name, binding, 'native-' + name, cwd=observed)
        assert entry['execution']['directory'] == str(root)
        if observed is None:
            assert 'cwd' not in entry['execution']
        else:
            assert entry['execution']['cwd'] == shared
        assert app.require_binding('sea', name, binding)[1]['session'] == 'native-' + name
