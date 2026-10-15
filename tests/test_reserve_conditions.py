"""Continuation conditions use actual temporary bare Git; native sessions are fixtures."""
import pytest

from agent_workspace.app import App
from agent_workspace.util import Conflict


@pytest.fixture
def released_agent(app, monkeypatch):
    resources = app._resources
    monkeypatch.setattr(app, "_resources", lambda: {**resources(), "AGENTS.md": b"Responsibilities\n"})
    app.create("sea", "alice")
    point = app.checkpoint("sea", "alice", "saved material", checkpoint_id="saved-point")
    old = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", old, "fixture-original-session")
    app.stop("sea", "alice", old, point["id"])
    handoff = app.finish_stop("sea", "alice", old, observed_idle=True)
    return app, point["id"], handoff


def test_matching_handoff_can_be_consumed(released_agent):
    app, _, handoff = released_agent
    result = app.reserve("sea", "alice", binding_id="matched-successor", expected_handoff=handoff["id"])
    snap = app.store("sea").snapshot()
    assert snap.json(".agentworkspace/agents/alice.json")["current"] == result["binding"]
    assert snap.json(f".agentworkspace/bindings/{result['binding']}.json")["handoff"] == handoff["id"]
    assert snap.json(f".agentworkspace/handoffs/{handoff['id']}.json")["consumed_by"] == result["binding"]


def test_old_continuation_rejects_forced_successor_but_manual_reserve_can_use_it(released_agent):
    app, checkpoint, old_handoff = released_agent
    intervening = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", intervening, "fixture-intervening-session")
    forced = app.takeover("sea", "alice", intervening, checkpoint, confirm=True)["handoff"]
    store = app.store("sea")
    before = store.head("main")
    local_entry = app.root("sea", "alice") / ".agentworkspace/local/runtime/entry.json"
    before_entry = local_entry.read_bytes()
    with pytest.raises(Conflict):
        app.reserve("sea", "alice", binding_id="stale-before-read", expected_handoff=old_handoff["id"])
    snap = store.snapshot()
    assert snap.revision == before
    assert snap.json(".agentworkspace/agents/alice.json")["handoff"] == forced["id"]
    assert snap.json(".agentworkspace/agents/alice.json")["current"] is None
    assert snap.json(f".agentworkspace/handoffs/{forced['id']}.json")["consumed_by"] is None
    assert ".agentworkspace/bindings/stale-before-read.json" not in snap.entries
    assert local_entry.read_bytes() == before_entry
    # Explicit manual entry preparation keeps the existing default behavior.
    manual = app.reserve("sea", "alice", binding_id="manual-successor")
    snap = store.snapshot()
    assert snap.json(f".agentworkspace/handoffs/{forced['id']}.json")["consumed_by"] == manual["binding"]
    assert snap.json(".agentworkspace/agents/alice.json")["current"] == manual["binding"]


def test_change_after_handoff_read_is_rejected_by_existing_version_conditions(released_agent, tmp_path, monkeypatch):
    app, checkpoint, old_handoff = released_agent
    peer = App(tmp_path / "peer-home")
    peer.workspace_connect("peer", str(tmp_path / "sea.git"))
    peer.connect_agent("peer", "alice", tmp_path / "peer-copy")
    store = app.store("sea")
    change = store.change
    forced_results = []
    local_entry = app.root("sea", "alice") / ".agentworkspace/local/runtime/entry.json"
    before_entry = local_entry.read_bytes()

    def change_after_read(branch, changes, expected, message, **kwargs):
        if message == "Reserve entry stale-after-read":
            intervening = peer.reserve("peer", "alice")["binding"]
            peer.bind("peer", "alice", intervening, "fixture-peer-session")
            forced_results.append(peer.takeover("peer", "alice", intervening, checkpoint, confirm=True)["handoff"])
        return change(branch, changes, expected, message, **kwargs)

    monkeypatch.setattr(store, "change", change_after_read)
    with pytest.raises(Conflict):
        app.reserve("sea", "alice", binding_id="stale-after-read", expected_handoff=old_handoff["id"])
    assert len(forced_results) == 1
    forced = forced_results[0]
    snap = store.snapshot()
    assert snap.json(".agentworkspace/agents/alice.json")["handoff"] == forced["id"]
    assert snap.json(".agentworkspace/agents/alice.json")["current"] is None
    assert snap.json(f".agentworkspace/handoffs/{forced['id']}.json")["consumed_by"] is None
    assert ".agentworkspace/bindings/stale-after-read.json" not in snap.entries
    assert local_entry.read_bytes() == before_entry


def test_expected_handoff_cannot_be_used_for_a_fresh_agent(app, monkeypatch):
    resources = app._resources
    monkeypatch.setattr(app, "_resources", lambda: {**resources(), "AGENTS.md": b"Responsibilities\n"})
    app.create("sea", "alice")
    store = app.store("sea")
    before = store.head("main")
    with pytest.raises(Conflict):
        app.reserve("sea", "alice", binding_id="missing-handoff", expected_handoff="fixture-absent-handoff")
    snap = store.snapshot()
    assert snap.revision == before
    assert snap.json(".agentworkspace/agents/alice.json")["current"] is None
    assert ".agentworkspace/bindings/missing-handoff.json" not in snap.entries
