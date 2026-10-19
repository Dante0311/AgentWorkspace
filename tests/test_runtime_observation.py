"""Protocol observation and versioned paths; no real Desktop or layout migration."""
from pathlib import Path
import queue
import threading
from types import SimpleNamespace

import pytest

from agent_workspace import backend, layout, model_profiles, runtime, software
from agent_workspace.util import Conflict, Error, digest, encode, read_json, write_bytes, write_json


@pytest.fixture(params=[0, 1])
def original_entry(app, monkeypatch, request):
    app.create("sea", "alice")
    app.configure("sea", "alice", {"kind": "desktop", "command": ["original-captured-tool"],
                  "pipe_path": "original-pipe", "caller_thread": "original-caller", "model": "fixture-model", "effort": "low"})
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "original-chat")
    root = app.root("sea", "alice")
    if request.param == 0:
        internal = root / ".agentworkspace"
        for path in internal.rglob("*"):
            if not path.is_file() or path.name == "layout.json":
                continue
            rel = path.relative_to(internal).as_posix()
            if rel.startswith("local/"):
                category, name = rel.removeprefix("local/").split("/", 1)
                target = root / ".aw-local" / (rel.removeprefix("local/") if category == "cache" else name)
            else:
                target = root / layout.instance_relpath({}, rel)
            write_bytes(target, path.read_bytes())
        (root / layout.MARKER).unlink()
    else:
        # A stale old-format control must not override a versioned copy.
        write_json(root / ".aw-local/control.json", {"stop": binding})
    assert layout.version(root, "instance") == request.param
    peer = {"reads": threading.Event(), "sent": threading.Event(), "attached": [], "closed": [], "inputs": [], "state": "idle"}

    class Native:
        def __init__(self, directory, config, session, *, read_only=False, worker_id=None, title=None):
            assert directory == root and session == "original-chat"
            assert config["pipe_path"] == "original-pipe"
            self.config = config
            self.session = session
            self.read_only = read_only
            self.tools = {"send_message_to_thread": {}}
            if not read_only:
                peer["attached"].append(session)
            if not read_only and peer.get("on_attach"):
                peer["on_attach"]()

        def read(self):
            return {"thread": {"id": self.session, "hostId": "local", "cwd": str(peer.get("cwd", root)),
                               "status": {"type": "idle"}}}

        def status(self):
            peer["reads"].set()
            return peer["state"]

        def completed_turns(self, identifiers):
            return {}

        def close(self):
            if not self.read_only:
                peer["closed"].append(self.session)

        def create(self, *args):
            pytest.fail("Observation cannot create a session")

        def notify(self, text, delivery):
            peer["inputs"].append((text, delivery))
            peer["state"] = "busy"
            peer["sent"].set()
            return {"threadId": self.session, "turn": {"id": "new-original-queued-turn"}}

        def model_choice(self, tool, selected_binding=None):
            return model_profiles.adopted(root, selected_binding or binding), {"effective": "unconfirmed"}

    monkeypatch.setattr(runtime, "Desktop", Native)
    return app, root, binding, peer


def test_recover_resumes_only_unattempted_input_on_same_chat_and_keeps_user_pause(original_entry):
    app, root, binding, peer = original_entry
    originals = {}
    for state in ("queued", "dispatching", "submitted", "outcome_unknown"):
        record = runtime.queue_input(app, "sea", "alice", "explicit original fixture", request_id=state)
        path = layout.local_path(root, "inputs") / f"{state}.json"
        write_json(path, {**record, "state": state, "turn_id": "original-turn"})
        originals[path] = path.read_bytes()
    snap = app.store("sea").snapshot()
    original_binding = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
    manager = backend.Backend(app, SimpleNamespace(server_port=0))
    app.backend = manager
    try:
        result = backend.recover(app, "sea", "alice", expected_binding=binding)
        assert result["state"] == "starting_runner" and peer["sent"].wait(30)
        assert backend.recover(app, "sea", "alice", expected_binding=binding)["state"] == "runner_present"
        assert peer["attached"] == ["original-chat"]
        write_json(layout.local_path(root, "control.json"), {"stop": binding})
        assert manager.cancel(root, binding)
        manager.runners[root]["thread"].join(30)
        assert not manager.runners[root]["thread"].is_alive()
        assert backend.recover(app, "sea", "alice", expected_binding=binding)["state"] == "recovery_paused"
        assert peer["attached"] == ["original-chat"]
    finally:
        manager.close()
        del app.backend
    snap = app.store("sea").snapshot()
    assert snap.json(layout.shared_path(snap, f"bindings/{binding}.json")) == original_binding
    assert all(path.read_bytes() == original for path, original in originals.items() if path.stem != "queued")
    assert read_json(layout.local_path(root, "inputs/queued.json"))["state"] == "submitted"
    assert len(peer["inputs"]) == 1
    assert peer["closed"] == ["original-chat"]


def test_recover_requires_original_execution_and_rejects_stale_request(original_entry):
    app, root, binding, peer = original_entry
    manager = backend.Backend(app, SimpleNamespace(server_port=0))
    with pytest.raises(Conflict):
        manager.recover("sea", "alice", expected_binding="different-binding")
    store = app.store("sea")
    snap = store.snapshot()
    path = layout.shared_path(snap, f"bindings/{binding}.json")
    entry = snap.json(path)
    entry.pop("execution")
    store.change("main", {path: encode(entry)}, {path: snap.entries[path]}, "Explicit legacy fixture")
    assert manager.recover("sea", "alice", expected_binding=binding)["reason_code"] == "execution_source_missing"
    assert not peer["attached"] and not manager.runners


def test_recovery_refuses_changed_native_cwd_without_moving_chat_or_claiming_controller(original_entry):
    app, root, binding, peer = original_entry
    peer["cwd"] = root.parent / "different-project"
    store = app.store("sea")
    before = store.snapshot()
    manager = backend.Backend(app, SimpleNamespace(server_port=0))
    result = manager.recover("sea", "alice", expected_binding=binding)
    assert result["state"] == "recovery_blocked" and result["reason_code"] == "native_local_copy_unconfirmed"
    assert not manager.runners and not peer["attached"] and not peer["inputs"]
    assert store.snapshot().entries == before.entries


def test_original_chat_moved_to_its_registered_material_directory_is_confirmed(original_entry):
    app, root, binding, peer = original_entry
    store = app.store("sea")
    snap = store.snapshot()
    path = layout.shared_path(snap, f"bindings/{binding}.json")
    entry = snap.json(path)
    entry["execution"]["cwd"] = str(root.parent / "original-shared-project")
    store.change("main", {path: encode(entry)}, {path: snap.entries[path]}, "Original shared-project observation")
    before = store.snapshot()
    result = runtime.desktop_observe(app, "sea", "alice")
    assert result["local_session_confirmed"] and result["session"] == "original-chat"
    assert result["native_cwd"] == str(root)
    assert store.snapshot().entries == before.entries
    assert not peer["attached"] and not peer["inputs"]


def test_pause_arriving_during_native_observation_prevents_recovery(original_entry, monkeypatch):
    app, root, binding, peer = original_entry
    observe = runtime.desktop_observe
    def paused(*args, **kwargs):
        result = observe(*args, **kwargs)
        write_json(layout.local_path(root, "control.json"), {"stop": binding})
        return result
    monkeypatch.setattr(runtime, "desktop_observe", paused)
    manager = backend.Backend(app, SimpleNamespace(server_port=0))
    result = manager.recover("sea", "alice", expected_binding=binding)
    assert result["state"] == "recovery_paused" and result["reason_code"] == "user_paused"
    assert not manager.runners and not peer["attached"] and not peer["inputs"]


@pytest.mark.parametrize("original_entry", [1], indirect=True)
def test_backend_updates_materials_before_connecting_original_session(original_entry):
    app, root, binding, peer = original_entry
    fresh = layout.resource_files()
    for rel, content in fresh.items():
        write_bytes(root / rel, content)
    prompt = ".agentworkspace/prompts/entry.md"
    old = b"previous installed platform entry instructions"
    write_bytes(root / prompt, old)
    manifest = read_json(root / software.MANIFEST)
    write_json(root / software.MANIFEST, {**manifest, "files": {**manifest["files"], prompt: digest(old)}})
    original_agents = (root / "AGENTS.md").read_bytes()
    ready = threading.Event()

    def check_materials():
        assert (root / prompt).read_bytes() == fresh[prompt]
        ready.set()

    peer["on_attach"] = check_materials
    manager = backend.Backend(app, SimpleNamespace(server_port=0))
    app.backend = manager
    try:
        manager.start()
        assert ready.wait(30)
        updated = next(row for row in manager.status()["software"]["instances"] if row["agent_id"] == "alice")
        assert updated["state"] == "updated" and manager.status()["watch_alive"]
        assert (root / "AGENTS.md").read_bytes() == original_agents
    finally:
        manager.close()
        del app.backend
    assert peer["attached"] == ["original-chat"] and not peer["inputs"]


@pytest.mark.parametrize("original_entry", [1], indirect=True)
def test_pending_material_update_blocks_recovery_before_any_native_connection(original_entry):
    app, root, binding, peer = original_entry
    path = layout.local_path(root, software.OPERATION)
    write_json(path, {"state": "pending", "original_plan": "preserved"})
    original_bytes = path.read_bytes()
    manager = backend.Backend(app, SimpleNamespace(server_port=0))
    with pytest.raises(Conflict):
        manager.recover("sea", "alice", expected_binding=binding)
    assert path.read_bytes() == original_bytes and not peer["attached"] and not manager.runners


def test_native_tool_rejection_pauses_stop_without_transport_retries(app, monkeypatch):
    app.create("sea", "alice")
    app.configure("sea", "alice", {"kind": "desktop", "command": ["protocol-fixture"],
                  "pipe_path": "fixture", "caller_thread": "fixture"})
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "original-chat")
    point = app.checkpoint("sea", "alice", "original stop", binding=binding)
    app.stop("sea", "alice", binding, point["id"])
    calls = []

    class RejectedRpc:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, method, params=None):
            calls.append((method, params))
            if method == "tools/list":
                return {"tools": [{"name": "read_thread"}]}
            if method == "tools/call":
                return {"isError": True, "content": [{"type": "text", "text": "configuration or authentication rejected"}]}
            return {}

        def send(self, *args):
            pass

        def close(self):
            pass

    monkeypatch.setattr(runtime, "Rpc", RejectedRpc)
    runner = runtime.Runner(app, "sea", "alice", stop_binding=binding)
    with pytest.raises(Error) as rejection:
        runner.run()
    assert rejection.value.code == "operation_failed"
    assert [params["name"] for method, params in calls if method == "tools/call"] == ["read_thread"]
    snap = app.store("sea").snapshot()
    entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
    assert entry["phase"] == "stopping" and entry["checkpoint"] == point["id"]
    assert entry["session"] == "original-chat"


@pytest.mark.parametrize("kind", ["codex", "claude", "codebuddy"])
def test_confirmed_managed_cli_reconnects_original_session_and_keeps_user_pause(app, monkeypatch, kind):
    app.create("sea", "alice")
    app.configure("sea", "alice", {"kind": kind, "command": ["captured-cli"], "executable": "captured-cli",
                                  "model": "fixture-model", "effort": "low"})
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "original-cli-session")
    root = app.root("sea", "alice")
    attached = []
    connected = threading.Event()

    class OriginalCli:
        def __init__(self, app, workspace, agent_id, entry, directory, config, session, *, worker_id=None, title=None):
            assert session == "original-cli-session" and entry == binding and directory == root
            self.session = session
            self.profile = {"model": "fixture-model", "effort": "low"}
            self.profile_validation = {"effective": "unconfirmed"}
            self.completed = queue.Queue()
            attached.append(session)
            connected.set()

        def connect(self):
            pass

        def status(self):
            return "busy"

        def bootstrap(self, *args):
            pytest.fail("Existing CLI session cannot redo initialization")

        def notify(self, *args):
            pytest.fail("This recovery has no new queued model work")

        def close(self):
            pass

    monkeypatch.setattr(runtime, "Codex" if kind == "codex" else "NativeSDK", OriginalCli)
    manager = backend.Backend(app, SimpleNamespace(server_port=0))
    try:
        resumed = manager.recover("sea", "alice", expected_binding=binding)
        assert resumed["state"] == "starting_runner" and connected.wait(30)
        write_json(layout.local_path(root, "control.json"), {"stop": binding})
        manager.cancel(root, binding)
        manager.runners[root]["thread"].join(30)
        assert not manager.runners[root]["thread"].is_alive()
        assert manager.recover("sea", "alice", expected_binding=binding)["state"] == "recovery_paused"
    finally:
        manager.close()
    assert attached == ["original-cli-session"]
    snap = app.store("sea").snapshot()
    saved = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
    assert saved["phase"] == "active" and saved["session"] == "original-cli-session"
