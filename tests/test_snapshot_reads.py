"""Pinned snapshot reuse does not cache mutable JSON or a later branch head."""
import pytest

from agent_workspace import layout
from agent_workspace.gitstore import GitStore, Snapshot
from agent_workspace.util import RetryableRead, encode


def test_pinned_layout_and_repeated_reads_load_each_blob_once(tmp_path, monkeypatch):
    remote = tmp_path / 'remote.git'
    GitStore.initialize(remote)
    store = GitStore(str(remote), tmp_path / 'home')
    data = encode({'name': 'original'})
    store.branch('main', {layout.MARKER: layout.marker('workspace'),
                          '.agentworkspace/workspace.json': data, 'reference.json': data})
    snap = store.snapshot()
    original = store.blob
    reads = []
    def read(sha):
        reads.append(sha)
        return original(sha)
    monkeypatch.setattr(store, 'blob', read)
    assert layout.shared_path(snap, 'workspace.json') == '.agentworkspace/workspace.json'
    first = snap.json('.agentworkspace/workspace.json')
    first['name'] = 'caller edit'
    assert snap.json('.agentworkspace/workspace.json')['name'] == 'original'
    assert snap.bytes('reference.json') == data
    assert layout.shared_path(snap, 'agents/') == '.agentworkspace/agents/'
    assert snap.all() == {layout.MARKER: layout.marker('workspace'),
                          '.agentworkspace/workspace.json': data, 'reference.json': data}
    assert len(reads) == 2 and len(set(reads)) == 2
    store.change('main', {'.agentworkspace/workspace.json': encode({'name': 'new head'})},
                 {'.agentworkspace/workspace.json': snap.entries['.agentworkspace/workspace.json']}, 'Later write')
    newer = store.snapshot()
    assert newer.revision != snap.revision
    assert newer.json('.agentworkspace/workspace.json')['name'] == 'new head'
    assert snap.json('.agentworkspace/workspace.json')['name'] == 'original'


def test_initial_read_failure_is_not_cached_as_missing_or_success(monkeypatch):
    class Store:
        def blob(self, sha):
            raise RetryableRead('Fixture original read unavailable')
    store = Store()
    snap = Snapshot(store, 'pinned', {'fact.json': 'original-blob'})
    with pytest.raises(RetryableRead):
        snap.json('fact.json')
    monkeypatch.setattr(store, 'blob', lambda sha: encode({'state': 'actual original bytes'}))
    assert snap.json('fact.json') == {'state': 'actual original bytes'}
    assert snap.json('not-in-this-commit.json') is None
