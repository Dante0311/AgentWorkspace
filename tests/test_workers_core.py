"""Two Workers of one Agent against isolated real Git; no native/model acceptance."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil

import pytest

from agent_workspace import instance_worktrees, layout
from agent_workspace.app import App
from agent_workspace.gitstore import GitStore
from agent_workspace.util import Conflict, Error, LockBusy, Uncertain, encode, read_json, write_bytes, write_json


@pytest.fixture
def team(tmp_path):
    app = App(tmp_path / 'home')
    app.workspace_init('team', str(tmp_path / 'remote.git'), worker_support=True)
    app.create('team', 'owner')
    app.worker_create('team', 'owner', 'Investigation', 'Independently investigate a task', worker_id='topic')
    bindings = {}
    for worker in ('default', 'topic'):
        binding = app.reserve('team', 'owner', worker_id=worker)['binding']
        app.bind('team', 'owner', binding, 'session-' + worker, worker_id=worker)
        bindings[worker] = binding
    return app, app.root('team', 'owner'), bindings


def test_workers_have_independent_entries_checkpoints_handoff_and_archive(team):
    app, root, bindings = team
    for worker in bindings:
        write_bytes(root / f'workers/{worker}/notes.md', worker.encode())
        point = app.checkpoint('team', 'owner', worker, binding=bindings[worker], worker_id=worker, checkpoint_id='same-id')
        assert point['worker'] == worker
        loaded = app.checkpoint_show('team', 'owner', 'same-id', worker_id=worker)
        assert loaded['record']['origin']['worker'] == worker
        assert all(not p.startswith(f'workers/{"topic" if worker == "default" else "default"}/') for p in loaded['files'])
    with pytest.raises(Conflict):
        app.require_binding('team', 'owner', bindings['default'], worker_id='topic')
    with pytest.raises(Conflict):
        app.stop('team', 'owner', bindings['default'], 'same-id', worker_id='topic')
    default_watch = layout.local_path(root, 'watch.json', 'default')
    topic_watch = layout.local_path(root, 'watch.json', 'topic')
    write_json(topic_watch, {'enabled': True, 'binding': bindings['topic']})
    app.stop('team', 'owner', bindings['default'], 'same-id', worker_id='default')
    handoff = app.finish_stop('team', 'owner', bindings['default'], observed_idle=True, worker_id='default')
    assert handoff['worker'] == 'default'
    assert not read_json(default_watch)['enabled'] and read_json(topic_watch)['enabled']
    assert app.worker('team', 'owner', 'topic')['current'] == bindings['topic']
    assert app.agents('team', archived=False)[0]['id'] == 'owner'
    app.worker_archive('team', 'owner', 'default')
    assert app.worker('team', 'owner', 'default')['archived']
    assert app.agents('team', archived=False)[0]['id'] == 'owner'
    assert app.worker('team', 'owner', 'topic')['current'] == bindings['topic']
    with pytest.raises(Conflict):
        app.archive('team', 'owner')
    app.worker_archive('team', 'owner', 'default', archived=False)
    next_binding = app.reserve('team', 'owner', worker_id='default')['binding']
    app.bind('team', 'owner', next_binding, 'next-default', worker_id='default')
    with pytest.raises(Conflict):
        app.require_binding('team', 'owner', bindings['default'])
    assert app.require_binding('team', 'owner', bindings['topic'])[1]['id'] == bindings['topic']
    # Re-reading the old release must not release either successor or peer.
    app.finish_stop('team', 'owner', bindings['default'], observed_idle=True, worker_id='default')
    assert app.worker('team', 'owner', 'default')['current'] == next_binding


def test_save_preserves_peer_tracked_untracked_missing_and_staged_files(team):
    app, root, bindings = team
    tracked = root / 'workers/topic/tracked.md'
    absent = root / 'workers/topic/absent.md'
    write_bytes(tracked, b'saved')
    write_bytes(absent, b'saved missing later')
    app.checkpoint('team', 'owner', 'peer initial', binding=bindings['topic'], worker_id='topic', checkpoint_id='peer-base')
    write_bytes(tracked, b'peer staged')
    instance_worktrees.git(root, 'add', '--', 'workers/topic/tracked.md')
    staged_before = instance_worktrees.git(root, 'ls-files', '--stage', '--', 'workers/topic/tracked.md').stdout
    write_bytes(tracked, b'peer unfinished after staging')
    absent.unlink()
    write_bytes(root / 'workers/topic/new.md', b'peer untracked')
    write_bytes(root / 'workers/default/mine.md', b'only me')
    point = app.checkpoint('team', 'owner', 'my save', binding=bindings['default'], worker_id='default', checkpoint_id='mine')
    snap = app.store('team').snapshot(revision=point['revision'])
    assert snap.bytes('workers/topic/tracked.md') == b'saved'
    assert snap.bytes('workers/topic/absent.md') == b'saved missing later'
    assert snap.bytes('workers/topic/new.md') is None
    assert snap.bytes('workers/default/mine.md') == b'only me'
    assert tracked.read_bytes() == b'peer unfinished after staging' and not absent.exists()
    assert (root / 'workers/topic/new.md').read_bytes() == b'peer untracked'
    assert instance_worktrees.git(root, 'ls-files', '--stage', '--', 'workers/topic/tracked.md').stdout == staged_before
    assert instance_worktrees.git(root, 'diff', '--name-only', 'HEAD').stdout
    listing, _ = app.collect(root)
    assert 'workers/topic/new.md' in listing and 'workers/default/mine.md' in listing
    with pytest.raises(Error):
        app._save_files('team', 'owner', root)
    with pytest.raises(Error):
        app.checkpoint('team', 'owner', 'bad scope', binding=bindings['default'], worker_id='default', shared_paths=['workers/topic/new.md'])
    write_bytes(root / '.env', b'excluded fixture, not a credential')
    with pytest.raises(Error):
        app.checkpoint('team', 'owner', 'excluded common file', binding=bindings['default'], worker_id='default', shared_paths=['.env'])


def test_two_worker_saves_are_coordinated_in_one_worktree(team):
    app, root, bindings = team
    for worker in bindings:
        write_bytes(root / f'workers/{worker}/notes.md', worker.encode())
    def save(worker):
        return app.checkpoint('team', 'owner', worker, binding=bindings[worker], worker_id=worker, checkpoint_id='parallel')
    with ThreadPoolExecutor(max_workers=2) as pool:
        points = list(pool.map(save, bindings))
    snap = app.store('team').snapshot('instance/owner')
    for worker in bindings:
        assert snap.bytes(f'workers/{worker}/notes.md') == worker.encode()
        assert app.worker('team', 'owner', worker)['current'] == bindings[worker]
    assert all(app.store('team').contains_commit(p['revision'], snap.revision) for p in points)


def test_common_file_requires_explicit_selection_and_original_worker_version(team, tmp_path):
    app, root, bindings = team
    common = root / 'knowledge.md'
    write_bytes(common, b'base')
    app.checkpoint('team', 'owner', 'common base', binding=bindings['default'], worker_id='default', checkpoint_id='base', shared_paths=['knowledge.md'])
    other = tmp_path / 'second-copy'
    app.connect_agent('team', 'owner', str(other))
    # The topic Worker deliberately reads the shared baseline before the other copy publishes.
    from agent_workspace.workers import prepare_context
    prepare_context(app, 'team', 'owner', other, 'topic')
    write_bytes(common, b'published by default')
    app.checkpoint('team', 'owner', 'common update', binding=bindings['default'], worker_id='default', checkpoint_id='updated', shared_paths=['knowledge.md'])
    write_bytes(other / 'knowledge.md', b'unsaved topic edit')
    with pytest.raises(Conflict):
        app.checkpoint('team', 'owner', 'conflict', binding=bindings['topic'], directory=str(other), worker_id='topic', checkpoint_id='conflict', shared_paths=['knowledge.md'])
    assert (other / 'knowledge.md').read_bytes() == b'unsaved topic edit'
    assert app.store('team').snapshot('instance/owner').bytes('knowledge.md') == b'published by default'
    # Omitting a common path neither saves nor deletes it.
    point = app.checkpoint('team', 'owner', 'own only', binding=bindings['topic'], directory=str(other), worker_id='topic', checkpoint_id='own-only')
    assert app.store('team').snapshot(revision=point['revision']).bytes('knowledge.md') == b'published by default'
    # Saving unrelated Worker files must not silently adopt the newer common-file version.
    with pytest.raises(Conflict):
        app.checkpoint('team', 'owner', 'still stale common edit', binding=bindings['topic'], directory=str(other), worker_id='topic', checkpoint_id='still-stale', shared_paths=['knowledge.md'])


@pytest.mark.parametrize('accepted', [False, True])
def test_unknown_worker_checkpoint_never_republishes_the_original_commit(team, monkeypatch, accepted):
    app, root, bindings = team
    original = GitStore.publish
    attempts = []
    def uncertain(store, branch, commit, expected):
        if branch == 'instance/owner':
            attempts.append(commit)
            if accepted:
                original(store, branch, commit, expected)
            raise Uncertain('fixture lost publication result')
        return original(store, branch, commit, expected)
    with monkeypatch.context() as fault:
        fault.setattr(GitStore, 'publish', uncertain)
        with pytest.raises(Uncertain):
            app.checkpoint('team', 'owner', 'one attempt', binding=bindings['default'], worker_id='default', checkpoint_id='unknown')
    if accepted:
        point = app.checkpoint('team', 'owner', 'one attempt', binding=bindings['default'], worker_id='default', checkpoint_id='unknown')
        assert point['revision'] == attempts[0]
        assert app.checkpoint_show('team', 'owner', 'unknown', worker_id='default')['record']['summary'] == 'one attempt'
        assert instance_worktrees.head(root) == point['revision']
    else:
        with pytest.raises(Uncertain):
            app.checkpoint('team', 'owner', 'one attempt', binding=bindings['default'], worker_id='default', checkpoint_id='unknown')
    assert len(attempts) == 1


def test_legacy_mapping_preserves_protocol_bytes_and_never_uses_new_default(app):
    app.create('sea', 'alice')
    binding = app.reserve('sea', 'alice')['binding']
    app.bind('sea', 'alice', binding, 'original-session')
    old_point = app.checkpoint('sea', 'alice', 'old immutable point', binding=binding, checkpoint_id='legacy')
    root = app.root('sea', 'alice')
    store = app.store('sea')
    snap = store.snapshot()
    locator = app.workspace_show('sea')['locator']
    message = {'id': 'old-message', 'from': {'workspace': locator, 'agent': 'alice'},
               'to': {'workspace': locator, 'agent': 'alice'}, 'created_at': 'fixture', 'delivery': 'normal', 'content': 'unchanged'}
    protected = {layout.shared_path(snap, 'messages/old-message.json'): encode(message),
                 layout.shared_path(snap, 'message-index/old-message.json'): encode({k: message[k] for k in ('id','from','to','created_at','delivery')}),
                 layout.shared_path(snap, 'acks/old-message.json'): encode({'message_id': 'old-message'})}
    for identifier, source, target in (
        ('native-out', {'workspace': locator, 'agent': 'alice'}, {'workspace': locator, 'agent': 'peer'}),
        ('native-in', {'workspace': locator, 'agent': 'peer'}, {'workspace': locator, 'agent': 'alice'}),
        ('foreign-name', {'workspace': 'workspace:other', 'agent': 'alice'}, {'workspace': locator, 'agent': 'peer'}),
    ):
        protected[layout.shared_path(snap, f'direct-messages/{identifier}.json')] = encode(
            {'id': identifier, 'from': source, 'to': target, 'content': 'optional native observation'})
    store.change('main', protected, {p: None for p in protected}, 'legacy protocol fixture')
    snap = store.snapshot()
    protected[layout.shared_path(snap, f'bindings/{binding}.json')] = snap.bytes(layout.shared_path(snap, f'bindings/{binding}.json'))
    protected[layout.shared_path(snap, 'checkpoints/alice/legacy.json')] = snap.bytes(layout.shared_path(snap, 'checkpoints/alice/legacy.json'))
    receipt_path = layout.local_path(root, 'inputs/old-input.json')
    write_json(receipt_path, {'binding': binding, 'state': 'outcome_unknown', 'text': 'do not replay'})
    raw_input = receipt_path.read_bytes()
    old_checkpoint_bytes = store.snapshot(revision=old_point['revision']).bytes(old_point['path'])
    with pytest.raises(Error):
        app.workers_migrate('sea', 'alice', 'daily', 'migration')
    result = app.workers_migrate('sea', 'alice', 'daily', 'migration', compatible_writers=['worker-v2'])
    assert result['starts_session'] is False
    assert layout.version(store.snapshot(), 'workspace') == layout.WORKER_VERSION
    assert layout.version(root, 'instance') == layout.WORKER_VERSION
    assert app.require_binding('sea', 'alice', binding, worker_id='daily')[0]['worker_id'] == 'daily'
    assert layout.local_path(root, 'inputs/old-input.json', 'daily').read_bytes() == raw_input
    after = store.snapshot()
    assert all(after.bytes(p) == raw for p, raw in protected.items())
    assert store.snapshot(revision=old_point['revision']).bytes(old_point['path']) == old_checkpoint_bytes
    assert app.checkpoint_show('sea', 'alice', 'legacy', worker_id='daily')['record']['summary'] == 'old immutable point'
    app.worker_create('sea', 'alice', 'Other', 'New work', worker_id='other', binding=binding)
    current_agent = app.show('sea', 'alice', worker_id='daily')
    app.worker_default('sea', 'alice', 'other', current_agent['revision'])
    assert app.legacy_worker('sea', 'alice', 'messages', 'old-message') == 'daily'
    assert app.legacy_worker('sea', 'alice', 'messages', 'native-out') == 'daily'
    assert app.legacy_worker('sea', 'alice', 'messages', 'native-in') == 'daily'
    with pytest.raises(Conflict):
        app.legacy_worker('sea', 'alice', 'messages', 'foreign-name')
    with pytest.raises(Conflict):
        app.legacy_worker('sea', 'alice', 'messages', 'unmapped-message')
    with pytest.raises(Conflict):
        app.checkpoint_show('sea', 'alice', 'legacy', worker_id='other')
    assert app.require_binding('sea', 'alice', binding)[0]['worker_id'] == 'daily'
    before_context = layout.local_path(root, 'context.json', 'daily').read_bytes()
    app.workers_migrate('sea', 'alice', 'daily', 'migration', compatible_writers=['worker-v2'])
    assert layout.local_path(root, 'context.json', 'daily').read_bytes() == before_context


def test_new_workspace_defaults_to_workers_and_fork_selects_nondefault_source(team, tmp_path):
    app, root, bindings = team
    fresh = App(tmp_path / 'fresh-home')
    fresh.workspace_init('fresh', str(tmp_path / 'fresh.git'))
    fresh.create('fresh', 'ordinary')
    assert fresh.worker('fresh', 'ordinary')['id'] == 'default'
    assert layout.version(fresh.store('fresh').snapshot(), 'workspace') == layout.WORKER_VERSION
    write_bytes(root / 'workers/default/not-in-fork.md', b'peer scope')
    app.checkpoint('team', 'owner', 'default materials', binding=bindings['default'], worker_id='default', checkpoint_id='default-point')
    write_bytes(root / 'workers/topic/investigation.md', b'only the selected Worker')
    app.checkpoint('team', 'owner', 'topic materials', binding=bindings['topic'], worker_id='topic', checkpoint_id='topic-point')
    forked = app.fork('team', 'owner', 'topic-point', 'Independent owner', new_id='forked', worker_id='topic')
    assert forked['forked_from']['worker'] == 'topic'
    child = app.agent('team', 'forked')
    assert child['id'] == 'forked' and child['worker_id'] == 'topic' and child['current'] is None
    assert not child['has_run'] and child['handoff'] is None
    child_files = app.store('team').snapshot('instance/forked')
    assert child_files.bytes('workers/topic/investigation.md') == b'only the selected Worker'
    assert child_files.bytes('workers/default/not-in-fork.md') is None
    assert app.worker('team', 'owner', 'topic')['current'] == bindings['topic']
    with pytest.raises(Error):
        app.fork('team', 'owner', 'topic-point', 'Wrong source', new_id='wrong-source', worker_id='default')


def test_reserve_adopts_inherited_connection_and_independent_worker_profile(tmp_path):
    app = App(tmp_path / 'home')
    app.workspace_init('team', str(tmp_path / 'remote.git'))
    app.create('team', 'owner')
    app.worker_create('team', 'owner', 'Topic', 'An independent approved investigation', worker_id='topic')
    app.configure('team', 'owner', {'kind': 'desktop', 'pipe_path': 'fixture',
                                 'caller_thread': 'fixture', 'model': 'base-model', 'effort': 'low'})
    app.configure('team', 'owner', {'kind': 'desktop', 'model': 'topic-model', 'effort': 'high'}, worker_id='topic')
    root = app.root('team', 'owner')
    for worker, model in (('default', 'base-model'), ('topic', 'topic-model')):
        binding = app.reserve('team', 'owner', worker_id=worker)
        adopted = read_json(layout.local_path(root, 'entry.json', worker))
        assert binding['kind'] == adopted['config']['kind'] == 'desktop'
        assert adopted['config']['pipe_path'] == 'fixture'
        assert adopted['config']['caller_thread'] == 'fixture'
        assert adopted['model_profile']['model'] == model
    app.configure('team', 'owner', {'kind': 'manual'})
    assert all(read_json(layout.local_path(root, 'entry.json', worker))['config']['kind'] == 'desktop'
               for worker in ('default', 'topic'))


def test_worker_creation_can_resume_same_request_and_configuration_stays_scoped(team):
    app, root, bindings = team
    created = app.worker_create('team', 'owner', '中文工作', 'A user-approved independent task',
                                request_id='create-once', binding=bindings['default'])
    repeated = app.worker_create('team', 'owner', '中文工作', 'A user-approved independent task',
                                 request_id='create-once', binding=bindings['default'])
    assert repeated['id'] == created['id'] and repeated['created_at'] == created['created_at']
    assert repeated['current'] is None and not repeated['starts_session']
    with pytest.raises(Conflict):
        app.worker_create('team', 'owner', 'Changed request', 'Different work', request_id='create-once', binding=bindings['default'])
    before_entry = layout.local_path(root, 'entry.json', 'topic').read_bytes()
    common_config = layout.instance_path(root, 'config.json')
    before_common = common_config.read_bytes() if common_config.exists() else None
    app.configure('team', 'owner', {'kind': 'codex', 'command': ['fixture-only'], 'model': 'worker-model', 'effort': 'high'}, worker_id='topic')
    portable = read_json(layout.instance_path(root, 'config.json', 'topic'))
    assert portable == {'kind': 'codex', 'codex': {'model': 'worker-model', 'effort': 'high'}}
    local = read_json(layout.local_path(root, 'runtime.json', 'topic'))
    assert local['kind'] == 'codex' and 'model' not in local and 'effort' not in local
    assert layout.local_path(root, 'entry.json', 'topic').read_bytes() == before_entry
    assert (common_config.read_bytes() if common_config.exists() else None) == before_common
    unreserved = layout.local_path(root, 'context.json', created['id'])
    assert not unreserved.exists()
    app.collect(root, worker_id=created['id'])
    assert not unreserved.exists()


@pytest.mark.parametrize('accepted', [False, True])
def test_unknown_worker_creation_never_starts_or_repeats_a_publication(team, monkeypatch, accepted):
    app, root, bindings = team
    publish = GitStore.publish
    attempts = []
    def uncertain(store, branch, commit, expected):
        attempts.append(commit)
        if accepted:
            publish(store, branch, commit, expected)
        raise Uncertain('fixture Worker registration reply lost')
    arguments = dict(worker_id='uncertain-create', request_id='create-once', binding=bindings['default'])
    with monkeypatch.context() as fault:
        fault.setattr(GitStore, 'publish', uncertain)
        with pytest.raises(Uncertain):
            app.worker_create('team', 'owner', 'New task', 'A user-approved task', **arguments)
    if accepted:
        result = app.worker_create('team', 'owner', 'New task', 'A user-approved task', **arguments)
        assert result['current'] is None and not result['starts_session']
    else:
        with pytest.raises(Uncertain):
            app.worker_create('team', 'owner', 'New task', 'A user-approved task', **arguments)
    assert len(attempts) == 1
    assert app.worker('team', 'owner', 'default')['current'] == bindings['default']


@pytest.mark.parametrize('accepted', [False, True])
def test_partial_worker_migration_reconciles_original_registration_without_replay(app, monkeypatch, accepted):
    app.create('sea', 'legacy')
    binding = app.reserve('sea', 'legacy')['binding']
    app.bind('sea', 'legacy', binding, 'original-legacy-session')
    original_change = GitStore.change
    attempts = []
    def uncertain(store, branch, changes, expected, message, **kwargs):
        if any(p.endswith('worker-mappings/legacy.json') for p in changes):
            attempts.append(changes)
            if accepted:
                original_change(store, branch, changes, expected, message, **kwargs)
            raise Uncertain('fixture original registration result lost')
        return original_change(store, branch, changes, expected, message, **kwargs)
    with monkeypatch.context() as fault:
        fault.setattr(GitStore, 'change', uncertain)
        with pytest.raises(Uncertain):
            app.workers_migrate('sea', 'legacy', 'daily', 'partial', compatible_writers=['worker-v2'])
    if accepted:
        # A published mapping must already have usable local materials. An unknown
        # response followed by readback must not restore the old context over use.
        root = app.root('sea', 'legacy')
        context_path = layout.local_path(root, 'context.json', 'daily')
        context = read_json(context_path)
        context['subsequent_use'] = 'preserve after original publication'
        write_json(context_path, context)
        write_json(layout.local_path(root, 'inputs/newer.json', 'daily'), {'state': 'submitted'})
        point = app.workers_migrate('sea', 'legacy', 'daily', 'partial', compatible_writers=['worker-v2'])
        assert point['worker'] == 'daily' and not point['starts_session']
        assert read_json(context_path) == context
        assert read_json(layout.local_path(root, 'inputs/newer.json', 'daily')) == {'state': 'submitted'}
        assert app.require_binding('sea', 'legacy', binding, worker_id='daily')[1]['session'] == 'original-legacy-session'
    else:
        with pytest.raises(Uncertain):
            app.workers_migrate('sea', 'legacy', 'daily', 'partial', compatible_writers=['worker-v2'])
    assert len(attempts) == 1


def test_worker_migration_refuses_busy_local_input_writer(app):
    app.create('sea', 'legacy')
    root = app.root('sea', 'legacy')
    store = app.store('sea')
    before = store.snapshot().revision
    with layout.lock(root, 'inputs.lock'):
        with pytest.raises(LockBusy):
            app.workers_migrate('sea', 'legacy', 'daily', 'busy', compatible_writers=['worker-v2'])
    assert store.snapshot().revision == before
    assert layout.version(root, 'instance') == layout.VERSION


@pytest.mark.parametrize('registered', [False, True])
def test_migrated_legacy_checkpoint_keeps_original_pointer_and_holds_ambiguous_receipt(app, monkeypatch, registered):
    app.create('sea', 'legacy')
    binding = app.reserve('sea', 'legacy')['binding']
    app.bind('sea', 'legacy', binding, 'original-session')
    store = app.store('sea')
    change = store.change
    def stop_registration(branch, changes, expected, message, **kwargs):
        if any(p.endswith('checkpoints/legacy/old-point.json') for p in changes):
            raise Error('fixture registration did not complete')
        return change(branch, changes, expected, message, **kwargs)
    if registered:
        original = app.checkpoint('sea', 'legacy', 'historical point', binding=binding, checkpoint_id='old-point')
    else:
        with monkeypatch.context() as fault:
            fault.setattr(store, 'change', stop_registration)
            with pytest.raises(Error):
                app.checkpoint('sea', 'legacy', 'historical point', binding=binding, checkpoint_id='old-point')
        original = read_json(layout.local_path(app.root('sea', 'legacy'), 'checkpoint-operations/old-point.json'))
    app.workers_migrate('sea', 'legacy', 'daily', 'legacy-checkpoint', compatible_writers=['worker-v2'])
    root = app.root('sea', 'legacy')
    operation = layout.local_path(root, 'checkpoint-operations/old-point.json', 'daily')
    before = operation.read_bytes()
    def no_publish(*args, **kwargs):
        pytest.fail('Reading a legacy checkpoint must not replay any publication')
    monkeypatch.setattr(GitStore, 'publish', no_publish)
    if registered:
        repeated = app.checkpoint('sea', 'legacy', 'historical point', binding=binding, worker_id='daily', checkpoint_id='old-point')
        assert repeated == original and 'worker' not in repeated
    else:
        with pytest.raises(Uncertain):
            app.checkpoint('sea', 'legacy', 'historical point', binding=binding, worker_id='daily', checkpoint_id='old-point')
    assert operation.read_bytes() == before
    snap = store.snapshot()
    assert snap.bytes(layout.shared_path(snap, 'checkpoints/legacy/daily/old-point.json')) is None


def test_worker_migration_covers_registered_copies_and_refuses_later_legacy_copy_adoption(app, tmp_path):
    app.create('sea', 'copies')
    root = app.root('sea', 'copies')
    old_copy = tmp_path / 'preserved-unregistered-copy'
    shutil.copytree(root, old_copy, ignore=shutil.ignore_patterns('.git'))
    original_identity = layout.instance_path(old_copy, 'identity.json').read_bytes()
    second = tmp_path / 'second-registered-copy'
    app.connect_agent('sea', 'copies', str(second))
    with pytest.raises(Conflict):
        app.workers_migrate('sea', 'copies', 'daily', 'all-copies', directory=str(root), compatible_writers=['worker-v2'])
    assert layout.version(root, 'instance') == layout.VERSION
    assert layout.version(second, 'instance') == layout.VERSION
    app.workers_migrate('sea', 'copies', 'daily', 'all-copies', compatible_writers=['worker-v2'])
    assert layout.version(root, 'instance') == layout.WORKER_VERSION
    assert layout.version(second, 'instance') == layout.WORKER_VERSION
    with pytest.raises(layout.MigrationRequired):
        app.connect_agent('sea', 'copies', str(old_copy))
    assert layout.version(old_copy, 'instance') == layout.VERSION
    assert layout.instance_path(old_copy, 'identity.json').read_bytes() == original_identity
