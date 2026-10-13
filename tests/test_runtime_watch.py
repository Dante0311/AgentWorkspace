from agent_workspace import layout
"""An enabled queue checker works without a model or a native writer."""
from pathlib import Path
import time
from types import SimpleNamespace

import pytest

from agent_workspace import backend, runtime
from agent_workspace.commands import execute
from agent_workspace.messages import Messages
from agent_workspace.util import RetryableRead, read_json, write_json


def wait_for(read, check, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = read()
        if check(value):
            return value
        time.sleep(.1)
    pytest.fail(f"Original watch did not reach the expected state: {value}")


def test_public_watch_start_checks_without_runner_and_preserves_stop_on_backend_restart(pair, monkeypatch):
    app, bindings = pair
    monkeypatch.setenv("PYTHONPATH", str(Path(runtime.__file__).parents[1]))
    Messages(app).send("sea", "bob", bindings["bob"], "alice", "explicit check-only message",
                       request_id="watch-queue-message")
    root = app.root("sea", "alice")
    original = runtime.queue_input(app, "sea", "alice", "do not execute while checking", request_id="saved-business")
    original_path = layout.local_path(root, 'inputs/saved-business.json')
    original_bytes = original_path.read_bytes()

    def watch_state():
        return next((row for row in backend.status(app).get("watches", []) if row["agent_id"] == "alice"), {})

    try:
        result = execute(app, "message.watch", {"workspace": "sea", "agent_id": "alice", "operation": "start", "interval": .5})
        assert result["enabled"] and result["backend"]["ready"]
        checked = wait_for(watch_state, lambda row: row.get("state") == "checked")
        assert checked["poll"]["state"] == "awaiting_manual_receive"
        assert checked["poll"]["notification"]["message_id"] == "watch-queue-message"
        assert backend.status(app)["watch_alive"] and not backend.status(app)["runners"]
        assert original_path.read_bytes() == original_bytes and original["state"] == "queued"
        paused = execute(app, "message.watch", {"workspace": "sea", "agent_id": "alice", "operation": "stop"})
        assert not paused["enabled"]
        wait_for(watch_state, lambda row: row.get("state") == "disabled")
        backend.stop(app)
        wait_for(lambda: backend.status(app), lambda row: row["running"] is False)
        assert backend.start(app)["ready"]
        wait_for(watch_state, lambda row: row.get("state") == "disabled")
        assert app.agent("sea", "alice")["current"] == bindings["alice"]
        assert original_path.read_bytes() == original_bytes
    finally:
        backend.stop(app)
        wait_for(lambda: backend.status(app), lambda row: row["running"] is False)


def test_watch_checker_honors_pause_handoff_and_ownership_without_native_calls(pair, monkeypatch):
    app, bindings = pair
    root = app.root("sea", "alice")
    manager = backend.Backend(app, SimpleNamespace(server_port=0))
    write_json(layout.local_path(root, 'watch.json'), {"enabled": True, "binding": bindings["alice"], "interval": .5})
    polls = []
    monkeypatch.setattr(Messages, "poll", lambda *args, **kwargs: polls.append(kwargs) or {"state": "empty"})
    key = ("sea", "alice", root.resolve())
    for field, state in (("stop", "user_paused"), ("handoff", "handoff_paused")):
        write_json(layout.local_path(root, 'control.json'), {field: bindings["alice"]})
        manager.watches.clear()
        manager._check_watches()
        assert manager.watches[key]["state"] == state and not polls
    write_json(layout.local_path(root, 'control.json'), {})
    write_json(layout.local_path(root, 'watch.json'), {"enabled": True, "binding": "unrelated-binding", "interval": .5})
    manager.watches.clear()
    manager._check_watches()
    assert manager.watches[key]["state"] == "entry_inactive" and not polls


def test_watch_transient_read_attempts_are_bounded_and_explicit_enable_resets_them(pair, monkeypatch):
    app, bindings = pair
    root = app.root("sea", "alice")
    manager = backend.Backend(app, SimpleNamespace(server_port=0))
    path = layout.local_path(root, 'watch.json')
    write_json(path, {"enabled": True, "binding": bindings["alice"], "interval": .5, "changed_at": "original"})
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise RetryableRead("temporary read failure")

    monkeypatch.setattr(Messages, "poll", fail)
    key = ("sea", "alice", root.resolve())
    for _ in range(5):
        manager._check_watches()
        manager.watches[key]["next_check"] = 0
    assert len(calls) == 5 and manager.watches[key]["state"] == "check_paused"
    manager._check_watches()
    assert len(calls) == 5
    write_json(path, {**read_json(path), "changed_at": "explicit-new-enable"})
    manager._check_watches()
    assert len(calls) == 6 and manager.watches[key]["attempts"] == 1


def test_watch_registry_read_failure_is_reported_and_bounded(pair, monkeypatch):
    app, _ = pair
    manager = backend.Backend(app, SimpleNamespace(server_port=0))
    calls, delays = [], []

    def unavailable():
        calls.append(1)
        raise RetryableRead("original registry temporarily unavailable")

    monkeypatch.setattr(app, "workspace_list", unavailable)
    monkeypatch.setattr(manager.stop_event, "wait", lambda seconds: delays.append(seconds) or False)
    manager._watch()
    assert len(calls) == 5 and delays == [2, 4, 8, 16]
    assert manager.status()["watch_failure"]["state"] == "check_paused"
    assert not manager.runners
