"""Synchronous Runner boundary around the native, stateful Python SDK clients.

One thread owns connect/disconnect in one async task. The SDK, not this module,
implements reasoning, tools and conversation persistence. No terminal scraping.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict
import importlib
import json
import os
import queue
import sys
import threading

from .util import Conflict, Error, Unavailable, locked, now, uid, write_json


SDK_TYPES = {
    "claude": ("claude_agent_sdk", "ClaudeSDKClient", "ClaudeAgentOptions", "cli_path"),
    "codebuddy": ("codebuddy_agent_sdk", "CodeBuddySDKClient", "CodeBuddyAgentOptions", "codebuddy_code_path"),
}


def sdk_options(config, app, workspace, agent_id, binding, root, session=None):
    """Secrets are read at launch and passed only to the child process."""
    module, client_name, options_name, executable_key = SDK_TYPES[config["kind"]]
    try:
        sdk = importlib.import_module(module)
    except ImportError as exc:
        raise Unavailable(f"Install AgentWorkspace's {config['kind']} extra before launching this entry.") from exc
    env = {"AW_HOME": str(app.home), "AW_WORKSPACE": workspace, "AW_AGENT": agent_id, "AW_BINDING": binding}
    provider = config.get("provider", {})
    if provider.get("base_url"):
        # Do not send an inherited official-account token to a different destination.
        keys = (("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN")
                if config["kind"] == "claude" else ("CODEBUDDY_API_KEY", "CODEBUDDY_AUTH_TOKEN"))
        env.update({key: "" for key in keys})
        env["ANTHROPIC_BASE_URL" if config["kind"] == "claude" else "CODEBUDDY_BASE_URL"] = provider["base_url"]
    if provider.get("env_key"):
        secret = os.environ.get(provider["env_key"])
        if not secret:
            raise Unavailable(f"Credential environment variable is missing: {provider['env_key']}")
        variable = "ANTHROPIC_AUTH_TOKEN" if config["kind"] == "claude" else "CODEBUDDY_API_KEY"
        env[variable] = secret
        if config["kind"] == "claude":
            env["ANTHROPIC_API_KEY"] = ""
    # No automatic user/project MCP configuration or broad native permissions.
    options = {"cwd": str(root), executable_key: config["executable"], "env": env,
               "setting_sources": [], "model": config.get("model"), "effort": config.get("effort"),
               "permission_mode": "default", "allowed_tools": config.get("allowed_tools", []),
               "mcp_servers": {"aw": {"type": "stdio", "command": sys.executable,
                   "args": ["-m", "agent_workspace", "--home", str(app.home), "mcp"],
                   "env": {key: value for key, value in env.items() if key.startswith("AW_")}}}}
    if session:
        options["resume"] = session
    return sdk, getattr(sdk, client_name), getattr(sdk, options_name), options


class NativeSDK:
    # Streaming input is not evidence of native expected-turn steering semantics.
    supports_insert = False

    def __init__(self, app, workspace, agent_id, binding, root, config, session=None):
        self.app, self.workspace, self.agent_id = app, workspace, agent_id
        self.binding, self.root, self.session = binding, root, session
        self.sdk, self.client_type, self.options_type, self.options = sdk_options(
            config, app, workspace, agent_id, binding, root, session)
        self.completed = queue.Queue()
        self.record = root / "records" / binding / "runtime.jsonl"
        self.record.parent.mkdir(parents=True, exist_ok=True)
        self.ready, self.observed = threading.Event(), threading.Event()
        self.guard = threading.Lock()
        self.failure, self.submission = None, None
        self.busy, self.closing, self.stopped = False, False, True
        # Recover terminal facts only; never replay an input to reconstruct them.
        if self.record.exists():
            for line in self.record.read_text(encoding="utf-8").splitlines():
                item = json.loads(line)
                if item.get("completion"):
                    self.completed.put(item["completion"])
        self.thread = threading.Thread(target=self._thread_main, daemon=True)

    def connect(self):
        self.stopped = False
        self.thread.start()
        if not self.ready.wait(30):
            self.close()
            raise Unavailable("Native SDK connection timed out; inspect the original launch.")
        if self.failure:
            self.close()
            raise Unavailable(self.failure)

    async def _tool_guard(self, data, tool_use_id, context):
        if self.session is None:
            await asyncio.to_thread(self.observed.wait, 10)
        try:
            await asyncio.to_thread(self.app.require_binding, self.workspace, self.agent_id, self.binding)
        except Error:
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                    "permissionDecisionReason": "This entry is not active; no native tool may run."}}
        return {}

    async def _permission(self, tool_name, arguments, context):
        # Only the explicitly supplied platform MCP server is accepted here.
        if tool_name == "mcp__aw__aw_execute":
            return self.sdk.PermissionResultAllow(updated_input=arguments)
        return self.sdk.PermissionResultDeny(message="Native approval requires the user; configure allowed tools explicitly.")

    def _thread_main(self):
        try:
            asyncio.run(self._serve())
        except Exception as exc:
            self.failure = f"Native SDK failed ({type(exc).__name__}); inspect the local native event record."
        finally:
            self.ready.set()
            self.observed.set()

    async def _serve(self):
        self.loop = asyncio.get_running_loop()
        self.stop = asyncio.Event()
        self.options["hooks"] = {"PreToolUse": [self.sdk.HookMatcher(hooks=[self._tool_guard])]}
        self.options["can_use_tool"] = self._permission
        self.client = self.client_type(self.options_type(**self.options))
        receiver = None
        try:
            await self.client.connect()
            receiver = asyncio.create_task(self._receive())
            self.ready.set()
            await self.stop.wait()
        finally:
            if receiver:
                receiver.cancel()
                await asyncio.gather(receiver, return_exceptions=True)
            # Claude's anyio task group must be closed in the task which opened it.
            await self.client.disconnect()
            self.stopped = True

    async def _receive(self):
        try:
            async for message in self.client.receive_messages():
                data = asdict(message)
                actual = data.get("session_id") or data.get("data", {}).get("session_id")
                completion = None
                with self.guard:
                    submission = self.submission
                if isinstance(message, self.sdk.ResultMessage) and submission:
                    completion = {"id": submission, "status": "failed" if message.is_error else "completed"}
                item = {"observed_at": now(), "native_type": type(message).__name__,
                        "local_submission_id": submission, "event": data}
                if completion:
                    item["completion"] = completion
                with locked(self.root / ".aw-local/records.lock"):
                    with self.record.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(item, ensure_ascii=False) + "\n")
                        stream.flush()
                        if completion:
                            os.fsync(stream.fileno())
                if actual:
                    if self.session and self.session != actual:
                        raise Conflict("Native SDK resumed a different session.")
                    if not self.session:
                        # A requested ID is not a binding. Only the native event confirms it.
                        await asyncio.to_thread(self.app.bind, self.workspace, self.agent_id,
                                                self.binding, actual, str(self.root))
                        self.session = actual
                    self.observed.set()
                if completion:
                    with self.guard:
                        self.submission, self.busy = None, False
                    self.completed.put(completion)
            if not self.closing:
                raise Unavailable("Native event stream closed.")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.failure = f"Native event stream failed ({type(exc).__name__}); execution outcome may be unknown."
            self.observed.set()
            self.stop.set()

    def status(self):
        if self.failure or not self.thread.is_alive():
            return "unknown"
        with self.guard:
            return "busy" if self.busy else "idle"

    def notify(self, prompt, delivery):
        if delivery == "insert":
            raise Error("This SDK entry does not yet support verified insert/steer; use normal delivery.")
        with self.guard:
            if self.failure or not self.thread.is_alive():
                raise Unavailable(self.failure or "Native SDK is disconnected.")
            if self.busy:
                raise Conflict("Native turn is busy; normal input must wait.")
            self.busy = True
            self.submission = uid("s")
            submission = self.submission
        try:
            future = asyncio.run_coroutine_threadsafe(self.client.query(prompt, session_id=self.session or "default"), self.loop)
            future.result(timeout=30)
        except Exception as exc:
            # Do not cancel/retry an externally dispatched request after timeout.
            self.failure = f"Native submission outcome unknown ({type(exc).__name__})."
            raise Unavailable(self.failure) from exc
        return {"turn": {"id": submission}, "id_source": "local_submission", "session": self.session}

    def bootstrap(self, prompt):
        path = self.root / ".aw-local/inputs" / f"boot-{self.binding}.json"
        item = {"id": path.stem, "binding": self.binding, "text": prompt, "delivery": "normal",
                "purpose": "initial", "state": "dispatching", "sequence": 0, "created_at": now()}
        write_json(path, item)
        response = self.notify(prompt, "normal")
        item.update(state="submitted", result=response)
        write_json(path, item)
        if not self.observed.wait(30) or not self.session or self.failure:
            raise Unavailable(self.failure or "No native session confirmation; do not repeat initialization.")

    def close(self):
        self.closing = True
        if hasattr(self, "loop") and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.stop.set)
        if self.thread.ident is None:
            return
        self.thread.join(timeout=10)
        if self.thread.is_alive() or not self.stopped:
            raise Unavailable("Native SDK did not stop; keep the binding controller until its process is confirmed stopped.")
