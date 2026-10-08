"""Use native Harness configuration; never edit the user's global configuration.

Codex uses native argv; Claude/CodeBuddy use SDK options. Desktop is not emulated.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import urllib.parse

from . import __version__
from .rpc import Rpc
from .util import Conflict, Error, locked


def _check_http_consent(base_url, allow_http):
    """Validate the shared model URL boundary; consent is per explicit profile."""
    if not isinstance(allow_http, bool):
        raise Error("allow_http must be a boolean.")
    if not isinstance(base_url, str):
        raise Error("Use a model service URL string.")
    if not base_url:
        return
    try:
        url = urllib.parse.urlsplit(base_url)
        port = url.port
    except ValueError as exc:
        raise Error("Invalid model service URL or port.") from exc
    if (url.scheme not in ("https", "http") or not url.hostname or url.username is not None
            or url.password is not None or url.query or url.fragment or port == 0
            or any(c.isspace() or ord(c) < 32 or c in '\x7f"&|<>^%!' for c in base_url)):
        raise Error("Use an HTTP(S) service URL without credentials or query parameters.")
    if (url.scheme == "http" and url.hostname not in ("localhost", "127.0.0.1", "::1")
            and not allow_http):
        raise Error("非本机 HTTP 会明文传输凭据和会话内容；仅在确认可信网络后使用 --allow-http / allow_http=true。")


def codex_config(model="", effort="", base_url="", env_key="", executable=None, *, allow_http=False):
    _check_http_consent(base_url, allow_http)
    for name, value in (("model", model), ("effort", effort), ("env_key", env_key)):
        pattern = r"[A-Za-z0-9_./:@+\[\]-]+" if name == "model" else r"[A-Za-z0-9_./:@+-]+"
        if not isinstance(value, str) or (value and not re.fullmatch(pattern, value)):
            raise Error(f"Invalid {name}; use a native identifier, not a command or credential.")
    if env_key and (not base_url or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env_key)):
        raise Error("An environment variable name requires a custom service URL.")
    command = executable or shutil.which("codex")
    if not command or not Path(command).is_file():
        raise Error("Codex CLI 未发现；请自行安装，或提供可执行文件的绝对路径。")
    command = str(Path(command).resolve())
    if any(c in command for c in '\r\n\0"&|<>^%!'):
        raise Error("Executable path contains unsupported shell characters.")
    overrides = {}
    if model:
        overrides["model"] = model
    if effort:
        overrides["model_reasoning_effort"] = effort
    if base_url:
        overrides["model_provider"] = "aw_custom"
        provider = {"name": "AgentWorkspace", "base_url": base_url, "wire_api": "responses",
                    "requires_openai_auth": False}
        if env_key:
            provider["env_key"] = env_key
        # Replace this provider table, rather than inherit headers from a global entry.
        overrides["model_providers.aw_custom"] = provider
    args = [command]
    for key, value in overrides.items():
        encoded = ("{" + ",".join(k + "=" + json.dumps(v) for k, v in value.items()) + "}"
                   if isinstance(value, dict) else json.dumps(value))
        args.extend(["-c", key + "=" + encoded])
    args.append("app-server")
    config = {"kind": "codex", "command": args, "sandbox": "workspace-write"}
    if model:
        config["model"] = model
    if env_key:
        config["credential_env"] = env_key
    if base_url:
        config["modelProvider"] = "aw_custom"
    if allow_http:
        config["allow_http"] = True
    return config


def inspect_codex(base_url="", env_key="", executable=None, *, allow_http=False):
    """Explicit metadata probe: no thread/start, turn/start, login or configuration write."""
    config = codex_config(base_url=base_url, env_key=env_key, executable=executable, allow_http=allow_http)
    if env_key and not os.environ.get(env_key):
        return {"state": "credential_missing", "env_key": env_key, "models": [], "model_invoked": False}
    with tempfile.TemporaryDirectory(prefix="aw-codex-probe-") as directory:
        rpc = None
        try:
            rpc = Rpc(config["command"], cwd=Path(directory), env=dict(os.environ))
            rpc.request("initialize", {"clientInfo": {"name": "agent_workspace_setup", "version": __version__}}, timeout=10)
            rpc.send({"method": "initialized", "params": {}})
            account = rpc.request("account/read", {"refreshToken": False}, timeout=10)
            auth = "configured_unverified" if account.get("account") else (
                "login_required" if account.get("requiresOpenaiAuth") else "provider_managed_unverified")
            if base_url:
                # Codex's built-in catalog is not evidence of a custom gateway's model list.
                return {"state": "connected", "authentication": auth, "models": [], "model_invoked": False,
                        "catalog": "custom_provider_unconfirmed", "hint": "自定义服务的模型 ID 与强度请按服务实际能力填写。"}
            models, cursor, seen = [], None, set()
            for _ in range(5):
                page = rpc.request("model/list", {"limit": 100, "cursor": cursor}, timeout=10)
                for item in page["data"]:
                    models.append({key: item[key] for key in ("id", "model", "displayName", "defaultReasoningEffort",
                                  "supportedReasoningEfforts", "isDefault") if key in item})
                cursor = page.get("nextCursor")
                if not cursor:
                    break
                if cursor in seen:
                    raise Error("Model catalog repeated a pagination cursor.")
                seen.add(cursor)
            return {"state": "connected", "authentication": auth, "models": models,
                    "catalog": "partial" if cursor else "reported_by_codex", "model_invoked": False}
        except (Error, OSError, ValueError, KeyError, TypeError):
            # Native error payloads may contain account details; do not expose them to the UI.
            return {"state": "capability_unconfirmed", "models": [], "model_invoked": False,
                    "hint": "无法确认当前 Codex 版本的接口或认证；请在本机完成配置后重试。"}
        finally:
            if rpc is not None:
                rpc.close()


def configure_codex(app, workspace, agent_id, model="", effort="", base_url="", env_key="", executable=None,
                    *, allow_http=False):
    config = codex_config(model, effort, base_url, env_key, executable, allow_http=allow_http)
    root = app.root(workspace, agent_id)
    # Lifecycle operations remain explicit. Saving a profile never starts a session.
    with locked(root / ".aw-local/runner.lock", wait=0):
        if app.agent(workspace, agent_id)["current"]:
            raise Conflict("先完成 handoff，再改变此实例的 Harness 或模型服务配置。")
        result = app.configure(workspace, agent_id, config)
    return {**result, "model_access": "unchecked", "effort_support": "unchecked",
            "credential_state": "missing" if env_key and not os.environ.get(env_key) else "not_validated",
            "sessions_started": False, "global_configuration_changed": False}


def sdk_config(kind, model="", effort="", base_url="", env_key="", executable=None, allowed_tools=None,
               *, allow_http=False):
    """Native SDK profiles are per instance. They never rewrite global settings."""
    _check_http_consent(base_url, allow_http)
    if kind not in ("claude", "codebuddy"):
        raise Error("Choose claude or codebuddy for a native SDK profile.")
    for field, value in (("model", model), ("effort", effort)):
        pattern = r"[A-Za-z0-9_./:@+\[\]-]+" if field == "model" else r"[A-Za-z0-9_./:@+-]+"
        if not isinstance(value, str) or (value and not re.fullmatch(pattern, value)):
            raise Error(f"Invalid native {field} identifier.")
    if env_key and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env_key):
        raise Error("Provide a credential environment variable name, not a key.")
    path = executable or shutil.which(kind)
    if not path or not Path(path).is_file():
        raise Error(f"{kind} CLI 未发现；请先自行安装。")
    if allowed_tools is not None and (not isinstance(allowed_tools, list) or
                                     not all(isinstance(t, str) and t for t in allowed_tools)):
        raise Error("allowed_tools must be an explicit array of native tool names.")
    config = {"kind": kind, "executable": str(Path(path).resolve()), "model": model or None,
              "effort": effort or None, "provider": {"base_url": base_url, "env_key": env_key},
              "allowed_tools": allowed_tools or []}
    if allow_http:
        config["allow_http"] = True
    return config


def configure_sdk(app, workspace, agent_id, kind, model="", effort="", base_url="", env_key="", executable=None,
                  allowed_tools=None, *, allow_http=False):
    config = sdk_config(kind, model, effort, base_url, env_key, executable, allowed_tools, allow_http=allow_http)
    root = app.root(workspace, agent_id)
    with locked(root / ".aw-local/runner.lock", wait=0):
        if app.agent(workspace, agent_id)["current"]:
            raise Conflict("Handoff before replacing an instance's runtime profile.")
        result = app.configure(workspace, agent_id, config)
    return {**result, "sessions_started": False, "model_access": "unchecked", "effort_support": "unchecked",
            "global_configuration_changed": False}


def inspect_sdk(kind, base_url="", env_key="", executable=None, *, allow_http=False):
    """Read native handshake metadata without sending a prompt or starting an Agent."""
    config = sdk_config(kind, base_url=base_url, env_key=env_key, executable=executable, allow_http=allow_http)
    result = {"state": "capability_unconfirmed", "models": [], "model_invoked": False}
    if env_key and not os.environ.get(env_key):
        return {**result, "state": "credential_missing", "env_key": env_key}
    if kind != "claude":
        return {**result, "catalog": "unsupported", "hint": "此 SDK 尚无已验证的模型目录查询接口，请按服务说明填写。"}
    try:
        from .native_sdk import sdk_environment
        sdk = importlib.import_module("claude_agent_sdk")
        with tempfile.TemporaryDirectory(prefix="aw-claude-probe-") as directory:
            options = sdk.ClaudeAgentOptions(cli_path=config["executable"], cwd=directory,
                setting_sources=[], tools=[], mcp_servers={}, env=sdk_environment(config))

            async def probe():
                async with asyncio.timeout(10):
                    async with sdk.ClaudeSDKClient(options=options) as client:
                        return await client.get_server_info()

            info = asyncio.run(probe())
        result.update(state="connected", authentication="configured_unverified" if info.get("account") else "unconfirmed")
        # Native built-in choices do not describe an arbitrary custom model service.
        if base_url or any(os.environ.get(key) for key in (
                "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")):
            return {**result, "catalog": "custom_provider_unconfirmed",
                    "hint": "自有或第三方服务的模型和强度请按实际能力填写，未使用内置目录。"}
        for model in info.get("models", [])[:500]:
            identifier = model["value"]
            result["models"].append({"id": identifier, "model": identifier,
                "displayName": model.get("displayName", identifier),
                "supportedReasoningEfforts": [{"reasoningEffort": effort}
                    for effort in model.get("supportedEffortLevels", [])]})
        result["catalog"] = "reported_by_claude" if "models" in info else "unconfirmed"
        return result
    except ImportError:
        return {"state": "sdk_missing", "models": [], "model_invoked": False,
                "hint": "请自行安装 AgentWorkspace 的 claude 可选依赖后重试。"}
    except Exception:
        # SDK diagnostics may contain account data or secrets. This is the external boundary.
        return {"state": "capability_unconfirmed", "models": [], "model_invoked": False,
                "hint": "无法确认当前 SDK/CLI 的元数据接口；没有发送模型输入或创建平台会话。"}
