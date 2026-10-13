"""One manually confirmed ChatGPT Web notification through a restricted local connection."""
from __future__ import annotations

import hmac
import re
import secrets
from urllib.parse import urlsplit

from .layout import shared_path
from .messages import Messages
from .util import Conflict, Error, digest, locked, now, read_json, slug, write_json


def canonical_target(value):
    if not isinstance(value, str):
        raise Error("A ChatGPT conversation URL is required.")
    try:
        parsed = urlsplit(value)
        path = parsed.path.rstrip("/")
        valid = (parsed.scheme == "https" and parsed.netloc == "chatgpt.com"
                 and not parsed.username and not parsed.password
                 and re.fullmatch(r"/c/[a-zA-Z0-9_-]{1,256}", path))
    except ValueError:
        valid = False
    if not valid:
        raise Error("Use an exact https://chatgpt.com/c/<id> conversation URL.")
    return "https://chatgpt.com" + path


def _paths(app, connection_id):
    root = app.home / "web-courier"
    return root / "connections" / (slug(connection_id) + ".json"), root / "attempts" / (connection_id + ".json")


def _connection(app, connection_id):
    path, _ = _paths(app, connection_id)
    record = read_json(path)
    if record is None:
        raise Error("Unknown Web Courier connection.")
    return record


def _entry(app, connection):
    workspace, agent, binding = connection["workspace"], connection["agent_id"], connection["binding"]
    snap = app.store(workspace).snapshot()
    _, entry = app.require_binding(workspace, agent, binding, snapshot=snap)
    if entry["kind"] != "manual" or not entry.get("session"):
        raise Conflict("Web Courier requires this instance's current manual session.")
    session = entry["session"]
    if session != connection["target_url"].rsplit("/", 1)[1]:
        try:
            same = canonical_target(session) == connection["target_url"]
        except Error:
            same = False
        if not same:
            raise Conflict("The current manual session does not match the registered conversation.")
    from .maintenance import installation_id
    execution = entry.get("execution") or {}
    if execution.get("installation_id") != installation_id(app):
        raise Conflict("The current entry belongs to another AW installation.")
    directory = execution.get("directory")
    if not directory:
        raise Conflict("The current entry has no local instance directory.")
    app.root(workspace, agent, directory)
    return snap


def _public(connection):
    return {key: value for key, value in connection.items() if key != "token"}


def connect(app, workspace, agent_id, expected_binding, target_url, extension_id, request_id, *, port=8765):
    """User-management action. Return the scoped token only from this explicit call."""
    connection_id = slug(request_id)
    slug(workspace); slug(agent_id); slug(expected_binding)
    target = canonical_target(target_url)
    if not isinstance(extension_id, str) or not re.fullmatch(r"[a-p]{32}", extension_id):
        raise Error("An actual Chrome extension ID is required.")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise Error("A valid local AW backend port is required.")
    proposed = {"id": connection_id, "workspace": workspace, "agent_id": agent_id,
                "binding": expected_binding, "target_url": target, "extension_id": extension_id,
                "backend_url": f"http://127.0.0.1:{port}", "state": "active"}
    path, _ = _paths(app, connection_id)
    with locked(path.with_suffix(".lock")):
        existing = read_json(path)
        if existing:
            if any(existing.get(key) != value for key, value in proposed.items() if key != "state"):
                raise Conflict("Connection request ID belongs to different settings.")
            if existing["state"] != "active":
                raise Conflict("This connection was revoked; its original request cannot reactivate it.")
            return {**_public(existing), "token": existing["token"], "connection_id": connection_id}
        _entry(app, proposed)
        record = {**proposed, "token": secrets.token_urlsafe(32), "created_at": now()}
        write_json(path, record)
        return {**_public(record), "token": record["token"], "connection_id": connection_id}


def _attempt_status(app, connection, snap=None):
    _, attempt_path = _paths(app, connection["id"])
    attempt = read_json(attempt_path)
    if attempt is None:
        return None, None
    snap = snap or app.store(connection["workspace"]).snapshot()
    dispatch = snap.json(shared_path(snap, f"dispatch/{connection['agent_id']}.json"), {})
    claimed = (attempt.get("claim_state") == "confirmed"
               or (dispatch.get("message_id") == attempt["message_id"]
                   and dispatch.get("binding") == connection["binding"]
                   and dispatch.get("manual_attempt_id") == attempt["attempt_id"]))
    return {"message_id": attempt["message_id"], "attempt_id": attempt["attempt_id"],
            "claim_state": "confirmed" if claimed else "outcome_unknown",
            "web_fact": attempt.get("web_fact", "unknown"), "attempted_at": attempt["attempted_at"]}, attempt


def status(app, connection_id):
    connection = _connection(app, connection_id)
    unknown_reason = None
    try:
        snap = _entry(app, connection) if connection["state"] == "active" else None
        eligible = connection["state"] == "active"
    except Conflict:
        snap = None
        eligible = False
    except (Error, OSError, ValueError):
        snap = None
        eligible = None
        unknown_reason = "current_entry_unavailable"
    safe_attempt, attempt = _attempt_status(app, connection, snap)
    ack = None
    if attempt:
        snap = snap or app.store(connection["workspace"]).snapshot()
        ack = snap.json(shared_path(snap, f"acks/{attempt['message_id']}.json"))
        if ack is not None and ack != {"message_id": attempt["message_id"]}:
            raise Error("The original ACK record is malformed; acknowledgement is unknown.")
    return {**_public(connection), "connection_id": connection["id"], "eligible": eligible,
            "unknown_reason": unknown_reason, "attempt": safe_attempt, "ack": ack}


def revoke(app, connection_id, request_id):
    slug(request_id)
    path, _ = _paths(app, connection_id)
    with locked(path.with_suffix(".lock")):
        record = _connection(app, connection_id)
        if record["state"] == "revoked":
            if record["revocation_id"] != request_id:
                raise Conflict("Connection is already revoked by a different request.")
        else:
            record.update(state="revoked", revocation_id=request_id, revoked_at=now())
            write_json(path, record)
        return {"connection_id": connection_id, "state": "revoked", "revoked_at": record["revoked_at"]}


def authorize(app, connection_id, token, origin):
    connection = _connection(app, connection_id)
    if (connection["state"] != "active" or not isinstance(token, str) or not token.isascii()
            or not hmac.compare_digest(token, connection["token"])):
        raise Conflict("Web Courier connection is not authorized.")
    expected_origin = "chrome-extension://" + connection["extension_id"]
    if origin is not None and origin != expected_origin:
        raise Conflict("Web Courier request has a different extension origin.")
    _entry(app, connection)
    return connection


def preflight(app, connection_id, origin):
    connection = _connection(app, connection_id)
    if (connection["state"] != "active" or not origin
            or origin != "chrome-extension://" + connection["extension_id"]):
        raise Conflict("Web Courier preflight has a different extension origin.")
    _entry(app, connection)
    return origin


def handle(app, connection_id, token, origin, body):
    """The extension can only inspect or claim its original single notification."""
    if not isinstance(body, dict) or body.get("action") not in ("get", "begin", "report", "status"):
        raise Error("Unknown Web Courier action.")
    connection = authorize(app, connection_id, token, origin)
    action = body["action"]
    if action == "status":
        return status(app, connection_id)
    if action == "get":
        _, attempt_path = _paths(app, connection_id)
        if read_json(attempt_path) is not None:
            return {"state": "attempt_exists", "attempt": status(app, connection_id)["attempt"]}
        return Messages(app).preview_manual(connection["workspace"], connection["agent_id"], connection["binding"])
    if action == "begin":
        mid, attempt_id = slug(body.get("message_id")), slug(body.get("attempt_id"))
        if body.get("binding") != connection["binding"] or body.get("target_url") != connection["target_url"]:
            raise Conflict("The requested entry or conversation changed.")
        path, attempt_path = _paths(app, connection_id)
        with locked(path.with_suffix(".lock")):
            connection = authorize(app, connection_id, token, origin)
            if read_json(attempt_path) is not None:
                raise Conflict("Original Web Courier attempt exists; use status without starting it again.")
            preview = Messages(app).preview_manual(connection["workspace"], connection["agent_id"], connection["binding"])
            if preview["state"] == "delivery_unsupported":
                raise Error("Web Courier does not support insert delivery; the original Message is unchanged.")
            if preview["state"] != "ready" or preview["message_id"] != mid:
                raise Conflict("The original notification is no longer ready at the FIFO head.")
            if body.get("prompt_digest") != preview["prompt_digest"]:
                raise Conflict("The original notification changed after the extension fetched it.")
            attempt = {"connection_id": connection_id, "message_id": mid, "attempt_id": attempt_id,
                       "binding": connection["binding"], "target_url": connection["target_url"],
                       "prompt_digest": digest(preview["prompt"].encode()), "attempted_at": now(),
                       "claim_state": "claiming", "web_fact": "unknown"}
            write_json(attempt_path, attempt)
            claimed = Messages(app).claim_manual(connection["workspace"], connection["agent_id"],
                connection["binding"], mid, attempt_id, attempt["prompt_digest"])
            attempt["claim_state"] = "confirmed"
            write_json(attempt_path, attempt)
            return claimed
    mid, attempt_id = slug(body.get("message_id")), slug(body.get("attempt_id"))
    _, attempt_path = _paths(app, connection_id)
    path, _ = _paths(app, connection_id)
    with locked(path.with_suffix(".lock")):
        connection = authorize(app, connection_id, token, origin)
        attempt = read_json(attempt_path)
        if not attempt or (attempt["message_id"], attempt["attempt_id"]) != (mid, attempt_id):
            raise Conflict("Web Courier report does not match its original attempt.")
        if body.get("target_url") != connection["target_url"]:
            raise Conflict("The report targets another conversation.")
        fact = body.get("web_fact")
        if fact not in ("unknown", "observed", "reload_verified"):
            raise Error("Unknown Web Courier page fact.")
        if fact == "reload_verified" or fact == "observed" and attempt["web_fact"] == "unknown":
            attempt["web_fact"] = fact
            write_json(attempt_path, attempt)
        return status(app, connection_id)
