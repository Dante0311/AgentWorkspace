from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from . import __version__
from .app import App
from .commands import SOFTWARE_OPERATIONS, execute
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
    review = domains.add_parser("model-review", help="Review one saved model-default change locally.")
    review.add_argument("request_id")
    setup = domains.add_parser("setup", help="Open first-use setup; detect dependencies, never install them.")
    setup.add_argument("--port", type=int, default=8765)
    setup.add_argument("--open", action="store_true")
    mcp = domains.add_parser("mcp", help="MCP stdio tools; use AW_* environment to bind model identity.")
    mcp.add_argument("--completion-config", help="Local configuration for identity-bound completion tools only.")
    domains.add_parser("codex-hook", help="Save the current AW session before compaction; reads Codex hook JSON on stdin.")

    def actions(domain, names):
        sub = domains.add_parser(domain).add_subparsers(dest="action", required=True)
        return {name: sub.add_parser(name) for name in names}

    service = actions("backend", ["run", "start", "status", "stop", "restart", "log"])
    for key in ("run", "start", "restart"):
        service[key].add_argument("--port", type=int)
        service[key].add_argument("--open", dest="open_app", action="store_true")
    service["log"].add_argument("--agent-id")
    service["log"].add_argument("--directory")
    service["log"].add_argument("--worker", dest="worker_id")
    service["log"].add_argument("--lines", type=int, default=100)

    actions("software", ["status", "update"])

    courier = actions("web-courier", ["connect", "status", "revoke"])
    courier["connect"].add_argument("agent_id")
    courier["connect"].add_argument("--binding", dest="expected_binding", required=True)
    courier["connect"].add_argument("--target-url", required=True)
    courier["connect"].add_argument("--extension-id", required=True)
    courier["connect"].add_argument("--request-id", required=True)
    courier["connect"].add_argument("--port", type=int, default=8765)
    courier["connect"].add_argument("--worker", dest="worker_id")
    for key in ("status", "revoke"):
        courier[key].add_argument("connection_id")
    courier["revoke"].add_argument("--request-id", required=True)

    migration = actions("layout", ["plan", "migrate"])
    for sub in migration.values():
        sub.add_argument("--agent", dest="agent_ids", action="append",
                         help="Limit instance migration to these Agents; repeat to select more than one.")
    migration["migrate"].add_argument("--request-id", required=True)
    migration["migrate"].add_argument("--migrate-shared", action="store_true")
    migration["migrate"].add_argument("--compatible-writers",
                                     help="Explicit writer confirmation for the planned shared revision: JSON or @file.json.")

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

    ws = actions("workspace", ["init", "connect", "bootstrap-remote", "list", "show", "friend", "project", "doctor", "read", "skills"])
    for key in ("init", "connect", "bootstrap-remote"):
        ws[key].add_argument("name")
        ws[key].add_argument("directory" if key == "init" else "address")
    for key in ("friend", "project"):
        ws[key].add_argument("operation", choices=["add", "list", "remove"])
        ws[key].add_argument("--alias")
        ws[key].add_argument("--address")
        ws[key].add_argument("--content", default="")

    ws["read"].add_argument("--path", dest="paths", action="append", required=True)
    ws["read"].add_argument("--revision")
    ws["skills"].add_argument("--revision")

    ag = actions("agent", ["create", "import", "list", "show", "history", "connect", "configure", "versions", "update",
        "promote", "archive", "unarchive", "start", "bind", "stop", "takeover", "handoff", "renew", "fork", "input",
        "capture-desktop", "configure-desktop", "sync", "upgrade-tools", "configure-codex", "configure-sdk",
        "transfer", "transfer-profile", "transfer-continue", "transfer-status", "desktop-project", "desktop-project-save", "skills", "skill-install", "skill-update", "desktop-discover", "desktop-prepare"])
    for key, sub in ag.items():
        if key != "list":
            sub.add_argument("name" if key in ("create", "import") else "agent_id")
            if key not in ("history", "takeover", "configure-codex", "configure-sdk", "transfer-profile", "desktop-project", "desktop-project-save", "desktop-discover", "desktop-prepare"):
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
    ag["start"].add_argument("--here", action="store_true", help="Relay into this real Codex Desktop chat without creating another chat.")
    ag["bind"].add_argument("--binding", required=True)
    ag["bind"].add_argument("--session", required=True)
    ag["stop"].add_argument("--binding", default=os.environ.get("AW_BINDING"))
    ag["stop"].add_argument("--checkpoint", required=True)
    ag["stop"].add_argument("--confirm-stopped", action="store_true", help="Current owner attestation for manual adapters only.")
    ag["takeover"].add_argument("--binding", required=True, help="The current entry selected by the user.")
    ag["takeover"].add_argument("--checkpoint", required=True, help="Saved materials to continue; unsaved files are not migrated.")
    ag["takeover"].add_argument("--confirm", action="store_true", help="Revoke AW authority; does not stop the old native chat.")
    ag["fork"].add_argument("--checkpoint", required=True)
    ag["fork"].add_argument("--name", required=True)
    ag["fork"].add_argument("--new-id")
    ag["fork"].add_argument("--resume", action="store_true", help="Continue preparing the same Fork target after checking its original source.")
    ag["create"].add_argument("--skill", dest="skills", action="append")
    for key in ("skill-install", "skill-update"):
        ag[key].add_argument("--name", required=True)
        ag[key].add_argument("--revision")
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
    ag["desktop-project-save"].add_argument("--project-directory", help="Existing native project root; omit to keep the chosen project.")
    ag["desktop-project-save"].add_argument("--revision")

    ag["desktop-prepare"].add_argument("--request-id", required=True)
    ag["desktop-prepare"].add_argument("--project-id")
    ag["desktop-prepare"].add_argument("--section-id")
    ag["desktop-prepare"].add_argument("--create-section", action="store_true")
    ag["desktop-prepare"].add_argument("--revision")

    for key in ("show", "history", "start", "bind", "stop", "takeover", "handoff", "renew", "input", "sync", "fork",
                "configure", "configure-codex", "configure-sdk", "configure-desktop", "capture-desktop",
                "transfer", "transfer-profile", "transfer-continue", "transfer-status", "desktop-project", "desktop-project-save", "desktop-discover", "desktop-prepare"):
        ag[key].add_argument("--worker", dest="worker_id")
    ag["sync"].add_argument("--shared-path", dest="shared_paths", action="append")

    wr = actions("worker", ["create", "list", "show", "update", "default", "archive", "unarchive", "migrate",
                            "start", "bind", "stop", "handoff", "renew", "input", "history", "configure",
                            "configure-codex", "configure-sdk", "configure-desktop"])
    for key, sub in wr.items():
        sub.add_argument("agent_id")
        if key not in ("create", "list"):
            sub.add_argument("worker_id")
    wr["create"].add_argument("name")
    wr["create"].add_argument("--id", dest="worker_id")
    wr["create"].add_argument("--request-id", help="Continue the same creation request after reading its original result.")
    wr["create"].add_argument("--description", required=True)
    wr["create"].add_argument("--background", default="")
    wr["create"].add_argument("--reference", dest="references", action="append")
    wr["list"].add_argument("--archived", action=argparse.BooleanOptionalAction, default=None)
    wr["update"].add_argument("--revision", required=True)
    for field in ("name", "description", "background"):
        wr["update"].add_argument("--" + field)
    wr["update"].add_argument("--reference", dest="references", action="append")
    wr["default"].add_argument("--revision", required=True, help="Agent revision from agent show, not a Worker revision.")
    wr["migrate"].add_argument("--request-id", required=True)
    wr["migrate"].add_argument("--directory")
    wr["migrate"].add_argument("--compatible-writers", required=True,
                               help="Explicit writer confirmation as JSON or @file.json.")
    for key in ("start", "bind", "stop", "handoff", "renew", "input", "configure", "configure-desktop"):
        wr[key].add_argument("--directory")
    wr["start"].add_argument("--open", dest="open_app", action="store_true")
    wr["start"].add_argument("--here", action="store_true")
    wr["bind"].add_argument("--binding", required=True)
    wr["bind"].add_argument("--session", required=True)
    wr["stop"].add_argument("--binding", default=os.environ.get("AW_BINDING"))
    wr["stop"].add_argument("--checkpoint", required=True)
    wr["stop"].add_argument("--confirm-stopped", action="store_true")
    wr["input"].add_argument("--text", required=True)
    wr["input"].add_argument("--delivery", choices=["normal", "insert"], default="normal")
    wr["input"].add_argument("--request-id")
    wr["configure"].add_argument("--config", dest="value", required=True, help="JSON or @file.json")
    for key in ("configure-codex", "configure-sdk"):
        wr[key].add_argument("--allow-http", action="store_true")
        for field in ("model", "effort", "base-url", "env-key", "executable"):
            wr[key].add_argument("--" + field, default=None if field == "executable" else "")
    wr["configure-sdk"].add_argument("--kind", required=True, choices=["claude", "codebuddy"])
    wr["configure-sdk"].add_argument("--allowed-tool", dest="allowed_tools", action="append")
    for field in ("model", "effort", "project-id"):
        wr["configure-desktop"].add_argument("--" + field, default="")

    mt = actions("maintenance", ["status", "schedule", "grant", "repair", "run"])
    mt["schedule"].add_argument("--enabled", action=argparse.BooleanOptionalAction, required=True)
    mt["schedule"].add_argument("--interval", type=float, default=300)
    mt["schedule"].add_argument("--notify", action="store_true")
    mt["grant"].add_argument("agent_id")
    mt["grant"].add_argument("--command", dest="commands", action="append", default=[])
    mt["grant"].add_argument("--target", dest="targets", action="append", default=[])
    mt["repair"].add_argument("agent_id")
    mt["repair"].add_argument("--repair-action", dest="repair_action", choices=["publication-reconcile", "bridge-retry", "sync-idle", "continue-stop", "runtime-recover"], required=True)
    mt["repair"].add_argument("--request-id", required=True)
    mt["repair"].add_argument("--worker", dest="worker_id")
    for field in ("operation-id", "bridge", "expected-binding", "expected-generation", "expected-checkpoint"):
        mt["repair"].add_argument("--" + field)

    cp = actions("checkpoint", ["create", "list", "show"])
    for sub in cp.values():
        sub.add_argument("agent_id")
        sub.add_argument("--worker", dest="worker_id")
    cp["create"].add_argument("--summary", required=True)
    cp["create"].add_argument("--content", default="")
    cp["create"].add_argument("--binding", default=os.environ.get("AW_BINDING"))
    cp["create"].add_argument("--directory")
    cp["create"].add_argument("--id", dest="checkpoint_id")
    cp["create"].add_argument("--shared-path", dest="shared_paths", action="append")
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
    msg["send"].add_argument("--to")
    msg["send"].add_argument("--to-worker")
    msg["send"].add_argument("--reply-to", help="Reply to the selected original sender and Worker.")
    msg["send"].add_argument("--content")
    msg["send"].add_argument("--content-file")
    msg["send"].add_argument("--delivery", choices=["normal", "insert"], required=True)
    msg["send"].add_argument("--ref", dest="message_refs", action="append")
    msg["send"].add_argument("--request-id")
    msg["list"].add_argument("--agent", dest="agent_id")
    msg["list"].add_argument("--worker", dest="worker_id")
    msg["list"].add_argument("--direction", choices=["in", "out"], default="in")
    msg["list"].add_argument("--unacked", action="store_true")
    for key in ("show", "receive"):
        msg[key].add_argument("--id", dest="message_id", required=True)
    msg["receive"].add_argument("--directory")
    msg["poll"].add_argument("--directory")
    msg["watch"].add_argument("operation", choices=["start", "stop", "status"])
    msg["watch"].add_argument("--interval", type=float, default=5)
    msg["watch"].add_argument("--directory")
    msg["watch"].add_argument("--worker", dest="worker_id")
    msg["reconcile"].add_argument("operation_id")

    rt = actions("runtime", ["run", "start", "stop", "status", "desktop-observe", "launch-show", "reconcile-create"])
    for sub in rt.values():
        sub.add_argument("agent_id")
        sub.add_argument("--directory")
        sub.add_argument("--worker", dest="worker_id")
    rt["run"].add_argument("--stop-binding")
    rt["reconcile-create"].add_argument("--binding", required=True)
    rt["reconcile-create"].add_argument("--session", required=True)
    bridge = actions("bridge", ["configure", "start", "stop", "status", "send"])
    for key, sub in bridge.items():
        sub.add_argument("agent_id")
        sub.add_argument("--directory")
        sub.add_argument("--worker", dest="worker_id")
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
        sub.add_argument("--worker", dest="worker_id")
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
    if domain == "codex-hook":
        from .compaction import run
        try:
            payload = json.load(sys.stdin)
            result = run(app, payload)
        except (Error, ValueError, OSError) as exc:
            result = {"continue": True, "systemMessage": f"AW 压缩前检查点未确认保存：{exc}"}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    try:
        actor = None
        operation = (options.get("command") if domain == "call" else
                     "agent.model-change-review" if domain == "model-review" else domain + "." + str(action))
        if (operation in ("agent.start", "worker.start") and options.get("here")
                or domain == "call" and operation in ("agent.start", "worker.start") and parse_json(options["arguments"]).get("here")):
            operation = "agent.start-here"
        software_operation = operation in SOFTWARE_OPERATIONS or domain == "serve"
        # Local software control uses the host's tool permissions, not an Agent's execution entry.
        if not software_operation and os.environ.get("AW_BINDING") and os.environ.get("AW_AGENT"):
            if not os.environ.get("AW_WORKSPACE"):
                raise Error("An inherited model identity requires AW_WORKSPACE.")
            actor = (os.environ["AW_WORKSPACE"], os.environ["AW_AGENT"], os.environ["AW_BINDING"])
        if actor is None and not software_operation:
            from .runtime import desktop_directory_actor
            actor = desktop_directory_actor(app, operation)
        if actor and not workspace:
            workspace = actor[0]
        if actor and (domain in ("serve", "setup") or (domain in ("maintenance", "runtime", "backend") and action == "run")):
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
        if domain == "backend" and action == "run":
            from .backend import run
            run(app, **options)
            return 0
        if domain in ("serve", "setup"):
            from .server import serve
            serve(app, options["port"], options["open"], setup=domain == "setup")
            return 0
        if domain == "mcp":
            from .server import mcp
            mcp(app, actor=actor, completion_config=options["completion_config"], workspace=workspace)
            return 0
        if domain == "runtime" and action == "run":
            from .runtime import Runner
            Runner(app, workspace, **options).run()
            return 0
        if domain == "call":
            command, args = options["command"], parse_json(options["arguments"])
            if options.get("desktop_agent") and not software_operation:
                from .runtime import desktop_actor
                desktop_identity = desktop_actor(app, workspace, options["desktop_agent"])
                if actor and actor != desktop_identity:
                    raise Error("Inherited identity differs from the actual Desktop session.")
                actor = desktop_identity
        else:
            if domain == "model-review":
                command, args = "agent.model-change-review", {"request_id": options["request_id"]}
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
            if args.get("compatible_writers") is not None:
                args["compatible_writers"] = parse_json(args["compatible_writers"])
            if command == "maintenance.repair":
                args["action"] = args.pop("repair_action")
            if command == "agent.capture-desktop" and args.get("command"):
                args["command"] = parse_json(args["command"])
            if command in ("workspace.friend", "workspace.project"):
                args["kind"] = "friends" if action == "friend" else "projects"
                command = "workspace.relation"
            if command == "agent.import":
                command = "agent.create"
            if command in ("agent.unarchive", "worker.unarchive"):
                command, args["archived"] = domain + ".archive", False
            if command in ("agent.renew", "worker.renew"):
                command, args["renew"] = domain + ".handoff", True
            if domain == "bridge" and action in ("start", "stop"):
                command, args["enabled"] = "bridge.switch", action == "start"
        if command == "backend.log" and args.get("agent_id"):
            if not workspace:
                raise Error("Select the Runner's --workspace.")
            args["workspace"] = workspace
        if not command.startswith(("setup.", "session.", "backend.", "software.")) and command not in ("workspace.init", "workspace.connect", "workspace.bootstrap-remote", "workspace.list", "message.reconcile", "web-courier.status", "web-courier.revoke"):
            if not workspace and not args.get("workspace"):
                raise Error("Select --workspace or set AW_WORKSPACE.")
            args.setdefault("workspace", workspace)
        # Agent business operations retain their inherited identity and target permissions.
        result = execute(app, command, args, actor=actor)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, indent=2))
        if (isinstance(result, dict) and result.get("confirmation") != "cancelled"
                and result.get("state") in ("pending", "outcome_unknown")):
            return 2
        return 0
    except (Error, ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "code": getattr(exc, "code", "invalid_input"), "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
