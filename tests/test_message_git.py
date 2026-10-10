"""Real isolated Git publication with a child Python that cannot import AW."""
import base64
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

from agent_workspace.messages import Messages
from agent_workspace.util import encode


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


def test_script_without_aw_reads_acknowledges_and_replies(pair, tmp_path):
    app, bindings, repo = seeded(pair, tmp_path)
    unavailable = subprocess.run([sys.executable, "-I", "-S", "-c",
                                  "import importlib.util; assert importlib.util.find_spec('agent_workspace') is None"],
                                 cwd=tmp_path, capture_output=True)
    assert unavailable.returncode == 0
    original = app.store("sea").snapshot().bytes("messages/original.json")
    shown = command(tmp_path, "show", "--repo", repo, "--agent", "bob", "--binding", bindings["bob"], "--id", "original")
    assert shown["message_json"].encode() == original and shown["ack"] is None
    record = tmp_path / "ack-operation.json"
    assert command(tmp_path, *receive_args(repo, bindings["bob"], record))["state"] == "prepared"
    assert app.store("sea").snapshot().bytes("acks/original.json") is None
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
    assert app.store("sea").snapshot().bytes("messages/original.json") == original
    assert command(tmp_path, *continue_args(bindings["bob"], operation))["state"] == "published"


@pytest.mark.parametrize("damaged", [None, b"broken JSON"])
def test_script_confirms_notification_when_body_missing_or_damaged(pair, tmp_path, damaged):
    app, bindings, repo = seeded(pair, tmp_path)
    app.store("sea").change("main", {"messages/original.json": damaged}, {}, "isolated body fault")
    result = command(tmp_path, *receive_args(repo, bindings["bob"], tmp_path / "ack.json"), "--publish")
    assert result["state"] == "published" and result["read_result"]["read_error"]
    assert app.store("sea").snapshot().json("acks/original.json") == {"message_id": "original"}


def test_cross_workspace_partial_reply_continues_original_bytes(pair, tmp_path, monkeypatch):
    app, bindings = pair
    app.workspace_init("peer", str(tmp_path / "peer.git"))
    app.create("peer", "sender")
    sender = app.reserve("peer", "sender")["binding"]
    app.bind("peer", "sender", sender, "isolated-sender-session")
    app.relation("sea", "friends", "add", "peer", app.store("peer").address)
    app.relation("peer", "friends", "add", "sea", app.store("sea").address)
    Messages(app).send("peer", "sender", sender, "sea/bob", "cross question", request_id="original")
    own, peer = clone(tmp_path, app, "sea", "own-cache"), clone(tmp_path, app, "peer", "peer-cache")
    ack = command(tmp_path, *receive_args(own, bindings["bob"], tmp_path / "ack.json"), "--peer", peer, "--publish")
    assert ack["state"] == "published"
    assert app.store("sea").snapshot().bytes("acks/original.json") == app.store("peer").snapshot().bytes("acks/original.json")
    reply = tmp_path / "reply.md"
    reply.write_text("cross reply", encoding="utf-8")
    record = tmp_path / "reply.json"
    operation = command(tmp_path, "reply", "--repo", own, "--peer", peer, "--agent", "bob", "--binding", bindings["bob"],
                        "--id", "original", "--content-file", reply, "--request-id", "reply-one", "--record", record)
    helper = load_helper()
    repository = helper["Repository"]
    head = repository.head

    def unavailable(repo):
        if repo.path == str(peer.resolve()):
            raise helper["ProtocolError"]("isolated peer read unavailable before any peer write")
        return head(repo)

    with monkeypatch.context() as scoped:
        scoped.setattr(repository, "head", unavailable)
        with pytest.raises(helper["ProtocolError"]):
            helper["publish"](record, operation)
    before = app.store("sea").snapshot()
    original_reply = before.bytes("messages/reply-one.json")
    assert original_reply is not None and app.store("peer").snapshot().bytes("messages/reply-one.json") is None
    assert command(tmp_path, *continue_args(bindings["bob"], record))["state"] == "published"
    assert app.store("sea").snapshot().revision == before.revision
    assert app.store("peer").snapshot().bytes("messages/reply-one.json") == original_reply
    assert app.store("peer").snapshot().bytes("message-index/reply-one.json") == before.bytes("message-index/reply-one.json")


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
            agent = snap.json("agents/bob.json")
            agent["current"] = None
            entry = snap.json(f"bindings/{bindings['bob']}.json")
            entry["phase"] = "released"
            changes.update({"agents/bob.json": encode(agent), f"bindings/{bindings['bob']}.json": encode(entry)})
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
        assert app.store("sea").snapshot().bytes("acks/original.json") is None
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
    assert after.json("acks/original.json") == {"message_id": "original"}
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
