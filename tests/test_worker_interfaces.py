"""Public Worker commands with isolated Git and manual entries, without native models."""
import json
import threading
import urllib.request

import pytest

from agent_workspace import bridges, commands, layout, runtime
from agent_workspace.app import App
from agent_workspace.cli import parser
from agent_workspace.server import make_server
from agent_workspace.util import Conflict, Error, read_json


@pytest.fixture
def workers_app(tmp_path):
    app = App(tmp_path / "home")
    app.workspace_init("team", str(tmp_path / "team.git"), worker_support=True)
    app.create("team", "helper")
    app.worker_create("team", "helper", "Review", "Review selected materials", worker_id="review")
    entries = {}
    for worker_id in ("default", "review"):
        entry = app.reserve("team", "helper", worker_id=worker_id)
        app.bind("team", "helper", entry["binding"], "manual-" + worker_id, worker_id=worker_id)
        entries[worker_id] = entry["binding"]
    return app, entries


def test_actor_keeps_its_worker_when_default_changes(workers_app):
    app, entries = workers_app
    actor = ("team", "helper", entries["default"])
    app.worker_default("team", "helper", "review", app.show("team", "helper")["revision"])
    point = commands.execute(app, "checkpoint.create", {"summary": "Original Worker progress"}, actor=actor)
    assert point["worker"] == "default"
    assert commands.execute(app, "worker.show", {}, actor=actor)["id"] == "default"
    with pytest.raises(Conflict):
        commands.execute(app, "checkpoint.create", {"worker_id": "review", "summary": "Wrong target"}, actor=actor)
    with pytest.raises(Conflict):
        commands.execute(app, "worker.handoff", {"worker_id": "review"}, actor=actor)
    with pytest.raises(Conflict):
        commands.execute(app, "asset.write", {"path": "workers/review/other.md", "content": "wrong"}, actor=actor)
    assert app.worker("team", "helper", "review")["current"] == entries["review"]
    assert not (app.root("team", "helper") / "workers/review/other.md").exists()

    app.stop("team", "helper", entries["default"], point["id"], worker_id="default")
    app.finish_stop("team", "helper", entries["default"], observed_idle=True, worker_id="default")
    assert commands.execute(app, "worker.show", {}, actor=actor)["id"] == "default"
    with pytest.raises(Conflict):
        commands.execute(app, "worker.create", {"name": "stale", "description": "No authority"}, actor=actor)


def test_current_worker_can_create_and_start_idle_sibling(workers_app):
    app, entries = workers_app
    actor = ("team", "helper", entries["default"])
    created = commands.execute(app, "worker.create", {
        "name": "Investigation", "worker_id": "investigate", "description": "Approved investigation",
        "request_id": "approved-worker-create",
    }, actor=actor)
    assert created["current"] is None and created["starts_session"] is False
    started = commands.execute(app, "worker.start", {"worker_id": "investigate"}, actor=actor)
    assert app.worker("team", "helper", "investigate")["current"] == started["binding"]
    assert app.worker("team", "helper", "default")["current"] == entries["default"]
    assert app.worker("team", "helper", "review")["current"] == entries["review"]
    with pytest.raises(Error):
        commands.execute(app, "worker.migrate", {"worker_id": "default", "request_id": "not-management"}, actor=actor)


def test_fresh_public_workspace_has_worker_tools_and_readable_state(tmp_path):
    app = App(tmp_path / "home")
    server = make_server(app, 0, "worker-http-test")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    headers = {"Authorization": "Bearer worker-http-test", "Content-Type": "application/json"}

    def call(name, arguments):
        request = urllib.request.Request(base + "/api/execute", headers=headers,
            data=json.dumps({"command": name, "arguments": arguments}).encode())
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)["result"]

    try:
        created = call("workspace.init", {"name": "team", "directory": str(tmp_path / "team.git")})
        assert created["state"] == "created"
        args = {"workspace": "team", "agent_id": "steward"}
        assert call("worker.list", args)[0]["id"] == "default"
        call("worker.create", {**args, "name": "Review", "worker_id": "review", "description": "Separate review"})
        entry = call("worker.start", {**args, "worker_id": "review"})
        call("worker.bind", {**args, "worker_id": "review", "binding": entry["binding"], "session": "manual-http-review"})
        with urllib.request.urlopen(urllib.request.Request(base + "/api/state", headers=headers), timeout=120) as response:
            state = json.load(response)["result"]
        steward = next(item for item in state["agents"] if item["id"] == "steward")
        scopes = {item["worker_id"]: item for item in steward["worker_states"]}
        assert set(scopes) == {"default", "review"}
        assert scopes["review"]["binding"]["session"] == "manual-http-review"
        assert scopes["default"]["current"] is None
        assert {item["snapshot_revision"] for item in scopes.values()} == {steward["snapshot_revision"]}
        assert (app.root("team", "steward") / ".agents/skills/worker/SKILL.md").is_file()
        assert call("asset.list", args)["files"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_bridge_input_and_records_stay_with_original_worker(workers_app, monkeypatch):
    app, entries = workers_app
    root = app.root("team", "helper")
    received = []
    monkeypatch.setattr(runtime, "queue_input", lambda *args, **kwargs: received.append(kwargs))
    manager = bridges.BridgeManager(app, "team", "helper", entries["review"], root)
    manager._event("test", {"event": "input", "id": "incoming-1", "text": "Original worker input"})
    assert received[0]["worker_id"] == "review"
    assert received[0]["expected_binding"] == entries["review"]
    assert list(layout.instance_path(root, "records/channels/test", "review").glob("*.json"))
    assert not layout.instance_path(root, "records/channels", "default").exists()


def test_worker_cli_arguments_are_explicit():
    parsed = parser().parse_args(["-w", "team", "worker", "create", "helper", "战斗规则", "--id", "combat",
                                  "--description", "Rules", "--request-id", "create-combat"])
    assert parsed.worker_id == "combat" and parsed.request_id == "create-combat"
    parsed = parser().parse_args(["-w", "team", "message", "send", "helper", "--reply-to", "original",
                                  "--delivery", "normal", "--content", "Reply"])
    assert parsed.to is None and parsed.reply_to == "original"
