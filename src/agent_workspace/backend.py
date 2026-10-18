"""One local AW home owns the HTTP service, maintenance and Runner threads."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import webbrowser

from .maintenance import installation_id
from . import layout, software
from .util import Conflict, Error, LockBusy, RetryableRead, Unavailable, Uncertain, locked, now, read_json, write_json


def _lock_held(app):
    try:
        with locked(app.home / "backend/service.lock", wait=0):
            return False
    except LockBusy:
        return True


def _read_connection(app):
    # Windows readers can deny replacement of this file. Keep the snapshot
    # closed before releasing the same lock used by the publishing process.
    with locked(app.home / "backend/connection.lock"):
        return read_json(app.home / "backend/connection.json", {})


def _request(app, command, arguments=None):
    connection = _read_connection(app)
    if not connection:
        raise Unavailable("The local backend is not ready; use backend start.")
    url = f"http://127.0.0.1:{connection['port']}/api/execute"
    request = urllib.request.Request(url, data=json.dumps({"command": command, "arguments": arguments or {}}).encode(),
        headers={"Authorization": "Bearer " + connection["token"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30 if command == "backend.attach" else 5) as response:
            return json.load(response)["result"]
    except urllib.error.HTTPError as exc:
        reply = json.load(exc)
        kind = Uncertain if reply.get("code") == "outcome_unknown" else Conflict if exc.code == 409 else Error
        raise kind(reply.get("error", "The local backend rejected the request.")) from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        if command in ("backend.status", "backend.log"):
            raise Unavailable("The local backend could not be observed.") from exc
        raise Uncertain("Backend request result unknown; inspect this home and the original Binding before retrying.") from exc


class Backend:
    def __init__(self, app, http):
        self.app, self.http = app, http
        self.stop_event = threading.Event()
        self.lock = threading.RLock()
        self.runners = {}
        self.threads = []
        self.resume_notes = []
        self.watches = {}
        self.watch_failure = None
        self.software = None
        self.restart_requested = False
        self.open_after_restart = False
        self.maintenance = threading.Thread(target=self._maintenance, name="aw-maintenance")
        self.restore = threading.Thread(target=self._restore, name="aw-restore")
        self.watch = threading.Thread(target=self._watch, name="aw-watch")

    def _worker_ids(self, workspace, agent_id):
        snap = self.app.store(workspace).snapshot()
        owner = self.app.agent(workspace, agent_id, snap)
        if owner.get("worker_id") is None:
            return [None]
        return [item["id"] for item in self.app.workers(workspace, agent_id, archived=False, snapshot=snap)]

    @staticmethod
    def _runner_key(root, worker_id):
        return (root, worker_id) if worker_id is not None else root

    def _maintenance(self):
        from .maintenance import run
        run(self.app, self.stop_event)

    def start(self):
        self.software = software.update(self.app)
        self.maintenance.start()
        self.restore.start()
        self.watch.start()

    def _watch(self):
        failures = 0
        while not self.stop_event.is_set():
            try:
                self._check_watches()
            except (Error, OSError, ValueError) as exc:
                failures += 1
                retry = isinstance(exc, RetryableRead) and failures < 5
                self.watch_failure = {"state": "check_backoff" if retry else "check_paused",
                                      "attempts": failures, "reason": str(exc), "error_code": getattr(exc, "code", None),
                                      "observed_at": now()}
                if not retry or self.stop_event.wait(min(2 ** failures, 30)):
                    return
                continue
            failures = 0
            self.watch_failure = None
            self.stop_event.wait(.5)

    def _check_watches(self):
        from .messages import Messages
        seen = set()
        for access in self.app.workspace_list():
            workspace = access["alias"]
            copies = self.app.local()["workspaces"][workspace].get("instances", {})
            for agent_id, locations in copies.items():
                if self.stop_event.is_set():
                    return
                for worker_id in self._worker_ids(workspace, agent_id):
                    for location in locations:
                        root = Path(location).resolve()
                        key = (workspace, agent_id, root, worker_id)
                        seen.add(key)
                        with self.lock:
                            previous = self.watches.get(key, {})
                            task = self.runners.get(self._runner_key(root, worker_id))
                        record = {"workspace": workspace, "agent_id": agent_id, "worker_id": worker_id, "directory": str(root)}
                        try:
                            setting = read_json(layout.local_path(root, "watch.json", worker_id), {"enabled": False})
                            if previous.get("changed_at") != setting.get("changed_at"):
                                previous = {}
                            binding = setting.get("binding")
                            record.update(binding=binding, changed_at=setting.get("changed_at"))
                            if not setting.get("enabled"):
                                record["state"] = "disabled"
                            elif previous.get("changed_at") == setting.get("changed_at") and previous.get("state") == "check_paused":
                                continue
                            elif previous.get("changed_at") == setting.get("changed_at") and time.monotonic() < previous.get("next_check", 0):
                                continue
                            else:
                                snap = self.app.store(workspace).snapshot()
                                owner = self.app.agent(workspace, agent_id, snap, worker_id=worker_id)
                                entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
                                control = read_json(layout.local_path(root, "control.json", worker_id), {})
                                if owner["current"] != binding or not entry or entry["phase"] != "active":
                                    record["state"] = "entry_inactive"
                                elif control.get("stop") == binding:
                                    record["state"] = "user_paused"
                                elif control.get("handoff") == binding:
                                    record["state"] = "handoff_paused"
                                elif task and task["binding"] == binding and task["thread"].is_alive():
                                    record["state"] = "runner_managed"
                                else:
                                    # Checking the formal queue needs no model or native writer.
                                    # Actual notification remains the qualified Runner's job.
                                    record.update(state="checked", checked_at=now(),
                                        poll=Messages(self.app).poll(workspace, agent_id, binding, directory=str(root)))
                                record["next_check"] = time.monotonic() + setting.get("interval", 5)
                        except (Error, OSError, ValueError, TypeError) as exc:
                            attempts = previous.get("attempts", 0) + 1
                            retry = isinstance(exc, RetryableRead) and attempts < 5
                            record.update(state="check_backoff" if retry else "check_paused", attempts=attempts,
                                reason=str(exc), error_code=getattr(exc, "code", None),
                                next_check=time.monotonic() + min(2 ** attempts, 30))
                        with self.lock:
                            self.watches[key] = record
        with self.lock:
            self.watches = {key: record for key, record in self.watches.items() if key in seen}

    def _restore(self):
        for access in self.app.workspace_list():
            if self.stop_event.is_set():
                return
            workspace = access["alias"]
            copies = self.app.local()["workspaces"][workspace].get("instances", {})
            for agent_id in copies:
                if self.stop_event.is_set():
                    return
                for worker_id in self._worker_ids(workspace, agent_id):
                    try:
                        result = self.recover(workspace, agent_id, worker_id=worker_id)
                        if result.get("reason"):
                            self.resume_notes.append({"workspace": workspace, "agent_id": agent_id, "worker_id": worker_id, **result, "observed_at": now()})
                    except (Error, OSError, ValueError, KeyError) as exc:
                        self.resume_notes.append({"workspace": workspace, "agent_id": agent_id, "worker_id": worker_id, "reason": str(exc), "observed_at": now()})

    def recover(self, workspace, agent_id, directory=None, expected_binding=None, worker_id=None):
        """Reconnect one confirmed session; preserve attempted inputs and user pauses."""
        snap = self.app.store(workspace).snapshot()
        from .runtime import _entry_owner
        snap, owner, worker_id = _entry_owner(self.app, workspace, agent_id, worker_id,
                                             binding=expected_binding, snapshot=snap)
        binding = owner.get("current")
        if expected_binding is not None and binding != expected_binding:
            raise Conflict("The original Binding changed before recovery.")
        result = {"binding": binding, "worker_id": worker_id, "state": "recovery_blocked"}
        if not binding or owner["archived"]:
            return {**result, "reason_code": "no_current_entry", "reason": "No current execution entry to observe."}
        entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
        result.update(session=entry.get("session"), checkpoint=entry.get("checkpoint"))
        execution = entry.get("execution")
        if not execution:
            return {**result, "reason_code": "execution_source_missing",
                    "reason": "Execution source is missing; a local directory does not establish ownership."}
        if execution["installation_id"] != installation_id(self.app):
            return {**result, "reason_code": "different_execution_environment", "reason": "The original entry belongs to another installation."}
        if directory is not None and Path(directory).resolve() != Path(execution["directory"]).resolve():
            raise Conflict("Recovery must use the original execution directory.")
        root = self.app.root(workspace, agent_id, execution["directory"])
        local = read_json(layout.local_path(root, "entry.json", worker_id), {})
        control = read_json(layout.local_path(root, "control.json", worker_id), {})
        if not isinstance(local, dict) or not isinstance(control, dict):
            raise Error("Local entry or control record is invalid; inspect this original copy.")
        if local.get("binding") != binding:
            return {**result, "reason_code": "local_entry_mismatch", "reason": "This copy is not attached to the original entry."}
        if control.get("stop") == binding or (entry["phase"] != "stopping" and control.get("handoff") == binding):
            return {**result, "state": "recovery_paused", "reason_code": "user_paused",
                    "reason": "The original observation was paused or handed off; it was not restarted."}
        if entry["phase"] not in ("active", "stopping") or not entry.get("session"):
            return {**result, "reason_code": "native_session_unconfirmed",
                    "reason": "No confirmed native session; no creation or model input was repeated."}
        with self.lock:
            task = self.runners.get(self._runner_key(root, worker_id))
            if task and task["binding"] == binding and task["thread"].is_alive():
                return {**result, "state": "runner_present", "pid": os.getpid()}
        if entry["phase"] != "stopping" and entry.get("controller"):
            return {**result, "reason_code": "original_controller_remains",
                    "reason": "Original controller remains; recovery cannot claim or replace it."}
        if entry["kind"] == "manual":
            return {**result, "reason_code": "independent_observation_unavailable",
                    "reason": "Manual entry has no automatic observer; use its actual session to receive."}
        if entry["phase"] == "stopping":
            from .runtime import continue_stop
            return continue_stop(self.app, workspace, agent_id, binding, str(root),
                                 expected_checkpoint=entry["checkpoint"], worker_id=worker_id)
        if entry["kind"] == "desktop":
            config = local["config"] if worker_id is not None else read_json(layout.local_path(root, "runtime.json"), {})
            if config.get("kind") != "desktop" or not all(config.get(key) for key in ("command", "pipe_path", "caller_thread")):
                return {**result, "reason_code": "desktop_connection_missing", "reason": "The original Desktop control connection is not captured."}
            from .runtime import desktop_observe
            native = desktop_observe(self.app, workspace, agent_id, str(root), worker_id=worker_id)
            if not native["local_session_confirmed"]:
                return {**result, "reason_code": native.get("unknown_reason", "native_session_unconfirmed"),
                        "reason": "The original Desktop session or working directory could not be confirmed."}
            if native["binding"] != binding or native["session"] != entry["session"]:
                raise Conflict("The original Desktop entry changed during recovery observation.")
        # Native observation can take time. Honor a pause that arrived during
        # that read, before creating a new observer for the original entry.
        with layout.lock(root, "files.lock", worker_id=worker_id):
            control = read_json(layout.local_path(root, "control.json", worker_id), {})
            if control.get("stop") == binding or control.get("handoff") == binding:
                return {**result, "state": "recovery_paused", "reason_code": "user_paused",
                        "reason": "The original observation was paused during recovery."}
            return {**result, **self.attach(workspace, agent_id, str(root), expected_binding=binding, worker_id=worker_id)}

    def attach(self, workspace, agent_id, directory=None, stop_binding=None, expected_binding=None, recovery=False, worker_id=None):
        from .runtime import Runner, _released_stop
        if recovery:
            if stop_binding is not None:
                raise Error("Recover one original entry; do not replace its stop request.")
            return self.recover(workspace, agent_id, directory, expected_binding, worker_id)
        root = self.app.root(workspace, agent_id, directory)
        software.require_ready(root)
        snap = self.app.store(workspace).snapshot()
        from .runtime import _entry_owner
        snap, owner, worker_id = _entry_owner(self.app, workspace, agent_id, worker_id,
            binding=expected_binding or stop_binding, snapshot=snap)
        if stop_binding:
            original = snap.json(layout.shared_path(snap, f"bindings/{stop_binding}.json"))
            if original and original["phase"] == "released":
                return _released_stop(snap, agent_id, stop_binding, original)
        local = read_json(layout.local_path(root, "entry.json", worker_id), {})
        binding = local.get("binding")
        if not binding:
            raise Error("No local entry; use agent start before starting its Runner.")
        if expected_binding and binding != expected_binding:
            raise Conflict("The original Binding changed before its backend request arrived.")
        entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
        if owner["current"] != binding or owner["archived"] or entry["phase"] not in ("starting", "active", "stopping"):
            raise Conflict("Only the current starting, active or stopping Binding can have a Runner.")
        if stop_binding and (stop_binding != binding or entry["phase"] != "stopping"):
            raise Conflict("Only the original stopping request can be observed.")
        if entry["phase"] == "starting" and not entry.get("session"):
            launch = read_json(layout.local_path(root, "launch.json", worker_id), {})
            if launch.get("binding") == binding and launch.get("attempted"):
                raise Conflict("The original native creation is unresolved; inspect and reconcile its launch receipt.")
        execution = entry.get("execution")
        if execution and (execution["installation_id"] != installation_id(self.app)
                          or Path(execution["directory"]).resolve() != root):
            raise Conflict("This Binding belongs to another execution environment or local copy.")
        with self.lock:
            if self.stop_event.is_set():
                raise Conflict("The backend is stopping; no Runner was started.")
            key = self._runner_key(root, worker_id)
            previous = self.runners.get(key)
            if previous and previous["thread"].is_alive() and previous["thread"] is not threading.current_thread():
                if previous["binding"] != binding:
                    raise Conflict("The original Runner is still exiting; inspect it before starting a successor.")
                return {"pid": os.getpid(), "binding": binding, "state": "runner_present"}
            runner = Runner(self.app, workspace, agent_id, str(root), stop_binding=stop_binding,
                            expected_binding=binding, worker_id=worker_id)
            task = {"runner": runner, "workspace": workspace, "agent_id": agent_id, "binding": binding, "worker_id": worker_id}
            thread = threading.Thread(target=self._run_runner, args=(task,), name="aw-runner-" + agent_id + ("-" + worker_id if worker_id else ""))
            task["thread"] = thread
            self.runners[key] = task
            self.threads = [item for item in self.threads if item["thread"].is_alive()]
            self.threads.append(task)
            thread.start()
            return {"pid": os.getpid(), "binding": binding, "state": "starting_runner"}

    def _run_runner(self, task):
        runner = task["runner"]
        try:
            runner.run()
        except Exception:
            # A task failure belongs to this Runner; it must not terminate other Agents.
            with layout.lock(runner.root, "files.lock", worker_id=runner.worker_id):
                log_path = layout.local_path(runner.root, "runner.log", runner.worker_id)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with log_path.open("a", encoding="utf-8") as log:
                    log.write(now() + "\n" + traceback.format_exc() + "\n")
        else:
            if runner.stop_event.is_set():
                with layout.lock(runner.root, "files.lock", worker_id=runner.worker_id):
                    runner.status(state="monitor_stopped", entry_automatically_released=False)

    def cancel(self, root, binding, worker_id=None):
        with self.lock:
            task = self.runners.get(self._runner_key(root, worker_id))
            if task and task["binding"] == binding and task["thread"].is_alive():
                task["runner"].stop_event.set()
                return True
        return False

    def status(self):
        with self.lock:
            tasks = list(self.runners.items())
            watches = [{key: value for key, value in record.items() if key != "next_check"}
                       for record in self.watches.values()]
        runners = []
        for key, task in tasks:
            root = key[0] if isinstance(key, tuple) else key
            worker_id = task.get("worker_id")
            try:
                observation = read_json(layout.local_path(root, "status.json", worker_id), {})
                if not isinstance(observation, dict):
                    raise ValueError("Runtime observation is not an object.")
            except (OSError, ValueError) as exc:
                observation = {"state": "unknown", "binding": task["binding"],
                               "unknown_reason": "runtime_observation_failed", "error_type": type(exc).__name__}
            if observation.get("binding") != task["binding"]:
                observation = {"state": "unknown", "reason": "No observation for this Binding yet."}
            runners.append({"workspace": task["workspace"], "agent_id": task["agent_id"], "worker_id": worker_id, "directory": str(root),
                            "binding": task["binding"], "runner_alive": task["thread"].is_alive(), "runtime": observation})
        return {"state": "stopping" if self.stop_event.is_set() else "running", "running": True,
                "ready": not self.stop_event.is_set(), "pid": os.getpid(), "home": str(self.app.home),
                "url": f"http://127.0.0.1:{self.http.server_port}/", "observed_at": now(),
                "maintenance_alive": self.maintenance.is_alive(), "restoring": self.restore.is_alive(),
                "watch_alive": self.watch.is_alive(), "watches": watches,
                "watch_failure": self.watch_failure,
                "software": self.software,
                "runners": runners, "resume_notes": list(self.resume_notes)}

    def request_stop(self, restart=False, open_app=False):
        with self.lock:
            self.restart_requested = self.restart_requested or restart
            self.open_after_restart = self.open_after_restart or open_app
            self.stop_event.set()
            for task in self.threads:
                task["runner"].stop_event.set()
        self.http.stopping.set()
        threading.Thread(target=self.http.shutdown, name="aw-http-stop", daemon=True).start()
        return {"stop_requested": True, "restart_requested": self.restart_requested,
                "running": True, "ready": False, "agent_bindings_released": False,
                "native_chat_shutdown_requested": False}

    def close(self):
        self.stop_event.set()
        with self.lock:
            for task in self.threads:
                task["runner"].stop_event.set()
        if self.maintenance.ident is not None:
            self.maintenance.join()
        if self.restore.ident is not None:
            self.restore.join()
        if self.watch.ident is not None:
            self.watch.join()
        for task in self.threads:
            task["thread"].join()


def status(app):
    manager = getattr(app, "backend", None)
    if manager:
        return manager.status()
    if not _lock_held(app):
        return {"state": "stopped", "running": False, "ready": False, "home": str(app.home), "observed_at": now()}
    try:
        return _request(app, "backend.status")
    except (Unavailable, Error, OSError, ValueError):
        return {"state": "unknown", "running": True, "ready": False, "home": str(app.home),
                "unknown_reason": "Backend lock is held but its control endpoint could not be read.", "observed_at": now()}


def start(app, port=None, open_app=False):
    manager = getattr(app, "backend", None)
    if manager:
        return {**manager.status(), "start_requested": False}
    with locked(app.home / "backend/start.lock"):
        if _lock_held(app):
            result = status(app)
            if open_app and result["ready"]:
                connection = _read_connection(app)
                webbrowser.open(result["url"] + "#token=" + connection["token"])
            return {**result, "start_requested": False}
        connection = _read_connection(app)
        port = port if port is not None else connection.get("port", 8765)
        args = [sys.executable, "-m", "agent_workspace", "--home", str(app.home), "backend", "run", "--port", str(port)]
        if open_app:
            args.append("--open")
        env = {key: value for key, value in os.environ.items()
               if key not in ("AW_HOME", "AW_WORKSPACE", "AW_AGENT", "AW_BINDING", "CODEX_THREAD_ID")}
        options = {"creationflags": 0x08000000} if os.name == "nt" else {"start_new_session": True}
        with (app.home / "backend/backend.log").open("ab") as log:
            process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log, env=env, **options)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise Error("Backend exited during startup; inspect backend log.")
            result = status(app)
            if result["ready"]:
                return {**result, "start_requested": True}
            time.sleep(0.1)
        return {"state": "starting", "running": None, "ready": False, "pid": process.pid,
                "home": str(app.home), "start_requested": True, "observed_at": now()}


def stop(app):
    manager = getattr(app, "backend", None)
    if manager:
        return manager.request_stop()
    if not _lock_held(app):
        return {**status(app), "stop_requested": False, "agent_bindings_released": False}
    return _request(app, "backend.stop")


def restart(app, port=None, open_app=False):
    manager = getattr(app, "backend", None)
    if manager:
        if port is not None and port != manager.http.server_port:
            raise Error("Restart keeps the current port; stop then start to change it.")
        return manager.request_stop(restart=True, open_app=open_app)
    if not _lock_held(app):
        return {**start(app, port, open_app), "restart_requested": True}
    return _request(app, "backend.restart", {"port": port, "open_app": open_app})


def attach(app, workspace, agent_id, directory=None, stop_binding=None, expected_binding=None, recovery=False, worker_id=None):
    if recovery:
        if stop_binding is not None:
            raise Error("Recover one original entry; do not replace its stop request.")
        return recover(app, workspace, agent_id, directory, expected_binding, worker_id)
    root = app.root(workspace, agent_id, directory)
    from .runtime import _entry_owner
    _, owner, worker_id = _entry_owner(app, workspace, agent_id, worker_id, binding=expected_binding or stop_binding)
    expected_binding = expected_binding or stop_binding or owner["current"]
    manager = getattr(app, "backend", None)
    if manager:
        return manager.attach(workspace, agent_id, str(root), stop_binding, expected_binding, worker_id=worker_id)
    start(app)
    return _request(app, "backend.attach", {"workspace": workspace, "agent_id": agent_id,
        "directory": str(root), "stop_binding": stop_binding, "expected_binding": expected_binding, "worker_id": worker_id})


def recover(app, workspace, agent_id, directory=None, expected_binding=None, worker_id=None):
    manager = getattr(app, "backend", None)
    if manager:
        return manager.recover(workspace, agent_id, directory, expected_binding, worker_id)
    start(app)
    return _request(app, "backend.attach", {"workspace": workspace, "agent_id": agent_id,
        "directory": directory, "expected_binding": expected_binding, "recovery": True, "worker_id": worker_id})


def cancel(app, workspace, agent_id, directory=None, expected_binding=None, worker_id=None):
    root = app.root(workspace, agent_id, directory)
    from .runtime import _entry_owner
    _, _, worker_id = _entry_owner(app, workspace, agent_id, worker_id, binding=expected_binding)
    manager = getattr(app, "backend", None)
    if manager:
        return {"observer_signalled": manager.cancel(root, expected_binding, worker_id)}
    if not _lock_held(app):
        return {"observer_signalled": False}
    return _request(app, "backend.cancel", {"workspace": workspace, "agent_id": agent_id,
        "directory": str(root), "expected_binding": expected_binding, "worker_id": worker_id})


def log(app, workspace=None, agent_id=None, directory=None, lines=100, worker_id=None):
    if not isinstance(lines, int) or not 1 <= lines <= 500:
        raise Error("Read 1–500 log lines.")
    if agent_id:
        if not workspace:
            raise Error("Choose the Runner's workspace.")
        root = app.root(workspace, agent_id, directory)
        from .runtime import _entry_owner
        _, _, worker_id = _entry_owner(app, workspace, agent_id, worker_id)
        path = layout.local_path(root, "runner.log", worker_id)
        source = {"kind": "runner", "workspace": workspace, "agent_id": agent_id, "worker_id": worker_id, "directory": str(root)}
    else:
        if directory or worker_id is not None:
            raise Error("Select an Agent before choosing its local copy.")
        path = app.home / "backend/backend.log"
        source = {"kind": "backend", "home": str(app.home)}
    content, truncated = "", False
    if path.exists():
        with path.open("rb") as stream:
            size = stream.seek(0, os.SEEK_END)
            offset = max(0, size - 65536)
            stream.seek(offset)
            content = stream.read().decode("utf-8", errors="replace")
            if offset:
                content = content.partition("\n")[2]
        content_lines = content.splitlines()
        truncated = bool(offset) or len(content_lines) > lines
        content = "\n".join(content_lines[-lines:])
    connection = _read_connection(app)
    if connection.get("token"):
        content = content.replace(connection["token"], "[redacted]")
    content = re.sub(r"(https?://)[^/@\s]+@", r"\1[redacted]@", content)
    content = re.sub(r"(?i)(Bearer\s+|[?&#]token=)[^\s&]+", r"\1[redacted]", content)
    return {"source": source, "observed_at": now(), "exists": path.exists(), "truncated": truncated, "content": content}


def run(app, port=None, open_app=False, setup=False):
    from .server import make_server
    with locked(app.home / "backend/service.lock", wait=0):
        connection = _read_connection(app)
        port = port if port is not None else connection.get("port", 8765)
        http = make_server(app, port, connection.get("token"))
        manager = Backend(app, http)
        app.backend = manager
        with locked(app.home / "backend/connection.lock"):
            write_json(app.home / "backend/connection.json", {"port": http.server_port, "pid": os.getpid(),
                       "token": http.control_token, "started_at": now()})
        url = f"http://127.0.0.1:{http.server_port}/" + ("setup" if setup else "") + "#token=" + http.control_token
        print("本机工作台（地址包含控制凭据，请勿分享）：\n" + url, flush=True)
        try:
            with (app.home / "backend/backend.log").open("a", encoding="utf-8") as log_file:
                log_file.write(f"{now()} Backend started pid={os.getpid()} port={http.server_port}\n")
            manager.start()
            if open_app:
                webbrowser.open(url)
            http.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            manager.stop_event.set()
            http.server_close()
            manager.close()
            del app.backend
            with (app.home / "backend/backend.log").open("a", encoding="utf-8") as log_file:
                log_file.write(f"{now()} Backend stopped pid={os.getpid()} restart={manager.restart_requested}\n")
    if manager.restart_requested:
        start(app, http.server_port, manager.open_after_restart)
