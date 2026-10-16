"""Optional native-send history; never an AW Message delivery source."""
from __future__ import annotations

from . import workers
from .messages import Messages
from .layout import expected as expected_layout, shared_path
from .util import Conflict, Error, Uncertain, encode, now, slug, uid


class DirectMessages:
    def __init__(self, app):
        self.app = app

    def record(self, workspace, agent_id, binding, to=None, content=None, request_id=None,
               record_type="codex", result=None, receipt=None, *, worker_id=None, to_worker=None, reply_to=None):
        """Save reported facts without sending, acknowledging or retrying anything."""
        identifier = request_id or uid("direct-")
        try:
            identifier = slug(identifier)
            if record_type != "codex" or not isinstance(content, str) or not content.strip():
                raise Error("A direct record requires type codex and nonempty content.")
            if any(value is not None and not isinstance(value, dict) for value in (result, receipt)):
                raise Error("Native result and optional receipt must be JSON objects.")
            store = self.app.store(workspace)
            snap = store.snapshot()
            routing = Messages(self.app)
            source_worker = routing._source(workspace, agent_id, binding, snap, worker_id)
            meta = snap.json(shared_path(snap, "workspace.json"))
            path = shared_path(snap, f"direct-messages/{identifier}.json")
            existing = snap.json(path)
            request = {"to": to, "to_worker": to_worker, "reply_to": reply_to}
            if existing is not None:
                source = routing._address(workspace, snap, existing["from"], identifier)
                if (source.get("worker") != source_worker or source["agent"] != agent_id
                        or source["workspace"] != meta["locator"] or existing["type"] != record_type
                        or existing["content"] != content):
                    raise Conflict("Direct record ID belongs to different content or endpoints.")
                if "route_request" in existing:
                    if existing["route_request"] != request:
                        raise Conflict("Direct record ID belongs to another original target.")
                else:
                    target, target_meta, target_id = routing._target(workspace, to)
                    endpoint = routing._address(workspace, target.snapshot(), existing["to"], identifier)
                    if (reply_to is not None or endpoint["agent"] != target_id
                            or endpoint["workspace"] != target_meta["locator"]
                            or to_worker is not None and endpoint.get("worker") != to_worker):
                        raise Conflict("Direct record ID belongs to another original target.")
                body = dict(existing)
            else:
                if reply_to is not None:
                    original = snap.json(shared_path(snap, f"direct-messages/{slug(reply_to)}.json"))
                    if original is None:
                        raise Error("The original native-send record is unavailable.")
                    target, target_meta = routing._peer(workspace, original["from"]["workspace"])
                    target_snap = target.snapshot()
                    endpoint = routing._address(workspace, target_snap, original["from"], reply_to)
                    target_id = endpoint["agent"]
                    if to is not None:
                        _, requested_meta, requested_id = routing._target(workspace, to)
                        if (requested_meta["locator"], requested_id) != (target_meta["locator"], target_id):
                            raise Conflict("reply_to fixes the original native sender.")
                    if to_worker is not None and endpoint.get("worker") != to_worker:
                        raise Conflict("reply_to fixes the original native sender Worker.")
                else:
                    target, target_meta, target_id = routing._target(workspace, to)
                    target_snap = target.snapshot()
                    endpoint = {"workspace": target_meta["locator"], "agent": target_id}
                    receiver = workers.agent_record(target_snap, target_id)
                    if workers.enabled(target_snap, receiver):
                        if to_worker is None:
                            raise Error("Record the actual native target Worker; do not infer it from a later default.")
                        endpoint["worker"] = self.app.worker(workspace, target_id, to_worker, snapshot=target_snap)["id"]
                    elif to_worker is not None:
                        raise Error("The native target Agent has not enabled Workers.")
                receiver = workers.agent_record(target_snap, target_id)
                if receiver["archived"]:
                    raise Error("Target agent is archived.")
                if endpoint.get("worker") is not None and self.app.worker(workspace, target_id,
                        endpoint["worker"], snapshot=target_snap)["archived"]:
                    raise Error("Target Worker is archived.")
                source = {"workspace": meta["locator"], "agent": agent_id}
                if source_worker is not None:
                    source["worker"] = source_worker
                body = {"id": identifier, "type": record_type, "from": source, "to": endpoint, "content": content}
                if source_worker is not None or endpoint.get("worker") is not None:
                    body["route_request"] = request
                body["created_at"] = now()
            for key, value in (("result", result), ("receipt", receipt)):
                if value is None:
                    continue
                if key in body and body[key] != value:
                    raise Conflict(f"The direct record already contains a different {key}.")
                body[key] = value
            if body != existing:
                expected = {path: snap.entries.get(path),
                            **routing._entry_expected(workspace, snap, agent_id, binding, source_worker)}
                if existing is None and target.address == store.address:
                    target_path = shared_path(snap, f"agents/{target_id}.json")
                    expected[target_path] = snap.entries[target_path]
                    if endpoint.get("worker") is not None:
                        target_path, _, _ = workers.execution_record(self.app, workspace, target_id, snap, endpoint["worker"])
                        expected[target_path] = snap.entries[target_path]
                store.change("main", {path: encode(body)}, expected_layout(snap, expected), f"Record native send {identifier}")
            return {"recorded": True, "record_id": identifier, "record": body}
        except (Error, OSError, TimeoutError, ValueError, TypeError) as exc:
            # Recording is optional. A failed/unknown write cannot undo a native send.
            return {"recorded": None if isinstance(exc, Uncertain) else False,
                    "record_id": identifier, "error": str(exc),
                    "code": getattr(exc, "code", "record_failed")}

    def list(self, workspace, agent_id=None, direction="in", worker_id=None):
        if direction not in ("in", "out"):
            raise Error("Direction must be in or out.")
        snap = self.app.store(workspace).snapshot()
        locator = snap.json(shared_path(snap, "workspace.json"))["locator"]
        prefix = shared_path(snap, "direct-messages") + "/"
        result = []
        if worker_id is not None and agent_id is None:
            raise Error("A Worker history filter requires its Agent.")
        for path in snap.entries:
            if not path.startswith(prefix):
                continue
            record = snap.json(path)
            if agent_id:
                side = record["to"] if direction == "in" else record["from"]
                if side.get("workspace") != locator or side.get("agent") != agent_id:
                    continue
                if worker_id is not None and Messages(self.app)._address(workspace, snap, side, record["id"]).get("worker") != worker_id:
                    continue
            result.append(record)
        return sorted(result, key=lambda record: (record["created_at"], record["id"]))

    def show(self, workspace, record_id):
        snap = self.app.store(workspace).snapshot()
        return {"record": snap.json(shared_path(snap, f"direct-messages/{slug(record_id)}.json"))}
