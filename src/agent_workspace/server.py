from __future__ import annotations

import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser

from .commands import command_map, execute
from .runtime import TOOL_SCHEMA
from .util import Error, now


def build_state(app):
    """Build the authenticated Workbench projection from shared and local facts.

    The projection labels its source revision and local observation instead of
    inventing a global online/offline state. It remains read-only; commands still
    re-check authorization, object revisions and Binding conditions.
    """
    from .maintenance import installation_id

    observed_at = now()
    installation = installation_id(app)
    result = {
        "installation_id": installation,
        "observed_at": observed_at,
        "default_instance_root": str((app.home / "instances").resolve()),
        "workspaces": [],
        "agents": [],
        "errors": [],
    }
    for access in app.workspace_list():
        alias = access["alias"]
        workspace = {**access, "observed_at": observed_at}
        try:
            shared = app.workspace_show(alias)
            workspace.update(
                snapshot_revision=shared["revision"],
                locator=shared.get("locator", access.get("locator")),
                caretakers=shared.get("caretakers", {}),
                projects=shared.get("projects", {}),
                friends=shared.get("friends", {}),
            )
        except (Error, ValueError, OSError, KeyError) as exc:
            workspace["unknown_reason"] = "workspace_read_failed"
            result["errors"].append({"workspace": alias, "error": str(exc)})
            result["workspaces"].append(workspace)
            continue
        result["workspaces"].append(workspace)
        try:
            agents = app.agents(alias)
        except (Error, ValueError, OSError, KeyError) as exc:
            result["errors"].append({"workspace": alias, "error": str(exc)})
            continue
        for agent in agents:
            try:
                detail = app.show(alias, agent["id"])
                directories = list(detail.get("directories", []))
                detail.update(
                    directory=directories[0] if directories else None,
                    local_ready=bool(directories),
                    observed_at=observed_at,
                    snapshot_revision=workspace.get("snapshot_revision"),
                    observation_source={
                        "installation_id": installation,
                        "kind": "local_registry_and_runtime",
                    },
                )
            except (Error, ValueError, OSError, KeyError) as exc:
                # Keep the known identity, not invented liveness or ownership.
                error = f"Instance observation failed ({type(exc).__name__}); use workspace doctor."
                detail = {
                    **agent,
                    "directory": None,
                    "directories": [],
                    "local_ready": False,
                    "observed_at": observed_at,
                    "snapshot_revision": workspace.get("snapshot_revision"),
                    "unknown_reason": "instance_observation_failed",
                    "observation_error": error,
                }
                result["errors"].append({"workspace": alias, "agent": agent["id"],
                                         "error": f"{agent['id']}: {error}"})
            result["agents"].append({"workspace": alias, **detail})
    return result


def make_server(app, port=8765, token=None):
    token = token or secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        timeout = 30  # Accepted but incomplete requests must not block orderly shutdown forever.

        def log_message(self, fmt, *args):
            pass  # Never log bearer tokens or request bodies.

        def reply(self, status, value, content_type="application/json; charset=utf-8"):
            data = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(data)

        def authorized(self):
            expected_host = f"127.0.0.1:{self.server.server_port}"
            allowed = {expected_host, f"localhost:{self.server.server_port}"}
            if self.headers.get("Host", "") not in allowed:
                self.reply(403, {"error": "Invalid local host."})
                return False
            origin = self.headers.get("Origin")
            if origin and urllib.parse.urlsplit(origin).netloc not in allowed:
                self.reply(403, {"error": "Cross-origin control is not allowed."})
                return False
            supplied = self.headers.get("Authorization", "").removeprefix("Bearer ")
            if not hmac.compare_digest(supplied, token):
                self.reply(401, {"error": "A local bearer token is required."})
                return False
            if self.server.stopping.is_set() and self.path != "/api/shutdown":
                self.reply(503, {"error": "Workbench is stopping; do not start another operation."})
                return False
            return True

        def do_GET(self):
            if self.path == "/capabilities":
                # Public, static package documentation only; no instance or account data.
                guide = (files("agent_workspace") / "resources" / "prompts" / "capabilities.md").read_bytes()
                self.reply(200, guide, "text/plain; charset=utf-8")
                return
            if self.path in ("/", "/setup", "/sessions"):
                if self.path == "/sessions":
                    page = (files("agent_workspace") / "resources/sessions.html").read_bytes()
                    self.reply(200, page, "text/html; charset=utf-8")
                    return
                name = "setup.html" if self.path == "/setup" or not app.workspace_list() else "index.html"
                page = (files("agent_workspace") / "resources" / name).read_bytes()
                self.reply(200, page, "text/html; charset=utf-8")
                return
            if not self.authorized():
                return
            try:
                if self.path == "/api/commands":
                    result = list(command_map(app))
                elif self.path == "/api/state":
                    result = build_state(app)
                else:
                    self.reply(404, {"error": "Not found"})
                    return
                self.reply(200, {"ok": True, "result": result})
            except (Error, ValueError, OSError) as exc:
                self.reply(400, {"ok": False, "error": str(exc)})

        def do_POST(self):
            if not self.authorized():
                return
            if self.path == "/api/shutdown":
                self.server.stopping.set()
                self.reply(200, {"ok": True, "result": {"shutdown_requested": True, "agent_bindings_released": False}})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if self.path != "/api/execute":
                self.reply(404, {"error": "Not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 2 * 1024 * 1024 or not self.headers.get("Content-Type", "").startswith("application/json"):
                    raise Error("Send a JSON request of at most 2 MiB.")
                payload = json.loads(self.rfile.read(length))
                result = execute(app, payload["command"], payload.get("arguments", {}))
                self.reply(200, {"ok": True, "result": result})
            except (Error, ValueError, OSError, KeyError, TypeError) as exc:
                self.reply(409 if getattr(exc, "code", "") == "conflict" else 400,
                           {"ok": False, "code": getattr(exc, "code", "invalid_input"), "error": str(exc)})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.control_token = token
    server.daemon_threads = False
    server.stopping = threading.Event()
    return server


def serve(app, port=8765, open_browser=False, setup=False):
    server = make_server(app, port)
    path = "/setup" if setup else "/"
    url = f"http://127.0.0.1:{server.server_port}{path}#token={server.control_token}"
    print("本机工作台（地址包含控制凭据，请勿分享）：\n" + url, flush=True)
    if open_browser:
        webbrowser.open(url)
    from .maintenance import run
    stop = threading.Event()
    worker = threading.Thread(target=run, args=(app, stop), name="aw-maintenance", daemon=False)
    worker.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass  # Ctrl+C is an orderly service stop, not an Agent release.
    finally:
        stop.set()
        server.server_close()  # Drain accepted HTTP handlers before stopping the worker.
        worker.join()  # Its external operations have their own bounded timeouts.


def mcp(app, actor=None):
    if actor is None and os.environ.get("AW_AGENT") and os.environ.get("AW_BINDING"):
        actor = (os.environ["AW_WORKSPACE"], os.environ["AW_AGENT"], os.environ["AW_BINDING"])
    for line in sys.stdin:
        try:
            message = json.loads(line)
            identifier, method, params = message.get("id"), message.get("method"), message.get("params", {})
            if identifier is None:
                continue
            if method == "initialize":
                result = {"protocolVersion": params.get("protocolVersion", "2024-11-05"),
                          "capabilities": {"tools": {}}, "serverInfo": {"name": "agent-workspace", "version": "0.1.0a1"}}
            elif method == "tools/list":
                result = {"tools": [{"name": "aw_execute", "description": "Agent Workspace operations. Commands: " + ", ".join(command_map(app)),
                                     "inputSchema": TOOL_SCHEMA}]}
            elif method == "tools/call":
                if params["name"] != "aw_execute":
                    raise Error("Unknown tool")
                values = params.get("arguments", {})
                output = execute(app, values["command"], values.get("arguments", {}), actor=actor)
                result = {"content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False)}]}
            elif method == "ping":
                result = {}
            else:
                raise Error("Unsupported MCP method")
            response = {"jsonrpc": "2.0", "id": identifier, "result": result}
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": locals().get("identifier"), "error": {"code": -32603, "message": str(exc)}}
        print(json.dumps(response, ensure_ascii=False), flush=True)
