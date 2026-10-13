"""Explicit original-chat reconciliation against local Git and read-only native facts."""
from unittest.mock import Mock

import pytest

from agent_workspace import layout, runtime
from agent_workspace.commands import execute
from agent_workspace.util import Conflict, Error, Unavailable, Uncertain, encode, read_json, write_json


@pytest.fixture
def pending(app, monkeypatch):
    app.create("sea", "alice")
    root = app.root("sea", "alice")
    app.configure("sea", "alice", {"kind": "desktop", "model": "fixture-model", "effort": "low"})
    binding = app.reserve("sea", "alice")["binding"]
    receipt = {"binding": binding, "attempted": True, "project_id": "original-project",
               "result": {"threadId": "original-chat", "hostId": "local", "clientThreadId": "original-client",
                          "token": "private-response-value"}}
    write_json(layout.local_path(root, "launch.json"), receipt)
    facts = {"thread": {"id": "original-chat", "hostId": "local", "cwd": str(root),
                        "status": {"type": "idle"}, "model": "fixture-model", "reasoningEffort": "low"}}
    peer = Mock()
    peer.read.side_effect = lambda: facts
    constructor = Mock(return_value=peer)
    monkeypatch.setattr(runtime, "Desktop", constructor)
    return root, binding, receipt, facts, peer, constructor


def test_launch_show_is_read_only_and_limits_original_receipt(app, pending):
    root, binding, receipt, _, peer, constructor = pending
    result = execute(app, "runtime.launch-show", {"workspace": "sea", "agent_id": "alice"})
    assert result["binding"] == binding and result["receipt_matches_current"]
    assert result["current_phase"] == "starting" and result["attempted"]
    assert result["result"]["clientThreadId"] == "original-client"
    assert "token" not in result["result"]
    assert read_json(layout.local_path(root, "launch.json")) == receipt
    constructor.assert_not_called()
    peer.create.assert_not_called()
    peer.notify.assert_not_called()


def test_reconcile_original_chat_binds_once_preserves_unknown_boot_and_receipt(app, pending, monkeypatch):
    root, binding, receipt, _, peer, constructor = pending
    spawn = Mock(side_effect=AssertionError("Reconcile does not start observation or a model turn"))
    monkeypatch.setattr(runtime, "spawn_runner", spawn)
    result = execute(app, "runtime.reconcile-create", {"workspace": "sea", "agent_id": "alice",
                                                       "binding": binding, "session": "original-chat"})
    assert result["state"] == "session_bound" and not result["observation_started"]
    assert result["association"] == "original_launch_thread_id"
    assert result["model_profile"]["effective"] == "native_reported"
    assert constructor.call_args.kwargs == {"read_only": True}
    boot = layout.local_path(root, "inputs") / f"boot-{binding}.json"
    write_json(boot, {**read_json(boot), "state": "outcome_unknown", "result": {"turn": {"id": "original-turn"}}})
    original_bytes = boot.read_bytes()
    result = runtime.reconcile_create(app, "sea", "alice", binding, "original-chat")
    assert result["already_bound"] and result["initial_input_state"] == "outcome_unknown"
    assert boot.read_bytes() == original_bytes
    saved = read_json(layout.local_path(root, "launch.json"))
    for key, value in receipt.items():
        assert saved[key] == value
    assert saved["reconciled"]["session"] == "original-chat"
    assert app.show("sea", "alice")["binding"]["session"] == "original-chat"
    spawn.assert_not_called()
    peer.create.assert_not_called()
    peer.notify.assert_not_called()
    peer.model_choice.assert_not_called()


def test_lost_bind_reply_rechecks_original_result_without_second_bind_or_create(app, pending, monkeypatch):
    root, binding, receipt, _, peer, _ = pending
    actual_bind = app.bind

    def lost_reply(*args, **kwargs):
        actual_bind(*args, **kwargs)
        raise Uncertain("Original shared bind committed; its reply was lost")

    bind = Mock(side_effect=lost_reply)
    monkeypatch.setattr(app, "bind", bind)
    with pytest.raises(Uncertain):
        runtime.reconcile_create(app, "sea", "alice", binding, "original-chat")
    assert read_json(layout.local_path(root, "launch.json"))["reconciled"]["session"] == "original-chat"
    result = runtime.reconcile_create(app, "sea", "alice", binding, "original-chat")
    assert result["already_bound"] and result["association"] == "original_launch_thread_id"
    assert result["initial_input_state"] == "queued" and bind.call_count == 1
    peer.create.assert_not_called()
    peer.notify.assert_not_called()


def test_missing_original_thread_id_keeps_unknown_without_probing_candidate(app, pending):
    root, binding, receipt, _, _, constructor = pending
    receipt["result"] = {"clientThreadId": "original-client"}
    write_json(layout.local_path(root, "launch.json"), receipt)
    result = runtime.reconcile_create(app, "sea", "alice", binding, "candidate-in-same-directory")
    assert result["state"] == "outcome_unknown" and not result["original_create_result_confirmed"]
    assert not result["observation_started"]
    assert read_json(layout.local_path(root, "launch.json")) == receipt
    assert app.show("sea", "alice")["binding"]["phase"] == "starting"
    constructor.assert_not_called()


def test_unconfirmed_native_identity_directory_state_or_model_cannot_bind(app, pending):
    root, binding, receipt, facts, peer, _ = pending
    thread = dict(facts["thread"])
    for field, value in (("id", "other-chat"), ("hostId", "remote"), ("cwd", str(root.parent)),
                         ("status", {"type": "notLoaded"}), ("model", "other-model"), ("reasoningEffort", "high")):
        facts["thread"] = {**thread, field: value}
        with pytest.raises(Error):
            runtime.reconcile_create(app, "sea", "alice", binding, "original-chat")
        assert read_json(layout.local_path(root, "launch.json")) == receipt
    facts["thread"] = thread
    peer.read.side_effect = Unavailable("Original native connection unavailable")
    with pytest.raises(Unavailable):
        runtime.reconcile_create(app, "sea", "alice", binding, "original-chat")
    assert app.show("sea", "alice")["binding"]["phase"] == "starting"
    peer.create.assert_not_called()
    peer.notify.assert_not_called()


def test_reconcile_refuses_unrelated_receipt_selection_or_controller(app, pending):
    root, binding, receipt, _, _, constructor = pending
    with pytest.raises(Conflict):
        runtime.reconcile_create(app, "sea", "alice", binding, "different-chat")
    with pytest.raises(Conflict):
        runtime.reconcile_create(app, "sea", "alice", "old-binding", "original-chat")
    write_json(layout.local_path(root, "launch.json"), {"binding": binding, "attempted": False})
    with pytest.raises(Conflict):
        runtime.reconcile_create(app, "sea", "alice", binding, "original-chat")
    write_json(layout.local_path(root, "launch.json"), receipt)
    store = app.store("sea")
    snap = store.snapshot()
    path = layout.shared_path(snap, f"bindings/{binding}.json")
    entry = snap.json(path)
    store.change("main", {path: encode({**entry, "controller": "original-controller"})},
                 {path: snap.entries[path]}, "Unreleased original controller fixture")
    with pytest.raises(Conflict, match="controller"):
        runtime.reconcile_create(app, "sea", "alice", binding, "original-chat")
    constructor.assert_not_called()
    with pytest.raises(Error, match="user-management"):
        execute(app, "runtime.reconcile-create", {"binding": binding, "session": "original-chat"},
                actor=("sea", "alice", binding))


def test_reconcile_requires_original_execution_source(app, pending):
    _, binding, _, _, _, constructor = pending
    store = app.store("sea")
    snap = store.snapshot()
    path = layout.shared_path(snap, f"bindings/{binding}.json")
    entry = snap.json(path)
    for execution in (None, {**entry["execution"], "installation_id": "other-home"}):
        store.change("main", {path: encode({**entry, "execution": execution})},
                     {path: snap.entries[path]}, "Unconfirmed execution fixture")
        with pytest.raises(Conflict, match="execution"):
            runtime.reconcile_create(app, "sea", "alice", binding, "original-chat")
        snap = store.snapshot()
    constructor.assert_not_called()
