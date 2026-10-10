"""Isolated runtime recovery; native peers below are protocol fixtures, not Desktop acceptance."""
from pathlib import Path
import sys
import threading
import time
from unittest.mock import Mock

import pytest

from agent_workspace import model_profiles, runtime
from agent_workspace.commands import execute
from agent_workspace.gitstore import GitStore
from agent_workspace.util import (Conflict, Error, LockBusy, RetryableRead, Uncertain,
                                  encode, locked, read_json, write_json)


@pytest.fixture
def desktop_owner(app, monkeypatch):
    app.create("sea", "alice")
    root = app.root("sea", "alice")
    config = {"kind": "desktop", "command": [sys.executable, str(Path(__file__).with_name("fake_native.py")), "desktop"],
              "pipe_path": "fixture", "caller_thread": "caller", "model": "fixture-model", "effort": "low"}
    app.configure("sea", "alice", config)
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "original-chat")
    native = {"attached": [], "sent": [], "states": ["idle"], "closed": 0}

    class DesktopPeer:
        supports_insert = True

        def __init__(self, root, config, session, *, read_only=False):
            self.root, self.read_only = root, read_only
            self.session = session
            native["attached"].append(session)
            native.setdefault("read_only", []).append(read_only)

        def status(self):
            callback = native.get("on_status")
            if callback:
                callback()
            return native["states"].pop(0) if len(native["states"]) > 1 else native["states"][0]

        def completed_turns(self, identifiers):
            return {}

        def model_choice(self, tool, binding=None):
            assert not self.read_only, "Stop observation must not require a model choice"
            return (model_profiles.adopted(self.root, binding, session=self.session),
                    {"catalog": "protocol_fixture", "effective": "unconfirmed"})

        def notify(self, prompt, delivery):
            native["sent"].append((self.session, prompt, delivery))
            callback = native.get("on_notify")
            if callback:
                callback()
            return {"threadId": self.session, "turn": {"id": "original-turn"}}

        def create(self, binding):
            pytest.fail("Recovery must not create a native session")

        def close(self):
            native["closed"] += 1
            callback = native.get("on_close")
            if callback:
                callback()

    monkeypatch.setattr(runtime, "Desktop", DesktopPeer)
    return app, root, binding, native


def fast_wait(runner, monkeypatch):
    delays = []

    def wait(delay):
        delays.append(delay)
        return runner.stop_event.is_set()

    monkeypatch.setattr(runner.stop_event, "wait", wait)
    return delays


def request_stop(owner):
    app, root, binding, native = owner
    point = app.checkpoint("sea", "alice", "original handoff", binding=binding)
    app.stop("sea", "alice", binding, point["id"])
    return point


def test_read_retry_retains_original_session_binding_and_single_input(desktop_owner, monkeypatch):
    app, root, binding, native = desktop_owner
    runtime.queue_input(app, "sea", "alice", "explicit test input", request_id="one-input")
    runner = runtime.Runner(app, "sea", "alice")
    delays = fast_wait(runner, monkeypatch)
    native["on_notify"] = runner.stop_event.set
    original_head = GitStore.head
    remaining = 2

    def head(store, branch):
        nonlocal remaining
        if branch == "main" and native["attached"] and not native["sent"] and remaining:
            remaining -= 1
            raise RetryableRead("temporary shared read failure")
        return original_head(store, branch)

    monkeypatch.setattr(GitStore, "head", head)
    runner.run()
    assert 2 in delays and 4 in delays
    assert native["attached"] == ["original-chat"]
    assert len(native["sent"]) == 1
    assert app.agent("sea", "alice")["current"] == binding
    item = read_json(root / ".aw-local/inputs/one-input.json")
    assert item["binding"] == binding and item["state"] == "submitted"
    assert item["result"]["turn"]["id"] == "original-turn"


def test_recovered_read_checks_new_stop_before_dispatch(desktop_owner, monkeypatch):
    app, root, binding, native = desktop_owner
    point = app.checkpoint("sea", "alice", "stop during outage", binding=binding)
    runtime.queue_input(app, "sea", "alice", "must remain queued", request_id="queued-input")
    runner = runtime.Runner(app, "sea", "alice")
    original_head = GitStore.head
    interrupted = False

    def head(store, branch):
        nonlocal interrupted
        if branch == "main" and native["attached"] and not interrupted:
            interrupted = True
            raise RetryableRead("read unavailable before qualification")
        return original_head(store, branch)

    def wait(delay):
        if delay >= 2:
            app.stop("sea", "alice", binding, point["id"])
        return runner.stop_event.is_set()

    monkeypatch.setattr(GitStore, "head", head)
    monkeypatch.setattr(runner.stop_event, "wait", wait)
    runner.run()
    assert not native["sent"]
    assert read_json(root / ".aw-local/inputs/queued-input.json")["state"] == "queued"
    assert app.show("sea", "alice")["current"] is None


def test_watch_read_failure_after_submission_does_not_repeat_input(desktop_owner, monkeypatch):
    app, root, binding, native = desktop_owner
    app.create("sea", "bob")
    sender = app.reserve("sea", "bob")["binding"]
    app.bind("sea", "bob", sender, "sender-chat")
    runtime.Messages(app).send("sea", "bob", sender, "alice", "explicit message fixture", request_id="original-message")
    runtime.queue_input(app, "sea", "alice", "one model input", request_id="one-input")
    runtime.watch(app, "sea", "alice", "start", interval=.5)
    runner = runtime.Runner(app, "sea", "alice")
    delays = fast_wait(runner, monkeypatch)
    original_head, original_poll = GitStore.head, runtime.Messages.poll
    in_poll, remaining = False, 1

    def head(store, branch):
        nonlocal remaining
        if in_poll and branch == "main" and remaining:
            remaining -= 1
            raise RetryableRead("watch read unavailable after model input accepted")
        return original_head(store, branch)

    def poll(messages, *args, **kwargs):
        nonlocal in_poll
        in_poll = True
        try:
            return original_poll(messages, *args, **kwargs)
        finally:
            in_poll = False

    def notified():
        if len(native["sent"]) == 2:
            runner.stop_event.set()

    native["on_notify"] = notified
    monkeypatch.setattr(GitStore, "head", head)
    monkeypatch.setattr(runtime.Messages, "poll", poll)
    runner.run()
    assert 2 in delays and native["attached"] == ["original-chat"]
    assert len(native["sent"]) == 2  # One model input and one original Message notification.
    assert "one-input" in native["sent"][0][1]
    assert "original-message" in native["sent"][1][1]
    assert read_json(root / ".aw-local/inputs/one-input.json")["state"] == "submitted"
    assert app.store("sea").snapshot().json("dispatch/alice.json")["attempts"] == 1


def test_persistent_read_failure_remains_visible_and_keeps_adapter(desktop_owner, monkeypatch):
    app, root, binding, native = desktop_owner
    runner = runtime.Runner(app, "sea", "alice")
    runner.binding = binding
    runner.adapter = runtime.Desktop(root, {}, "original-chat")
    waits = []

    def wait(delay):
        waits.append(delay)
        return len(waits) == 3

    monkeypatch.setattr(runner.stop_event, "wait", wait)
    read = Mock(side_effect=RetryableRead("still offline"))
    with pytest.raises(runtime._ReadStopped):
        runner._shared_read("ownership", read)
    status = read_json(root / ".aw-local/status.json")
    assert status["state"] == "shared_read_backoff" and status["attempts"] == 3
    assert status["reason"] == "still offline" and status["retry_seconds"] == 8
    assert not native["closed"] and app.agent("sea", "alice")["current"] == binding


@pytest.mark.parametrize("failure", [Error("access denied"), Error("bad object"), Conflict("owner changed"),
                                   Uncertain("original publication is unknown")])
def test_non_read_failures_are_not_retried(desktop_owner, monkeypatch, failure):
    app, _, _, _ = desktop_owner
    runner = runtime.Runner(app, "sea", "alice")
    wait = Mock()
    monkeypatch.setattr(runner.stop_event, "wait", wait)
    read = Mock(side_effect=failure)
    with pytest.raises(type(failure)) as raised:
        runner._shared_read("ownership", read)
    assert raised.value is failure and read.call_count == 1
    wait.assert_not_called()


def test_cleanup_does_not_replace_original_failure(desktop_owner, monkeypatch):
    app, root, _, _ = desktop_owner
    runner = runtime.Runner(app, "sea", "alice")
    original = Error("original access failure")
    runner.adapter = Mock()
    runner.adapter.close.side_effect = Uncertain("native close failed")

    def fail():
        try:
            raise original
        finally:
            runner._cleanup_native()

    monkeypatch.setattr(runner, "_run_owned", fail)
    monkeypatch.setattr(runner, "_release_controller", Mock(side_effect=Error("cleanup read failed")))
    with pytest.raises(Error) as raised:
        runner.run()
    assert raised.value is original
    status = read_json(root / ".aw-local/status.json")
    assert status["reason"] == "original access failure"
    assert status["cleanup_errors"] == ["native close failed", "cleanup read failed"]


def test_stopping_observer_waits_then_releases_only_original_request(desktop_owner, monkeypatch):
    app, root, binding, native = desktop_owner
    # Existing sessions without an adopted model must still be stoppable.
    local = read_json(root / ".aw-local/entry.json")
    local.pop("model_profile", None)
    write_json(root / ".aw-local/entry.json", local)
    (root / "runtime.json").unlink()
    runtime.queue_input(app, "sea", "alice", "remain queued", request_id="untouched")
    store = app.store("sea")
    snap = store.snapshot()
    path = f"bindings/{binding}.json"
    store.change("main", {path: encode({**snap.json(path), "controller": "original-controller"})},
                 {path: snap.entries[path]}, "Record original fixture controller")
    point = request_stop(desktop_owner)
    write_json(root / ".aw-local/renew.json", {"binding": binding, "requested": True})
    native["states"] = ["busy", "unknown", "idle"]
    runner = runtime.Runner(app, "sea", "alice", stop_binding=binding)
    fast_wait(runner, monkeypatch)
    monkeypatch.setattr(runtime, "start", Mock(side_effect=AssertionError("no successor")))
    from agent_workspace import bridges
    monkeypatch.setattr(bridges, "BridgeManager", Mock(side_effect=AssertionError("no bridge")))
    runner.run()
    released = app.show("sea", "alice")
    handoff = app.store("sea").snapshot().json(f"handoffs/{released['handoff']}.json")
    assert handoff["entry"] == binding and handoff["checkpoint"] == point["id"]
    assert native["attached"] == ["original-chat"] and not native["sent"]
    assert native["read_only"] == [True]
    assert read_json(root / ".aw-local/inputs/untouched.json")["state"] == "queued"
    assert read_json(root / ".aw-local/renew.json")["requested"]
    assert read_json(root / ".aw-local/status.json")["state"] == "released"


def test_unknown_native_status_keeps_stop_owned(desktop_owner, monkeypatch):
    app, root, binding, native = desktop_owner
    request_stop(desktop_owner)
    native["states"] = ["unknown"]
    runner = runtime.Runner(app, "sea", "alice", stop_binding=binding)
    native["on_status"] = runner.stop_event.set
    runner.run()
    assert app.show("sea", "alice")["binding"]["phase"] == "stopping"
    assert read_json(root / ".aw-local/status.json")["state"] == "stop_observation_unknown"


@pytest.mark.parametrize("field", ["checkpoint", "session", "controller"])
def test_changed_stop_facts_cannot_be_released(desktop_owner, monkeypatch, field):
    app, _, binding, native = desktop_owner
    request_stop(desktop_owner)
    changed = False

    def change_observed_fact():
        nonlocal changed
        if changed:
            return
        changed = True
        store = app.store("sea")
        snap = store.snapshot()
        path = f"bindings/{binding}.json"
        entry = snap.json(path)
        entry[field] = "changed-after-observation"
        store.change("main", {path: encode(entry)}, {path: snap.entries[path]}, "Change isolated stop fact")

    native["on_status"] = change_observed_fact
    with pytest.raises(Conflict):
        runtime.Runner(app, "sea", "alice", stop_binding=binding).run()
    assert app.agent("sea", "alice")["current"] == binding
    assert app.store("sea").snapshot().json("handoffs/h" + binding[1:] + ".json") is None


def test_missing_checkpoint_prevents_observation_and_release(desktop_owner):
    app, _, binding, native = desktop_owner
    point = request_stop(desktop_owner)
    store = app.store("sea")
    path = f"checkpoints/alice/{point['id']}.json"
    snap = store.snapshot()
    store.change("main", {path: None}, {path: snap.entries[path]}, "Remove isolated fixture checkpoint")
    with pytest.raises(Error):
        runtime.Runner(app, "sea", "alice", stop_binding=binding).run()
    assert not native["attached"]
    assert app.agent("sea", "alice")["current"] == binding


def test_unknown_stop_publication_is_not_replayed(desktop_owner, monkeypatch):
    app, root, binding, native = desktop_owner
    point = request_stop(desktop_owner)
    finish = Mock(side_effect=Uncertain("original handoff publication result unknown"))
    monkeypatch.setattr(app, "finish_stop", finish)
    with pytest.raises(Uncertain):
        runtime.Runner(app, "sea", "alice", stop_binding=binding).run()
    assert finish.call_count == 1 and not native["sent"]
    assert app.show("sea", "alice")["binding"]["checkpoint"] == point["id"]
    assert read_json(root / ".aw-local/status.json")["error_code"] == "outcome_unknown"



@pytest.mark.parametrize("stop_only", [False, True])
def test_stop_preflight_read_retry_reobserves_original_request(desktop_owner, monkeypatch, stop_only):
    app, root, binding, native = desktop_owner
    runtime.queue_input(app, "sea", "alice", "remain queued", request_id="untouched")
    point = app.checkpoint("sea", "alice", "fixed request", binding=binding)
    if stop_only:
        app.stop("sea", "alice", binding, point["id"])
    runner = runtime.Runner(app, "sea", "alice", stop_binding=binding if stop_only else None)
    waits, recorded_states = [], []
    stopping = stop_only

    def wait(delay):
        nonlocal stopping
        waits.append(delay)
        if not stopping:
            stopping = True
            app.stop("sea", "alice", binding, point["id"])
        status = read_json(root / ".aw-local/status.json", {})
        recorded_states.append(status.get("state"))
        return False

    monkeypatch.setattr(runner.stop_event, "wait", wait)
    original_finish, original_head = app.finish_stop, GitStore.head
    in_finish, remaining, calls = False, 1, []

    def head(store, branch):
        nonlocal remaining
        if in_finish and remaining and branch == "main":
            remaining -= 1
            raise RetryableRead("final stop preflight read unavailable")
        return original_head(store, branch)

    def finish(*args, **kwargs):
        nonlocal in_finish
        calls.append(kwargs)
        in_finish = True
        try:
            return original_finish(*args, **kwargs)
        finally:
            in_finish = False

    native["states"] = ["idle", "busy", "unknown", "idle"]
    monkeypatch.setattr(GitStore, "head", head)
    monkeypatch.setattr(app, "finish_stop", finish)
    from agent_workspace import bridges
    monkeypatch.setattr(bridges.BridgeManager, "tick", Mock(side_effect=AssertionError("no bridge events during stop")))
    runner.run()
    snap = app.store("sea").snapshot()
    handoffs = [path for path in snap.entries if path.startswith("handoffs/")]
    assert handoffs == ["handoffs/h" + binding[1:] + ".json"]
    assert app.agent("sea", "alice", snap)["current"] is None
    assert len(calls) == 2 and calls[0] == calls[1]
    assert calls[0]["expected_session"] == "original-chat"
    assert calls[0]["expected_checkpoint"] == point["id"]
    assert native["attached"] == ["original-chat", "original-chat"] and not native["sent"]
    assert 2 in waits and "stop_observation_unknown" in recorded_states
    assert read_json(root / ".aw-local/inputs/untouched.json")["state"] == "queued"


def test_regular_stop_unknown_publication_does_not_spawn_observer(desktop_owner, monkeypatch):
    app, root, binding, native = desktop_owner
    point = app.checkpoint("sea", "alice", "fixed request", binding=binding)
    runner = runtime.Runner(app, "sea", "alice")
    stopping = False

    def wait(delay):
        nonlocal stopping
        if not stopping:
            stopping = True
            app.stop("sea", "alice", binding, point["id"])
        return False

    monkeypatch.setattr(runner.stop_event, "wait", wait)
    finish = Mock(side_effect=Uncertain("handoff publication cannot be confirmed"))
    spawn = Mock(side_effect=AssertionError("unknown publication must not restart release"))
    monkeypatch.setattr(app, "finish_stop", finish)
    monkeypatch.setattr(runtime, "spawn_runner", spawn)
    with pytest.raises(Uncertain):
        runner.run()
    assert finish.call_count == 1 and not native["sent"]
    spawn.assert_not_called()
    assert app.show("sea", "alice")["binding"]["phase"] == "stopping"


def test_controller_cleanup_retries_only_its_failed_preflight_read(desktop_owner, monkeypatch):
    app, root, binding, _ = desktop_owner
    runner = runtime.Runner(app, "sea", "alice")
    runner.binding, runner.controller = binding, "original-controller"
    store = app.store("sea")
    snap = store.snapshot()
    path = f"bindings/{binding}.json"
    entry = snap.json(path)
    store.change("main", {path: encode({**entry, "controller": runner.controller})},
                 {path: snap.entries[path]}, "Isolated controller claim")
    original_change, original_head = store.change, GitStore.head
    in_cleanup, remaining = False, 1

    def head(current_store, branch):
        nonlocal remaining
        if in_cleanup and remaining and branch == "main":
            remaining -= 1
            raise RetryableRead("cleanup preflight read unavailable")
        return original_head(current_store, branch)

    def change(*args, **kwargs):
        nonlocal in_cleanup
        in_cleanup = True
        try:
            return original_change(*args, **kwargs)
        finally:
            in_cleanup = False

    delays = fast_wait(runner, monkeypatch)
    monkeypatch.setattr(GitStore, "head", head)
    monkeypatch.setattr(store, "change", change)
    runner._release_controller()
    assert delays == [2] and runner.controller is None
    entry = app.store("sea").snapshot().json(path)
    assert "controller" not in entry and entry["phase"] == "active"


def test_continue_reuses_live_runner(desktop_owner, monkeypatch):
    app, root, binding, _ = desktop_owner
    point = request_stop(desktop_owner)
    spawn = Mock()
    monkeypatch.setattr(runtime, "spawn_runner", spawn)
    with locked(root / ".aw-local/runner.lock", wait=0):
        result = runtime.continue_stop(app, "sea", "alice", binding, expected_checkpoint=point["id"])
    assert result["state"] == "runner_present"
    spawn.assert_not_called()


def test_stop_command_starts_only_stop_observer(desktop_owner, monkeypatch):
    app, _, binding, native = desktop_owner
    point = app.checkpoint("sea", "alice", "stop via public command", binding=binding)
    launches = []

    def spawn(app, workspace, agent_id, directory=None, *, stop_binding=None):
        launches.append(stop_binding)
        runtime.Runner(app, workspace, agent_id, directory, stop_binding=stop_binding).run()
        return {"pid": 1, "state": "starting_runner"}

    monkeypatch.setattr(runtime, "spawn_runner", spawn)
    result = execute(app, "agent.stop", {"workspace": "sea", "agent_id": "alice", "binding": binding,
                                        "checkpoint": point["id"]}, actor=("sea", "alice", binding))
    assert launches == [binding] and not native["sent"]
    assert result["observation"]["state"] == "starting_stop_observer"
    assert app.agent("sea", "alice")["current"] is None


def test_stop_arriving_during_runner_cleanup_has_an_observer(desktop_owner, monkeypatch):
    app, _, binding, native = desktop_owner
    point = app.checkpoint("sea", "alice", "stop while runner exits", binding=binding)
    runner = runtime.Runner(app, "sea", "alice")
    monkeypatch.setattr(runner.stop_event, "wait", Mock(return_value=True))
    native["on_close"] = lambda: app.stop("sea", "alice", binding, point["id"])
    spawn = Mock(return_value={"pid": 42, "state": "starting_runner"})
    monkeypatch.setattr(runtime, "spawn_runner", spawn)
    runner.run()
    spawn.assert_called_once()
    assert spawn.call_args.kwargs["stop_binding"] == binding
    assert app.show("sea", "alice")["binding"]["checkpoint"] == point["id"]
    assert not native["sent"]


def test_repeated_released_stop_does_not_touch_successor(desktop_owner, monkeypatch):
    app, _, binding, _ = desktop_owner
    point = request_stop(desktop_owner)
    runtime.Runner(app, "sea", "alice", stop_binding=binding).run()
    successor = app.reserve("sea", "alice")["binding"]
    spawn = Mock()
    monkeypatch.setattr(runtime, "spawn_runner", spawn)
    result = runtime.continue_stop(app, "sea", "alice", binding, expected_checkpoint=point["id"])
    assert result["state"] == "released" and result["handoff"] == "h" + binding[1:]
    assert app.agent("sea", "alice")["current"] == successor
    spawn.assert_not_called()


def test_concurrent_stop_observer_cannot_connect_second_adapter(desktop_owner):
    app, _, binding, native = desktop_owner
    request_stop(desktop_owner)
    entered, proceed = threading.Event(), threading.Event()
    failures = []

    def observe():
        entered.set()
        assert proceed.wait(20)

    native["on_status"] = observe

    def run():
        try:
            runtime.Runner(app, "sea", "alice", stop_binding=binding).run()
        except Exception as exc:
            failures.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    try:
        assert entered.wait(20)
        with pytest.raises(LockBusy):
            runtime.Runner(app, "sea", "alice", stop_binding=binding).run()
    finally:
        proceed.set()
        thread.join(timeout=20)
    assert not thread.is_alive() and not failures
    assert native["attached"] == ["original-chat"]


@pytest.mark.parametrize("kind", ["codex", "claude", "codebuddy"])
def test_missing_managed_runner_never_starts_new_writer(app, monkeypatch, kind):
    app.create("sea", "alice")
    app.configure("sea", "alice", {"kind": kind})
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "original-native-session")
    point = app.checkpoint("sea", "alice", "original stop", binding=binding)
    app.stop("sea", "alice", binding, point["id"])
    spawn = Mock()
    monkeypatch.setattr(runtime, "spawn_runner", spawn)
    result = runtime.continue_stop(app, "sea", "alice", binding)
    assert result["state"] == "stop_observation_unknown"
    assert app.show("sea", "alice")["binding"]["phase"] == "stopping"
    spawn.assert_not_called()


def test_desktop_different_native_session_is_not_idle(app, monkeypatch):
    root = app.home / "fixture-root"
    root.mkdir()
    adapter = object.__new__(runtime.Desktop)
    adapter.session = "original-chat"
    monkeypatch.setattr(adapter, "call", Mock(return_value={"thread": {"id": "another-chat", "status": {"type": "idle"}}}))
    with pytest.raises(Conflict):
        adapter.status()


def test_read_only_desktop_needs_only_read_tool_and_refuses_execution(app):
    app.create("sea", "alice")
    root = app.root("sea", "alice")
    config = {"kind": "desktop", "command": [sys.executable, str(Path(__file__).with_name("fake_native.py")), "desktop-readonly"],
              "pipe_path": "fixture", "caller_thread": "caller", "model": None}
    adapter = runtime.Desktop(root, config, "original-chat", read_only=True)
    try:
        assert adapter.status() == "idle"
        with pytest.raises(Conflict):
            adapter.create("original-binding")
        with pytest.raises(Conflict):
            adapter.notify("must not execute", "normal")
    finally:
        adapter.close()
    assert not (root / ".aw-local/launch.json").exists()


def test_stop_command_real_windows_process_and_git_protocol_peer(app, monkeypatch):
    app.create("sea", "alice")
    root = app.root("sea", "alice")
    config = {"kind": "desktop", "command": [sys.executable, str(Path(__file__).with_name("fake_native.py")), "desktop"],
              "pipe_path": "fixture", "caller_thread": "caller"}
    app.configure("sea", "alice", config)
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "original-protocol-chat")
    point = app.checkpoint("sea", "alice", "real child stop observer", binding=binding)
    monkeypatch.setenv("PYTHONPATH", str(Path(runtime.__file__).parents[1]))
    result = execute(app, "agent.stop", {"workspace": "sea", "agent_id": "alice", "binding": binding,
                                        "checkpoint": point["id"]}, actor=("sea", "alice", binding))
    assert result["observation"]["state"] == "starting_stop_observer"
    deadline = time.monotonic() + 30
    status = {}
    while time.monotonic() < deadline:
        status = read_json(root / ".aw-local/status.json", {})
        if status.get("state") in ("released", "failed"):
            break
        time.sleep(.1)
    assert status.get("state") == "released", (status, (root / ".aw-local/runner.log").read_text(encoding="utf-8"))
    assert status["session"] == "original-protocol-chat"
    assert app.agent("sea", "alice")["current"] is None
    assert not list((root / ".aw-local/inputs").glob("*.json"))
