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
            shared_snapshot = app.store(alias).snapshot()
            shared = app.workspace_show(alias, snapshot=shared_snapshot)
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
            agents = app.agents(alias, snapshot=shared_snapshot)
        except (Error, ValueError, OSError, KeyError) as exc:
            result["errors"].append({"workspace": alias, "error": str(exc)})
            continue
        for agent in agents:
            try:
                detail = app.show(alias, agent["id"], snapshot=shared_snapshot)
                directories = list(detail.get("directories", []))
                detail.update(
                    local_ready=bool(directories),
                    observed_at=observed_at,
                    snapshot_revision=workspace.get("snapshot_revision"),
                    observation_source={
                        "installation_id": installation,
                        "kind": "local_registry_and_runtime",
                    },
                )
                if detail.get("workers"):
                    worker_states = []
                    for worker in detail["workers"]:
                        scope = (dict(detail) if worker["id"] == detail.get("worker_id") else
                                 app.show(alias, agent["id"], snapshot=shared_snapshot, worker_id=worker["id"]))
                        scope.update(local_ready=bool(scope.get("directories")), observed_at=observed_at,
                                     snapshot_revision=workspace.get("snapshot_revision"),
                                     observation_source=detail["observation_source"])
                        worker_states.append(scope)
                    detail["worker_states"] = worker_states
                for scope in detail.get("worker_states", [detail]):
                    for copy in scope.get("copies", []):
                        if "observation_error" in copy:
                            result["errors"].append({"workspace": alias, "agent": agent["id"],
                                                     "worker": scope.get("worker_id"),
                                                     "directory": copy["directory"], "error": copy["observation_error"]})
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
            if getattr(self, "courier_origin", None):
                self.send_header("Access-Control-Allow-Origin", self.courier_origin)
                self.send_header("Vary", "Origin")
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

        def courier_id(self):
            prefix = "/api/web-courier/"
            if not self.path.startswith(prefix):
                return None
            from .util import slug
            try:
                return slug(self.path[len(prefix):])
            except Error:
                return None

        def courier_host(self):
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host", "") not in allowed:
                self.reply(403, {"error": "Invalid local host."})
                return False
            if self.server.stopping.is_set():
                self.reply(503, {"error": "Workbench is stopping."})
                return False
            return True

        def do_OPTIONS(self):
            self.courier_origin = None
            connection_id = self.courier_id()
            if connection_id is None or not self.courier_host():
                if connection_id is None:
                    self.reply(404, {"error": "Not found"})
                return
            from . import web_courier
            try:
                origin = web_courier.preflight(app, connection_id, self.headers.get("Origin"))
                if self.headers.get("Access-Control-Request-Method") != "POST":
                    raise Error("Web Courier only accepts POST.")
                requested = {part.strip().lower() for part in self.headers.get("Access-Control-Request-Headers", "").split(",") if part.strip()}
                if not requested.issubset({"authorization", "content-type"}):
                    raise Error("Web Courier request headers are not allowed.")
            except (Error, OSError, ValueError):
                self.reply(403, {"error": "Web Courier preflight was rejected."})
                return
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "POST")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Vary", "Origin")
            self.end_headers()

        def courier_post(self, connection_id):
            if not self.courier_host():
                return
            from . import web_courier
            token_header = self.headers.get("Authorization", "")
            token = token_header[7:] if token_header.startswith("Bearer ") else ""
            origin = self.headers.get("Origin")
            try:
                web_courier.authorize(app, connection_id, token, origin)
            except Error as exc:
                if getattr(exc, "code", "") == "conflict":
                    self.reply(403, {"error": "Web Courier connection is not authorized."})
                else:
                    self.reply(503, {"error": "Web Courier entry cannot be checked now."})
                return
            except (OSError, ValueError):
                self.reply(503, {"error": "Web Courier entry cannot be checked now."})
                return
            if origin:
                self.courier_origin = origin
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 64 * 1024 or not self.headers.get("Content-Type", "").startswith("application/json"):
                    raise Error("Web Courier needs a JSON request of at most 64 KiB.")
                payload = json.loads(self.rfile.read(length))
                if self.server.stopping.is_set():
                    self.reply(503, {"error": "Workbench is stopping."})
                    return
                result = web_courier.handle(app, connection_id, token, origin, payload)
                self.reply(200, {"ok": True, "result": result})
            except (Error, ValueError, OSError, TypeError) as exc:
                self.reply(409 if getattr(exc, "code", "") == "conflict" else 400,
                           {"ok": False, "code": getattr(exc, "code", "invalid_input"),
                            "error": str(exc)})

        def do_GET(self):
            self.courier_origin = None
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
                name = "setup.html" if self.path == "/setup" else "index.html"
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
            self.courier_origin = None
            if self.path.startswith("/api/web-courier/"):
                connection_id = self.courier_id()
                if connection_id is None:
                    self.reply(404, {"error": "Not found"})
                else:
                    self.courier_post(connection_id)
                return
            if not self.authorized():
                return
            if self.path == "/api/shutdown":
                if getattr(app, "backend", None):
                    from .backend import stop
                    self.reply(200, {"ok": True, "result": {**stop(app), "shutdown_requested": True}})
                    return
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
    from .backend import run
    run(app, port, open_browser, setup)


def mcp(app, actor=None, completion_config=None, workspace=None):
    if actor is None and os.environ.get("AW_AGENT") and os.environ.get("AW_BINDING"):
        actor = (os.environ["AW_WORKSPACE"], os.environ["AW_AGENT"], os.environ["AW_BINDING"])
    completion = None
    if completion_config is not None:
        from .mcp_completion import CompletionMCP
        completion = CompletionMCP(app, completion_config, actor, workspace)
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
                if completion is not None:
                    from .mcp_completion import TOOLS
                    result = {"tools": TOOLS}
                else:
                    result = {"tools": [{"name": "aw_execute", "description": "Agent Workspace operations. Commands: " + ", ".join(command_map(app)),
                                     "inputSchema": TOOL_SCHEMA}]}
            elif method == "tools/call":
                if completion is not None:
                    try:
                        output = completion.call(params["name"], params.get("arguments", {}))
                        result = {"content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False)}]}
                    except Error as exc:
                        result = {"isError": True, "content": [{"type": "text", "text": json.dumps(
                            {"error": str(exc), "code": exc.code}, ensure_ascii=False)}]}
                elif params["name"] != "aw_execute":
                    raise Error("Unknown tool")
                else:
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
