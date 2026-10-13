"""One explicit command surface for CLI, local HTTP and model tools."""
from __future__ import annotations

from functools import partial
import inspect

from . import backend, bridges, runtime, onboarding, harness_config, maintenance, transfer, sessions, desktop_projects, shared, skills, software, layout, web_courier
from .messages import Messages
from .direct_messages import DirectMessages
from .util import Conflict, Error, digest, inside, read_json, relpath, user_asset_path, write_bytes, write_json


READ_ONLY = {"agent.desktop-discover", "workspace.read", "workspace.skills", "agent.skills", "workspace.list", "workspace.show", "agent.list", "agent.show", "agent.history", "agent.versions",
             "checkpoint.list", "checkpoint.show", "work.list", "work.show", "message.list", "message.show", "message.operation",
             "direct-message.list", "direct-message.show",
             "asset.list", "asset.read", "runtime.status", "runtime.desktop-observe", "runtime.launch-show", "bridge.status",
             "agent.transfer-status", "maintenance.status", "workspace.doctor", "agent.desktop-project", "backend.status", "backend.log", "software.status", "layout.plan", "web-courier.status"}

SOFTWARE_OPERATIONS = {"backend.start", "backend.stop", "backend.restart", "backend.status", "backend.log", "backend.run",
                       "software.status", "software.update"}

USER_MANAGEMENT = {"agent.desktop-prepare", "session.prepare", "session.open", "session.show", "agent.desktop-project-save", "agent.bind", "agent.start", "runtime.start", "runtime.stop", "bridge.configure", "agent.configure",
                   "workspace.init", "setup.scan", "setup.check-git", "setup.create",
                   "setup.inspect-codex", "setup.inspect-sdk", "setup.prepare-instance", "agent.configure-codex",
                   "agent.configure-sdk", "agent.configure-desktop", "agent.capture-desktop", "agent.transfer", "agent.transfer-profile", "agent.transfer-continue",
                   "maintenance.grant", "maintenance.schedule", "maintenance.repair", "backend.attach", "backend.cancel", "runtime.reconcile-create"}
CALLER_BOUND = {"message.send", "message.receive", "message.poll", "checkpoint.create", "agent.stop", "bridge.send", "runtime.receive-input", "message.reconcile", "direct-message.record"}


def assets(app, operation, workspace, agent_id, path=None, content=None, revision=None, directory=None):
    root = app.root(workspace, agent_id, directory)
    if operation == "list":
        content_map, skipped = app.collect(root)
        return {"files": [{"path": p, "bytes": len(data), "revision": digest(data)} for p, data in content_map.items()],
                "excluded": skipped}
    path = relpath(path)
    if any(":" in part or part.endswith((".", " ")) for part in path.split("/")):
        raise Error("Use portable asset paths without drive/stream syntax or trailing dots/spaces.")
    if operation == "read":
        target = inside(root, path)
        data = target.read_bytes()
        return {"path": path, "content": data.decode("utf-8"), "revision": digest(data)}
    with layout.lock(root, "files.lock"):
        target = user_asset_path(root, path, write=True)
        existing = target.read_bytes() if target.exists() else None
        if (digest(existing) if existing is not None else None) != revision:
            raise Conflict("Asset changed; read it before replacing it.")
        write_bytes(target, content.encode())
    return {"path": path, "revision": digest(content.encode()), "saved": "local"}


def bind_entry(app, workspace, agent_id, binding, session, directory=None):
    root = app.root(workspace, agent_id, directory)
    snap = app.store(workspace).snapshot()
    entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
    if entry is None:
        raise Error("Binding not found.")
    if entry["kind"] == "desktop":
        config = read_json(layout.local_path(root, "runtime.json"), {})
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
        snap = app.store(workspace).snapshot()
        entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
        if entry["kind"] != "manual":
            raise Error("Desktop/CLI stop must be observed by its adapter, not overridden by a flag.")
        result = app.finish_stop(workspace, agent_id, binding, observed_idle=True)
        result["confirmation"] = "explicit_current_owner_attestation; not OS isolation"
    else:
        result["observation"] = runtime.continue_stop(app, workspace, agent_id, binding, directory,
                                                     expected_checkpoint=checkpoint)
    return result


def runtime_stop(app, workspace, agent_id, directory=None):
    root = app.root(workspace, agent_id, directory)
    with layout.lock(root, "stop-launch.lock"):
        binding = app.agent(workspace, agent_id)["current"]
        control = layout.local_path(root, "control.json")
        write_json(control, {**read_json(control, {}), "stop": binding})
        signal = backend.cancel(app, workspace, agent_id, str(root), expected_binding=binding)
    return {"monitor_stop_requested": True, "binding": binding, "execution_right_released": False, **signal}


def runtime_launch(app, workspace, agent_id, directory=None):
    root = app.root(workspace, agent_id, directory)
    with layout.lock(root, "stop-launch.lock"):
        snap = app.store(workspace).snapshot()
        binding = app.agent(workspace, agent_id, snap)["current"]
        entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json")) if binding else None
        control = layout.local_path(root, "control.json")
        write_json(control, {**read_json(control, {}), "stop": None})
    if entry and entry["phase"] == "starting":
        return backend.attach(app, workspace, agent_id, str(root), expected_binding=binding)
    return backend.recover(app, workspace, agent_id, str(root), expected_binding=binding)


def message_poll(app, workspace, agent_id, binding, directory=None):
    root = app.root(workspace, agent_id, directory)
    item, entry = app.require_binding(workspace, agent_id, binding)
    if entry["kind"] == "desktop":
        adapter = runtime.Desktop(root, read_json(layout.local_path(root, "runtime.json")), entry["session"])
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
    return software.update_instance(app, workspace, agent_id, directory)


def bridge_switch(app, workspace, agent_id, name, enabled, directory=None):
    root = app.root(workspace, agent_id, directory)
    path = layout.local_path(root, f"bridges/{name}.json")
    value = read_json(path)
    if value is None:
        raise Error("Bridge is not configured.")
    return bridges.configure(app, workspace, agent_id, name, {**value, "enabled": enabled}, directory)


def bridge_status(app, workspace, agent_id, directory=None):
    root = app.root(workspace, agent_id, directory)
    return {p.stem: read_json(p) for p in layout.local_path(root, "bridges/status").glob("*.json")}


def command_map(app):
    messages = Messages(app)
    direct_messages = DirectMessages(app)
    return {
        "backend.start": partial(backend.start, app), "backend.status": partial(backend.status, app),
        "backend.stop": partial(backend.stop, app), "backend.restart": partial(backend.restart, app),
        "backend.log": partial(backend.log, app), "backend.attach": partial(backend.attach, app),
        "backend.cancel": partial(backend.cancel, app),
        "software.status": partial(software.status, app), "software.update": partial(software.update, app),
        "web-courier.connect": partial(web_courier.connect, app),
        "web-courier.status": partial(web_courier.status, app),
        "web-courier.revoke": partial(web_courier.revoke, app),
        "layout.plan": app.layout_plan, "layout.migrate": app.layout_migrate,
        "session.prepare": partial(sessions.prepare, app), "session.open": partial(sessions.open_terminal, app),
        "session.show": partial(sessions.show, app),
        "agent.desktop-project": partial(desktop_projects.plan, app),
        "agent.desktop-discover": partial(desktop_projects.discover, app),
        "agent.desktop-prepare": partial(desktop_projects.prepare, app),
        "agent.desktop-project-save": partial(desktop_projects.save, app),
        "workspace.init": partial(onboarding.init_workspace, app), "workspace.connect": app.workspace_connect,
        "workspace.bootstrap-remote": app.workspace_bootstrap_remote,
        "workspace.read": partial(shared.read, app),
        "workspace.skills": partial(skills.catalog, app),
        "agent.skills": partial(skills.inspect, app),
        "agent.skill-install": partial(skills.apply, app, "install"),
        "agent.skill-update": partial(skills.apply, app, "update"),
        "workspace.list": app.workspace_list, "workspace.show": app.workspace_show,
        "workspace.relation": app.relation,
        "setup.scan": onboarding.scan, "setup.check-git": onboarding.check_git,
        "setup.create": partial(onboarding.create_workspace, app),
        "setup.inspect-codex": harness_config.inspect_codex,
        "setup.inspect-sdk": harness_config.inspect_sdk,
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
        "agent.create": app.create, "agent.list": app.agents, "agent.show": app.show, "agent.history": app.history,
        "agent.connect": app.connect_agent, "agent.configure": app.configure,
        "agent.update": app.update, "agent.versions": app.versions, "agent.promote": app.promote,
        "agent.archive": app.archive, "agent.fork": app.fork, "agent.takeover": app.takeover,
        "checkpoint.create": app.checkpoint, "checkpoint.list": app.checkpoints, "checkpoint.show": app.checkpoint_show,
        "agent.sync": app.sync_agent,
        "agent.start": partial(runtime.start, app), "agent.bind": partial(bind_entry, app),
        "agent.stop": partial(stop_entry, app), "agent.handoff": partial(runtime.handoff_request, app),
        "agent.input": partial(runtime.queue_input, app),
        "agent.capture-desktop": partial(runtime.configure_desktop, app),
        "agent.configure-desktop": partial(runtime.desktop_profile, app),
        "agent.upgrade-tools": partial(upgrade_tools, app),
        "runtime.start": partial(runtime_launch, app), "runtime.stop": partial(runtime_stop, app),
        "runtime.status": app.show,
        "runtime.desktop-observe": partial(runtime.desktop_observe, app),
        "runtime.launch-show": partial(runtime.launch_show, app),
        "runtime.reconcile-create": partial(runtime.reconcile_create, app),
        "runtime.receive-input": partial(runtime.receive_input, app),
        "work.create": app.work_create, "work.list": app.work_list, "work.show": app.work_show,
        "work.update": app.work_update, "work.deliver": app.work_deliver,
        "message.send": messages.send, "message.list": messages.list, "message.show": messages.show,
        "message.receive": messages.receive, "message.poll": partial(message_poll, app),
        "message.operation": messages.operation, "message.reconcile": messages.reconcile, "message.watch": partial(runtime.watch, app),
        "direct-message.record": direct_messages.record, "direct-message.list": direct_messages.list,
        "direct-message.show": direct_messages.show,
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
    # Snapshot objects are in-process read contexts, not command input.
    if "snapshot" in args:
        raise Error(f"Invalid arguments for {command}: unsupported snapshot argument.")
    if command == "agent.start" and "expected_handoff" in args:
        raise Error("expected_handoff is an internal automatic-continuation condition, not command input.")
    if actor and command not in SOFTWARE_OPERATIONS:
        workspace, aid, binding = actor
        if command == "agent.takeover":
            raise Error("Force takeover is an explicit user operation, not an Agent or caretaker operation.")
        if command == "layout.migrate":
            raise Error("Layout migration is an explicit user operation; run it from the user management terminal.")
        if command in ("web-courier.connect", "web-courier.revoke"):
            raise Error("Web Courier connections are explicit user operations; use the user management terminal.")
        # Signatures supply defaults, never authorization. A new agent's ID is a target.
        if "workspace" in signature.parameters:
            args.setdefault("workspace", workspace)
        if "agent_id" in signature.parameters and command != "agent.create":
            args.setdefault("agent_id", aid)
        if command in ("workspace.read", "workspace.skills") and args["workspace"] != workspace:
            raise Conflict("Shared materials must belong to the calling Workspace.")
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
    if actor and command not in READ_ONLY and command not in SOFTWARE_OPERATIONS:
        app.require_binding(workspace, aid, binding, allow_stopping=command in ("checkpoint.create", "agent.stop"))
    return handler(**args)
