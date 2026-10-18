"""Message/permission races use real isolated Git; GraphQL checks do not use an account."""
from pathlib import Path
import subprocess
import types

import pytest

from agent_workspace import commands, layout, message_store
from agent_workspace.app import App
from agent_workspace.gitstore import GitHubStore, GitStore
from agent_workspace.util import Conflict, Error, Uncertain, encode, read_json, write_json


@pytest.fixture
def fresh(tmp_path):
    app = App(tmp_path / 'home')
    app.workspace_init('team', str(tmp_path / 'remote.git'))
    return app, app.store('team')


def append(store, state, identifier):
    path = layout.shared_path(state.messages, f'messages/{identifier}.json')
    return store.message_change(state, {path: encode({'id': identifier, 'content': 'fixture'})},
                                {path: None}, 'Append fixture message')


def test_new_workspace_and_ordinary_messages_keep_permissions_on_main(fresh):
    app, store = fresh
    app.create('team', 'owner')
    binding = app.reserve('team', 'owner')['binding']
    app.bind('team', 'owner', binding, 'isolated-native-session')
    state = store.message_snapshot()
    assert state.branch == 'aw-messages'
    assert app.worker('team', 'owner')['current'] == binding
    assert layout.version(app.root('team', 'owner'), 'instance') == 2
    append(store, state, 'first')
    current = store.message_snapshot()
    assert current.main.revision == state.main.revision
    assert current.messages.revision != state.messages.revision
    assert current.messages.json(layout.MESSAGE_GUARD) == state.messages.json(layout.MESSAGE_GUARD)
    assert not any('/agents/' in p or '/workers/' in p or '/bindings/' in p for p in current.messages.entries)
    with pytest.raises(Error):
        layout.shared_path(current.main, 'messages/first.json')
    with pytest.raises(Error):
        store.message_change(current, {layout.shared_path(current.main, 'agents/evil.json'): b'{}'}, {}, 'bad scope')
    path = layout.shared_path(current.main, 'work/independent.json')
    store.change('main', {path: b'{}'}, {path: None}, 'Independent Work update')
    assert store.head('aw-messages') == current.messages.revision


def test_real_atomic_permission_races_reject_whole_original_update(fresh, monkeypatch):
    app, store = fresh
    before = store.message_snapshot()
    path = layout.shared_path(before.main, 'agents/owner.json')
    commit = store.commit(before.main.revision, {path: encode({'id': 'owner', 'archived': False})}, 'Register owner')
    original = store._publish_atomic
    attempts = []
    def message_wins(updates):
        attempts.append(updates)
        append(store, before, 'message-won')
        return original(updates)
    with monkeypatch.context() as fault:
        fault.setattr(store, '_publish_atomic', message_wins)
        with pytest.raises(Conflict):
            store.publish('main', commit, before.main.revision)
    assert len(attempts) == 1
    assert store.head('main') == before.main.revision
    assert store.snapshot('aw-messages').json(layout.MESSAGE_GUARD) == before.messages.json(layout.MESSAGE_GUARD)
    stale = store.message_snapshot()
    store.change('main', {path: encode({'id': 'owner', 'archived': False})}, {path: None}, 'Register owner after reread')
    latest = store.message_snapshot()
    assert latest.main.revision != stale.main.revision
    assert latest.messages.revision != stale.messages.revision
    assert latest.messages.json(layout.MESSAGE_GUARD)['main_revision'] == latest.main.revision
    with pytest.raises(Conflict):
        append(store, stale, 'stale-owner')
    assert store.snapshot('aw-messages').bytes(layout.shared_path(latest.messages, 'messages/stale-owner.json')) is None


@pytest.mark.parametrize('old_version', [0, 1, 2])
def test_explicit_migration_preserves_legacy_identity_protocol_and_old_writer_gate(tmp_path, old_version):
    remote = tmp_path / 'remote.git'
    GitStore.initialize(remote)
    app = App(tmp_path / 'home')
    store = GitStore(str(remote), app.home)
    prefix = '.agentworkspace/' if old_version else ''
    identity = {'id': 'legacy', 'name': 'Legacy', 'description': '', 'branch': 'instance/legacy',
                'current': 'old-binding', 'has_run': True, 'handoff': None, 'archived': False}
    original = {prefix + 'workspace.json': encode({'schema': 1, 'name': 'old', 'locator': 'local:old', 'friends': {}, 'projects': {}}),
                prefix + 'agents/legacy.json': encode(identity),
                prefix + 'bindings/old-binding.json': encode({'id': 'old-binding', 'agent': 'legacy', 'phase': 'active', 'kind': 'manual', 'session': 'old-session'}),
                prefix + 'direct-messages/native.json': b'{ "id": "native", "observation": "unchanged" }\n'}
    for root in layout.MESSAGE_ROOTS:
        original[prefix + root + '/old.json'] = ('{ "root": "' + root + '", "unknown_field": true }\n').encode()
    if old_version:
        original[layout.MARKER] = layout.marker('workspace', version=old_version)
    store.branch('main', original)
    app.workspace_connect('old', str(remote))
    store = app.store('old')
    original_receipt = app.home / 'operations' / 'old-unknown.json'
    write_json(original_receipt, {'state': 'publishing', 'commit': 'original-unknown'})
    receipt_bytes = original_receipt.read_bytes()
    legacy_state = store.message_snapshot()
    with pytest.raises(Error):
        app.message_branch_migrate('old', 'move')
    result = app.message_branch_migrate('old', 'move', compatible_writers=['message-v3'])
    state = store.message_snapshot()
    assert result['main_revision'] == state.main.revision
    assert result['message_revision'] == state.messages.revision
    assert not result['starts_session']
    assert app.agent('old', 'legacy') == identity
    assert app.require_binding('old', 'legacy', 'old-binding')[1]['session'] == 'old-session'
    for path, raw in original.items():
        if path == layout.MARKER:
            continue
        if path.startswith(tuple(prefix + root + '/' for root in layout.MESSAGE_ROOTS)):
            assert state.messages.bytes(path) == raw and state.main.bytes(path) is None
        else:
            assert state.main.bytes(path) == raw and state.messages.bytes(path) is None
    assert original_receipt.read_bytes() == receipt_bytes
    with pytest.raises(Conflict):
        append(store, legacy_state, 'late-old-layout')
    assert app.message_branch_migrate('old', 'move', compatible_writers=['message-v3']) == result
    assert layout.worker_support(state.main) is (old_version == 2)
    # Run the actual previous writer's parser and commit validator, not a fake version check.
    old_layout = types.ModuleType('agent_workspace.previous_layout')
    exec(subprocess.run(['git', 'show', '9e1bf44:src/agent_workspace/layout.py'], capture_output=True, check=True).stdout, old_layout.__dict__)
    old_store_module = types.ModuleType('agent_workspace.previous_gitstore')
    exec(subprocess.run(['git', 'show', '9e1bf44:src/agent_workspace/gitstore.py'], capture_output=True, check=True).stdout, old_store_module.__dict__)
    old_store_module.layout = old_layout
    old_store = old_store_module.GitStore(str(remote), tmp_path / 'old-writer')
    with pytest.raises(Error, match='Unsupported workspace layout version'):
        old_store.commit(state.main.revision, {prefix + 'messages/forbidden.json': b'{}'}, 'Old writer must refuse')
    assert store.head('main') == state.main.revision


@pytest.mark.parametrize('accepted', [False, True])
def test_unknown_migration_reconciles_original_two_refs_without_replay(app, monkeypatch, accepted):
    store = app.store('sea')
    original = store._publish_atomic
    attempts = []
    def lost(updates):
        attempts.append(updates)
        if accepted:
            original(updates)
        raise Uncertain('fixture lost original publication response')
    with monkeypatch.context() as fault:
        fault.setattr(store, '_publish_atomic', lost)
        if accepted:
            result = app.message_branch_migrate('sea', 'unknown', compatible_writers=['message-v3'])
            assert result['state'] == 'published'
        else:
            with pytest.raises(Uncertain):
                app.message_branch_migrate('sea', 'unknown', compatible_writers=['message-v3'])
    if accepted:
        again = app.message_branch_migrate('sea', 'unknown', compatible_writers=['message-v3'])
        assert again['main_revision'] == attempts[0]['main']['after']
    else:
        with pytest.raises(Uncertain):
            app.message_branch_migrate('sea', 'unknown', compatible_writers=['message-v3'])
        with pytest.raises(Uncertain):
            app.message_branch_migrate('sea', 'another-id', compatible_writers=['message-v3'])
    assert len(attempts) == 1


@pytest.mark.parametrize('accepted', [False, True])
def test_unknown_permission_publication_keeps_original_pair_and_does_not_replay(fresh, monkeypatch, accepted):
    _, store = fresh
    state = store.message_snapshot()
    path = layout.shared_path(state.main, 'agents/owner.json')
    commit = store.commit(state.main.revision, {path: b'{"id":"owner"}'}, 'Original permission change')
    original = store._publish_atomic
    attempts = []
    def lost(updates):
        attempts.append(updates)
        if accepted:
            original(updates)
        raise Uncertain('fixture lost permission response')
    with monkeypatch.context() as fault:
        fault.setattr(store, '_publish_atomic', lost)
        if accepted:
            store.publish('main', commit, state.main.revision)
        else:
            with pytest.raises(Uncertain):
                store.publish('main', commit, state.main.revision)
    if accepted:
        store.publish('main', commit, state.main.revision)
        assert store.head('main') == commit
    else:
        with pytest.raises(Uncertain):
            store.publish('main', commit, state.main.revision)
    assert len(attempts) == 1


@pytest.mark.parametrize('accepted', [False, True])
def test_initialization_reuses_original_pair_after_unknown_result(tmp_path, monkeypatch, accepted):
    remote = tmp_path / 'remote.git'
    GitStore.initialize(remote)
    store = GitStore(str(remote), tmp_path / 'home')
    original = store._publish_atomic
    attempts = []
    def lost(updates):
        attempts.append(updates)
        if accepted:
            original(updates)
        raise Uncertain('fixture lost initialization response')
    metadata = {'schema': 1, 'name': 'isolated', 'locator': 'local:isolated', 'friends': {}, 'projects': {}}
    with monkeypatch.context() as fault:
        fault.setattr(store, '_publish_atomic', lost)
        if accepted:
            message_store.initialize(store, metadata)
        else:
            with pytest.raises(Uncertain):
                message_store.initialize(store, metadata)
    if accepted:
        assert message_store.initialize(store, metadata) == attempts[0]
    else:
        with pytest.raises(Uncertain):
            message_store.initialize(store, metadata)
    assert len(attempts) == 1


def test_github_atomic_contract_uses_update_refs_and_before_oid(tmp_path, monkeypatch):
    store = GitHubStore('github:owner/repo', tmp_path)
    calls = []
    def request(method, path, value):
        calls.append((method, path, value))
        if value['query'].startswith('query'):
            return {'data': {'repository': {'id': 'repository-id'}, '__type': {'fields': [{'name': 'updateRefs'}]}}}
        return {'data': {'updateRefs': {'clientMutationId': value['variables']['input']['clientMutationId']}}}
    monkeypatch.setattr(store, 'request', request)
    updates = {'main': {'before': 'a' * 40, 'after': 'b' * 40}, 'aw-messages': {'before': '', 'after': 'c' * 40}}
    store._publish_atomic(updates)
    assert [call[:2] for call in calls] == [('POST', '/graphql'), ('POST', '/graphql')]
    refs = calls[-1][2]['variables']['input']['refUpdates']
    assert refs == [{'name': 'refs/heads/main', 'beforeOid': 'a' * 40, 'afterOid': 'b' * 40, 'force': False},
                    {'name': 'refs/heads/aw-messages', 'beforeOid': '0' * 40, 'afterOid': 'c' * 40, 'force': False}]


def test_known_migration_ref_rejection_stays_a_conflict_and_preserves_original_id(app, monkeypatch):
    store = app.store('sea')
    before = store.head('main')
    original = store._publish_atomic
    attempts = []
    def main_wins(updates):
        attempts.append(updates)
        store.change('main', {'peer-note.md': b'preserved peer work'}, {'peer-note.md': None}, 'Peer advanced main')
        original(updates)
    with monkeypatch.context() as fault:
        fault.setattr(store, '_publish_atomic', main_wins)
        with pytest.raises(Conflict):
            app.message_branch_migrate('sea', 'raced', compatible_writers=['message-v3'])
    with pytest.raises(Conflict):
        app.message_branch_migrate('sea', 'raced', compatible_writers=['message-v3'])
    receipt = read_json(store.operations / 'migrations/raced.json')
    assert receipt['request_id'] == 'raced' and receipt['phase'] == 'rejected'
    assert receipt['updates'] == attempts[0] and attempts[0]['main']['before'] == before
    assert len(attempts) == 1 and store.head('aw-messages') is None
    assert store.snapshot().bytes('peer-note.md') == b'preserved peer work'


def test_real_remote_without_atomic_support_cannot_enable_message_layout(app):
    store = app.store('sea')
    subprocess.run(['git', '--git-dir', store.address, 'config', 'receive.advertiseAtomic', 'false'], check=True)
    before = store.head('main')
    with pytest.raises(Error, match='does not support atomic'):
        app.message_branch_migrate('sea', 'unsupported', compatible_writers=['message-v3'])
    assert store.head('main') == before and store.head('aw-messages') is None
    with pytest.raises(Conflict):
        app.message_branch_migrate('sea', 'unsupported', compatible_writers=['message-v3'])


def test_message_migration_then_worker_migration_preserves_v3_and_message_visibility(app):
    app.create('sea', 'legacy')
    binding = app.reserve('sea', 'legacy')['binding']
    app.bind('sea', 'legacy', binding, 'old-real-entry')
    store = app.store('sea')
    snap = store.snapshot()
    locator = app.workspace_show('sea')['locator']
    old = {'id': 'old', 'from': {'workspace': locator, 'agent': 'legacy'},
           'to': {'workspace': locator, 'agent': 'legacy'}}
    path = layout.shared_path(snap, 'message-index/old.json')
    store.change('main', {path: encode(old)}, {path: None}, 'Legacy message index')
    app.message_branch_migrate('sea', 'first-messages', compatible_writers=['message-v3'])
    app.workers_migrate('sea', 'legacy', 'daily', 'then-worker', compatible_writers=['worker-v2'])
    state = store.message_snapshot()
    assert layout.version(state.main, 'workspace') == 3 and state.branch == 'aw-messages'
    assert state.messages.bytes(path) == encode(old) and state.main.bytes(path) is None
    assert app.legacy_worker('sea', 'legacy', 'messages', 'old') == 'daily'
    assert app.require_binding('sea', 'legacy', binding)[0]['worker_id'] == 'daily'


def test_unsupported_atomic_capability_and_agent_migration_are_refused(fresh, monkeypatch, tmp_path):
    app, _ = fresh
    store = GitHubStore('github:owner/repo', tmp_path)
    calls = []
    def unsupported(method, path, value):
        calls.append(path)
        return {'data': {'repository': {'id': 'id'}, '__type': {'fields': []}}}
    monkeypatch.setattr(store, 'request', unsupported)
    with pytest.raises(Error):
        store._publish_atomic({'main': {'before': '', 'after': 'a'}, 'aw-messages': {'before': '', 'after': 'b'}})
    assert calls == ['/graphql']
    with pytest.raises(Error, match='explicit user operation'):
        commands.execute(app, 'message.migrate', {'request_id': 'forbidden', 'compatible_writers': ['message-v3']},
                         actor=('team', 'owner', 'not-an-authorized-management-entry'))
