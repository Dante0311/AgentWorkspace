import os
from pathlib import Path

import pytest

from agent_workspace import layout, model_profiles
from agent_workspace.app import App
from agent_workspace.gitstore import GitStore
from agent_workspace.util import Conflict, Error, encode, read_json, user_asset_path, write_bytes, write_json


def legacy_app(tmp_path):
    app = App(tmp_path / 'home')
    address = tmp_path / 'legacy.git'
    GitStore.initialize(address)
    store = GitStore(str(address), app.home)
    store.branch('main', {'workspace.json': encode({'schema': 1, 'name': 'sea', 'locator': 'local:sea',
                                                  'friends': {}, 'projects': {}})})
    app.workspace_connect('sea', str(address))
    identity = {'workspace': 'local:sea', 'agent': 'alice'}
    files = {'.aw/identity.json': encode(identity), 'AGENTS.md': b'Private responsibility\n',
             'startup.md': b'Private startup\n', 'notes/work.md': b'Original work\n',
             '.agents/skills/custom/SKILL.md': b'Private skill\n',
             '.aw/software.json': encode({'version': 'legacy', 'files': {}}),
             '.aw/checkpoints/c-old.json': encode({'id': 'c-old', 'summary': 'original', 'content': 'old facts',
                                                  'created_at': '2020-01-01', 'record_refs': []})}
    saved = store.branch('instance/alice', files)
    agent = {'id': 'alice', 'name': 'alice', 'description': '', 'branch': 'instance/alice', 'archived': False,
             'current': None, 'has_run': True, 'handoff': None, 'created_at': '2020-01-01'}
    point = {'id': 'c-old', 'agent': 'alice', 'revision': saved,
             'path': '.aw/checkpoints/c-old.json', 'created_at': '2020-01-01'}
    store.change('main', {'agents/alice.json': encode(agent), 'checkpoints/alice/c-old.json': encode(point)},
                 {'agents/alice.json': None, 'checkpoints/alice/c-old.json': None}, 'Seed old facts')
    app.connect_agent('sea', 'alice', tmp_path / 'alice')
    return app


def publish_unchecked(store, branch, changes, tmp_path):
    """Seed externally tracked unsafe/unknown data, bypassing AW on purpose."""
    assert Path(store.address).resolve().is_relative_to(tmp_path.resolve())
    parent = store.head(branch)
    environment = dict(os.environ, GIT_INDEX_FILE=str(tmp_path / 'external-index'),
                       GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.test',
                       GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.test')
    store.git('read-tree', parent, env=environment)
    for path, data in changes.items():
        sha = store.git('hash-object', '-w', '--stdin', data=data).stdout.decode().strip()
        store.git('update-index', '--add', '--cacheinfo', f'100644,{sha},{path}', env=environment)
    tree = store.git('write-tree', env=environment).stdout.decode().strip()
    commit = store.git('commit-tree', tree, '-p', parent, data=b'External fixture', env=environment).stdout.decode().strip()
    store.git('push', '--porcelain', 'origin', f'{commit}:refs/heads/{branch}')
    return commit


def test_new_workspace_and_agent_keep_user_discovery_and_separate_configuration(app):
    app.create('sea', 'alice')
    shared = app.store('sea').snapshot()
    assert layout.version(shared, 'workspace') == 1
    assert 'workspace.json' not in shared.entries
    assert '.agentworkspace/agents/alice.json' in shared.entries
    root = app.root('sea', 'alice')
    assert (root / 'AGENTS.md').exists()
    assert (root / '.agents/skills/message/SKILL.md').exists()
    assert layout.version(root, 'instance') == 1
    assert not (root / '.aw').exists() and not (root / '.aw-local').exists()
    assert read_json(layout.instance_path(root, 'identity.json'))['agent'] == 'alice'
    app.configure('sea', 'alice', {'kind': 'desktop', 'model': 'gpt-6.1-sol', 'effort': 'high',
                                 'provider': {'env_key': 'PRIVATE_API_TOKEN'}})
    assert model_profiles.selected(root)['source']['path'] == '.agentworkspace/config.json'
    assert model_profiles.desired(root)['model'] == 'gpt-6.1-sol'
    assert 'model' not in read_json(layout.local_path(root, 'runtime.json'))
    assert b'PRIVATE_API_TOKEN' not in layout.instance_path(root, 'config.json').read_bytes()


def test_new_checkpoint_and_fork_save_current_layout_and_user_files(app):
    app.create('sea', 'alice')
    root = app.root('sea', 'alice')
    write_bytes(root / 'notes/business.txt', b'Actual user material')
    binding = app.reserve('sea', 'alice')['binding']
    app.bind('sea', 'alice', binding, 'native-a')
    point = app.checkpoint('sea', 'alice', 'saved', 'facts', binding=binding, checkpoint_id='c-new')
    assert point['path'] == '.agentworkspace/checkpoints/c-new.json'
    assert app.checkpoint_show('sea', 'alice', 'c-new')['record']['content'] == 'facts'
    fork = app.fork('sea', 'alice', 'c-new', 'bob')
    new_root = app.root('sea', fork['id'])
    assert layout.version(new_root, 'instance') == 1
    assert read_json(layout.instance_path(new_root, 'identity.json'))['agent'] == 'bob'
    assert (new_root / 'notes/business.txt').read_bytes() == b'Actual user material'
    assert app.require_binding('sea', 'alice', binding)[1]['session'] == 'native-a'


def test_collection_excludes_local_data_even_if_user_removes_configured_excludes(app):
    app.create('sea', 'alice')
    root = app.root('sea', 'alice')
    context = read_json(layout.local_path(root, 'context.json'))
    context['exclude'] = []
    write_json(layout.local_path(root, 'context.json'), context)
    write_bytes(layout.local_path(root, 'inputs/unconfirmed.json'), b'Unknown original operation')
    write_bytes(root / '.aw-local/old-receipt.json', b'Legacy unresolved receipt')
    write_bytes(root / 'messages/business.txt', b'User-owned messages folder')
    files, skipped = app.collect(root)
    assert 'messages/business.txt' in files
    assert not any(path.startswith(('.aw-local/', '.agentworkspace/local/')) for path in files)
    assert '.agentworkspace/local/' in skipped and '.aw-local/' in skipped
    point = app.checkpoint('sea', 'alice', 'safe', checkpoint_id='c-safe')
    saved = app.store('sea').snapshot(revision=point['revision'])
    assert not any(path.startswith(('.aw-local/', '.agentworkspace/local/')) for path in saved.entries)
    assert b'/.agentworkspace/local/' in saved.bytes('.gitignore')


def test_inherited_tracked_local_files_block_public_save_and_store_writes(app, tmp_path):
    app.create('sea', 'alice')
    store = app.store('sea')
    head = publish_unchecked(store, 'instance/alice', {'.agentworkspace/local/operations/pending.json': b'Private receipt'}, tmp_path)
    with pytest.raises(Error):
        store.change('instance/alice', {'note.md': b'new'}, {'note.md': None}, 'Would inherit secret')
    assert store.head('instance/alice') == head
    with pytest.raises(Error):
        app.sync_agent('sea', 'alice')
    assert not (app.root('sea', 'alice') / '.agentworkspace/local/operations/pending.json').exists()


@pytest.mark.parametrize('legacy', [False, True])
def test_existing_shared_archives_survive_agent_creation(app, tmp_path, legacy):
    if legacy:
        app = legacy_app(tmp_path / 'legacy')
    store = app.store('sea')
    archives = {'development/archive/proof/.aw-local/old-receipt.json': b'Archived test evidence',
                'development/archive/proof/.agentworkspace/local/old-state.json': b'Archived state'}
    publish_unchecked(store, 'main', archives, tmp_path)
    before = store.snapshot()

    created = app.create('sea', 'receiver', agent_id='receiver', request_id='archive-receiver')
    branch = store.head('instance/receiver')
    repeated = app.create('sea', 'receiver', agent_id='receiver', request_id='archive-receiver')
    after = store.snapshot()

    assert created['id'] == repeated['id'] == 'receiver'
    assert store.head('instance/receiver') == branch
    assert app.agent('sea', 'receiver')['creation']['request_id'] == 'archive-receiver'
    for path, content in archives.items():
        assert after.entries[path] == before.entries[path]
        assert after.bytes(path) == content


@pytest.mark.parametrize('path', ['.aw-local/runtime.json', '.agentworkspace/local/runtime/status.json',
                                  'maintenance/.aw-local/private.json'])
def test_shared_platform_local_data_still_blocks_inherited_writes(app, tmp_path, path):
    store = app.store('sea')
    head = publish_unchecked(store, 'main', {path: b'Live local state'}, tmp_path)
    with pytest.raises(Error):
        store.change('main', {'note.md': b'new'}, {'note.md': None}, 'Would inherit live local data')
    assert store.head('main') == head


@pytest.mark.parametrize('existing', [False, True])
def test_shared_archive_exception_does_not_allow_publishing_local_data(app, tmp_path, existing):
    store = app.store('sea')
    path = 'development/archive/proof/.aw-local/state.json'
    if existing:
        publish_unchecked(store, 'main', {path: b'Existing archive'}, tmp_path)
    before = store.snapshot()
    with pytest.raises(Error):
        store.change('main', {path: b'New local state'}, {path: before.entries.get(path)}, 'Publish local state')
    assert store.head('main') == before.revision


def test_unknown_shared_layout_blocks_writes_without_erasing_the_marker(app, tmp_path):
    store = app.store('sea')
    unknown_marker = encode({'version': 99, 'kind': 'workspace'})
    head = publish_unchecked(store, 'main', {layout.MARKER: unknown_marker}, tmp_path)
    assert store.snapshot().bytes(layout.MARKER) == unknown_marker
    with pytest.raises(Error):
        store.change('main', {layout.MARKER: None, 'note.md': b'new'}, {'note.md': None}, 'Erase unknown layout')
    with pytest.raises(Error):
        app.agents('sea')
    assert store.head('main') == head
    assert store.snapshot().bytes(layout.MARKER) == unknown_marker


def test_pending_software_update_cannot_be_saved_as_a_checkpoint(app):
    app.create('sea', 'alice')
    root = app.root('sea', 'alice')
    path = layout.local_path(root, 'software-update.json')
    assert path == root / '.agentworkspace/local/operations/software-update.json'
    write_json(path, {'state': 'pending'})
    head = app.store('sea').head('instance/alice')
    with pytest.raises(Conflict):
        app.checkpoint('sea', 'alice', 'would save half updated materials', checkpoint_id='c-half')
    assert app.store('sea').head('instance/alice') == head
    assert not layout.instance_path(root, 'checkpoints/c-half.json').exists()


def test_old_checkpoint_uses_pinned_original_path_and_identity(tmp_path):
    app = legacy_app(tmp_path)
    point = app.checkpoint_show('sea', 'alice', 'c-old')
    assert point['path'] == '.aw/checkpoints/c-old.json'
    assert point['record']['content'] == 'old facts'
    assert app.show('sea', 'alice')['id'] == 'alice'
    with pytest.raises(layout.MigrationRequired):
        layout.resource_files(app.root('sea', 'alice'))


def test_layout_change_rejects_an_old_shared_conditional_write(tmp_path):
    app = legacy_app(tmp_path)
    store = app.store('sea')
    original = store.snapshot()
    key = layout.shared_path(original, 'agents/bob.json')
    expected = layout.expected(original, {key: None})
    store.change('main', {layout.MARKER: layout.marker('workspace'),
                         '.agentworkspace/workspace.json': original.bytes('workspace.json'), 'workspace.json': None},
                 {'workspace.json': original.entries['workspace.json'], layout.MARKER: None}, 'Concurrent layout update', base=original.revision)
    after = store.head('main')
    with pytest.raises(Conflict):
        store.change('main', {key: b'old writer'}, expected, 'Old append')
    assert store.head('main') == after
    assert key not in store.snapshot().entries


@pytest.mark.parametrize('path', ['.aw/identity.json', 'source.json', '.agentworkspace/identity.json',
                                  '.agentworkspace/layout.json', '.agentworkspace/messages/m1.json',
                                  '.agentworkspace/local/runtime/status.json'])
def test_user_assets_cannot_replace_platform_metadata(tmp_path, path):
    with pytest.raises(Error):
        user_asset_path(tmp_path, path, write=True)
    assert user_asset_path(tmp_path, 'messages/my-notes.md', write=True) == tmp_path / 'messages/my-notes.md'
    assert user_asset_path(tmp_path, '.agentworkspace/config.json', write=True) == tmp_path / '.agentworkspace/config.json'
