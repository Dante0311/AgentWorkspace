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


MESSAGE_BRANCH = "aw-messages"
MESSAGE_GUARD = ".agentworkspace/message-permissions.json"
MESSAGE_ROOTS = ("messages", "acks", "message-index", "dispatch")


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
        self._layout_prefixes = {}
        self._layout_versions = {}
        self._layout_documents = {}

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

    def ref(self, branch, *, required=True):
        rows = self.git("ls-remote", "--heads", "origin", "refs/heads/" + branch).stdout.splitlines()
        if not rows and not required:
            return None
        if len(rows) != 1:
            raise ProtocolError("Expected the explicitly selected Workspace branch.")
        head = rows[0].split()[0].decode("ascii")
        self.git("fetch", "--quiet", "--no-tags", "origin", head)
        return head

    def head(self):
        return self.ref("main")

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

    def protocol_path(self, head, name):
        """Resolve the same ready workspace layout as AW, without importing AW."""
        if head not in self._layout_prefixes:
            marker = self.json(head, ".agentworkspace/layout.json")
            if marker is None:
                prefix = ""
                version = 0
            else:
                if (not isinstance(marker, dict) or marker.get("kind") != "workspace"
                        or type(marker.get("version")) is not int or marker["version"] not in (1, 2, 3)):
                    raise ProtocolError("Unsupported or invalid Workspace layout; do not write protocol records.")
                if marker.get("state", "ready") != "ready":
                    raise ProtocolError("Finish the original layout migration before accessing protocol records.")
                version = marker["version"]
                prefix = marker.get("platform_prefix") if version == 3 else ".agentworkspace"
                if prefix not in ("", ".agentworkspace"):
                    raise ProtocolError("Unsupported platform data prefix.")
                prefix = prefix + "/" if prefix else ""
            self._layout_prefixes[head] = prefix
            self._layout_versions[head] = version
            self._layout_documents[head] = marker or {}
        if (self._layout_versions[head] == 3 and name.split("/", 1)[0] in MESSAGE_ROOTS
                and self._layout_documents[head].get("role") != "messages"):
            raise ProtocolError("Read Message/ACK/index/dispatch from the dedicated message snapshot.")
        return self._layout_prefixes[head] + name

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

    def push(self, commit, parent, *, branch="main"):
        # commit is a direct child of parent: exact lease, never history rewriting.
        return self.git("push", "--porcelain", f"--force-with-lease=refs/heads/{branch}:{parent}",
                        "origin", f"{commit}:refs/heads/{branch}", check=False)


def message_snapshots(repo):
    messages = repo.ref(MESSAGE_BRANCH, required=False)
    main = repo.head()
    repo.protocol_path(main, "workspace.json")
    if repo._layout_versions[main] != 3:
        return {"main": main, "messages": main, "branch": "main"}
    document = repo._layout_documents[main]
    if document.get("messages_branch") != MESSAGE_BRANCH or document.get("role") == "messages":
        raise ProtocolError("The main layout does not identify its dedicated message branch.")
    if messages is None:
        raise ProtocolError("The dedicated message branch is missing; do not fall back to main.")
    repo.protocol_path(messages, "messages/")
    if repo._layout_versions[messages] != 3 or repo._layout_documents[messages].get("role") != "messages":
        raise ProtocolError("The dedicated message branch has a different layout.")
    guard = repo.json(messages, MESSAGE_GUARD)
    if not isinstance(guard, dict) or not guard.get("main_revision"):
        raise ProtocolError("The message permission marker is missing.")
    ancestry = repo.git("merge-base", "--is-ancestor", guard["main_revision"], main, check=False)
    if ancestry.returncode != 0:
        raise ProtocolError("The main read does not include the sampled message permission version.")
    return {"main": main, "messages": messages, "branch": MESSAGE_BRANCH}


def legacy_worker_at(repo, head, agent, kind, identifier_value):
    mapping = repo.json(head, repo.protocol_path(head, f"worker-mappings/{identifier(agent)}.json")) or {}
    worker = mapping.get(kind, {}).get(identifier_value)
    if worker is None:
        raise ProtocolError("The original record has no explicit Worker mapping; do not use the current default.")
    return identifier(worker)


def worker_at(repo, head, agent, worker):
    path = repo.protocol_path(head, f"workers/{identifier(agent)}/{identifier(worker)}.json")
    version = repo._layout_versions[head]
    if not (version == 2 or version == 3 and repo._layout_documents[head].get("worker_support") is True):
        raise ProtocolError("Worker records require the Worker data version gate.")
    record = repo.json(head, path)
    if not record or record.get("agent") != agent or record.get("id") != worker:
        raise ProtocolError("Worker record is missing or belongs to another Agent.")
    return record


def binding_worker_at(repo, head, agent, entry):
    actor = repo.json(head, repo.protocol_path(head, f"agents/{identifier(agent)}.json"))
    if actor.get("worker_schema") != 1:
        if entry.get("worker") is not None:
            raise ProtocolError("Worker Binding has no explicitly enabled Worker schema.")
        return None
    worker = entry.get("worker") or legacy_worker_at(repo, head, agent, "bindings", entry["id"])
    worker_at(repo, head, agent, worker)
    return worker


def endpoint_at(repo, head, address, message_id):
    agent = repo.json(head, repo.protocol_path(head, f"agents/{identifier(address['agent'])}.json"))
    if not agent:
        raise ProtocolError("Message endpoint Agent is missing.")
    if agent.get("worker_schema") != 1:
        if address.get("worker") is not None:
            raise ProtocolError("Message endpoint Worker has no enabled Worker schema.")
        return dict(address)
    worker = address.get("worker") or legacy_worker_at(repo, head, address["agent"], "messages", message_id)
    worker_at(repo, head, address["agent"], worker)
    return {**address, "worker": worker}


def actor_at(repo, head, agent, binding):
    agent, binding = identifier(agent), identifier(binding)
    meta = repo.json(head, repo.protocol_path(head, "workspace.json"))
    actor = repo.json(head, repo.protocol_path(head, f"agents/{agent}.json"))
    entry = repo.json(head, repo.protocol_path(head, f"bindings/{binding}.json"))
    if (not meta or not actor or actor.get("archived")
            or not entry or entry.get("id") != binding or entry.get("agent") != agent or entry.get("phase") != "active"):
        raise ProtocolError("The explicitly granted Binding is not this instance's current active entry.")
    worker = binding_worker_at(repo, head, agent, entry)
    owner = worker_at(repo, head, agent, worker) if worker is not None else actor
    if owner.get("current") != binding or owner.get("archived"):
        raise ProtocolError("The explicitly granted Binding is not this Worker's current active entry.")
    return meta


def notification_at(repo, main, messages, meta, agent, message_id, worker=None):
    index = repo.json(messages, repo.protocol_path(messages, f"message-index/{identifier(message_id)}.json"))
    if (not index or index.get("id") != message_id or index.get("to", {}).get("workspace") != meta["locator"]
            or index["to"].get("agent") != agent):
        raise ProtocolError("The trusted notification index does not target this instance.")
    target = endpoint_at(repo, main, index["to"], message_id)
    if target.get("worker") != worker:
        raise ProtocolError("Only the addressed Worker's current Binding may receive this notification.")
    return index


def targets_for(own, meta, peer_path, locator):
    if locator == meta["locator"]:
        return [{"repo": own.path, "locator": locator}]
    if not peer_path or not any(friend.get("locator") == locator for friend in meta.get("friends", {}).values()):
        raise ProtocolError("Cross-Workspace publication needs the explicit current friend repository.")
    peer = Repository(peer_path)
    head = peer.head()
    other = peer.json(head, peer.protocol_path(head, "workspace.json"))
    if not other or other.get("locator") != locator:
        raise ProtocolError("The supplied peer repository has a different Workspace locator.")
    return [{"repo": own.path, "locator": meta["locator"]}, {"repo": peer.path, "locator": locator}]


def prepare(args, own, head, messages, meta, index):
    entry = own.json(head, own.protocol_path(head, f"bindings/{args.binding}.json"))
    worker = binding_worker_at(own, head, args.agent, entry)
    actor_address = {"workspace": meta["locator"], "agent": args.agent}
    if worker is not None:
        actor_address["worker"] = worker
    if args.action == "receive":
        existing = own.read(messages, own.protocol_path(messages, f"acks/{args.id}.json"))
        if existing is not None:
            if json.loads(existing) != {"message_id": args.id}:
                raise ProtocolError("Existing ACK is damaged or has different fields; do not replace it.")
            return {"message_id": args.id, "already_acknowledged": True,
                    "instruction": "Do not repeat business. Continue an incomplete original operation file separately."}
    raw = own.read(messages, own.protocol_path(messages, f"messages/{args.id}.json"))
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
        return {**result, "index": index, "ack": own.json(messages, own.protocol_path(messages, f"acks/{args.id}.json"))}
    if args.action == "receive":
        payload = {"message_id": args.id}
        records = {f"acks/{args.id}.json": encode(payload)}
        locator = index["from"]["workspace"]
    else:
        content = Path(args.content_file).read_bytes().decode("utf-8")
        if not content.strip():
            raise ProtocolError("Reply content must be non-empty.")
        targets_for(own, meta, args.peer, index["from"]["workspace"])
        target = own if index["from"]["workspace"] == meta["locator"] else Repository(args.peer)
        target_head = head if target is own else target.head()
        endpoint = endpoint_at(target, target_head, index["from"], args.id)
        receiver = target.json(target_head, target.protocol_path(target_head, f"agents/{identifier(endpoint['agent'])}.json"))
        if receiver.get("archived") or (endpoint.get("worker") is not None
                and worker_at(target, target_head, endpoint["agent"], endpoint["worker"]).get("archived")):
            raise ProtocolError("The reply target is archived; do not reroute it.")
        payload = {"id": identifier(args.request_id), "from": actor_address,
                   "to": endpoint, "created_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                   "message_refs": list(dict.fromkeys([args.id, *args.ref])), "delivery": args.delivery, "content": content}
        if worker is not None:
            payload["reply_to"] = args.id
        for ref in payload["message_refs"]:
            identifier(ref)
        records = {f"messages/{payload['id']}.json": encode(payload),
                   f"message-index/{payload['id']}.json": encode({key: payload[key] for key in ("id", "from", "to", "created_at", "delivery")})}
        locator = payload["to"]["workspace"]
    operation = {"format": "message-git-operation-v2" if worker is not None else "message-git-operation-v1",
            "kind": "ack" if args.action == "receive" else "message",
            "actor": {**actor_address, "binding": args.binding},
            "source_id": args.id, "source_index": base64.b64encode(own.read(messages, own.protocol_path(messages, f"message-index/{args.id}.json"))).decode(),
            "records": {path: base64.b64encode(value).decode() for path, value in records.items()},
            "read_result": result, "targets": targets_for(own, meta, args.peer, locator), "state": "prepared"}
    if worker is not None and args.action == "reply":
        operation["reply_target"] = payload["to"]
    return operation


def original_records(operation):
    if operation.get("format") not in ("message-git-operation-v1", "message-git-operation-v2"):
        raise ProtocolError("Not a helper operation file; AW receipts are not accepted.")
    actor = operation["actor"]
    identifier(actor["agent"])
    identifier(actor["binding"])
    actor_address = {key: actor[key] for key in ("workspace", "agent")}
    if operation["format"] == "message-git-operation-v2":
        actor_address["worker"] = identifier(actor["worker"])
    source_id = identifier(operation["source_id"])
    source = json.loads(base64.b64decode(operation["source_index"], validate=True))
    if (source["id"] != source_id or source["to"].get("workspace") != actor["workspace"]
            or source["to"].get("agent") != actor["agent"]
            or source["to"].get("worker") is not None and source["to"]["worker"] != actor.get("worker")):
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
        target = operation.get("reply_target", source["from"])
        if (body["from"] != actor_address
                or body["to"] != target or body["delivery"] not in ("normal", "insert")
                or not isinstance(body["content"], str) or not body["content"].strip()
                or not isinstance(body["message_refs"], list) or source_id not in body["message_refs"]):
            raise ProtocolError("Reply differs from the original actor, target or message relation.")
        if operation["format"] == "message-git-operation-v2" and body.get("reply_to") != source_id:
            raise ProtocolError("The explicit reply_to must preserve the original selected Message.")
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
        own_state = message_snapshots(own)
        head, messages = own_state["main"], own_state["messages"]
        meta = actor_at(own, head, actor["agent"], actor["binding"])
        if meta["locator"] != actor["workspace"] or own.read(messages, own.protocol_path(messages, f"message-index/{operation['source_id']}.json")) != base64.b64decode(operation["source_index"]):
            raise ProtocolError("The original Workspace or notification index changed.")
        entry = own.json(head, own.protocol_path(head, f"bindings/{actor['binding']}.json"))
        worker = binding_worker_at(own, head, actor["agent"], entry)
        if actor.get("worker", worker) != worker:
            raise ProtocolError("The original operation belongs to another Worker.")
        notification_at(own, head, messages, meta, actor["agent"], operation["source_id"], worker)
        repo = own if target["repo"] == own.path else Repository(target["repo"])
        if repo is not own and not any(friend.get("locator") == target["locator"] for friend in meta.get("friends", {}).values()):
            raise ProtocolError("The original friend route was removed; no peer write is authorized.")
        target_state = own_state if repo is own else message_snapshots(repo)
        parent, branch = target_state["messages"], target_state["branch"]
        target_main = target_state["main"]
        if repo.json(target_main, repo.protocol_path(target_main, "workspace.json"))["locator"] != target["locator"]:
            raise ProtocolError("Target Workspace changed.")
        if operation["kind"] == "message":
            body = json.loads(next(content for record, content in records.items() if record.startswith("messages/")))
            source = json.loads(base64.b64decode(operation["source_index"]))
            destination = next(row for row in operation["targets"] if row["locator"] == body["to"]["workspace"])
            if destination["repo"] == own.path:
                destination_repo, destination_state = own, own_state
            elif destination["repo"] == repo.path:
                destination_repo, destination_state = repo, target_state
            else:
                destination_repo = Repository(destination["repo"])
                destination_state = message_snapshots(destination_repo)
            destination_head = destination_state["main"]
            expected_target = endpoint_at(destination_repo, destination_head, source["from"], operation["source_id"])
            actual_target = endpoint_at(destination_repo, destination_head, body["to"], body["id"])
            source_endpoint = endpoint_at(own, head, body["from"], body["id"])
            if actual_target != expected_target or source_endpoint.get("worker") != worker:
                raise ProtocolError("The saved reply differs from the original source or target Worker.")
        missing = {}
        for record, content in records.items():
            target_path = repo.protocol_path(parent, record)
            existing = repo.read(parent, target_path)
            if existing is None:
                missing[target_path] = content
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
                receiver = repo.json(target_main, repo.protocol_path(target_main, f"agents/{identifier(body['to']['agent'])}.json"))
                if not receiver or receiver.get("archived"):
                    raise ProtocolError("Reply target is missing or archived.")
                endpoint = endpoint_at(repo, target_main, body["to"], body["id"])
                if endpoint.get("worker") is not None and worker_at(repo, target_main, endpoint["agent"], endpoint["worker"]).get("archived"):
                    raise ProtocolError("Reply target Worker is archived; do not choose another Worker.")
        commit = repo.commit(parent, missing)
        target.setdefault("attempts", []).append({"parent": parent, "commit": commit, "branch": branch})
        target.update(parent=parent, commit=commit, branch=branch, state="outcome_unknown")
        operation["state"] = "outcome_unknown"
        save(path, operation)  # Preserve the original commit before the possibly ambiguous write.
        try:
            pushed = repo.push(commit, parent) if branch == "main" else repo.push(commit, parent, branch=branch)
        except (subprocess.TimeoutExpired, OSError):
            pushed = None
        try:
            current = repo.head() if branch == "main" else repo.ref(branch)
            confirmed = all(repo.read(current, repo.protocol_path(current, record)) == content
                            for record, content in records.items())
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
        state = message_snapshots(own)
        head, messages = state["main"], state["messages"]
        meta = actor_at(own, head, args.agent, args.binding)
        entry = own.json(head, own.protocol_path(head, f"bindings/{args.binding}.json"))
        worker = binding_worker_at(own, head, args.agent, entry)
        index = notification_at(own, head, messages, meta, args.agent, args.id, worker)
        if args.action == "show":
            result = prepare(args, own, head, messages, meta, index)
        else:
            path = Path(args.record).resolve()
            with operation_lock(path):
                if path.exists():
                    raise ProtocolError("Original operation already saved. Inspect it and use continue; do not prepare another request.")
                result = prepare(args, own, head, messages, meta, index)
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
