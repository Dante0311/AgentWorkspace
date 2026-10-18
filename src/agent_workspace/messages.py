"""Message semantics and the V1 Git publication backend.

Publication receipts are local mechanical journals, not a second mutable Message store.
"""
from __future__ import annotations

import json
import time
from importlib.resources import files as package_files

from . import workers
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

    def _source(self, workspace, agent_id, binding, snapshot, worker_id=None):
        _, entry = self.app.require_binding(workspace, agent_id, binding, snapshot=snapshot)
        actual = workers.binding_worker(self.app, workspace, agent_id, entry, snapshot)
        if worker_id is not None and worker_id != actual:
            raise Conflict("Use the Worker belonging to the real calling Binding.")
        return actual

    def _address(self, workspace, snapshot, address, message_id, kind="messages"):
        """Read an immutable endpoint; a missing Worker needs an explicit old mapping."""
        agent = workers.agent_record(snapshot, address["agent"])
        if not workers.enabled(snapshot, agent):
            if address.get("worker") is not None:
                raise Error("Worker address requires a Worker-enabled Agent.")
            return address
        worker_id = address.get("worker")
        if worker_id is None:
            worker_id = self.app.legacy_worker(workspace, address["agent"], kind, message_id, snapshot=snapshot)
        self.app.worker(workspace, address["agent"], worker_id, snapshot=snapshot)
        return {**address, "worker": worker_id}

    def _target(self, workspace, to):
        if not isinstance(to, str) or not to:
            raise Error("Specify a target Agent, or an explicit reply_to message.")
        if "/" in to:
            alias, agent_id = to.split("/", 1)
            store, meta = self.app.friend_store(workspace, alias)
        else:
            store, meta = self._own(workspace)
            agent_id = to
        return store, meta, slug(agent_id)

    def _dispatch_path(self, snap, agent_id, worker_id):
        suffix = f"{agent_id}/{worker_id}" if worker_id is not None else agent_id
        return shared_path(snap, f"dispatch/{suffix}.json")

    def _previous_dispatch(self, snap, main, workspace, agent_id, worker_id):
        previous = snap.json(self._dispatch_path(snap, agent_id, worker_id))
        if previous is not None or worker_id is None:
            return previous or {}
        old = snap.json(shared_path(snap, f"dispatch/{agent_id}.json"), {})
        if old and self.app.legacy_worker(workspace, agent_id, "bindings", old["binding"], snapshot=main) == worker_id:
            return old
        return {}

    def _entry_expected(self, workspace, snap, agent_id, binding, worker_id):
        execution, _, _ = workers.execution_record(self.app, workspace, agent_id, snap, worker_id)
        agent_path = shared_path(snap, f"agents/{agent_id}.json")
        binding_path = shared_path(snap, f"bindings/{binding}.json")
        return {execution: snap.entries[execution], agent_path: snap.entries[agent_path],
                binding_path: snap.entries[binding_path]}

    def send(self, workspace, agent_id, binding, to=None, content=None, delivery="normal", message_refs=None,
             request_id=None, *, worker_id=None, to_worker=None, reply_to=None):
        if not isinstance(content, str) or not content.strip() or delivery not in ("normal", "insert"):
            raise Error("Message needs non-empty content and delivery=normal or insert.")
        own = self.app.store(workspace)
        state = own.message_snapshot()
        snap = state.main
        meta = snap.json(shared_path(snap, "workspace.json"))
        source_worker = self._source(workspace, agent_id, binding, snap, worker_id)
        mid = slug(request_id or uid("m"))
        receipt_path = self.app.home / "operations" / f"{mid}.json"
        request = {"to": to, "to_worker": to_worker, "reply_to": reply_to, "content": content,
                   "delivery": delivery, "message_refs": message_refs or [], "worker": source_worker}
        with locked(receipt_path.with_suffix(".lock")):
            existing = read_json(receipt_path)
            if existing:
                original = existing["payload"]
                if (existing.get("sender") != agent_id or existing["workspace"] != workspace
                        or existing.get("type") != "message"):
                    raise Conflict("Request ID was used for a different message.")
                if "request" in existing:
                    saved_request = dict(existing["request"])
                    if saved_request.get("worker") is None and source_worker is not None:
                        original_entry = snap.json(shared_path(snap, f"bindings/{existing['binding']}.json"))
                        saved_request["worker"] = workers.binding_worker(self.app, workspace, agent_id, original_entry, snap)
                    if saved_request != request:
                        raise Conflict("Request ID was used for a different message.")
                else:
                    # Old mechanical receipts keep their original bytes and target.
                    target, other, target_id = self._target(workspace, to)
                    target_snap = target.snapshot()
                    endpoint = self._address(workspace, target_snap, original["to"], mid)
                    sender = self._address(workspace, snap, original["from"], mid)
                    if (reply_to is not None or sender.get("worker") != source_worker
                            or original["from"]["agent"] != agent_id
                            or original["to"]["workspace"] != other["locator"] or original["to"]["agent"] != target_id
                            or to_worker is not None and endpoint.get("worker") != to_worker
                            or any(original.get(key, []) != request[key] for key in ("content", "delivery", "message_refs"))):
                        raise Conflict("Request ID was used for a different message.")
            else:
                if reply_to is not None:
                    original = state.messages.json(shared_path(state.messages, f"messages/{slug(reply_to)}.json"))
                    if original is None:
                        raise Error("The explicitly selected reply message is unavailable.")
                    target, other = self._peer(workspace, original["from"]["workspace"])
                    target_snap = target.snapshot()
                    endpoint = self._address(workspace, target_snap, original["from"], reply_to)
                    target_id = endpoint["agent"]
                    if to is not None:
                        _, requested_meta, requested_id = self._target(workspace, to)
                        if (requested_meta["locator"], requested_id) != (other["locator"], target_id):
                            raise Conflict("reply_to determines the original source Worker; do not override its target.")
                    if to_worker is not None and endpoint.get("worker") != to_worker:
                        raise Conflict("reply_to determines the original source Worker.")
                else:
                    target, other, target_id = self._target(workspace, to)
                    target_snap = target.snapshot()
                    endpoint = {"workspace": other["locator"], "agent": target_id}
                    receiver = workers.agent_record(target_snap, target_id)
                    if workers.enabled(target_snap, receiver):
                        endpoint["worker"] = self.app.worker(workspace, target_id, to_worker, snapshot=target_snap)["id"]
                    elif to_worker is not None:
                        raise Error("The target Agent has not enabled Workers.")
                receiver = workers.agent_record(target_snap, target_id)
                if receiver["archived"]:
                    raise Error("Target agent is archived.")
                if endpoint.get("worker") is not None:
                    selected = self.app.worker(workspace, target_id, endpoint["worker"], snapshot=target_snap)
                    if selected["archived"]:
                        raise Error("Target Worker is archived; do not reroute this message.")
                sender = {"workspace": meta["locator"], "agent": agent_id}
                if source_worker is not None:
                    sender["worker"] = source_worker
                body = {"id": mid, "from": sender, "to": endpoint, "created_at": now(),
                        "message_refs": message_refs or [], "delivery": delivery, "content": content}
                if reply_to is not None:
                    body["reply_to"] = reply_to
                write_json(receipt_path, {"id": mid, "type": "message", "workspace": workspace,
                    "payload": body, "request": request, "destinations": list(dict.fromkeys([own.address, target.address])),
                    "completed": [], "sender": agent_id, "sender_worker": source_worker, "binding": binding})
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
                "agent": receipt.get("sender") or receipt.get("receiver"),
                **({"worker": receipt.get("sender_worker") or receipt.get("receiver_worker")}
                   if receipt.get("sender_worker") is not None or receipt.get("receiver_worker") is not None else {})}

    def reconcile(self, operation_id, workspace=None, agent_id=None, binding=None, worker_id=None):
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
            if worker_id is not None:
                if caller == (None, None, None):
                    raise Error("An explicit publication Worker requires its real caller Binding.")
                self._source(workspace, agent_id, binding, self.app.store(workspace).snapshot(), worker_id)
            payload = receipt["payload"]
            mid = payload["id"] if receipt["type"] == "message" else payload["message_id"]
            records = {f"messages/{mid}.json" if receipt["type"] == "message" else f"acks/{mid}.json": encode(payload)}
            if receipt["type"] == "message":
                records[f"message-index/{mid}.json"] = encode({k: payload[k] for k in ("id", "from", "to", "created_at", "delivery")})
            uncertain_destination = receipt.get("uncertain_destination")
            if uncertain_destination is None and receipt.get("state") == "outcome_unknown":
                uncertain_destination = next((address for address in receipt["destinations"]
                                              if address not in receipt["completed"]), None)
            for address in receipt["destinations"]:
                if address in receipt["completed"]:
                    continue
                try:
                    store = open_store(address, self.app.home)
                    state = store.message_snapshot()
                    snap, main = state.messages, state.main
                    expected, changes = {}, {}
                    for logical, raw in records.items():
                        target = shared_path(snap, logical)
                        existing = snap.bytes(target)
                        if existing is not None and existing != raw:
                            raise Conflict("Existing protocol record has different bytes; refusing overwrite.")
                        expected[target] = snap.entries.get(target)
                        if existing is None:
                            changes[target] = raw
                    if changes:
                        if address == uncertain_destination:
                            return receipt
                        permission_expected = {}
                        meta_path = shared_path(main, "workspace.json")
                        meta = main.json(meta_path)
                        permission_expected[meta_path] = main.entries[meta_path]
                        own_address = self.app.store(receipt["workspace"]).address
                        if address == own_address:
                            actor_id = receipt.get("sender") or receipt.get("receiver")
                            source_worker = self._source(receipt["workspace"], actor_id, receipt["binding"], main)
                            recorded_worker = receipt.get("sender_worker") if receipt["type"] == "message" else receipt.get("receiver_worker")
                            if recorded_worker is not None and source_worker != recorded_worker:
                                raise Conflict("The original publication belongs to another Worker.")
                            permission_expected.update(self._entry_expected(receipt["workspace"], main, actor_id,
                                                                            receipt["binding"], source_worker))
                            if receipt["type"] == "ack":
                                index_path = shared_path(snap, f"message-index/{mid}.json")
                                index = snap.json(index_path)
                                if (index is None or index["to"]["workspace"] != meta["locator"]
                                        or index["to"]["agent"] != actor_id):
                                    raise Conflict("The original ACK notification no longer targets this receiver.")
                                endpoint = self._address(receipt["workspace"], main, index["to"], mid)
                                if endpoint.get("worker") != source_worker:
                                    raise Conflict("The original ACK notification belongs to another Worker.")
                                expected[index_path] = snap.entries[index_path]
                        if receipt["type"] == "message":
                            locator = payload["from"]["workspace"] if address == own_address else payload["to"]["workspace"]
                            if meta["locator"] != locator:
                                raise Conflict("The original publication destination has a different Workspace.")
                            if meta["locator"] == payload["to"]["workspace"]:
                                agent_path = shared_path(main, f"agents/{payload['to']['agent']}.json")
                                agent = main.json(agent_path)
                                if agent is None or agent["archived"]:
                                    raise Error("Target is archived or missing; publication remains incomplete.")
                                permission_expected[agent_path] = main.entries[agent_path]
                                endpoint = self._address(receipt["workspace"], main, payload["to"], mid)
                                if endpoint.get("worker") is not None:
                                    worker_path, selected, _ = workers.execution_record(self.app, receipt["workspace"],
                                        endpoint["agent"], main, endpoint["worker"])
                                    if selected["archived"]:
                                        raise Error("Target Worker is archived; publication remains incomplete.")
                                    permission_expected[worker_path] = main.entries[worker_path]
                        store.message_change(state, changes, expected_layout(snap, expected),
                            f"Publish {receipt['type']} {mid}", permission_expected=permission_expected)
                    receipt["completed"].append(address)
                    if address == uncertain_destination:
                        receipt.pop("uncertain_destination", None)
                    receipt.pop("error", None)
                    write_json(path, receipt)
                except (Error, OSError, TimeoutError) as exc:
                    receipt["error"] = str(exc)
                    if isinstance(exc, Uncertain) or address == uncertain_destination:
                        receipt["state"] = "outcome_unknown"
                        receipt["uncertain_destination"] = address
                    else:
                        receipt["state"] = "pending"
                    write_json(path, receipt)
                    return receipt
            receipt["state"] = "published"
            write_json(path, receipt)
            return receipt

    def list(self, workspace, agent_id=None, direction="in", unacked=False, worker_id=None):
        state = self.app.store(workspace).message_snapshot()
        return self._list(state.messages, state.main, agent_id, direction, unacked,
                          workspace=workspace, worker_id=worker_id)

    def _list(self, snap, main, agent_id=None, direction="in", unacked=False, *, workspace=None, worker_id=None):
        if worker_id is not None and agent_id is None:
            raise Error("A Worker filter requires its Agent.")
        meta = main.json(shared_path(main, "workspace.json"))
        prefix = shared_path(snap, "message-index") + "/"
        result = []
        for path in snap.entries:
            if not path.startswith(prefix):
                continue
            item = snap.json(path)
            if agent_id:
                side = item["to"] if direction == "in" else item["from"]
                if side.get("workspace") != meta["locator"] or side.get("agent") != agent_id:
                    continue
                if worker_id is not None:
                    endpoint = self._address(workspace, main, side, item["id"])
                    if endpoint.get("worker") != worker_id:
                        continue
            acked = shared_path(snap, f"acks/{item['id']}.json") in snap.entries
            if unacked and acked:
                continue
            result.append({**item, "notification_acknowledged": acked})
        return sorted(result, key=lambda m: (m["created_at"], m["id"]))

    def show(self, workspace, message_id):
        snap = self.app.store(workspace).message_snapshot().messages
        item = snap.json(shared_path(snap, f"messages/{slug(message_id)}.json"))
        if item is None:
            raise Error("Message not found.")
        return {"message": item, "ack": snap.json(shared_path(snap, f"acks/{message_id}.json"))}

    def receive(self, workspace, agent_id, binding, message_id, directory=None, worker_id=None):
        own = self.app.store(workspace)
        state = own.message_snapshot()
        snap, main = state.messages, state.main
        meta = main.json(shared_path(main, "workspace.json"))
        actual_worker = self._source(workspace, agent_id, binding, main, worker_id)
        mid = slug(message_id)
        envelope = snap.json(shared_path(snap, f"message-index/{mid}.json"))
        if (not envelope or envelope["to"].get("workspace") != meta["locator"]
                or envelope["to"].get("agent") != agent_id):
            raise Error("The notification does not target this instance.")
        endpoint = self._address(workspace, main, envelope["to"], mid)
        if endpoint.get("worker") != actual_worker:
            raise Conflict("Only the addressed Worker's current Binding may acknowledge this notification.")
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
                    "completed": [], "receiver": agent_id, "receiver_worker": actual_worker, "binding": binding})
        result["publication"] = self.reconcile(opid)
        if result["publication"]["state"] != "published":
            result["instruction"] = "ACK publication is incomplete. Preserve this result; reconcile the original operation before new business effects."
        try:
            root = self.app.root(workspace, agent_id, directory)
        except Error:
            root = None
        if root is not None:
            with layout_lock(root, "files.lock"):
                write_json(instance_path(root, f"messages/{mid}.json", worker_id=actual_worker), {
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

    def _head(self, snap, main, workspace, agent_id, binding):
        actual_worker = self._source(workspace, agent_id, binding, main)
        messages = self._list(snap, main, agent_id, unacked=True, workspace=workspace, worker_id=actual_worker)
        return messages[0] if messages else None

    def _dispatch(self, state, workspace, agent_id, binding, message, attempts, *, manual_attempt_id=None):
        snap, main = state.messages, state.main
        worker_id = self._source(workspace, agent_id, binding, main)
        path = self._dispatch_path(snap, agent_id, worker_id)
        record = {"message_id": message["id"], "workspace": workspace, "agent": agent_id,
                  "binding": binding, "delivery": message["delivery"],
                  "attempts": attempts, "attempted_at": time.time()}
        if manual_attempt_id is not None:
            record["manual_attempt_id"] = manual_attempt_id
        if worker_id is not None:
            record["worker"] = worker_id
        expected = {path: snap.entries.get(path), shared_path(snap, f"acks/{message['id']}.json"): None}
        if worker_id is not None:
            legacy_path = shared_path(snap, f"dispatch/{agent_id}.json")
            expected[legacy_path] = snap.entries.get(legacy_path)
        for original in (f"messages/{message['id']}.json", f"message-index/{message['id']}.json"):
            original_path = shared_path(snap, original)
            expected[original_path] = snap.entries.get(original_path)
        self.app.store(workspace).message_change(state, {path: encode(record)},
            expected_layout(snap, expected), "Claim notification attempt",
            permission_expected=self._entry_expected(workspace, main, agent_id, binding, worker_id))
        return record

    def preview_manual(self, workspace, agent_id, binding, worker_id=None):
        state = self.app.store(workspace).message_snapshot()
        snap, main = state.messages, state.main
        worker_id = self._source(workspace, agent_id, binding, main, worker_id)
        message = self._head(snap, main, workspace, agent_id, binding)
        if message is None:
            return {"state": "empty"}
        if message["delivery"] != "normal":
            return {"state": "delivery_unsupported", "message_id": message["id"],
                    "delivery": message["delivery"]}
        previous = self._previous_dispatch(snap, main, workspace, agent_id, worker_id)
        if previous.get("message_id") == message["id"]:
            return {"state": "waiting_ack", "message_id": message["id"]}
        prompt = self._notification(snap, message, require_body=True)
        notification = {"message_id": message["id"], "workspace": workspace,
                        "agent": agent_id, "binding": binding, "delivery": message["delivery"]}
        if worker_id is not None:
            notification["worker"] = worker_id
        return {"state": "ready", "message_id": message["id"], "prompt_digest": digest(prompt.encode()),
                "notification": notification,
                "prompt": prompt}

    def claim_manual(self, workspace, agent_id, binding, message_id, attempt_id, expected_prompt_digest, worker_id=None):
        """Share poll's FIFO and dispatch claim; a manual outcome is never retried."""
        mid, attempt = slug(message_id), slug(attempt_id)
        state = self.app.store(workspace).message_snapshot()
        snap, main = state.messages, state.main
        worker_id = self._source(workspace, agent_id, binding, main, worker_id)
        message = self._head(snap, main, workspace, agent_id, binding)
        if message is None or message["id"] != mid:
            raise Conflict("The original message is no longer the unacknowledged FIFO head.")
        if message["delivery"] != "normal":
            raise Error("This manual Web route does not support insert delivery.")
        previous = self._previous_dispatch(snap, main, workspace, agent_id, worker_id)
        if previous.get("message_id") == mid:
            raise Conflict("The original message already has a notification attempt; inspect it without claiming again.")
        prompt = self._notification(snap, message, require_body=True)
        if digest(prompt.encode()) != expected_prompt_digest:
            raise Conflict("The original notification changed before this attempt.")
        self._dispatch(state, workspace, agent_id, binding, message, 1, manual_attempt_id=attempt)
        return {"state": "claimed", "message_id": mid, "attempt_id": attempt}

    def poll(self, workspace, agent_id, binding, *, adapter=None, directory=None,
             retry_seconds=60, max_attempts=3, worker_id=None):
        store = self.app.store(workspace)
        state = store.message_snapshot()
        snap, main = state.messages, state.main
        worker_id = self._source(workspace, agent_id, binding, main, worker_id)
        message = self._head(snap, main, workspace, agent_id, binding)
        if message is None:
            return {"state": "empty"}
        notification = {"message_id": message["id"], "workspace": workspace, "agent": agent_id,
                        "binding": binding, "delivery": message["delivery"]}
        if worker_id is not None:
            notification["worker"] = worker_id
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
        state = store.message_snapshot()
        snap, main = state.messages, state.main
        self.app.require_binding(workspace, agent_id, binding, snapshot=main)
        previous = self._previous_dispatch(snap, main, workspace, agent_id, worker_id)
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
        self._dispatch(state, workspace, agent_id, binding, message, attempts + 1)
        self.app.require_binding(workspace, agent_id, binding)
        try:
            adapter.notify(prompt, message["delivery"])
        except Exception as exc:
            return {"state": "notification_outcome_unknown", "message_id": message["id"], "error": str(exc),
                    "instruction": "Await ACK; do not generate another Message."}
        return {"state": "notified_waiting_ack", "message_id": message["id"]}
