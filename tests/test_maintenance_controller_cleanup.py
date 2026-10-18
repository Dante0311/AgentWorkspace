"""Public maintenance integration; Runtime's cleanup is a contract fixture here."""
from concurrent.futures import ThreadPoolExecutor
import json
from unittest.mock import Mock

import pytest

from agent_workspace import backend, cli, commands, layout, maintenance, runtime
from agent_workspace.util import Conflict, Error, Uncertain, encode, read_json, write_json


@pytest.fixture
def cleanup_team(app):
    for aid in ("alice", "maintainer"):
        app.create("sea", aid)
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "original-session")
    store = app.store("sea")
    snap = store.snapshot()
    meta_path = layout.shared_path(snap, "workspace.json")
    entry_path = layout.shared_path(snap, f"bindings/{binding}.json")
    meta, entry = snap.json(meta_path), snap.json(entry_path)
    meta["caretakers"] = {"maintainer": "maintainer"}
    entry["controller"] = "original-controller"
    store.change("main", {meta_path: encode(meta), entry_path: encode(entry)},
                 {meta_path: snap.entries[meta_path], entry_path: snap.entries[entry_path]},
                 "Register isolated cleanup owner and caretaker")
    actor_binding = app.reserve("sea", "maintainer")["binding"]
    app.bind("sea", "maintainer", actor_binding, "maintainer-session")
    args = {"agent_id": "alice", "action": "controller-cleanup", "request_id": "original-cleanup",
            "expected_binding": binding, "expected_controller": "original-controller",
            "expected_session": "original-session", "expected_revision": maintenance.doctor(app, "sea")["revision"],
            "cleanup_commit": "original-cleanup-commit"}
    return app, ("sea", "maintainer", actor_binding), args


def test_public_cleanup_authority_duplicates_cli_and_changed_owner(cleanup_team, monkeypatch, capsys):
    app, actor, args = cleanup_team
    result = {"state": "controller_cleared", "binding": args["expected_binding"],
              "runner_started": False, "binding_released": False}

    def clear(*unused, **kwargs):
        store = app.store("sea")
        snap = store.snapshot()
        path = layout.shared_path(snap, f"bindings/{args['expected_binding']}.json")
        entry = snap.json(path)
        del entry["controller"]
        store.change("main", {path: encode(entry)}, {path: snap.entries[path]}, "Contract fixture cleanup")
        return result

    cleanup = Mock(side_effect=clear)
    monkeypatch.setattr(runtime, "cleanup_controller", cleanup, raising=False)
    recover, start = Mock(), Mock()
    monkeypatch.setattr(backend, "recover", recover)
    monkeypatch.setattr(runtime, "start", start)
    with pytest.raises(Error):
        commands.execute(app, "maintenance.repair", args, actor=actor)
    maintenance.grant(app, "sea", "maintainer", ["maintenance.repair"], ["alice"])
    with pytest.raises(Error):
        commands.execute(app, "maintenance.repair", {**args, "agent_id": "ungranted"}, actor=actor)
    with pytest.raises(Error):
        commands.execute(app, "maintenance.repair", args, actor=("sea", "maintainer", "old-actor"))
    original_fields = ("expected_binding", "expected_controller", "expected_session", "expected_revision", "cleanup_commit")
    for field in original_fields:
        with pytest.raises(Error):
            commands.execute(app, "maintenance.repair", {**args, field: None}, actor=actor)
    path = maintenance.folder(app, "sea") / "repairs/original-cleanup.json"
    assert not path.exists()
    cleanup.assert_not_called()

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda _: commands.execute(app, "maintenance.repair", args, actor=actor), range(2)))
    cleanup.assert_called_once_with(app, "sea", "alice", **{key: args[key] for key in original_fields})
    assert all(item["state"] == "controller_cleared" and item["result"] == result for item in receipts)
    assert all(item["verification"]["cleanup"]["state"] == "controller_cleared" for item in receipts)
    expected_request = {key: value for key, value in args.items() if key != "request_id"}
    expected_request.update(operation_id=None, bridge=None, expected_generation=None)
    assert read_json(path)["request"] == expected_request

    for name, value in zip(("AW_WORKSPACE", "AW_AGENT", "AW_BINDING"), actor):
        monkeypatch.setenv(name, value)
    argv = ["--home", str(app.home), "maintenance", "repair", "alice",
            "--repair-action", "controller-cleanup", "--request-id", args["request_id"]]
    for key in original_fields:
        argv.extend(["--" + key.replace("_", "-"), args[key]])
    assert cli.main(argv) == 0
    assert json.loads(capsys.readouterr().out)["result"]["result"] == result
    for field in original_fields:
        with pytest.raises(Conflict):
            commands.execute(app, "maintenance.repair", {**args, field: "changed"}, actor=actor)

    store = app.store("sea")
    snap = store.snapshot()
    entry_path = layout.shared_path(snap, f"bindings/{args['expected_binding']}.json")
    entry = snap.json(entry_path)
    entry["controller"] = "replacement-controller"
    store.change("main", {entry_path: encode(entry)}, {entry_path: snap.entries[entry_path]}, "New controller")
    receipt = commands.execute(app, "maintenance.repair", args, actor=actor)
    assert receipt["result"] == result
    assert receipt["verification"]["cleanup"]["state"] == "request_changed"
    assert receipt["verification"]["cleanup"]["controller"] == "replacement-controller"
    point = app.checkpoint("sea", "alice", "later handoff", binding=args["expected_binding"])
    app.stop("sea", "alice", args["expected_binding"], point["id"])
    app.finish_stop("sea", "alice", args["expected_binding"], observed_idle=True)
    successor = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", successor, "successor-session")
    receipt = commands.execute(app, "maintenance.repair", args, actor=actor)
    observed = receipt["verification"]["cleanup"]
    assert observed["state"] == "request_changed" and observed["binding"] == args["expected_binding"]
    assert observed["session"] == "original-session" and observed["current_binding"] == successor
    assert app.agent("sea", "alice")["current"] == successor
    saved = path.read_bytes()
    maintenance.grant(app, "sea", "maintainer", [], [])
    with pytest.raises(Error):
        commands.execute(app, "maintenance.repair", args, actor=actor)
    assert path.read_bytes() == saved
    cleanup.assert_called_once()
    recover.assert_not_called()
    start.assert_not_called()


def test_cleanup_results_unknowns_and_interrupted_attempt_are_not_replayed(cleanup_team, monkeypatch):
    app, actor, args = cleanup_team
    maintenance.grant(app, "sea", "maintainer", ["maintenance.repair"], ["alice"])
    root = app.root("sea", "alice")
    control = layout.local_path(root, "control.json")
    unknown_input = layout.local_path(root, "inputs/unknown.json")
    write_json(control, {"stop": args["expected_binding"]})
    write_json(unknown_input, {"id": "unknown", "binding": args["expected_binding"], "state": "outcome_unknown"})
    original = (control.read_bytes(), unknown_input.read_bytes())
    cleanup = Mock()
    monkeypatch.setattr(runtime, "cleanup_controller", cleanup, raising=False)
    for state in ("controller_already_cleared", "cleanup_blocked", "cleanup_paused"):
        result = {"state": state, "reason_code": "fixture-precondition", "runner_started": False, "binding_released": False}
        cleanup.return_value = result
        request = {**args, "request_id": state}
        first = commands.execute(app, "maintenance.repair", request, actor=actor)
        repeated = commands.execute(app, "maintenance.repair", request, actor=actor)
        assert first["state"] == repeated["state"] == state
        assert first["result"] == repeated["result"] == result
        # Observation can disagree with the action's earlier result; neither is rewritten.
        assert repeated["verification"]["cleanup"]["state"] == "controller_present"
    assert cleanup.call_count == 3

    for index, error in enumerate((Conflict("changed"), Uncertain("original outcome unknown"), KeyboardInterrupt())):
        cleanup.side_effect = error
        request = {**args, "request_id": f"interrupted-{index}"}
        with pytest.raises(type(error)):
            commands.execute(app, "maintenance.repair", request, actor=actor)
        repeated = commands.execute(app, "maintenance.repair", request, actor=actor)
        assert repeated["state"] == ("attempting" if isinstance(error, KeyboardInterrupt) else "outcome_unknown")
        assert "result" not in repeated
        assert repeated["verification"]["cleanup"]["state"] == "controller_present"
    assert cleanup.call_count == 6
    assert (control.read_bytes(), unknown_input.read_bytes()) == original


def test_cleanup_verification_failure_only_repeats_observation(cleanup_team, monkeypatch):
    app, actor, args = cleanup_team
    maintenance.grant(app, "sea", "maintainer", ["maintenance.repair"], ["alice"])
    result = {"state": "controller_cleared", "runner_started": False, "binding_released": False}
    cleanup = Mock(return_value=result)
    monkeypatch.setattr(runtime, "cleanup_controller", cleanup, raising=False)
    doctor = Mock(side_effect=[Error("observation failed"), {"state": "healthy", "issues": []}])
    monkeypatch.setattr(maintenance, "doctor", doctor)
    first = commands.execute(app, "maintenance.repair", args, actor=actor)
    assert first["state"] == "controller_cleared" and first["result"] == result
    assert first["verification"]["state"] == "unavailable"
    second = commands.execute(app, "maintenance.repair", args, actor=actor)
    assert second["verification"]["cleanup"]["state"] == "controller_present"
    assert doctor.call_count == 2
    cleanup.assert_called_once()
