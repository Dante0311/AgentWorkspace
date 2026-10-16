"""Current execution source plus read-only native facts; no real Desktop/model acceptance."""
from agent_workspace import layout
from unittest.mock import Mock

import pytest

from agent_workspace import runtime
from agent_workspace.commands import execute
from agent_workspace.util import Unavailable, encode, read_json, write_json


@pytest.fixture
def desktop(app, monkeypatch):
    app.create("sea", "alice")
    root = app.root("sea", "alice")
    app.configure("sea", "alice", {"kind": "desktop", "model": "fixture-model", "effort": "low"})
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "actual-native-id")
    facts = {"thread": {"id": "actual-native-id", "hostId": "local", "cwd": str(root), "status": {"type": "active"}}}
    peer = Mock()
    peer.tools = {"read_thread", "send_message_to_thread"}
    peer.read.side_effect = lambda: facts
    constructor = Mock(return_value=peer)
    monkeypatch.setattr(runtime, "Desktop", constructor)
    return root, binding, facts, peer, constructor


def test_observe_returns_actual_current_local_session_without_model_input(app, desktop):
    root, binding, _, peer, constructor = desktop
    result = execute(app, "runtime.desktop-observe", {"workspace": "sea", "agent_id": "alice"})
    assert result["local_session_confirmed"] and result["phase"] == "active"
    assert result["binding"] == binding and result["session"] == "actual-native-id"
    assert result["native_host"] == "local" and result["native_cwd"] == str(root) and result["native_state"] == "busy"
    assert constructor.call_args.kwargs["read_only"] is True
    peer.read.assert_called_once()
    peer.close.assert_called_once()
    peer.create.assert_not_called()
    peer.notify.assert_not_called()
    peer.model_choice.assert_not_called()


@pytest.mark.parametrize("field,value", [("hostId", "another-host"), ("hostId", None), ("cwd", "wrong-folder"),
                                         ("status", {"type": "notLoaded"})])
def test_native_metadata_or_state_does_not_establish_local_entry(app, desktop, field, value):
    _, _, facts, peer, _ = desktop
    facts["thread"][field] = value
    result = runtime.desktop_observe(app, "sea", "alice")
    assert not result["local_session_confirmed"] and result["unknown_reason"]
    peer.notify.assert_not_called()


@pytest.mark.parametrize("execution", [None, {"installation_id": "other-installation", "directory": "remote-copy"}])
def test_missing_or_remote_execution_does_not_probe_native(app, desktop, execution):
    _, binding, _, _, constructor = desktop
    store = app.store("sea")
    snap = store.snapshot()
    path = layout.shared_path(snap, f"bindings/{binding}.json")
    entry = snap.json(path)
    entry["execution"] = execution
    store.change("main", {path: encode(entry)}, {path: snap.entries[path]}, "Fixture unavailable execution source")
    result = runtime.desktop_observe(app, "sea", "alice")
    assert not result["local_session_confirmed"]
    constructor.assert_not_called()


def test_observation_rechecks_current_authority_after_native_read(app, desktop):
    _, binding, facts, peer, _ = desktop
    point = app.checkpoint("sea", "alice", "explicit fixture handoff", binding=binding)

    def read():
        app.stop("sea", "alice", binding, point["id"])
        return facts

    peer.read.side_effect = read
    result = runtime.desktop_observe(app, "sea", "alice")
    assert not result["local_session_confirmed"] and result["unknown_reason"] == "binding_changed_during_observation"


def test_unavailable_native_connection_remains_unknown(app, desktop):
    root, _, _, peer, _ = desktop
    peer.read.side_effect = Unavailable("fixture connection lost")
    before = read_json(layout.local_path(root, "entry.json"))
    result = runtime.desktop_observe(app, "sea", "alice")
    assert not result["local_session_confirmed"] and result["unknown_reason"] == "native_observation_failed"
    assert read_json(layout.local_path(root, "entry.json")) == before
    peer.close.assert_called_once()


def test_wrong_local_entry_and_read_only_control_cannot_qualify_direct_send(app, desktop):
    root, binding, _, peer, constructor = desktop
    local = read_json(layout.local_path(root, "entry.json"))
    write_json(layout.local_path(root, "entry.json"), {**local, "binding": "old-binding"})
    assert not runtime.desktop_observe(app, "sea", "alice")["local_session_confirmed"]
    constructor.assert_not_called()
    write_json(layout.local_path(root, "entry.json"), local)
    peer.tools = {"read_thread"}
    result = runtime.desktop_observe(app, "sea", "alice")
    assert result["binding"] == binding and not result["local_session_confirmed"]
