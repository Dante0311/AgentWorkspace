"""One-time, user-approved changes to saved Codex model choices."""
from __future__ import annotations

from contextlib import ExitStack
import ctypes
import json
import os
from pathlib import Path

from . import layout, model_profiles, workers
from .util import Conflict, Error, digest, locked, now, read_json, slug, write_json


def _request_path(app, workspace, request_id):
    slug(workspace)
    slug(request_id)
    return app.home / "model-change-requests" / workspace / f"{request_id}.json"


def _binding(app, workspace, agent_id):
    snap = app.store(workspace).snapshot()
    agent = workers.agent_record(snap, agent_id)
    if workers.enabled(snap, agent):
        # This request changes the Agent's common defaults. No default Worker
        # selects its target; retain every Worker's entry for the review check.
        bindings = {}
        for worker in app.workers(workspace, agent_id, snapshot=snap):
            binding = worker["current"]
            if binding:
                entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
                if (not isinstance(entry, dict) or entry.get("id") != binding or entry.get("agent") != agent_id
                        or app.binding_worker(workspace, agent_id, entry, snap) != worker["id"]):
                    raise Conflict(f"Current binding for {agent_id}/{worker['id']} is inconsistent.")
            bindings[worker["id"]] = binding
        return agent, bindings
    binding = agent.get("current")
    entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json")) if binding else None
    if binding and (not isinstance(entry, dict) or entry.get("id") != binding
                    or entry.get("agent") != agent_id):
        raise Conflict(f"Current binding for {agent_id} is inconsistent.")
    return agent, binding


def _root(app, workspace, agent_id):
    root = app.root(workspace, agent_id).resolve()
    registered = app.local()["workspaces"][workspace].get("instances", {}).get(agent_id, [])
    if str(root) not in {str(Path(path).expanduser().resolve()) for path in registered}:
        raise Conflict(f"The selected directory for {agent_id} is no longer registered.")
    identity = read_json(layout.instance_path(root, "identity.json"), {})
    locator = app.local()["workspaces"][workspace]["locator"]
    if (not isinstance(identity, dict) or identity.get("workspace") != locator
            or identity.get("agent") != agent_id):
        raise Conflict(f"The registered directory identity for {agent_id} changed.")
    return root


def _target(app, workspace, change):
    agent_id = slug(change["agent_id"])
    choice = model_profiles.validate({"model": change["model"], "effort": change["effort"]})
    agent, binding = _binding(app, workspace, agent_id)
    if agent.get("archived"):
        raise Conflict(f"Agent {agent_id} is archived.")
    root = _root(app, workspace, agent_id)
    runtime = read_json(layout.local_path(root, "runtime.json"), {"kind": "manual"})
    if not isinstance(runtime, dict) or runtime.get("kind") not in model_profiles.CODEX_KINDS:
        raise Error(f"Agent {agent_id} is not a Codex or Desktop instance.")
    path = layout.instance_path(root, "config.json")
    raw = path.read_bytes() if path.exists() else b"{}"
    try:
        config = json.loads(raw)
    except ValueError as exc:
        raise Error(f"Agent {agent_id} config.json is not valid JSON.") from exc
    if not isinstance(config, dict):
        raise Error(f"Agent {agent_id} config.json must contain an object.")
    before = config.get("codex")
    if isinstance(before, dict):
        before = {key: before.get(key) for key in ("model", "effort")}
    elif before is not None:
        raise Error(f"Agent {agent_id} codex selection must be an object.")
    return {"agent_id": agent_id, "root": str(root), "binding": binding,
            "runtime_kind": runtime["kind"], "config_sha256": digest(raw),
            "before": before, "model": choice["model"], "effort": choice["effort"]}


def prepare(app, actor, /, workspace, request_id, changes):
    if not actor or not isinstance(actor, (list, tuple)) or len(actor) != 3:
        raise Error("A current Agent binding is required to prepare a model-change request.")
    caller_workspace, caller_id, caller_binding = actor
    if workspace != caller_workspace:
        raise Conflict("A model-change request must use the caller's workspace.")
    slug(workspace); slug(caller_id); slug(caller_binding)
    app.require_binding(workspace, caller_id, caller_binding)
    if not isinstance(changes, list) or not changes:
        raise Error("changes must be a non-empty list.")
    targets, seen = [], set()
    for item in changes:
        if not isinstance(item, dict) or set(item) != {"agent_id", "model", "effort"}:
            raise Error("Each change may contain only agent_id, model and effort.")
        target = _target(app, workspace, item)
        if target["agent_id"] in seen:
            raise Error("Each target may appear only once.")
        seen.add(target["agent_id"])
        targets.append(target)

    path = _request_path(app, workspace, request_id)
    requester = {"agent_id": caller_id, "binding": caller_binding}
    scope = {"workspace": workspace, "requester": requester,
             "changes": [{key: item[key] for key in ("agent_id", "model", "effort")}
                         for item in sorted(targets, key=lambda row: row["agent_id"])]}
    with locked(path.with_suffix(".lock")):
        previous = read_json(path)
        if previous is not None:
            if previous.get("scope") != scope:
                raise Conflict("request_id already belongs to a different model-change scope.")
            return _result(app, previous)
        record = {"request_id": request_id, "workspace": workspace,
                  "workspace_locator": app.local()["workspaces"][workspace]["locator"],
                  "requester": {**requester, "root": str(_root(app, workspace, caller_id))},
                  "scope": scope, "changes": targets, "state": "pending",
                  "created_at": now()}
        write_json(path, record)
    return _result(app, record)


def _current(app, record):
    workspace = record["workspace"]
    current = []
    for item in record["changes"]:
        root = _root(app, workspace, item["agent_id"])
        _, binding = _binding(app, workspace, item["agent_id"])
        runtime = read_json(layout.local_path(root, "runtime.json"), {"kind": "manual"})
        raw = layout.instance_path(root, "config.json").read_bytes() if layout.instance_path(root, "config.json").exists() else b"{}"
        try:
            config = json.loads(raw)
        except ValueError:
            config = None
        selection = config.get("codex") if isinstance(config, dict) else None
        current.append({"agent_id": item["agent_id"], "root": str(root),
                        "binding": binding, "runtime_kind": runtime.get("kind") if isinstance(runtime, dict) else None,
                        "config_sha256": digest(raw), "selection": selection})
    return current


def _result(app, record):
    observation_error = None
    try:
        current = _current(app, record)
    except (Error, ValueError, OSError, KeyError) as exc:
        current = []
        observation_error = {"type": type(exc).__name__, "reason": "Current choices could not be read."}
    result = {"request_id": record["request_id"], "workspace": record["workspace"],
            "state": record["state"], "requester": record["requester"],
            "changes": [{**{key: item[key] for key in ("agent_id", "before", "model", "effort")},
                         "current": next((row["selection"] for row in current
                                          if row["agent_id"] == item["agent_id"]), None)}
                        for item in record["changes"]],
            "entry_changed": False, "approval_required": record["state"] == "pending"}
    if observation_error:
        result["current_observation_error"] = observation_error
    return result


def show(app, workspace, request_id):
    path = _request_path(app, workspace, request_id)
    record = read_json(path)
    if record is None:
        raise Error("Model-change request not found.")
    return _result(app, record)


def native_confirm(record):
    """Ask the signed-in Windows desktop user to approve this exact request."""
    if os.name != "nt":
        raise Error("Native model-change confirmation is unsupported on this platform.")
    changes = record["changes"]
    if len(changes) > 5:
        raise Error("This confirmation dialog supports at most five targets; split the request into smaller batches.")

    def display(value):
        if value is None or value == "":
            return "未设置"
        return json.dumps(value, ensure_ascii=False)

    lines = [
        f"工作区：{record['workspace']}    发起者：{record['requester']['agent_id']}",
        "",
        "确认保存以下角色的后续 Codex 启动默认值吗？",
        "",
    ]
    for item in changes:
        before = item.get("before") or {}
        lines.extend((
            item["agent_id"],
            f"  model: {display(before.get('model'))} → {display(item['model'])}",
            f"  effort: {display(before.get('effort'))} → {display(item['effort'])}",
            "",
        ))
    lines.append("只影响后续启动；不会改变当前会话。选择“是”保存；“否”或“取消”保持不变。")
    text = "\n".join(lines)
    if len(text) > 2000:
        raise Error("This confirmation dialog exceeds 2000 characters; reduce the batch size or review unusually long values.")
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    message_box = user32.MessageBoxW
    message_box.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint)
    message_box.restype = ctypes.c_int
    # MB_YESNOCANCEL | MB_ICONQUESTION | MB_DEFBUTTON2; default is No.
    result = message_box(None, text, "确认模型默认值", 0x00000003 | 0x00000020 | 0x00000100)
    if result == 0:
        code = ctypes.get_last_error()
        raise OSError(code, "Windows confirmation dialog could not be displayed.")
    if result in (2, 7):  # Cancel and No both preserve the pending request.
        return False
    if result == 6:  # Yes.
        return True
    raise Error("Windows confirmation returned an unexpected result.")


def _verify_requester(app, actor, workspace, record):
    if actor is None:
        return
    if not isinstance(actor, (list, tuple)) or len(actor) != 3:
        raise Error("A current Agent binding is required to review this request.")
    actor_workspace, agent_id, binding = actor
    if actor_workspace != workspace:
        raise Conflict("A model-change review must use the caller's workspace.")
    requester = record["requester"]
    if (requester.get("agent_id"), requester.get("binding")) != (agent_id, binding):
        raise Error("Only the Agent that prepared this request may review it.")
    app.require_binding(workspace, agent_id, binding)
    if str(_root(app, workspace, agent_id)) != requester["root"]:
        raise Conflict("Requester directory changed after this request was prepared.")


def review(app, actor, /, workspace, request_id):
    path = _request_path(app, workspace, request_id)
    with locked(path.with_suffix(".review.lock")):
        record = read_json(path)
        if record is None:
            raise Error("Model-change request not found.")
        _verify_requester(app, actor, workspace, record)
        if record["state"] != "pending":
            return _result(app, record)
        if native_confirm(record):
            # The requester may have handed off while the user was deciding.
            _verify_requester(app, actor, workspace, record)
            return _apply(app, workspace, request_id)
        return {**_result(app, record), "confirmation": "cancelled"}


def _apply(app, workspace, request_id):
    path = _request_path(app, workspace, request_id)
    lock_path = path.with_suffix(".lock")
    with locked(lock_path):
        record = read_json(path)
        if record is None:
            raise Error("Model-change request not found.")
        if record["state"] != "pending":
            return _result(app, record)
        local = app.local()["workspaces"].get(workspace)
        if not local or local.get("locator") != record["workspace_locator"]:
            raise Conflict("Workspace registration changed after this request was prepared.")
        requester = record["requester"]
        if str(_root(app, workspace, requester["agent_id"])) != requester["root"]:
            raise Conflict("Requester directory changed after this request was prepared.")
        app.require_binding(workspace, requester["agent_id"], requester["binding"])

        ordered = sorted(record["changes"], key=lambda row: str(Path(row["root"]).resolve()).casefold())
        with ExitStack() as stack:
            roots = []
            for item in ordered:
                root = _root(app, workspace, item["agent_id"])
                if str(root) != item["root"]:
                    raise Conflict(f"Registered directory for {item['agent_id']} changed after preparation.")
                stack.enter_context(layout.lock(root, "files.lock"))
                roots.append((item, root))

            checked = []
            for item, root in roots:
                agent, binding = _binding(app, workspace, item["agent_id"])
                runtime = read_json(layout.local_path(root, "runtime.json"), {"kind": "manual"})
                config_path = layout.instance_path(root, "config.json")
                raw = config_path.read_bytes() if config_path.exists() else b"{}"
                if (agent.get("archived") or binding != item["binding"]
                        or not isinstance(runtime, dict) or runtime.get("kind") != item["runtime_kind"]
                        or runtime.get("kind") not in model_profiles.CODEX_KINDS
                        or digest(raw) != item["config_sha256"]):
                    raise Conflict(f"Agent {item['agent_id']} changed after the request was prepared.")
                config = json.loads(raw)
                if not isinstance(config, dict):
                    raise Error(f"Agent {item['agent_id']} config.json must contain an object.")
                checked.append((item, config_path, config))

            record["state"] = "applying"
            record["applying_at"] = now()
            write_json(path, record)
            for item, config_path, config in checked:
                previous = config.get("codex")
                selection = dict(previous) if isinstance(previous, dict) else {}
                selection.update(model=item["model"], effort=item["effort"])
                config["codex"] = selection
                write_json(config_path, config)
            record["state"] = "applied"
            record["applied_at"] = now()
            write_json(path, record)
    return _result(app, record)
