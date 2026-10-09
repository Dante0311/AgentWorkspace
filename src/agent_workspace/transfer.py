"""Durable same-instance handoff to a chosen native Harness.

Each side effect is tied to one old binding and one preselected successor ID.
An uncertain launch is inspected, never replaced by another new session.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import os

from .util import Conflict, Error, locked, now, read_json, slug, uid, write_json


def preflight(app, workspace, agent_id, config, root):
    from .shared import requirements
    requirements(app, workspace, root)
    if (root / ".aw-local/skill-install/operation.json").exists():
        raise Conflict("Recover the pending Skill update before handing off.")
    from .native_sdk import SDK_TYPES, sdk_options
    kind = config.get("kind")
    if config.get("credential_env") and not os.environ.get(config["credential_env"]):
        raise Error("Target credential environment variable is missing; the old entry was not handed off.")
    if kind == "codex":
        command = config.get("command", ["codex", "app-server"])
        if not command or not (Path(command[0]).is_file() or shutil.which(command[0])):
            raise Error("Target Codex executable is unavailable; the old session was not handed off.")
    elif kind in SDK_TYPES:
        if not config.get("executable") or not Path(config["executable"]).is_file():
            raise Error("Target native CLI is unavailable; install it before handoff.")
        sdk_options(config, app, workspace, agent_id, "", root)
    elif kind == "desktop":
        from .runtime import Desktop
        adapter = Desktop(root, config, None)
        try:
            adapter.project()
        finally:
            adapter.close()
    else:
        raise Error("Automatic transfer needs a managed native entry; no Desktop/CLI substitution.")


def request(app, workspace, agent_id, target_config, request_id=None, directory=None):
    from .runtime import handoff_request
    if not isinstance(target_config, dict):
        raise Error("target_config must be a native runtime configuration object.")
    root = app.root(workspace, agent_id, directory)
    path = root / ".aw-local/transfer.json"
    identifier = slug(request_id or uid("transfer-"))
    with locked(root / ".aw-local/transfer.lock"):
        archived = read_json(root / ".aw-local/transfers" / (identifier + ".json"))
        if archived:
            if archived["target_config"] != target_config:
                raise Conflict("Transfer request ID already has a different target configuration.")
            return archived
        previous = read_json(path)
        if previous and previous["state"] != "completed":
            previous = status(app, workspace, agent_id, directory)
        if previous and previous["id"] == identifier:
            if previous["target_config"] != target_config:
                raise Conflict("Transfer request ID already has a different target configuration.")
            return previous
        if previous and previous["state"] != "completed":
            raise Conflict("Another transfer is unresolved; continue its original request.")
        preflight(app, workspace, agent_id, target_config, root)
        current = app.agent(workspace, agent_id)["current"]
        app.require_binding(workspace, agent_id, current)
        record = {"id": identifier, "old_binding": current, "target_binding": uid("b"),
                  "target_config": target_config, "state": "handoff_requested", "created_at": now()}
        if previous:
            write_json(root / ".aw-local/transfers" / (previous["id"] + ".json"), previous)
        write_json(path, record)
        # Stable handoff input ID is supplied by the existing implementation.
        handoff_request(app, workspace, agent_id, directory=str(root))
        return record


def advance(app, workspace, agent_id, directory=None):
    from .runtime import start
    root = app.root(workspace, agent_id, directory)
    path = root / ".aw-local/transfer.json"
    with locked(root / ".aw-local/transfer.lock"):
        record = read_json(path)
        if not record:
            raise Error("No transfer has been requested.")
        if record["state"] == "completed":
            return record
        snap = app.store(workspace).snapshot()
        agent = app.agent(workspace, agent_id, snap)
        current = agent["current"]
        if current == record["old_binding"]:
            # A request may have been persisted just before its input was queued.
            entry = snap.json(f"bindings/{current}.json")
            if entry["phase"] == "active":
                from .runtime import handoff_request
                handoff_request(app, workspace, agent_id, directory=str(root))
            return record
        if current == record["target_binding"]:
            entry = snap.json(f"bindings/{current}.json")
            record = observed_target(record, entry, root)
            write_json(path, record)
            return record
        if current is not None:
            raise Conflict("A different successor owns this instance; transfer cannot take it over.")
        old = snap.json(f"bindings/{record['old_binding']}.json")
        handoff = snap.json(f"handoffs/{agent['handoff']}.json") if agent["handoff"] else None
        if not old or old["phase"] != "released" or not handoff or handoff["entry"] != record["old_binding"]:
            raise Conflict("The original entry has not published a usable handoff.")
        if record["state"] in ("launching", "starting", "outcome_unknown"):
            raise Conflict("The original launch needs reconciliation; no replacement session was created.")
        preflight(app, workspace, agent_id, record["target_config"], root)
        # This lock also proves the original local runner has finished its cleanup.
        with locked(root / ".aw-local/runner.lock", wait=0):
            app.configure(workspace, agent_id, record["target_config"], str(root))
            record["state"] = "launching"
            write_json(path, record)
        try:
            result = start(app, workspace, agent_id, str(root), binding_id=record["target_binding"])
        except (Error, OSError) as exc:
            record.update(state="outcome_unknown", failure=type(exc).__name__)
            write_json(path, record)
            raise
        record.update(state="starting", launch=result)
        write_json(path, record)
        return record


def observed_target(record, entry, root):
    record = dict(record, session=entry["session"])
    boot = read_json(root / ".aw-local/inputs" / f"boot-{record['target_binding']}.json", {})
    if (entry["session"] and entry["phase"] in ("active", "stopping", "released")
            and boot.get("binding") == record["target_binding"]
            and boot.get("state") == "completed" and boot.get("checkpoint_revision")):
        record["state"] = "completed"
    elif entry["phase"] == "active" and entry["session"]:
        record["state"] = "relay_failed" if boot.get("state") == "failed" else "session_bound"
    else:
        record["state"] = "outcome_unknown" if record.get("failure") else "starting"
    return record


def persist_completion(root, entry):
    """The successor runner records boot success, independently of UI queries.

    Share the launch lock: a fast boot must not be overwritten by advance()'s
    final starting write. An older runner must not modify a later transfer.
    """
    path = root / ".aw-local/transfer.json"
    record = read_json(path)
    if not record or record["state"] == "completed" or record["target_binding"] != entry["id"]:
        return
    with locked(root / ".aw-local/transfer.lock"):
        record = read_json(path)
        if not record or record["state"] == "completed" or record["target_binding"] != entry["id"]:
            return
        observed = observed_target(record, entry, root)
        if observed["state"] == "completed":
            write_json(path, observed)


def status(app, workspace, agent_id, directory=None):
    root = app.root(workspace, agent_id, directory)
    record = read_json(root / ".aw-local/transfer.json", {"state": "none"})
    if "target_binding" in record and record["state"] != "completed":
        snap = app.store(workspace).snapshot()
        if app.agent(workspace, agent_id, snap)["current"] == record["target_binding"]:
            return observed_target(record, snap.json(f"bindings/{record['target_binding']}.json"), root)
    return record


def request_profile(app, workspace, agent_id, kind, model="", effort="", base_url="", env_key="", executable=None,
                    allowed_tools=None, request_id=None, *, allow_http=False):
    from .harness_config import codex_config, sdk_config
    if kind == "codex":
        if allowed_tools:
            raise Error("Native SDK tool allowlists do not configure Codex permissions.")
        config = codex_config(model, effort, base_url, env_key, executable, allow_http=allow_http)
    else:
        config = sdk_config(kind, model, effort, base_url, env_key, executable, allowed_tools, allow_http=allow_http)
    return request(app, workspace, agent_id, config, request_id)
