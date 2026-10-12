"""Fork continuation with actual temporary bare Git; faults simulate lost local replies."""
from pathlib import Path

import pytest

from agent_workspace.util import Conflict, Error, RetryableRead, Uncertain, encode


@pytest.fixture
def source(app, monkeypatch):
    # Bundle installation is covered elsewhere; keep these Git fixtures focused on Fork assets.
    monkeypatch.setattr(app, "_resources", lambda: {"reference.txt": b"saved reference"})
    app.create("sea", "alice")
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "fixture-source-session")
    root = app.root("sea", "alice")
    (root / "notes.txt").write_text("original assets", encoding="utf-8")
    point = app.checkpoint("sea", "alice", "starting files", binding=binding)
    return app, binding, point


def fork(source, **kwargs):
    app, _, point = source
    return app.fork("sea", "alice", point["id"], "exploration", new_id="target", **kwargs)


def assert_source_unchanged(source):
    app, binding, _ = source
    assert app.agent("sea", "alice")["current"] == binding
    assert (app.root("sea", "alice") / "notes.txt").read_text(encoding="utf-8") == "original assets"


def test_normal_fork_has_independent_identity_without_starting(source):
    result = fork(source)
    assert result["id"] == "target"
    assert result["current"] is None and result["has_run"] is False
    assert (Path(result["directory"]) / "notes.txt").read_text(encoding="utf-8") == "original assets"
    assert_source_unchanged(source)


def test_resume_registers_saved_branch_without_recreating_it(source, monkeypatch):
    app, _, _ = source
    store = app.store("sea")
    change = store.change

    def fail_registration(*args, **kwargs):
        raise Error("fixture registration rejected before write")

    monkeypatch.setattr(store, "change", fail_registration)
    with pytest.raises(Error):
        fork(source)
    revision = store.snapshot("instance/target").revision
    assert store.snapshot().json("agents/target.json") is None
    monkeypatch.setattr(store, "change", change)
    result = fork(source, resume=True)
    assert result["revision"] == revision
    assert store.snapshot("instance/target").revision == revision
    assert_source_unchanged(source)


def test_resume_only_connects_after_directory_preparation_failure(source, monkeypatch):
    app, _, _ = source
    connect = app.connect_agent

    def fail_connect(*args, **kwargs):
        raise Error("fixture directory unavailable")

    monkeypatch.setattr(app, "connect_agent", fail_connect)
    with pytest.raises(Error):
        fork(source)
    shared = app.store("sea").snapshot().revision
    monkeypatch.setattr(app, "connect_agent", connect)
    result = fork(source, resume=True)
    root = Path(result["directory"])
    (root / "notes.txt").write_text("user changed this", encoding="utf-8")
    (root / "new.txt").write_text("new user file", encoding="utf-8")
    fork(source, resume=True)
    assert app.store("sea").snapshot().revision == shared
    assert (root / "notes.txt").read_text(encoding="utf-8") == "user changed this"
    assert (root / "new.txt").read_text(encoding="utf-8") == "new user file"
    assert_source_unchanged(source)


@pytest.mark.parametrize("publication", ["branch", "registration"])
def test_resume_reads_back_original_publication_after_reply_lost(source, monkeypatch, publication):
    app, _, _ = source
    store = app.store("sea")
    method = "branch" if publication == "branch" else "change"
    original = getattr(store, method)

    def publish_then_lose_reply(*args, **kwargs):
        original(*args, **kwargs)
        raise Uncertain("fixture reply lost after actual Git publication")

    monkeypatch.setattr(store, method, publish_then_lose_reply)
    with pytest.raises(Uncertain):
        fork(source)
    branch = store.snapshot("instance/target").revision
    shared = store.snapshot().revision
    monkeypatch.setattr(store, method, original)
    fork(source, resume=True)
    assert store.snapshot("instance/target").revision == branch
    if publication == "registration":
        assert store.snapshot().revision == shared


def test_unconfirmed_registration_is_not_replayed(source, monkeypatch):
    app, _, _ = source
    store = app.store("sea")
    calls = []

    def unknown(*args, **kwargs):
        calls.append(args)
        raise Uncertain("fixture publication unknown")

    monkeypatch.setattr(store, "change", unknown)
    with pytest.raises(Uncertain):
        fork(source)
    with pytest.raises(Uncertain):
        fork(source, resume=True)
    assert len(calls) == 1


def test_unavailable_read_does_not_replay_publication(source, monkeypatch):
    app, _, _ = source
    fork(source)
    store = app.store("sea")
    shared = store.snapshot().revision

    def unavailable(*args, **kwargs):
        raise RetryableRead("fixture original facts unavailable")

    with monkeypatch.context() as fault:
        fault.setattr(store, "snapshot", unavailable)
        with pytest.raises(RetryableRead):
            fork(source, resume=True)
    assert store.snapshot().revision == shared


def test_original_unknown_registration_can_be_read_after_it_finishes(source, monkeypatch):
    app, _, _ = source
    store = app.store("sea")
    change = store.change

    def unknown(*args, **kwargs):
        raise Uncertain("fixture original write has not completed")

    monkeypatch.setattr(store, "change", unknown)
    with pytest.raises(Uncertain):
        fork(source)
    with pytest.raises(Uncertain):
        fork(source, resume=True)
    # Simulate the original server operation finishing, using its exact saved record.
    item = store.snapshot("instance/target").json(".aw/fork.json")
    change("main", {"agents/target.json": encode(item)}, {"agents/target.json": None}, "fixture original finishes")
    shared = store.snapshot().revision
    result = fork(source, resume=True)
    assert result["id"] == "target"
    assert store.snapshot().revision == shared


@pytest.mark.parametrize("conflict", ["checkpoint", "identity", "registration"])
def test_resume_rejects_changed_source_or_other_target_identity(source, monkeypatch, conflict):
    app, binding, point = source
    fork(source)
    store = app.store("sea")
    if conflict == "checkpoint":
        newer = app.checkpoint("sea", "alice", "later files", binding=binding)
        snap = store.snapshot()
        path = f"checkpoints/alice/{point['id']}.json"
        changed = dict(point, revision=newer["revision"])
        store.change("main", {path: encode(changed)}, {path: snap.entries[path]}, "fixture changed pointer")
    elif conflict == "identity":
        snap = store.snapshot("instance/target")
        store.change("instance/target", {".aw/identity.json": encode({"workspace": "local:sea", "agent": "other"})},
                     {}, "fixture other identity", base=snap.revision)
    else:
        snap = store.snapshot()
        item = snap.json("agents/target.json")
        item["forked_from"]["agent"] = "other"
        store.change("main", {"agents/target.json": encode(item)},
                     {"agents/target.json": snap.entries["agents/target.json"]}, "fixture other registration")
    with pytest.raises(Conflict):
        fork(source, resume=True)


def test_ordinary_fork_still_refuses_existing_target(source):
    app, _, _ = source
    fork(source)
    before = app.store("sea").snapshot().revision
    with pytest.raises(Conflict):
        fork(source)
    assert app.store("sea").snapshot().revision == before


def test_resume_never_creates_an_unconfirmed_branch(source, monkeypatch):
    app, _, _ = source
    store = app.store("sea")
    attempts = []

    def unknown(*args, **kwargs):
        attempts.append(args)
        raise Uncertain("fixture branch publication unknown")

    monkeypatch.setattr(store, "branch", unknown)
    with pytest.raises(Uncertain):
        fork(source)
    with pytest.raises(Uncertain):
        fork(source, resume=True)
    with pytest.raises(Conflict):
        fork(source)
    assert len(attempts) == 1


def test_known_branch_failure_allows_same_target_retry(source, monkeypatch):
    app, _, _ = source
    store = app.store("sea")

    def rejected(*args, **kwargs):
        raise Error("fixture branch rejected before publication")

    with monkeypatch.context() as fault:
        fault.setattr(store, "branch", rejected)
        with pytest.raises(Error):
            fork(source)
    assert store.snapshot("instance/target").revision == ""
    assert store.snapshot().json("agents/target.json") is None
    result = fork(source)
    assert result["id"] == "target" and result["current"] is None
    assert len([agent for agent in app.agents("sea") if agent["id"] == "target"]) == 1
    assert store.snapshot("instance/target").revision == result["revision"]
    assert_source_unchanged(source)
