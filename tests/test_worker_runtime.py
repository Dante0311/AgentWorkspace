"""Same-Agent Worker isolation using real Git and protocol-only native peers."""
import json
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent_workspace import backend, bridges, compaction, layout, model_profiles, runtime, transfer
from agent_workspace.app import App
from agent_workspace.util import Conflict, Unavailable, read_json, write_bytes


@pytest.fixture
def team(tmp_path):
    app = App(tmp_path / "home")
    app.workspace_init("team", str(tmp_path / "remote.git"), worker_support=True)
    app.create("team", "owner")
    app.worker_create("team", "owner", "Topic", "Isolated protocol test task", worker_id="topic")
    app.configure("team", "owner", {"kind": "desktop", "command": ["protocol-fixture"],
                  "pipe_path": "fixture", "caller_thread": "fixture", "model": "base-model", "effort": "low"})
    root = app.root("team", "owner")
    bindings = {}
    for worker in ("default", "topic"):
        binding = app.reserve("team", "owner", worker_id=worker)["binding"]
        app.bind("team", "owner", binding, "session-" + worker, worker_id=worker)
        bindings[worker] = binding
    return app, root, bindings


def until(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.05)
    assert predicate(), "Worker did not reach the expected durable state"


def test_actual_session_selects_worker_and_sibling_argument_cannot_change_identity(team, monkeypatch):
    app, root, bindings = team
    monkeypatch.setenv("CODEX_THREAD_ID", "session-topic")
    assert runtime.desktop_actor(app, "team", "owner") == ("team", "owner", bindings["topic"])
    with pytest.raises(Conflict):
        runtime.queue_input(app, "team", "owner", "wrong worker", expected_binding=bindings["topic"], worker_id="default")
    runtime.queue_input(app, "team", "owner", "topic input", expected_binding=bindings["topic"], request_id="same-id")
    assert read_json(layout.local_path(root, "inputs/same-id.json", "topic"))["binding"] == bindings["topic"]
    assert not layout.local_path(root, "inputs/same-id.json", "default").exists()
    monkeypatch.setenv("CODEX_THREAD_ID", "unregistered-session")
    monkeypatch.chdir(root)
    assert runtime.desktop_directory_actor(app, "checkpoint.create") is None
    with pytest.raises(Conflict):
        runtime.desktop_actor(app, "team", "owner")


def test_worker_overrides_and_adopted_configuration_remain_independent(team):
    app, root, bindings = team
    model_profiles.configure(root, {"kind": "desktop", "model": "topic-model", "effort": "high"}, "topic")
    assert model_profiles.selected(root, "topic")["model"] == "topic-model"
    assert model_profiles.selected(root, "default")["model"] == "base-model"
    app.configure("team", "owner", {"kind": "manual", "model": "later-model", "effort": "medium"})
    for worker, binding in bindings.items():
        adopted = read_json(layout.local_path(root, "entry.json", worker))
        assert adopted["config"]["kind"] == "desktop"
        assert adopted["config"]["pipe_path"] == "fixture"
        assert model_profiles.adopted(root, binding, worker_id=worker)["model"] == "base-model"
    assert model_profiles.runtime_config(root, "default")["kind"] == "manual"
    assert model_profiles.runtime_config(root, "topic")["kind"] == "desktop"


def test_two_controllers_pause_and_recover_only_the_original_worker(team, monkeypatch):
    app, root, bindings = team
    sent, connected = [], []

    class DesktopPeer:
        supports_insert = True

        def __init__(self, root, config, session, *, read_only=False, worker_id=None, title=None):
            self.root, self.config, self.session, self.worker_id = root, config, session, worker_id
            connected.append((worker_id, session, config["kind"]))

        def status(self):
            return "idle"

        def completed_turns(self, identifiers):
            return {}

        def model_choice(self, tool, binding=None):
            return model_profiles.adopted(self.root, binding, worker_id=self.worker_id), {"effective": "unconfirmed"}

        def notify(self, text, delivery):
            sent.append((self.worker_id, text))
            return {"turn": {"id": self.worker_id + "-turn"}}

        def create(self, *args):
            pytest.fail("Recovery must not create a session")

        def close(self):
            pass

    monkeypatch.setattr(runtime, "Desktop", DesktopPeer)
    service = backend.Backend(app, SimpleNamespace(server_port=0))
    app.configure("team", "owner", {"kind": "manual"})
    for worker, binding in bindings.items():
        runtime.queue_input(app, "team", "owner", worker, request_id="one", expected_binding=binding)
    try:
        for worker, binding in bindings.items():
            service.recover("team", "owner", expected_binding=binding)
        until(lambda: all(read_json(layout.local_path(root, "inputs/one.json", worker))["state"] == "submitted"
                          for worker in bindings))
        assert len(service.runners) == 2
        assert {item["worker_id"] for item in service.status()["runners"]} == set(bindings)
        assert service.cancel(root, bindings["default"], worker_id="default")
        service.runners[(root, "default")]["thread"].join(10)
        assert service.runners[(root, "topic")]["thread"].is_alive()
        # A submitted result belongs to the original turn. Restarting observation
        # must not reset it to queued, even when current Agent defaults changed.
        service.recover("team", "owner", expected_binding=bindings["default"])
        runtime.queue_input(app, "team", "owner", "topic continues", request_id="two", expected_binding=bindings["topic"])
        until(lambda: read_json(layout.local_path(root, "inputs/two.json", "topic"))["state"] == "submitted")
        assert [worker for worker, _ in sent].count("default") == 1
        assert [worker for worker, _ in sent].count("topic") == 2
        assert all(kind == "desktop" for _, _, kind in connected)
        assert all(app.worker("team", "owner", worker)["current"] == binding for worker, binding in bindings.items())
    finally:
        service.stop_event.set()
        for task in service.threads:
            task["runner"].stop_event.set()
        for task in service.threads:
            task["thread"].join(10)
        assert not any(task["thread"].is_alive() for task in service.threads)


def test_unknown_transfer_preserves_peer_and_original_launch(team, monkeypatch):
    app, root, bindings = team
    monkeypatch.setattr(transfer, "preflight", Mock(return_value=None))
    transfer.request(app, "team", "owner", {"kind": "desktop"}, request_id="move", worker_id="topic")
    assert not layout.local_path(root, "transfer.json", "default").exists()
    point = app.checkpoint("team", "owner", "handoff", binding=bindings["topic"], worker_id="topic")
    app.stop("team", "owner", bindings["topic"], point["id"], worker_id="topic")
    app.finish_stop("team", "owner", bindings["topic"], observed_idle=True, worker_id="topic")
    launch = Mock(side_effect=Unavailable("original launch reply lost"))
    monkeypatch.setattr(runtime, "start", launch)
    with pytest.raises(Unavailable):
        transfer.advance(app, "team", "owner", worker_id="topic")
    with pytest.raises(Conflict, match="reconciliation"):
        transfer.advance(app, "team", "owner", worker_id="topic")
    assert launch.call_count == 1
    assert launch.call_args.kwargs["worker_id"] == "topic"
    assert app.worker("team", "owner", "default")["current"] == bindings["default"]
    assert not layout.local_path(root, "control.json", "default").exists()


def test_bridge_input_and_control_use_binding_worker(team, monkeypatch):
    app, root, bindings = team
    manager = bridges.BridgeManager(app, "team", "owner", bindings["topic"], root)
    manager._event("chat", {"event": "input", "id": "original", "text": "external fixture"})
    queued = list(layout.local_path(root, "inputs", "topic").glob("*.json"))
    assert len(queued) == 1 and read_json(queued[0])["binding"] == bindings["topic"]
    assert not list(layout.local_path(root, "inputs", "default").glob("*.json"))
    with pytest.raises(Conflict):
        bridges.BridgeManager(app, "team", "owner", bindings["topic"], root, worker_id="default")
    monkeypatch.setenv("AW_WORKER", "stale-peer")
    bridges.configure(app, "team", "owner", "chat", {"command": ["protocol-fixture"], "enabled": True}, worker_id="topic")
    process = Mock(stdout=[])
    process.poll.return_value = None
    launch = Mock(return_value=process)
    monkeypatch.setattr(bridges.subprocess, "Popen", launch)
    try:
        manager.tick()
        assert launch.call_args.kwargs["env"]["AW_WORKER"] == "topic"
        assert launch.call_args.kwargs["env"]["AW_BINDING"] == bindings["topic"]
    finally:
        manager.stop_all()


def test_precompact_uses_only_source_worker_summary_and_files(team, tmp_path):
    app, root, bindings = team
    for worker in bindings:
        app.checkpoint("team", "owner", worker + " summary", content=worker + " details",
                       binding=bindings[worker], worker_id=worker, checkpoint_id="business")
    write_bytes(root / "workers/default/unfinished.md", b"peer unsaved work")
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(json.dumps({"type": "session_meta", "payload": {"id": "session-topic"}}) + "\n",
                          encoding="utf-8")
    payload = {"hook_event_name": "PreCompact", "session_id": "session-topic", "turn_id": "one",
               "trigger": "auto", "transcript_path": str(transcript)}
    reply = compaction.run(app, payload, actor=("team", "owner", bindings["topic"]))
    assert "已保存" in reply["systemMessage"], reply
    point = app.checkpoints("team", "owner", worker_id="topic")[-1]
    saved = app.checkpoint_show("team", "owner", point["id"], worker_id="topic")
    assert "topic summary" in saved["record"]["summary"]
    assert "default summary" not in saved["record"]["summary"]
    assert not any(path.startswith("workers/default/") for path in saved["files"])
    assert (root / "workers/default/unfinished.md").read_bytes() == b"peer unsaved work"
    assert len(app.checkpoints("team", "owner", worker_id="default")) == 1
    assert compaction.run(app, payload, actor=("team", "owner", bindings["topic"])) == reply
