"""Transfer failures keep ownership and never recreate an uncertain session."""
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

from agent_workspace import runtime, transfer, bridges
from agent_workspace.messages import Messages
from agent_workspace.util import Conflict, Error, Unavailable, read_json, write_json


@pytest.fixture
def owner(app):
    app.create("sea", "alice")
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "original-session")
    return app, binding, app.root("sea", "alice")


def test_unknown_launch_is_not_retried_when_no_successor_was_observed(owner, monkeypatch):
    app, binding, root = owner
    target = {"kind": "codex", "command": [sys.executable, "-c", "pass"]}
    transfer.request(app, "sea", "alice", target, request_id="one-transfer")
    point = app.checkpoint("sea", "alice", "explicit handoff", binding=binding)
    app.stop("sea", "alice", binding, point["id"])
    app.finish_stop("sea", "alice", binding, observed_idle=True)
    start = Mock(side_effect=Unavailable("launch reply lost"))
    monkeypatch.setattr(runtime, "start", start)
    with pytest.raises(Unavailable):
        transfer.advance(app, "sea", "alice")
    assert read_json(root / ".aw-local/transfer.json")["state"] == "outcome_unknown"
    with pytest.raises(Conflict, match="reconciliation"):
        transfer.advance(app, "sea", "alice")
    assert start.call_count == 1
    assert app.agent("sea", "alice")["current"] is None


def test_preflight_failure_does_not_touch_the_old_entry(owner):
    app, binding, root = owner
    with pytest.raises(Error):
        transfer.request(app, "sea", "alice", {"kind": "codex", "command": ["/missing/native-tool"]})
    assert app.agent("sea", "alice")["current"] == binding
    assert not (root / ".aw-local/transfer.json").exists()
    assert not (root / ".aw-local/control.json").exists()


def test_unconfirmed_native_close_does_not_release_binding(app, monkeypatch):
    app.create("sea", "alice")
    app.configure("sea", "alice", {"kind": "codex", "command": [sys.executable]})
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "native-session")
    point = app.checkpoint("sea", "alice", "explicit handoff", binding=binding)
    adapter = Mock(session="native-session")
    adapter.status.return_value = "idle"
    adapter.close.side_effect = Unavailable("native close unconfirmed")
    def connect(*args):
        app.stop("sea", "alice", binding, point["id"])
        return adapter
    monkeypatch.setattr(runtime, "Codex", connect)
    runner = runtime.Runner(app, "sea", "alice")
    with pytest.raises(Unavailable, match="unconfirmed"):
        runner.run()
    state = app.show("sea", "alice")
    assert state["current"] == binding
    assert state["binding"]["phase"] == "stopping"
    assert state["binding"]["controller"]
    assert state["runtime"]["state"] == "native_stop_unconfirmed"


def test_unsupported_insert_does_not_consume_an_attempt_or_relabel_the_input(owner):
    app, binding, root = owner
    adapter = Mock(supports_insert=False)
    messages = Messages(app)
    messages.send("sea", "alice", binding, "alice", "explicit test", delivery="insert", request_id="insert-message")
    assert messages.poll("sea", "alice", binding, adapter=adapter)["state"] == "delivery_unsupported"
    assert app.store("sea").snapshot().json("dispatch/alice.json") is None
    runtime.queue_input(app, "sea", "alice", "explicit input", delivery="insert", request_id="input")
    runner = runtime.Runner(app, "sea", "alice")
    runner.binding, runner.adapter = binding, adapter
    runner._inputs()
    assert read_json(root / ".aw-local/inputs/input.json")["state"] == "queued"
    adapter.notify.assert_not_called()


def test_bridge_retry_cannot_overwrite_a_new_disable(owner):
    app, binding, root = owner
    value = {"command": [sys.executable], "enabled": True}
    bridges.configure(app, "sea", "alice", "test", value)
    old = read_json(root / ".aw-local/bridges/test.json")
    bridges.configure(app, "sea", "alice", "test", {**value, "enabled": False})
    with pytest.raises(Conflict, match="changed"):
        bridges.configure(app, "sea", "alice", "test", old, expected_generation=old["generation"])
    assert not read_json(root / ".aw-local/bridges/test.json")["enabled"]
