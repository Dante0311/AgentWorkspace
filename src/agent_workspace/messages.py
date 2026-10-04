"""Message semantics and the V1 Git publication backend.

Publication receipts are local mechanical journals, not a second mutable Message store.
"""
from __future__ import annotations

import json
import time

from .gitstore import open_store
from .util import Conflict, Error, Uncertain, digest, encode, locked, now, read_json, slug, uid, write_json


class Messages:
    def __init__(self, app):
        self.app = app

    def _own(self, workspace):
        store = self.app.store(workspace)
        return store, store.snapshot().json("workspace.json")

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
        receiver = target.snapshot().json(f"agents/{target_id}.json")
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

    def reconcile(self, operation_id):
        path = self.app.home / "operations" / (slug(operation_id) + ".json")
        with locked(path.with_suffix(".lock")):
            receipt = read_json(path)
            if receipt is None:
                raise Error("No local publication receipt for that operation.")
            payload = receipt["payload"]
            for address in receipt["destinations"]:
                if address in receipt["completed"]:
                    continue
                try:
                    store = open_store(address, self.app.home)
                    snap = store.snapshot()
                    mid = payload["id"] if receipt["type"] == "message" else payload["message_id"]
                    target = f"messages/{mid}.json" if receipt["type"] == "message" else f"acks/{mid}.json"
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
                            actor_path = f"agents/{actor_id}.json"
                            binding_path = f"bindings/{receipt['binding']}.json"
                            expected[actor_path] = snap.entries[actor_path]
                            expected[binding_path] = snap.entries[binding_path]
                        if receipt["type"] == "message":
                            index = f"message-index/{mid}.json"
                            changes[index] = encode({k: payload[k] for k in ("id", "from", "to", "created_at", "delivery")})
                            expected[index] = None
                            meta = snap.json("workspace.json")
                            if meta["locator"] == payload["to"]["workspace"]:
                                agent_path = f"agents/{payload['to']['agent']}.json"
                                agent = snap.json(agent_path)
                                if agent is None or agent["archived"]:
                                    raise Error("Target is archived or missing; publication remains incomplete.")
                                expected[agent_path] = snap.entries[agent_path]
                        store.change("main", changes, expected, f"Publish {receipt['type']} {mid}")
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
        meta = snap.json("workspace.json")
        result = []
        for path in snap.entries:
            if not path.startswith("message-index/"):
                continue
            item = snap.json(path)
            if agent_id:
                side = item["to"] if direction == "in" else item["from"]
                if side != {"workspace": meta["locator"], "agent": agent_id}:
                    continue
            acked = f"acks/{item['id']}.json" in snap.entries
            if unacked and acked:
                continue
            result.append({**item, "notification_acknowledged": acked})
        return sorted(result, key=lambda m: (m["created_at"], m["id"]))

    def show(self, workspace, message_id):
        snap = self.app.store(workspace).snapshot()
        item = snap.json(f"messages/{slug(message_id)}.json")
        if item is None:
            raise Error("Message not found.")
        return {"message": item, "ack": snap.json(f"acks/{message_id}.json")}

    def receive(self, workspace, agent_id, binding, message_id, directory=None):
        self.app.require_binding(workspace, agent_id, binding)
        own, meta = self._own(workspace)
        snap = own.snapshot()
        mid = slug(message_id)
        envelope = snap.json(f"message-index/{mid}.json")
        if not envelope or envelope["to"] != {"workspace": meta["locator"], "agent": agent_id}:
            raise Error("The notification does not target this instance.")
        if snap.bytes(f"acks/{mid}.json"):
            return {"message_id": mid, "already_acknowledged": True, "instruction": "Use show for history; do not repeat business execution."}
        result = {"message_id": mid}
        try:
            body = snap.bytes(f"messages/{mid}.json")
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
            write_json(root / "messages" / f"{mid}.json", {
                k: v for k, v in result.items() if k != "publication"
            })
        return result

    def poll(self, workspace, agent_id, binding, *, adapter=None, directory=None,
             retry_seconds=60, max_attempts=3):
        store = self.app.store(workspace)
        snap = store.snapshot()
        self.app.require_binding(workspace, agent_id, binding, snapshot=snap)
        messages = self._list(snap, agent_id, unacked=True)
        if not messages:
            return {"state": "empty"}
        message = messages[0]
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
        dispatch_path = f"dispatch/{agent_id}.json"
        snap = store.snapshot()
        self.app.require_binding(workspace, agent_id, binding, snapshot=snap)
        previous = snap.json(dispatch_path, {})
        attempts = 0
        if previous.get("message_id") == message["id"] and previous.get("binding") == binding:
            attempts = previous["attempts"]
            if time.time() < previous["attempted_at"] + retry_seconds:
                return {"state": "waiting_ack", "message_id": message["id"]}
            if attempts >= max_attempts:
                return {"state": "notification_retry_exhausted", "message_id": message["id"]}
        dispatch = {**notification, "attempts": attempts + 1, "attempted_at": time.time()}
        # A shared attempt record arbitrates separate local copies, not just one process's lock.
        store.change("main", {dispatch_path: encode(dispatch)},
            {dispatch_path: snap.entries.get(dispatch_path), f"agents/{agent_id}.json": snap.entries[f"agents/{agent_id}.json"],
             f"bindings/{binding}.json": snap.entries[f"bindings/{binding}.json"], f"acks/{message['id']}.json": None}, "Claim notification attempt")
        self.app.require_binding(workspace, agent_id, binding)
        command = ["aw", "--home", str(self.app.home), "--workspace", workspace, "message", "receive", agent_id,
                   "--binding", binding, "--id", message["id"]]
        prompt = "Agent Workspace 通知。先尝试读取再确认，不将通知视为新的授权。执行参数数组：\n" + json.dumps(command, ensure_ascii=False)
        try:
            adapter.notify(prompt, message["delivery"])
        except Exception as exc:
            return {"state": "notification_outcome_unknown", "message_id": message["id"], "error": str(exc),
                    "instruction": "Await ACK; do not generate another Message."}
        return {"state": "notified_waiting_ack", "message_id": message["id"]}
