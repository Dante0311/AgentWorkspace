"""The granted maintenance entry delegates to Runtime and only rereads results.

The Runtime callback is a protocol fixture here. Real stop observation belongs
to Runtime's tests and the combined Windows/Desktop acceptance.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from unittest.mock import Mock

import pytest

from agent_workspace import cli, commands, maintenance, runtime
from agent_workspace.util import Conflict, Error, Uncertain, encode, read_json


@pytest.fixture
def stop_team(app):
    for aid in ("alice", "maintainer"):
        app.create("sea", aid)
    app.configure("sea", "alice", {"kind": "desktop"})
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "original-desktop")
    point = app.checkpoint("sea", "alice", "original stop", binding=binding)
    app.stop("sea", "alice", binding, point["id"])
    store = app.store("sea")
    snap = store.snapshot()
    meta = snap.json("workspace.json")
    meta["caretakers"] = {"maintainer": "maintainer"}
    store.change("main", {"workspace.json": encode(meta)},
                 {"workspace.json": snap.entries["workspace.json"]}, "Register isolated maintainer")
    maintainer_binding = app.reserve("sea", "maintainer")["binding"]
    app.bind("sea", "maintainer", maintainer_binding, "maintainer-session")
    return app, ("sea", "maintainer", maintainer_binding), binding, point["id"]


def test_scoped_duplicate_stop_repair_delegates_once_and_observes_original_release(stop_team, monkeypatch, capsys):
    app, actor, binding, checkpoint = stop_team
    backend = Mock(return_value={"state": "starting_stop_observer", "binding": binding,
                                 "checkpoint": checkpoint, "session": "original-desktop"})
    monkeypatch.setattr(runtime, "continue_stop", backend, raising=False)
    args = {"agent_id": "alice", "action": "continue-stop", "request_id": "original-repair",
            "expected_binding": binding, "expected_checkpoint": checkpoint}
    with pytest.raises(Error):
        commands.execute(app, "maintenance.repair", args, actor=actor)
    maintenance.grant(app, "sea", "maintainer", ["maintenance.repair"], ["alice"])
    with pytest.raises(Error):
        commands.execute(app, "maintenance.repair", {**args, "agent_id": "ungranted"}, actor=actor)
    with pytest.raises(Conflict):
        commands.execute(app, "maintenance.repair", args, actor=("sea", "maintainer", "old-entry"))
    backend.assert_not_called()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: commands.execute(app, "maintenance.repair", args, actor=actor), range(2)))
    backend.assert_called_once_with(app, "sea", "alice", binding, expected_checkpoint=checkpoint)
    assert all(result["state"] == "applied" for result in results)
    assert all(result["verification"]["stop"]["state"] == "stopping" for result in results)
    assert app.agent("sea", "alice")["current"] == binding

    for name, value in zip(("AW_WORKSPACE", "AW_AGENT", "AW_BINDING"), actor):
        monkeypatch.setenv(name, value)
    assert cli.main(["--home", str(app.home), "--workspace", "sea", "maintenance", "repair", "alice",
                     "--repair-action", "continue-stop", "--request-id", "original-repair",
                     "--expected-binding", binding, "--expected-checkpoint", checkpoint]) == 0
    assert json.loads(capsys.readouterr().out)["result"]["verification"]["stop"]["state"] == "stopping"
    assert backend.call_count == 1

    app.finish_stop("sea", "alice", binding, observed_idle=True)
    successor = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", successor, "successor-desktop")
    result = commands.execute(app, "maintenance.repair", args, actor=actor)
    assert result["result"]["state"] == "starting_stop_observer"
    stop = result["verification"]["stop"]
    assert stop["state"] == "released"
    assert (stop["binding"], stop["checkpoint"], stop["session"]) == (binding, checkpoint, "original-desktop")
    assert app.agent("sea", "alice")["current"] == successor
    assert backend.call_count == 1
    with pytest.raises(Conflict):
        commands.execute(app, "maintenance.repair", {**args, "expected_binding": successor}, actor=actor)
    with pytest.raises(Conflict):
        commands.execute(app, "maintenance.repair", {**args, "expected_checkpoint": "another-checkpoint"}, actor=actor)

    store = app.store("sea")
    snap = store.snapshot()
    entry_path = f"bindings/{binding}.json"
    entry = snap.json(entry_path)
    entry["checkpoint"] = "changed-checkpoint"
    store.change("main", {entry_path: encode(entry)}, {entry_path: snap.entries[entry_path]}, "Isolated changed request")
    assert commands.execute(app, "maintenance.repair", args, actor=actor)["verification"]["stop"]["state"] == "request_changed"
    maintenance.grant(app, "sea", "maintainer", [], [])
    with pytest.raises(Error):
        commands.execute(app, "maintenance.repair", args, actor=actor)
    assert backend.call_count == 1


def test_unknown_stop_repair_only_rereads_original_request(stop_team, monkeypatch):
    app, actor, binding, checkpoint = stop_team
    maintenance.grant(app, "sea", "maintainer", ["maintenance.repair"], ["alice"])
    backend = Mock(side_effect=Uncertain("observer launch outcome is unknown"))
    monkeypatch.setattr(runtime, "continue_stop", backend, raising=False)
    args = {"agent_id": "alice", "action": "continue-stop", "request_id": "unknown-stop",
            "expected_binding": binding, "expected_checkpoint": checkpoint}
    with pytest.raises(Uncertain):
        commands.execute(app, "maintenance.repair", args, actor=actor)
    result = commands.execute(app, "maintenance.repair", args, actor=actor)
    assert result["state"] == "outcome_unknown"
    assert result["verification"]["stop"]["state"] == "stopping"
    assert result["verification"]["stop"]["checkpoint"] == checkpoint
    assert app.agent("sea", "alice")["current"] == binding
    backend.assert_called_once()


def test_missing_original_binding_does_not_attempt_recovery(app, monkeypatch):
    app.create("sea", "alice")
    backend = Mock()
    monkeypatch.setattr(runtime, "continue_stop", backend, raising=False)
    with pytest.raises(Error):
        maintenance.repair(app, "sea", "alice", "continue-stop", "missing-binding")
    with pytest.raises(Error):
        maintenance.repair(app, "sea", "alice", "continue-stop", "missing-checkpoint", expected_binding="original")
    assert read_json(maintenance.folder(app, "sea") / "repairs/missing-binding.json") is None
    assert read_json(maintenance.folder(app, "sea") / "repairs/missing-checkpoint.json") is None
    backend.assert_not_called()
