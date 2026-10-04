"""Launch ordinary native CLI conversations, without a Workspace or an Agent loop.

The local receipt describes a launch, never a verified native session or a Binding.
Conversation history, interactive permissions and continuation remain with the CLI.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from .harness_config import codex_config, sdk_config
from .native_sdk import sdk_environment
from .util import Conflict, Error, Unavailable, locked, now, read_json, slug, uid, write_json


_IDENTITY_ENV = {"AW_HOME", "AW_WORKSPACE", "AW_AGENT", "AW_BINDING",
                 "CODEX_THREAD_ID", "CODEX_APP_TOOLS_PIPE_PATH"}


def _directory(value):
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise Error("Choose an existing work directory.")
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_dir():
        raise Error("The work directory must be an existing folder; it will not be created or copied.")
    for parent in (path, *path.parents):
        if (parent / ".aw-local/context.json").exists():
            raise Conflict("This is an Agent instance directory; use agent start/relay, not an ordinary session.")
    return path


def _path(app, request_id):
    return app.home / "ordinary-sessions" / (slug(request_id) + ".json")


def _invocation(profile, prompt):
    if profile["kind"] == "codex":
        argv = profile["command"][:-1] + ["--ask-for-approval", "on-request", "--sandbox", "workspace-write"]
    else:
        argv = [profile["executable"], "--permission-mode", "default"]
        for option in ("model", "effort"):
            if profile.get(option):
                argv.extend(["--" + option, profile[option]])
    # Batch wrappers implicitly invoke cmd.exe; never send arbitrary task text to it.
    if Path(argv[0]).suffix.lower() in (".cmd", ".bat"):
        raise Error("Choose the native executable instead of a .cmd/.bat wrapper for this launcher.")
    if prompt:
        argv.extend(["--", prompt])
    return argv


def _environment(profile):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AW_") and k not in _IDENTITY_ENV}
    if profile["kind"] == "codex":
        key = profile.get("credential_env")
        if key:
            if not os.environ.get(key):
                raise Unavailable(f"Credential environment variable is missing in this terminal: {key}")
            env[key] = os.environ[key]
    else:
        env.update(sdk_environment(profile))
    return env


def prepare(app, kind, directory, model="", effort="", base_url="", env_key="", executable=None,
            prompt="", request_id=None, allow_http=False):
    """Save an immutable request. No Git, model, terminal or native session is started."""
    root = _directory(directory)
    if not isinstance(prompt, str) or "\0" in prompt or len(prompt) > 16000:
        raise Error("Use a task of at most 16000 characters, without NUL bytes.")
    if env_key in _IDENTITY_ENV:
        raise Error("A platform identity variable cannot be used as a model credential.")
    values = dict(model=model, effort=effort, base_url=base_url, env_key=env_key,
                  executable=executable, allow_http=allow_http)
    profile = codex_config(**values) if kind == "codex" else sdk_config(kind, **values)
    _invocation(profile, prompt)
    request_id = slug(request_id or uid("session-"))
    path = _path(app, request_id)
    spec = {"directory": str(root), "profile": profile, "prompt": prompt}
    with locked(path.with_suffix(".lock")):
        existing = read_json(path)
        if existing:
            if existing["spec"] != spec:
                raise Conflict("This launch ID already has different settings; continue it or explicitly start a new request.")
        else:
            write_json(path, {"id": request_id, "spec": spec, "state": "prepared", "created_at": now()})
    return show(app, request_id)


def show(app, request_id):
    record = read_json(_path(app, request_id))
    if record is None:
        raise Error("Ordinary session launch request not found.")
    argv = [sys.executable, "-m", "agent_workspace", "--home", str(app.home), "session", "run", request_id]
    command = ("& " + " ".join("'" + arg.replace("'", "''") + "'" for arg in argv)
               if os.name == "nt" else shlex.join(argv))
    return {**record, "run_argv": argv, "run_command": command,
            "native_session": "not_observed", "workspace_created": False,
            "hint": "启动记录不是会话 ID 或就绪证明。请在原生终端完成登录/信任确认和继续对话；历史由 Harness 保存。"}


def _terminal(argv):
    """OS terminal launch only. No task text or secrets in shell/AppleScript input."""
    if os.name == "nt":
        return argv, {"creationflags": subprocess.CREATE_NEW_CONSOLE}
    if sys.platform == "darwin":
        # Terminal's shell resolves credentials itself; never serialize keys into AppleScript.
        command = shlex.join(argv)
        script = 'tell application "Terminal"\n do script ' + json.dumps(command, ensure_ascii=False) + '\n activate\nend tell'
        return ["/usr/bin/osascript", "-e", script], {}
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise Unavailable("没有图形终端；在已配置凭据的终端执行下方原请求命令，无需自行切换目录。")
    for name, option in (("xterm", "-e"), ("gnome-terminal", "--"), ("konsole", "-e")):
        executable = shutil.which(name)
        if executable:
            return [executable, option, *argv], {}
    raise Unavailable("未发现支持的终端；执行原请求命令，或自行安装并选择可用运行环境。")


def open_terminal(app, request_id):
    path = _path(app, request_id)
    with locked(path.with_suffix(".lock")):
        record = read_json(path)
        if record is None:
            raise Error("Prepare a launch request first.")
        if record["state"] != "prepared":
            return show(app, request_id)  # Never reopen an already dispatched/unknown native session.
        _directory(record["spec"]["directory"])
        _environment(record["spec"]["profile"])
        try:
            argv, options = _terminal(show(app, request_id)["run_argv"])
        except Unavailable as exc:
            return {**show(app, request_id), "terminal_available": False, "hint": str(exc)}
        record.update(state="terminal_requested", requested_at=now())
        write_json(path, record)
        try:
            subprocess.Popen(argv, cwd=app.home, **options)
        except OSError as exc:
            record.update(state="terminal_failed", error=type(exc).__name__)
            write_json(path, record)
            return {**show(app, request_id), "hint": "终端未能启动。请执行原请求命令；不重新创建请求。"}
    return show(app, request_id)


def run(app, request_id):
    """Called in a real terminal, never via the HTTP/MCP dispatcher."""
    if not sys.stdin.isatty():
        raise Unavailable("This ordinary session needs an interactive terminal; no model was started.")
    path = _path(app, request_id)
    # Held for the native process lifetime. No second native process for a repeated request.
    with locked(path.with_suffix(".run.lock"), wait=0):
        with locked(path.with_suffix(".lock")):
            record = read_json(path)
            if record is None:
                raise Error("Prepare a launch request first.")
            if record["state"] not in ("prepared", "terminal_requested", "terminal_failed", "preflight_failed"):
                raise Conflict("This request was already attempted. Continue the original conversation in the Harness; do not replay it.")
            try:
                spec = record["spec"]
                directory = _directory(spec["directory"])
                argv = _invocation(spec["profile"], spec["prompt"])
                env = _environment(spec["profile"])
            except (Error, OSError) as exc:
                record.update(state="preflight_failed", error=type(exc).__name__)
                write_json(path, record)
                raise
            record.update(state="starting_native", attempted_at=now())
            write_json(path, record)
        try:
            process = subprocess.Popen(argv, cwd=directory, env=env)
            record.update(state="native_running", pid=process.pid)
            write_json(path, record)
            returncode = process.wait()
            record.update(state="native_exited", returncode=returncode, exited_at=now())
            write_json(path, record)
            return returncode
        except BaseException:
            # A wrapper error or lost terminal cannot prove what the native process did.
            record.update(state="outcome_unknown")
            write_json(path, record)
            raise
