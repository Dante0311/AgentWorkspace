"""Granted repair delegates once; recovery acceptance is separate from observation.

The shared recovery callback is a contract fixture. Actual Runner and native
session recovery are verified by Runtime and the combined acceptance tests.
"""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent_workspace import backend, commands, layout, maintenance
from agent_workspace.util import Conflict, Error, Uncertain, encode, read_json, write_json


@pytest.fixture
def recovery_team(app):
    for aid in ("alice", "maintainer"):
        app.create("sea", aid)
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "original-session")
    store = app.store("sea")
    snap = store.snapshot()
    meta = snap.json(".agentworkspace/workspace.json")
    meta["caretakers"] = {"maintainer": "maintainer"}
    store.change("main", {".agentworkspace/workspace.json": encode(meta)},
                 {".agentworkspace/workspace.json": snap.entries[".agentworkspace/workspace.json"]},
                 "Register isolated recovery maintainer")
    actor_binding = app.reserve("sea", "maintainer")["binding"]
    app.bind("sea", "maintainer", actor_binding, "maintainer-session")
    actor = ("sea", "maintainer", actor_binding)
    arguments = {"agent_id": "alice", "action": "runtime-recover",
                 "request_id": "original-recovery", "expected_binding": binding}
    return app, actor, arguments


@pytest.mark.parametrize("state", ["recovery_paused", "recovery_blocked", "starting_runner", "runner_present"])
def test_recovery_result_is_preserved_and_duplicate_requests_only_observe(recovery_team, monkeypatch, state):
    app, actor, args = recovery_team
    result = {"state": state, "binding": args["expected_binding"], "session": "original-session"}
    recover = Mock(return_value=result)
    monkeypatch.setattr(backend, "recover", recover, raising=False)
    maintenance.grant(app, "sea", "maintainer", ["maintenance.repair"], ["alice"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda _: commands.execute(app, "maintenance.repair", args, actor=actor), range(2)))
    recover.assert_called_once_with(app, "sea", "alice", expected_binding=args["expected_binding"])
    assert all(value["state"] == state and value["result"] == result for value in receipts)
    assert all(value["verification"]["runtime"]["state"] == "active" for value in receipts)
    assert read_json(maintenance.folder(app, "sea") / "repairs/original-recovery.json")["result"] == result

    point = app.checkpoint("sea", "alice", "later handoff", binding=args["expected_binding"])
    app.stop("sea", "alice", args["expected_binding"], point["id"])
    app.finish_stop("sea", "alice", args["expected_binding"], observed_idle=True)
    successor = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", successor, "successor-session")
    receipt = commands.execute(app, "maintenance.repair", args, actor=actor)
    assert receipt["result"] == result
    assert receipt["verification"]["runtime"]["state"] == "released"
    assert receipt["verification"]["runtime"]["session"] == "original-session"
    assert app.agent("sea", "alice")["current"] == successor
    assert recover.call_count == 1
    with pytest.raises(Conflict):
        commands.execute(app, "maintenance.repair", {**args, "expected_binding": successor}, actor=actor)


def test_recovery_requires_target_grant_current_actor_and_original_binding(recovery_team, monkeypatch):
    app, actor, args = recovery_team
    recover = Mock()
    monkeypatch.setattr(backend, "recover", recover, raising=False)
    with pytest.raises(Error):
        commands.execute(app, "maintenance.repair", args, actor=actor)
    maintenance.grant(app, "sea", "maintainer", ["maintenance.repair"], ["alice"])
    with pytest.raises(Error):
        commands.execute(app, "maintenance.repair", {**args, "agent_id": "ungranted"}, actor=actor)
    with pytest.raises(Conflict):
        commands.execute(app, "maintenance.repair", args, actor=("sea", "maintainer", "old-actor"))
    with pytest.raises(Error):
        commands.execute(app, "maintenance.repair", {**args, "expected_binding": None}, actor=actor)
    with pytest.raises(Conflict):
        commands.execute(app, "maintenance.repair", {**args, "expected_binding": "old-target"}, actor=actor)
    assert read_json(maintenance.folder(app, "sea") / "repairs/original-recovery.json") is None
    maintenance.grant(app, "sea", "maintainer", [], [])
    with pytest.raises(Error):
        commands.execute(app, "maintenance.repair", args, actor=actor)
    recover.assert_not_called()


def test_unknown_recovery_is_never_replayed(recovery_team, monkeypatch):
    app, actor, args = recovery_team
    maintenance.grant(app, "sea", "maintainer", ["maintenance.repair"], ["alice"])
    recover = Mock(side_effect=Uncertain("original recovery result is unknown"))
    monkeypatch.setattr(backend, "recover", recover, raising=False)
    with pytest.raises(Uncertain):
        commands.execute(app, "maintenance.repair", args, actor=actor)
    receipt = commands.execute(app, "maintenance.repair", args, actor=actor)
    assert receipt["state"] == "outcome_unknown" and "result" not in receipt
    assert receipt["verification"]["runtime"]["binding"] == args["expected_binding"]
    recover.assert_called_once()


def test_failed_recovery_verification_only_retries_observation(recovery_team, monkeypatch):
    app, actor, args = recovery_team
    maintenance.grant(app, "sea", "maintainer", ["maintenance.repair"], ["alice"])
    result = {"state": "starting_runner", "binding": args["expected_binding"]}
    recover = Mock(return_value=result)
    monkeypatch.setattr(backend, "recover", recover, raising=False)
    doctor = Mock(side_effect=[Error("health observation unavailable"), {"state": "healthy", "issues": []}])
    monkeypatch.setattr(maintenance, "doctor", doctor)
    first = commands.execute(app, "maintenance.repair", args, actor=actor)
    assert first["state"] == "starting_runner" and first["result"] == result
    assert first["verification"]["state"] == "unavailable"
    second = commands.execute(app, "maintenance.repair", args, actor=actor)
    assert second["verification"]["runtime"]["state"] == "active"
    assert doctor.call_count == 2
    recover.assert_called_once()


@pytest.mark.parametrize("condition", ["user_paused", "execution_source_missing"])
def test_shared_runtime_recovery_preserves_pause_or_missing_source(recovery_team, condition):
    app, actor, args = recovery_team
    maintenance.grant(app, "sea", "maintainer", ["maintenance.repair"], ["alice"])
    binding = args["expected_binding"]
    root = app.root("sea", "alice")
    control = layout.local_path(root, "control.json")
    if condition == "user_paused":
        write_json(control, {"stop": binding})
        original_control = control.read_bytes()
    else:
        store = app.store("sea")
        snap = store.snapshot()
        path = layout.shared_path(snap, f"bindings/{binding}.json")
        entry = snap.json(path)
        entry.pop("execution")
        store.change("main", {path: encode(entry)}, {path: snap.entries[path]}, "Remove isolated execution source")
    snap = app.store("sea").snapshot()
    original_entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
    manager = backend.Backend(app, SimpleNamespace(server_port=0))
    app.backend = manager
    try:
        first = commands.execute(app, "maintenance.repair", args, actor=actor)
        second = commands.execute(app, "maintenance.repair", args, actor=actor)
        state = "recovery_paused" if condition == "user_paused" else "recovery_blocked"
        assert first["state"] == second["state"] == state
        assert first["result"]["reason_code"] == condition
        assert not manager.runners and not manager.threads
        assert not manager.maintenance.is_alive() and not manager.restore.is_alive()
        if condition == "user_paused":
            assert control.read_bytes() == original_control
        snap = app.store("sea").snapshot()
        assert snap.json(layout.shared_path(snap, f"bindings/{binding}.json")) == original_entry
    finally:
        del app.backend
