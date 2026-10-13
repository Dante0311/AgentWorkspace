"""Authority changes use actual local Git; native observations remain fixtures."""
import pytest

from agent_workspace.app import App
from agent_workspace.cli import parser
from agent_workspace.commands import execute
from agent_workspace.util import Conflict, Error, RetryableRead, Uncertain, write_json


@pytest.fixture
def running_agent(app, monkeypatch):
    resources = app._resources
    monkeypatch.setattr(app, "_resources", lambda: {**resources(), "AGENTS.md": b"Responsibilities\n"})
    app.create("sea", "alice")
    root = app.root("sea", "alice")
    (root / "notes.md").write_text("saved", encoding="utf-8")
    checkpoint = app.checkpoint("sea", "alice", "saved materials", checkpoint_id="saved-point")
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "fixture-old-session")
    return app, binding, checkpoint["id"]


def take(app, binding, checkpoint):
    return execute(app, "agent.takeover", {"workspace": "sea", "agent_id": "alice",
                                           "binding": binding, "checkpoint": checkpoint, "confirm": True})


def test_takeover_revokes_aw_rights_without_claiming_native_stop(running_agent, tmp_path):
    app, old, checkpoint = running_agent
    root = app.root("sea", "alice")
    (root / "notes.md").write_text("unsaved old-copy work", encoding="utf-8")
    write_json(root / ".agentworkspace/local/runtime/status.json", {"binding": old, "session": "fixture-old-session", "state": "busy"})
    store = app.store("sea")
    before_files = store.head(app.agent("sea", "alice")["branch"])
    result = take(app, old, checkpoint)
    assert result["execution_right_revoked"] is True
    assert result["native_stop_confirmed"] is False
    assert result["native_state"] == "not_observed"
    assert result["starts_new_session"] is False
    assert app.agent("sea", "alice")["current"] is None
    old_entry = store.snapshot().json(f".agentworkspace/bindings/{old}.json")
    assert old_entry["phase"] == "revoked"
    assert "stopped_at" not in old_entry
    assert app.show("sea", "alice")["copies"][0]["runtime"]["state"] == "busy"
    assert (root / "notes.md").read_text(encoding="utf-8") == "unsaved old-copy work"
    assert store.head(app.agent("sea", "alice")["branch"]) == before_files
    with pytest.raises(Conflict):
        execute(app, "asset.write", {"path": "forbidden.md", "content": "old entry"}, actor=("sea", "alice", old))
    assert not (root / "forbidden.md").exists()
    target = tmp_path / "new-copy"
    app.connect_agent("sea", "alice", target)
    new = app.reserve("sea", "alice", target)["binding"]
    assert app.agent("sea", "alice")["current"] == new
    assert (target / "notes.md").read_text(encoding="utf-8") == "saved"
    with pytest.raises(Conflict):
        app.reserve("sea", "alice")


def test_original_takeover_result_does_not_revoke_a_successor(running_agent):
    app, old, checkpoint = running_agent
    original = take(app, old, checkpoint)
    current = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", current, "fixture-new-session")
    before = app.store("sea").head("main")
    repeated = take(app, old, checkpoint)
    assert repeated["handoff"]["id"] == original["handoff"]["id"]
    assert repeated["handoff"]["consumed_by"] == current
    assert app.agent("sea", "alice")["current"] == current
    assert app.store("sea").head("main") == before


def test_takeover_requires_user_confirmation_and_refuses_agent_actor(running_agent):
    app, binding, checkpoint = running_agent
    before = app.store("sea").head("main")
    with pytest.raises(Error):
        app.takeover("sea", "alice", binding, checkpoint)
    with pytest.raises(Error):
        execute(app, "agent.takeover", {"binding": binding, "checkpoint": checkpoint, "confirm": True},
                actor=("sea", "alice", binding))
    assert app.store("sea").head("main") == before
    args = parser().parse_args(["agent", "takeover", "alice", "--binding", binding,
                               "--checkpoint", checkpoint, "--confirm"])
    assert args.confirm is True


def test_takeover_rejects_another_agents_checkpoint(running_agent):
    app, binding, _ = running_agent
    app.create("sea", "bob")
    point = app.checkpoint("sea", "bob", "other", checkpoint_id="other-point")
    before = app.store("sea").head("main")
    with pytest.raises(Error):
        take(app, binding, point["id"])
    assert app.store("sea").head("main") == before
    assert app.agent("sea", "alice")["current"] == binding


def test_normal_stop_wins_a_race_without_second_handoff(running_agent, tmp_path, monkeypatch):
    app, binding, checkpoint = running_agent
    app.stop("sea", "alice", binding, checkpoint)
    peer = App(tmp_path / "peer")
    peer.workspace_connect("peer", str(tmp_path / "sea.git"))
    store = app.store("sea")
    change = store.change

    def release_before_takeover(branch, changes, expected, message, **kwargs):
        if message == "User takeover":
            peer.finish_stop("peer", "alice", binding, observed_idle=True)
        return change(branch, changes, expected, message, **kwargs)

    monkeypatch.setattr(store, "change", release_before_takeover)
    with pytest.raises(Conflict):
        take(app, binding, checkpoint)
    snap = store.snapshot()
    assert snap.json(f".agentworkspace/bindings/{binding}.json")["phase"] == "released"
    handoffs = [path for path in snap.entries if path.startswith(".agentworkspace/handoffs/")]
    assert len(handoffs) == 1
    assert "forced" not in snap.json(handoffs[0])


def test_lost_takeover_reply_reads_the_original_publication(running_agent, monkeypatch):
    app, binding, checkpoint = running_agent
    store = app.store("sea")
    change = store.change
    calls = []

    def lost_reply(*args, **kwargs):
        calls.append(args)
        change(*args, **kwargs)
        raise Uncertain("fixture reply lost after real Git publication")

    monkeypatch.setattr(store, "change", lost_reply)
    result = take(app, binding, checkpoint)
    assert result["execution_right_revoked"] is True
    assert len(calls) == 1
    assert app.agent("sea", "alice")["current"] is None


def test_unknown_takeover_is_not_republished_and_later_original_can_be_read(running_agent, monkeypatch):
    app, binding, checkpoint = running_agent
    store = app.store("sea")
    change = store.change
    calls = []

    def pending_publication(*args, **kwargs):
        calls.append((args, kwargs))
        raise Uncertain("fixture original publication still pending")

    monkeypatch.setattr(store, "change", pending_publication)
    with pytest.raises(Uncertain):
        take(app, binding, checkpoint)
    with pytest.raises(Uncertain):
        take(app, binding, checkpoint)
    assert len(calls) == 1
    assert app.agent("sea", "alice")["current"] == binding
    args, kwargs = calls[0]
    change(*args, **kwargs)
    result = take(app, binding, checkpoint)
    assert result["execution_right_revoked"] is True
    assert len(calls) == 1


def test_result_read_failure_preserves_unknown_until_original_is_read(running_agent, monkeypatch):
    app, binding, checkpoint = running_agent
    store = app.store("sea")
    change, snapshot = store.change, store.snapshot
    published = False

    def lost_reply(*args, **kwargs):
        nonlocal published
        change(*args, **kwargs)
        published = True
        raise Uncertain("fixture lost reply")

    def unreadable_result(*args, **kwargs):
        if published:
            raise RetryableRead("fixture result read unavailable")
        return snapshot(*args, **kwargs)

    with monkeypatch.context() as failure:
        failure.setattr(store, "change", lost_reply)
        failure.setattr(store, "snapshot", unreadable_result)
        with pytest.raises(Uncertain):
            take(app, binding, checkpoint)
    assert take(app, binding, checkpoint)["execution_right_revoked"] is True
    assert app.agent("sea", "alice")["current"] is None
