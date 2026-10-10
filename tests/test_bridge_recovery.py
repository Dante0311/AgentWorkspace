"""Isolated channel event ordering; no channel process or native session is started."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent_workspace import bridges, runtime
from agent_workspace.util import Conflict, Unavailable, digest, read_json, write_json


@pytest.fixture
def local_bridge(tmp_path):
    app = SimpleNamespace(
        home=tmp_path / "home",
        root=Mock(return_value=tmp_path),
        agent=Mock(return_value={"current": "b-current"}),
        require_binding=Mock(return_value=({}, {})),
    )
    manager = bridges.BridgeManager(app, "sea", "alice", "b-current", tmp_path)
    return app, manager


def input_event(identifier, text):
    return {"event": "input", "id": identifier, "sender": "tester", "target": "test-room", "text": text}


def input_id(event):
    return "i" + digest(("chat:" + event["id"]).encode())[:40]


@pytest.mark.parametrize("failed_read", [2, 3])
def test_read_failure_keeps_original_event_before_later_input_and_receipt(local_bridge, failed_read):
    app, manager = local_bridge
    first, second = input_event("first", "first input"), input_event("second", "second input")
    send = {"id": "send-one", "binding": "b-current", "bridge": "chat", "state": "dispatching",
            "target": "test-room", "text": "explicit reply"}
    write_json(manager.root / ".aw-local/bridge-sends/send-one.json", send)
    manager.events.put(("chat", first))
    manager.events.put(("chat", second))
    manager.events.put(("chat", {"event": "sent", "id": "send-one", "receipt": "fixture-receipt"}))
    reads = 0

    def authority_read(*args, **kwargs):
        nonlocal reads
        reads += 1
        if reads == failed_read:
            raise Unavailable("isolated shared read failure")
        return {}, {}

    app.require_binding.side_effect = authority_read
    with pytest.raises(Unavailable):
        manager.tick()
    assert not list((manager.root / ".aw-local/inputs").glob("*.json"))
    assert read_json(manager.root / ".aw-local/bridge-sends/send-one.json") == send

    manager.tick()
    records = [read_json(manager.root / ".aw-local/inputs" / f"{input_id(event)}.json") for event in (first, second)]
    assert all(records)
    assert [record["binding"] for record in records] == ["b-current", "b-current"]
    assert records[0]["sequence"] < records[1]["sequence"]
    assert records[0]["text"].endswith("first input") and records[1]["text"].endswith("second input")
    receipt = read_json(manager.root / ".aw-local/bridge-sends/send-one.json")
    assert receipt["state"] == "sent" and receipt["receipt"] == "fixture-receipt"
    assert read_json(manager.root / "channels/chat/sent/send-one.json") == receipt
    assert manager.events.empty()


@pytest.mark.parametrize("native_state", ["submitted", "outcome_unknown"])
def test_retry_only_fills_missing_enqueue_and_preserves_existing_input(local_bridge, monkeypatch, native_state):
    app, manager = local_bridge
    event = input_event("original", "original input")
    manager.events.put(("chat", event))
    enqueue = runtime.queue_input
    attempts = []

    def lost_enqueue_response(*args, **kwargs):
        result = enqueue(*args, **kwargs)
        attempts.append(kwargs["request_id"])
        if len(attempts) == 1:
            result.update(state=native_state, result={"turn": {"id": "original-turn"}})
            write_json(manager.root / ".aw-local/inputs" / f"{result['id']}.json", result)
            raise Unavailable("isolated response lost after local enqueue")
        return result

    monkeypatch.setattr(runtime, "queue_input", lost_enqueue_response)
    with pytest.raises(Unavailable):
        manager.tick()
    path = manager.root / ".aw-local/inputs" / f"{input_id(event)}.json"
    saved = path.read_bytes()
    assert manager.events.empty()

    manager.tick()
    manager.events.put(("chat", event))
    manager.tick()
    assert path.read_bytes() == saved
    assert attempts == [input_id(event)] * 3
    assert read_json(manager.root / ".aw-local/input-sequence.json") == 1
    assert len(list(path.parent.glob("*.json"))) == 1


def test_bridge_enqueue_pins_the_original_binding(local_bridge):
    app, manager = local_bridge
    manager.events.put(("chat", input_event("original", "original input")))
    # Ownership changed between the event's old-entry check and enqueue's fresh read.
    app.agent.return_value = {"current": "b-successor"}
    with pytest.raises(Conflict):
        manager.tick()
    assert not list((manager.root / ".aw-local/inputs").glob("*.json"))
