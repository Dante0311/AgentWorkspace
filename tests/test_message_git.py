"""Message layout compatibility and real Git with a child Python that cannot import AW."""
import base64
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

from agent_workspace.messages import Messages
from agent_workspace.direct_messages import DirectMessages
from agent_workspace.gitstore import GitStore
from agent_workspace import commands, layout, maintenance
from agent_workspace.util import Conflict, Error, Uncertain, encode
from agent_workspace.app import App


SCRIPT = Path(__file__).parents[1] / "src/agent_workspace/resources/skills/message/scripts/message_git.py"


def clone(tmp_path, app, workspace, name):
    path = tmp_path / name
    subprocess.run(["git", "clone", "--bare", app.store(workspace).address, str(path)], check=True, capture_output=True)
    return path


def command(tmp_path, *args, success=True):
    # -I -S ignores PYTHONPATH and site packages; cwd is outside the source tree.
    result = subprocess.run([sys.executable, "-I", "-S", str(SCRIPT), *map(str, args)],
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    return json.loads(result.stdout)


def receive_args(repo, binding, record, *extra):
    return ("receive", "--repo", repo, "--agent", "bob", "--binding", binding, "--id", "original", "--record", record, *extra)


def continue_args(binding, record):
    return ("continue", "--record", record, "--agent", "bob", "--binding", binding)


def seeded(pair, tmp_path):
    app, bindings = pair
    Messages(app).send("sea", "alice", bindings["alice"], "bob", '中文\n"引号"\n```code```', request_id="original")
    return app, bindings, clone(tmp_path, app, "sea", "own-cache")


def load_helper():
    return runpy.run_path(str(SCRIPT))


def legacy_workspace(app, name, directory):
    """Historical 0/1 transitions start from a real v1 repository, not new v3."""
    GitStore.initialize(directory)
    store = GitStore(str(directory), app.home)
    metadata = {"schema": 1, "name": name, "locator": "local:" + name, "friends": {}, "projects": {}}
    store.branch("main", {layout.MARKER: layout.marker("workspace"),
                          ".agentworkspace/workspace.json": encode(metadata)})
    app.workspace_connect(name, str(directory))


@pytest.fixture
def worker_protocol(tmp_path):
    app = App(tmp_path / "worker-home")
    app.workspace_init("sea", str(tmp_path / "worker-sea.git"), worker_support=True)
    app.create("sea", "team")
    app.worker_create("sea", "team", "Topic", "Independent work", worker_id="topic")
    bindings = {}
    for wid in ("default", "topic"):
        bid = app.reserve("sea", "team", worker_id=wid)["binding"]
        app.bind("sea", "team", bid, "native-" + wid, worker_id=wid)
        bindings[wid] = bid
    Messages(app).send("sea", "team", bindings["default"], "team", "原始 Worker 通知\n保留字节",
                       to_worker="topic", request_id="worker-original")
    return app, bindings, clone(tmp_path, app, "sea", "worker-cache")


def worker_command(repo, bid, action, *extra):
    return (action, "--repo", repo, "--agent", "team", "--binding", bid,
            "--id", "worker-original", *extra)


def test_script_worker_ack_reply_and_default_change_without_aw_import(worker_protocol, tmp_path):
    app, bids, repo = worker_protocol
    store = app.store("sea")
    snap = store.message_snapshot().messages
    path = layout.shared_path(snap, "messages/worker-original.json")
    original = snap.bytes(path)
    shown = command(tmp_path, *worker_command(repo, bids["topic"], "show"))
    assert shown["message_json"].encode() == original
    wrong = tmp_path / "wrong-worker.json"
    command(tmp_path, *worker_command(repo, bids["default"], "receive", "--record", wrong, "--publish"), success=False)
    assert not wrong.exists()
    ack = command(tmp_path, *worker_command(repo, bids["topic"], "receive", "--record", tmp_path / "worker-ack.json", "--publish"))
    assert ack["state"] == "published" and ack["actor"]["worker"] == "topic"
    assert Messages(app).show("sea", "worker-original")["ack"] == {"message_id": "worker-original"}
    content = tmp_path / "worker-reply.md"
    content.write_text("明确回复原 Worker", encoding="utf-8")
    journal = tmp_path / "worker-reply.json"
    prepared = command(tmp_path, *worker_command(repo, bids["topic"], "reply", "--content-file", content,
                       "--request-id", "worker-reply", "--record", journal))
    assert prepared["format"] == "message-git-operation-v2"
    app.worker_default("sea", "team", "topic", app.show("sea", "team")["revision"])
    published = command(tmp_path, "continue", "--agent", "team", "--binding", bids["topic"], "--record", journal)
    assert published["state"] == "published" and published["records"] == prepared["records"]
    reply = Messages(app).show("sea", "worker-reply")["message"]
    assert reply["from"]["worker"] == "topic" and reply["to"]["worker"] == "default"
    assert reply["reply_to"] == "worker-original"
    assert store.message_snapshot().messages.bytes(path) == original


def test_script_worker_unknown_write_is_only_observed(worker_protocol, tmp_path, monkeypatch):
    app, bids, repo = worker_protocol
    journal = tmp_path / "worker-unknown.json"
    prepared = command(tmp_path, *worker_command(repo, bids["topic"], "receive", "--record", journal))
    namespace = load_helper()
    calls = []

    def lost(repo, commit, parent, **kwargs):
        calls.append(commit)
        raise subprocess.TimeoutExpired("isolated original push", 1)

    monkeypatch.setattr(namespace["Repository"], "push", lost)
    first = namespace["publish"](journal, prepared)
    assert first["state"] == "outcome_unknown" and len(calls) == 1
    app.worker_default("sea", "team", "topic", app.show("sea", "team")["revision"])
    second = namespace["publish"](journal, json.loads(journal.read_bytes()))
    assert second["state"] == "outcome_unknown" and len(calls) == 1
    assert second["records"] == first["records"]
    assert Messages(app).show("sea", "worker-original")["ack"] is None


def test_script_prepared_legacy_ack_uses_explicit_worker_mapping(app, tmp_path):
    app.create("sea", "team")
    bid = app.reserve("sea", "team")["binding"]
    app.bind("sea", "team", bid, "original-session")
    Messages(app).send("sea", "team", bid, "team", "legacy notification", request_id="worker-original")
    repo = clone(tmp_path, app, "sea", "legacy-worker-cache")
    journal = tmp_path / "legacy-worker-ack.json"
    prepared = command(tmp_path, *worker_command(repo, bid, "receive", "--record", journal))
    original = Messages(app).show("sea", "worker-original")["message"]
    app.checkpoint("sea", "team", "before explicit Worker mapping", binding=bid)
    app.workers_migrate("sea", "team", "daily", "legacy-helper-map", compatible_writers=["worker-v2"])
    app.worker_create("sea", "team", "Other", "New work", worker_id="other")
    app.worker_default("sea", "team", "other", app.show("sea", "team")["revision"])
    result = command(tmp_path, "continue", "--agent", "team", "--binding", bid, "--record", journal)
    assert result["state"] == "published" and result["records"] == prepared["records"]
    assert Messages(app).show("sea", "worker-original")["message"] == original
    assert Messages(app).show("sea", "worker-original")["ack"] == {"message_id": "worker-original"}


def test_script_unmapped_legacy_reply_is_preserved_without_guessing_default(app, tmp_path):
    app.create("sea", "team")
    bid = app.reserve("sea", "team")["binding"]
    app.bind("sea", "team", bid, "original-session")
    Messages(app).send("sea", "team", bid, "team", "legacy notification", request_id="worker-original")
    repo = clone(tmp_path, app, "sea", "unmapped-legacy-cache")
    content = tmp_path / "legacy-reply.md"
    content.write_text("prepared before migration", encoding="utf-8")
    journal = tmp_path / "unmapped-reply.json"
    command(tmp_path, *worker_command(repo, bid, "reply", "--record", journal,
            "--content-file", content, "--request-id", "unpublished-old-reply"))
    original_journal = journal.read_bytes()
    app.checkpoint("sea", "team", "before explicit Worker mapping", binding=bid)
    app.workers_migrate("sea", "team", "daily", "unmapped-helper-map", compatible_writers=["worker-v2"])
    app.worker_create("sea", "team", "Other", "New work", worker_id="other")
    app.worker_default("sea", "team", "other", app.show("sea", "team")["revision"])
    original_head = app.store("sea").snapshot().revision
    result = command(tmp_path, "continue", "--agent", "team", "--binding", bid, "--record", journal, success=False)
    assert result["error_type"] == "ProtocolError"
    assert journal.read_bytes() == original_journal
    assert app.store("sea").snapshot().revision == original_head
    with pytest.raises(Error):
        Messages(app).show("sea", "unpublished-old-reply")


def fixture_shared_layout(store, current):
    """Arrange isolated protocol fixtures; this is not a production migration test."""
    snap = store.snapshot()
    old_prefix = ".agentworkspace/" if layout.version(snap, "workspace") else ""
    prefix = ".agentworkspace/" if current else ""
    if old_prefix == prefix:
        return
    changes = {}
    for path in snap.entries:
        if not path.startswith(old_prefix):
            continue
        name = path[len(old_prefix):]
        if name != "workspace.json" and name.split("/")[0] not in layout.SHARED_ROOTS:
            continue
        changes[prefix + name] = snap.bytes(path)
        changes[path] = None
    changes[layout.MARKER] = layout.marker("workspace") if current else None
    store.change("main", changes, {path: snap.entries.get(path) for path in changes}, "Arrange isolated layout fixture")


def fixture_external_records(store, changes):
    """Inject an external client's invalid metadata without weakening AW validation."""
    repository = load_helper()["Repository"](store.address)
    parent = store.snapshot().revision
    commit = repository.commit(parent, changes)
    repository.git("update-ref", "refs/heads/main", commit, parent)


@pytest.mark.parametrize("current", [False, True])
def test_script_layout_preserves_original_bytes_and_publishes_only_protocol_records(pair, tmp_path, current):
    app, bindings = pair
    messages = Messages(app)
    messages.send("sea", "alice", bindings["alice"], "bob", "original", request_id="original")
    store = app.store("sea")
    fixture_shared_layout(store, current)
    snap = store.snapshot()
    path = layout.shared_path(snap, "messages/original.json")
    body = snap.json(path)
    body.update(content='中文\r\n"quotes"\r\n```json\r\n{}\r\n```', future={"keep": True})
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    store.change("main", {path: raw}, {path: snap.entries[path]}, "Arrange raw protocol fixture")
    repo = clone(tmp_path, app, "sea", "layout-cache")
    shown = command(tmp_path, "show", "--repo", repo, "--agent", "bob", "--binding", bindings["bob"], "--id", "original")
    assert shown["message_json"].encode() == raw
    before = store.snapshot()
    received = command(tmp_path, *receive_args(repo, bindings["bob"], tmp_path / "ack-layout.json"), "--publish")
    assert received["state"] == "published"
    after = store.snapshot()
    ack = layout.shared_path(after, "acks/original.json")
    assert after.json(ack) == {"message_id": "original"}
    assert set(after.entries) - set(before.entries) == {ack}
    assert after.bytes(path) == raw and before.all() == store.snapshot(revision=before.revision).all()
    assert messages.show("sea", "original")["message"]["future"] == {"keep": True}
    assert messages._list(before, "bob", unacked=True)[0]["id"] == "original"
    assert messages.list("sea", "bob", unacked=True) == []


def test_script_layout_continues_original_prepared_v1_operation_after_path_change(pair, tmp_path):
    app, bindings = pair
    fixture_shared_layout(app.store("sea"), False)
    messages = Messages(app)
    messages.send("sea", "alice", bindings["alice"], "bob", "saved once", request_id="original")
    before = app.store("sea").snapshot()
    repo = clone(tmp_path, app, "sea", "old-cache")
    record = tmp_path / "original-ack.json"
    operation = command(tmp_path, *receive_args(repo, bindings["bob"], record))
    records = operation["records"]
    source = operation["source_index"]
    fixture_shared_layout(app.store("sea"), True)
    result = command(tmp_path, *continue_args(bindings["bob"], record))
    assert result["state"] == "published" and result["format"] == "message-git-operation-v1"
    assert result["records"] == records and result["source_index"] == source
    after = app.store("sea").snapshot()
    assert after.json(".agentworkspace/acks/original.json") == {"message_id": "original"}
    assert after.bytes("acks/original.json") is None
    assert after.bytes(".agentworkspace/messages/original.json") == before.bytes("messages/original.json")
    assert messages._notification(before, before.json("message-index/original.json")) == messages._notification(
        after, after.json(".agentworkspace/message-index/original.json"))


@pytest.mark.parametrize("own_current", [False, True])
def test_script_layout_cross_workspace_targets_choose_their_own_layout(pair, tmp_path, own_current):
    app, bindings = pair
    legacy_workspace(app, "peer", tmp_path / "peer.git")
    app.create("peer", "sender")
    sender = app.reserve("peer", "sender")["binding"]
    app.bind("peer", "sender", sender, "peer-fixture-session")
    app.relation("sea", "friends", "add", "peer", app.store("peer").address)
    app.relation("peer", "friends", "add", "sea", app.store("sea").address)
    Messages(app).send("peer", "sender", sender, "sea/bob", "cross original", request_id="original")
    fixture_shared_layout(app.store("sea"), own_current)
    fixture_shared_layout(app.store("peer"), not own_current)
    own = clone(tmp_path, app, "sea", "mixed-own")
    peer = clone(tmp_path, app, "peer", "mixed-peer")
    ack = command(tmp_path, *receive_args(own, bindings["bob"], tmp_path / "mixed-ack.json"), "--peer", peer, "--publish")
    assert ack["state"] == "published"
    reply = tmp_path / "reply.md"
    reply.write_bytes('跨布局\n"quoted"\n```code```'.encode())
    result = command(tmp_path, "reply", "--repo", own, "--peer", peer, "--agent", "bob", "--binding", bindings["bob"],
                     "--id", "original", "--content-file", reply, "--request-id", "mixed-reply", "--record", tmp_path / "mixed-reply.json", "--publish")
    assert result["state"] == "published"
    snapshots = [app.store(workspace).snapshot() for workspace in ("sea", "peer")]
    for name in ("acks/original.json", "messages/mixed-reply.json", "message-index/mixed-reply.json"):
        assert snapshots[0].bytes(layout.shared_path(snapshots[0], name)) == snapshots[1].bytes(layout.shared_path(snapshots[1], name))
    body = snapshots[0].json(layout.shared_path(snapshots[0], "messages/mixed-reply.json"))
    assert body["content"].encode() == reply.read_bytes() and body["message_refs"] == ["original"]


@pytest.mark.parametrize("landed", [False, True])
def test_script_layout_unknown_original_write_is_only_observed_after_path_change(pair, tmp_path, monkeypatch, landed):
    app, bindings = pair
    store = app.store("sea")
    fixture_shared_layout(store, False)
    Messages(app).send("sea", "alice", bindings["alice"], "bob", "original", request_id="original")
    repo = clone(tmp_path, app, "sea", "unknown-cache")
    record = tmp_path / "unknown-original.json"
    operation = command(tmp_path, *receive_args(repo, bindings["bob"], record))
    helper = load_helper()
    repository = helper["Repository"]
    head, push = repository.head, repository.push
    lost = [False]
    pushes = []
    def lost_response(repo, commit, parent):
        pushes.append(commit)
        if landed:
            push(repo, commit, parent)
        lost[0] = True
        raise subprocess.TimeoutExpired("isolated lost push response", 60)
    def unavailable_readback(repo):
        if lost[0]:
            raise helper["ProtocolError"]("isolated readback unavailable")
        return head(repo)
    with monkeypatch.context() as scoped:
        scoped.setattr(repository, "push", lost_response)
        scoped.setattr(repository, "head", unavailable_readback)
        assert helper["publish"](record, operation)["state"] == "outcome_unknown"
    saved = json.loads(record.read_bytes())
    original_commit = saved["targets"][0]["commit"]
    fixture_shared_layout(store, True)
    before = store.snapshot().revision
    def no_replay(*args):
        raise AssertionError("An unknown original write must not be pushed again")
    monkeypatch.setattr(repository, "push", no_replay)
    result = helper["publish"](record, saved)
    assert result["state"] == ("published" if landed else "outcome_unknown")
    assert result["targets"][0]["commit"] == original_commit and len(pushes) == 1
    assert store.snapshot().revision == before
    assert bool(store.snapshot().bytes(".agentworkspace/acks/original.json")) is landed


@pytest.mark.parametrize("marker", [
    {"version": 99, "kind": "workspace"}, {"version": True, "kind": "workspace"},
    {"version": 1, "kind": "instance"}, {"version": 1, "kind": "workspace", "state": "migrating"},
])
def test_script_layout_rejects_unsupported_or_unfinished_marker_before_ack(pair, tmp_path, marker):
    app, bindings, repo = seeded(pair, tmp_path)
    store = app.store("sea")
    fixture_external_records(store, {layout.MARKER: encode(marker)})
    before = store.snapshot().revision
    record = tmp_path / "refused-ack.json"
    result = command(tmp_path, *receive_args(repo, bindings["bob"], record), "--publish", success=False)
    assert result["ok"] is False and not record.exists()
    assert store.snapshot().revision == before
    assert store.snapshot().bytes(".agentworkspace/acks/original.json") is None
    assert store.snapshot().bytes("acks/original.json") is None


def test_aw_layout_keeps_original_ack_receipt_and_pinned_message_history(pair, monkeypatch):
    app, bindings = pair
    store = app.store("sea")
    fixture_shared_layout(store, False)
    messages = Messages(app)
    messages.send("sea", "alice", bindings["alice"], "bob", "原消息\n```text```", request_id="original")
    change = GitStore.change
    writes = []
    def lost_ack(store, branch, changes, *args, **kwargs):
        result = change(store, branch, changes, *args, **kwargs)
        if "acks/original.json" in changes:
            writes.append(result)
            raise Uncertain("The original ACK landed but its response was lost")
        return result
    with monkeypatch.context() as scoped:
        scoped.setattr(GitStore, "change", lost_ack)
        received = messages.receive("sea", "bob", bindings["bob"], "original")
    receipt = received["publication"]
    assert receipt["state"] == "outcome_unknown"
    legacy = store.snapshot()
    fixture_shared_layout(store, True)
    before = store.snapshot()
    def no_write(*args, **kwargs):
        raise AssertionError("The original published ACK only needs readback")
    monkeypatch.setattr(GitStore, "change", no_write)
    result = messages.reconcile(receipt["id"])
    assert result["state"] == "published" and result["binding"] == bindings["bob"] and len(writes) == 1
    assert store.snapshot().revision == before.revision
    assert before.bytes(".agentworkspace/messages/original.json") == legacy.bytes("messages/original.json")
    assert before.bytes(".agentworkspace/acks/original.json") == legacy.bytes("acks/original.json")
    assert messages.show("sea", "original")["ack"] == {"message_id": "original"}
    assert messages._list(legacy, "bob") == messages.list("sea", "bob")
    assert messages._notification(legacy, legacy.json("message-index/original.json")) == messages._notification(
        before, before.json(".agentworkspace/message-index/original.json"))


def test_aw_layout_reads_the_same_direct_history_without_creating_formal_records(pair):
    app, bindings = pair
    store = app.store("sea")
    fixture_shared_layout(store, False)
    history = DirectMessages(app)
    result = history.record("sea", "alice", bindings["alice"], "bob", "native once", request_id="native-once")
    assert result["recorded"] is True
    legacy = store.snapshot()
    fixture_shared_layout(store, True)
    before = store.snapshot()
    assert before.bytes(".agentworkspace/direct-messages/native-once.json") == legacy.bytes("direct-messages/native-once.json")
    assert history.show("sea", "native-once")["record"] == result["record"]
    assert history.list("sea", "bob") == [result["record"]]
    assert Messages(app).list("sea", "bob") == []
    assert store.snapshot().revision == before.revision


def test_aw_layout_future_format_refuses_writes_and_reports_unavailable_health(pair):
    app, bindings = pair
    store = app.store("sea")
    fixture_shared_layout(store, False)
    fixture_external_records(store, {layout.MARKER: encode({"kind": "workspace", "version": 99})})
    before = store.snapshot().revision
    with pytest.raises(Error):
        Messages(app).send("sea", "alice", bindings["alice"], "bob", "must not publish", request_id="future-send")
    result = DirectMessages(app).record("sea", "alice", bindings["alice"], "bob", "optional history", request_id="future-direct")
    assert result["recorded"] is False
    assert maintenance.doctor(app, "sea")["state"] == "unavailable"
    assert store.snapshot().revision == before
    assert not (app.home / "operations/future-send.json").exists()


def test_aw_layout_missing_current_record_does_not_read_a_legacy_file(pair):
    app, bindings = pair
    store = app.store("sea")
    fixture_shared_layout(store, False)
    messages = Messages(app)
    messages.send("sea", "alice", bindings["alice"], "bob", "old body", request_id="original")
    history = DirectMessages(app)
    assert history.record("sea", "alice", bindings["alice"], "bob", "old history", request_id="old-direct")["recorded"]
    snap = store.snapshot()
    store.change("main", {layout.MARKER: layout.marker("workspace"), ".agentworkspace/workspace.json": snap.bytes("workspace.json")},
                 {layout.MARKER: None, ".agentworkspace/workspace.json": None}, "Arrange conflicting old files in a current layout")
    with pytest.raises(Error):
        messages.show("sea", "original")
    assert history.show("sea", "old-direct") == {"record": None}
    assert history.list("sea") == []
    assert store.snapshot().bytes("messages/original.json") == snap.bytes("messages/original.json")


def test_aw_layout_guard_keeps_a_partial_ack_from_writing_the_old_peer_path(pair, tmp_path, monkeypatch):
    app, bindings = pair
    legacy_workspace(app, "peer", tmp_path / "peer.git")
    app.create("peer", "sender")
    sender = app.reserve("peer", "sender")["binding"]
    app.bind("peer", "sender", sender, "peer-fixture-session")
    app.relation("sea", "friends", "add", "peer", app.store("peer").address)
    app.relation("peer", "friends", "add", "sea", app.store("sea").address)
    fixture_shared_layout(app.store("sea"), False)
    peer = app.store("peer")
    fixture_shared_layout(peer, False)
    messages = Messages(app)
    messages.send("peer", "sender", sender, "sea/bob", "original", request_id="original")
    change = GitStore.change
    changed = []
    def change_layout_before_ack(store, branch, changes, *args, **kwargs):
        if store.address == peer.address and "acks/original.json" in changes and not changed:
            changed.append(True)
            fixture_shared_layout(peer, True)
        return change(store, branch, changes, *args, **kwargs)
    with monkeypatch.context() as scoped:
        scoped.setattr(GitStore, "change", change_layout_before_ack)
        received = messages.receive("sea", "bob", bindings["bob"], "original")
    receipt = received["publication"]
    assert receipt["state"] == "pending" and changed == [True]
    assert peer.snapshot().bytes("acks/original.json") is None
    assert peer.snapshot().bytes(".agentworkspace/acks/original.json") is None
    result = messages.reconcile(receipt["id"])
    assert result["state"] == "published" and result["id"] == receipt["id"]
    assert result["binding"] == bindings["bob"]
    assert app.store("sea").snapshot().bytes("acks/original.json") == peer.snapshot().bytes(".agentworkspace/acks/original.json")


def test_aw_layout_guard_refuses_stale_schedule_creation(app, monkeypatch):
    store = app.store("sea")
    fixture_shared_layout(store, False)
    change = GitStore.change
    changed = []
    def change_layout_before_schedule(store, branch, changes, *args, **kwargs):
        if "maintenance/schedule.json" in changes and not changed:
            changed.append(True)
            fixture_shared_layout(store, True)
        return change(store, branch, changes, *args, **kwargs)
    with monkeypatch.context() as scoped:
        scoped.setattr(GitStore, "change", change_layout_before_schedule)
        with pytest.raises(Conflict):
            maintenance.schedule(app, "sea", True)
    assert not (maintenance.folder(app, "sea") / "schedule.json").exists()
    assert store.snapshot().bytes("maintenance/schedule.json") is None
    assert store.snapshot().bytes(".agentworkspace/maintenance/schedule.json") is None
    value = maintenance.schedule(app, "sea", True)
    assert store.snapshot().json(".agentworkspace/maintenance/schedule.json") == {key: value[key] for key in value if key != "execution"}


def test_work_and_maintenance_shared_history_keep_ids_revisions_and_original_bytes(pair):
    app, bindings = pair
    store = app.store("sea")
    fixture_shared_layout(store, False)
    actor = ("sea", "alice", bindings["alice"])
    proof = commands.execute(app, "asset.write", {
        "path": "notes/layout-proof.txt", "content": "isolated Work result"}, actor=actor)
    work = commands.execute(app, "work.create", {"owner": "alice", "content": "isolated Work"}, actor=actor)
    refs = [{"agent": "alice", "path": proof["path"], "revision": proof["revision"]}]
    commands.execute(app, "work.deliver", {
        "work_id": work["id"], "revision": work["revision"], "content": "isolated fixture completed", "refs": refs}, actor=actor)
    original = app.work_show("sea", work["id"])
    maintenance.schedule(app, "sea", True, notify=False)
    legacy = store.snapshot()
    fixture_shared_layout(store, True)
    current = store.snapshot()
    for name in (f"work/{work['id']}/work.json", f"work/{work['id']}/delivery.json", "maintenance/schedule.json"):
        assert current.bytes(".agentworkspace/" + name) == legacy.bytes(name)
    assert commands.execute(app, "work.show", {"work_id": work["id"]}, actor=actor) == original
    assert app.work_list("sea", owner="alice")[0]["delivery"] == original["delivery"]
    assert maintenance.status(app, "sea")["schedule"] == legacy.json("maintenance/schedule.json")
    with pytest.raises(Conflict):
        app.work_update("sea", work["id"], work["revision"], content="sealed Work must not change")
    assert store.snapshot().revision == current.revision


def test_script_without_aw_reads_acknowledges_and_replies(pair, tmp_path):
    app, bindings, repo = seeded(pair, tmp_path)
    unavailable = subprocess.run([sys.executable, "-I", "-S", "-c",
                                  "import importlib.util; assert importlib.util.find_spec('agent_workspace') is None"],
                                 cwd=tmp_path, capture_output=True)
    assert unavailable.returncode == 0
    original = app.store("sea").snapshot().bytes(".agentworkspace/messages/original.json")
    shown = command(tmp_path, "show", "--repo", repo, "--agent", "bob", "--binding", bindings["bob"], "--id", "original")
    assert shown["message_json"].encode() == original and shown["ack"] is None
    record = tmp_path / "ack-operation.json"
    assert command(tmp_path, *receive_args(repo, bindings["bob"], record))["state"] == "prepared"
    assert app.store("sea").snapshot().bytes(".agentworkspace/acks/original.json") is None
    assert command(tmp_path, *continue_args(bindings["bob"], record))["state"] == "published"
    before = app.store("sea").snapshot().revision
    duplicate = command(tmp_path, *receive_args(repo, bindings["bob"], tmp_path / "duplicate.json"), "--publish")
    assert duplicate["already_acknowledged"] and app.store("sea").snapshot().revision == before
    content = '答复\r\n"引号"\r\n```json\r\n{}\r\n```'
    reply = tmp_path / "reply.md"
    reply.write_bytes(content.encode())
    operation = tmp_path / "reply-operation.json"
    prepared = command(tmp_path, "reply", "--repo", repo, "--agent", "bob", "--binding", bindings["bob"],
                       "--id", "original", "--content-file", reply, "--request-id", "reply-one", "--record", operation)
    assert prepared["state"] == "prepared"
    assert command(tmp_path, *continue_args(bindings["bob"], operation))["state"] == "published"
    body = Messages(app).show("sea", "reply-one")["message"]
    assert body["content"] == content and body["message_refs"] == ["original"]
    assert body["from"]["agent"] == "bob" and body["to"]["agent"] == "alice"
    assert app.store("sea").snapshot().bytes(".agentworkspace/messages/original.json") == original
    assert command(tmp_path, *continue_args(bindings["bob"], operation))["state"] == "published"


@pytest.mark.parametrize("damaged", [None, b"broken JSON"])
def test_script_confirms_notification_when_body_missing_or_damaged(pair, tmp_path, damaged):
    app, bindings, repo = seeded(pair, tmp_path)
    app.store("sea").change("main", {".agentworkspace/messages/original.json": damaged}, {}, "isolated body fault")
    result = command(tmp_path, *receive_args(repo, bindings["bob"], tmp_path / "ack.json"), "--publish")
    assert result["state"] == "published" and result["read_result"]["read_error"]
    assert app.store("sea").snapshot().json(".agentworkspace/acks/original.json") == {"message_id": "original"}


@pytest.mark.parametrize("failure_stage", ["target-validation", "peer-publication"])
def test_cross_workspace_partial_reply_continues_original_bytes(pair, tmp_path, monkeypatch, failure_stage):
    app, bindings = pair
    legacy_workspace(app, "peer", tmp_path / "peer.git")
    app.create("peer", "sender")
    sender = app.reserve("peer", "sender")["binding"]
    app.bind("peer", "sender", sender, "isolated-sender-session")
    app.relation("sea", "friends", "add", "peer", app.store("peer").address)
    app.relation("peer", "friends", "add", "sea", app.store("sea").address)
    Messages(app).send("peer", "sender", sender, "sea/bob", "cross question", request_id="original")
    own, peer = clone(tmp_path, app, "sea", "own-cache"), clone(tmp_path, app, "peer", "peer-cache")
    ack = command(tmp_path, *receive_args(own, bindings["bob"], tmp_path / "ack.json"), "--peer", peer, "--publish")
    assert ack["state"] == "published"
    assert app.store("sea").snapshot().bytes(".agentworkspace/acks/original.json") == app.store("peer").snapshot().bytes(".agentworkspace/acks/original.json")
    reply = tmp_path / "reply.md"
    reply.write_text("cross reply", encoding="utf-8")
    record = tmp_path / "reply.json"
    operation = command(tmp_path, "reply", "--repo", own, "--peer", peer, "--agent", "bob", "--binding", bindings["bob"],
                        "--id", "original", "--content-file", reply, "--request-id", "reply-one", "--record", record)
    helper = load_helper()
    repository = helper["Repository"]
    head, commit, push = repository.head, repository.commit, repository.push
    own_path, peer_path = str(own.resolve()), str(peer.resolve())
    own_before, peer_before = app.store("sea").snapshot(), app.store("peer").snapshot()
    saved_journal = record.read_bytes()
    original_records = dict(operation["records"])
    writes = []

    def unavailable(repo):
        # Let destination validation finish when testing the later partial publication.
        if repo.path == peer_path and (failure_stage == "target-validation"
                or operation["targets"][0].get("state") == "confirmed"):
            raise helper["ProtocolError"]("isolated peer read unavailable before any peer write")
        return head(repo)

    def observed_commit(repo, parent, records):
        writes.append(("commit", repo.path))
        return commit(repo, parent, records)

    def observed_push(repo, revision, parent):
        writes.append(("push", repo.path))
        return push(repo, revision, parent)

    with monkeypatch.context() as scoped:
        scoped.setattr(repository, "head", unavailable)
        scoped.setattr(repository, "commit", observed_commit)
        scoped.setattr(repository, "push", observed_push)
        with pytest.raises(helper["ProtocolError"]):
            helper["publish"](record, operation)
    before = app.store("sea").snapshot()
    assert app.store("peer").snapshot().revision == peer_before.revision
    paths = (".agentworkspace/messages/reply-one.json", ".agentworkspace/message-index/reply-one.json")
    expected_records = {path: base64.b64decode(original_records[path.removeprefix(".agentworkspace/")]) for path in paths}
    assert operation["records"] == original_records
    original_reply = before.bytes(".agentworkspace/messages/reply-one.json")
    if failure_stage == "target-validation":
        assert writes == []
        assert before.revision == own_before.revision
        assert record.read_bytes() == saved_journal
        assert all(before.bytes(path) is None for path in paths)
    else:
        assert writes == [("commit", own_path), ("push", own_path)]
        assert all(before.bytes(path) == raw for path, raw in expected_records.items())
        assert json.loads(record.read_bytes())["targets"][0]["state"] == "confirmed"
    assert all(app.store("peer").snapshot().bytes(path) is None for path in paths)

    continued = command(tmp_path, *continue_args(bindings["bob"], record))
    assert continued["state"] == "published" and continued["records"] == original_records
    after = app.store("sea").snapshot()
    peer_after = app.store("peer").snapshot()
    assert all(after.bytes(path) == peer_after.bytes(path) == raw for path, raw in expected_records.items())
    assert {path: blob for path, blob in after.entries.items() if path not in paths} == own_before.entries
    assert {path: blob for path, blob in peer_after.entries.items() if path not in paths} == peer_before.entries
    if failure_stage == "peer-publication":
        assert original_reply is not None and after.revision == before.revision


@pytest.mark.parametrize("landed", [True, False])
def test_unknown_write_only_reads_original_and_never_pushes_again(pair, tmp_path, monkeypatch, landed):
    app, bindings, repo = seeded(pair, tmp_path)
    record = tmp_path / "ack.json"
    operation = command(tmp_path, *receive_args(repo, bindings["bob"], record))
    helper = load_helper()
    repository = helper["Repository"]
    push, head = repository.push, repository.head
    pushes = []
    response_lost = False

    def lost_response(repo, commit, parent):
        nonlocal response_lost
        pushes.append(commit)
        if landed:
            push(repo, commit, parent)
        response_lost = True
        raise subprocess.TimeoutExpired("isolated Git push", 60)

    def failed_readback(repo):
        if response_lost:
            raise helper["ProtocolError"]("isolated readback failed")
        return head(repo)

    with monkeypatch.context() as scoped:
        scoped.setattr(repository, "push", lost_response)
        scoped.setattr(repository, "head", failed_readback)
        assert helper["publish"](record, operation)["state"] == "outcome_unknown"
    saved = json.loads(record.read_bytes())
    before = app.store("sea").snapshot().revision
    result = command(tmp_path, *continue_args(bindings["bob"], record))
    assert result["state"] == ("published" if landed else "outcome_unknown")
    assert app.store("sea").snapshot().revision == before
    assert len(pushes) == 1 and result["targets"][0]["commit"] == saved["targets"][0]["commit"]
    assert len(result["targets"][0]["attempts"]) == 1


@pytest.mark.parametrize("revoked", [False, True])
def test_conflicting_head_is_preserved_and_revoked_binding_cannot_continue(pair, tmp_path, monkeypatch, revoked):
    app, bindings, repo = seeded(pair, tmp_path)
    record = tmp_path / "ack.json"
    operation = command(tmp_path, *receive_args(repo, bindings["bob"], record))
    helper = load_helper()
    repository = helper["Repository"]
    push = repository.push

    def concurrent_change(repo, commit, parent):
        store = app.store("sea")
        changes = {"other-owner.txt": b"keep concurrent content"}
        if revoked:
            snap = store.snapshot()
            agent = snap.json(".agentworkspace/agents/bob.json")
            agent["current"] = None
            entry = snap.json(f".agentworkspace/bindings/{bindings['bob']}.json")
            entry["phase"] = "released"
            changes.update({".agentworkspace/agents/bob.json": encode(agent), f".agentworkspace/bindings/{bindings['bob']}.json": encode(entry)})
        store.change("main", changes, {}, "isolated concurrent owner")
        return push(repo, commit, parent)

    with monkeypatch.context() as scoped:
        scoped.setattr(repository, "push", concurrent_change)
        assert helper["publish"](record, operation)["state"] == "conflict"
    before = app.store("sea").snapshot().revision
    result = command(tmp_path, *continue_args(bindings["bob"], record), success=not revoked)
    assert app.store("sea").snapshot().bytes("other-owner.txt") == b"keep concurrent content"
    if revoked:
        assert not result["ok"] and app.store("sea").snapshot().revision == before
        assert app.store("sea").snapshot().bytes(".agentworkspace/acks/original.json") is None
    else:
        assert result["state"] == "published" and len(result["targets"][0]["attempts"]) == 2
    assert not command(tmp_path, *continue_args("copied-new-binding", record), success=False)["ok"]


def test_concurrent_ack_publishers_create_one_ack(pair, tmp_path):
    app, bindings, repo = seeded(pair, tmp_path)
    before = app.store("sea").snapshot().revision
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda number: command(tmp_path, *receive_args(repo, bindings["bob"], tmp_path / f"ack-{number}.json"), "--publish"), range(2)))
    assert all(result.get("already_acknowledged") or result.get("state") == "published" for result in results)
    after = app.store("sea").snapshot()
    assert after.json(".agentworkspace/acks/original.json") == {"message_id": "original"}
    count = subprocess.run(["git", "-C", str(repo), "rev-list", "--count", f"{before}..{after.revision}"],
                           capture_output=True, text=True, check=True)
    assert count.stdout.strip() == "1"


def test_helper_operation_cannot_write_non_message_paths(pair, tmp_path):
    app, bindings, repo = seeded(pair, tmp_path)
    record = tmp_path / "ack.json"
    operation = command(tmp_path, *receive_args(repo, bindings["bob"], record))
    operation["records"]["agents/alice.json"] = base64.b64encode(b"forbidden").decode()
    record.write_bytes(encode(operation))
    before = app.store("sea").snapshot().revision
    assert not command(tmp_path, *continue_args(bindings["bob"], record), success=False)["ok"]
    assert app.store("sea").snapshot().revision == before
