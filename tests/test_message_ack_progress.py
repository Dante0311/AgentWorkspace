"""A published ACK is normal queue progress, including at the dispatch CAS boundary."""
from unittest.mock import Mock

import pytest

from agent_workspace import layout
from agent_workspace.app import App
from agent_workspace.gitstore import GitStore
from agent_workspace.messages import Messages
from agent_workspace.util import encode


@pytest.fixture(params=["legacy", "message-branch"])
def inbox(tmp_path, request):
    app = App(tmp_path / "home")
    address = tmp_path / "sea.git"
    if request.param == "legacy":
        GitStore.initialize(address)
        store = GitStore(str(address), app.home)
        store.branch("main", {"workspace.json": encode({"schema": 1, "name": "sea", "locator": "local:sea",
                                                        "friends": {}, "projects": {}})})
        app.workspace_connect("sea", str(address))
        sender = receiver = app.create("sea", "team")["id"]
        binding = app.reserve("sea", receiver)["binding"]
        app.bind("sea", receiver, binding, "isolated-receiver")
        sender_binding = binding
        target = {}
    else:
        app.workspace_init("sea", str(address))
        sender = receiver = app.create("sea", "team")["id"]
        sender_binding = app.reserve("sea", sender, worker_id="default")["binding"]
        app.bind("sea", sender, sender_binding, "isolated-sender", worker_id="default")
        app.worker_create("sea", receiver, "Topic", "Isolated ACK recipient", worker_id="topic")
        binding = app.reserve("sea", receiver, worker_id="topic")["binding"]
        app.bind("sea", receiver, binding, "isolated-receiver", worker_id="topic")
        target = {"to_worker": "topic"}
    messages = Messages(app)
    for identifier in ("first", "next"):
        assert messages.send("sea", sender, sender_binding, receiver, identifier,
                             request_id=identifier, **target)["state"] == "published"
    return app, messages, receiver, binding


@pytest.mark.parametrize("window", ["refresh", "publication"])
def test_ack_during_notification_retry_is_progress_and_next_message_still_flows(inbox, monkeypatch, window):
    app, messages, receiver, binding = inbox
    store = app.store("sea")
    adapter = Mock()
    adapter.status.return_value = "idle"
    adapter.notify.return_value = {}
    assert messages.poll("sea", receiver, binding, adapter=adapter)["message_id"] == "first"
    before = store.message_snapshot()
    dispatch = layout.shared_path(before.messages, "dispatch/team/topic.json" if before.branch == "aw-messages"
                                  else "dispatch/team.json")
    original_dispatch = before.messages.bytes(dispatch)
    original_message = before.messages.bytes(layout.shared_path(before.messages, "messages/first.json"))
    acknowledged = []

    def acknowledge():
        acknowledged.append("first")
        assert messages.receive("sea", receiver, binding, "first")["publication"]["state"] == "published"

    if window == "refresh":
        def status():
            acknowledge()
            return "idle"
        adapter.status.side_effect = status
    else:
        change = GitStore.message_change

        def publish(store, state, changes, expected, description, **kwargs):
            if description == "Claim notification attempt" and not acknowledged:
                acknowledge()
            return change(store, state, changes, expected, description, **kwargs)
        monkeypatch.setattr(GitStore, "message_change", publish)

    result = messages.poll("sea", receiver, binding, adapter=adapter, retry_seconds=0)
    assert result == {"state": "acknowledged", "message_id": "first"}
    assert acknowledged == ["first"] and adapter.notify.call_count == 1
    after = store.message_snapshot()
    assert after.messages.bytes(dispatch) == original_dispatch
    assert after.messages.json(layout.shared_path(after.messages, "acks/first.json")) == {"message_id": "first"}
    adapter.status.side_effect = None
    assert messages.poll("sea", receiver, binding, adapter=adapter)["message_id"] == "next"
    assert adapter.notify.call_count == 2
    assert "next" in adapter.notify.call_args.args[0]
    final = store.message_snapshot()
    assert final.messages.bytes(layout.shared_path(final.messages, "messages/first.json")) == original_message
    assert {item["id"] for item in messages.list("sea")} == {"first", "next"}
    assert app.require_binding("sea", receiver, binding)[1]["phase"] == "active"
    if final.branch == "aw-messages":
        assert final.main.revision == before.main.revision
