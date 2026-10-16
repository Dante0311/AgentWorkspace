"""Two real Workers of one Agent; isolated Git, without native model calls."""
from unittest.mock import Mock

import pytest

from agent_workspace import backend, layout, maintenance, web_courier
from agent_workspace.app import App
from agent_workspace.direct_messages import DirectMessages
from agent_workspace.messages import Messages
from agent_workspace.util import Conflict, Error, read_json, write_json


@pytest.fixture
def team(tmp_path):
    app = App(tmp_path / "home")
    app.workspace_init("sea", str(tmp_path / "sea.git"), worker_support=True)
    app.create("sea", "team")
    app.worker_create("sea", "team", "Topic", "Independent topic", worker_id="topic")
    bindings = {}
    for wid in ("default", "topic"):
        bid = app.reserve("sea", "team", worker_id=wid)["binding"]
        app.bind("sea", "team", bid, "native-" + wid, worker_id=wid)
        bindings[wid] = bid
    return app, bindings


def set_default(app, wid):
    revision = app.show("sea", "team")["revision"]
    app.worker_default("sea", "team", wid, revision)


def test_frozen_default_explicit_reply_wrong_worker_and_offline_archive(team, monkeypatch):
    app, ids = team
    messages = Messages(app)
    sent = messages.send("sea", "team", ids["topic"], "team", "first", request_id="frozen")
    assert sent["payload"]["from"]["worker"] == "topic"
    assert sent["payload"]["to"]["worker"] == "default"
    original = app.store("sea").snapshot().bytes(layout.shared_path(app.store("sea").snapshot(), "messages/frozen.json"))
    with monkeypatch.context() as pending:
        pending.setattr(messages, "reconcile", lambda operation_id: {"id": operation_id, "state": "pending"})
        messages.send("sea", "team", ids["topic"], "team", "original pending payload", request_id="pending")
    set_default(app, "topic")
    assert messages.operation("sea", "pending")["payload"]["to"]["worker"] == "default"
    assert messages.reconcile("pending")["payload"]["to"]["worker"] == "default"
    repeated = messages.send("sea", "team", ids["topic"], "team", "first", request_id="frozen")
    assert repeated["payload"] == sent["payload"]
    with pytest.raises(Conflict):
        messages.receive("sea", "team", ids["topic"], "frozen")
    with pytest.raises(Conflict):
        messages.send("sea", "team", ids["default"], "team", "forged", worker_id="topic")
    received = messages.receive("sea", "team", ids["default"], "frozen")
    assert received["publication"]["state"] == "published"
    assert messages.show("sea", "frozen")["ack"] == {"message_id": "frozen"}
    reply = messages.send("sea", "team", ids["default"], content="reply", reply_to="frozen", request_id="reply")
    assert reply["payload"]["to"]["worker"] == "topic"
    refs = messages.send("sea", "team", ids["default"], "team", "references only",
                         message_refs=["frozen", "reply"], request_id="references")
    assert refs["payload"]["to"]["worker"] == "topic" and "reply_to" not in refs["payload"]
    snap = app.store("sea").snapshot()
    assert snap.bytes(layout.shared_path(snap, "messages/frozen.json")) == original
    root = app.root("sea", "team")
    assert layout.instance_path(root, "messages/frozen.json", worker_id="default").exists()
    assert not layout.instance_path(root, "messages/frozen.json", worker_id="topic").exists()

    app.worker_create("sea", "team", "Offline", "Wait for explicit entry", worker_id="offline")
    offline = messages.send("sea", "team", ids["topic"], "team", "wait", to_worker="offline", request_id="offline")
    assert offline["state"] == "published"
    assert app.worker("sea", "team", "offline")["current"] is None
    app.worker_archive("sea", "team", "offline")
    with pytest.raises(Error):
        messages.send("sea", "team", ids["topic"], "team", "new", to_worker="offline", request_id="archived-new")
    assert not (app.home / "operations/archived-new.json").exists()
    assert messages.send("sea", "team", ids["topic"], "team", "wait", to_worker="offline", request_id="offline")["payload"] == offline["payload"]
    assert [row["id"] for row in messages.list("sea", "team", worker_id="offline")] == ["offline"]


class Adapter:
    def __init__(self):
        self.calls = []

    def status(self):
        return "idle"

    def notify(self, prompt, delivery):
        self.calls.append((prompt, delivery))


def test_fifo_and_ack_are_independent_for_workers_of_same_agent(team):
    app, ids = team
    messages = Messages(app)
    for wid in ("default", "topic"):
        for number in (1, 2):
            messages.send("sea", "team", ids["default"], "team", f"{wid}-{number}",
                          to_worker=wid, request_id=f"{wid}-{number}")
    adapters = {wid: Adapter() for wid in ids}
    for wid, bid in ids.items():
        result = messages.poll("sea", "team", bid, adapter=adapters[wid])
        assert result["message_id"] == f"{wid}-1"
        assert messages.poll("sea", "team", bid, adapter=adapters[wid])["state"] == "waiting_ack"
    with pytest.raises(Conflict):
        messages.receive("sea", "team", ids["topic"], "default-1")
    messages.receive("sea", "team", ids["default"], "default-1")
    assert messages.poll("sea", "team", ids["default"], adapter=adapters["default"])["message_id"] == "default-2"
    assert messages.poll("sea", "team", ids["topic"], adapter=adapters["topic"])["state"] == "waiting_ack"
    snap = app.store("sea").snapshot()
    assert snap.json(layout.shared_path(snap, "dispatch/team/default.json"))["message_id"] == "default-2"
    assert snap.json(layout.shared_path(snap, "dispatch/team/topic.json"))["message_id"] == "topic-1"
    assert len(adapters["topic"].calls) == 1


def test_native_history_freezes_actual_worker_without_formal_delivery(team):
    app, ids = team
    history = DirectMessages(app)
    recorded = history.record("sea", "team", ids["default"], "team", "sent natively",
                              to_worker="topic", request_id="native-one", result={"threadId": "native-topic"})
    assert recorded["recorded"] and recorded["record"]["to"]["worker"] == "topic"
    set_default(app, "topic")
    repeated = history.record("sea", "team", ids["default"], "team", "sent natively",
                              to_worker="topic", request_id="native-one")
    assert repeated == recorded
    assert history.record("sea", "team", ids["default"], "team", "unknown native target",
                          request_id="no-actual-target")["recorded"] is False
    reply = history.record("sea", "team", ids["topic"], content="native reply", reply_to="native-one",
                           request_id="native-reply")
    assert reply["record"]["to"]["worker"] == "default"
    assert len(history.list("sea", "team", worker_id="topic")) == 1
    assert Messages(app).list("sea", "team", unacked=True) == []
    assert not list((app.home / "operations").glob("native-*"))


def test_web_courier_connection_and_claim_use_original_worker(team):
    app, ids = team
    messages = Messages(app)
    connections = {}
    extension = "a" * 32
    for wid, bid in ids.items():
        connections[wid] = web_courier.connect(app, "sea", "team", bid,
            "https://chatgpt.com/c/native-" + wid, extension, "connection-" + wid, worker_id=wid)
        messages.send("sea", "team", ids["default"], "team", "for " + wid, to_worker=wid, request_id="web-" + wid)
    set_default(app, "topic")
    previews = {}
    for wid, conn in connections.items():
        previews[wid] = web_courier.handle(app, conn["connection_id"], conn["token"],
            "chrome-extension://" + extension, {"action": "get"})
        assert previews[wid]["message_id"] == "web-" + wid
        assert previews[wid]["notification"]["worker"] == wid
    conn = connections["default"]
    web_courier.handle(app, conn["connection_id"], conn["token"], "chrome-extension://" + extension,
        {"action": "begin", "message_id": "web-default", "attempt_id": "attempt-default",
         "binding": ids["default"], "target_url": conn["target_url"], "prompt_digest": previews["default"]["prompt_digest"]})
    other = connections["topic"]
    assert web_courier.handle(app, other["connection_id"], other["token"], "chrome-extension://" + extension,
                              {"action": "get"})["state"] == "ready"
    assert web_courier.status(app, conn["connection_id"])["worker"] == "default"
    assert web_courier.status(app, conn["connection_id"])["ack"] is None


def test_health_and_recovery_are_fixed_to_original_worker(team, monkeypatch):
    app, ids = team
    root = app.root("sea", "team")
    default_control = layout.local_path(root, "control.json", worker_id="default")
    topic_input = layout.local_path(root, "inputs/unknown.json", worker_id="topic")
    write_json(default_control, {"stop": ids["default"]})
    write_json(topic_input, {"id": "unknown", "binding": ids["topic"], "state": "outcome_unknown"})
    original = default_control.read_bytes(), topic_input.read_bytes()
    report = maintenance.doctor(app, "sea")
    assert report["local_observations"]["team#default"]["monitor_stop_requested"]
    assert not report["local_observations"]["team#topic"]["monitor_stop_requested"]
    assert any(row["code"] == "input_outcome_unknown" and row["worker"] == "topic" for row in report["issues"])
    recover = Mock(return_value={"state": "recovery_paused", "reason_code": "user_paused"})
    monkeypatch.setattr(backend, "recover", recover)
    args = {"expected_binding": ids["default"]}
    first = maintenance.repair(app, "sea", "team", "runtime-recover", "original-recovery", **args)
    set_default(app, "topic")
    repeated = maintenance.repair(app, "sea", "team", "runtime-recover", "original-recovery", **args)
    assert first["request"]["worker_id"] == repeated["request"]["worker_id"] == "default"
    assert repeated["state"] == "recovery_paused"
    recover.assert_called_once_with(app, "sea", "team", expected_binding=ids["default"], worker_id="default")
    with pytest.raises(Conflict):
        maintenance.repair(app, "sea", "team", "runtime-recover", "wrong-worker", worker_id="topic", **args)
    assert (default_control.read_bytes(), topic_input.read_bytes()) == original
    receipt = read_json(maintenance.folder(app, "sea") / "repairs/original-recovery.json")
    assert receipt["verification"]["runtime"]["worker"] == "default"


def test_explicit_old_mapping_keeps_protocol_bytes_and_original_manual_attempt(app):
    app.create("sea", "team")
    bid = app.reserve("sea", "team")["binding"]
    app.bind("sea", "team", bid, "original-session")
    messages = Messages(app)
    messages.send("sea", "team", bid, "team", "already acknowledged", request_id="old-ack")
    messages.receive("sea", "team", bid, "old-ack")
    messages.send("sea", "team", bid, "team", "original manual attempt", request_id="old-wait")
    preview = messages.preview_manual("sea", "team", bid)
    messages.claim_manual("sea", "team", bid, "old-wait", "original-attempt", preview["prompt_digest"])
    history = DirectMessages(app)
    history.record("sea", "team", bid, "team", "old native fact", request_id="old-native")
    app.checkpoint("sea", "team", "before explicit mapping", binding=bid)
    snap = app.store("sea").snapshot()
    originals = {path: snap.bytes(path) for path in snap.entries if any(part in path for part in
        ("messages/", "message-index/", "acks/", "dispatch/", "direct-messages/", "bindings/"))}
    app.workers_migrate("sea", "team", "daily", "explicit-worker-mapping", compatible_writers=["worker-v2"])
    app.worker_create("sea", "team", "Other", "Independent work", worker_id="other")
    other = app.reserve("sea", "team", worker_id="other")["binding"]
    app.bind("sea", "team", other, "other-session", worker_id="other")
    set_default(app, "other")
    assert messages.preview_manual("sea", "team", bid)["state"] == "waiting_ack"
    with pytest.raises(Conflict):
        messages.receive("sea", "team", other, "old-wait")
    assert messages.receive("sea", "team", bid, "old-ack")["already_acknowledged"]
    assert messages.send("sea", "team", bid, "team", "original manual attempt", request_id="old-wait")["state"] == "published"
    assert [row["id"] for row in history.list("sea", "team", worker_id="daily")] == ["old-native"]
    after = app.store("sea").snapshot()
    assert all(after.bytes(path) == raw for path, raw in originals.items())
