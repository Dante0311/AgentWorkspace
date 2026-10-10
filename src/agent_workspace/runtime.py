from __future__ import annotations

from importlib.resources import files
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser

from . import __version__
from . import model_profiles
from .messages import Messages
from .shared import requirements
from .rpc import Rpc
from .native_sdk import NativeSDK, SDK_TYPES, sdk_options
from .util import Conflict, Error, Unavailable, encode, locked, now, read_json, slug, uid, write_bytes, write_json


TOOL_SCHEMA = {"type": "object", "properties": {"command": {"type": "string"},
    "arguments": {"type": "object"}}, "required": ["command", "arguments"], "additionalProperties": False}


def entry_prompt(app, workspace, agent_id, binding, root):
    snap = app.store(workspace).snapshot()
    entry = snap.json(f"bindings/{binding}.json")
    item = app.agent(workspace, agent_id, snap)
    # Read installed guidance, not a potentially stale copy from an older checkpoint.
    capabilities = (files("agent_workspace") / "resources" / "prompts" / "capabilities.md").read_text(encoding="utf-8")
    entry_mode = "relay" if entry["handoff"] else "fork" if item.get("forked_from") else "initial"
    lines = [json.dumps({"workspace": workspace, "agent": agent_id, "binding": binding,
                        "entry_mode": entry_mode, "runtime_kind": entry["kind"], "instance_root": str(root)}, ensure_ascii=False),
             (files("agent_workspace") / "resources/prompts/entry.md").read_text(encoding="utf-8"), capabilities,
             "平台命令使用 aw_execute 动态工具，或运行 aw。调用参数中的 workspace、agent_id、binding 必须使用上述值。"]
    required = requirements(app, workspace, root, snap)
    if required:
        lines.append("required_workspace_read: " + json.dumps(required, ensure_ascii=False))
    if entry["handoff"]:
        handoff = snap.json(f"handoffs/{entry['handoff']}.json")
        point = app.checkpoint_show(workspace, agent_id, handoff["checkpoint"])
        lines.append("交接点与检查点：\n" + json.dumps(point, ensure_ascii=False))
    elif item.get("forked_from"):
        lines.append("你是新的实例，不是历史里的发送者或负责人。来源：\n" + json.dumps(item["forked_from"], ensure_ascii=False))
    else:
        lines.append((root / ".aw/prompts/initialization.md").read_text(encoding="utf-8"))
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
    agent = app.agent(workspace, agent_id)
    binding = agent["current"]
    if not session or not binding:
        raise Conflict("This Desktop session has no current execution entry.")
    _, entry = app.require_binding(workspace, agent_id, binding, allow_stopping=True)
    if entry["kind"] != "desktop" or entry["session"] != session:
        raise Conflict("The real Desktop session does not own this execution entry.")
    return workspace, agent_id, binding


def desktop_directory_actor(app, operation=None):
    """Keep ordinary CLI calls inside a managed Desktop directory caller-bound."""
    session = os.environ.get("CODEX_THREAD_ID")
    if not session:
        return None
    cwd = Path.cwd().resolve()
    for workspace, settings in app.local()["workspaces"].items():
        for agent_id, locations in settings.get("instances", {}).items():
            for location in locations:
                root = Path(location).resolve()
                if not cwd.is_relative_to(root):
                    continue
                snapshot = app.store(workspace).snapshot()
                agent = app.agent(workspace, agent_id, snapshot)
                entry = snapshot.json(f"bindings/{agent['current']}.json") if agent["current"] else None
                if entry and entry["kind"] == "desktop":
                    if (entry["phase"] == "starting" and entry["session"] is None
                            and operation in ("agent.bind", "agent.capture-desktop")
                            and not entry.get("controller")
                            and not read_json(root / ".aw-local/launch.json", {}).get("attempted")):
                        return None  # User-started manual bootstrap, before an execution identity exists.
                    return desktop_actor(app, workspace, agent_id)
                for path in snapshot.entries:
                    if not path.startswith("bindings/"):
                        continue
                    old = snapshot.json(path)
                    if old["agent"] == agent_id and old["kind"] == "desktop" and old["session"] == session:
                        raise Conflict("This Desktop chat has handed off; it cannot become a user-management caller.")
                if not entry and agent["has_run"] and read_json(root / ".aw-local/runtime.json", {}).get("kind") == "desktop":
                    raise Conflict("This Desktop instance has handed off; the old chat cannot become a user-management caller.")
    return None


def configure_desktop(app, workspace, agent_id, command=None, directory=None):
    root = app.root(workspace, agent_id, directory)
    pipe, thread = os.environ.get("CODEX_APP_TOOLS_PIPE_PATH"), os.environ.get("CODEX_THREAD_ID")
    if not pipe or not thread:
        raise Error("Run capture-desktop inside the real Desktop session; both CODEX environment values are required.")
    model_profiles.migrate(root)
    with locked(root / ".aw-local/files.lock"):
        value = read_json(root / ".aw-local/runtime.json", {})
        value.update(kind="desktop", pipe_path=pipe, caller_thread=thread)
        if command:
            value["command"] = command
        if not value.get("command"):
            raise Error("Supply the actual desktop MCP server command as a JSON array; do not start codex app-server here.")
        write_json(root / ".aw-local/runtime.json", value)
    return {"captured": True, "kind": "desktop", "credentials_printed": False}


def desktop_profile(app, workspace, agent_id, model="", effort="", project_id="", directory=None):
    root = app.root(workspace, agent_id, directory)
    if app.agent(workspace, agent_id)["current"]:
        raise Conflict("Handoff before changing the Desktop profile of an active instance.")
    config = read_json(root / ".aw-local/runtime.json", {})
    if config.get("kind") != "desktop":
        raise Unavailable("Capture this instance's real Desktop connection first.")
    config.update(model=model, effort=effort, project_id=project_id or config.get("project_id", ""))
    adapter = Desktop(root, config, None)
    try:
        project = adapter.project()
    finally:
        adapter.close()
    app.configure(workspace, agent_id, config, str(root))
    return {"configured": True, "kind": "desktop", "project_id": project["projectId"],
            "project_name": project["label"], "primary_folder": project["path"], "model": model, "effort": effort}


class Codex:
    supports_insert = True

    def __init__(self, app, workspace, agent_id, binding, root, config, session=None):
        self.app, self.workspace, self.agent_id, self.binding, self.root = app, workspace, agent_id, binding, root
        self.session = session
        model_profiles.migrate(root)
        self.profile = model_profiles.pin(root, binding, model_profiles.adopted(root, binding, session=session))
        self.profile_validation = {"catalog": "unconfirmed", "effective": "unconfirmed"}
        self.model_receipt = model_profiles.receipt(self.profile, self.profile_validation)
        config, _, _ = model_profiles.split_config(config)
        self.busy, self.turn_id = False, None
        self.completed = queue.Queue()
        self.record = root / "records" / binding / "runtime.jsonl"
        self.record.parent.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, AW_HOME=str(app.home), AW_WORKSPACE=workspace, AW_AGENT=agent_id, AW_BINDING=binding)
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
                write_json(root / ".aw-local/launch.json", {"binding": binding, "attempted": True,
                           "model_profile": model_profiles.receipt(self.profile, self.profile_validation)})
                result = self.rpc.request("thread/start", params)
                self.session = result["thread"]["id"]
            self.model_receipt = model_profiles.receipt(self.profile, self.profile_validation, accepted=True, result=result)
            launch = read_json(root / ".aw-local/launch.json", {})
            write_json(root / ".aw-local/launch.json", {**launch, "binding": binding,
                       "session": self.session, "model_profile": self.model_receipt})
            model_profiles.require_matching(self.model_receipt)
            self.status()
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
        with locked(self.root / ".aw-local/records.lock"):
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


class Desktop:
    supports_insert = True

    """Attach to the desktop-owned MCP control endpoint; never spawn a competing writer."""
    def __init__(self, root, config, session):
        self.root, self.session = root, session
        self.config = config
        self.profile = None
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
            if not {"read_thread", "send_message_to_thread"}.issubset(names):
                self.close()
                raise Unavailable("Installed Desktop does not expose the expected control tools; no CLI fallback was used.")
        except BaseException:
            self.rpc.close()
            raise

    def call(self, name, arguments):
        result = self.rpc.request("tools/call", {"name": name, "arguments": arguments,
                                    "_meta": {"openai/threadId": self.caller_thread}})
        if result.get("isError"):
            raise Unavailable("Desktop tool rejected the request: " + json.dumps(result.get("content", []), ensure_ascii=False)[:1000])
        return json.loads(result["content"][0]["text"])

    def status(self):
        result = self.read()
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

    def read(self, **options):
        return self.call("read_thread", {"threadId": self.session, "turnLimit": 1,
                                        "maxOutputCharsPerItem": 100, **options})

    def project(self):
        if not {"create_thread", "list_projects"}.issubset(self.tools):
            raise Unavailable("This Desktop connection cannot create real project chats.")
        projects = self.call("list_projects", {})["projects"]
        matches = [p for p in projects if p.get("projectKind") == "local"
                   and p.get("hostId") == "local" and p.get("path")
                   and Path(p["path"]).resolve() == self.root.resolve()]
        selected = self.config.get("project_id")
        if selected:
            matches = [p for p in matches if p["projectId"] == selected]
        if len(matches) != 1:
            raise Unavailable("Select one saved local Codex project whose primary folder is this instance. "
                              "Create it manually if missing; set project_id when more than one matches.")
        return matches[0]

    def create(self, binding):
        profile, validation = self.model_choice("create_thread", binding)
        project = self.project()
        path = self.root / ".aw-local/launch.json"
        previous = read_json(path, {})
        if previous.get("binding") == binding and previous.get("attempted"):
            raise Conflict("Desktop creation was already attempted; inspect the original result before recovery.")
        prompt = (files("agent_workspace") / "resources/prompts/desktop-connect.md").read_text(encoding="utf-8")
        arguments = {"target": {"type": "project", "projectId": project["projectId"],
                                "environment": {"type": "local"}}, "prompt": prompt}
        arguments.update(model=profile["model"], thinking=profile["effort"])
        write_json(path, {"binding": binding, "attempted": True, "project_id": project["projectId"],
                   "model_profile": model_profiles.receipt(profile, validation)})
        result = self.call("create_thread", arguments)
        self.model_receipt = model_profiles.receipt(profile, validation, accepted=True, result=result)
        write_json(path, {"binding": binding, "attempted": True, "result": result, "model_profile": self.model_receipt})
        model_profiles.require_matching(self.model_receipt)
        if not result.get("threadId") or result.get("hostId") != "local":
            raise Unavailable("Desktop did not return a ready local chat; preserve the launch receipt, do not repeat creation.")
        self.session = result["threadId"]
        thread = self.read()["thread"]
        if thread.get("id") != self.session or not thread.get("cwd") or Path(thread["cwd"]).resolve() != self.root.resolve():
            raise Unavailable("The created Desktop chat has not verified this instance directory; it was not bound.")

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
        profile = selected or self.profile or model_profiles.adopted(self.root, binding, session=self.session)
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
        record = read_json(self.root / ".aw-local/entry.json", {})
        if selected is None and record.get("binding"):
            profile = model_profiles.pin(self.root, binding or record["binding"], profile)
        if selected is None:
            self.profile = profile
            self.profile_validation = validation
        return profile, validation

    def close(self):
        self.rpc.close()


def spawn_runner(app, workspace, agent_id, directory=None):
    root = app.root(workspace, agent_id, directory)
    log = root / ".aw-local/runner.log"
    with log.open("ab") as output:
        args = [sys.executable, "-m", "agent_workspace", "--home", str(app.home), "--workspace", workspace,
                "runtime", "run", agent_id, "--directory", str(root)]
        kwargs = {"creationflags": 0x08000000} if os.name == "nt" else {"start_new_session": True}
        env = {key: value for key, value in os.environ.items()
               if key not in ("AW_HOME", "AW_WORKSPACE", "AW_AGENT", "AW_BINDING", "CODEX_THREAD_ID")}
        proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=output, stderr=output, env=env, **kwargs)
    return {"pid": proc.pid, "state": "starting_runner"}


def start(app, workspace, agent_id, directory=None, open_app=False, binding_id=None):
    root = app.root(workspace, agent_id, directory)
    if (root / ".aw-local/skill-install/operation.json").exists():
        raise Conflict("Recover the pending Skill update before starting a session.")
    requirements(app, workspace, root)  # Fail before reserving an entry or opening a native session.
    config = model_profiles.migrate(root)
    item = app.agent(workspace, agent_id)
    profile = None
    if config.get("kind") in model_profiles.CODEX_KINDS:
        profile = model_profiles.adopted(root, item["current"]) if item["current"] else model_profiles.selected(root)
    desktop_ready = config.get("kind") == "desktop" and all(config.get(k) for k in ("command", "pipe_path", "caller_thread"))
    if desktop_ready:
        adapter = Desktop(root, config, None)
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
    existing = read_json(root / ".aw-local/entry.json", {})
    if item["current"]:
        if binding_id and item["current"] != binding_id:
            raise Conflict("Another entry already owns this instance.")
        entry = app.store(workspace).snapshot().json(f"bindings/{item['current']}.json")
        if entry["phase"] != "starting" or existing.get("binding") != item["current"] or entry["kind"] != config.get("kind", "manual"):
            raise Conflict("Entry is already owned. Start cannot resume or take over an active session.")
        launch = read_json(root / ".aw-local/launch.json", {})
        if entry.get("controller") or launch.get("attempted"):
            raise Conflict("The original session creation is running or has an unknown result; inspect it instead of repeating it.")
        result = {"agent": agent_id, "binding": item["current"], "phase": "starting", "kind": entry["kind"]}
    else:
        app.sync_agent(workspace, agent_id, str(root))
        result = app.reserve(workspace, agent_id, str(root), binding_id=binding_id)
    binding = result["binding"]
    prompt = entry_prompt(app, workspace, agent_id, binding, root)
    bind_args = ["aw", "--home", str(app.home), "--workspace", workspace, "agent", "bind", agent_id,
                 "--binding", binding, "--session", "<THIS_NEW_NATIVE_SESSION_ID>", "--directory", str(root)]
    if result["kind"] == "manual" or (result["kind"] == "desktop" and not desktop_ready):
        prefix = ("这是新会话接入。先登记这个新会话的真实 ID，成功前不要执行其他工作。不要使用历史 ID。\n"
                  "参数数组：" + json.dumps(bind_args, ensure_ascii=False) + "\nCodex 中真实 ID 可从 CODEX_THREAD_ID 读取。\n\n")
        prompt = prefix + prompt
        write_bytes(root / ".aw-local/entry-prompt.md", prompt.encode())
        result.update(state="awaiting_new_session_bind", prompt_file=str(root / ".aw-local/entry-prompt.md"), prompt=prompt)
        if result["kind"] == "desktop":
            result["open_url"] = "codex://new?" + urllib.parse.urlencode({"path": str(root), "prompt": prompt})
            if open_app:
                result["app_open_requested"] = webbrowser.open(result["open_url"])
        return result
    write_json(root / ".aw-local/launch.json", {"binding": binding, "attempted": False})
    return {**result, **spawn_runner(app, workspace, agent_id, str(root))}


def queue_input(app, workspace, agent_id, text, *, delivery="normal", purpose="user", directory=None, request_id=None,
                expected_binding=None):
    root = app.root(workspace, agent_id, directory)
    agent = app.agent(workspace, agent_id)
    if expected_binding is not None and agent["current"] != expected_binding:
        raise Conflict("The intended input binding changed; inspect the new entry before retrying.")
    if not isinstance(text, str) or not text.strip() or delivery not in ("normal", "insert"):
        raise Error("Input requires non-empty text and normal/insert delivery.")
    identifier = slug(request_id or uid("i"))
    path = root / ".aw-local/inputs" / f"{identifier}.json"
    # Serialize producers, not model turns. IDs identify requests; they do not order them.
    with locked(root / ".aw-local/inputs.lock"):
        app.require_binding(workspace, agent_id, agent["current"])
        previous = read_json(path)
        if previous:
            if (previous["text"], previous["binding"], previous["delivery"], previous["purpose"]) != (
                    text, agent["current"], delivery, purpose):
                raise Conflict("Input request ID has different content or belongs to an old entry.")
            return previous
        sequence_path = root / ".aw-local/input-sequence.json"
        sequence = read_json(sequence_path)
        if sequence is None:
            sequence = max((read_json(p).get("sequence", 0) for p in path.parent.glob("*.json")), default=0)
        sequence += 1
        # Reserve before publishing the input. A failed write may leave a gap, never a duplicate.
        write_json(sequence_path, sequence)
        record = {"id": identifier, "binding": agent["current"], "text": text, "delivery": delivery,
                  "purpose": purpose, "state": "queued", "created_at": now(), "sequence": sequence}
        write_json(path, record)
    return record


def receive_input(app, workspace, agent_id, binding, request_id, directory=None):
    """Associate a delivered Desktop input with its actual executing native turn."""
    if desktop_actor(app, workspace, agent_id) != (workspace, agent_id, binding):
        raise Conflict("Input belongs to another execution entry.")
    root = app.root(workspace, agent_id, directory)
    path = root / ".aw-local/inputs" / (slug(request_id) + ".json")
    with locked(path.with_suffix(".lock")):
        item = read_json(path)
        if not item or item["binding"] != binding or item["state"] not in ("dispatching", "submitted"):
            raise Conflict("This input is not awaiting this Desktop session.")
        if item.get("result", {}).get("turn", {}).get("id"):
            return {"request_id": request_id, "already_received": True,
                    "instruction": "Do not repeat execution; the original receipt is retained."}
        adapter = Desktop(root, read_json(root / ".aw-local/runtime.json"), os.environ["CODEX_THREAD_ID"])
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


def handoff_request(app, workspace, agent_id, *, renew=False, directory=None):
    root = app.root(workspace, agent_id, directory)
    agent = app.agent(workspace, agent_id)
    app.require_binding(workspace, agent_id, agent["current"])
    control = read_json(root / ".aw-local/control.json", {})
    write_json(root / ".aw-local/control.json", {**control, "handoff": agent["current"]})
    write_json(root / ".aw-local/watch.json", {"enabled": False, "reason": "handoff_requested"})
    if renew:
        write_json(root / ".aw-local/renew.json", {"binding": agent["current"], "requested": True})
    text = (root / ".aw/prompts/handoff.md").read_text(encoding="utf-8")
    kind = app.store(workspace).snapshot().json(f"bindings/{agent['current']}.json")["kind"]
    return queue_input(app, workspace, agent_id, text, delivery="normal" if kind in SDK_TYPES else "insert", purpose="handoff", directory=str(root),
                       request_id="handoff-" + agent["current"])


def watch(app, workspace, agent_id, operation, interval=5, directory=None):
    root = app.root(workspace, agent_id, directory)
    path = root / ".aw-local/watch.json"
    if operation == "status":
        return read_json(path, {"enabled": False})
    if operation not in ("start", "stop") or interval < 0.5:
        raise Error("Watch expects start/stop and an interval of at least 0.5 seconds.")
    binding = app.agent(workspace, agent_id)["current"]
    if operation == "start":
        app.require_binding(workspace, agent_id, binding)
    result = {"enabled": operation == "start", "interval": interval, "binding": binding, "changed_at": now()}
    write_json(path, result)
    return result


class Runner:
    def __init__(self, app, workspace, agent_id, directory=None):
        self.app, self.workspace, self.agent_id = app, workspace, agent_id
        self.root = app.root(workspace, agent_id, directory)
        self.adapter = None
        self.binding = None
        self.stop_event = threading.Event()
        self.renew_after_exit = False
        self.runtime_kind = None
        self.controller = None
        self.adapter_closed = False

    def _close_adapter(self):
        if self.adapter is not None and not self.adapter_closed:
            self.adapter.close()
            self.adapter_closed = True

    def status(self, **values):
        model_receipt = getattr(self.adapter, "model_receipt", None)
        if isinstance(model_receipt, dict):
            values["model_profile"] = model_receipt
        write_json(self.root / ".aw-local/status.json", {"pid": os.getpid(), "binding": self.binding,
                   "observed_at": now(), **values})

    def run(self):
        with locked(self.root / ".aw-local/runner.lock", wait=0):
            try:
                self._run_owned()
            except Exception as exc:
                self.status(state="failed", reason=str(exc), entry_automatically_released=False)
                raise
            finally:
                self._release_controller()
        transfer = read_json(self.root / ".aw-local/transfer.json")
        if transfer and transfer["old_binding"] == self.binding:
            from .transfer import advance
            advance(self.app, self.workspace, self.agent_id, str(self.root))
        elif self.renew_after_exit:
            result = start(self.app, self.workspace, self.agent_id, str(self.root), open_app=self.runtime_kind == "desktop")
            write_json(self.root / ".aw-local/renew-result.json", result)

    def _run_owned(self):
        app, workspace, aid = self.app, self.workspace, self.agent_id
        record = read_json(self.root / ".aw-local/entry.json")
        if not record:
            raise Error("No local entry; use relay/start before launching a runner.")
        self.binding = record["binding"]
        snap = app.store(workspace).snapshot()
        item = app.agent(workspace, aid, snap)
        if item["current"] != self.binding:
            raise Conflict("Local runner entry has been superseded.")
        entry = snap.json(f"bindings/{self.binding}.json")
        config = read_json(self.root / ".aw-local/runtime.json", record["config"])
        if config.get("kind", "manual") != entry["kind"]:
            raise Conflict("Configured Runtime changed; handoff is required before changing the active Runtime.")
        if entry["phase"] == "stopping":
            raise Conflict("Handoff is already in progress; do not restart its execution components.")
        if entry.get("controller"):
            raise Conflict("Another runner owns this binding. A crashed controller is not automatically taken over.")
        if entry["kind"] in model_profiles.CODEX_KINDS:
            model_profiles.migrate(self.root)
            profile = model_profiles.adopted(self.root, self.binding, session=entry["session"])
            model_profiles.pin(self.root, self.binding, profile)
        controller = uid("r")
        path = f"bindings/{self.binding}.json"
        app.store(workspace).change("main", {path: encode({**entry, "controller": controller})},
            {path: snap.entries[path], f"agents/{aid}.json": snap.entries[f"agents/{aid}.json"]}, "Claim binding runner")
        self.controller = controller
        self.runtime_kind = entry["kind"]
        failures, next_poll, bridges = 0, 0.0, None
        self.status(state="connecting", kind=entry["kind"])
        try:
            if entry["kind"] == "manual":
                raise Unavailable("Manual entry has no push runner. Use receive in the actual session.")
            if entry["kind"] == "codex":
                launch_path = self.root / ".aw-local/launch.json"
                launch = read_json(launch_path, {})
                if entry["session"] is None and launch.get("attempted"):
                    raise Unavailable("A native session creation was already attempted. Inspect its result; it is not automatically repeated.")
                self.adapter = Codex(app, workspace, aid, self.binding, self.root, config, entry["session"])
                if entry["session"] is None:
                    app.bind(workspace, aid, self.binding, self.adapter.session, str(self.root))
                    queue_input(app, workspace, aid, entry_prompt(app, workspace, aid, self.binding, self.root),
                                purpose="initial", directory=str(self.root), request_id="boot-" + self.binding)
            elif entry["kind"] in SDK_TYPES:
                launch_path = self.root / ".aw-local/launch.json"
                if entry["session"] is None and read_json(launch_path, {}).get("attempted"):
                    raise Unavailable("The original native launch is unresolved; do not repeat it.")
                if entry["session"] is None:
                    write_json(launch_path, {"binding": self.binding, "attempted": True})
                self.adapter = NativeSDK(app, workspace, aid, self.binding, self.root, config, entry["session"])
                self.adapter.connect()
                if entry["session"] is None:
                    self.adapter.bootstrap(entry_prompt(app, workspace, aid, self.binding, self.root))
            else:
                self.adapter = Desktop(self.root, config, entry["session"])
                if entry["session"] is None:
                    self.adapter.create(self.binding)
                    app.bind(workspace, aid, self.binding, self.adapter.session, str(self.root))
                    queue_input(app, workspace, aid, entry_prompt(app, workspace, aid, self.binding, self.root),
                                purpose="initial", directory=str(self.root), request_id="boot-" + self.binding)
                entry = app.store(workspace).snapshot().json(f"bindings/{self.binding}.json")
            from .bridges import BridgeManager
            from .transfer import persist_completion
            bridges = BridgeManager(app, workspace, aid, self.binding, self.root)
            self.status(state="running", kind=entry["kind"], session=self.adapter.session)
            while not self.stop_event.wait(0.5):
                snap = app.store(workspace).snapshot()
                agent = app.agent(workspace, aid, snap)
                if agent["current"] != self.binding:
                    break
                current = snap.json(f"bindings/{self.binding}.json")
                if entry["kind"] in SDK_TYPES and self.adapter.status() == "unknown":
                    raise Unavailable("Native SDK is disconnected; inspect the original input before recovery.")
                if current["phase"] == "stopping":
                    bridges.stop_all()
                    self.status(state="handoff_waiting_idle", session=self.adapter.session)
                    if self.adapter.status() == "idle":
                        if isinstance(self.adapter, Desktop):
                            self._complete_inputs(stopping_checkpoint=current["checkpoint"])
                        # Desktop retains its idle chat; its platform authority is released below.
                        # Other adapters close the managed writer before releasing ownership.
                        self._close_adapter()
                        # Closing drains native events; idle alone is not input success.
                        if not isinstance(self.adapter, Desktop):
                            self._complete_inputs(stopping_checkpoint=current["checkpoint"])
                        persist_completion(self.root, current)
                        result = app.finish_stop(workspace, aid, self.binding, observed_idle=True)
                        self.status(state="released", handoff=result["id"])
                        break
                    continue
                if read_json(self.root / ".aw-local/control.json", {}).get("stop") == self.binding:
                    self.status(state="monitor_stopped", entry_still_owned=True)
                    break
                try:
                    handoff_requested = read_json(self.root / ".aw-local/control.json", {}).get("handoff") == self.binding
                    if handoff_requested:
                        bridges.stop_all()
                    else:
                        bridges.tick()
                    records = self._read_inputs()
                    self._complete_inputs(records)
                    persist_completion(self.root, current)
                    self._inputs(records)
                    setting = read_json(self.root / ".aw-local/watch.json", {"enabled": False})
                    if not handoff_requested and setting.get("enabled") and setting.get("binding") == self.binding and time.monotonic() >= next_poll:
                        result = Messages(app).poll(workspace, aid, self.binding, adapter=self.adapter, directory=str(self.root))
                        self.status(state="running", kind=entry["kind"], session=self.adapter.session, poll=result)
                        next_poll = time.monotonic() + setting.get("interval", 5)
                    failures = 0
                except Conflict:
                    # Only an observed ownership transition is a reason to continue the loop.
                    latest = app.store(workspace).snapshot()
                    owner = app.agent(workspace, aid, latest)
                    if owner["current"] != self.binding:
                        break
                    if latest.json(f"bindings/{self.binding}.json")["phase"] == "stopping":
                        continue
                    raise
                except (Unavailable, OSError) as exc:
                    failures += 1
                    self.status(state="connection_failed", reason=str(exc), attempts=failures)
                    if entry["kind"] != "desktop" or failures >= 5:
                        break
                    if self.stop_event.wait(min(2 **failures, 30)):
                        break
                    latest = app.store(workspace).snapshot()
                    owner = app.agent(workspace, aid, latest)
                    current = latest.json(f"bindings/{self.binding}.json")
                    if owner["current"] != self.binding or current["phase"] != "active":
                        break
                    self.adapter.close()
                    config = read_json(self.root / ".aw-local/runtime.json", config)
                    self.adapter = self._reconnect_desktop(config, entry["session"], failures)
                    if self.adapter is None:
                        break
        finally:
            if bridges:
                bridges.stop_all()
            self._close_adapter()
        renew = read_json(self.root / ".aw-local/renew.json", {})
        if renew.get("requested") and renew.get("binding") == self.binding and app.agent(workspace, aid)["current"] is None:
            write_json(self.root / ".aw-local/renew.json", {**renew, "requested": False})
            # The old model is no longer involved. A new local runner owns the next entry.
            self.renew_after_exit = True

    def _release_controller(self):
        if self.controller is None:
            return
        if self.adapter is not None and not self.adapter_closed:
            self.status(state="native_stop_unconfirmed", entry_automatically_released=False)
            return
        store = self.app.store(self.workspace)
        snap = store.snapshot()
        path = f"bindings/{self.binding}.json"
        entry = snap.json(path)
        if entry.get("controller") == self.controller:
            entry.pop("controller")
            store.change("main", {path: encode(entry)}, {path: snap.entries[path]}, "Release binding runner")
        self.controller = None

    def _reconnect_desktop(self, config, session, attempts):
        while attempts < 5:
            latest = self.app.store(self.workspace).snapshot()
            owner = self.app.agent(self.workspace, self.agent_id, latest)
            entry = latest.json(f"bindings/{self.binding}.json")
            control = read_json(self.root / ".aw-local/control.json", {})
            stopped = control.get("stop") == self.binding or control.get("handoff") == self.binding
            if stopped or owner["current"] != self.binding or entry["phase"] != "active":
                return None
            try:
                return Desktop(self.root, config, session)
            except (Unavailable, OSError) as exc:
                attempts += 1
                self.status(state="connection_failed", reason=str(exc), attempts=attempts)
                if attempts >= 5 or self.stop_event.wait(min(2 ** attempts, 30)):
                    return None
        return None

    def _read_inputs(self):
        records = []
        for path in (self.root / ".aw-local/inputs").glob("*.json"):
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
                    write_json(self.root / "records" / self.binding / "desktop-turns" / (slug(turn_id) + ".json"),
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
                point = self.app.checkpoint_show(self.workspace, self.agent_id, stopping_checkpoint)
            else:
                point = self.app.checkpoint(self.workspace, self.agent_id,
                    "本会话进入轮次已结束。实际职责与资料以此快照中的文件为准。",
                    content=("Desktop 轮次元数据按记录段保存，正文仍在原聊天；不宣称执行了未安排的产品任务。"
                             if isinstance(self.adapter, Desktop) else
                             "原生事件按记录段保存；此记录不宣称执行了任何未安排的产品任务。"),
                    binding=self.binding, directory=str(self.root), checkpoint_id="initial-" + self.binding)
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
            self.app.require_binding(self.workspace, self.agent_id, self.binding)
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
                    prompt = "平台有一条待处理输入。先执行以下参数数组对应的命令，读取返回 text 后按其内容工作；already_received 时不要重复执行。\n" + json.dumps(args, ensure_ascii=False)
                else:
                    prompt = item["text"]
                response = self.adapter.notify(prompt, item["delivery"])
            except Exception as exc:
                with locked(path.with_suffix(".lock")):
                    latest = read_json(path) if isinstance(self.adapter, Desktop) else item
                    received = latest.get("result", {}).get("turn", {}).get("id")
                    latest.update(state="submitted" if received else "outcome_unknown", error=str(exc))
                    model_receipt = getattr(self.adapter, "model_receipt", None)
                    if isinstance(model_receipt, dict):
                        latest["model_profile"] = model_receipt
                    write_json(path, latest)
                raise
            with locked(path.with_suffix(".lock")):
                latest = read_json(path) if isinstance(self.adapter, Desktop) else item
                latest.update(state="submitted", result={**response, **latest.get("result", {})})
                model_receipt = getattr(self.adapter, "model_receipt", None)
                if isinstance(model_receipt, dict):
                    latest["model_profile"] = model_receipt
                write_json(path, latest)
            return
