"""Public maintenance operations against real isolated Workspace state."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from unittest.mock import Mock

import pytest

from agent_workspace import commands, maintenance, runtime
from agent_workspace.util import Conflict, Error, encode, locked, read_json, write_json


@pytest.fixture
def team(app):
    for aid in ("steward", "sentinel", "alice"):
        app.create("sea", aid)
    store = app.store("sea")
    snap = store.snapshot()
    meta = snap.json("workspace.json")
    meta["caretakers"] = {"steward": "steward", "sentinel": "sentinel"}
    store.change("main", {"workspace.json": encode(meta)}, {"workspace.json": snap.entries["workspace.json"]}, "Register test team")
    binding = app.reserve("sea", "steward")["binding"]
    app.bind("sea", "steward", binding, "steward-test-session")
    return app, ("sea", "steward", binding)


def test_commands_are_wired_without_launching_a_model(app):
    surface = commands.command_map(app)
    for name in ("agent.configure-sdk", "agent.transfer-profile", "agent.transfer", "agent.transfer-continue",
                 "agent.transfer-status", "workspace.doctor", "maintenance.grant", "maintenance.schedule",
                 "maintenance.status", "maintenance.repair"):
        assert name in surface
    assert commands.execute(app, "workspace.doctor", {"workspace": "sea"})["state"] == "healthy"


def test_caretaker_grant_is_scoped_revocable_and_not_a_name_privilege(team, monkeypatch):
    app, actor = team
    start = Mock(return_value={"state": "explicit-fixture"})
    monkeypatch.setattr(runtime, "start", start)
    args = {"workspace": "sea", "agent_id": "alice"}
    with pytest.raises(Error, match="grant"):
        commands.execute(app, "agent.start", args, actor=actor)
    maintenance.grant(app, "sea", "steward", ["agent.start"], ["alice"])
    commands.execute(app, "agent.start", args, actor=actor)
    start.assert_called_once()
    for other in ({"agent_id": "sentinel"}, {"workspace": "other", "agent_id": "alice"}):
        with pytest.raises(Error, match="grant"):
            commands.execute(app, "agent.start", other, actor=actor)
    maintenance.grant(app, "sea", "steward", [], [])
    with pytest.raises(Error, match="grant"):
        commands.execute(app, "agent.start", args, actor=actor)
    assert start.call_count == 1


def test_grant_admin_and_raw_process_configuration_cannot_be_delegated(team):
    app, actor = team
    for name in ("maintenance.grant", "agent.configure", "agent.transfer", "bridge.configure"):
        with pytest.raises(Error):
            maintenance.grant(app, "sea", "steward", [name], ["*"])
        with pytest.raises(Error, match="user-management"):
            commands.execute(app, name, {}, actor=actor)
    with pytest.raises(Error):
        maintenance.grant(app, "sea", "alice", ["agent.start"], ["*"])


@pytest.mark.parametrize("extra", [{"executable": "/untrusted/program"}, {"allowed_tools": ["Bash"]}])
def test_delegated_profiles_cannot_change_executables_or_tool_permissions(team, extra):
    app, actor = team
    maintenance.grant(app, "sea", "steward", ["agent.configure-sdk"], ["alice"])
    with pytest.raises(Error, match="user-management"):
        commands.execute(app, "agent.configure-sdk", {"agent_id": "alice", "kind": "claude", **extra}, actor=actor)


def test_old_binding_never_inherits_a_grant(team, monkeypatch):
    app, actor = team
    maintenance.grant(app, "sea", "steward", ["agent.start"], ["alice"])
    start = Mock()
    monkeypatch.setattr(runtime, "start", start)
    with pytest.raises(Conflict):
        commands.execute(app, "agent.start", {"agent_id": "alice"}, actor=("sea", "steward", "old-binding"))
    start.assert_not_called()


def test_cross_instance_mutations_need_grants_but_own_ops_do_not(team):
    app, actor = team
    with pytest.raises(Error, match="grant"):
        commands.execute(app, "agent.archive", {"agent_id": "alice"}, actor=actor)
    assert not app.agent("sea", "alice")["archived"]
    maintenance.grant(app, "sea", "steward", ["agent.archive"], ["alice"])
    assert commands.execute(app, "agent.archive", {"agent_id": "alice"}, actor=actor)["archived"]


def test_schedule_disabled_and_not_due_do_not_read_shared_state(team, monkeypatch):
    app, _ = team
    original = app.store
    reads = Mock(wraps=original)
    monkeypatch.setattr(app, "store", reads)
    assert maintenance.tick(app, "sea")["state"] == "disabled"
    reads.assert_not_called()
    maintenance.schedule(app, "sea", True, interval=30)
    assert maintenance.tick(app, "sea")["state"] == "checked"
    reads.reset_mock()
    assert maintenance.tick(app, "sea")["state"] == "not_due"
    reads.assert_not_called()


def test_schedule_owned_by_one_installation_and_alias(team, tmp_path):
    from agent_workspace.app import App
    app, _ = team
    maintenance.schedule(app, "sea", True)
    other = App(tmp_path / "other-home")
    other.workspace_connect("sea", app.store("sea").address)
    with pytest.raises(Conflict):
        maintenance.schedule(other, "sea", True)
    app.workspace_connect("alias", app.store("sea").address)
    config = read_json(maintenance.folder(app, "sea") / "schedule.json")
    write_json(maintenance.folder(app, "alias") / "schedule.json", config)
    assert maintenance.tick(app, "alias")["state"] == "schedule_not_owned"
    maintenance.schedule(other, "sea", False)
    assert maintenance.tick(app, "sea")["state"] == "schedule_not_owned"


@pytest.mark.parametrize("interval", [float("nan"), float("inf"), -1, 0, 29])
def test_schedule_rejects_unbounded_or_too_frequent_intervals(app, interval):
    with pytest.raises(Error):
        maintenance.schedule(app, "sea", True, interval=interval)
    assert app.store("sea").snapshot().json("maintenance/schedule.json") is None


def test_notify_is_opt_in_and_same_incident_is_not_queued_repeatedly(team, monkeypatch):
    app, _ = team
    binding = app.reserve("sea", "sentinel")["binding"]
    app.bind("sea", "sentinel", binding, "sentinel-session")
    clock = [1000.0]
    monkeypatch.setattr(maintenance.time, "time", lambda: clock[0])
    monkeypatch.setattr(maintenance, "doctor", lambda *args: {"state": "degraded", "issues": [{"code": "test-fault"}]})
    maintenance.schedule(app, "sea", True, interval=30, notify=False)
    maintenance.tick(app, "sea")
    inputs = app.root("sea", "sentinel") / ".aw-local/inputs"
    assert not list(inputs.glob("*.json"))
    maintenance.schedule(app, "sea", True, interval=30, notify=True)
    first = maintenance.tick(app, "sea")
    clock[0] += 31
    second = maintenance.tick(app, "sea")
    assert first["notice"]["id"] == second["notice"]["id"]
    assert len(list(inputs.glob("*.json"))) == 1
    assert read_json(next(inputs.glob("*.json")))["binding"] == binding


def test_disable_during_check_cannot_queue_notification(team, monkeypatch):
    app, _ = team
    binding = app.reserve("sea", "sentinel")["binding"]
    app.bind("sea", "sentinel", binding, "sentinel-session")
    maintenance.schedule(app, "sea", True, notify=True)
    def changed(*args):
        maintenance.schedule(app, "sea", False)
        return {"state": "degraded", "issues": [{"code": "test-fault"}]}
    monkeypatch.setattr(maintenance, "doctor", changed)
    assert maintenance.tick(app, "sea")["state"] == "schedule_changed"
    assert not list((app.root("sea", "sentinel") / ".aw-local/inputs").glob("*.json"))


def test_maintenance_notification_does_not_follow_a_changed_binding(team):
    app, _ = team
    binding = app.reserve("sea", "sentinel")["binding"]
    app.bind("sea", "sentinel", binding, "sentinel-session")
    with pytest.raises(Conflict):
        runtime.queue_input(app, "sea", "sentinel", "old notification", expected_binding="old")
    assert not list((app.root("sea", "sentinel") / ".aw-local/inputs").glob("*.json"))


def test_doctor_reports_unresolved_effects_and_pending_checkpoint(team):
    app, actor = team
    root = app.root("sea", "steward")
    write_json(root / ".aw-local/inputs/unknown.json", {"id": "unknown", "state": "outcome_unknown"})
    write_json(root / ".aw-local/inputs/initial.json", {"id": "initial", "state": "completed", "binding": actor[2], "purpose": "initial"})
    report = maintenance.doctor(app, "sea")
    assert {i["code"] for i in report["issues"]} == {"input_outcome_unknown", "initial_checkpoint_pending"}
    assert "steward" in report["coverage"]["local"]


def test_repair_is_idempotent_and_refuses_unknown_actions(team, monkeypatch):
    app, _ = team
    sync = Mock(wraps=app.sync_agent)
    monkeypatch.setattr(app, "sync_agent", sync)
    first = commands.execute(app, "maintenance.repair", {"workspace": "sea", "agent_id": "alice", "action": "sync-idle", "request_id": "repair-1"})
    second = maintenance.repair(app, "sea", "alice", "sync-idle", "repair-1")
    assert first == second and first["state"] == "applied"
    assert sync.call_count == 1
    with pytest.raises(Error):
        maintenance.repair(app, "sea", "alice", "force-takeover", "bad")
    with pytest.raises(Conflict):
        maintenance.repair(app, "sea", "steward", "sync-idle", "active")


def test_status_distinguishes_a_schedule_from_a_running_worker(team):
    app, _ = team
    maintenance.schedule(app, "sea", True)
    assert not maintenance.status(app, "sea")["worker_running"]
    with locked(app.home / "maintenance/worker.lock"):
        assert maintenance.status(app, "sea")["worker_running"]


def test_cli_commands_and_identity_origin(team):
    app, actor = team
    env = dict(os.environ)
    for key in ("AW_WORKSPACE", "AW_AGENT", "AW_BINDING"):
        env.pop(key, None)
    base = [sys.executable, "-m", "agent_workspace", "--home", str(app.home), "-w", "sea"]
    def call(*args, env=env):
        return subprocess.run([*base, *args], env=env, capture_output=True, text=True, encoding="utf-8", timeout=30)
    result = call("workspace", "doctor")
    assert result.returncode == 0, result.stderr
    result = call("maintenance", "schedule", "--enabled", "--interval", "60")
    assert result.returncode == 0, result.stderr
    result = call("maintenance", "repair", "alice", "--repair-action", "sync-idle", "--request-id", "cli-repair")
    assert result.returncode == 0, result.stderr
    model_env = dict(env, AW_WORKSPACE=actor[0], AW_AGENT=actor[1], AW_BINDING=actor[2])
    for domain in ("maintenance", "runtime"):
        result = call(domain, "run", *( ["alice"] if domain == "runtime" else []), env=model_env)
        assert result.returncode == 2 and "user-management" in result.stderr
