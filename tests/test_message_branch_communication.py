"""Message-branch behavior with real isolated Git and no native model sessions."""
import base64
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

from agent_workspace import layout, maintenance, message_store, web_courier
from agent_workspace.app import App
from agent_workspace.direct_messages import DirectMessages
from agent_workspace.gitstore import GitStore
from agent_workspace.messages import Messages
from agent_workspace.util import Conflict, Error, encode, read_json, write_json


SCRIPT = Path(__file__).parents[1] / "src/agent_workspace/resources/skills/message/scripts/message_git.py"


@pytest.fixture
def branch_team(tmp_path):
    app = App(tmp_path / "home")
    app.workspace_init("sea", str(tmp_path / "sea.git"))
    app.create("sea", "team")
    app.worker_create("sea", "team", "Topic", "Independent topic", worker_id="topic")
    bindings = {}
    for wid in ("default", "topic"):
        bid = app.reserve("sea", "team", worker_id=wid)["binding"]
        app.bind("sea", "team", bid, "native-" + wid, worker_id=wid)
        bindings[wid] = bid
    return app, bindings


class Adapter:
    def __init__(self):
        self.calls = []
        self.busy = False

    def status(self):
        return "busy" if self.busy else "idle"

    def notify(self, prompt, delivery):
        self.calls.append((prompt, delivery))


def test_worker_message_reply_fifo_and_ack_only_change_message_branch(branch_team):
    app, ids = branch_team
    messages = Messages(app)
    store = app.store("sea")
    native = DirectMessages(app).record("sea", "team", ids["default"], "team", "reported native send",
                                       to_worker="topic", request_id="native")
    assert native["recorded"]
    first = messages.send("sea", "team", ids["topic"], "team", "frozen recipient", request_id="first")
    original = store.message_snapshot().messages.bytes(".agentworkspace/messages/first.json")
    app.worker_default("sea", "team", "topic", app.show("sea", "team")["revision"])
    baseline = store.message_snapshot()
    assert first["payload"]["to"]["worker"] == "default"
    assert messages.send("sea", "team", ids["topic"], "team", "frozen recipient", request_id="first")["payload"] == first["payload"]
    with pytest.raises(Conflict):
        messages.receive("sea", "team", ids["topic"], "first")
    assert messages.receive("sea", "team", ids["default"], "first")["publication"]["state"] == "published"
    assert messages.receive("sea", "team", ids["default"], "first")["already_acknowledged"]
    reply = messages.send("sea", "team", ids["default"], content="explicit reply", reply_to="first", request_id="reply")
    assert reply["payload"]["to"]["worker"] == "topic"
    messages.send("sea", "team", ids["default"], "team", "insert next", delivery="insert", request_id="insert")
    adapter = Adapter()
    assert messages.poll("sea", "team", ids["topic"], adapter=adapter)["message_id"] == "reply"
    assert messages.poll("sea", "team", ids["topic"], adapter=adapter)["state"] == "waiting_ack"
    messages.receive("sea", "team", ids["topic"], "reply")
    adapter.busy = True
    assert messages.poll("sea", "team", ids["topic"], adapter=adapter)["message_id"] == "insert"
    assert [delivery for _, delivery in adapter.calls] == ["normal", "insert"]
    observed = store.message_snapshot()
    assert observed.branch == "aw-messages" and observed.main.revision == baseline.main.revision
    assert observed.messages.bytes(".agentworkspace/messages/first.json") == original
    assert observed.messages.json(".agentworkspace/acks/first.json") == {"message_id": "first"}
    assert not any(path.startswith(tuple(".agentworkspace/" + root + "/" for root in layout.MESSAGE_ROOTS))
                   for path in observed.main.entries)
    assert observed.main.json(".agentworkspace/direct-messages/native.json") == native["record"]
    assert observed.messages.bytes(".agentworkspace/direct-messages/native.json") is None
    report = maintenance.doctor(app, "sea")
    assert report["unacknowledged_notifications"] == {"team#topic": 1}
    assert report["message_branch"] == "aw-messages" and report["message_revision"] == observed.messages.revision
    assert report["revision"] == observed.main.revision


@pytest.mark.parametrize("action", ["send", "ack", "dispatch"])
def test_permission_change_between_main_check_and_message_write_blocks_action(branch_team, monkeypatch, action):
    app, ids = branch_team
    store, messages = app.store("sea"), Messages(app)
    actor = "default" if action == "send" else "topic"
    if action != "send":
        messages.send("sea", "team", ids["default"], "team", "original", to_worker="topic", request_id="race-seed")
    point = app.checkpoint("sea", "team", "explicit test stop", binding=ids[actor], worker_id=actor)
    before = store.message_snapshot()
    change = GitStore.message_change
    revoked = []

    def revoke(store, state, changes, expected, description, **kwargs):
        if not revoked:
            revoked.append(ids[actor])
            app.stop("sea", "team", ids[actor], point["id"], worker_id=actor)
        return change(store, state, changes, expected, description, **kwargs)

    monkeypatch.setattr(GitStore, "message_change", revoke)
    adapter = Adapter()
    if action == "send":
        assert messages.send("sea", "team", ids["default"], "team", "new", to_worker="topic",
                             request_id="raced")["state"] == "pending"
    elif action == "ack":
        assert messages.receive("sea", "team", ids["topic"], "race-seed")["publication"]["state"] == "pending"
    else:
        with pytest.raises(Conflict):
            messages.poll("sea", "team", ids["topic"], adapter=adapter)
    assert revoked == [ids[actor]] and adapter.calls == []
    after = store.message_snapshot()
    assert after.messages.bytes(layout.MESSAGE_GUARD) != before.messages.bytes(layout.MESSAGE_GUARD)
    assert {p: blob for p, blob in after.messages.entries.items() if p != layout.MESSAGE_GUARD} == {
        p: blob for p, blob in before.messages.entries.items() if p != layout.MESSAGE_GUARD}
    assert after.main.json(layout.shared_path(after.main, f"bindings/{ids[actor]}.json"))["phase"] == "stopping"
    sibling = "topic" if actor == "default" else "default"
    assert after.main.json(layout.shared_path(after.main, f"bindings/{ids[sibling]}.json"))["phase"] == "active"


@pytest.mark.parametrize("raced_record", ["ack", "messages", "message-index"])
def test_claim_preserves_ack_and_original_record_conditions_on_message_branch(branch_team, monkeypatch, raced_record):
    app, ids = branch_team
    store, messages = app.store("sea"), Messages(app)
    messages.send("sea", "team", ids["default"], "team", "original", to_worker="topic", request_id="head")
    before = store.message_snapshot()
    change = GitStore.message_change
    injected = []

    def race(store, state, changes, expected, description, **kwargs):
        if description == "Claim notification attempt" and not injected:
            injected.append(raced_record)
            if raced_record == "ack":
                assert messages.receive("sea", "team", ids["topic"], "head")["publication"]["state"] == "published"
            else:
                current = store.message_snapshot()
                path = layout.shared_path(current.messages, f"{raced_record}/head.json")
                record = current.messages.json(path)
                record["future_field"] = "changed before claim"
                change(store, current, {path: encode(record)}, {path: current.messages.entries[path]},
                       "Isolated original-record change")
        return change(store, state, changes, expected, description, **kwargs)

    monkeypatch.setattr(GitStore, "message_change", race)
    adapter = Adapter()
    with pytest.raises(Conflict):
        messages.poll("sea", "team", ids["topic"], adapter=adapter)
    assert injected == [raced_record] and adapter.calls == []
    after = store.message_snapshot()
    assert after.main.revision == before.main.revision
    assert after.messages.bytes(".agentworkspace/dispatch/team/topic.json") is None
    if raced_record == "ack":
        assert after.messages.json(".agentworkspace/acks/head.json") == {"message_id": "head"}


def test_message_read_failure_does_not_hide_other_worker_diagnostics(branch_team, monkeypatch):
    app, ids = branch_team
    root = app.root("sea", "team")
    write_json(layout.local_path(root, "inputs/unknown.json", worker_id="topic"),
               {"id": "unknown", "binding": ids["topic"], "state": "outcome_unknown"})
    before = app.store("sea").snapshot().revision

    def unavailable(store):
        raise Error("Isolated message branch unavailable")

    monkeypatch.setattr(GitStore, "message_snapshot", unavailable)
    report = maintenance.doctor(app, "sea")
    assert report["unacknowledged_notifications"] is None
    assert report["message_revision"] is None and report["message_branch"] is None
    assert any(row["code"] == "message_observation_failed" for row in report["issues"])
    assert any(row["code"] == "input_outcome_unknown" and row["worker"] == "topic" for row in report["issues"])
    assert report["revision"] == app.store("sea").snapshot().revision == before


def test_web_courier_reads_worker_dispatch_and_ack_from_message_branch(branch_team):
    app, ids = branch_team
    store, messages = app.store("sea"), Messages(app)
    before = store.snapshot().revision
    extension = "a" * 32
    connections = {}
    for wid, bid in ids.items():
        connections[wid] = web_courier.connect(app, "sea", "team", bid, "https://chatgpt.com/c/native-" + wid,
                                              extension, "connection-" + wid, worker_id=wid)
    messages.send("sea", "team", ids["default"], "team", "manual notification", to_worker="topic", request_id="web")
    default, topic = connections["default"], connections["topic"]
    origin = "chrome-extension://" + extension
    assert web_courier.handle(app, default["connection_id"], default["token"], origin, {"action": "get"})["state"] == "empty"
    preview = web_courier.handle(app, topic["connection_id"], topic["token"], origin, {"action": "get"})
    assert preview["notification"]["worker"] == "topic"
    claimed = web_courier.handle(app, topic["connection_id"], topic["token"], origin,
        {"action": "begin", "message_id": "web", "attempt_id": "web-attempt", "binding": ids["topic"],
         "target_url": topic["target_url"], "prompt_digest": preview["prompt_digest"]})
    assert claimed["state"] == "claimed" and web_courier.status(app, topic["connection_id"])["ack"] is None
    messages.receive("sea", "team", ids["topic"], "web")
    observed = web_courier.status(app, topic["connection_id"])
    assert observed["ack"] == {"message_id": "web"} and observed["attempt"]["claim_state"] == "confirmed"
    assert observed["worker"] == "topic" and store.snapshot().revision == before


def legacy_workspace(app, name, path, version):
    GitStore.initialize(path)
    store = GitStore(str(path), app.home)
    prefix = ".agentworkspace/" if version else ""
    metadata = {"schema": 1, "name": name, "locator": "local:" + name, "friends": {}, "projects": {}}
    files = {prefix + "workspace.json": encode(metadata)}
    if version:
        files[layout.MARKER] = layout.marker("workspace", version=version)
    store.branch("main", files)
    app.workspace_connect(name, str(path))


def clone_repo(tmp_path, app, workspace, name):
    path = tmp_path / name
    subprocess.run(["git", "clone", "--bare", app.store(workspace).address, str(path)],
                   check=True, capture_output=True, timeout=120)
    return path


def script(tmp_path, *arguments, success=True):
    result = subprocess.run([sys.executable, "-I", "-S", str(SCRIPT), *map(str, arguments)],
                            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("version", [0, 1])
def test_old_partial_publication_continues_after_explicit_message_migration(tmp_path, monkeypatch, version):
    import agent_workspace.messages as message_module

    app = App(tmp_path / "home")
    legacy_workspace(app, "left", tmp_path / "left.git", version)
    app.workspace_init("right", str(tmp_path / "right.git"), worker_support=False)
    ids = {}
    for workspace, aid in (("left", "alice"), ("right", "bob")):
        app.create(workspace, aid)
        bid = app.reserve(workspace, aid)["binding"]
        app.bind(workspace, aid, bid, "native-" + aid)
        ids[workspace] = bid
    app.relation("left", "friends", "add", "right", app.store("right").address)
    app.relation("right", "friends", "add", "left", app.store("left").address)
    messages = Messages(app)
    original_open = message_module.open_store

    def offline(address, home):
        if address == app.store("right").address:
            raise Error("Isolated peer unavailable before its first write")
        return original_open(address, home)

    with monkeypatch.context() as fault:
        fault.setattr(message_module, "open_store", offline)
        pending = messages.send("left", "alice", ids["left"], "right/bob", "original\n中文", request_id="cross")
    assert pending["state"] == "pending" and pending["completed"] == [app.store("left").address]
    left = app.store("left")
    before = left.snapshot()
    old_path = layout.shared_path(before, "messages/cross.json")
    raw = before.bytes(old_path)
    binding_path = layout.shared_path(before, f"bindings/{ids['left']}.json")
    original_binding = before.bytes(binding_path)
    root = app.root("left", "alice")
    instance_marker = (root / layout.MARKER).read_bytes()
    migrated = message_store.migrate(app, "left", "explicit-message-migration", compatible_writers=["message-v3"])
    assert migrated["state"] == "published" and migrated["starts_session"] is False
    baseline = {workspace: app.store(workspace).snapshot().revision for workspace in ("left", "right")}
    assert messages.reconcile("cross")["payload"] == pending["payload"]
    assert messages.receive("right", "bob", ids["right"], "cross")["publication"]["state"] == "published"
    for workspace in ("left", "right"):
        state = app.store(workspace).message_snapshot()
        assert state.branch == "aw-messages" and state.main.revision == baseline[workspace]
        assert state.messages.bytes(layout.shared_path(state.messages, "messages/cross.json")) == raw
        assert state.messages.json(layout.shared_path(state.messages, "acks/cross.json")) == {"message_id": "cross"}
    state = left.message_snapshot()
    assert state.main.bytes(binding_path) == original_binding
    assert (root / layout.MARKER).read_bytes() == instance_marker
    assert "worker_schema" not in app.agent("left", "alice")

    # Simulate an unmanaged old writer leaving a same-ID copy on main.
    repo = runpy.run_path(str(SCRIPT))["Repository"](clone_repo(tmp_path, app, "left", "stale-main-cache"))
    commit = repo.commit(state.main.revision, {old_path: raw})
    assert repo.push(commit, state.main.revision).returncode == 0
    current = left.message_snapshot()
    path = layout.shared_path(current.messages, "messages/cross.json")
    left.message_change(current, {path: None}, {path: current.messages.entries[path]}, "Isolated missing message body")
    assert left.snapshot().bytes(old_path) == raw
    with pytest.raises(Error):
        messages.show("left", "cross")


def test_standalone_script_reads_acks_and_replies_on_sampled_message_branch(branch_team, tmp_path):
    app, ids = branch_team
    store, messages = app.store("sea"), Messages(app)
    messages.send("sea", "team", ids["default"], "team", "原文\n```text```", to_worker="topic", request_id="original")
    repo = clone_repo(tmp_path, app, "sea", "script-cache")
    actor = ("--repo", repo, "--agent", "team", "--binding", ids["topic"], "--id", "original")
    original = store.message_snapshot().messages.bytes(".agentworkspace/messages/original.json")
    shown = script(tmp_path, "show", *actor)
    assert shown["message_json"].encode() == original
    baseline = store.snapshot().revision
    ack = script(tmp_path, "receive", *actor, "--record", tmp_path / "ack.json", "--publish")
    assert ack["state"] == "published" and ack["targets"][0]["branch"] == "aw-messages"
    assert store.snapshot().revision == baseline
    assert store.message_snapshot().messages.json(".agentworkspace/acks/original.json") == {"message_id": "original"}
    duplicate_path = tmp_path / "duplicate.json"
    assert script(tmp_path, "receive", *actor, "--record", duplicate_path)["already_acknowledged"]
    assert not duplicate_path.exists()
    content = tmp_path / "reply.md"
    content.write_text("回复原 Worker\n保留时间", encoding="utf-8")
    record = tmp_path / "reply-operation.json"
    prepared = script(tmp_path, "reply", *actor, "--content-file", content,
                      "--request-id", "reply-once", "--record", record)
    original_records = dict(prepared["records"])
    app.worker_default("sea", "team", "topic", app.show("sea", "team")["revision"])
    baseline = store.snapshot().revision
    published = script(tmp_path, "continue", "--agent", "team", "--binding", ids["topic"], "--record", record)
    assert published["state"] == "published" and published["records"] == original_records
    state = store.message_snapshot()
    reply = state.messages.json(".agentworkspace/messages/reply-once.json")
    assert reply["to"]["worker"] == "default" and reply["reply_to"] == "original"
    assert state.messages.bytes(".agentworkspace/messages/reply-once.json") == base64.b64decode(original_records["messages/reply-once.json"])
    assert state.main.revision == baseline


def test_standalone_script_message_lease_rejects_revocation_after_main_read(branch_team, tmp_path, monkeypatch):
    app, ids = branch_team
    store, messages = app.store("sea"), Messages(app)
    messages.send("sea", "team", ids["default"], "team", "original", to_worker="topic", request_id="original")
    point = app.checkpoint("sea", "team", "explicit script stop", binding=ids["topic"], worker_id="topic")
    repo = clone_repo(tmp_path, app, "sea", "script-race-cache")
    record = tmp_path / "script-race.json"
    operation = script(tmp_path, "receive", "--repo", repo, "--agent", "team", "--binding", ids["topic"],
                       "--id", "original", "--record", record)
    helper = runpy.run_path(str(SCRIPT))
    repository = helper["Repository"]
    commit = repository.commit
    revoked = []

    def revoke(repo, parent, records):
        if not revoked:
            revoked.append(ids["topic"])
            app.stop("sea", "team", ids["topic"], point["id"], worker_id="topic")
        return commit(repo, parent, records)

    monkeypatch.setattr(repository, "commit", revoke)
    rejected = helper["publish"](record, operation)
    assert revoked == [ids["topic"]] and rejected["state"] == "conflict"
    after = store.message_snapshot()
    assert after.messages.bytes(".agentworkspace/acks/original.json") is None
    original_journal = record.read_bytes()
    result = script(tmp_path, "continue", "--record", record, "--agent", "team", "--binding", ids["topic"], success=False)
    assert result["error_type"] == "ProtocolError" and record.read_bytes() == original_journal
    assert store.message_snapshot().messages.revision == after.messages.revision


@pytest.mark.parametrize("landed", [False, True])
def test_standalone_script_unknown_message_branch_write_is_only_observed(branch_team, tmp_path, monkeypatch, landed):
    app, ids = branch_team
    store = app.store("sea")
    Messages(app).send("sea", "team", ids["default"], "team", "original", to_worker="topic", request_id="original")
    repo = clone_repo(tmp_path, app, "sea", "script-unknown-cache")
    record = tmp_path / "script-unknown.json"
    operation = script(tmp_path, "receive", "--repo", repo, "--agent", "team", "--binding", ids["topic"],
                       "--id", "original", "--record", record)
    helper = runpy.run_path(str(SCRIPT))
    repository = helper["Repository"]
    push, ref = repository.push, repository.ref
    attempts = []

    def lost(repo, revision, parent, **kwargs):
        attempts.append((revision, parent, kwargs["branch"]))
        if landed:
            push(repo, revision, parent, **kwargs)
        raise subprocess.TimeoutExpired("isolated git push", 1)

    def unreadable(repo, branch, **kwargs):
        if attempts and branch == "aw-messages":
            raise helper["ProtocolError"]("Isolated message readback unavailable")
        return ref(repo, branch, **kwargs)

    with monkeypatch.context() as fault:
        fault.setattr(repository, "push", lost)
        fault.setattr(repository, "ref", unreadable)
        assert helper["publish"](record, operation)["state"] == "outcome_unknown"
    assert len(attempts) == 1 and attempts[0][2] == "aw-messages"

    def no_replay(*args, **kwargs):
        raise AssertionError("An unknown original message-branch write cannot be pushed again")

    monkeypatch.setattr(repository, "push", no_replay)
    before = store.message_snapshot()
    for _ in range(2):
        assert helper["publish"](record, operation)["state"] == ("published" if landed else "outcome_unknown")
    after = store.message_snapshot()
    assert after.main.revision == before.main.revision and after.messages.revision == before.messages.revision
