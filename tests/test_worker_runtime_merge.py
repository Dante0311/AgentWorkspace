"""Worker-aware integration on isolated Git; native observation/consent are fixtures."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent_workspace import backend, layout, maintenance, model_changes, model_profiles, runtime
from agent_workspace.app import App
from agent_workspace.commands import execute
from agent_workspace.util import Conflict, encode, write_json


@pytest.fixture
def team(tmp_path):
    app = App(tmp_path / "home")
    app.workspace_init("team", str(tmp_path / "team.git"))
    app.create("team", "owner")
    app.worker_create("team", "owner", "Topic", "Isolated integration checks", worker_id="topic")
    config = {"kind": "desktop", "command": ["fixture"], "pipe_path": "fixture", "caller_thread": "fixture"}
    app.configure("team", "owner", {**config, "model": "base-model", "effort": "low"})
    app.configure("team", "owner", {**config, "model": "topic-model", "effort": "high"}, worker_id="topic")
    bindings = {}
    for worker in ("default", "topic"):
        binding = app.reserve("team", "owner", worker_id=worker)["binding"]
        app.bind("team", "owner", binding, "session-" + worker, worker_id=worker)
        bindings[worker] = binding
    return app, app.root("team", "owner"), bindings


@pytest.fixture
def cleanup(team, monkeypatch):
    app, root, bindings = team
    store = app.store("team")
    snap = store.snapshot()
    changes = {}
    for worker, binding in bindings.items():
        path = layout.shared_path(snap, f"bindings/{binding}.json")
        changes[path] = encode({**snap.json(path), "controller": "controller-" + worker})
        write_json(layout.local_path(root, "status.json", worker), {"binding": binding, "state": "failed"})
        write_json(layout.local_path(root, "inputs/unknown.json", worker), {"binding": binding, "state": "outcome_unknown"})
    store.change("main", changes, {p: snap.entries[p] for p in changes}, "Claim fixture controllers")
    snap = store.snapshot()
    path = layout.shared_path(snap, f"bindings/{bindings['topic']}.json")
    entry = snap.json(path)
    original = store.commit(snap.revision, {path: encode({k: v for k, v in entry.items() if k != "controller"})}, "Original cleanup")
    other = layout.shared_path(snap, "maintenance/concurrent.json")
    store.change("main", {other: encode({"unrelated": True})}, {other: None}, "Diverge from original cleanup")
    write_json(layout.local_path(root, "control.json", "default"), {"stop": bindings["default"]})
    monkeypatch.setattr(backend, "status", Mock(return_value={"state": "running", "ready": True, "runners": [
        {"directory": str(root), "worker_id": "default", "binding": bindings["default"], "runner_alive": True}]}))
    native = Mock(return_value={"binding": bindings["topic"], "session": "session-topic", "local_session_confirmed": True})
    monkeypatch.setattr(runtime, "desktop_observe", native)
    args = {"expected_binding": bindings["topic"], "expected_controller": "controller-topic",
            "expected_session": "session-topic", "expected_revision": snap.revision, "cleanup_commit": original}
    return app, root, bindings, store, path, args, native


def test_granted_cleanup_and_recovery_use_binding_worker_and_preserve_peer(cleanup, monkeypatch):
    app, root, bindings, store, path, args, native = cleanup
    peer_path = layout.shared_path(store.snapshot(), f"bindings/{bindings['default']}.json")
    peer = store.snapshot().bytes(peer_path)
    local = {p: p.read_bytes() for worker in bindings for p in layout.local_path(root, "inputs", worker).glob("*.json")}
    app.create("team", "maintainer")
    snap = store.snapshot()
    meta_path = layout.shared_path(snap, "workspace.json")
    meta = snap.json(meta_path)
    meta["caretakers"] = {"maintainer": "maintainer"}
    store.change("main", {meta_path: encode(meta)}, {meta_path: snap.entries[meta_path]}, "Grant fixture role")
    caller = app.reserve("team", "maintainer")["binding"]
    app.bind("team", "maintainer", caller, "caretaker-session")
    maintenance.grant(app, "team", "maintainer", ["maintenance.repair"], ["owner"])
    spy = Mock(wraps=runtime.cleanup_controller)
    monkeypatch.setattr(runtime, "cleanup_controller", spy)
    request = {"workspace": "team", "agent_id": "owner", "action": "controller-cleanup", "request_id": "cleanup-topic", **args}
    with layout.lock(root, "runner.lock", wait=0, worker_id="default"):
        result = execute(app, "maintenance.repair", request, actor=("team", "maintainer", caller))
    assert result["result"]["state"] == "controller_cleared"
    assert result["verification"]["cleanup"]["state"] == "controller_cleared"
    assert result["request"]["worker_id"] == "topic"
    assert native.call_args.kwargs["worker_id"] == "topic"
    assert store.snapshot().bytes(peer_path) == peer
    assert all(p.read_bytes() == data for p, data in local.items())
    app.configure("team", "owner", {"kind": "manual"})
    manager = backend.Backend(app, SimpleNamespace(server_port=0))
    manager.attach = Mock(return_value={"state": "fixture_observer"})
    assert manager.recover("team", "owner", expected_binding=bindings["topic"])["state"] == "fixture_observer"
    assert manager.attach.call_args.kwargs["worker_id"] == "topic"
    snap = store.snapshot()
    app.worker_default("team", "owner", "topic", snap.entries[layout.shared_path(snap, "agents/owner.json")])
    duplicate = execute(app, "maintenance.repair", request, actor=("team", "maintainer", caller))
    assert duplicate["result"] == result["result"] and spy.call_count == 1
    assert duplicate["verification"]["cleanup"]["worker"] == "topic"
    with pytest.raises(Conflict):
        execute(app, "maintenance.repair", {**request, "worker_id": "default"}, actor=("team", "maintainer", caller))


def test_cleanup_rejects_explicit_peer_and_worker_change_during_observation(cleanup):
    app, root, bindings, store, path, args, native = cleanup
    with pytest.raises(Conflict):
        runtime.cleanup_controller(app, "team", "owner", worker_id="default", **args)
    native.assert_not_called()
    def changed(*positional, **keywords):
        item = app.worker("team", "owner", "topic")
        app.worker_update("team", "owner", "topic", item["revision"], description="Changed during observation")
        return native.return_value
    native.side_effect = changed
    with pytest.raises(Conflict):
        runtime.cleanup_controller(app, "team", "owner", **args)
    assert store.snapshot().json(path)["controller"] == "controller-topic"


def test_model_consent_from_nondefault_worker_changes_only_common_defaults(team, monkeypatch):
    app, root, bindings = team
    entries = {worker: layout.local_path(root, "entry.json", worker).read_bytes() for worker in bindings}
    override = layout.instance_path(root, "config.json", "topic").read_bytes()
    actor = ("team", "owner", bindings["topic"])
    execute(app, "agent.model-change-request", {"workspace": "team", "request_id": "common-model", "changes": [
        {"agent_id": "owner", "model": "next-model", "effort": "medium"}]}, actor=actor)
    def confirm(record):
        assert record["changes"][0]["binding"] == bindings
        snap = app.store("team").snapshot()
        app.worker_default("team", "owner", "topic", snap.entries[layout.shared_path(snap, "agents/owner.json")])
        return True
    consent = Mock(side_effect=confirm)
    monkeypatch.setattr(model_changes, "native_confirm", consent)
    result = execute(app, "agent.model-change-review", {"workspace": "team", "request_id": "common-model"}, actor=actor)
    assert result["state"] == "applied" and result["entry_changed"] is False
    assert model_profiles.selected(root)["model"] == "next-model"
    assert model_profiles.selected(root, "topic")["model"] == "topic-model"
    assert layout.instance_path(root, "config.json", "topic").read_bytes() == override
    assert all(layout.local_path(root, "entry.json", worker).read_bytes() == data for worker, data in entries.items())
    execute(app, "agent.model-change-review", {"workspace": "team", "request_id": "common-model"}, actor=actor)
    consent.assert_called_once()


def test_model_consent_rejects_changed_nondefault_entry_before_writing(team, monkeypatch):
    app, root, bindings = team
    actor = ("team", "owner", bindings["default"])
    execute(app, "agent.model-change-request", {"workspace": "team", "request_id": "changed-topic", "changes": [
        {"agent_id": "owner", "model": "next-model", "effort": "medium"}]}, actor=actor)
    original = layout.instance_path(root, "config.json").read_bytes()
    def confirm(record):
        point = app.checkpoint("team", "owner", "Explicit fixture stop", binding=bindings["topic"], worker_id="topic")
        app.stop("team", "owner", bindings["topic"], point["id"], worker_id="topic")
        app.finish_stop("team", "owner", bindings["topic"], observed_idle=True, worker_id="topic")
        return True
    monkeypatch.setattr(model_changes, "native_confirm", confirm)
    with pytest.raises(Conflict):
        execute(app, "agent.model-change-review", {"workspace": "team", "request_id": "changed-topic"}, actor=actor)
    assert layout.instance_path(root, "config.json").read_bytes() == original
    assert app.worker("team", "owner", "default")["current"] == bindings["default"]
