"""An uncertain original publication is observed, never submitted again."""
import pytest

from agent_workspace.gitstore import GitStore
from agent_workspace.messages import Messages
from agent_workspace.util import Error, Uncertain


@pytest.mark.parametrize("kind", ["message", "ack"])
@pytest.mark.parametrize("landed", [False, True])
def test_uncertain_original_publication_only_reads_back(pair, monkeypatch, kind, landed):
    app, bindings = pair
    messages = Messages(app)
    if kind == "ack":
        messages.send("sea", "alice", bindings["alice"], "bob", "original", request_id="uncertain")
    original_change = GitStore.change
    writes = []

    def lost(store, branch, changes, *args, **kwargs):
        writes.append(dict(changes))
        if landed:
            original_change(store, branch, changes, *args, **kwargs)
        raise Uncertain("Isolated original publication response unavailable")

    with monkeypatch.context() as fault:
        fault.setattr(GitStore, "change", lost)
        if kind == "message":
            receipt = messages.send("sea", "alice", bindings["alice"], "bob", "original", request_id="uncertain")
        else:
            receipt = messages.receive("sea", "bob", bindings["bob"], "uncertain")["publication"]
    assert receipt["state"] == "outcome_unknown" and len(writes) == 1
    original_payload = dict(receipt["payload"])
    before = app.store("sea").snapshot().revision

    def no_replay(*args, **kwargs):
        raise AssertionError("An uncertain original publication cannot be submitted again")

    monkeypatch.setattr(GitStore, "change", no_replay)
    if not landed:
        def unreadable(*args, **kwargs):
            raise Error("Isolated original publication readback unavailable")

        with monkeypatch.context() as fault:
            fault.setattr(GitStore, "snapshot", unreadable)
            assert messages.reconcile(receipt["id"])["state"] == "outcome_unknown"
    for _ in range(2):
        observed = messages.reconcile(receipt["id"])
        assert observed["state"] == ("published" if landed else "outcome_unknown")
        assert observed["payload"] == original_payload
    assert app.store("sea").snapshot().revision == before
