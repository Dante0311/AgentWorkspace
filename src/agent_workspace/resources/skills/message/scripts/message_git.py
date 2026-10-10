"""Optional Message/ACK helper: Python standard library and Git, no AW installation.

Use prepared bare clones with origin. Never creates an Agent, Binding or session.
Operation files are private helper journals, not AW publication receipts.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


class ProtocolError(RuntimeError):
    pass


def identifier(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
        raise ProtocolError("IDs must contain 1-64 ASCII letters, digits, underscores or hyphens.")
    return value


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".message-operation-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encode(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def operation_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ProtocolError("Operation is locked. Inspect the original process; do not remove a live lock.") from exc
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        lock.unlink()


class Repository:
    def __init__(self, path):
        self.path = str(Path(path).resolve())

    def git(self, *args, data=None, env=None, check=True):
        settings = dict(os.environ, GIT_TERMINAL_PROMPT="0")
        settings.update(env or {})
        result = subprocess.run(["git", "-c", "credential.interactive=false", "-C", self.path, *args],
                                input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=settings, timeout=60)
        if check and result.returncode:
            # Git diagnostics may include credential-bearing remote URLs.
            raise ProtocolError(f"Git {args[0]} failed ({result.returncode}); no publication is confirmed.")
        return result

    def head(self):
        rows = self.git("ls-remote", "--heads", "origin", "refs/heads/main").stdout.splitlines()
        if len(rows) != 1:
            raise ProtocolError("Expected an existing Workspace main branch.")
        head = rows[0].split()[0].decode("ascii")
        self.git("fetch", "--quiet", "--no-tags", "origin", head)
        return head

    def read(self, head, path):
        row = self.git("ls-tree", "-z", head, "--", path).stdout
        if not row:
            return None
        metadata, name = row.rstrip(b"\0").split(b"\t", 1)
        mode, kind, blob = metadata.split()
        if kind != b"blob" or mode not in (b"100644", b"100755") or name.decode() != path:
            raise ProtocolError("Protocol records must be regular files.")
        return self.git("cat-file", "blob", blob.decode()).stdout

    def json(self, head, path):
        value = self.read(head, path)
        return None if value is None else json.loads(value)

    def commit(self, parent, records):
        # A separate index keeps the user's checkout/index untouched.
        with tempfile.TemporaryDirectory(prefix="message-index-") as directory:
            env = {"GIT_INDEX_FILE": str(Path(directory) / "index"),
                   "GIT_AUTHOR_NAME": "Message protocol", "GIT_AUTHOR_EMAIL": "message@localhost",
                   "GIT_COMMITTER_NAME": "Message protocol", "GIT_COMMITTER_EMAIL": "message@localhost"}
            self.git("read-tree", parent, env=env)
            entries = []
            for path, content in records.items():
                blob = self.git("hash-object", "-w", "--stdin", data=content).stdout.strip()
                entries.append(b"100644 " + blob + b"\t" + path.encode() + b"\0")
            self.git("update-index", "-z", "--index-info", data=b"".join(entries), env=env)
            tree = self.git("write-tree", env=env).stdout.strip().decode()
            return self.git("commit-tree", tree, "-p", parent,
                            data=b"Publish original Message protocol records\n", env=env).stdout.strip().decode()

    def push(self, commit, parent):
        # commit is a direct child of parent: exact lease, never history rewriting.
        return self.git("push", "--porcelain", f"--force-with-lease=refs/heads/main:{parent}",
                        "origin", f"{commit}:refs/heads/main", check=False)


def actor_at(repo, head, agent, binding):
    agent, binding = identifier(agent), identifier(binding)
    meta = repo.json(head, "workspace.json")
    actor = repo.json(head, f"agents/{agent}.json")
    entry = repo.json(head, f"bindings/{binding}.json")
    if (not meta or not actor or actor.get("archived") or actor.get("current") != binding
            or not entry or entry.get("id") != binding or entry.get("agent") != agent or entry.get("phase") != "active"):
        raise ProtocolError("The explicitly granted Binding is not this instance's current active entry.")
    return meta


def notification_at(repo, head, meta, agent, message_id):
    index = repo.json(head, f"message-index/{identifier(message_id)}.json")
    if not index or index.get("id") != message_id or index.get("to") != {"workspace": meta["locator"], "agent": agent}:
        raise ProtocolError("The trusted notification index does not target this instance.")
    return index


def targets_for(own, meta, peer_path, locator):
    if locator == meta["locator"]:
        return [{"repo": own.path, "locator": locator}]
    if not peer_path or not any(friend.get("locator") == locator for friend in meta.get("friends", {}).values()):
        raise ProtocolError("Cross-Workspace publication needs the explicit current friend repository.")
    peer = Repository(peer_path)
    other = peer.json(peer.head(), "workspace.json")
    if not other or other.get("locator") != locator:
        raise ProtocolError("The supplied peer repository has a different Workspace locator.")
    return [{"repo": own.path, "locator": meta["locator"]}, {"repo": peer.path, "locator": locator}]


def prepare(args, own, head, meta, index):
    if args.action == "receive":
        existing = own.read(head, f"acks/{args.id}.json")
        if existing is not None:
            if json.loads(existing) != {"message_id": args.id}:
                raise ProtocolError("Existing ACK is damaged or has different fields; do not replace it.")
            return {"message_id": args.id, "already_acknowledged": True,
                    "instruction": "Do not repeat business. Continue an incomplete original operation file separately."}
    raw = own.read(head, f"messages/{args.id}.json")
    result = {"message_id": args.id}
    try:
        if raw is None:
            raise ValueError("Message body unavailable")
        text = raw.decode("utf-8")
        body = json.loads(text)
        if (not isinstance(body, dict) or any(body.get(key) != index[key] for key in ("id", "from", "to", "created_at", "delivery"))
                or not isinstance(body.get("content"), str) or not body["content"].strip()
                or not isinstance(body.get("message_refs", []), list)):
            raise ValueError("Message does not match its notification index")
        result["message_json"] = text
    except ValueError as exc:
        result["read_error"] = str(exc)
    if args.action == "show":
        return {**result, "index": index, "ack": own.json(head, f"acks/{args.id}.json")}
    if args.action == "receive":
        payload = {"message_id": args.id}
        records = {f"acks/{args.id}.json": encode(payload)}
        locator = index["from"]["workspace"]
    else:
        content = Path(args.content_file).read_bytes().decode("utf-8")
        if not content.strip():
            raise ProtocolError("Reply content must be non-empty.")
        payload = {"id": identifier(args.request_id), "from": {"workspace": meta["locator"], "agent": args.agent},
                   "to": index["from"], "created_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                   "message_refs": list(dict.fromkeys([args.id, *args.ref])), "delivery": args.delivery, "content": content}
        for ref in payload["message_refs"]:
            identifier(ref)
        records = {f"messages/{payload['id']}.json": encode(payload),
                   f"message-index/{payload['id']}.json": encode({key: payload[key] for key in ("id", "from", "to", "created_at", "delivery")})}
        locator = payload["to"]["workspace"]
    return {"format": "message-git-operation-v1", "kind": "ack" if args.action == "receive" else "message",
            "actor": {"workspace": meta["locator"], "agent": args.agent, "binding": args.binding},
            "source_id": args.id, "source_index": base64.b64encode(own.read(head, f"message-index/{args.id}.json")).decode(),
            "records": {path: base64.b64encode(value).decode() for path, value in records.items()},
            "read_result": result, "targets": targets_for(own, meta, args.peer, locator), "state": "prepared"}


def original_records(operation):
    if operation.get("format") != "message-git-operation-v1":
        raise ProtocolError("Not a helper operation file; AW receipts are not accepted.")
    actor = operation["actor"]
    identifier(actor["agent"])
    identifier(actor["binding"])
    source_id = identifier(operation["source_id"])
    source = json.loads(base64.b64decode(operation["source_index"], validate=True))
    if source["id"] != source_id or source["to"] != {"workspace": actor["workspace"], "agent": actor["agent"]}:
        raise ProtocolError("Operation source does not target its explicitly granted actor.")
    records = {key: base64.b64decode(value, validate=True) for key, value in operation["records"].items()}
    if operation["kind"] == "ack":
        if records != {f"acks/{source_id}.json": encode({"message_id": source_id})}:
            raise ProtocolError("ACK operations contain only the original single-field ACK.")
        destination = source["from"]["workspace"]
    elif operation["kind"] == "message":
        bodies = [value for key, value in records.items() if key.startswith("messages/")]
        if len(bodies) != 1:
            raise ProtocolError("A reply operation contains exactly one Message.")
        body = json.loads(bodies[0])
        mid = identifier(body["id"])
        if (body["from"] != {"workspace": actor["workspace"], "agent": actor["agent"]}
                or body["to"] != source["from"] or body["delivery"] not in ("normal", "insert")
                or not isinstance(body["content"], str) or not body["content"].strip()
                or not isinstance(body["message_refs"], list) or source_id not in body["message_refs"]):
            raise ProtocolError("Reply differs from the original actor, target or message relation.")
        for ref in body["message_refs"]:
            identifier(ref)
        created = datetime.fromisoformat(body["created_at"])
        if created.tzinfo is None:
            raise ProtocolError("Message time must include its timezone.")
        expected = {f"messages/{mid}.json": bodies[0], f"message-index/{mid}.json": encode({
            key: body[key] for key in ("id", "from", "to", "created_at", "delivery")})}
        if records != expected:
            raise ProtocolError("Reply contains unexpected paths or a different index.")
        destination = body["to"]["workspace"]
    else:
        raise ProtocolError("Only Message and ACK records can be published.")
    locators = [actor["workspace"]] if destination == actor["workspace"] else [actor["workspace"], destination]
    if [target["locator"] for target in operation["targets"]] != locators:
        raise ProtocolError("Operation destinations differ from the original Message route.")
    return records


def publish(path, operation):
    records = original_records(operation)
    own = Repository(operation["targets"][0]["repo"])
    actor = operation["actor"]
    for target in operation["targets"]:
        head = own.head()
        meta = actor_at(own, head, actor["agent"], actor["binding"])
        if meta["locator"] != actor["workspace"] or own.read(head, f"message-index/{operation['source_id']}.json") != base64.b64decode(operation["source_index"]):
            raise ProtocolError("The original Workspace or notification index changed.")
        repo = own if target["repo"] == own.path else Repository(target["repo"])
        if repo is not own and not any(friend.get("locator") == target["locator"] for friend in meta.get("friends", {}).values()):
            raise ProtocolError("The original friend route was removed; no peer write is authorized.")
        parent = head if repo is own else repo.head()
        if repo.json(parent, "workspace.json")["locator"] != target["locator"]:
            raise ProtocolError("Target Workspace changed.")
        missing = {}
        for record, content in records.items():
            existing = repo.read(parent, record)
            if existing is None:
                missing[record] = content
            elif existing != content:
                raise ProtocolError("Original ID has different bytes; refusing overwrite.")
        if not missing:
            target["state"] = "confirmed"
            save(path, operation)
            continue
        if target.get("state") == "outcome_unknown":
            operation["state"] = "outcome_unknown"
            save(path, operation)
            return operation  # Only inspect an uncertain write; never push it again.
        if operation["kind"] == "message":
            body = json.loads(next(content for record, content in records.items() if record.startswith("messages/")))
            if target["locator"] == body["to"]["workspace"]:
                receiver = repo.json(parent, f"agents/{identifier(body['to']['agent'])}.json")
                if not receiver or receiver.get("archived"):
                    raise ProtocolError("Reply target is missing or archived.")
        commit = repo.commit(parent, missing)
        target.setdefault("attempts", []).append({"parent": parent, "commit": commit})
        target.update(parent=parent, commit=commit, state="outcome_unknown")
        operation["state"] = "outcome_unknown"
        save(path, operation)  # Preserve the original commit before the possibly ambiguous write.
        try:
            pushed = repo.push(commit, parent)
        except (subprocess.TimeoutExpired, OSError):
            pushed = None
        try:
            current = repo.head()
            confirmed = all(repo.read(current, record) == content for record, content in records.items())
        except (ProtocolError, subprocess.TimeoutExpired, OSError):
            confirmed = False
        if not confirmed:
            if pushed is not None and b"[rejected]" in pushed.stdout and b"(stale info)" in pushed.stdout:
                target["state"] = "conflict"
                operation["state"] = "conflict"
            save(path, operation)
            return operation
        target["state"] = "confirmed"
        save(path, operation)
    operation["state"] = "published"
    save(path, operation)
    return operation


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    for name in ("show", "receive", "reply"):
        action = actions.add_parser(name)
        for field in ("repo", "agent", "binding", "id"):
            action.add_argument("--" + field, required=True)
        action.add_argument("--peer")
        if name != "show":
            action.add_argument("--record", required=True)
            action.add_argument("--publish", action="store_true")
        if name == "reply":
            action.add_argument("--content-file", required=True)
            action.add_argument("--request-id", required=True)
            action.add_argument("--delivery", choices=("normal", "insert"), default="normal")
            action.add_argument("--ref", action="append", default=[])
    resume = actions.add_parser("continue")
    resume.add_argument("--record", required=True)
    resume.add_argument("--agent", required=True)
    resume.add_argument("--binding", required=True)
    args = parser.parse_args(argv)
    if args.action == "continue":
        path = Path(args.record).resolve()
        with operation_lock(path):
            operation = json.loads(path.read_bytes())
            if (operation["actor"]["agent"], operation["actor"]["binding"]) != (args.agent, args.binding):
                raise ProtocolError("Continue requires this session's explicitly granted original actor and Binding.")
            result = publish(path, operation)
    else:
        own = Repository(args.repo)
        head = own.head()
        meta = actor_at(own, head, args.agent, args.binding)
        index = notification_at(own, head, meta, args.agent, args.id)
        if args.action == "show":
            result = prepare(args, own, head, meta, index)
        else:
            path = Path(args.record).resolve()
            with operation_lock(path):
                if path.exists():
                    raise ProtocolError("Original operation already saved. Inspect it and use continue; do not prepare another request.")
                result = prepare(args, own, head, meta, index)
                if not result.get("already_acknowledged"):
                    save(path, result)
                    if args.publish:
                        result = publish(path, result)
    # ASCII JSON also works through Windows pipes with a legacy console encoding.
    # Stored records stay UTF-8; message_json retains its original string value.
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProtocolError, ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired) as exc:
        result = {"ok": False, "error_type": type(exc).__name__, "instruction": "Preserve the original operation; inspect before another write."}
        if isinstance(exc, ProtocolError):
            result["error"] = str(exc)
        print(json.dumps(result))
        raise SystemExit(1)
