"""Workspace health, explicit caretaker grants and one bounded periodic worker.

The report is observation, not a second store of execution rights. Repairs use
existing operations, never clear bindings or replay uncertain business effects.
"""
from __future__ import annotations

import math
from pathlib import Path
import threading
import time

from .util import Conflict, Error, digest, encode, locked, now, read_json, slug, uid, write_json


GRANTABLE = {"agent.start", "runtime.stop", "agent.transfer-profile", "agent.transfer-continue",
             "agent.configure-codex", "agent.configure-sdk", "setup.prepare-instance",
             "maintenance.schedule", "maintenance.repair", "agent.input", "agent.handoff", "message.watch",
             "agent.archive", "agent.sync", "agent.update", "agent.skill-install", "agent.skill-update", "agent.upgrade-tools", "bridge.switch", "asset.write"}


def folder(app, workspace):
    return app.home / "maintenance" / slug(workspace)


def grant(app, workspace, agent_id, commands, targets=None):
    if not isinstance(commands, list) or not all(isinstance(c, str) and c in GRANTABLE for c in commands):
        raise Error("Grant only explicitly listed caretaker operations; grant administration cannot be delegated.")
    targets = [] if targets is None else targets
    if not isinstance(targets, list) or not all(isinstance(t, str) for t in targets):
        raise Error("targets must be instance IDs, or an explicit '*' for this workspace.")
    snap = app.store(workspace).snapshot()
    if agent_id not in snap.json("workspace.json").get("caretakers", {}).values():
        raise Error("Only a registered caretaker instance may receive maintenance grants.")
    app.agent(workspace, agent_id, snap)
    for target in targets:
        if target != "*":
            app.agent(workspace, target, snap)
    path = folder(app, workspace) / "grants.json"
    with locked(path.with_suffix(".lock")):
        grants = read_json(path, {})
        grants[agent_id] = {"commands": sorted(set(commands)), "targets": targets, "updated_at": now()}
        write_json(path, grants)
    return {"agent": agent_id, **grants[agent_id], "scope": "this installation and workspace; not OS isolation"}


def allowed(app, actor, command, arguments):
    workspace, agent_id, binding = actor
    if command not in GRANTABLE or arguments.get("workspace", workspace) != workspace:
        return False
    if command in ("agent.configure-codex", "agent.configure-sdk", "agent.transfer-profile"):
        if arguments.get("executable") or arguments.get("allowed_tools") or arguments.get("allow_http"):
            return False  # Native permissions and consent to plaintext transport stay with the user.
    value = read_json(folder(app, workspace) / "grants.json", {}).get(agent_id, {})
    if command not in value.get("commands", []):
        return False
    target = arguments.get("agent_id", agent_id)
    if command not in ("maintenance.schedule",) and target != agent_id:
        if target not in value.get("targets", []) and "*" not in value.get("targets", []):
            return False
    snap = app.store(workspace).snapshot()
    return agent_id in snap.json("workspace.json").get("caretakers", {}).values()


def _lock_held(path):
    try:
        with locked(path, wait=0):
            return False
    except Conflict:
        return True


def _schedule_observation(app, workspace, schedule):
    try:
        worker_running = _lock_held(app.home / "maintenance/worker.lock")
        if schedule is None:
            state = "not_configured"
        elif not schedule["enabled"]:
            state = "disabled"
        elif (schedule["owner"] != read_json(app.home / "installation.json", {}).get("id")
              or schedule.get("owner_workspace") != workspace):
            state = "not_owned"
        else:
            state = "worker_observed" if worker_running else "worker_not_observed"
    except (OSError, ValueError, KeyError) as exc:
        return {"state": "unavailable", "schedule": schedule, "worker_running": None,
                "error_type": type(exc).__name__}
    return {"state": state, "schedule": schedule, "worker_running": worker_running}


def doctor(app, workspace):
    """Read shared protocol facts and explicitly label this machine's coverage."""
    observed = now()
    issues, local_agents, remote_agents = [], [], []
    observations = {}
    try:
        snap = app.store(workspace).snapshot()
    except (Error, OSError, ValueError, KeyError) as exc:
        return {"state": "unavailable", "observed_at": observed, "issues": [{"code": "store_unavailable"}],
                "coverage": "shared state unavailable; no execution eligibility inferred", "error_type": type(exc).__name__}
    meta = snap.json("workspace.json")
    locations = app.local()["workspaces"][workspace].get("instances", {})
    def issue(code, agent=None, **fields):
        issues.append({"code": code, **({"agent": agent} if agent else {}), **fields})
    for path in snap.entries:
        if not path.startswith("agents/") or not path.endswith(".json"):
            continue
        agent = snap.json(path)
        aid, binding = agent["id"], agent["current"]
        entry = snap.json(f"bindings/{binding}.json") if binding else None
        if binding and (not entry or entry.get("agent") != aid or entry.get("phase") == "released"):
            issue("binding_inconsistent", aid)
        if not locations.get(aid):
            remote_agents.append(aid)
            continue
        root = Path(locations[aid][0])
        local_agents.append(aid)
        if not root.is_dir():
            issue("instance_directory_missing", aid)
            continue
        try:
            control = read_json(root / ".aw-local/control.json", {})
            runtime = read_json(root / ".aw-local/status.json", {})
            running = _lock_held(root / ".aw-local/runner.lock")
            watch = read_json(root / ".aw-local/watch.json")
            if watch is None:
                watch_state = "not_configured"
            elif not watch.get("enabled"):
                watch_state = "disabled"
            else:
                watch_state = "enabled" if binding and watch.get("binding") == binding else "binding_mismatch"
            monitor_stopped = bool(binding and control.get("stop") == binding)
            observations[aid] = {
                "binding": binding, "phase": entry.get("phase") if entry else None,
                "runner_observed": running, "monitor_stop_requested": monitor_stopped,
                "runtime": runtime if binding and runtime.get("binding") == binding else None,
                "watch": {**(watch or {}), "state": watch_state},
            }
            if binding and entry and entry["kind"] != "manual":
                if entry["phase"] == "stopping" and not running:
                    issue("stop_confirmation_not_observed", aid, binding=binding,
                          checkpoint=entry.get("checkpoint"))
                elif not running and not monitor_stopped:
                    issue("runner_not_observed", aid, binding=binding,
                          controller_present=bool(entry.get("controller")))
                if runtime.get("binding") == binding:
                    state = runtime.get("state")
                    if state in ("failed", "connection_failed", "native_stop_unconfirmed"):
                        issue("runtime_fault", aid, state=state)
                    elif state == "shared_read_backoff":
                        issue("runtime_shared_read_backoff", aid, binding=binding)
                    elif state == "stop_observation_unknown":
                        issue("stop_observation_unknown", aid, binding=binding,
                              checkpoint=entry.get("checkpoint"))
            for p in (root / ".aw-local/inputs").glob("*.json"):
                record = read_json(p)
                if record["state"] in ("dispatching", "outcome_unknown"):
                    issue("input_outcome_unknown", aid, operation=record["id"])
                if (record.get("binding") == binding and record.get("purpose") == "initial"
                        and record["state"] == "completed" and not record.get("checkpoint_revision")):
                    issue("initial_checkpoint_pending", aid, operation=record["id"])
            for p in (root / ".aw-local/bridges").glob("*.json"):
                config = read_json(p)
                if config.get("enabled"):
                    state = read_json(p.parent / "status" / p.name, {})
                    if state.get("fatal") or state.get("state") in ("failed", "error", "disconnected"):
                        issue("bridge_fault", aid, binding=binding, bridge=p.stem, generation=config["generation"])
            transfer = read_json(root / ".aw-local/transfer.json")
            if transfer:
                if entry and binding == transfer["target_binding"]:
                    from .transfer import observed_target
                    transfer = observed_target(transfer, entry, root)
                if transfer["state"] != "completed":
                    issue("transfer_pending", aid, operation=transfer["id"], state=transfer["state"])
        except (OSError, ValueError, KeyError) as exc:
            # One damaged local record must not hide the health of other instances.
            issue("local_observation_failed", aid, error_type=type(exc).__name__)
            observations[aid] = {"binding": binding, "state": "unavailable", "error_type": type(exc).__name__}
    for p in (app.home / "operations").glob("*.json"):
        try:
            receipt = read_json(p)
            if receipt.get("workspace") == workspace and receipt.get("state") != "published":
                issue("publication_pending", receipt.get("sender") or receipt.get("receiver"), operation=receipt["id"],
                      state=receipt.get("state", "pending"))
        except (OSError, ValueError, KeyError) as exc:
            issue("publication_record_unreadable", operation=p.stem,
                  scope="installation; workspace ownership unconfirmed", error_type=type(exc).__name__)
    waiting = {}
    for path in snap.entries:
        if path.startswith("message-index/"):
            item = snap.json(path)
            if f"acks/{item['id']}.json" not in snap.entries and item["to"]["workspace"] == meta["locator"]:
                aid = item["to"]["agent"]
                waiting[aid] = waiting.get(aid, 0) + 1
    monitoring = _schedule_observation(app, workspace, snap.json("maintenance/schedule.json"))
    if monitoring["state"] == "worker_not_observed":
        issue("maintenance_worker_not_observed")
    elif monitoring["state"] == "unavailable":
        issue("maintenance_observation_failed", error_type=monitoring["error_type"])
    issues.sort(key=lambda item: (item["code"], item.get("agent", ""), item.get("operation", ""), item.get("bridge", "")))
    partial = bool(remote_agents) or monitoring["state"] == "not_owned"
    return {"state": "degraded" if issues else "partial" if partial else "healthy", "observed_at": observed,
            "revision": snap.revision, "issues": issues, "unacknowledged_notifications": waiting,
            "coverage": {"local": local_agents, "unobserved_remote": remote_agents},
            "local_observations": observations, "maintenance": monitoring}


def repair(app, workspace, agent_id, action, request_id, operation_id=None, bridge=None,
           expected_binding=None, expected_generation=None, expected_checkpoint=None):
    """No arbitrary shell, no automatic reset of a native writer or uncertain send."""
    if action not in ("publication-reconcile", "bridge-retry", "sync-idle", "continue-stop"):
        raise Error("Only publication-reconcile, bridge-retry, sync-idle and continue-stop are repair operations.")
    if action == "publication-reconcile" and not operation_id:
        raise Error("Publication repair requires the original operation_id.")
    if action == "bridge-retry" and not (bridge and expected_binding and expected_generation):
        raise Error("Bridge repair requires bridge, expected_binding and expected_generation.")
    if action == "continue-stop" and not (expected_binding and expected_checkpoint):
        raise Error("Stop continuation requires the original expected_binding and expected_checkpoint.")
    root = app.root(workspace, agent_id)
    path = folder(app, workspace) / "repairs" / (slug(request_id) + ".json")
    payload = {"agent_id": agent_id, "action": action, "operation_id": operation_id, "bridge": bridge,
               "expected_binding": expected_binding, "expected_generation": expected_generation}
    if action == "continue-stop":
        payload["expected_checkpoint"] = expected_checkpoint
    with locked(path.with_suffix(".lock")):
        receipt = read_json(path)
        if receipt:
            if receipt["request"] != payload:
                raise Conflict("Repair request ID belongs to a different action.")
            return _verify_repair(app, workspace, path, receipt)
        receipt = {"id": request_id, "request": payload, "state": "attempting", "created_at": now()}
        if action == "publication-reconcile":
            source = read_json(app.home / "operations" / (slug(operation_id) + ".json"))
            if not source or source["workspace"] != workspace or (source.get("sender") or source.get("receiver")) != agent_id:
                raise Error("Publication receipt is not owned by the selected workspace and instance.")
        elif action == "bridge-retry":
            app.require_binding(workspace, agent_id, expected_binding)
            control = read_json(root / ".aw-local/control.json", {})
            if control.get("stop") == expected_binding or control.get("handoff") == expected_binding:
                raise Conflict("An intentionally stopped entry cannot be restarted by maintenance.")
            config = read_json(root / ".aw-local/bridges" / (slug(bridge) + ".json"))
            if not config or not config.get("enabled") or config["generation"] != expected_generation:
                raise Conflict("Bridge configuration changed or was disabled; inspect it again.")
        elif action == "sync-idle" and app.agent(workspace, agent_id)["current"]:
            raise Conflict("Sync repair only runs without an active entry; handoff first.")
        write_json(path, receipt)
        try:
            if action == "publication-reconcile":
                from .messages import Messages
                result = Messages(app).reconcile(operation_id)
            elif action == "bridge-retry":
                from .bridges import configure
                result = configure(app, workspace, agent_id, bridge, config, expected_generation=expected_generation)
            elif action == "continue-stop":
                from .runtime import continue_stop
                result = continue_stop(app, workspace, agent_id, expected_binding,
                                       expected_checkpoint=expected_checkpoint)
            else:
                # Prevent a local managed writer from entering during the file update.
                with locked(root / ".aw-local/runner.lock", wait=0):
                    if app.agent(workspace, agent_id)["current"]:
                        raise Conflict("An entry was acquired before sync repair; no files were changed.")
                    result = app.sync_agent(workspace, agent_id)
        except (Error, OSError, ValueError, KeyError) as exc:
            receipt.update(state="outcome_unknown", error_type=type(exc).__name__)
            write_json(path, receipt)
            raise
        # Persist the effect before a separate observation can fail or the process exits.
        receipt.update(state="applied", result=result)
        write_json(path, receipt)
        return _verify_repair(app, workspace, path, receipt)


def _verify_repair(app, workspace, path, receipt):
    stop_repair = receipt["request"]["action"] == "continue-stop"
    if not stop_repair and (receipt["state"] != "applied"
            or receipt.get("verification", {}).get("state") not in (None, "unavailable")):
        return receipt
    try:
        receipt["verification"] = doctor(app, workspace)
        if stop_repair:
            # Observe the fixed request, even after a successor owns the instance.
            binding = receipt["request"]["expected_binding"]
            snap = app.store(workspace).snapshot()
            entry = snap.json(f"bindings/{binding}.json")
            stop = {"binding": binding, "state": "not_observed", "observed_at": now()}
            if entry and entry["agent"] == receipt["request"]["agent_id"]:
                stop.update(state=entry["phase"], checkpoint=entry.get("checkpoint"), session=entry.get("session"))
                if entry.get("checkpoint") != receipt["request"]["expected_checkpoint"]:
                    stop.update(state="request_changed", phase=entry["phase"])
            receipt["verification"]["stop"] = stop
    except (Error, OSError, ValueError, KeyError) as exc:
        receipt["verification"] = {"state": "unavailable", "observed_at": now(),
                                   "error_type": type(exc).__name__}
    # Observe separately; never repeat the saved effect.
    write_json(path, receipt)
    return receipt


def installation_id(app):
    path = app.home / "installation.json"
    with locked(path.with_suffix(".lock")):
        identity = read_json(path)
        if identity is None:
            identity = {"id": uid("host-")}
            write_json(path, identity)
    return identity["id"]


def schedule(app, workspace, enabled, interval=300, notify=False):
    if type(enabled) is not bool or type(notify) is not bool or not isinstance(interval, (int, float)) or not math.isfinite(interval) or interval < 30:
        raise Error("Schedule requires booleans and a finite interval of at least 30 seconds.")
    store = app.store(workspace)
    snap = store.snapshot()
    owner = installation_id(app)
    path = "maintenance/schedule.json"
    old = snap.json(path)
    if old and old["enabled"] and old["owner"] != owner and enabled:
        raise Conflict("Another installation owns the active schedule; explicitly disable it before moving execution.")
    value = {"owner": owner, "owner_workspace": workspace, "enabled": enabled, "interval": interval, "notify": notify,
             "generation": uid("schedule-"), "updated_at": now()}
    store.change("main", {path: encode(value)}, {path: snap.entries.get(path)}, "Configure maintenance schedule")
    write_json(folder(app, workspace) / "schedule.json", value)
    return {**value, "execution": "while aw serve or aw maintenance run is running; no model started"}


def tick(app, workspace):
    """At most one observation per due interval; no catch-up model storm after sleep."""
    root = folder(app, workspace)
    config = read_json(root / "schedule.json")
    if not config or not config["enabled"]:
        return {"state": "disabled"}
    with locked(root / "tick.lock", wait=0):
        run = read_json(root / "run.json", {})
        if run.get("generation") == config["generation"] and time.time() < run.get("next_due", 0):
            return {"state": "not_due"}
        # Reserve the next check before network I/O, including on read failure.
        run.update(generation=config["generation"], last_attempt=now(),
                   next_due=time.time() + config["interval"])
        write_json(root / "run.json", run)
        try:
            snap = app.store(workspace).snapshot()
            shared = snap.json("maintenance/schedule.json")
            if (not shared or not shared["enabled"] or shared["owner"] != installation_id(app)
                    or shared.get("owner_workspace") != workspace):
                return {"state": "schedule_not_owned"}
            if shared["generation"] != config["generation"]:
                write_json(root / "schedule.json", shared)
                return {"state": "schedule_changed"}
            report = doctor(app, workspace)
        except (Error, OSError, ValueError, KeyError) as exc:
            run.update(error_type=type(exc).__name__, state="check_unavailable")
            write_json(root / "run.json", run)
            return run
        fingerprint = digest(encode(report["issues"]))
        run.update(last_run=now(), report=report, state="checked")
        run.pop("error_type", None)
        if not report["issues"]:
            run.pop("notice", None)
        elif config["notify"]:
            sentinel = snap.json("workspace.json").get("caretakers", {}).get("sentinel")
            binding = app.agent(workspace, sentinel)["current"] if sentinel else None
            notice = run.get("notice", {})
            if (notice.get("fingerprint"), notice.get("binding")) != (fingerprint, binding):
                run["notice"] = {"id": uid("health-"), "fingerprint": fingerprint,
                                 "agent": sentinel, "binding": binding, "state": "pending"}
            write_json(root / "run.json", run)
            if sentinel and binding and run["notice"]["state"] == "pending":
                # A user may disable/move the schedule while diagnostics are running.
                current = app.store(workspace).snapshot().json("maintenance/schedule.json")
                if current != shared:
                    return {"state": "schedule_changed", "report": report}
                from .runtime import queue_input
                app.require_binding(workspace, sentinel, binding)
                queue_input(app, workspace, sentinel,
                            "Workspace 巡检发现异常。读取 maintenance.status；需要诊断时发送 Message 给登记的 Maintainer。"
                            "只在授权范围内修复；禁止重放不明业务。",
                            purpose="maintenance", request_id=run["notice"]["id"], expected_binding=binding)
                run["notice"]["state"] = "queued"
        write_json(root / "run.json", run)
        return run


def status(app, workspace):
    root = folder(app, workspace)
    snap = app.store(workspace).snapshot()
    monitoring = _schedule_observation(app, workspace, snap.json("maintenance/schedule.json"))
    run = read_json(root / "run.json")
    notice = run.get("notice") if run else None
    if notice:
        # Queue acceptance and the original native input's outcome are separate facts.
        sentinel = notice.get("agent") or snap.json("workspace.json").get("caretakers", {}).get("sentinel")
        locations = app.local()["workspaces"][workspace].get("instances", {}).get(sentinel, [])
        notice["input_state"] = "not_observed"
        if locations:
            try:
                path = Path(locations[0]) / ".aw-local/inputs" / (slug(notice["id"]) + ".json")
                record = read_json(path)
                if (record and record["id"] == notice["id"] and record["binding"] == notice["binding"]
                        and record["purpose"] == "maintenance"):
                    notice["input_state"] = record["state"]
            except (OSError, ValueError, KeyError) as exc:
                notice.update(input_state="unavailable", error_type=type(exc).__name__)
    return {**monitoring, "grantable_commands": sorted(GRANTABLE), "local_run": run,
            "worker_error": read_json(root / "worker-error.json"), "grants": read_json(root / "grants.json", {})}


def run(app, stop_event=None):
    stop_event = stop_event or threading.Event()
    try:
        with locked(app.home / "maintenance/worker.lock", wait=0):
            while not stop_event.is_set():
                for entry in app.workspace_list():
                    workspace = entry["alias"]
                    try:
                        tick(app, workspace)
                    except (Error, OSError, ValueError, KeyError) as exc:
                        write_json(folder(app, workspace) / "worker-error.json", {
                            "observed_at": now(), "error_type": type(exc).__name__, "retry": "next scheduled check; no business replay"})
                stop_event.wait(5)
    except Conflict:
        return  # A second workbench must not start a duplicate worker.
