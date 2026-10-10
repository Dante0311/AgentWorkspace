import json

import pytest

from agent_workspace.gitstore import Snapshot
from agent_workspace.messages import Messages
from agent_workspace.util import RetryableRead


class Adapter:
    supports_insert = True

    def __init__(self):
        self.calls = []

    def status(self):
        return "idle"

    def notify(self, prompt, delivery):
        self.calls.append((prompt, delivery))


@pytest.mark.parametrize("with_refs", [True, False])
def test_notification_preserves_complete_stored_json_and_unknown_fields(pair, with_refs):
    app, bindings = pair
    messages = Messages(app)
    result = messages.send("sea", "alice", bindings["alice"], "bob",
                           '中文\n"引号"\n```json\n{"a": 1}\n```\n<aw-message-json>', request_id="raw-message")
    body = {**result["payload"], "future_field": {"original": ["未知", 17]}}
    if not with_refs:
        body.pop("message_refs")
    raw = ("  " + json.dumps(body, ensure_ascii=False, indent=3) + " \n\n").encode("utf-8")
    app.store("sea").change("main", {"messages/raw-message.json": raw}, {}, "isolated formatting fixture")
    adapter = Adapter()
    assert messages.poll("sea", "bob", bindings["bob"], adapter=adapter)["state"] == "notified_waiting_ack"
    prompt = adapter.calls[0][0]
    stored = prompt.split("<aw-message-json>\n", 1)[1].rsplit("\n</aw-message-json>", 1)[0]
    assert stored.encode("utf-8") == raw
    assert json.loads(stored) == body
    assert str(app.home) not in prompt and "执行参数数组" not in prompt
    assert messages.poll("sea", "bob", bindings["bob"], adapter=adapter)["state"] == "waiting_ack"
    assert len(adapter.calls) == 1


@pytest.mark.parametrize("damaged", [None, b"invalid JSON", b"[]"])
def test_missing_or_damaged_body_keeps_index_and_ack_path(pair, damaged):
    app, bindings = pair
    messages = Messages(app)
    messages.send("sea", "alice", bindings["alice"], "bob", "original", request_id="bad-body")
    store = app.store("sea")
    store.change("main", {"messages/bad-body.json": damaged}, {}, "isolated body fault")
    index = store.snapshot().bytes("message-index/bad-body.json")
    adapter = Adapter()
    assert messages.poll("sea", "bob", bindings["bob"], adapter=adapter)["state"] == "notified_waiting_ack"
    prompt = adapter.calls[0][0]
    assert "<aw-message-json>" not in prompt
    assert prompt.split("<aw-message-index-json>\n", 1)[1].rsplit("\n</aw-message-index-json>", 1)[0].encode() == index
    received = messages.receive("sea", "bob", bindings["bob"], "bad-body")
    assert received["publication"]["state"] == "published"
    assert store.snapshot().json("acks/bad-body.json") == {"message_id": "bad-body"}
    assert messages.poll("sea", "bob", bindings["bob"], adapter=adapter)["state"] == "empty"


def test_temporary_body_read_failure_does_not_claim_notification_attempt(pair, monkeypatch):
    app, bindings = pair
    messages = Messages(app)
    messages.send("sea", "alice", bindings["alice"], "bob", "original", request_id="temporary")
    read = Snapshot.bytes

    def temporary_failure(snapshot, path):
        if path == "messages/temporary.json":
            raise RetryableRead("isolated temporary blob read")
        return read(snapshot, path)

    adapter = Adapter()
    monkeypatch.setattr(Snapshot, "bytes", temporary_failure)
    with pytest.raises(RetryableRead):
        messages.poll("sea", "bob", bindings["bob"], adapter=adapter)
    assert not adapter.calls
    assert app.store("sea").snapshot().bytes("dispatch/bob.json") is None
    assert app.store("sea").snapshot().bytes("acks/temporary.json") is None
