from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from . import __version__
from .app import App
from .commands import execute
from .util import Error


def parser():
    p = argparse.ArgumentParser(prog="aw", description="Persistent agents, explicit handoff, Git collaboration.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--home", default=os.environ.get("AW_HOME"))
    p.add_argument("--workspace", "-w", default=os.environ.get("AW_WORKSPACE"))
    domains = p.add_subparsers(dest="domain", required=True)
    call = domains.add_parser("call", help="Invoke the same JSON operation used by HTTP/MCP.")
    call.add_argument("command")
    call.add_argument("--desktop-agent", help="Bind this call to the actual CODEX_THREAD_ID of a Desktop instance.")
    call.add_argument("--arguments", default="{}", help="JSON object, or @file.json")
    serve = domains.add_parser("serve", help="Local workbench and authenticated HTTP tools.")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--open", action="store_true")
    setup = domains.add_parser("setup", help="Open first-use setup; detect dependencies, never install them.")
    setup.add_argument("--port", type=int, default=8765)
    setup.add_argument("--open", action="store_true")
    domains.add_parser("mcp", help="MCP stdio tools; use AW_* environment to bind model identity.")

    def actions(domain, names):
        sub = domains.add_parser(domain).add_subparsers(dest="action", required=True)
        return {name: sub.add_parser(name) for name in names}

    session = actions("session", ["prepare", "open", "show", "run"])
    for key in ("open", "show", "run"):
        session[key].add_argument("request_id")
    session["prepare"].add_argument("--kind", required=True, choices=["codex", "claude", "codebuddy"])
    session["prepare"].add_argument("--directory", required=True)
    session["prepare"].add_argument("--prompt", default="")
    session["prepare"].add_argument("--request-id")
    session["prepare"].add_argument("--allow-http", action="store_true")
    for field in ("model", "effort", "base-url", "env-key", "executable"):
        session["prepare"].add_argument("--" + field, default=None if field == "executable" else "")

    ws = actions("workspace", ["init", "connect", "bootstrap-remote", "list", "show", "friend", "project", "doctor"])
    for key in ("init", "connect", "bootstrap-remote"):
        ws[key].add_argument("name")
        ws[key].add_argument("directory" if key == "init" else "address")
    for key in ("friend", "project"):
        ws[key].add_argument("operation", choices=["add", "list", "remove"])
        ws[key].add_argument("--alias")
        ws[key].add_argument("--address")
        ws[key].add_argument("--content", default="")

    ag = actions("agent", ["create", "import", "list", "show", "connect", "configure", "versions", "update",
        "promote", "archive", "unarchive", "start", "bind", "stop", "handoff", "renew", "fork", "input",
        "capture-desktop", "configure-desktop", "sync", "upgrade-tools", "configure-codex", "configure-sdk",
        "transfer", "transfer-profile", "transfer-continue", "transfer-status", "desktop-project", "desktop-project-save"])
    for key, sub in ag.items():
        if key != "list":
            sub.add_argument("name" if key in ("create", "import") else "agent_id")
            if key not in ("configure-codex", "configure-sdk", "transfer-profile", "desktop-project", "desktop-project-save"):
                sub.add_argument("--directory")
    for key in ("create", "import"):
        ag[key].add_argument("--id", dest="agent_id")
        ag[key].add_argument("--description", default="")
        ag[key].add_argument("--definition")
        ag[key].add_argument("--revision")
    ag["create"].add_argument("--request-id", help="Resume an exact creation request; requires --id.")
    ag["import"].add_argument("--from-directory", dest="import_directory", required=True)
    ag["import"].add_argument("--asset", dest="assets", action="append", required=True)
    ag["configure"].add_argument("--config", dest="value", required=True, help="JSON or @file.json")
    ag["update"].add_argument("--revision")
    ag["promote"].add_argument("--path", dest="paths", action="append", required=True)
    ag["promote"].add_argument("--destination", required=True)
    ag["start"].add_argument("--open", dest="open_app", action="store_true")
    ag["bind"].add_argument("--binding", required=True)
    ag["bind"].add_argument("--session", required=True)
    ag["stop"].add_argument("--binding", default=os.environ.get("AW_BINDING"))
    ag["stop"].add_argument("--checkpoint", required=True)
    ag["stop"].add_argument("--confirm-stopped", action="store_true", help="Current owner attestation for manual adapters only.")
    ag["fork"].add_argument("--checkpoint", required=True)
    ag["fork"].add_argument("--name", required=True)
    ag["fork"].add_argument("--new-id")
    ag["input"].add_argument("--text", required=True)
    ag["input"].add_argument("--delivery", choices=["normal", "insert"], default="normal")
    ag["capture-desktop"].add_argument("--command", help="JSON argv array of the actual desktop MCP server.")
    ag["configure-desktop"].add_argument("--model", default="")
    ag["configure-desktop"].add_argument("--effort", default="")
    ag["configure-desktop"].add_argument("--project-id", default="")

    for key in ("configure-codex", "configure-sdk", "transfer-profile"):
        ag[key].add_argument("--allow-http", action="store_true",
                             help="Allow this profile's non-loopback HTTP URL; credentials and content are unencrypted.")
        for field in ("model", "effort", "base-url", "env-key", "executable"):
            ag[key].add_argument("--" + field, default=None if field == "executable" else "")
        if key != "configure-codex":
            ag[key].add_argument("--kind", required=True, choices=["claude", "codebuddy"] if key == "configure-sdk" else ["codex", "claude", "codebuddy"])
            ag[key].add_argument("--allowed-tool", dest="allowed_tools", action="append")
    ag["transfer"].add_argument("--config", dest="target_config", required=True, help="Runtime JSON or @file.json")
    for key in ("transfer", "transfer-profile", "input"):
        ag[key].add_argument("--request-id")

    for key in ("desktop-project", "desktop-project-save"):
        ag[key].add_argument("--harness", choices=["codex", "claude", "workbuddy"], default="codex")
    ag["desktop-project-save"].add_argument("--project-name", required=True)
    ag["desktop-project-save"].add_argument("--section-name", default="")
    ag["desktop-project-save"].add_argument("--product-path", dest="product_paths", action="append")
    ag["desktop-project-save"].add_argument("--revision")

    mt = actions("maintenance", ["status", "schedule", "grant", "repair", "run"])
    mt["schedule"].add_argument("--enabled", action=argparse.BooleanOptionalAction, required=True)
    mt["schedule"].add_argument("--interval", type=float, default=300)
    mt["schedule"].add_argument("--notify", action="store_true")
    mt["grant"].add_argument("agent_id")
    mt["grant"].add_argument("--command", dest="commands", action="append", default=[])
    mt["grant"].add_argument("--target", dest="targets", action="append", default=[])
    mt["repair"].add_argument("agent_id")
    mt["repair"].add_argument("--repair-action", dest="repair_action", choices=["publication-reconcile", "bridge-retry", "sync-idle"], required=True)
    mt["repair"].add_argument("--request-id", required=True)
    for field in ("operation-id", "bridge", "expected-binding", "expected-generation"):
        mt["repair"].add_argument("--" + field)

    cp = actions("checkpoint", ["create", "list", "show"])
    for sub in cp.values():
        sub.add_argument("agent_id")
    cp["create"].add_argument("--summary", required=True)
    cp["create"].add_argument("--content", default="")
    cp["create"].add_argument("--binding", default=os.environ.get("AW_BINDING"))
    cp["create"].add_argument("--directory")
    cp["create"].add_argument("--id", dest="checkpoint_id")
    cp["show"].add_argument("--id", dest="checkpoint", required=True)

    wk = actions("work", ["create", "list", "show", "update", "deliver"])
    wk["create"].add_argument("--owner", required=True)
    wk["create"].add_argument("--parent", dest="parent_id")
    wk["list"].add_argument("--owner")
    wk["list"].add_argument("--tree", action="store_true")
    wk["list"].add_argument("--parent", dest="parent_id")
    for key in ("create", "update", "deliver"):
        wk[key].add_argument("--content")
        wk[key].add_argument("--content-file")
    for key in ("show", "update", "deliver"):
        wk[key].add_argument("work_id")
    for key in ("update", "deliver"):
        wk[key].add_argument("--revision", required=True)
    wk["update"].add_argument("--owner")
    wk["update"].add_argument("--parent", dest="parent_id")
    wk["deliver"].add_argument("--ref", dest="refs", action="append", required=True)

    msg = actions("message", ["send", "list", "show", "receive", "poll", "watch", "reconcile"])
    for key in ("send", "receive", "poll", "watch"):
        msg[key].add_argument("agent_id")
    for key in ("send", "receive", "poll"):
        msg[key].add_argument("--binding", default=os.environ.get("AW_BINDING"))
    msg["send"].add_argument("--to", required=True)
    msg["send"].add_argument("--content")
    msg["send"].add_argument("--content-file")
    msg["send"].add_argument("--delivery", choices=["normal", "insert"], required=True)
    msg["send"].add_argument("--ref", dest="message_refs", action="append")
    msg["send"].add_argument("--request-id")
    msg["list"].add_argument("--agent", dest="agent_id")
    msg["list"].add_argument("--direction", choices=["in", "out"], default="in")
    msg["list"].add_argument("--unacked", action="store_true")
    for key in ("show", "receive"):
        msg[key].add_argument("--id", dest="message_id", required=True)
    msg["receive"].add_argument("--directory")
    msg["poll"].add_argument("--directory")
    msg["watch"].add_argument("operation", choices=["start", "stop", "status"])
    msg["watch"].add_argument("--interval", type=float, default=5)
    msg["watch"].add_argument("--directory")
    msg["reconcile"].add_argument("operation_id")

    rt = actions("runtime", ["run", "start", "stop", "status"])
    for sub in rt.values():
        sub.add_argument("agent_id")
        sub.add_argument("--directory")
    rt["run"].add_argument("--stop-binding")
    bridge = actions("bridge", ["configure", "start", "stop", "status", "send"])
    for key, sub in bridge.items():
        sub.add_argument("agent_id")
        sub.add_argument("--directory")
        if key != "status":
            sub.add_argument("--name", required=True)
    bridge["configure"].add_argument("--config", dest="value", required=True)
    bridge["send"].add_argument("--binding", default=os.environ.get("AW_BINDING"))
    bridge["send"].add_argument("--target", required=True)
    bridge["send"].add_argument("--text", required=True)
    bridge["send"].add_argument("--request-id")
    asset = actions("asset", ["list", "read", "write"])
    for key, sub in asset.items():
        sub.add_argument("agent_id")
        sub.add_argument("--directory")
        if key != "list":
            sub.add_argument("--path", required=True)
    asset["write"].add_argument("--content", required=True)
    asset["write"].add_argument("--revision")
    return p


def parse_json(value):
    if value.startswith("@"):
        value = Path(value[1:]).read_text(encoding="utf-8")
    return json.loads(value)


def main(argv=None):
    # Machine-readable JSON uses UTF-8 even when redirected on Windows.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    options = vars(parser().parse_args(argv))
    home, workspace = options.pop("home"), options.pop("workspace")
    domain, action = options.pop("domain"), options.pop("action", None)
    app = App(home)
    try:
        actor = None
        if os.environ.get("AW_BINDING") and os.environ.get("AW_AGENT"):
            if not os.environ.get("AW_WORKSPACE"):
                raise Error("An inherited model identity requires AW_WORKSPACE.")
            actor = (os.environ["AW_WORKSPACE"], os.environ["AW_AGENT"], os.environ["AW_BINDING"])
        if actor is None:
            from .runtime import desktop_directory_actor
            operation = options.get("command") if domain == "call" else domain + "." + str(action)
            actor = desktop_directory_actor(app, operation)
        if actor and not workspace:
            workspace = actor[0]
        if actor and (domain in ("serve", "setup") or (domain in ("maintenance", "runtime") and action == "run")):
            raise Error("Starting a server or worker is a user-management operation.")
        if domain == "session" and action == "run":
            if actor:
                raise Error("Ordinary native sessions are a user-management operation.")
            from .sessions import run
            return run(app, options["request_id"])
        if domain == "maintenance" and action == "run":
            from .maintenance import run
            run(app)
            return 0
        if domain in ("serve", "setup"):
            from .server import serve
            serve(app, options["port"], options["open"], setup=domain == "setup")
            return 0
        if domain == "mcp":
            from .server import mcp
            mcp(app, actor=actor)
            return 0
        if domain == "runtime" and action == "run":
            from .runtime import Runner
            Runner(app, workspace, **options).run()
            return 0
        if domain == "call":
            command, args = options["command"], parse_json(options["arguments"])
            if options.get("desktop_agent"):
                from .runtime import desktop_actor
                desktop_identity = desktop_actor(app, workspace, options["desktop_agent"])
                if actor and actor != desktop_identity:
                    raise Error("Inherited identity differs from the actual Desktop session.")
                actor = desktop_identity
        else:
            command, args = domain + "." + action, options
            file = args.pop("content_file", None)
            if file:
                if args.get("content") is not None:
                    raise Error("Choose either --content or --content-file.")
                args["content"] = Path(file).read_text(encoding="utf-8")
            for key in ("value", "target_config"):
                if key in args:
                    args[key] = parse_json(args[key])
            if command == "maintenance.repair":
                args["action"] = args.pop("repair_action")
            if command == "agent.capture-desktop" and args.get("command"):
                args["command"] = parse_json(args["command"])
            if command in ("workspace.friend", "workspace.project"):
                args["kind"] = "friends" if action == "friend" else "projects"
                command = "workspace.relation"
            if command == "agent.import":
                command = "agent.create"
            if command == "agent.unarchive":
                command, args["archived"] = "agent.archive", False
            if command == "agent.renew":
                command, args["renew"] = "agent.handoff", True
            if domain == "bridge" and action in ("start", "stop"):
                command, args["enabled"] = "bridge.switch", action == "start"
        if not command.startswith(("setup.", "session.")) and command not in ("workspace.init", "workspace.connect", "workspace.bootstrap-remote", "workspace.list", "message.reconcile"):
            if not workspace and not args.get("workspace"):
                raise Error("Select --workspace or set AW_WORKSPACE.")
            args.setdefault("workspace", workspace)
        # A model's inherited identity never silently becomes an administrator.
        result = execute(app, command, args, actor=actor)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, indent=2))
        if isinstance(result, dict) and result.get("state") in ("pending", "outcome_unknown"):
            return 2
        return 0
    except (Error, ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "code": getattr(exc, "code", "invalid_input"), "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
