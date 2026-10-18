"""Original cleanup continuation on isolated Git, without native input or recovery."""
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent_workspace import backend, layout, maintenance, runtime
from agent_workspace.commands import execute
from agent_workspace.util import Conflict, Error, LockBusy, Uncertain, encode, write_json


@pytest.fixture
def exited_runner(app, monkeypatch):
    app.create("sea", "alice")
    app.configure("sea", "alice", {"kind": "desktop", "command": ["fixture"],
                  "caller_thread": "fixture", "pipe_path": "fixture", "model": "fixture", "effort": "high"})
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "original-chat")
    root, store = app.root("sea", "alice"), app.store("sea")
    snap = store.snapshot()
    path = layout.shared_path(snap, f"bindings/{binding}.json")
    entry = {**snap.json(path), "controller": "original-controller"}
    store.change("main", {path: encode(entry)}, {path: snap.entries[path]}, "Claim fixture runner")
    snap = store.snapshot()
    public_revision = execute(app, "workspace.doctor", {}, actor=("sea", "alice", binding))["revision"]
    cleaned = {key: value for key, value in entry.items() if key != "controller"}
    commit = store.commit(snap.revision, {path: encode(cleaned)}, "Release binding runner")
    other = layout.shared_path(snap, "maintenance/fixture.json")
    store.change("main", {other: encode({"concurrent": True})}, {other: None}, "Concurrent unrelated update")
    write_json(layout.local_path(root, "status.json"), {"binding": binding, "state": "failed", "primary_failure": "preserved"})
    write_json(layout.local_path(root, "inputs/unknown.json"), {"binding": binding, "state": "outcome_unknown", "text": "never replay"})
    native = Mock(return_value={"binding": binding, "session": "original-chat", "local_session_confirmed": True})
    monkeypatch.setattr(runtime, "desktop_observe", native)
    manager = backend.Backend(app, SimpleNamespace(server_port=0))
    app.backend = manager
    args = dict(expected_binding=binding, expected_controller="original-controller", expected_session="original-chat",
                expected_revision=public_revision, cleanup_commit=commit)
    yield app, root, store, path, args, native
    del app.backend


def test_continuation_preserves_other_shared_files_and_never_replays_old_push(exited_runner, monkeypatch):
    app, root, store, path, args, native = exited_runner
    before = store.snapshot()
    local_files = {p: p.read_bytes() for p in layout.local_path(root, "inputs").glob("*.json")}
    status = layout.local_path(root, "status.json").read_bytes()
    publish = Mock(wraps=store.publish)
    monkeypatch.setattr(store, "publish", publish)
    result = runtime.cleanup_controller(app, "sea", "alice", **args)
    after = store.snapshot()
    assert result["state"] == "controller_cleared" and not result["runner_started"] and not result["binding_released"]
    assert result["original_outcome"] == "diverged"
    assert len(publish.call_args_list) == 1 and publish.call_args.args[1] != args["cleanup_commit"]
    assert {key: value for key, value in before.entries.items() if key != path} == {
        key: value for key, value in after.entries.items() if key != path}
    assert after.json(path) == {key: value for key, value in before.json(path).items() if key != "controller"}
    assert all(p.read_bytes() == data for p, data in local_files.items())
    assert layout.local_path(root, "status.json").read_bytes() == status
    assert not app.backend.runners
    assert runtime.cleanup_controller(app, "sea", "alice", **args)["state"] == "controller_already_cleared"
    assert publish.call_count == 1


def test_original_publication_is_reconciled_before_any_new_write(exited_runner, monkeypatch):
    app, root, store, path, args, native = exited_runner
    before = store.snapshot()
    store.change("main", {path: store.snapshot(revision=args["cleanup_commit"]).bytes(path)},
                 {path: before.entries[path]}, "Previously completed cleanup")
    publish = Mock(side_effect=AssertionError("Do not republish completed cleanup"))
    monkeypatch.setattr(store, "publish", publish)
    assert runtime.cleanup_controller(app, "sea", "alice", **args)["state"] == "controller_already_cleared"
    publish.assert_not_called()


@pytest.mark.parametrize("condition", ["controller", "revision", "binding", "session", "execution", "native_cwd", "pause", "exit_unknown"])
def test_changed_preconditions_do_not_clear_or_resume(exited_runner, condition):
    app, root, store, path, args, native = exited_runner
    if condition == "controller":
        args["expected_controller"] = "other-controller"
    elif condition == "revision":
        args["expected_revision"] = args["cleanup_commit"]
    elif condition == "binding":
        args["expected_binding"] = "different-binding"
    elif condition == "session":
        args["expected_session"] = "different-chat"
    elif condition == "execution":
        snap = store.snapshot()
        entry = snap.json(path)
        entry["execution"]["installation_id"] = "different-installation"
        store.change("main", {path: encode(entry)}, {path: snap.entries[path]}, "Explicit foreign source fixture")
    elif condition == "native_cwd":
        native.return_value = {"local_session_confirmed": False, "unknown_reason": "native_local_copy_unconfirmed"}
    elif condition == "pause":
        write_json(layout.local_path(root, "control.json"), {"stop": args["expected_binding"]})
    elif condition == "exit_unknown":
        write_json(layout.local_path(root, "status.json"), {"binding": args["expected_binding"], "state": "native_stop_unconfirmed"})
    before = store.snapshot()
    if condition in ("controller", "revision", "binding", "session"):
        with pytest.raises(Conflict):
            runtime.cleanup_controller(app, "sea", "alice", **args)
    else:
        result = runtime.cleanup_controller(app, "sea", "alice", **args)
        assert result["state"] in ("cleanup_blocked", "cleanup_paused")
    assert store.snapshot().entries == before.entries and not app.backend.runners


def test_live_backend_thread_prevents_cleanup_even_before_it_acquires_runner_lock(exited_runner):
    app, root, store, path, args, native = exited_runner
    app.backend.runners[root] = {"workspace": "sea", "agent_id": "alice", "binding": args["expected_binding"],
                                 "thread": threading.current_thread()}
    assert runtime.cleanup_controller(app, "sea", "alice", **args)["reason_code"] == "runner_present"


def test_runner_os_lock_prevents_cleanup_from_another_process(exited_runner):
    app, root, store, path, args, native = exited_runner
    with layout.lock(root, "runner.lock", wait=0):
        with pytest.raises(LockBusy):
            runtime.cleanup_controller(app, "sea", "alice", **args)


def test_still_possible_original_push_remains_unknown(exited_runner, monkeypatch):
    app, root, store, path, args, native = exited_runner
    original_contains = store.contains_commit
    def contains(commit, head):
        if head == args["cleanup_commit"]:
            return True
        return original_contains(commit, head)
    monkeypatch.setattr(store, "contains_commit", contains)
    with pytest.raises(Uncertain):
        runtime.cleanup_controller(app, "sea", "alice", **args)
    assert store.snapshot().json(path)["controller"] == args["expected_controller"]


def test_binding_update_during_native_observation_is_preserved(exited_runner):
    app, root, store, path, args, native = exited_runner
    def observe(*unused, **kwargs):
        snap = store.snapshot()
        entry = {**snap.json(path), "controller": "new-controller"}
        store.change("main", {path: encode(entry)}, {path: snap.entries[path]}, "Concurrent controller change")
        return {"binding": args["expected_binding"], "session": "original-chat", "local_session_confirmed": True}
    native.side_effect = observe
    with pytest.raises(Conflict):
        runtime.cleanup_controller(app, "sea", "alice", **args)
    assert store.snapshot().json(path)["controller"] == "new-controller"


def test_unknown_cleanup_push_is_not_replayed(exited_runner, monkeypatch):
    app, root, store, path, args, native = exited_runner
    publish = Mock(side_effect=Uncertain("unknown original conditional push"))
    monkeypatch.setattr(store, "publish", publish)
    with pytest.raises(Uncertain):
        runtime.cleanup_controller(app, "sea", "alice", **args)
    publish.assert_called_once()


def test_public_granted_repair_runs_real_cleanup_once_and_only_observes_duplicates(exited_runner, monkeypatch):
    app, root, store, path, args, native = exited_runner
    app.create("sea", "maintainer")
    snap = store.snapshot()
    workspace_path = layout.shared_path(snap, "workspace.json")
    meta = snap.json(workspace_path)
    meta["caretakers"] = {"maintainer": "maintainer"}
    store.change("main", {workspace_path: encode(meta)}, {workspace_path: snap.entries[workspace_path]}, "Fixture caretaker role")
    actor_binding = app.reserve("sea", "maintainer")["binding"]
    app.bind("sea", "maintainer", actor_binding, "maintenance-session")
    actor = ("sea", "maintainer", actor_binding)
    request = {"agent_id": "alice", "action": "controller-cleanup", "request_id": "original-cleanup", **args}
    cleanup = Mock(wraps=runtime.cleanup_controller)
    monkeypatch.setattr(runtime, "cleanup_controller", cleanup)
    with pytest.raises(Error):
        execute(app, "maintenance.repair", request, actor=actor)
    cleanup.assert_not_called()
    maintenance.grant(app, "sea", "maintainer", ["maintenance.repair"], ["alice"])
    first = execute(app, "maintenance.repair", request, actor=actor)
    assert first["result"]["state"] == "controller_cleared"
    assert first["verification"]["cleanup"]["state"] == "controller_cleared"
    assert execute(app, "maintenance.repair", request, actor=actor)["result"] == first["result"]
    cleanup.assert_called_once()
    assert not app.backend.runners and store.snapshot().json(path)["session"] == "original-chat"
    assert not first["result"]["runner_started"] and not first["result"]["binding_released"]
