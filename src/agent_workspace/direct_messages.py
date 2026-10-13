"""Optional native-send history; never an AW Message delivery source."""
from __future__ import annotations

from .layout import expected as expected_layout, shared_path
from .util import Conflict, Error, Uncertain, encode, now, slug, uid


class DirectMessages:
    def __init__(self, app):
        self.app = app

    def record(self, workspace, agent_id, binding, to, content, request_id=None,
               record_type="codex", result=None, receipt=None):
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
            self.app.require_binding(workspace, agent_id, binding, snapshot=snap)
            meta = snap.json(shared_path(snap, "workspace.json"))
            if "/" in to:
                alias, target_id = to.split("/", 1)
                target, target_meta = self.app.friend_store(workspace, alias)
            else:
                target_id, target, target_meta = to, store, meta
            slug(target_id)
            target_snap = snap if target.address == store.address else target.snapshot()
            receiver = target_snap.json(shared_path(target_snap, f"agents/{target_id}.json"))
            if receiver is None or receiver["archived"]:
                raise Error("Target agent does not exist or is archived.")
            path = shared_path(snap, f"direct-messages/{identifier}.json")
            body = {"id": identifier, "type": record_type,
                    "from": {"workspace": meta["locator"], "agent": agent_id},
                    "to": {"workspace": target_meta["locator"], "agent": target_id},
                    "content": content}
            existing = snap.json(path)
            if existing is not None:
                if any(existing.get(key) != value for key, value in body.items()):
                    raise Conflict("Direct record ID belongs to different content or endpoints.")
                body = dict(existing)
            else:
                body["created_at"] = now()
            for key, value in (("result", result), ("receipt", receipt)):
                if value is None:
                    continue
                if key in body and body[key] != value:
                    raise Conflict(f"The direct record already contains a different {key}.")
                body[key] = value
            if body != existing:
                agent_path = shared_path(snap, f"agents/{agent_id}.json")
                binding_path = shared_path(snap, f"bindings/{binding}.json")
                expected = {path: snap.entries.get(path),
                            agent_path: snap.entries[agent_path], binding_path: snap.entries[binding_path]}
                if target.address == store.address:
                    target_path = shared_path(target_snap, f"agents/{target_id}.json")
                    expected[target_path] = target_snap.entries[target_path]
                store.change("main", {path: encode(body)}, expected_layout(snap, expected), f"Record native send {identifier}")
            return {"recorded": True, "record_id": identifier, "record": body}
        except (Error, OSError, TimeoutError, ValueError, TypeError) as exc:
            # Recording is optional. A failed/unknown write cannot undo a native send.
            return {"recorded": None if isinstance(exc, Uncertain) else False,
                    "record_id": identifier, "error": str(exc),
                    "code": getattr(exc, "code", "record_failed")}

    def list(self, workspace, agent_id=None, direction="in"):
        if direction not in ("in", "out"):
            raise Error("Direction must be in or out.")
        snap = self.app.store(workspace).snapshot()
        locator = snap.json(shared_path(snap, "workspace.json"))["locator"]
        prefix = shared_path(snap, "direct-messages") + "/"
        result = []
        for path in snap.entries:
            if not path.startswith(prefix):
                continue
            record = snap.json(path)
            if agent_id:
                side = record["to"] if direction == "in" else record["from"]
                if side != {"workspace": locator, "agent": agent_id}:
                    continue
            result.append(record)
        return sorted(result, key=lambda record: (record["created_at"], record["id"]))

    def show(self, workspace, record_id):
        snap = self.app.store(workspace).snapshot()
        return {"record": snap.json(shared_path(snap, f"direct-messages/{slug(record_id)}.json"))}
