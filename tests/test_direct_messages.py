"""Optional native history uses real isolated Git, without a delivery adapter."""
import pytest

from agent_workspace.commands import execute
from agent_workspace.direct_messages import DirectMessages
from agent_workspace.messages import Messages
from agent_workspace.util import Conflict, Uncertain, encode


def test_history_and_optional_receipt_never_enter_formal_delivery(pair):
    app, bindings = pair
    history = DirectMessages(app)
    before = app.store("sea").snapshot()
    result = execute(app, "direct-message.record", {
        "to": "bob", "content": "原生正文\n中文", "request_id": "direct-one",
        "result": {"threadId": "native-bob"}}, actor=("sea", "alice", bindings["alice"]))
    assert result["recorded"] is True
    record = result["record"]
    assert record["type"] == "codex" and "receipt" not in record
    assert execute(app, "direct-message.list", {"workspace": "sea"}) == [record]
    assert history.list("sea", "bob") == [record]
    assert history.list("sea", "alice", "out") == [record]
    assert history.list("sea", "alice") == []
    assert history.show("sea", "direct-one") == {"record": record}
    assert history.show("sea", "absent") == {"record": None}
    after = app.store("sea").snapshot()
    assert set(after.entries) - set(before.entries) == {"direct-messages/direct-one.json"}
    assert all(after.entries[path] == revision for path, revision in before.entries.items())
    assert Messages(app).list("sea", unacked=True) == []
    assert Messages(app).poll("sea", "bob", bindings["bob"])["state"] == "empty"

    revision = after.revision
    repeated = history.record("sea", "alice", bindings["alice"], "bob", record["content"],
                              request_id=record["id"], result=record["result"])
    assert repeated == result and app.store("sea").snapshot().revision == revision
    enriched = history.record("sea", "alice", bindings["alice"], "bob", record["content"],
                              request_id=record["id"], receipt={"content": "实际回执"})
    assert enriched["record"]["created_at"] == record["created_at"]
    assert enriched["record"]["result"] == record["result"]
    assert enriched["record"]["receipt"] == {"content": "实际回执"}
    conflict = history.record("sea", "alice", bindings["alice"], "bob", "changed",
                              request_id=record["id"])
    assert conflict["recorded"] is False and conflict["code"] == "conflict"
    assert history.show("sea", record["id"])["record"] == enriched["record"]
    assert Messages(app).list("sea") == []


@pytest.mark.parametrize("landed", [False, True])
def test_unknown_record_write_only_reads_original_history(pair, monkeypatch, landed):
    app, bindings = pair
    store = app.store("sea")
    original_change = store.change
    attempts = []

    def unknown_write(*args, **kwargs):
        attempts.append(args)
        if landed:
            original_change(*args, **kwargs)
        raise Uncertain("Native-history write response was lost.")

    monkeypatch.setattr(store, "change", unknown_write)
    monkeypatch.setattr(app, "store", lambda workspace: store)
    history = DirectMessages(app)
    result = history.record("sea", "alice", bindings["alice"], "bob", "sent once",
                            request_id="direct-unknown", result={"state": "outcome_unknown"})
    assert result["recorded"] is None and result["record_id"] == "direct-unknown"
    observed = history.show("sea", "direct-unknown")["record"]
    assert bool(observed) is landed
    assert len(attempts) == 1
    assert Messages(app).list("sea", unacked=True) == []
    assert not list((app.home / "operations").glob("direct-unknown*"))


def test_logging_failure_is_optional_but_revoked_or_forged_writer_cannot_write(pair, monkeypatch):
    app, bindings = pair
    history = DirectMessages(app)
    before = app.store("sea").snapshot()
    with monkeypatch.context() as scoped:
        store = app.store("sea")
        def unavailable(*args, **kwargs):
            raise OSError("History storage is unavailable.")
        scoped.setattr(store, "change", unavailable)
        scoped.setattr(app, "store", lambda workspace: store)
        failed = history.record("sea", "alice", bindings["alice"], "bob", "already sent",
                                request_id="direct-unavailable")
    assert failed["recorded"] is False
    assert app.store("sea").snapshot().revision == before.revision
    with pytest.raises(Conflict):
        execute(app, "direct-message.record", {
            "agent_id": "bob", "binding": bindings["bob"], "to": "alice", "content": "forged"},
            actor=("sea", "alice", bindings["alice"]))
    agent = before.json("agents/alice.json")
    agent["current"] = None
    app.store("sea").change("main", {"agents/alice.json": encode(agent)},
                            {"agents/alice.json": before.entries["agents/alice.json"]}, "Revoke test writer")
    revoked = history.record("sea", "alice", bindings["alice"], "bob", "late history",
                             request_id="direct-revoked")
    assert revoked["recorded"] is False
    assert history.list("sea") == []


def test_direct_history_preserves_existing_formal_message_and_ack(pair):
    app, bindings = pair
    formal = Messages(app)
    formal.send("sea", "alice", bindings["alice"], "bob", "formal", request_id="formal-one")
    before = app.store("sea").snapshot()
    history = DirectMessages(app)
    assert history.record("sea", "alice", bindings["alice"], "bob", "native",
                          request_id="direct-beside-formal")["recorded"] is True
    assert formal.list("sea", "bob", unacked=True)[0]["id"] == "formal-one"
    after = app.store("sea").snapshot()
    assert after.bytes("messages/formal-one.json") == before.bytes("messages/formal-one.json")
    assert after.bytes("message-index/formal-one.json") == before.bytes("message-index/formal-one.json")
    assert after.bytes("acks/formal-one.json") is None
    received = formal.receive("sea", "bob", bindings["bob"], "formal-one")
    assert received["message"]["content"] == "formal"
    assert formal.show("sea", "formal-one")["ack"] == {"message_id": "formal-one"}
    assert len(history.list("sea")) == 1


def test_entry_revoked_during_record_publication_cannot_publish(pair, monkeypatch):
    app, bindings = pair
    store = app.store("sea")
    original_change = store.change

    def revoke_before_write(*args, **kwargs):
        snap = store.snapshot()
        agent = snap.json("agents/alice.json")
        agent["current"] = None
        original_change("main", {"agents/alice.json": encode(agent)},
                        {"agents/alice.json": snap.entries["agents/alice.json"]}, "Revoke before record write")
        return original_change(*args, **kwargs)

    monkeypatch.setattr(store, "change", revoke_before_write)
    result = DirectMessages(app).record("sea", "alice", bindings["alice"], "bob", "already sent",
                                        request_id="direct-race")
    assert result["recorded"] is False and result["code"] == "conflict"
    assert store.snapshot().bytes("direct-messages/direct-race.json") is None
    assert Messages(app).list("sea") == []
