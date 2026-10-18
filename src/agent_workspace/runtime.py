from __future__ import annotations

from importlib.resources import files
import json
import os
from pathlib import Path
import queue
import shutil
import sys
import threading
import time
import urllib.parse
import webbrowser

from . import __version__
from . import backend, model_profiles, software, session_titles, workers
from .messages import Messages
from .shared import requirements
from .rpc import Rpc
from .native_sdk import NativeSDK, SDK_TYPES, sdk_options
from . import layout
from .util import (Conflict, Error, LockBusy, RetryableRead, Unavailable, Uncertain, digest, encode,
                   now, read_json, slug, uid, write_bytes, write_json)


TOOL_SCHEMA = {"type": "object", "properties": {"command": {"type": "string"},
    "arguments": {"type": "object"}}, "required": ["command", "arguments"], "additionalProperties": False}


class _ReadStopped(Exception):
    """The local monitor was stopped while waiting for an authoritative read."""


def entry_context(workspace, agent_id, binding, root, item, entry):
    from .desktop_projects import project_directory
    worker_id = item.get("worker_id")
    return {"workspace": workspace, "agent": agent_id, "binding": binding,
            "worker_id": worker_id, "worker": item.get("worker"),
            "worker_directory": str(root / "workers" / worker_id) if worker_id is not None else str(root),
            "binding_phase": entry["phase"], "session": entry["session"],
            "entry_mode": "relay" if entry["handoff"] else "fork" if item.get("forked_from") else "initial",
            "runtime_kind": entry["kind"], "instance_root": str(root), "instance_branch": item["branch"],
            "instructions_file": str(root / "AGENTS.md"), "skills_directory": str(root / ".agents/skills"),
            "selected_project_directory": str(project_directory(root, worker_id=worker_id)),
            "native_cwd": entry.get("execution", {}).get("cwd")}


def entry_prompt(app, workspace, agent_id, binding, root):
    snap = app.store(workspace).snapshot()
    entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
    worker_id = app.binding_worker(workspace, agent_id, entry, snap)
    item = app.agent(workspace, agent_id, snap, worker_id=worker_id)
    # Read installed guidance, not a potentially stale copy from an older checkpoint.
    capabilities = (files("agent_workspace") / "resources" / "prompts" / "capabilities.md").read_text(encoding="utf-8")
    lines = [json.dumps(entry_context(workspace, agent_id, binding, root, item, entry), ensure_ascii=False),
             (files("agent_workspace") / "resources/prompts/entry.md").read_text(encoding="utf-8"), capabilities,
             "平台命令使用 aw_execute 动态工具，或运行 aw。调用参数中的 workspace、agent_id、binding 必须使用上述值。"]
    required = requirements(app, workspace, root, snap)
    if required:
        lines.append("required_workspace_read: " + json.dumps(required, ensure_ascii=False))
    if entry["handoff"]:
        handoff = snap.json(layout.shared_path(snap, f"handoffs/{entry['handoff']}.json"))
        point = app.checkpoint_show(workspace, agent_id, handoff["checkpoint"], worker_id=worker_id)
        lines.append("以下检查点由此前入口 " + handoff["entry"] + " 保存。其中描述旧入口的 renew、stop 或交出安排是历史上下文，"
                     "不是对当前入口再次停工的指令；明确交给后继的待续业务按 relay Skill 接手。\n"
                     "交接点与检查点：\n" + json.dumps(point, ensure_ascii=False))
    elif item.get("forked_from"):
        lines.append("你是新的实例，不是历史里的发送者或负责人。来源：\n" + json.dumps(item["forked_from"], ensure_ascii=False))
    else:
        lines.append((layout.instance_path(root, "prompts/initialization.md")).read_text(encoding="utf-8"))
        lines.append("用户原始描述：\n" + item["description"])
    if entry["kind"] == "desktop":
        lines.append("本桌面会话的所有平台操作使用以下命令前缀，再加命令名及 --arguments JSON。"
                     "入口根据真实 CODEX_THREAD_ID 校验；不要设置或替换该变量。\n" +
                     json.dumps(desktop_cli(app, workspace, agent_id), ensure_ascii=False))
    return "\n\n".join(lines)


def desktop_cli(app, workspace, agent_id):
    return [sys.executable, "-m", "agent_workspace", "--home", str(app.home),
            "--workspace", workspace, "call", "--desktop-agent", agent_id]


def desktop_actor(app, workspace, agent_id):
    session = os.environ.get("CODEX_THREAD_ID")
    snap = app.store(workspace).snapshot()
    linked = snap.json(layout.shared_path(snap, f"sessions/desktop/{digest(session.encode())}.json")) if session else None
    if not linked or linked["agent"] != agent_id:
        raise Conflict("This Desktop session has no current execution entry.")
    binding = linked["binding"]
    _, entry = app.require_binding(workspace, agent_id, binding, allow_stopping=True, snapshot=snap)
    if entry["kind"] != "desktop" or entry["session"] != session:
        raise Conflict("The real Desktop session does not own this execution entry.")
    return workspace, agent_id, binding


def desktop_directory_actor(app, operation=None):
    """A known Desktop session keeps its identity across command working directories."""
    session = os.environ.get("CODEX_THREAD_ID")
    if not session:
        return None
    settings_by_workspace = app.local()["workspaces"]
    for workspace in settings_by_workspace:
        snapshot = app.store(workspace).snapshot()
        linked = snapshot.json(layout.shared_path(snapshot, f"sessions/desktop/{digest(session.encode())}.json"))
        if linked is not None:
            app.require_binding(workspace, linked["agent"], linked["binding"], allow_stopping=True, snapshot=snapshot)
            return desktop_actor(app, workspace, linked["agent"])
    cwd = Path.cwd().resolve()
    for workspace, settings in settings_by_workspace.items():
        for agent_id, locations in settings.get("instances", {}).items():
            for location in locations:
                root = Path(location).resolve()
                if not cwd.is_relative_to(root):
                    continue
                snapshot = app.store(workspace).snapshot()
                agent = app.agent(workspace, agent_id, snapshot)
                if agent.get("worker_id") is not None:
                    # A shared directory cannot select which Worker owns an
                    # unregistered native session. Only the session index can.
                    continue
                entry = snapshot.json(layout.shared_path(snapshot, f"bindings/{agent['current']}.json")) if agent["current"] else None
                if entry and entry["kind"] == "desktop":
                    if (entry["phase"] == "starting" and entry["session"] is None
                            and operation in ("agent.bind", "agent.capture-desktop", "agent.start-here")
                            and not entry.get("controller")
                            and not read_json(layout.local_path(root, "launch.json"), {}).get("attempted")):
                        return None  # User-started manual bootstrap, before an execution identity exists.
                    return desktop_actor(app, workspace, agent_id)
                for path in snapshot.entries:
                    if not path.startswith(layout.shared_path(snapshot, "bindings") + "/"):
                        continue
                    old = snapshot.json(path)
                    if old["agent"] == agent_id and old["kind"] == "desktop" and old["session"] == session:
                        raise Conflict("This Desktop chat has handed off; it cannot become a user-management caller.")
                if (not entry and agent["has_run"] and operation not in ("agent.start-here", "agent.capture-desktop")
                        and read_json(layout.local_path(root, "runtime.json"), {}).get("kind") == "desktop"):
                    raise Conflict("This Desktop instance has handed off; the old chat cannot become a user-management caller.")
    return None


def _session_title(app, workspace, owner):
    if owner.get("worker_id") is None:
        return None
    space = app.workspace_show(workspace)
    return session_titles.format_title(space.get("short_name", space["name"]), owner["name"], owner["worker"]["name"])


def _entry_owner(app, workspace, agent_id, worker_id=None, *, binding=None, snapshot=None):
    snap = snapshot or app.store(workspace).snapshot()
    if binding is not None:
        entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
        if not entry or entry["agent"] != agent_id:
            raise Conflict("The execution entry does not belong to this Agent.")
        actual = app.binding_worker(workspace, agent_id, entry, snap)
        if worker_id is not None and worker_id != actual:
            raise Conflict("The execution entry belongs to a different Worker.")
        worker_id = actual
    owner = app.agent(workspace, agent_id, snap, worker_id=worker_id)
    return snap, owner, owner.get("worker_id")


def configure_desktop(app, workspace, agent_id, command=None, directory=None, worker_id=None):
    pipe, thread = os.environ.get("CODEX_APP_TOOLS_PIPE_PATH"), os.environ.get("CODEX_THREAD_ID")
    if not pipe or not thread:
        raise Error("Run capture-desktop inside the real Desktop session; both CODEX environment values are required.")
    root = Path(app.prepare_agent_directory(workspace, agent_id, directory)["directory"])
    app.agent(workspace, agent_id, worker_id=worker_id)
    model_profiles.migrate(root, worker_id)
    with layout.lock(root, "files.lock", worker_id=worker_id):
        value = model_profiles.runtime_config(root, worker_id)
        value.update(kind="desktop", pipe_path=pipe, caller_thread=thread)
        if command:
            value["command"] = command
        if not value.get("command"):
            raise Error("Supply the actual desktop MCP server command as a JSON array; do not start codex app-server here.")
        write_json(layout.local_path(root, "runtime.json", worker_id), value)
    return {"captured": True, "kind": "desktop", "credentials_printed": False}


def desktop_profile(app, workspace, agent_id, model="", effort="", project_id="", directory=None, worker_id=None):
    root = Path(app.prepare_agent_directory(workspace, agent_id, directory)["directory"])
    owner = app.agent(workspace, agent_id, worker_id=worker_id)
    # Worker entries keep adopted snapshots; Agent defaults only affect future entries.
    # Legacy entries still read the common connection and retain the original guard.
    if owner["current"] and (worker_id is not None or owner.get("worker_id") is None):
        raise Conflict("Handoff before changing the Desktop profile of an active instance.")
    config = model_profiles.runtime_config(root, worker_id)
    if config.get("kind") != "desktop":
        raise Unavailable("Capture this instance's real Desktop connection first.")
    config.update(model=model, effort=effort, project_id=project_id or config.get("project_id", ""))
    adapter = Desktop(root, config, None, worker_id=worker_id)
    try:
        project = adapter.project()
    finally:
        adapter.close()
    app.configure(workspace, agent_id, config, str(root), worker_id=worker_id)
    return {"configured": True, "kind": "desktop", "project_id": project["projectId"],
            "project_name": project["label"], "primary_folder": project["path"], "model": model, "effort": effort}


class Codex:
    supports_insert = True

    def __init__(self, app, workspace, agent_id, binding, root, config, session=None, *, title=None, worker_id=None):
        self.app, self.workspace, self.agent_id, self.binding, self.root = app, workspace, agent_id, binding, root
        self.session = session
        self.worker_id = worker_id
        self.title_receipt = session_titles.receipt(title, "thread/name/set") if title else None
        model_profiles.migrate(root, worker_id)
        self.profile = model_profiles.pin(root, binding,
            model_profiles.adopted(root, binding, session=session, worker_id=worker_id), worker_id)
        self.profile_validation = {"catalog": "unconfirmed", "effective": "unconfirmed"}
        self.model_receipt = model_profiles.receipt(self.profile, self.profile_validation)
        config, _, _ = model_profiles.split_config(config)
        self.busy, self.turn_id = False, None
        self.completed = queue.Queue()
        self.record = layout.instance_path(root, "records", self.worker_id) / binding / "runtime.jsonl"
        self.record.parent.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, AW_HOME=str(app.home), AW_WORKSPACE=workspace, AW_AGENT=agent_id, AW_BINDING=binding)
        if self.worker_id is None:
            env.pop("AW_WORKER", None)
        else:
            env["AW_WORKER"] = self.worker_id
        self.rpc = Rpc(config.get("command", ["codex", "app-server"]), cwd=root, env=env,
                       on_event=self.event, on_request=self.tool_call)
        try:
            self.rpc.request("initialize", {"clientInfo": {"name": "agent_workspace", "version": __version__},
                                             "capabilities": {"experimentalApi": True}})
            self.rpc.send({"method": "initialized", "params": {}})
            self._validate_model(config)
            if session:
                params = {"threadId": session, "model": self.profile["model"],
                          "config": {"model_reasoning_effort": self.profile["effort"]}}
                if config.get("modelProvider"):
                    params["modelProvider"] = config["modelProvider"]
                result = self.rpc.request("thread/resume", params)
            else:
                params = {"cwd": str(root), "approvalPolicy": "never", "sandbox": config.get("sandbox", "workspace-write"),
                          "dynamicTools": [{"type": "function", "name": "aw_execute", "description": "Operate the Agent Workspace platform; not a shell.",
                                            "inputSchema": TOOL_SCHEMA}]}
                params.update(model=self.profile["model"], config={"model_reasoning_effort": self.profile["effort"]})
                if config.get("modelProvider"):
                    params["modelProvider"] = config["modelProvider"]
                write_json(layout.local_path(root, "launch.json", self.worker_id), {"binding": binding, "attempted": True,
                           "model_profile": model_profiles.receipt(self.profile, self.profile_validation)})
                result = self.rpc.request("thread/start", params)
                self.session = result["thread"]["id"]
            self.model_receipt = model_profiles.receipt(self.profile, self.profile_validation, accepted=True, result=result)
            launch = read_json(layout.local_path(root, "launch.json", self.worker_id), {})
            write_json(layout.local_path(root, "launch.json", self.worker_id), {**launch, "binding": binding,
                       "session": self.session, "model_profile": self.model_receipt})
            model_profiles.require_matching(self.model_receipt)
            if title and session is None:
                try:
                    self.rpc.request("thread/name/set", {"threadId": self.session, "name": title})
                except Unavailable:
                    # An older server or a lost reply does not justify creating
                    # another session or repeating this optional metadata write.
                    self.title_receipt = session_titles.receipt(title, "unconfirmed")
                else:
                    self.title_receipt = session_titles.receipt(title, "thread/name/set", accepted=True)
                write_json(layout.local_path(root, "launch.json", self.worker_id), {**read_json(layout.local_path(root, "launch.json", self.worker_id)),
                           "native_title": self.title_receipt})
            self.status()
            if self.title_receipt is not None:
                write_json(layout.local_path(root, "launch.json", self.worker_id), {**read_json(layout.local_path(root, "launch.json", self.worker_id)),
                           "native_title": self.title_receipt})
        except BaseException:
            self.rpc.close()
            raise

    def _validate_model(self, config):
        if config.get("modelProvider"):
            self.profile_validation = {"catalog": "custom_provider_unconfirmed", "effective": "unconfirmed"}
            return
        models, cursor = [], None
        try:
            for _ in range(5):
                page = self.rpc.request("model/list", {"limit": 100, "cursor": cursor}, timeout=10)
                models.extend(page["data"])
                cursor = page.get("nextCursor")
                if not cursor:
                    break
        except (Error, KeyError, TypeError):
            # This optional read-only interface may not exist on an older native client.
            return
        self.profile_validation = model_profiles.check_catalog(self.profile, models, complete=not cursor)

    def event(self, value):
        with layout.lock(self.root, "records.lock", worker_id=self.worker_id):
            self.record = layout.instance_path(self.root, "records", self.worker_id) / self.binding / "runtime.jsonl"
            self.record.parent.mkdir(parents=True, exist_ok=True)
            with self.record.open("ab") as stream:
                stream.write(encode(value).replace(b"\n", b" ") + b"\n")
                stream.flush()
        method, params = value.get("method"), value.get("params", {})
        if method == "turn/started":
            self.busy, self.turn_id = True, params["turn"]["id"]
        if method == "turn/completed":
            self.busy, self.turn_id = False, None
            self.completed.put(params["turn"])

    def tool_call(self, request):
        if request["method"] != "item/tool/call":
            # Unattended runtime never silently grants native approval/permission requests.
            raise Error("Native approval/input needs the user; use an interactive provider for this operation.")
        params = request["params"]
        if params.get("tool") != "aw_execute":
            raise Error("Unknown dynamic tool.")
        from .commands import execute
        arguments = params["arguments"]
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        try:
            result = execute(self.app, arguments["command"], arguments["arguments"],
                             actor=(self.workspace, self.agent_id, self.binding))
            return {"success": True, "contentItems": [{"type": "inputText", "text": json.dumps(result, ensure_ascii=False)}]}
        except Exception as exc:
            return {"success": False, "contentItems": [{"type": "inputText", "text": str(exc)}]}

    def status(self):
        # Status does not require a full history export. Turn IDs come from native events.
        result = self.rpc.request("thread/read", {"threadId": self.session, "includeTurns": False})
        thread = result["thread"]
        if self.title_receipt is not None:
            self.title_receipt = session_titles.receipt(self.title_receipt["requested"],
                self.title_receipt["capability"], accepted=self.title_receipt["native_accepted"], reported=thread.get("name"))
        state = thread.get("status", {}).get("type")
        turns = thread.get("turns", [])
        active = next((t for t in reversed(turns) if t.get("status") == "inProgress"), None)
        if active:
            self.turn_id = active["id"]
        self.busy = state == "active"
        return "busy" if self.busy else "idle" if state == "idle" else "unknown"

    def notify(self, prompt, delivery):
        state = self.status()
        if state == "unknown":
            raise Unavailable("Native thread status is unknown.")
        params = {"threadId": self.session, "input": [{"type": "text", "text": prompt}]}
        self.model_receipt = model_profiles.receipt(self.profile, self.profile_validation)
        if state == "busy":
            if delivery != "insert" or not self.turn_id:
                raise Conflict("Native turn is busy; normal input must wait.")
            params["expectedTurnId"] = self.turn_id
            result = self.rpc.request("turn/steer", params)
            self.model_receipt = model_profiles.receipt(self.profile, self.profile_validation, accepted=True, result=result)
            self.model_receipt["application"] = "existing_turn"
            model_profiles.require_matching(self.model_receipt)
            return result
        params.update(model=self.profile["model"], effort=self.profile["effort"])
        self.busy = True
        result = self.rpc.request("turn/start", params)
        self.model_receipt = model_profiles.receipt(self.profile, self.profile_validation, accepted=True, result=result)
        model_profiles.require_matching(self.model_receipt)
        return result

    def close(self):
        self.rpc.close()


def desktop_native_state(result):
    state = result["thread"]["status"]["type"]
    if state == "active":
        return "busy"
    if state == "idle":
        return "idle"
    if state == "notLoaded":
        turns = result.get("turns", result["thread"].get("turns", []))
        if turns and turns[0].get("status") in ("completed", "interrupted"):
            return "idle"
    return "unknown"


def desktop_observe(app, workspace, agent_id, directory=None, worker_id=None):
    """Read the current local Desktop entry; never create or submit model input."""
    from .maintenance import installation_id
    store = app.store(workspace)
    snap = store.snapshot()
    snap, owner, worker_id = _entry_owner(app, workspace, agent_id, worker_id, snapshot=snap)
    binding = owner["current"]
    entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json")) if binding else None
    result = {"binding": binding, "phase": entry["phase"] if entry else None,
              "session": entry.get("session") if entry else None, "observed_at": now(),
              "native_state": "unknown", "native_host": None, "native_cwd": None,
              "local_session_confirmed": False, "worker_id": worker_id}
    if not entry or entry["phase"] != "active" or entry["kind"] != "desktop":
        return {**result, "unknown_reason": "no_active_desktop_entry"}
    execution = entry.get("execution")
    if not execution:
        return {**result, "unknown_reason": "execution_source_missing"}
    if execution["installation_id"] != installation_id(app):
        return {**result, "unknown_reason": "different_execution_environment"}
    if directory is not None and Path(directory).resolve() != Path(execution["directory"]).resolve():
        return {**result, "unknown_reason": "different_local_copy"}
    root = app.root(workspace, agent_id, execution["directory"])
    result["directory"] = str(root)
    local = read_json(layout.local_path(root, "entry.json", worker_id), {})
    if local.get("binding") != binding:
        return {**result, "unknown_reason": "local_entry_mismatch"}
    config = local["config"] if worker_id is not None else model_profiles.runtime_config(root)
    if config.get("kind") != "desktop":
        return {**result, "unknown_reason": "desktop_connection_missing"}
    try:
        adapter = Desktop(root, config, entry["session"], read_only=True, worker_id=worker_id)
        try:
            native = adapter.read()
            can_send = "send_message_to_thread" in adapter.tools
        finally:
            adapter.close()
    except (Error, OSError, ValueError, KeyError) as exc:
        return {**result, "unknown_reason": "native_observation_failed", "error_code": getattr(exc, "code", None)}
    thread = native["thread"]
    result.update(native_state=desktop_native_state(native), native_host=thread.get("hostId"),
                  native_cwd=thread.get("cwd"), observed_at=now())
    native_root = Path(execution["cwd"]).resolve() if "cwd" in execution else root
    if thread.get("hostId") != "local" or not thread.get("cwd") or Path(thread["cwd"]).resolve() != native_root:
        return {**result, "unknown_reason": "native_local_copy_unconfirmed"}
    if not can_send or result["native_state"] == "unknown":
        return {**result, "unknown_reason": "native_control_unconfirmed"}
    latest = store.snapshot()
    current = app.agent(workspace, agent_id, latest, worker_id=worker_id)
    checked = latest.json(layout.shared_path(latest, f"bindings/{binding}.json"))
    if (current["current"] != binding or checked["phase"] != "active"
            or checked["session"] != entry["session"] or checked.get("execution") != execution):
        return {**result, "unknown_reason": "binding_changed_during_observation"}
    return {**result, "local_session_confirmed": True, "snapshot_revision": latest.revision}


def cleanup_controller(app, workspace, agent_id, *, expected_binding, expected_controller,
                       expected_session, expected_revision, cleanup_commit, directory=None, worker_id=None):
    """Finish one exited runner's cleanup, never resume its work or old push."""
    from .maintenance import installation_id
    if not all((expected_binding, expected_controller, expected_session, expected_revision, cleanup_commit)):
        raise Error("Controller cleanup requires the original Binding, controller, session, snapshot revision and cleanup commit.")
    store = app.store(workspace)
    expected = store.snapshot(revision=expected_revision)
    expected_path = layout.shared_path(expected, f"bindings/{expected_binding}.json")
    expected_blob = expected.entries.get(expected_path)
    if expected_blob is None:
        raise Conflict("The supplied snapshot does not contain the original Binding.")
    snap = store.snapshot()
    snap, owner, worker_id = _entry_owner(app, workspace, agent_id, worker_id, binding=expected_binding, snapshot=snap)
    owner_path, _, _ = workers.execution_record(app, workspace, agent_id, snap, worker_id)
    path = layout.shared_path(snap, f"bindings/{expected_binding}.json")
    entry = snap.json(path)
    if (owner["current"] != expected_binding or owner["archived"] or not entry
            or entry["agent"] != agent_id or entry["phase"] != "active"
            or entry.get("session") != expected_session):
        raise Conflict("The original active Binding or session changed before controller cleanup.")
    result = {"binding": expected_binding, "session": expected_session, "worker_id": worker_id,
              "controller": expected_controller, "cleanup_commit": cleanup_commit,
              "state": "cleanup_blocked", "runner_started": False, "binding_released": False}
    execution = entry.get("execution")
    if not execution or execution["installation_id"] != installation_id(app):
        return {**result, "reason_code": "execution_source_unconfirmed"}
    if directory is not None and Path(directory).resolve() != Path(execution["directory"]).resolve():
        raise Conflict("Cleanup must use the original execution directory.")
    root = app.root(workspace, agent_id, execution["directory"])
    # The OS lock covers runners outside the current backend as well as threads
    # known to it. Keep it held through the conditional shared-file update.
    with layout.lock(root, "runner.lock", wait=0, worker_id=worker_id):
        status = backend.status(app)
        if status["state"] not in ("running", "stopped") or (status["state"] == "running" and not status.get("ready")):
            return {**result, "reason_code": "runner_observation_unknown"}
        tasks = [row for row in status.get("runners", []) if Path(row["directory"]).resolve() == root
                 and (row.get("worker_id") == worker_id or row.get("binding") == expected_binding)]
        if any(row["runner_alive"] for row in tasks):
            return {**result, "reason_code": "runner_present"}
        with layout.lock(root, "files.lock", worker_id=worker_id):
            local = read_json(layout.local_path(root, "entry.json", worker_id), {})
            control = read_json(layout.local_path(root, "control.json", worker_id), {})
            observation = read_json(layout.local_path(root, "status.json", worker_id), {})
            if local.get("binding") != expected_binding:
                raise Conflict("This copy is not attached to the original Binding.")
            if control.get("stop") == expected_binding or control.get("handoff") == expected_binding:
                return {**result, "state": "cleanup_paused", "reason_code": "user_paused"}
            if (observation.get("binding") != expected_binding
                    or observation.get("state") not in ("failed", "monitor_stopped")):
                return {**result, "reason_code": "runner_exit_unconfirmed"}
            if entry["kind"] != "desktop":
                return {**result, "reason_code": "native_observation_unavailable"}
            native = desktop_observe(app, workspace, agent_id, str(root), worker_id=worker_id)
            if not native["local_session_confirmed"]:
                return {**result, "reason_code": native.get("unknown_reason", "native_session_unconfirmed")}
            if native["binding"] != expected_binding or native["session"] != expected_session:
                raise Conflict("The original session changed during cleanup observation.")
            latest = store.snapshot()
            agent_path = layout.shared_path(snap, f"agents/{agent_id}.json")
            if any(latest.entries.get(p) != snap.entries[p] for p in (path, agent_path, owner_path)):
                raise Conflict("The Binding or owner changed during cleanup observation; read it again.")
            snap = latest
            original = store.snapshot(revision=cleanup_commit)
            cleaned = original.json(layout.shared_path(original, f"bindings/{expected_binding}.json"))
            without_controller = {key: value for key, value in entry.items() if key != "controller"}
            if cleaned != without_controller:
                raise Conflict("The original cleanup commit does not describe this Binding's controller removal.")
            published = store.contains_commit(cleanup_commit, snap.revision)
            if not entry.get("controller"):
                return {**result, "state": "controller_already_cleared", "original_published": published,
                        "revision": snap.revision}
            if entry["controller"] != expected_controller or snap.entries[path] != expected_blob:
                raise Conflict("The original controller or Binding file version changed; read it again.")
            if published:
                raise Conflict("The original cleanup was published but the controller is present again; inspect its ownership.")
            if store.contains_commit(snap.revision, cleanup_commit):
                raise Uncertain("The original cleanup push can still fast-forward; its outcome is not confirmed.")
            # Diverged history cannot accept the old fast-forward push. Publish
            # only the removal, against freshly checked owner and Binding blobs.
            revision = store.change("main", {path: encode(without_controller)},
                layout.expected(snap, {path: expected_blob, agent_path: snap.entries[agent_path],
                                      owner_path: snap.entries[owner_path]}), "Continue original runner cleanup")
            return {**result, "state": "controller_cleared", "original_published": False,
                    "original_outcome": "diverged", "revision": revision}


def launch_show(app, workspace, agent_id, directory=None, worker_id=None):
    """Expose the original receipt's identifiers, without native probing or credentials."""
    from .maintenance import installation_id
    snap = app.store(workspace).snapshot()
    snap, owner, worker_id = _entry_owner(app, workspace, agent_id, worker_id, snapshot=snap)
    binding = owner["current"]
    entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json")) if binding else None
    execution = entry.get("execution") if entry else None
    if directory is None and execution and execution["installation_id"] == installation_id(app):
        directory = execution["directory"]
    root = app.root(workspace, agent_id, directory)
    launch = read_json(layout.local_path(root, "launch.json", worker_id), {})
    returned = launch.get("result") or {}
    profile = launch.get("model_profile") or {}
    requested, reported = profile.get("requested", {}), profile.get("reported", {})
    recovery = launch.get("reconciled") or {}
    return {"binding": launch.get("binding"), "current_binding": binding,
            "current_phase": entry["phase"] if entry else None, "directory": str(root), "observed_at": now(),
            "attempted": launch.get("attempted", False), "receipt_matches_current": bool(binding and launch.get("binding") == binding),
            "project_id": launch.get("project_id"), "has_original_session_id": bool(returned.get("threadId")),
            "result": {key: returned[key] for key in ("threadId", "hostId", "clientThreadId") if key in returned},
            "model_profile": {"requested": {key: requested[key] for key in ("generation", "model", "effort") if key in requested},
                "reported": {key: reported[key] for key in ("model", "effort") if key in reported},
                "effective": profile.get("effective", "unconfirmed"), "native_accepted": profile.get("native_accepted")},
            "reconciled": {key: recovery[key] for key in ("binding", "session", "association", "selected_at", "observed_at",
                "native_host", "native_cwd", "native_state") if key in recovery}}


def reconcile_create(app, workspace, agent_id, binding, session, directory=None, worker_id=None):
    """Bind only a verified original launch ID; never create or execute native input."""
    from .maintenance import installation_id
    store = app.store(workspace)
    snap = store.snapshot()
    snap, owner, worker_id = _entry_owner(app, workspace, agent_id, worker_id, binding=binding, snapshot=snap)
    entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
    if owner["current"] != binding or not entry or entry["kind"] != "desktop" or entry["phase"] not in ("starting", "active"):
        raise Conflict("Only the current original Desktop launch can be reconciled.")
    execution = entry.get("execution")
    if not execution or execution["installation_id"] != installation_id(app):
        raise Conflict("Original execution source is unconfirmed or belongs to another home.")
    root = app.root(workspace, agent_id, directory or execution["directory"])
    if root != Path(execution["directory"]).resolve():
        raise Conflict("The original execution belongs to another local copy.")
    with layout.lock(root, "runner.lock", wait=0, worker_id=worker_id):
        if entry.get("controller"):
            raise Conflict("The original controller remains; inspect it or use explicit takeover.")
        if read_json(layout.local_path(root, "entry.json", worker_id), {}).get("binding") != binding:
            raise Conflict("The original local entry changed; no session was bound.")
        if entry.get("session") not in (None, session):
            raise Conflict("This Binding already names a different native session.")
        launch = read_json(layout.local_path(root, "launch.json", worker_id), {})
        if launch.get("binding") != binding or not launch.get("attempted"):
            raise Conflict("No matching attempted original launch receipt exists.")
        original = (launch.get("result") or {}).get("threadId")
        if not original:
            return {"state": "outcome_unknown", "binding": binding, "session": entry.get("session"),
                    "original_create_result_confirmed": False, "observation_started": False,
                    "reason": "Original launch has no real threadId; candidate location cannot prove original creation."}
        if original != session or (launch.get("reconciled", {}).get("session") not in (None, session)):
            raise Conflict("Use only the real threadId returned by this original launch.")
        local = read_json(layout.local_path(root, "entry.json", worker_id), {})
        config = local["config"] if worker_id is not None else model_profiles.runtime_config(root)
        if config.get("kind") != "desktop":
            raise Conflict("The original Desktop connection configuration changed.")
        profile = model_profiles.adopted(root, binding, session=entry.get("session"), worker_id=worker_id)
        adapter = Desktop(root, config, session, read_only=True, worker_id=worker_id)
        try:
            native = adapter.read()
        finally:
            adapter.close()
        thread = native["thread"]
        original_cwd = Path(launch["project_directory"]).resolve() if "project_directory" in launch else root
        if thread.get("id") != session or thread.get("hostId") != "local" or not thread.get("cwd") or Path(thread["cwd"]).resolve() != original_cwd:
            raise Conflict("The original native session has not confirmed this local execution directory.")
        native_state = desktop_native_state(native)
        if native_state == "unknown":
            raise Unavailable("Original native session state remains unknown; no session was bound.")
        model_receipt = model_profiles.receipt(profile, {"catalog": "unconfirmed", "effective": "unconfirmed"},
                                               result={**native, **thread})
        model_profiles.require_matching(model_receipt)
        latest = store.snapshot()
        checked = latest.json(layout.shared_path(latest, f"bindings/{binding}.json"))
        if (app.agent(workspace, agent_id, latest, worker_id=worker_id)["current"] != binding or checked["phase"] not in ("starting", "active")
                or checked.get("controller") or checked.get("execution") != execution or checked.get("session") not in (None, session)):
            raise Conflict("The original Binding changed during native observation; no session was bound.")
        already_bound = checked["phase"] == "active" and checked.get("session") == session
        recovery = {"binding": binding, "session": session, "association": "original_launch_thread_id",
                    "selected_at": launch.get("reconciled", {}).get("selected_at", now()), "observed_at": now(),
                    "native_host": thread["hostId"], "native_cwd": thread["cwd"], "native_state": native_state,
                    "model_profile": model_receipt}
        # Persist the original choice before the shared write, so a lost reply can be read back.
        write_json(layout.local_path(root, "launch.json", worker_id), {**launch, "reconciled": recovery})
        if not already_bound:
            app.bind(workspace, agent_id, binding, session, str(root), cwd=thread["cwd"], worker_id=worker_id)
        boot_path = layout.local_path(root, "inputs", worker_id) / f"boot-{binding}.json"
        boot = read_json(boot_path)
        if boot is None:
            boot = queue_input(app, workspace, agent_id, entry_prompt(app, workspace, agent_id, binding, root),
                               purpose="initial", directory=str(root), request_id="boot-" + binding,
                               expected_binding=binding, worker_id=worker_id)
        elif boot.get("binding") != binding or boot.get("purpose") != "initial":
            raise Conflict("The original boot input does not match this Binding; its bytes were preserved.")
        return {"state": "session_bound", "binding": binding, "session": session, "directory": str(root),
                "already_bound": already_bound, "association": recovery["association"], "original_create_result_confirmed": True,
                "native_state": native_state, "model_profile": model_receipt,
                "initial_input_state": boot["state"], "observation_started": False}


class Desktop:
    supports_insert = True

    """Attach to the desktop-owned MCP control endpoint; never spawn a competing writer."""
    def __init__(self, root, config, session, *, read_only=False, title=None, worker_id=None):
        self.root, self.session = root, session
        self.worker_id = worker_id
        self.requested_title = title
        self.title_receipt = None
        self.config = config
        self.profile = None
        self.read_only = read_only
        if not read_only:
            for name in ("project_id",):
                if name in config and not isinstance(config[name], str):
                    raise Error(f"Desktop {name} must be a string.")
        command = config.get("command")
        if not command or not config.get("pipe_path") or not config.get("caller_thread"):
            raise Unavailable("Desktop connection is not captured. Configure the real MCP command and capture it in Desktop.")
        env = dict(os.environ, CODEX_APP_TOOLS_PIPE_PATH=config["pipe_path"], CODEX_THREAD_ID=config["caller_thread"])
        self.rpc = Rpc(command, cwd=root, env=env, jsonrpc=True)
        self.caller_thread = config["caller_thread"]
        try:
            self.rpc.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "agent-workspace", "version": __version__}})
            self.rpc.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            tools = self.rpc.request("tools/list")["tools"]
            names = {t["name"] for t in tools}
            self.tools = names
            self.tool_schemas = {t["name"]: t.get("inputSchema", {}) for t in tools}
            required = {"read_thread"} if read_only else {"read_thread", "send_message_to_thread"}
            if not required.issubset(names):
                self.close()
                if read_only:
                    raise Error("Installed Desktop cannot observe the original session; the stop request remains pending.")
                raise Unavailable("Installed Desktop does not expose the expected control tools; no CLI fallback was used.")
        except BaseException:
            self.rpc.close()
            raise

    def call(self, name, arguments):
        result = self.rpc.request("tools/call", {"name": name, "arguments": arguments,
                                    "_meta": {"openai/threadId": self.caller_thread}})
        if result.get("isError"):
            raise Error("Desktop tool rejected the request: " + json.dumps(result.get("content", []), ensure_ascii=False)[:1000])
        return json.loads(result["content"][0]["text"])

    def status(self):
        return desktop_native_state(self.read())

    def read(self, **options):
        result = self.call("read_thread", {"threadId": self.session, "turnLimit": 1,
                                          "maxOutputCharsPerItem": 100, **options})
        if result["thread"].get("id") != self.session:
            raise Conflict("Desktop returned a different native session; its state was not used.")
        return result

    def set_title(self, title):
        """One optional native metadata write; a lost reply is only read back."""
        if self.read_only:
            raise Conflict("A read-only observer cannot change a native title.")
        schema = self.tool_schemas.get("set_thread_title", {}).get("properties", {})
        if not {"title", "threadId"}.issubset(schema):
            self.title_receipt = session_titles.receipt(title, "unsupported_by_installed_schema")
            return self.title_receipt
        path = layout.local_path(self.root, "native-titles", self.worker_id) / (digest(self.session.encode()) + ".json")
        with layout.lock(self.root, "native-titles.lock", worker_id=self.worker_id):
            original = read_json(path)
            if original and (original["session"] != self.session or original["requested"] != title):
                raise Conflict("The original native title request changed; inspect it before requesting another name.")
            current = original or {**session_titles.receipt(title, "set_thread_title"), "session": self.session}
            if original is None:
                write_json(path, current)
                try:
                    self.call("set_thread_title", {"threadId": self.session, "title": title})
                except (Error, OSError) as exc:
                    current["error_code"] = getattr(exc, "code", None)
                else:
                    current["native_accepted"] = True
                write_json(path, current)
            try:
                reported = self.read()["thread"].get("title")
            except (Error, OSError):
                reported = None
            self.title_receipt = session_titles.receipt(title, current["capability"],
                accepted=current["native_accepted"], reported=reported)
            write_json(path, {**current, **self.title_receipt})
            return self.title_receipt

    def project(self):
        from .desktop_projects import project_directory
        if not {"create_thread", "list_projects"}.issubset(self.tools):
            raise Unavailable("This Desktop connection cannot create real project chats.")
        project_root = project_directory(self.root, worker_id=self.worker_id)
        projects = self.call("list_projects", {})["projects"]
        matches = [p for p in projects if p.get("projectKind") == "local"
                   and p.get("hostId") == "local" and p.get("path")
                   and Path(p["path"]).resolve() == project_root]
        selected = self.config.get("project_id")
        if selected:
            matches = [p for p in matches if p["projectId"] == selected]
        if len(matches) != 1:
            raise Unavailable("Select one saved local Codex project whose primary folder is the chosen project directory. "
                              "Create it manually if missing; set project_id when more than one matches.")
        return matches[0]

    def create(self, binding, prompt):
        if self.read_only:
            raise Conflict("A stop observer cannot create a native session.")
        profile, validation = self.model_choice("create_thread", binding)
        project = self.project()
        path = layout.local_path(self.root, "launch.json", self.worker_id)
        previous = read_json(path, {})
        if previous.get("binding") == binding and previous.get("attempted"):
            raise Conflict("Desktop creation was already attempted; inspect the original result before recovery.")
        arguments = {"target": {"type": "project", "projectId": project["projectId"],
                                "environment": {"type": "local"}}, "prompt": prompt}
        arguments.update(model=profile["model"], thinking=profile["effort"])
        if self.requested_title:
            supported = "title" in self.tool_schemas["create_thread"].get("properties", {})
            self.title_receipt = session_titles.receipt(self.requested_title,
                "create_thread.title" if supported else "unsupported_by_installed_schema")
            if supported:
                arguments["title"] = self.requested_title
        launch = {"binding": binding, "attempted": True, "project_id": project["projectId"],
                  "project_directory": str(Path(project["path"]).resolve()),
                  "model_profile": model_profiles.receipt(profile, validation)}
        if self.title_receipt is not None:
            launch["native_title"] = self.title_receipt
        write_json(path, launch)
        result = self.call("create_thread", arguments)
        self.model_receipt = model_profiles.receipt(profile, validation, accepted=True, result=result)
        write_json(path, {**launch, "result": result, "model_profile": self.model_receipt})
        model_profiles.require_matching(self.model_receipt)
        if not result.get("threadId") or result.get("hostId") != "local":
            raise Unavailable("Desktop did not return a ready local chat; preserve the launch receipt, do not repeat creation.")
        self.session = result["threadId"]
        thread = self.read()["thread"]
        if thread.get("id") != self.session or thread.get("hostId") != "local" or not thread.get("cwd") or Path(thread["cwd"]).resolve() != Path(launch["project_directory"]):
            raise Unavailable("The created Desktop chat has not verified the chosen project directory; it was not bound.")
        if self.title_receipt is not None:
            reported_title = thread.get("title")
            if "title" not in arguments:
                self.set_title(self.requested_title)
                if self.title_receipt["capability"] != "unsupported_by_installed_schema":
                    reported_title = self.title_receipt["reported"]
            self.title_receipt = session_titles.receipt(self.requested_title, self.title_receipt["capability"],
                accepted=True if "title" in arguments else self.title_receipt["native_accepted"],
                reported=reported_title)
            saved = read_json(path)
            write_json(path, {**saved, "native_title": self.title_receipt})
        return thread

    def completed_turns(self, identifiers):
        found, cursor = {}, None
        while identifiers - found.keys():
            result = self.read(turnLimit=10, **({"cursor": cursor} if cursor else {}))
            for turn in result.get("turns", []):
                if turn["id"] in identifiers:
                    found[turn["id"]] = turn
            cursor = result.get("page", {}).get("nextCursor")
            if not cursor:
                break
        return {key: value for key, value in found.items()
                if value.get("status") in ("completed", "interrupted", "failed")}

    def notify(self, prompt, delivery):
        if self.read_only:
            raise Conflict("A stop observer cannot send model input.")
        profile, validation = self.model_choice("send_message_to_thread")
        self.model_receipt = model_profiles.receipt(profile, validation)
        state = self.status()
        if state == "unknown" or (state == "busy" and delivery == "normal"):
            raise Conflict("Desktop is not ready for this delivery mode.")
        result = self.call("send_message_to_thread", {"threadId": self.session, "prompt": prompt,
                           "model": profile["model"], "thinking": profile["effort"]})
        self.model_receipt = model_profiles.receipt(profile, validation, accepted=True, result=result)
        model_profiles.require_matching(self.model_receipt)
        return result

    def model_choice(self, tool, binding=None, *, selected=None):
        profile = selected or self.profile or model_profiles.adopted(self.root, binding,
            session=self.session, worker_id=self.worker_id)
        validation = {"catalog": "unconfirmed", "effective": "unconfirmed"}
        schema = self.tool_schemas.get(tool)
        if schema:
            properties = schema.get("properties", {})
            for field, native in (("model", "model"), ("effort", "thinking")):
                if native not in properties:
                    raise Unavailable(f"Desktop {tool} cannot explicitly select {native}; no inherited configuration was used.")
                allowed = properties[native].get("enum")
                if allowed is not None and profile[field] not in allowed:
                    raise Error(f"Desktop {tool} does not support the selected {field}; no fallback was used.")
            validation["parameters"] = "reported_by_current_desktop"
        record = read_json(layout.local_path(self.root, "entry.json", self.worker_id), {})
        if selected is None and record.get("binding"):
            profile = model_profiles.pin(self.root, binding or record["binding"], profile, self.worker_id)
        if selected is None:
            self.profile = profile
            self.profile_validation = validation
        return profile, validation

    def close(self):
        self.rpc.close()


def spawn_runner(app, workspace, agent_id, directory=None, *, stop_binding=None, worker_id=None):
    from .backend import attach
    return attach(app, workspace, agent_id, directory, stop_binding, worker_id=worker_id)


def _released_stop(snap, agent_id, binding, entry, expected_checkpoint=None):
    handoff_id = "h" + binding[1:]
    handoff = snap.json(layout.shared_path(snap, f"handoffs/{handoff_id}.json"))
    if (entry.get("id") != binding or entry.get("agent") != agent_id or not handoff
            or handoff.get("id") != handoff_id or handoff.get("agent") != agent_id
            or handoff.get("entry") != binding or handoff.get("checkpoint") != entry.get("checkpoint")):
        raise Conflict("The released entry has no matching handoff; inspect its original publication.")
    if expected_checkpoint is not None and entry.get("checkpoint") != expected_checkpoint:
        raise Conflict("The original stopping checkpoint changed.")
    return {"state": "released", "binding": binding, "handoff": handoff_id,
            "checkpoint": entry["checkpoint"], "session": entry["session"]}


def continue_stop(app, workspace, agent_id, binding, directory=None, *, expected_checkpoint=None, worker_id=None):
    """Continue one saved stop request without starting an execution adapter."""
    root = app.root(workspace, agent_id, directory)
    snap = app.store(workspace).snapshot()
    snap, agent, worker_id = _entry_owner(app, workspace, agent_id, worker_id, binding=binding, snapshot=snap)
    entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
    if not entry or entry["agent"] != agent_id:
        raise Conflict("The stop request does not belong to this instance.")
    if expected_checkpoint is not None and entry.get("checkpoint") != expected_checkpoint:
        raise Conflict("The original stopping checkpoint changed.")
    if entry["phase"] == "released":
        return _released_stop(snap, agent_id, binding, entry, expected_checkpoint)
    if agent["current"] != binding or entry["phase"] != "stopping":
        raise Conflict("Only the current binding's existing stop request can be continued.")
    local = read_json(layout.local_path(root, "entry.json", worker_id), {})
    if local.get("binding") != binding:
        raise Conflict("This directory is not attached to the original stopping entry.")
    app.checkpoint_show(workspace, agent_id, entry["checkpoint"], worker_id=worker_id)
    request = {"binding": binding, "checkpoint": entry["checkpoint"], "session": entry["session"]}
    # A held OS lock is evidence of a live local runner, unlike an old PID file.
    # The child takes this same lock before connecting to any native interface.
    with layout.lock(root, "stop-launch.lock", worker_id=worker_id):
        try:
            with layout.lock(root, "runner.lock", wait=0, worker_id=worker_id):
                pass
        except LockBusy:
            return {**request, "state": "runner_present"}
        if entry["kind"] != "desktop":
            reason = ("Manual stop requires the current owner's explicit confirmation." if entry["kind"] == "manual"
                      else "The original managed CLI runner is absent. No independent native stop observation is available; no writer was restarted.")
            result = {**request, "state": "stop_observation_unknown", "kind": entry["kind"], "reason": reason}
            write_json(layout.local_path(root, "status.json", worker_id), {**result, "observed_at": now(),
                       "entry_automatically_released": False})
            return result
        config = local["config"] if worker_id is not None else model_profiles.runtime_config(root)
        if config.get("kind") != "desktop":
            raise Conflict("Configured Runtime changed before stop observation.")
        if not all(config.get(key) for key in ("command", "pipe_path", "caller_thread")):
            result = {**request, "state": "stop_observation_unknown", "kind": "desktop",
                      "reason": "The original Desktop control connection is not captured; stop was not confirmed."}
            write_json(layout.local_path(root, "status.json", worker_id), {**result, "observed_at": now(),
                       "entry_automatically_released": False})
            return result
        # A validated stopping request resumes confirmation only, never business work.
        control = read_json(layout.local_path(root, "control.json", worker_id), {})
        if control.get("stop") == binding:
            write_json(layout.local_path(root, "control.json", worker_id), {**control, "stop": None})
        result = spawn_runner(app, workspace, agent_id, str(root), stop_binding=binding, worker_id=worker_id)
        if result.get("state") == "released":
            return {**request, **result}
        return {**request, **result, "state": "starting_stop_observer"}


def start_here(app, workspace, agent_id, directory=None, *, binding_id=None, expected_handoff=None, worker_id=None):
    """Bind the user's new Desktop chat and return its materials without submitting a turn."""
    session, pipe = os.environ.get("CODEX_THREAD_ID"), os.environ.get("CODEX_APP_TOOLS_PIPE_PATH")
    if not session or not pipe:
        raise Unavailable("Run agent start --here in the real new Codex Desktop chat; its session and pipe are required.")
    if desktop_directory_actor(app, "agent.start-here"):
        raise Conflict("This Desktop chat already owns an entry; it cannot be reused for a new entry.")
    root = Path(app.prepare_agent_directory(workspace, agent_id, directory)["directory"])
    _, item, worker_id = _entry_owner(app, workspace, agent_id, worker_id)
    if worker_id is not None:
        workers.prepare_context(app, workspace, agent_id, root, worker_id)
    with layout.lock(root, "runner.lock", wait=0, worker_id=worker_id):
        software.require_ready(root)
        if layout.local_path(root, "skill-install/operation.json").exists():
            raise Conflict("Recover the pending Skill update before starting a session.")
        requirements(app, workspace, root)
        model_profiles.migrate(root, worker_id)
        config = model_profiles.runtime_config(root, worker_id)
        if worker_id is not None and item["current"]:
            adopted = read_json(layout.local_path(root, "entry.json", worker_id), {})
            if adopted.get("binding") == item["current"]:
                config = adopted["config"]
        if config.get("kind") != "desktop" or not config.get("command"):
            raise Unavailable("Configure this instance's real Desktop MCP command before using --here; no native chat was created.")
        item = app.agent(workspace, agent_id, worker_id=worker_id)
        if item["current"]:
            snap = app.store(workspace).snapshot()
            entry = snap.json(layout.shared_path(snap, f"bindings/{item['current']}.json"))
            record = read_json(layout.local_path(root, "entry.json", worker_id), {})
            launch = read_json(layout.local_path(root, "launch.json", worker_id), {})
            if (expected_handoff is not None or (binding_id and item["current"] != binding_id)
                    or entry["kind"] != "desktop" or entry["phase"] != "starting" or entry["session"] is not None
                    or entry.get("controller") or record.get("binding") != item["current"] or launch.get("attempted")):
                raise Conflict("The original entry is owned or its creation is unresolved; --here cannot replace it.")
        profile = (model_profiles.adopted(root, item["current"], worker_id=worker_id) if item["current"]
                   else model_profiles.selected(root, worker_id))
        captured = {**config, "pipe_path": pipe, "caller_thread": session}
        adapter = Desktop(root, captured, session, worker_id=worker_id)
        try:
            native = adapter.read()
            thread = native["thread"]
            if (thread.get("id") != session or thread.get("hostId") != "local" or not thread.get("cwd")
                    or desktop_native_state(native) == "unknown"):
                raise Unavailable("Desktop cannot verify this current local chat; no Binding was activated.")
            receipt = model_profiles.receipt(profile, {"effective": "unconfirmed"}, result=thread)
            model_profiles.require_matching(receipt)
            title = _session_title(app, workspace, item)
            title_receipt = None
            if title is not None:
                adapter.set_title(title)
                title_receipt = adapter.title_receipt
        finally:
            adapter.close()
        if item["current"]:
            binding = item["current"]
        else:
            app.sync_agent(workspace, agent_id, str(root), worker_id=worker_id)
            write_json(layout.local_path(root, "runtime.json", worker_id), captured)
            binding = app.reserve(workspace, agent_id, str(root), binding_id=binding_id,
                                  expected_handoff=expected_handoff, worker_id=worker_id)["binding"]
        entry = app.bind(workspace, agent_id, binding, session, str(root), cwd=thread["cwd"], worker_id=worker_id)
        with layout.lock(root, "files.lock", worker_id=worker_id):
            write_json(layout.local_path(root, "runtime.json", worker_id), captured)
        record = read_json(layout.local_path(root, "entry.json", worker_id))
        write_json(layout.local_path(root, "entry.json", worker_id), {**record, "config": captured})
        model_profiles.pin(root, binding, profile, worker_id)
        prompt = entry_prompt(app, workspace, agent_id, binding, root)
        prompt_path = layout.local_path(root, "entry-prompt.md", worker_id)
        with layout.lock(root, "files.lock", worker_id=worker_id):
            write_bytes(prompt_path, prompt.encode())
    runner = spawn_runner(app, workspace, agent_id, str(root), worker_id=worker_id)
    return {"state": "bound_current_chat", "agent": agent_id, "binding": binding, "session": session,
            "phase": entry["phase"], "directory": str(root), "native_cwd": thread["cwd"],
            "model_profile": receipt, "native_title": title_receipt, "worker_id": worker_id,
            "prompt_file": str(prompt_path), "prompt": prompt, "runner": runner}


def start(app, workspace, agent_id, directory=None, open_app=False, binding_id=None, *, expected_handoff=None, here=False, worker_id=None):
    if here:
        return start_here(app, workspace, agent_id, directory, binding_id=binding_id, expected_handoff=expected_handoff, worker_id=worker_id)
    root = Path(app.prepare_agent_directory(workspace, agent_id, directory)["directory"])
    _, item, worker_id = _entry_owner(app, workspace, agent_id, worker_id)
    if worker_id is not None:
        workers.prepare_context(app, workspace, agent_id, root, worker_id)
    software.require_ready(root)
    if (layout.local_path(root, "skill-install/operation.json")).exists():
        raise Conflict("Recover the pending Skill update before starting a session.")
    requirements(app, workspace, root)  # Fail before reserving an entry or opening a native session.
    model_profiles.migrate(root, worker_id)
    config = model_profiles.runtime_config(root, worker_id)
    item = app.agent(workspace, agent_id, worker_id=worker_id)
    if worker_id is not None and item["current"]:
        adopted = read_json(layout.local_path(root, "entry.json", worker_id), {})
        if adopted.get("binding") == item["current"]:
            config = adopted["config"]
    if expected_handoff is not None and item["current"]:
        raise Conflict("Another entry already owns this Agent; the original automatic continuation was refused.")
    profile = None
    if config.get("kind") in model_profiles.CODEX_KINDS:
        profile = (model_profiles.adopted(root, item["current"], worker_id=worker_id) if item["current"]
                   else model_profiles.selected(root, worker_id))
    desktop_ready = config.get("kind") == "desktop" and all(config.get(k) for k in ("command", "pipe_path", "caller_thread"))
    if desktop_ready:
        adapter = Desktop(root, config, None, worker_id=worker_id)
        try:
            adapter.model_choice("create_thread", selected=profile)
            adapter.project()
        finally:
            adapter.close()
    if config.get("credential_env") and not os.environ.get(config["credential_env"]):
        raise Unavailable("Configured credential environment variable is missing; no execution entry was reserved.")
    if config.get("kind") == "codex":
        command = config.get("command", ["codex", "app-server"])
        if not command or not (Path(command[0]).is_file() or shutil.which(command[0])):
            raise Unavailable("Codex command is unavailable; no execution entry was reserved.")
    if config.get("kind") in SDK_TYPES:
        executable = config.get("executable")
        if not executable or not Path(executable).is_file():
            raise Unavailable("Native CLI is missing; install it before starting a session.")
        sdk_options(config, app, workspace, agent_id, "", root)
    existing = read_json(layout.local_path(root, "entry.json", worker_id), {})
    if item["current"]:
        if binding_id and item["current"] != binding_id:
            raise Conflict("Another entry already owns this instance.")
        snap = app.store(workspace).snapshot()
        entry = snap.json(layout.shared_path(snap, f"bindings/{item['current']}.json"))
        if entry["phase"] != "starting" or existing.get("binding") != item["current"] or entry["kind"] != config.get("kind", "manual"):
            raise Conflict("Entry is already owned. Start cannot resume or take over an active session.")
        launch = read_json(layout.local_path(root, "launch.json", worker_id), {})
        if entry.get("controller") or launch.get("attempted"):
            raise Conflict("The original session creation is running or has an unknown result; inspect it instead of repeating it.")
        result = {"agent": agent_id, "binding": item["current"], "phase": "starting", "kind": entry["kind"]}
    else:
        app.sync_agent(workspace, agent_id, str(root), worker_id=worker_id)
        result = app.reserve(workspace, agent_id, str(root), binding_id=binding_id,
                             expected_handoff=expected_handoff, worker_id=worker_id)
    binding = result["binding"]
    prompt = entry_prompt(app, workspace, agent_id, binding, root)
    bind_args = ["aw", "--home", str(app.home), "--workspace", workspace, "agent", "bind", agent_id,
                 "--binding", binding, "--session", "<THIS_NEW_NATIVE_SESSION_ID>", "--directory", str(root)]
    if worker_id is not None:
        bind_args += ["--worker-id", worker_id]
    if result["kind"] == "manual" or (result["kind"] == "desktop" and not desktop_ready):
        prefix = ("这是新会话接入。先登记这个新会话的真实 ID，成功前不要执行其他工作。不要使用历史 ID。\n"
                  "参数数组：" + json.dumps(bind_args, ensure_ascii=False) + "\nCodex 中真实 ID 可从 CODEX_THREAD_ID 读取。\n\n")
        prompt = prefix + prompt
        with layout.lock(root, "files.lock", worker_id=worker_id):
            prompt_path = layout.local_path(root, "entry-prompt.md", worker_id)
            write_bytes(prompt_path, prompt.encode())
            result.update(state="awaiting_new_session_bind", prompt_file=str(prompt_path), prompt=prompt)
        if result["kind"] == "desktop":
            from .desktop_projects import project_directory
            result["open_url"] = "codex://new?" + urllib.parse.urlencode({"path": str(project_directory(root, worker_id=worker_id)), "prompt": prompt})
            if open_app:
                result["app_open_requested"] = webbrowser.open(result["open_url"])
        return result
    with layout.lock(root, "files.lock", worker_id=worker_id):
        write_json(layout.local_path(root, "launch.json", worker_id), {"binding": binding, "attempted": False})
    return {**result, **spawn_runner(app, workspace, agent_id, str(root), worker_id=worker_id), "worker_id": worker_id}


def queue_input(app, workspace, agent_id, text, *, delivery="normal", purpose="user", directory=None, request_id=None,
                expected_binding=None, worker_id=None):
    root = app.root(workspace, agent_id, directory)
    _, agent, worker_id = _entry_owner(app, workspace, agent_id, worker_id, binding=expected_binding)
    if expected_binding is not None and agent["current"] != expected_binding:
        raise Conflict("The intended input binding changed; inspect the new entry before retrying.")
    if not isinstance(text, str) or not text.strip() or delivery not in ("normal", "insert"):
        raise Error("Input requires non-empty text and normal/insert delivery.")
    identifier = slug(request_id or uid("i"))
    # Serialize producers, not model turns. IDs identify requests; they do not order them.
    with layout.lock(root, "inputs.lock", worker_id=worker_id):
        path = layout.local_path(root, "inputs", worker_id) / f"{identifier}.json"
        app.require_binding(workspace, agent_id, agent["current"])
        previous = read_json(path)
        if previous:
            if (previous["text"], previous["binding"], previous["delivery"], previous["purpose"]) != (
                    text, agent["current"], delivery, purpose):
                raise Conflict("Input request ID has different content or belongs to an old entry.")
            return previous
        sequence_path = layout.local_path(root, "input-sequence.json", worker_id)
        sequence = read_json(sequence_path)
        if sequence is None:
            sequence = max((read_json(p).get("sequence", 0) for p in path.parent.glob("*.json")), default=0)
        sequence += 1
        # Reserve before publishing the input. A failed write may leave a gap, never a duplicate.
        write_json(sequence_path, sequence)
        record = {"id": identifier, "binding": agent["current"], "text": text, "delivery": delivery,
                  "purpose": purpose, "state": "queued", "created_at": now(), "sequence": sequence}
        if worker_id is not None:
            record["worker"] = worker_id
        write_json(path, record)
    return record


def receive_input(app, workspace, agent_id, binding, request_id, directory=None, worker_id=None):
    """Associate a delivered Desktop input with its actual executing native turn."""
    if desktop_actor(app, workspace, agent_id) != (workspace, agent_id, binding):
        raise Conflict("Input belongs to another execution entry.")
    root = app.root(workspace, agent_id, directory)
    owner, entry = app.require_binding(workspace, agent_id, binding, worker_id=worker_id)
    worker_id = owner.get("worker_id")
    identifier = slug(request_id)
    with layout.lock(root, "files.lock", worker_id=worker_id):
        path = layout.local_path(root, "inputs", worker_id) / (identifier + ".json")
        item = read_json(path)
        if not item or item["binding"] != binding or item["state"] not in ("dispatching", "submitted"):
            raise Conflict("This input is not awaiting this Desktop session.")
        if item.get("result", {}).get("turn", {}).get("id"):
            return {"request_id": request_id, "already_received": True,
                    "instruction": "Do not repeat execution; the original receipt is retained."}
        adopted = read_json(layout.local_path(root, "entry.json", worker_id))
        config = adopted["config"] if worker_id is not None else model_profiles.runtime_config(root)
        adapter = Desktop(root, config, os.environ["CODEX_THREAD_ID"], worker_id=worker_id)
        try:
            result = adapter.read()
        finally:
            adapter.close()
        turns = result.get("turns", [])
        if result["thread"]["status"]["type"] != "active" or not turns or turns[0].get("status") != "inProgress":
            raise Unavailable("Desktop cannot identify the active native turn; no input receipt was recorded.")
        app.require_binding(workspace, agent_id, binding)
        item.update(state="submitted", result={**item.get("result", {}), "turn": {"id": turns[0]["id"]}})
        write_json(path, item)
        return {"request_id": request_id, "text": item["text"]}


def handoff_request(app, workspace, agent_id, *, renew=False, directory=None, worker_id=None):
    _, agent, worker_id = _entry_owner(app, workspace, agent_id, worker_id)
    app.require_binding(workspace, agent_id, agent["current"])
    root = Path(app.prepare_agent_directory(workspace, agent_id, directory)["directory"])
    with layout.lock(root, "files.lock", worker_id=worker_id):
        control = read_json(layout.local_path(root, "control.json", worker_id), {})
        write_json(layout.local_path(root, "control.json", worker_id), {**control, "handoff": agent["current"]})
        write_json(layout.local_path(root, "watch.json", worker_id), {"enabled": False, "reason": "handoff_requested"})
        if renew:
            write_json(layout.local_path(root, "renew.json", worker_id), {"binding": agent["current"], "requested": True})
    guidance = (layout.instance_path(root, "prompts/handoff.md")).read_text(encoding="utf-8")
    text = ("本次明确请求当前入口 " + agent["current"] + " 正常交出。请使用这个 Binding 执行 handoff Skill，"
            "保存实际检查点、请求 agent.stop 后结束当前轮次，不自行启动后继。\n\n" + guidance)
    snap = app.store(workspace).snapshot()
    kind = snap.json(layout.shared_path(snap, f"bindings/{agent['current']}.json"))["kind"]
    return queue_input(app, workspace, agent_id, text, delivery="normal" if kind in SDK_TYPES else "insert", purpose="handoff", directory=str(root),
                       request_id="handoff-" + agent["current"], expected_binding=agent["current"], worker_id=worker_id)


def watch(app, workspace, agent_id, operation, interval=5, directory=None, worker_id=None):
    root = app.root(workspace, agent_id, directory)
    _, owner, worker_id = _entry_owner(app, workspace, agent_id, worker_id)
    path = layout.local_path(root, "watch.json", worker_id)
    if operation == "status":
        return read_json(path, {"enabled": False})
    if operation not in ("start", "stop") or interval < 0.5:
        raise Error("Watch expects start/stop and an interval of at least 0.5 seconds.")
    binding = owner["current"]
    if operation == "start":
        app.require_binding(workspace, agent_id, binding)
    result = {"enabled": operation == "start", "interval": interval, "binding": binding, "changed_at": now()}
    with layout.lock(root, "files.lock", worker_id=worker_id):
        write_json(layout.local_path(root, "watch.json", worker_id), result)
    if operation == "start":
        result["backend"] = backend.start(app)
    return result


class Runner:
    def __init__(self, app, workspace, agent_id, directory=None, stop_binding=None, expected_binding=None, worker_id=None):
        self.app, self.workspace, self.agent_id = app, workspace, agent_id
        self.root = app.root(workspace, agent_id, directory)
        self.adapter = None
        self.expected_binding = expected_binding or stop_binding
        _, _, self.worker_id = _entry_owner(app, workspace, agent_id, worker_id, binding=self.expected_binding)
        self.binding = self.expected_binding
        self.stop_event = threading.Event()
        self.renew_after_exit = False
        self.runtime_kind = None
        self.controller = None
        self.adapter_closed = False
        self.stop_binding = stop_binding
        self.stop_only = False
        self.cleanup_errors = []
        self.primary_failure = None
        self.stop_request = None

    def _close_adapter(self):
        if self.adapter is not None and not self.adapter_closed:
            self.adapter.close()
            self.adapter_closed = True

    def status(self, **values):
        model_receipt = getattr(self.adapter, "model_receipt", None)
        if isinstance(model_receipt, dict):
            values["model_profile"] = model_receipt
        native_title = getattr(self.adapter, "title_receipt", None)
        if isinstance(native_title, dict):
            values["native_title"] = native_title
        write_json(layout.local_path(self.root, "status.json", self.worker_id), {"pid": os.getpid(), "binding": self.binding, "worker_id": self.worker_id,
                   "observed_at": now(), **({"primary_failure": self.primary_failure} if self.primary_failure else {}),
                   **({"stop_request": self.stop_request} if self.stop_request else {}),
                   **values})

    def _wait_shared_read(self, stage, failure, attempts):
        delay = min(2 ** min(attempts, 5), 30)
        self.status(state="shared_read_backoff", stage=stage, reason=str(failure),
                    error_code=failure.code, attempts=attempts, retry_seconds=delay,
                    kind=self.runtime_kind, session=getattr(self.adapter, "session", None),
                    entry_automatically_released=False)
        if self._stop_requested() or self.stop_event.wait(delay) or self._stop_requested():
            raise _ReadStopped(str(failure)) from failure

    def _stop_requested(self):
        if self.stop_event.is_set():
            return True
        control = read_json(layout.local_path(self.root, "control.json", self.worker_id), {})
        if self.binding and control.get("stop") == self.binding:
            self.stop_event.set()
            self.status(state="monitor_stopped", entry_automatically_released=False)
            return True
        return False

    def _shared_read(self, stage, read, *args, **kwargs):
        # Only call this with a read. Retrying an outer operation could replay
        # inputs, native creation or a publication whose result is unknown.
        attempts = 0
        while True:
            try:
                result = read(*args, **kwargs)
            except RetryableRead as exc:
                attempts += 1
                self._wait_shared_read(stage, exc, attempts)
                continue
            if attempts:
                self.status(state="shared_read_recovered", stage=stage, attempts=attempts,
                            kind=self.runtime_kind, session=getattr(self.adapter, "session", None))
            return result

    def _read_state(self, stage="ownership"):
        def read():
            snap = self.app.store(self.workspace).snapshot()
            owner = self.app.agent(self.workspace, self.agent_id, snap, worker_id=self.worker_id)
            entry = snap.json(layout.shared_path(snap, f"bindings/{self.binding}.json"))
            return snap, owner, entry
        return self._shared_read(stage, read)

    def _cleanup_native(self, bridges=None):
        original = sys.exception()
        failures = []
        for close in ([bridges.stop_all] if bridges is not None else []) + [self._close_adapter]:
            try:
                close()
            except Exception as exc:
                failures.append(exc)
        if not failures:
            return
        self.cleanup_errors.extend(str(exc) for exc in failures)
        if original is not None:
            for exc in failures:
                original.add_note("Native cleanup failed: " + str(exc))
            return
        raise failures[0]

    def run(self):
        with layout.lock(self.root, "runner.lock", wait=0, worker_id=self.worker_id):
            failure = None
            try:
                self._run_owned()
            except _ReadStopped:
                self.status(state="monitor_stopped", entry_still_owned=True)
            except BaseException as exc:
                failure = exc
                self.primary_failure = {"reason": str(exc), "error_code": getattr(exc, "code", None)}
            try:
                self._release_controller()
            except BaseException as exc:
                if failure is None:
                    failure = exc
                else:
                    failure.add_note("Controller cleanup failed: " + str(exc))
                    self.cleanup_errors.append(str(exc))
        pending_stop = None
        if not self.stop_event.is_set() and not self.stop_only and self.binding and not isinstance(failure, Uncertain):
            # A stop can arrive while an execution runner is exiting. Reuse the
            # saved request after releasing the local lock, never restart work.
            try:
                _, owner, entry = self._read_state("stop_handover")
                if owner["current"] == self.binding and entry["phase"] == "stopping":
                    pending_stop = continue_stop(self.app, self.workspace, self.agent_id, self.binding,
                                                 str(self.root), expected_checkpoint=entry["checkpoint"], worker_id=self.worker_id)
            except BaseException as exc:
                if failure is None:
                    failure = exc
                else:
                    failure.add_note("Stop observation continuation failed: " + str(exc))
                    self.cleanup_errors.append(str(exc))
        if failure is not None:
            state = ("native_stop_unconfirmed" if self.controller is not None and self.adapter is not None
                     and not self.adapter_closed else "failed")
            with layout.lock(self.root, "files.lock", worker_id=self.worker_id):
                self.status(state=state, reason=str(failure), error_code=getattr(failure, "code", None),
                            cleanup_errors=self.cleanup_errors, stop_observation=pending_stop,
                            entry_automatically_released=False)
            raise failure
        if pending_stop is not None:
            return
        if self.stop_only or self.stop_event.is_set():
            return
        transfer = read_json(layout.local_path(self.root, "transfer.json", self.worker_id))
        if not (transfer and transfer["old_binding"] == self.binding) and not self.renew_after_exit:
            return
        handoff = self._normal_handoff_ready()
        if not handoff:
            return
        if transfer and transfer["old_binding"] == self.binding:
            from .transfer import advance
            advance(self.app, self.workspace, self.agent_id, str(self.root), worker_id=self.worker_id)
        elif self.renew_after_exit:
            renew = read_json(layout.local_path(self.root, "renew.json", self.worker_id))
            result = start(self.app, self.workspace, self.agent_id, str(self.root),
                           open_app=self.runtime_kind == "desktop", expected_handoff=handoff, worker_id=self.worker_id)
            with layout.lock(self.root, "files.lock", worker_id=self.worker_id):
                write_json(layout.local_path(self.root, "renew-result.json", self.worker_id), result)
                write_json(layout.local_path(self.root, "renew.json", self.worker_id), {**renew, "requested": False})

    def _normal_handoff_ready(self):
        snap, owner, entry = self._read_state("successor_qualification")
        if owner["current"] is not None or entry["phase"] != "released" or not owner["handoff"]:
            return False
        result = self._shared_read("successor_handoff", _released_stop, snap, self.agent_id, self.binding, entry)
        return result["handoff"] if owner["handoff"] == result["handoff"] else None

    def _run_owned(self):
        app, workspace, aid = self.app, self.workspace, self.agent_id
        software.require_ready(self.root)
        record = read_json(layout.local_path(self.root, "entry.json", self.worker_id))
        if not record:
            raise Error("No local entry; use relay/start before launching a runner.")
        if self.expected_binding and record["binding"] != self.expected_binding:
            raise Conflict("The original Binding changed before its Runner started.")
        self.binding = record["binding"]
        snap, item, entry = self._read_state()
        if self.stop_binding and entry and entry["phase"] == "released":
            self.stop_only = True
            result = self._shared_read("stop_result", _released_stop, snap, aid, self.binding, entry)
            self.status(**result)
            return
        if item["current"] != self.binding:
            raise Conflict("Local runner entry has been superseded.")
        config = record["config"] if self.worker_id is not None else model_profiles.runtime_config(self.root)
        if config.get("kind", "manual") != entry["kind"]:
            raise Conflict("Configured Runtime changed; handoff is required before changing the active Runtime.")
        if self.stop_binding and entry["phase"] != "stopping":
            raise Conflict("The observer cannot start or resume an execution entry.")
        if entry["phase"] == "stopping":
            self.stop_only = True
            self.runtime_kind = entry["kind"]
            self._observe_stop(entry, config)
            return
        if entry.get("controller"):
            raise Conflict("Another runner owns this binding. A crashed controller is not automatically taken over.")
        if entry["kind"] in model_profiles.CODEX_KINDS:
            model_profiles.migrate(self.root, self.worker_id)
            profile = model_profiles.adopted(self.root, self.binding, session=entry["session"], worker_id=self.worker_id)
            model_profiles.pin(self.root, self.binding, profile, self.worker_id)
        controller = uid("r")
        path = layout.shared_path(snap, f"bindings/{self.binding}.json")
        owner_path, _, _ = workers.execution_record(app, workspace, aid, snap, self.worker_id)
        app.store(workspace).change("main", {path: encode({**entry, "controller": controller})},
            {path: snap.entries[path], owner_path: snap.entries[owner_path],
             layout.shared_path(snap, f"agents/{aid}.json"): snap.entries[layout.shared_path(snap, f"agents/{aid}.json")]}, "Claim binding runner")
        self.controller = controller
        self.runtime_kind = entry["kind"]
        failures, read_failures, next_poll, bridges = 0, 0, 0.0, None
        self.status(state="connecting", kind=entry["kind"])
        try:
            if entry["kind"] == "manual":
                raise Unavailable("Manual entry has no push runner. Use receive in the actual session.")
            if entry["kind"] == "codex":
                launch_path = layout.local_path(self.root, "launch.json", self.worker_id)
                launch = read_json(launch_path, {})
                if entry["session"] is None and launch.get("attempted"):
                    raise Unavailable("A native session creation was already attempted. Inspect its result; it is not automatically repeated.")
                self.adapter = Codex(app, workspace, aid, self.binding, self.root, config, entry["session"],
                                     worker_id=self.worker_id, title=_session_title(app, workspace, item))
                if entry["session"] is None:
                    app.bind(workspace, aid, self.binding, self.adapter.session, str(self.root), worker_id=self.worker_id)
                    queue_input(app, workspace, aid, entry_prompt(app, workspace, aid, self.binding, self.root),
                                purpose="initial", directory=str(self.root), request_id="boot-" + self.binding,
                                expected_binding=self.binding, worker_id=self.worker_id)
            elif entry["kind"] in SDK_TYPES:
                launch_path = layout.local_path(self.root, "launch.json", self.worker_id)
                if entry["session"] is None and read_json(launch_path, {}).get("attempted"):
                    raise Unavailable("The original native launch is unresolved; do not repeat it.")
                if entry["session"] is None:
                    write_json(launch_path, {"binding": self.binding, "attempted": True})
                self.adapter = NativeSDK(app, workspace, aid, self.binding, self.root, config, entry["session"],
                                         worker_id=self.worker_id, title=_session_title(app, workspace, item))
                self.adapter.connect()
                if entry["session"] is None:
                    self.adapter.bootstrap(entry_prompt(app, workspace, aid, self.binding, self.root))
            else:
                self.adapter = Desktop(self.root, config, entry["session"], worker_id=self.worker_id,
                                       title=_session_title(app, workspace, item))
                if entry["session"] is None:
                    context = entry_context(workspace, aid, self.binding, self.root, item, entry)
                    prompt = json.dumps(context, ensure_ascii=False) + "\n\n" + (
                        files("agent_workspace") / "resources/prompts/desktop-connect.md").read_text(encoding="utf-8")
                    native = self.adapter.create(self.binding, prompt)
                    app.bind(workspace, aid, self.binding, self.adapter.session, str(self.root),
                             cwd=native["cwd"], worker_id=self.worker_id)
                    queue_input(app, workspace, aid, entry_prompt(app, workspace, aid, self.binding, self.root),
                                purpose="initial", directory=str(self.root), request_id="boot-" + self.binding,
                                expected_binding=self.binding, worker_id=self.worker_id)
                _, _, entry = self._read_state()
            from .bridges import BridgeManager
            from .transfer import persist_completion
            bridges = BridgeManager(app, workspace, aid, self.binding, self.root, worker_id=self.worker_id)
            self.status(state="running", kind=entry["kind"], session=self.adapter.session)
            while not self.stop_event.wait(0.5):
                if self._stop_requested():
                    break
                snap, agent, current = self._read_state()
                if agent["current"] != self.binding:
                    break
                if entry["kind"] in SDK_TYPES and self.adapter.status() == "unknown":
                    raise Unavailable("Native SDK is disconnected; inspect the original input before recovery.")
                if current["phase"] == "stopping":
                    if self.stop_request is None:
                        self.stop_request = {"id": self.binding, "session": self.adapter.session,
                                             "checkpoint": current["checkpoint"], "controller": self.controller}
                    if any(current.get(key) != value for key, value in self.stop_request.items()):
                        raise Conflict("The original stop request changed during observation.")
                    bridges.stop_all()
                    # A closed managed writer cannot execute again. Closing a
                    # Desktop control connection leaves the chat alive, so read
                    # its current state again before retrying a preflight read.
                    if isinstance(self.adapter, Desktop) and self.adapter_closed:
                        self.adapter = Desktop(self.root, config, self.stop_request["session"], read_only=True, worker_id=self.worker_id)
                        self.adapter_closed = False
                    native_closed = self.adapter_closed and not isinstance(self.adapter, Desktop)
                    native_state = "idle" if native_closed else self.adapter.status()
                    self.status(state="handoff_waiting_idle" if native_state in ("idle", "busy") else "stop_observation_unknown",
                                session=self.adapter.session, native_state=native_state)
                    if self._stop_requested():
                        break
                    if native_state == "idle":
                        if isinstance(self.adapter, Desktop):
                            self._complete_inputs(stopping_checkpoint=current["checkpoint"])
                        # Desktop retains its idle chat; its platform authority is released below.
                        # Other adapters close the managed writer before releasing ownership.
                        self._close_adapter()
                        # Closing drains native events; idle alone is not input success.
                        if not isinstance(self.adapter, Desktop):
                            self._complete_inputs(stopping_checkpoint=current["checkpoint"])
                        persist_completion(self.root, current, self.worker_id)
                        try:
                            result = app.finish_stop(workspace, aid, self.binding, observed_idle=True,
                                expected_controller=self.stop_request["controller"], expected_checkpoint=self.stop_request["checkpoint"],
                                expected_session=self.stop_request["session"], worker_id=self.worker_id)
                        except RetryableRead as exc:
                            # Core only raises this before a publication can
                            # happen. Reobserve the fixed request; Uncertain is
                            # deliberately left outside this recovery path.
                            read_failures += 1
                            self._wait_shared_read("stop_preflight", exc, read_failures)
                            continue
                        self.status(state="released", handoff=result["id"])
                        break
                    continue
                try:
                    stage = "bridge_poll"
                    handoff_requested = read_json(layout.local_path(self.root, "control.json", self.worker_id), {}).get("handoff") == self.binding
                    if handoff_requested:
                        bridges.stop_all()
                    else:
                        bridges.tick()
                    records = self._read_inputs()
                    stage = "input_completion"
                    self._complete_inputs(records)
                    persist_completion(self.root, current, self.worker_id)
                    stage = "input_dispatch"
                    self._inputs(records)
                    setting = read_json(layout.local_path(self.root, "watch.json", self.worker_id), {"enabled": False})
                    if not handoff_requested and setting.get("enabled") and setting.get("binding") == self.binding and time.monotonic() >= next_poll:
                        stage = "watch_poll"
                        result = Messages(app).poll(workspace, aid, self.binding, adapter=self.adapter, directory=str(self.root))
                        self.status(state="running", kind=entry["kind"], session=self.adapter.session, poll=result)
                        next_poll = time.monotonic() + setting.get("interval", 5)
                    failures = 0
                    if read_failures:
                        self.status(state="running", kind=entry["kind"], session=self.adapter.session,
                                    recovered_read_failures=read_failures)
                        read_failures = 0
                except RetryableRead as exc:
                    # Return to a fresh ownership read and durable queue records.
                    # Adapter setup is not repeated; submitted/unknown inputs keep
                    # their original IDs and are never reset to queued.
                    read_failures += 1
                    self._wait_shared_read(stage, exc, read_failures)
                except Conflict:
                    # Only an observed ownership transition is a reason to continue the loop.
                    latest, owner, current = self._read_state()
                    if owner["current"] != self.binding:
                        break
                    if current["phase"] == "stopping":
                        continue
                    raise
                except (Unavailable, OSError) as exc:
                    failures += 1
                    self.status(state="connection_failed", reason=str(exc), attempts=failures)
                    if entry["kind"] != "desktop" or failures >= 5:
                        break
                    if self.stop_event.wait(min(2 **failures, 30)):
                        break
                    latest, owner, current = self._read_state()
                    if owner["current"] != self.binding or current["phase"] != "active":
                        break
                    self._close_adapter()
                    if self.worker_id is None:
                        config = model_profiles.runtime_config(self.root)
                    self.adapter = self._reconnect_desktop(config, entry["session"], failures)
                    self.adapter_closed = False
                    if self.adapter is None:
                        break
        finally:
            self._cleanup_native(bridges)
        renew = read_json(layout.local_path(self.root, "renew.json", self.worker_id), {})
        if renew.get("requested") and renew.get("binding") == self.binding:
            self.renew_after_exit = True

    def _observe_stop(self, request, config):
        """Observe the saved Desktop request; never claim a native writer."""
        if request["kind"] != "desktop" or not request["session"]:
            self.status(state="stop_observation_unknown", kind=request["kind"],
                        reason="No independent stop observer for this native entry.",
                        entry_automatically_released=False)
            return
        from .transfer import persist_completion
        self.stop_request = {key: request.get(key) for key in ("id", "session", "checkpoint", "controller")}
        failures, read_failures = 0, 0
        try:
            while not self._stop_requested():
                snap, owner, current = self._read_state()
                if current["phase"] == "released":
                    if current["session"] != request["session"]:
                        raise Conflict("The released entry belongs to a different native session.")
                    result = self._shared_read("stop_result", _released_stop, snap, self.agent_id,
                                              self.binding, current, request["checkpoint"])
                    self.status(**result)
                    return
                if owner["current"] != self.binding or current["phase"] != "stopping":
                    raise Conflict("The original stop request no longer owns this instance.")
                for key in ("session", "checkpoint", "controller"):
                    if current.get(key) != request.get(key):
                        raise Conflict("The stop request or its controller changed during observation.")
                self._shared_read("stop_checkpoint", self.app.checkpoint_show, self.workspace,
                                  self.agent_id, current["checkpoint"], worker_id=self.worker_id)
                try:
                    if self.adapter is None:
                        if self.worker_id is None:
                            config = model_profiles.runtime_config(self.root)
                        if config.get("kind") != request["kind"]:
                            raise Conflict("Configured Runtime changed during stop observation.")
                        self.adapter = Desktop(self.root, config, request["session"], read_only=True, worker_id=self.worker_id)
                        self.adapter_closed = False
                    native_state = self.adapter.status()
                    failures = 0
                except (Unavailable, OSError) as exc:
                    failures += 1
                    delay = min(2 ** min(failures, 5), 30)
                    self.status(state="stop_observation_unknown", session=request["session"],
                                reason=str(exc), attempts=failures, retry_seconds=delay if failures < 5 else 0,
                                recovery_paused=failures >= 5)
                    self._close_adapter()
                    self.adapter = None
                    if failures >= 5:
                        return
                    if self.stop_event.wait(delay):
                        return
                    continue
                self.status(state="handoff_waiting_idle" if native_state in ("idle", "busy") else "stop_observation_unknown",
                            session=request["session"], native_state=native_state)
                if self._stop_requested():
                    return
                if native_state == "idle":
                    self._complete_inputs(stopping_checkpoint=current["checkpoint"])
                    self._close_adapter()
                    persist_completion(self.root, current, self.worker_id)
                    try:
                        result = self.app.finish_stop(self.workspace, self.agent_id, self.binding, observed_idle=True,
                            expected_controller=request.get("controller"), expected_checkpoint=request["checkpoint"],
                            expected_session=request["session"], worker_id=self.worker_id)
                    except RetryableRead as exc:
                        read_failures += 1
                        self._wait_shared_read("stop_preflight", exc, read_failures)
                        self.adapter = None
                        continue
                    self.status(state="released", handoff=result["id"], session=request["session"])
                    return
                if self.stop_event.wait(0.5):
                    return
        finally:
            self._cleanup_native()

    def _release_controller(self):
        if self.controller is None:
            return
        if self.adapter is not None and not self.adapter_closed:
            self.status(state="native_stop_unconfirmed", entry_automatically_released=False)
            return
        store = self.app.store(self.workspace)
        attempts = 0
        while True:
            snap, _, entry = self._read_state("controller_cleanup")
            path = layout.shared_path(snap, f"bindings/{self.binding}.json")
            if entry.get("controller") == self.controller:
                entry.pop("controller")
                try:
                    store.change("main", {path: encode(entry)}, {path: snap.entries[path]}, "Release binding runner")
                except RetryableRead as exc:
                    attempts += 1
                    self._wait_shared_read("controller_cleanup", exc, attempts)
                    continue
            self.controller = None
            return

    def _reconnect_desktop(self, config, session, attempts):
        while attempts < 5:
            latest, owner, entry = self._read_state()
            control = read_json(layout.local_path(self.root, "control.json", self.worker_id), {})
            stopped = control.get("stop") == self.binding or control.get("handoff") == self.binding
            if stopped or owner["current"] != self.binding or entry["phase"] != "active":
                return None
            try:
                return Desktop(self.root, config, session, worker_id=self.worker_id)
            except (Unavailable, OSError) as exc:
                attempts += 1
                self.status(state="connection_failed", reason=str(exc), attempts=attempts)
                if attempts >= 5 or self.stop_event.wait(min(2 ** attempts, 30)):
                    return None
        return None

    def _read_inputs(self):
        records = []
        for path in (layout.local_path(self.root, "inputs", self.worker_id)).glob("*.json"):
            item = read_json(path)
            if item["binding"] == self.binding and (
                    item["state"] in ("queued", "submitted") or
                    (item["purpose"] == "initial" and item["state"] == "completed" and not item.get("checkpoint_revision"))):
                records.append((path, item))
        return records

    def _complete_inputs(self, records=None, *, stopping_checkpoint=None):
        if not isinstance(self.adapter, (Codex, NativeSDK, Desktop)):
            return
        records = self._read_inputs() if records is None else records
        completed = {}
        if isinstance(self.adapter, Desktop):
            identifiers = {item["result"]["turn"]["id"] for _, item in records
                           if item["state"] == "submitted" and item.get("result", {}).get("turn", {}).get("id")}
            if identifiers:
                completed = self.adapter.completed_turns(identifiers)
                for turn_id, turn in completed.items():
                    metadata = {key: turn[key] for key in ("id", "status", "error", "startedAt", "completedAt", "durationMs") if key in turn}
                    write_json(layout.instance_path(self.root, "records", self.worker_id) / self.binding / "desktop-turns" / (slug(turn_id) + ".json"),
                               {"source": "Codex Desktop read_thread", "thread_id": self.adapter.session,
                                "observed_at": now(), "turn": metadata,
                                "scope": "Native turn metadata only; message and tool bodies remain in Desktop."})
        else:
            while not self.adapter.completed.empty():
                turn = self.adapter.completed.get_nowait()
                completed[turn["id"]] = turn
        for path, item in records:
            result = item.get("result", {})
            # Codex turn/start returns turn.id; busy turn/steer returns turnId.
            turn_id = result.get("turn", {}).get("id") or result.get("turnId")
            if item["state"] == "submitted" and turn_id in completed:
                item["state"] = "completed" if completed[turn_id].get("status") == "completed" else "failed"
                write_json(path, item)
        # Persist all observed completions before attempting any checkpoint publication.
        for path, item in records:
            if item["purpose"] != "initial" or item["state"] != "completed" or item.get("checkpoint_revision"):
                continue
            if stopping_checkpoint:
                # A boot turn can itself stop. Reuse its explicit handoff snapshot;
                # never publish a later automatic checkpoint during writer cleanup.
                point = self._shared_read("stop_checkpoint", self.app.checkpoint_show,
                                         self.workspace, self.agent_id, stopping_checkpoint, worker_id=self.worker_id)
            else:
                point = self.app.checkpoint(self.workspace, self.agent_id,
                    "本会话进入轮次已结束。实际职责与资料以此快照中的文件为准。",
                    content=("Desktop 轮次元数据按记录段保存，正文仍在原聊天；不宣称执行了未安排的产品任务。"
                             if isinstance(self.adapter, Desktop) else
                             "原生事件按记录段保存；此记录不宣称执行了任何未安排的产品任务。"),
                    binding=self.binding, directory=str(self.root), checkpoint_id="initial-" + self.binding,
                    worker_id=self.worker_id)
            item["checkpoint_revision"] = point["revision"]
            write_json(path, item)

    def _inputs(self, records=None):
        records = self._read_inputs() if records is None else records
        queued = [(path, item) for path, item in records if item["state"] == "queued"]
        # Legacy records have no sequence; keep them first in recorded timestamp order.
        queued.sort(key=lambda pair: (pair[1].get("sequence", 0), pair[1]["created_at"], pair[1]["id"]))
        for path, item in queued:
            if item["delivery"] == "insert" and getattr(self.adapter, "supports_insert", True) is False:
                self.status(state="input_blocked", message_id=item["id"], reason="insert_not_supported")
                return
            if self.adapter.status() == "busy" and item["delivery"] == "normal":
                return
            owner, entry = self._shared_read("input_qualification", self.app.require_binding,
                                            self.workspace, self.agent_id, self.binding)
            if isinstance(self.adapter, Desktop):
                profile, validation = self.adapter.model_choice("send_message_to_thread", self.binding)
                item["model_profile"] = model_profiles.receipt(profile, validation)
            elif isinstance(self.adapter, Codex):
                item["model_profile"] = model_profiles.receipt(self.adapter.profile, self.adapter.profile_validation)
            item.update(state="dispatching", attempted_at=now())
            write_json(path, item)
            try:
                if isinstance(self.adapter, Desktop):
                    args = desktop_cli(self.app, self.workspace, self.agent_id) + ["runtime.receive-input", "--arguments",
                           json.dumps({"request_id": item["id"]}, ensure_ascii=False)]
                    context = entry_context(self.workspace, self.agent_id, self.binding, self.root, owner, entry)
                    prompt = "\n\n".join([json.dumps(context, ensure_ascii=False), (
                        files("agent_workspace") / "resources/prompts/desktop-input.md").read_text(encoding="utf-8"),
                        json.dumps(args, ensure_ascii=False)])
                else:
                    prompt = item["text"]
                response = self.adapter.notify(prompt, item["delivery"])
            except Exception as exc:
                with layout.lock(self.root, "files.lock", worker_id=self.worker_id):
                    latest = read_json(path) if isinstance(self.adapter, Desktop) else item
                    received = latest.get("result", {}).get("turn", {}).get("id")
                    latest.update(state="submitted" if received else "outcome_unknown", error=str(exc))
                    model_receipt = getattr(self.adapter, "model_receipt", None)
                    if isinstance(model_receipt, dict):
                        latest["model_profile"] = model_receipt
                    write_json(path, latest)
                raise
            with layout.lock(self.root, "files.lock", worker_id=self.worker_id):
                latest = read_json(path) if isinstance(self.adapter, Desktop) else item
                latest.update(state="submitted", result={**response, **latest.get("result", {})})
                model_receipt = getattr(self.adapter, "model_receipt", None)
                if isinstance(model_receipt, dict):
                    latest["model_profile"] = model_receipt
                write_json(path, latest)
            return
