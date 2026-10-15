"""Message semantics and the V1 Git publication backend.

Publication receipts are local mechanical journals, not a second mutable Message store.
"""
from __future__ import annotations

import json
import time
from importlib.resources import files as package_files

from .gitstore import open_store
from .layout import expected as expected_layout, instance_path, lock as layout_lock, shared_path
from .util import Conflict, Error, RetryableRead, Uncertain, digest, encode, locked, now, read_json, slug, uid, write_json


class Messages:
    def __init__(self, app):
        self.app = app

    def _own(self, workspace):
        store = self.app.store(workspace)
        snap = store.snapshot()
        return store, snap.json(shared_path(snap, "workspace.json"))

    def _peer(self, workspace, locator):
        own, meta = self._own(workspace)
        if locator == meta["locator"]:
            return own, meta
        for alias, friend in meta["friends"].items():
            if friend["locator"] == locator:
                return self.app.friend_store(workspace, alias)
        raise Error("No current friend route to the other workspace.")

    def send(self, workspace, agent_id, binding, to, content, delivery="normal", message_refs=None, request_id=None):
        self.app.require_binding(workspace, agent_id, binding)
        if not isinstance(content, str) or not content.strip() or delivery not in ("normal", "insert"):
            raise Error("Message needs non-empty content and delivery=normal or insert.")
        own, meta = self._own(workspace)
        if "/" in to:
            alias, target_id = to.split("/", 1)
            target, other = self.app.friend_store(workspace, alias)
        else:
            target_id, target, other = to, own, meta
        slug(target_id)
        target_snap = target.snapshot()
        receiver = target_snap.json(shared_path(target_snap, f"agents/{target_id}.json"))
        if receiver is None or receiver["archived"]:
            raise Error("Target agent does not exist or is archived.")
        mid = slug(request_id or uid("m"))
        receipt_path = self.app.home / "operations" / f"{mid}.json"
        body = {"id": mid, "from": {"workspace": meta["locator"], "agent": agent_id},
                "to": {"workspace": other["locator"], "agent": target_id}, "created_at": now(),
                "message_refs": message_refs or [], "delivery": delivery, "content": content}
        with locked(receipt_path.with_suffix(".lock")):
            existing = read_json(receipt_path)
            if existing:
                original = existing["payload"]
                if any(original.get(k) != body[k] for k in body if k != "created_at"):
                    raise Conflict("Request ID was used for a different message.")
                body = original
            else:
                write_json(receipt_path, {"id": mid, "type": "message", "workspace": workspace,
                    "payload": body, "destinations": list(dict.fromkeys([own.address, target.address])), "completed": [], "sender": agent_id, "binding": binding})
        return self.reconcile(mid)

    def operation(self, workspace, operation_id):
        """Inspect the existing local receipt without publishing or replaying it."""
        if workspace not in self.app.local()["workspaces"]:
            raise Error("Unknown workspace.")
        identifier = slug(operation_id)
        receipt = read_json(self.app.home / "operations" / f"{identifier}.json")
        if receipt is None:
            return {"id": identifier, "state": "not_recorded"}
        if receipt["workspace"] != workspace:
            raise Conflict("Operation belongs to a different workspace.")
        return {"id": identifier, "state": receipt.get("state", "pending"),
                "type": receipt["type"], "payload": receipt["payload"],
                "binding": receipt["binding"],
                "agent": receipt.get("sender") or receipt.get("receiver")}

    def reconcile(self, operation_id, workspace=None, agent_id=None, binding=None):
        path = self.app.home / "operations" / (slug(operation_id) + ".json")
        with locked(path.with_suffix(".lock")):
            receipt = read_json(path)
            if receipt is None:
                raise Error("No local publication receipt for that operation.")
            # Model calls carry their entry; internal sends and authorized repairs
            # have already checked their scope before reaching this backend.
            caller = (workspace, agent_id, binding)
            owner = (receipt["workspace"], receipt.get("sender") or receipt.get("receiver"), receipt["binding"])
            if caller != (None, None, None) and caller != owner:
                raise Conflict("Publication belongs to another entry; use an authorized maintenance.repair for another instance.")
            payload = receipt["payload"]
            for address in receipt["destinations"]:
                if address in receipt["completed"]:
                    continue
                try:
                    store = open_store(address, self.app.home)
                    snap = store.snapshot()
                    mid = payload["id"] if receipt["type"] == "message" else payload["message_id"]
                    target = shared_path(snap, f"messages/{mid}.json" if receipt["type"] == "message" else f"acks/{mid}.json")
                    existing = snap.bytes(target)
                    if existing is not None:
                        if existing != encode(payload):
                            raise Conflict("Existing protocol record has different bytes; refusing overwrite.")
                    else:
                        expected = {target: None}
                        changes = {target: encode(payload)}
                        own_address = self.app.store(receipt["workspace"]).address
                        if address == own_address:
                            actor_id = receipt.get("sender") or receipt.get("receiver")
                            self.app.require_binding(receipt["workspace"], actor_id, receipt["binding"], snapshot=snap)
                            actor_path = shared_path(snap, f"agents/{actor_id}.json")
                            binding_path = shared_path(snap, f"bindings/{receipt['binding']}.json")
                            expected[actor_path] = snap.entries[actor_path]
                            expected[binding_path] = snap.entries[binding_path]
                        if receipt["type"] == "message":
                            index = shared_path(snap, f"message-index/{mid}.json")
                            changes[index] = encode({k: payload[k] for k in ("id", "from", "to", "created_at", "delivery")})
                            expected[index] = None
                            meta = snap.json(shared_path(snap, "workspace.json"))
                            if meta["locator"] == payload["to"]["workspace"]:
                                agent_path = shared_path(snap, f"agents/{payload['to']['agent']}.json")
                                agent = snap.json(agent_path)
                                if agent is None or agent["archived"]:
                                    raise Error("Target is archived or missing; publication remains incomplete.")
                                expected[agent_path] = snap.entries[agent_path]
                        store.change("main", changes, expected_layout(snap, expected), f"Publish {receipt['type']} {mid}")
                    receipt["completed"].append(address)
                    receipt.pop("error", None)
                    write_json(path, receipt)
                except (Error, OSError, TimeoutError) as exc:
                    receipt["error"] = str(exc)
                    receipt["state"] = "outcome_unknown" if isinstance(exc, Uncertain) else "pending"
                    write_json(path, receipt)
                    return receipt
            receipt["state"] = "published"
            write_json(path, receipt)
            return receipt

    def list(self, workspace, agent_id=None, direction="in", unacked=False):
        return self._list(self.app.store(workspace).snapshot(), agent_id, direction, unacked)

    def _list(self, snap, agent_id=None, direction="in", unacked=False):
        meta = snap.json(shared_path(snap, "workspace.json"))
        prefix = shared_path(snap, "message-index") + "/"
        result = []
        for path in snap.entries:
            if not path.startswith(prefix):
                continue
            item = snap.json(path)
            if agent_id:
                side = item["to"] if direction == "in" else item["from"]
                if side != {"workspace": meta["locator"], "agent": agent_id}:
                    continue
            acked = shared_path(snap, f"acks/{item['id']}.json") in snap.entries
            if unacked and acked:
                continue
            result.append({**item, "notification_acknowledged": acked})
        return sorted(result, key=lambda m: (m["created_at"], m["id"]))

    def show(self, workspace, message_id):
        snap = self.app.store(workspace).snapshot()
        item = snap.json(shared_path(snap, f"messages/{slug(message_id)}.json"))
        if item is None:
            raise Error("Message not found.")
        return {"message": item, "ack": snap.json(shared_path(snap, f"acks/{message_id}.json"))}

    def receive(self, workspace, agent_id, binding, message_id, directory=None):
        self.app.require_binding(workspace, agent_id, binding)
        own, meta = self._own(workspace)
        snap = own.snapshot()
        mid = slug(message_id)
        envelope = snap.json(shared_path(snap, f"message-index/{mid}.json"))
        if not envelope or envelope["to"] != {"workspace": meta["locator"], "agent": agent_id}:
            raise Error("The notification does not target this instance.")
        if snap.bytes(shared_path(snap, f"acks/{mid}.json")):
            return {"message_id": mid, "already_acknowledged": True, "instruction": "Use show for history; do not repeat business execution."}
        result = {"message_id": mid}
        try:
            body = snap.bytes(shared_path(snap, f"messages/{mid}.json"))
            if body is None:
                raise Error("Message body unavailable.")
            result["message"] = json.loads(body)
        except (ValueError, Error) as exc:
            result["read_error"] = str(exc)
        # Recheck after reading; publication also conditions on the current entry record.
        self.app.require_binding(workspace, agent_id, binding)
        peer, _ = self._peer(workspace, envelope["from"]["workspace"])
        opid = "ack-" + (mid if len(mid) <= 60 else digest(mid.encode())[:40])
        path = self.app.home / "operations" / f"{opid}.json"
        with locked(path.with_suffix(".lock")):
            if not path.exists():
                write_json(path, {"id": opid, "type": "ack", "workspace": workspace,
                    "payload": {"message_id": mid}, "destinations": list(dict.fromkeys([own.address, peer.address])),
                    "completed": [], "receiver": agent_id, "binding": binding})
        result["publication"] = self.reconcile(opid)
        if result["publication"]["state"] != "published":
            result["instruction"] = "ACK publication is incomplete. Preserve this result; reconcile the original operation before new business effects."
        try:
            root = self.app.root(workspace, agent_id, directory)
        except Error:
            root = None
        if root is not None:
            with layout_lock(root, "files.lock"):
                write_json(instance_path(root, f"messages/{mid}.json"), {
                    k: v for k, v in result.items() if k != "publication"
                })
        return result

    def _notification(self, snap, index, *, require_body=False):
        template = json.loads((package_files("agent_workspace") / "resources/prompts/message-notification.json").read_bytes())
        try:
            raw = snap.bytes(shared_path(snap, f"messages/{index['id']}.json"))
            if raw is None:
                raise Error("Message body unavailable.")
            text = raw.decode("utf-8")
            body = json.loads(text)
            if (not isinstance(body, dict)
                    or any(body.get(key) != index[key] for key in ("id", "from", "to", "created_at", "delivery"))
                    or not isinstance(body.get("content"), str) or not body["content"].strip()
                    or not isinstance(body.get("message_refs", []), list)):
                raise Error("Message does not match its notification index.")
        except RetryableRead:
            # A temporary blob read does not mean the immutable body is damaged.
            raise
        except (Error, ValueError, UnicodeError):
            if require_body:
                raise Error("The complete original Message is unavailable; Web Courier cannot send it.")
            text = snap.bytes(shared_path(snap, f"message-index/{index['id']}.json")).decode("utf-8")
            return template["instruction"] + template["unavailable"].format(record=text)
        return template["instruction"] + template["message"].format(record=text)

    def _head(self, snap, workspace, agent_id, binding):
        self.app.require_binding(workspace, agent_id, binding, snapshot=snap)
        messages = self._list(snap, agent_id, unacked=True)
        return messages[0] if messages else None

    def _dispatch(self, snap, workspace, agent_id, binding, message, attempts, *, manual_attempt_id=None):
        path = shared_path(snap, f"dispatch/{agent_id}.json")
        record = {"message_id": message["id"], "workspace": workspace, "agent": agent_id,
                  "binding": binding, "delivery": message["delivery"],
                  "attempts": attempts, "attempted_at": time.time()}
        if manual_attempt_id is not None:
            record["manual_attempt_id"] = manual_attempt_id
        agent_path = shared_path(snap, f"agents/{agent_id}.json")
        binding_path = shared_path(snap, f"bindings/{binding}.json")
        expected = {path: snap.entries.get(path), agent_path: snap.entries[agent_path],
                    binding_path: snap.entries[binding_path],
                    shared_path(snap, f"acks/{message['id']}.json"): None}
        for original in (f"messages/{message['id']}.json", f"message-index/{message['id']}.json"):
            original_path = shared_path(snap, original)
            expected[original_path] = snap.entries.get(original_path)
        self.app.store(workspace).change("main", {path: encode(record)},
                                         expected_layout(snap, expected), "Claim notification attempt")
        return record

    def preview_manual(self, workspace, agent_id, binding):
        snap = self.app.store(workspace).snapshot()
        message = self._head(snap, workspace, agent_id, binding)
        if message is None:
            return {"state": "empty"}
        if message["delivery"] != "normal":
            return {"state": "delivery_unsupported", "message_id": message["id"],
                    "delivery": message["delivery"]}
        previous = snap.json(shared_path(snap, f"dispatch/{agent_id}.json"), {})
        if previous.get("message_id") == message["id"]:
            return {"state": "waiting_ack", "message_id": message["id"]}
        prompt = self._notification(snap, message, require_body=True)
        return {"state": "ready", "message_id": message["id"], "prompt_digest": digest(prompt.encode()),
                "notification": {"message_id": message["id"], "workspace": workspace,
                                 "agent": agent_id, "binding": binding, "delivery": message["delivery"]},
                "prompt": prompt}

    def claim_manual(self, workspace, agent_id, binding, message_id, attempt_id, expected_prompt_digest):
        """Share poll's FIFO and dispatch claim; a manual outcome is never retried."""
        mid, attempt = slug(message_id), slug(attempt_id)
        snap = self.app.store(workspace).snapshot()
        message = self._head(snap, workspace, agent_id, binding)
        if message is None or message["id"] != mid:
            raise Conflict("The original message is no longer the unacknowledged FIFO head.")
        if message["delivery"] != "normal":
            raise Error("This manual Web route does not support insert delivery.")
        previous = snap.json(shared_path(snap, f"dispatch/{agent_id}.json"), {})
        if previous.get("message_id") == mid:
            raise Conflict("The original message already has a notification attempt; inspect it without claiming again.")
        prompt = self._notification(snap, message, require_body=True)
        if digest(prompt.encode()) != expected_prompt_digest:
            raise Conflict("The original notification changed before this attempt.")
        self._dispatch(snap, workspace, agent_id, binding, message, 1, manual_attempt_id=attempt)
        return {"state": "claimed", "message_id": mid, "attempt_id": attempt}

    def poll(self, workspace, agent_id, binding, *, adapter=None, directory=None,
             retry_seconds=60, max_attempts=3):
        store = self.app.store(workspace)
        snap = store.snapshot()
        message = self._head(snap, workspace, agent_id, binding)
        if message is None:
            return {"state": "empty"}
        notification = {"message_id": message["id"], "workspace": workspace, "agent": agent_id,
                        "binding": binding, "delivery": message["delivery"]}
        if adapter is None:
            return {"state": "awaiting_manual_receive", "notification": notification}
        if message["delivery"] == "insert" and getattr(adapter, "supports_insert", True) is False:
            return {"state": "delivery_unsupported", "message_id": message["id"], "delivery": "insert",
                    "instruction": "当前接入不支持 insert；队头与原消息保留。告知用户，按其选择主动接收原消息或交接到支持的入口；不要重发副本、改写 delivery 或伪造 ACK。"}
        state = adapter.status()
        if state == "unknown":
            return {"state": "entry_state_unknown"}
        if state == "busy" and message["delivery"] == "normal":
            return {"state": "waiting_idle", "message_id": message["id"]}
        snap = store.snapshot()
        dispatch_path = shared_path(snap, f"dispatch/{agent_id}.json")
        self.app.require_binding(workspace, agent_id, binding, snapshot=snap)
        previous = snap.json(dispatch_path, {})
        if previous.get("message_id") == message["id"] and previous.get("manual_attempt_id"):
            return {"state": "waiting_ack", "message_id": message["id"]}
        attempts = 0
        if previous.get("message_id") == message["id"] and previous.get("binding") == binding:
            attempts = previous["attempts"]
            if time.time() < previous["attempted_at"] + retry_seconds:
                return {"state": "waiting_ack", "message_id": message["id"]}
            if attempts >= max_attempts:
                return {"state": "notification_retry_exhausted", "message_id": message["id"]}
        prompt = self._notification(snap, message)
        # A shared attempt record arbitrates separate local copies, not just one process's lock.
        self._dispatch(snap, workspace, agent_id, binding, message, attempts + 1)
        self.app.require_binding(workspace, agent_id, binding)
        try:
            adapter.notify(prompt, message["delivery"])
        except Exception as exc:
            return {"state": "notification_outcome_unknown", "message_id": message["id"], "error": str(exc),
                    "instruction": "Await ACK; do not generate another Message."}
        return {"state": "notified_waiting_ack", "message_id": message["id"]}
