"""One explicit command surface for CLI, local HTTP and model tools."""
from __future__ import annotations

from functools import partial
import inspect

from . import bridges, runtime, onboarding, harness_config, maintenance, transfer
from .messages import Messages
from .util import Conflict, Error, digest, inside, locked, read_json, relpath, write_bytes, write_json


READ_ONLY = {"workspace.list", "workspace.show", "agent.list", "agent.show", "agent.versions",
             "checkpoint.list", "checkpoint.show", "work.list", "work.show", "message.list", "message.show",
             "asset.list", "asset.read", "runtime.status", "bridge.status",
             "agent.transfer-status", "maintenance.status", "workspace.doctor"}

USER_MANAGEMENT = {"agent.bind", "agent.start", "runtime.start", "runtime.stop", "bridge.configure", "agent.configure",
                   "workspace.init", "setup.scan", "setup.check-git", "setup.create",
                   "setup.inspect-codex", "setup.prepare-instance", "agent.configure-codex",
                   "agent.configure-sdk", "agent.transfer", "agent.transfer-profile", "agent.transfer-continue",
                   "maintenance.grant", "maintenance.schedule", "maintenance.repair"}
CALLER_BOUND = {"message.send", "message.receive", "message.poll", "checkpoint.create", "agent.stop", "bridge.send"}


def assets(app, operation, workspace, agent_id, path=None, content=None, revision=None, directory=None):
    root = app.root(workspace, agent_id, directory)
    if operation == "list":
        content_map, skipped = app.collect(root)
        return {"files": [{"path": p, "bytes": len(data), "revision": digest(data)} for p, data in content_map.items()],
                "excluded": skipped}
    path = relpath(path)
    if any(":" in part or part.endswith((".", " ")) for part in path.split("/")):
        raise Error("Use portable asset paths without drive/stream syntax or trailing dots/spaces.")
    target = inside(root, path)
    if operation == "read":
        data = target.read_bytes()
        return {"path": path, "content": data.decode("utf-8"), "revision": digest(data)}
    with locked(root / ".aw-local/files.lock"):
        # Check both the normalized name and its destination, including directory symlinks.
        resolved = relpath(target.resolve().relative_to(root.resolve()).as_posix())
        for candidate in (path, resolved):
            if candidate.split("/", 1)[0].casefold() == ".aw" or candidate.casefold() == "source.json":
                raise Error("Use platform operations to change managed metadata; asset.write edits user assets.")
        existing = target.read_bytes() if target.exists() else None
        if (digest(existing) if existing is not None else None) != revision:
            raise Conflict("Asset changed; read it before replacing it.")
        write_bytes(target, content.encode())
    return {"path": path, "revision": digest(content.encode()), "saved": "local"}


def bind_entry(app, workspace, agent_id, binding, session, directory=None):
    root = app.root(workspace, agent_id, directory)
    entry = app.store(workspace).snapshot().json(f"bindings/{binding}.json")
    if entry is None:
        raise Error("Binding not found.")
    if entry["kind"] == "desktop":
        config = read_json(root / ".aw-local/runtime.json", {})
        adapter = runtime.Desktop(root, config, session)
        try:
            if adapter.status() == "unknown":
                raise Error("Desktop cannot verify this new session; entry was not activated.")
        finally:
            adapter.close()
    return app.bind(workspace, agent_id, binding, session, directory)


def stop_entry(app, workspace, agent_id, binding, checkpoint, directory=None, confirm_stopped=False):
    result = app.stop(workspace, agent_id, binding, checkpoint, directory)
    if confirm_stopped:
        entry = app.store(workspace).snapshot().json(f"bindings/{binding}.json")
        if entry["kind"] != "manual":
            raise Error("Desktop/CLI stop must be observed by its adapter, not overridden by a flag.")
        result = app.finish_stop(workspace, agent_id, binding, observed_idle=True)
        result["confirmation"] = "explicit_current_owner_attestation; not OS isolation"
    return result


def runtime_stop(app, workspace, agent_id, directory=None):
    root = app.root(workspace, agent_id, directory)
    binding = app.agent(workspace, agent_id)["current"]
    write_json(root / ".aw-local/control.json", {**read_json(root / ".aw-local/control.json", {}), "stop": binding})
    return {"monitor_stop_requested": True, "binding": binding, "execution_right_released": False}


def runtime_launch(app, workspace, agent_id, directory=None):
    root = app.root(workspace, agent_id, directory)
    write_json(root / ".aw-local/control.json", {**read_json(root / ".aw-local/control.json", {}), "stop": None})
    return runtime.spawn_runner(app, workspace, agent_id, directory)


def message_poll(app, workspace, agent_id, binding, directory=None):
    root = app.root(workspace, agent_id, directory)
    item, entry = app.require_binding(workspace, agent_id, binding)
    if entry["kind"] == "desktop":
        adapter = runtime.Desktop(root, read_json(root / ".aw-local/runtime.json"), entry["session"])
        try:
            return Messages(app).poll(workspace, agent_id, binding, adapter=adapter, directory=directory)
        finally:
            adapter.close()
    # Never start another app-server just to poll a managed CLI thread.
    result = Messages(app).poll(workspace, agent_id, binding, directory=directory)
    if entry["kind"] in ("codex", "claude", "codebuddy"):
        result["hint"] = "The owning runner performs push polling. This invocation only reports the pending notification."
    return result


def upgrade_tools(app, workspace, agent_id, directory=None):
    root = app.root(workspace, agent_id, directory)
    with locked(root / ".aw-local/files.lock"):
        manifest = read_json(root / ".aw/software.json", {"files": {}})
        fresh = app._resources()
        for path, data in fresh.items():
            if path == ".aw/software.json":
                continue
            local = inside(root, path)
            if local.exists() and digest(local.read_bytes()) != manifest["files"].get(path):
                raise Conflict(f"Modified platform resource: {path}. Preserve or reconcile it before upgrading.")
        for path, data in fresh.items():
            write_bytes(inside(root, path), data)
    return {"resources_updated": list(fresh), "user_assets_changed": False, "snapshot_saved": False}


def bridge_switch(app, workspace, agent_id, name, enabled, directory=None):
    root = app.root(workspace, agent_id, directory)
    path = root / ".aw-local/bridges" / f"{name}.json"
    value = read_json(path)
    if value is None:
        raise Error("Bridge is not configured.")
    return bridges.configure(app, workspace, agent_id, name, {**value, "enabled": enabled}, directory)


def bridge_status(app, workspace, agent_id, directory=None):
    root = app.root(workspace, agent_id, directory)
    return {p.stem: read_json(p) for p in (root / ".aw-local/bridges/status").glob("*.json")}


def command_map(app):
    messages = Messages(app)
    return {
        "workspace.init": partial(onboarding.init_workspace, app), "workspace.connect": app.workspace_connect,
        "workspace.bootstrap-remote": app.workspace_bootstrap_remote,
        "workspace.list": app.workspace_list, "workspace.show": app.workspace_show,
        "workspace.relation": app.relation,
        "setup.scan": onboarding.scan, "setup.check-git": onboarding.check_git,
        "setup.create": partial(onboarding.create_workspace, app),
        "setup.inspect-codex": harness_config.inspect_codex,
        "setup.prepare-instance": partial(onboarding.prepare_instance, app),
        "agent.configure-codex": partial(harness_config.configure_codex, app),
        "agent.configure-sdk": partial(harness_config.configure_sdk, app),
        "agent.transfer": partial(transfer.request, app),
        "agent.transfer-profile": partial(transfer.request_profile, app),
        "agent.transfer-continue": partial(transfer.advance, app),
        "agent.transfer-status": partial(transfer.status, app),
        "workspace.doctor": partial(maintenance.doctor, app),
        "maintenance.grant": partial(maintenance.grant, app),
        "maintenance.schedule": partial(maintenance.schedule, app),
        "maintenance.status": partial(maintenance.status, app),
        "maintenance.repair": partial(maintenance.repair, app),
        "agent.create": app.create, "agent.list": app.agents, "agent.show": app.show,
        "agent.connect": app.connect_agent, "agent.configure": app.configure,
        "agent.update": app.update, "agent.versions": app.versions, "agent.promote": app.promote,
        "agent.archive": app.archive, "agent.fork": app.fork,
        "checkpoint.create": app.checkpoint, "checkpoint.list": app.checkpoints, "checkpoint.show": app.checkpoint_show,
        "agent.sync": app.sync_agent,
        "agent.start": partial(runtime.start, app), "agent.bind": partial(bind_entry, app),
        "agent.stop": partial(stop_entry, app), "agent.handoff": partial(runtime.handoff_request, app),
        "agent.input": partial(runtime.queue_input, app),
        "agent.capture-desktop": partial(runtime.configure_desktop, app),
        "agent.upgrade-tools": partial(upgrade_tools, app),
        "runtime.start": partial(runtime_launch, app), "runtime.stop": partial(runtime_stop, app),
        "runtime.status": app.show,
        "work.create": app.work_create, "work.list": app.work_list, "work.show": app.work_show,
        "work.update": app.work_update, "work.deliver": app.work_deliver,
        "message.send": messages.send, "message.list": messages.list, "message.show": messages.show,
        "message.receive": messages.receive, "message.poll": partial(message_poll, app),
        "message.reconcile": messages.reconcile, "message.watch": partial(runtime.watch, app),
        "asset.list": partial(assets, app, "list"),
        "asset.read": partial(assets, app, "read"),
        "asset.write": partial(assets, app, "write"),
        "bridge.configure": partial(bridges.configure, app),
        "bridge.switch": partial(bridge_switch, app), "bridge.status": partial(bridge_status, app),
        "bridge.send": partial(bridges.send, app),
    }


def execute(app, command, arguments, *, actor=None):
    commands = command_map(app)
    if command not in commands:
        raise Error(f"Unknown operation: {command}")
    handler = commands[command]
    signature = inspect.signature(handler)
    if not isinstance(arguments, dict):
        raise Error("Operation arguments must be a JSON object.")
    args = dict(arguments)
    if actor:
        workspace, aid, binding = actor
        # Signatures supply defaults, never authorization. A new agent's ID is a target.
        if "workspace" in signature.parameters:
            args.setdefault("workspace", workspace)
        if "agent_id" in signature.parameters and command != "agent.create":
            args.setdefault("agent_id", aid)
        if command in USER_MANAGEMENT and not maintenance.allowed(app, actor, command, args):
            raise Error("This is a user-management operation; a scoped caretaker grant is required.")
        # Ordinary agents may act on their own assets; another instance is a management target.
        if (command not in READ_ONLY and command not in CALLER_BOUND
                and (args.get("workspace", workspace) != workspace
                     or (command != "agent.create" and args.get("agent_id", aid) != aid))
                and not maintenance.allowed(app, actor, command, args)):
            raise Error("Managing another instance requires an explicit caretaker grant.")
        if command in CALLER_BOUND:
            for name, value in (("workspace", workspace), ("agent_id", aid), ("binding", binding)):
                if args.get(name, value) != value:
                    raise Conflict("This operation must use the calling workspace, instance and binding.")
                args[name] = value
    try:
        signature.bind(**args)
    except TypeError as exc:
        raise Error(f"Invalid arguments for {command}: {exc}") from exc
    if actor and command not in READ_ONLY:
        app.require_binding(workspace, aid, binding, allow_stopping=command in ("checkpoint.create", "agent.stop"))
    return handler(**args)
