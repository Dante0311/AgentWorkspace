"""Health observations do not turn stopped or unobserved workers into success."""
import pytest

from agent_workspace import maintenance, runtime
from agent_workspace.util import encode, locked, read_json, write_json


@pytest.fixture
def desktop_entry(app):
    app.create("sea", "alice")
    app.configure("sea", "alice", {"kind": "desktop"})
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "original-desktop-session")
    return app, binding, app.root("sea", "alice")


def test_stopping_without_observer_remains_visible_after_handoff_request(desktop_entry):
    app, binding, root = desktop_entry
    checkpoint = app.checkpoint("sea", "alice", "original stop", binding=binding)
    app.stop("sea", "alice", binding, checkpoint["id"])
    write_json(root / ".aw-local/control.json", {"handoff": binding})
    write_json(root / ".aw-local/status.json", {"binding": binding, "state": "failed"})

    report = maintenance.doctor(app, "sea")

    assert report["state"] == "degraded"
    issues = {item["code"]: item for item in report["issues"]}
    assert issues["stop_confirmation_not_observed"]["binding"] == binding
    assert issues["stop_confirmation_not_observed"]["checkpoint"] == checkpoint["id"]
    assert issues["runtime_fault"]["state"] == "failed"
    assert app.agent("sea", "alice")["current"] == binding


def test_busy_stop_with_live_observer_is_not_a_missing_runner(desktop_entry):
    app, binding, root = desktop_entry
    checkpoint = app.checkpoint("sea", "alice", "wait for busy turn", binding=binding)
    app.stop("sea", "alice", binding, checkpoint["id"])
    write_json(root / ".aw-local/status.json", {"binding": binding, "state": "handoff_waiting_idle"})

    with locked(root / ".aw-local/runner.lock"):
        report = maintenance.doctor(app, "sea")

    assert report["state"] == "healthy"
    observation = report["local_observations"]["alice"]
    assert observation["phase"] == "stopping"
    assert observation["runtime"]["state"] == "handoff_waiting_idle"
    assert observation["runner_observed"] is True


def test_monitor_stop_does_not_hide_recorded_failure(desktop_entry):
    app, binding, root = desktop_entry
    write_json(root / ".aw-local/control.json", {"stop": binding})
    write_json(root / ".aw-local/status.json", {"binding": binding, "state": "connection_failed"})

    report = maintenance.doctor(app, "sea")

    assert {item["code"] for item in report["issues"]} == {"runtime_fault"}
    assert report["local_observations"]["alice"]["monitor_stop_requested"] is True


def test_retry_and_unknown_stop_observation_are_not_reported_as_healthy(desktop_entry):
    app, binding, root = desktop_entry
    checkpoint = app.checkpoint("sea", "alice", "original request", binding=binding)
    app.stop("sea", "alice", binding, checkpoint["id"])
    for state, code in (("shared_read_backoff", "runtime_shared_read_backoff"),
                        ("stop_observation_unknown", "stop_observation_unknown")):
        write_json(root / ".aw-local/status.json", {"binding": binding, "state": state,
                   "attempts": 2, "retry_seconds": 4, "reason": "observation temporarily unavailable"})
        with locked(root / ".aw-local/runner.lock"):
            report = maintenance.doctor(app, "sea")
        assert report["state"] == "degraded"
        assert {item["code"] for item in report["issues"]} == {code}
        assert report["local_observations"]["alice"]["runtime"]["retry_seconds"] == 4


def test_watch_configuration_and_unknown_runtime_are_separate(desktop_entry):
    app, binding, root = desktop_entry
    write_json(root / ".aw-local/control.json", {"stop": binding})
    observation = maintenance.doctor(app, "sea")["local_observations"]["alice"]
    assert observation["runtime"] is None
    assert observation["watch"]["state"] == "not_configured"
    runtime.watch(app, "sea", "alice", "stop")
    assert maintenance.doctor(app, "sea")["local_observations"]["alice"]["watch"]["state"] == "disabled"
    runtime.watch(app, "sea", "alice", "start")
    observation = maintenance.doctor(app, "sea")["local_observations"]["alice"]
    assert observation["watch"]["state"] == "enabled"
    assert observation["runner_observed"] is False
    write_json(root / ".aw-local/watch.json", {"enabled": True, "binding": "old-entry"})
    assert maintenance.doctor(app, "sea")["local_observations"]["alice"]["watch"]["state"] == "binding_mismatch"


def test_disabled_schedule_and_missing_worker_are_not_equivalent(app):
    assert maintenance.doctor(app, "sea")["maintenance"]["state"] == "not_configured"
    maintenance.schedule(app, "sea", False)
    assert maintenance.doctor(app, "sea")["maintenance"]["state"] == "disabled"
    maintenance.schedule(app, "sea", True)
    report = maintenance.doctor(app, "sea")
    assert report["maintenance"]["state"] == "worker_not_observed"
    assert {item["code"] for item in report["issues"]} == {"maintenance_worker_not_observed"}
    with locked(app.home / "maintenance/worker.lock"):
        assert maintenance.doctor(app, "sea")["maintenance"]["state"] == "worker_observed"
    assert maintenance.status(app, "sea")["state"] == "worker_not_observed"


def test_another_installations_schedule_is_unobserved(app, tmp_path):
    from agent_workspace.app import App

    maintenance.schedule(app, "sea", True)
    other = App(tmp_path / "other-home")
    other.workspace_connect("sea", app.store("sea").address)
    report = maintenance.doctor(other, "sea")
    assert report["state"] == "partial"
    assert report["maintenance"]["state"] == "not_owned"
    assert not (other.home / "installation.json").exists()


def test_unreadable_scheduler_identity_preserves_other_observations(desktop_entry):
    app, binding, root = desktop_entry
    write_json(root / ".aw-local/status.json", {"binding": binding, "state": "failed"})
    maintenance.schedule(app, "sea", True)
    identity = app.home / "installation.json"
    identity.write_text("{broken", encoding="utf-8")

    report = maintenance.doctor(app, "sea")

    assert report["maintenance"]["state"] == "unavailable"
    assert {item["code"] for item in report["issues"]} == {
        "runner_not_observed", "runtime_fault", "maintenance_observation_failed"}
    assert identity.read_text() == "{broken"


@pytest.fixture
def queued_notice(app, monkeypatch):
    app.create("sea", "sentinel")
    store = app.store("sea")
    snap = store.snapshot()
    meta = snap.json("workspace.json")
    meta["caretakers"] = {"sentinel": "sentinel"}
    store.change("main", {"workspace.json": encode(meta)},
                 {"workspace.json": snap.entries["workspace.json"]}, "Register test sentinel")
    binding = app.reserve("sea", "sentinel")["binding"]
    app.bind("sea", "sentinel", binding, "sentinel-test-session")
    monkeypatch.setattr(maintenance, "doctor", lambda *args: {
        "state": "degraded", "issues": [{"code": "test_fault"}]})
    maintenance.schedule(app, "sea", True, notify=True)
    run = maintenance.tick(app, "sea")
    path = app.root("sea", "sentinel") / ".aw-local/inputs" / (run["notice"]["id"] + ".json")
    return app, path


def test_notice_readback_observes_original_input_without_requeue(queued_notice):
    app, path = queued_notice
    record = read_json(path)
    run_path = maintenance.folder(app, "sea") / "run.json"
    saved_run = run_path.read_bytes()
    for state in ("queued", "outcome_unknown", "completed"):
        record["state"] = state
        write_json(path, record)
        before = path.read_bytes()
        notice = maintenance.status(app, "sea")["local_run"]["notice"]
        assert notice["state"] == "queued"
        assert notice["input_state"] == state
        assert notice["id"] == record["id"]
        assert path.read_bytes() == before
        assert run_path.read_bytes() == saved_run
    assert len(list(path.parent.glob("*.json"))) == 1


def test_notice_readback_does_not_attribute_other_binding_or_corrupt_record(queued_notice):
    app, path = queued_notice
    record = read_json(path)
    record["binding"] = "other-binding"
    write_json(path, record)
    assert maintenance.status(app, "sea")["local_run"]["notice"]["input_state"] == "not_observed"
    path.write_text("{broken", encoding="utf-8")
    assert maintenance.status(app, "sea")["local_run"]["notice"]["input_state"] == "unavailable"
    assert path.read_text() == "{broken"
