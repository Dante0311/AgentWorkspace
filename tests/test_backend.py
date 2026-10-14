"""Isolated home lifecycle and real Runner threads; Desktop is a protocol fixture."""
from agent_workspace import layout
import json
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import urllib.request

import pytest

from agent_workspace import backend, cli, model_profiles, runtime
from agent_workspace.app import App
from agent_workspace.commands import execute
from agent_workspace.util import Conflict, Error, encode, read_json, write_json


def wait_for(read, check, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = read()
        if check(value):
            return value
        time.sleep(.05)
    pytest.fail(f"Timed out waiting for the original operation: {value}")


def test_empty_home_actual_process_lifecycle_and_cli(tmp_path, monkeypatch, capsys):
    app = App(tmp_path / "isolated-home")
    other = App(tmp_path / "other-home")
    monkeypatch.setenv("PYTHONPATH", str(Path(runtime.__file__).parents[1]))
    token = None
    try:
        started = execute(app, "backend.start", {"port": 0})
        running = wait_for(lambda: backend.status(app), lambda state: state["ready"])
        assert started["start_requested"] and running["maintenance_alive"]
        assert running["runners"] == [] and not backend.status(other)["running"]
        connection = read_json(app.home / "backend/connection.json")
        token = connection["token"]
        with urllib.request.urlopen(running["url"], timeout=5) as response:
            assert response.read() == (Path(runtime.__file__).parent / "resources/index.html").read_bytes()
        assert not execute(app, "backend.start", {})["start_requested"]
        assert backend.status(app)["pid"] == running["pid"]
        assert cli.main(["--home", str(app.home), "backend", "status"]) == 0
        assert json.loads(capsys.readouterr().out)["result"]["ready"]
        request = execute(app, "backend.restart", {})
        assert request["restart_requested"] and not request["ready"]
        renewed = wait_for(lambda: backend.status(app), lambda state: state["ready"] and state.get("pid") != running["pid"])
        assert renewed["url"] == running["url"]
        assert read_json(app.home / "backend/connection.json")["token"] == token
        stopped = execute(app, "backend.stop", {})
        assert stopped["stop_requested"] and not stopped["agent_bindings_released"]
        assert not stopped["native_chat_shutdown_requested"]
        wait_for(lambda: backend.status(app), lambda state: state["running"] is False)
        assert cli.main(["--home", str(app.home), "backend", "log", "--lines", "5"]) == 0
        log = json.loads(capsys.readouterr().out)["result"]
        assert log["exists"] and "Backend stopped" in log["content"] and token not in log["content"]
        assert backend.start(app)["start_requested"]
        assert wait_for(lambda: backend.status(app), lambda state: state["ready"])["url"] == running["url"]
    finally:
        backend.stop(app)
        wait_for(lambda: backend.status(app), lambda state: state["running"] is False)


def test_model_cannot_control_another_agents_runner(pair, monkeypatch, capsys):
    app, ids = pair
    actor = ("sea", "alice", ids["alice"])
    for command in ("backend.attach", "backend.cancel"):
        with pytest.raises(Error, match="user-management"):
            execute(app, command, {}, actor=actor)
    assert execute(app, "backend.status", {}, actor=actor)["running"] is False
    monkeypatch.setenv("AW_WORKSPACE", "sea")
    monkeypatch.setenv("AW_AGENT", "alice")
    monkeypatch.setenv("AW_BINDING", ids["alice"])
    assert cli.main(["--home", str(app.home), "runtime", "run", "alice"]) == 2
    assert not json.loads(capsys.readouterr().err)["ok"]


def test_two_agents_share_process_preserve_routes_and_resume_original_sessions(app, monkeypatch):
    roots, bindings, configured = {}, {}, {}
    for name in ("alice", "bob"):
        app.create("sea", name)
        root = app.root("sea", name)
        config = {"kind": "desktop", "command": ["captured-native"], "pipe_path": "pipe-" + name,
                  "caller_thread": "caller-" + name, "model": "fixture-model", "effort": "low"}
        app.configure("sea", name, config)
        binding = app.reserve("sea", name)["binding"]
        app.bind("sea", name, binding, "native-" + name)
        runtime.queue_input(app, "sea", name, "keep queued while busy", request_id="queued-original")
        runtime.queue_input(app, "sea", name, "uncertain original", request_id="unknown-original")
        unknown = layout.local_path(root, "inputs/unknown-original.json")
        write_json(unknown, {**read_json(unknown), "state": "outcome_unknown", "turn_id": "original-turn"})
        roots[name], bindings[name], configured[name] = root, binding, read_json(layout.local_path(root, "runtime.json"))
    attached, closed, observed = [], [], {name: threading.Event() for name in roots}

    class DesktopPeer:
        supports_insert = True

        def __init__(self, root, config, session, *, read_only=False):
            self.root, self.session = root, session
            self.name = root.name
            assert root == roots[self.name] and config == configured[self.name]
            assert model_profiles.adopted(root, bindings[self.name])["model"] == "fixture-model"
            assert session == "native-" + self.name and not read_only
            attached.append((self.name, session, os.getpid(), config["pipe_path"], config["caller_thread"]))

        def status(self):
            observed[self.name].set()
            return "busy"

        def completed_turns(self, identifiers):
            return {}

        def notify(self, *args):
            pytest.fail("Busy or unknown original inputs must not be replayed")

        def create(self, *args):
            pytest.fail("Backend resume must never create a replacement native session")

        def close(self):
            closed.append(self.name)

    monkeypatch.setattr(runtime, "Desktop", DesktopPeer)
    http = SimpleNamespace(server_port=12345)
    manager = backend.Backend(app, http)
    app.backend = manager
    try:
        # One damaged local copy must not prevent another Agent from resuming.
        control = layout.local_path(roots["alice"], "control.json")
        control.write_text("invalid JSON", encoding="utf-8")
        manager._restore()
        assert observed["bob"].wait(90)
        assert "alice" not in [item[0] for item in attached]
        assert any(note.get("agent_id") == "alice" for note in manager.resume_notes)
        write_json(control, {})
        runtime.spawn_runner(app, "sea", "alice")
        assert observed["alice"].wait(90)
        assert {item[2] for item in attached} == {os.getpid()}
        assert runtime.spawn_runner(app, "sea", "bob")["state"] == "runner_present"
        (layout.local_path(roots["alice"], "status.json")).write_text("not JSON", encoding="utf-8")
        state = manager.status()
        assert state["ready"] and len(state["runners"]) == 2
        assert next(item for item in state["runners"] if item["agent_id"] == "alice")["runtime"]["state"] == "unknown"
        assert next(item for item in state["runners"] if item["agent_id"] == "bob")["runner_alive"]
        result = execute(app, "runtime.stop", {"workspace": "sea", "agent_id": "alice"})
        assert result["observer_signalled"] and not result["execution_right_released"]
        manager.runners[roots["alice"]]["thread"].join(90)
        assert not manager.runners[roots["alice"]]["thread"].is_alive()
        assert manager.runners[roots["bob"]]["thread"].is_alive()
    finally:
        manager.close()
        del app.backend
    assert all(not task["thread"].is_alive() for task in manager.threads)
    snap = app.store("sea").snapshot()
    for name, binding in bindings.items():
        entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
        assert entry["phase"] == "active" and entry["session"] == "native-" + name and not entry.get("controller")
        assert read_json(layout.local_path(roots[name], "inputs/queued-original.json"))["state"] == "queued"
        assert read_json(layout.local_path(roots[name], "inputs/unknown-original.json"))["state"] == "outcome_unknown"
    # Whole-backend stop is reversible. An explicit per-Agent cancellation is retained.
    observed["bob"].clear()
    renewed = backend.Backend(app, http)
    app.backend = renewed
    try:
        renewed._restore()
        assert observed["bob"].wait(90)
        assert roots["alice"] not in renewed.runners
        assert [item[0] for item in attached].count("alice") == 1
        assert [item[0] for item in attached].count("bob") == 2
    finally:
        renewed.close()
        del app.backend
    assert sorted(closed) == ["alice", "bob", "bob"]


def test_restore_does_not_repeat_unknown_creation_or_guess_execution(app, monkeypatch):
    app.create("sea", "alice")
    app.configure("sea", "alice", {"kind": "desktop", "model": "fixture-model", "effort": "low"})
    binding = app.reserve("sea", "alice")["binding"]
    root = app.root("sea", "alice")
    receipt = {"binding": binding, "attempted": True, "result": {"clientThreadId": "original-client"}}
    write_json(layout.local_path(root, "launch.json"), receipt)
    manager = backend.Backend(app, SimpleNamespace(server_port=12345))
    monkeypatch.setattr(manager, "attach", lambda *args, **kwargs: pytest.fail("Unqualified record must not restart"))
    manager._restore()
    assert not manager.runners and read_json(layout.local_path(root, "launch.json")) == receipt
    assert any("No confirmed native session" in note["reason"] for note in manager.resume_notes)
    store = app.store("sea")
    snap = store.snapshot()
    entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
    entry.pop("execution")
    path = layout.shared_path(snap, f"bindings/{binding}.json")
    store.change("main", {path: encode(entry)}, {path: snap.entries[path]}, "Legacy execution fixture")
    manager._restore()
    assert any("Execution source is missing" in note["reason"] for note in manager.resume_notes)


def test_explicit_starting_binding_runs_once_and_stale_request_is_rejected(app, monkeypatch):
    app.create("sea", "alice")
    app.configure("sea", "alice", {"kind": "desktop", "model": "fixture-model", "effort": "low"})
    binding = app.reserve("sea", "alice")["binding"]
    root = app.root("sea", "alice")
    observed, creations = threading.Event(), []

    class DesktopPeer:
        def __init__(self, root, config, session):
            assert session is None
            self.session = None

        def create(self, expected, prompt):
            assert expected == binding
            assert json.loads(prompt.split('\n\n')[0])['binding'] == binding
            creations.append(expected)
            self.session = "explicit-original-chat"
            return {"id": self.session, "hostId": "local", "cwd": str(root)}

        def status(self):
            observed.set()
            return "busy"

        def close(self):
            pass

    monkeypatch.setattr(runtime, "Desktop", DesktopPeer)
    manager = backend.Backend(app, SimpleNamespace(server_port=12345))
    app.backend = manager
    try:
        with pytest.raises(Conflict, match="original Binding changed"):
            backend.attach(app, "sea", "alice", expected_binding="older-original")
        assert not manager.runners
        result = execute(app, "runtime.start", {"workspace": "sea", "agent_id": "alice"})
        assert result["binding"] == binding and result["pid"] == os.getpid()
        assert observed.wait(90)
    finally:
        manager.close()
        del app.backend
    assert creations == [binding]
    snap = app.store("sea").snapshot()
    assert snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))["session"] == "explicit-original-chat"
    boot = read_json(layout.local_path(root, "inputs") / f"boot-{binding}.json")
    assert boot["state"] == "queued" and boot["binding"] == binding


def test_log_is_bounded_registered_and_redacts_control_credentials(app):
    app.create("sea", "alice")
    root = app.root("sea", "alice")
    write_json(app.home / "backend/connection.json", {"token": "original-control-token"})
    path = layout.local_path(root, "runner.log")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("old\noriginal-control-token Bearer secret-value https://user:password@host/path#token=secret\nlast\n", encoding="utf-8")
    result = execute(app, "backend.log", {"workspace": "sea", "agent_id": "alice", "lines": 2})
    assert result["truncated"] and result["source"]["directory"] == str(root)
    assert result["content"].endswith("last") and "[redacted]" in result["content"]
    for secret in ("original-control-token", "secret-value", "user:password", "token=secret"):
        assert secret not in result["content"]
    with pytest.raises(Error):
        backend.log(app, "sea", "alice", str(app.home / "unregistered"))
    with pytest.raises(Error):
        backend.log(app, lines=501)
