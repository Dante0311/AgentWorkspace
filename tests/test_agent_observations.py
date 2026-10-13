"""Shared authority uses real local Git; native/local status observations are fixtures."""
import pytest

from agent_workspace.app import App
from agent_workspace.cli import parser
from agent_workspace.commands import execute
from agent_workspace.maintenance import installation_id
from agent_workspace.server import build_state
from agent_workspace.util import encode, write_json


@pytest.fixture
def observed_app(app, monkeypatch):
    resources = app._resources
    monkeypatch.setattr(app, "_resources", lambda: {**resources(), "AGENTS.md": b"Agent responsibilities\n"})
    app.create("sea", "alice")
    return app


def test_current_binding_uses_its_copy_and_retains_old_observation(observed_app, tmp_path):
    app = observed_app
    first = app.root("sea", "alice")
    second = tmp_path / "second-copy"
    app.connect_agent("sea", "alice", second)
    entry = app.reserve("sea", "alice", second)
    binding = entry["binding"]
    app.bind("sea", "alice", binding, "fixture-current-session", second)
    write_json(first / ".agentworkspace/local/runtime/entry.json", {"binding": "fixture-old-binding"})
    write_json(first / ".agentworkspace/local/runtime/status.json", {"binding": "fixture-old-binding", "session": "fixture-old-session",
                                                "state": "fixture-old-busy", "observed_at": "past-observation"})
    write_json(second / ".agentworkspace/local/runtime/status.json", {"binding": binding, "session": "fixture-current-session",
                                                 "state": "fixture-current-idle", "observed_at": "current-observation"})
    value = app.show("sea", "alice")
    assert value["directory"] == str(second)
    assert value["runtime"]["state"] == "fixture-current-idle"
    assert value["binding"]["execution"] == {"installation_id": installation_id(app), "directory": str(second)}
    copies = {copy["directory"]: copy for copy in value["copies"]}
    assert copies[str(first)]["runtime"]["state"] == "fixture-old-busy"
    assert copies[str(first)]["runtime"]["observed_at"] == "past-observation"
    assert copies[str(first)]["entry_matches_current"] is False
    assert copies[str(second)]["entry_matches_current"] is True
    assert copies[str(second)]["runtime_matches_current"] is True
    projected = build_state(app)["agents"][0]
    assert projected["directory"] == str(second)
    assert projected["runtime"]["state"] == "fixture-current-idle"
    assert len(projected["copies"]) == 2
    assert app.show("sea", "alice", first)["runtime"]["state"] == "unknown"


def test_current_remote_installation_is_not_inferred_from_local_copy(observed_app, tmp_path):
    app = observed_app
    peer = App(tmp_path / "peer-home")
    peer.workspace_connect("peer", str(tmp_path / "sea.git"))
    peer.connect_agent("peer", "alice", tmp_path / "peer-copy")
    binding = peer.reserve("peer", "alice")["binding"]
    peer.bind("peer", "alice", binding, "fixture-peer-session")
    local = app.root("sea", "alice")
    # Even a copied receipt/status cannot override the shared execution location.
    write_json(local / ".agentworkspace/local/runtime/entry.json", {"binding": binding})
    write_json(local / ".agentworkspace/local/runtime/status.json", {"binding": binding, "session": "fixture-peer-session", "state": "idle"})
    value = app.show("sea", "alice")
    assert value["binding"]["execution"]["installation_id"] == installation_id(peer)
    assert value["directory"] is None
    assert value["runtime"]["state"] == "unknown"
    assert value["copies"][0]["execution_matches_local"] is False
    assert len(value["copies"]) == 1


def test_current_binding_with_different_observed_session_is_unknown(observed_app):
    app = observed_app
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "fixture-current-session")
    root = app.root("sea", "alice")
    write_json(root / ".agentworkspace/local/runtime/status.json", {"binding": binding, "session": "fixture-different-session", "state": "busy"})
    value = app.show("sea", "alice")
    assert value["runtime"]["state"] == "unknown"
    assert value["copies"][0]["runtime"]["session"] == "fixture-different-session"
    assert value["copies"][0]["runtime_matches_current"] is False


def test_history_retains_released_and_current_bindings_and_copies(observed_app, tmp_path):
    app = observed_app
    first = app.root("sea", "alice")
    old = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", old, "fixture-old-session")
    checkpoint = app.checkpoint("sea", "alice", "saved", binding=old, checkpoint_id="point")
    app.stop("sea", "alice", old, checkpoint["id"])
    app.finish_stop("sea", "alice", old, observed_idle=True)
    second = tmp_path / "second-copy"
    app.connect_agent("sea", "alice", second)
    current = app.reserve("sea", "alice", second)["binding"]
    app.bind("sea", "alice", current, "fixture-new-session", second)
    history = execute(app, "agent.history", {"workspace": "sea", "agent_id": "alice"})
    by_id = {entry["id"]: entry for entry in history["bindings"]}
    assert by_id[old]["phase"] == "released"
    assert by_id[current]["phase"] == "active"
    assert by_id[old]["execution"]["directory"] == str(first)
    assert by_id[current]["execution"]["directory"] == str(second)
    view = app.show("sea", "alice")
    assert {entry["id"] for entry in view["history"]} == {old, current}
    assert set(view["directories"]) == {str(first), str(second)}
    assert view["current"] == current
    assert parser().parse_args(["agent", "history", "alice"]).agent_id == "alice"


def test_old_binding_without_execution_source_is_not_backfilled(observed_app):
    app = observed_app
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "fixture-legacy-session")
    store = app.store("sea")
    snap = store.snapshot()
    path = f".agentworkspace/bindings/{binding}.json"
    legacy = snap.json(path)
    del legacy["execution"]
    store.change("main", {path: encode(legacy)}, {path: snap.entries[path]}, "Legacy record fixture")
    before = store.head("main")
    value = app.show("sea", "alice")
    assert "execution" not in value["binding"]
    assert "execution" not in value["history"][0]
    assert value["copies"][0]["execution_matches_local"] is False
    assert store.head("main") == before


def test_damaged_old_copy_preserves_healthy_current_copy_and_history(observed_app, tmp_path):
    app = observed_app
    old_copy = app.root("sea", "alice")
    current_copy = tmp_path / "current-copy"
    app.connect_agent("sea", "alice", current_copy)
    binding = app.reserve("sea", "alice", current_copy)["binding"]
    app.bind("sea", "alice", binding, "fixture-current-session", current_copy)
    damaged = old_copy / ".agentworkspace/local/runtime/status.json"
    damaged.write_bytes(b"{broken")
    write_json(current_copy / ".agentworkspace/local/runtime/status.json", {"binding": binding, "session": "fixture-current-session",
                                                       "state": "idle"})
    before = app.store("sea").head("main")
    value = app.show("sea", "alice")
    assert value["binding"]["id"] == binding
    assert value["directory"] == str(current_copy)
    assert value["runtime"]["state"] == "idle"
    assert value["history"][0]["id"] == binding
    copies = {copy["directory"]: copy for copy in value["copies"]}
    broken = copies[str(old_copy)]
    assert broken["unknown_reason"] == "local_copy_observation_failed"
    assert "JSONDecodeError" in broken["observation_error"]
    assert broken["observation_source"]["directory"] == str(old_copy)
    assert "runtime" not in broken and "entry_binding" not in broken
    assert copies[str(current_copy)]["runtime_matches_current"] is True
    explicit = app.show("sea", "alice", old_copy)
    assert explicit["directory"] == str(old_copy)
    assert explicit["runtime"]["state"] == "unknown"
    assert explicit["binding"]["id"] == binding
    state = build_state(app)
    projected = state["agents"][0]
    assert projected["runtime"]["state"] == "idle"
    assert projected["history"][0]["id"] == binding
    assert state["errors"][0]["directory"] == str(old_copy)
    assert damaged.read_bytes() == b"{broken"
    assert app.store("sea").head("main") == before
