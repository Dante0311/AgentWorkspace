"""Core stop conditions use real local Git; no native idle is claimed here."""
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from agent_workspace.gitstore import GitStore
from agent_workspace.util import Conflict, Error, RetryableRead, Uncertain, encode


@pytest.fixture
def owner(app):
    app.create("sea", "alice")
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "fixture-session")
    point = app.checkpoint("sea", "alice", "fixture stop", binding=binding)
    return app, binding, point["id"]


@pytest.fixture
def stopping(owner):
    app, binding, checkpoint = owner
    app.stop("sea", "alice", binding, checkpoint)
    return owner


def finish(owner):
    app, binding, checkpoint = owner
    return app.finish_stop("sea", "alice", binding, observed_idle=True,
                           expected_controller=None, expected_checkpoint=checkpoint,
                           expected_session="fixture-session")


def assert_still_owned(owner):
    app, binding, _ = owner
    snap = app.store("sea").snapshot()
    assert snap.json("agents/alice.json")["current"] == binding
    assert snap.json(f"bindings/{binding}.json")["phase"] == "stopping"
    assert f"handoffs/h{binding[1:]}.json" not in snap.entries


def test_stop_repeat_preserves_original_request(owner):
    app, binding, checkpoint = owner
    second = app.checkpoint("sea", "alice", "another point", binding=binding)["id"]
    first = app.stop("sea", "alice", binding, checkpoint)
    before = app.store("sea").snapshot().revision
    assert app.stop("sea", "alice", binding, checkpoint) == first
    with pytest.raises(Conflict):
        app.stop("sea", "alice", binding, second)
    assert app.store("sea").snapshot().revision == before
    assert_still_owned(owner)


def test_busy_observation_never_releases(stopping):
    app, binding, _ = stopping
    with pytest.raises(Conflict):
        app.finish_stop("sea", "alice", binding, observed_idle=False)
    assert_still_owned(stopping)


@pytest.mark.parametrize("field,value", [("controller", "another controller"),
                                        ("checkpoint", "another-checkpoint"), ("session", "another-session")])
def test_observation_must_match_saved_request(stopping, field, value):
    app, binding, checkpoint = stopping
    expected = {"expected_controller": None, "expected_checkpoint": checkpoint, "expected_session": "fixture-session"}
    expected["expected_" + field] = value
    with pytest.raises(Conflict):
        app.finish_stop("sea", "alice", binding, observed_idle=True, **expected)
    assert_still_owned(stopping)


@pytest.mark.parametrize("damage", ["missing", "wrong-agent", "missing-material", "foreign-material"])
def test_checkpoint_must_belong_and_remain_available(stopping, damage):
    app, _, checkpoint = stopping
    store = app.store("sea")
    snap = store.snapshot()
    path = f"checkpoints/alice/{checkpoint}.json"
    pointer = snap.json(path)
    if damage == "missing":
        content = None
    else:
        if damage == "wrong-agent":
            pointer["agent"] = "another-agent"
        elif damage == "foreign-material":
            pointer["revision"] = store.commit(pointer["revision"], {
                ".aw/identity.json": encode({"agent": "another-agent", "workspace": snap.json("workspace.json")["locator"]})
            }, "foreign fixture material with the same checkpoint ID")
        else:
            pointer["revision"] = store.commit(pointer["revision"], {pointer["path"]: None}, "missing fixture material")
        content = encode(pointer)
    store.change("main", {path: content}, {path: snap.entries[path]}, "damaged fixture checkpoint")
    with pytest.raises(Error):
        finish(stopping)
    assert_still_owned(stopping)


@pytest.mark.parametrize("stage", ["Prepare handoff", "Release entry"])
def test_changed_checkpoint_cannot_be_committed_from_old_snapshot(owner, monkeypatch, stage):
    app, binding, checkpoint = owner
    if stage == "Release entry":
        app.stop("sea", "alice", binding, checkpoint)
    change = GitStore.change
    raced = []
    def race(store, branch, changes, expected, message, **kwargs):
        if message == stage and not raced:
            raced.append(True)
            snap = store.snapshot()
            path = f"checkpoints/alice/{checkpoint}.json"
            pointer = snap.json(path)
            pointer["excluded"] = ["fixture peer revision"]
            change(store, branch, {path: encode(pointer)}, {path: snap.entries[path]}, "fixture peer change")
        return change(store, branch, changes, expected, message, **kwargs)
    monkeypatch.setattr(GitStore, "change", race)
    with pytest.raises(Conflict):
        if stage == "Prepare handoff":
            app.stop("sea", "alice", binding, checkpoint)
        else:
            finish(owner)
    snap = app.store("sea").snapshot()
    assert snap.json("agents/alice.json")["current"] == binding
    assert snap.json(f"bindings/{binding}.json")["phase"] == ("active" if stage == "Prepare handoff" else "stopping")
    assert f"handoffs/h{binding[1:]}.json" not in snap.entries


def test_lost_publication_reply_returns_one_saved_handoff(stopping, monkeypatch):
    app, binding, _ = stopping
    publish = GitStore.publish
    attempts = []
    def lose_reply(store, branch, commit, expected):
        attempts.append(commit)
        publish(store, branch, commit, expected)
        raise Uncertain("fixture reply lost after actual local Git publication")
    monkeypatch.setattr(GitStore, "publish", lose_reply)
    result = finish(stopping)
    assert finish(stopping) == result
    assert len(attempts) == 1
    snap = app.store("sea").snapshot()
    assert snap.json("agents/alice.json")["current"] is None
    assert snap.json(f"bindings/{binding}.json")["phase"] == "released"
    assert len([p for p in snap.entries if p.startswith("handoffs/")]) == 1


def test_failed_result_lookup_is_unknown_not_retryable(stopping, monkeypatch):
    publish_attempts = []
    snapshot = GitStore.snapshot
    def lose_reply(store, *args):
        publish_attempts.append(args)
        raise Uncertain("fixture publication unknown")
    def unavailable(store, *args, **kwargs):
        if publish_attempts:
            raise RetryableRead("fixture read unavailable")
        return snapshot(store, *args, **kwargs)
    with monkeypatch.context() as fault:
        fault.setattr(GitStore, "publish", lose_reply)
        fault.setattr(GitStore, "snapshot", unavailable)
        with pytest.raises(Uncertain):
            finish(stopping)
    assert len(publish_attempts) == 1
    assert_still_owned(stopping)


@pytest.mark.parametrize("result_record", ["binding", "handoff"])
def test_failed_result_blob_read_is_unknown_not_retryable(stopping, monkeypatch, result_record):
    app, binding, _ = stopping
    path = f"bindings/{binding}.json" if result_record == "binding" else f"handoffs/h{binding[1:]}.json"
    publish, snapshot, blob = GitStore.publish, GitStore.snapshot, GitStore.blob
    attempts, unreadable = [], []

    def lose_reply(store, branch, commit, expected):
        attempts.append(commit)
        publish(store, branch, commit, expected)
        unreadable.append(snapshot(store).entries[path])
        raise Uncertain("fixture reply lost after actual local Git publication")

    def unavailable(store, sha):
        if sha in unreadable:
            raise RetryableRead("fixture published result content unavailable")
        return blob(store, sha)

    with monkeypatch.context() as fault:
        fault.setattr(GitStore, "publish", lose_reply)
        fault.setattr(GitStore, "blob", unavailable)
        with pytest.raises(Uncertain):
            finish(stopping)

    assert len(attempts) == 1
    snap = app.store("sea").snapshot()
    assert snap.json("agents/alice.json")["current"] is None
    assert snap.json(f"bindings/{binding}.json")["phase"] == "released"
    assert len([p for p in snap.entries if p.startswith("handoffs/")]) == 1


def test_concurrent_observers_publish_one_handoff(stopping, monkeypatch):
    app, binding, _ = stopping
    read_checkpoint = app._read_checkpoint
    ready = threading.Barrier(2)
    def read(*args):
        result = read_checkpoint(*args)
        ready.wait(timeout=30)
        return result
    monkeypatch.setattr(app, "_read_checkpoint", read)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: finish(stopping), range(2)))
    assert results[0] == results[1]
    snap = app.store("sea").snapshot()
    assert snap.json(f"bindings/{binding}.json")["phase"] == "released"
    assert len([p for p in snap.entries if p.startswith("handoffs/")]) == 1


def test_released_repeat_does_not_change_the_successor(stopping):
    app, old, _ = stopping
    result = finish(stopping)
    new = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", new, "fixture-successor")
    before = app.store("sea").snapshot().revision
    assert finish(stopping)["id"] == result["id"]
    assert app.store("sea").snapshot().revision == before
    assert app.agent("sea", "alice")["current"] == new
    with pytest.raises(Conflict):
        app.require_binding("sea", "alice", old)
    with pytest.raises(Conflict):
        app.finish_stop("sea", "alice", old, observed_idle=True, expected_controller="wrong")


def test_released_entry_requires_its_matching_handoff(stopping):
    app, binding, _ = stopping
    finish(stopping)
    store = app.store("sea")
    snap = store.snapshot()
    path = f"handoffs/h{binding[1:]}.json"
    store.change("main", {path: None}, {path: snap.entries[path]}, "missing fixture handoff")
    with pytest.raises(Error):
        finish(stopping)
    assert app.agent("sea", "alice")["current"] is None
