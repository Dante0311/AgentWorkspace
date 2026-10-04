"""Install a built wheel in a clean temporary environment, without source imports."""
from pathlib import Path
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request


@contextmanager
def running_workbench(aw, home, cwd, env):
    """Use the installed CLI and real HTTP; keep control tokens out of test output."""
    process = subprocess.Popen([str(aw), "--home", str(home), "serve", "--port", "0"],
                               cwd=cwd, env=env, text=True, encoding="utf-8",
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = queue.Queue()

    def read_output():
        for line in process.stdout:
            output.put(line)
        output.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    try:
        deadline = time.monotonic() + 30
        while True:
            line = output.get(timeout=max(.01, deadline - time.monotonic()))
            if line is None:
                raise RuntimeError("Installed workbench exited before announcing its endpoint.")
            if line.startswith("http://127.0.0.1:"):
                url = urllib.parse.urlsplit(line.strip())
                token = urllib.parse.parse_qs(url.fragment)["token"][0]
                break
        base = f"{url.scheme}://{url.netloc}"

        def request(command=None, arguments=None):
            payload = None if command is None else json.dumps({
                "command": command, "arguments": arguments or {}}).encode()
            headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
            req = urllib.request.Request(base + ("/api/state" if payload is None else "/api/execute"),
                                         data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as response:
                value = json.load(response)
            assert value["ok"], value
            return value["result"]

        yield request
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        reader.join(timeout=5)
        process.stdout.close()
        assert not reader.is_alive()


def main() -> None:
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else "dist").resolve()
    wheels = sorted(directory.glob("git_native_agent_workspace-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"Expected one project wheel in {directory}, found {len(wheels)}")

    with tempfile.TemporaryDirectory(prefix="aw-wheel-") as temporary:
        root = Path(temporary)
        environment = root / "venv"
        binary = environment / ("Scripts" if os.name == "nt" else "bin")
        python = binary / ("python.exe" if os.name == "nt" else "python")
        aw = binary / ("aw.exe" if os.name == "nt" else "aw")
        env = dict(os.environ)
        for key in list(env):
            if key.startswith("AW_") or key in {"PYTHONPATH", "PYTHONHOME"}:
                env.pop(key)

        def run(*arguments: str) -> str:
            result = subprocess.run(arguments, cwd=root, env=env, text=True,
                                    capture_output=True, encoding="utf-8", timeout=120)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            return result.stdout

        # Exercise the distributed installer, including a failure after a real
        # virtual environment exists. Only that first package command is failed.
        installer_path = root / "install.py"
        installer_path.write_bytes((Path(__file__).parent / "install.py").read_bytes())
        spec = importlib.util.spec_from_file_location("smoke_installer", installer_path)
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        checksum = hashlib.sha256(wheels[0].read_bytes()).hexdigest()
        real_run = installer.subprocess.run

        def fail_package(*args, **kwargs):
            raise subprocess.CalledProcessError(1, "injected package installation failure")

        try:
            installer.subprocess.run = fail_package
            try:
                installer.install(wheels[0], environment, checksum=checksum)
            except subprocess.CalledProcessError:
                pass
        finally:
            installer.subprocess.run = real_run
        marker = environment / ".aw-install.json"
        assert json.loads(marker.read_text())["state"] == "installing"
        evidence = environment / "preserved-after-failure.txt"
        evidence.write_text("do not remove this partial installation")
        install_args = (sys.executable, "-I", str(installer_path), str(wheels[0]),
                        "--sha256", checksum, "--destination", str(environment))
        run(*install_args)
        assert evidence.read_text() == "do not remove this partial installation"
        marker_bytes = marker.read_bytes()
        run(*install_args)
        assert marker.read_bytes() == marker_bytes  # Completed attempts are not rebuilt.
        run(str(aw), "--help")
        run(str(python), "-I", "-m", "agent_workspace", "--help")
        args = (str(aw), "--home", str(root / "home"))
        for command in (
            ("workspace", "init", "smoke", str(root / "shared.git")),
            ("-w", "smoke", "agent", "create", "helper", "--id", "helper"),
            ("-w", "smoke", "agent", "list"),
        ):
            result = json.loads(run(*args, *command))
            if not result.get("ok"):
                raise RuntimeError(f"CLI operation failed: {result}")

        ids = {item["id"] for item in result["result"]}
        assert ids == {"helper", "steward", "sentinel", "maintainer"}

        for command in (
            ("-w", "smoke", "workspace", "doctor"),
            ("-w", "smoke", "maintenance", "schedule", "--enabled", "--interval", "60"),
            ("-w", "smoke", "maintenance", "status"),
            ("-w", "smoke", "maintenance", "schedule", "--no-enabled"),
            ("-w", "smoke", "agent", "transfer-status", "helper"),
        ):
            assert json.loads(run(*args, *command))["ok"]

        resource_check = """
from importlib.resources import files
root = files('agent_workspace').joinpath('resources')
for name in ('workspace', 'work', 'message', 'agent', 'handoff', 'relay', 'fork'):
    assert root.joinpath('skills', name, 'SKILL.md').read_text(encoding='utf-8')
for name in ('checkpoints', 'entry', 'handoff', 'initialization', 'capabilities'):
    assert root.joinpath('prompts', name + '.md').read_text(encoding='utf-8')
for name in ('steward', 'sentinel', 'maintainer'):
    assert root.joinpath('definitions', name + '.md').read_text(encoding='utf-8')
for name in ('index.html', 'setup.html'):
    assert root.joinpath(name).read_text(encoding='utf-8')
"""
        run(str(python), "-I", "-c", resource_check)
        # Separate software installations must observe the same unchanged data.
        registry = (root / "home/registry.json").read_bytes()
        second = root / "another-installation"
        run(sys.executable, "-I", str(installer_path), str(wheels[0]), "--sha256", checksum,
            "--destination", str(second))
        second_aw = second / binary.name / aw.name
        observed = json.loads(run(str(second_aw), "--home", str(root / "home"), "-w", "smoke", "agent", "list"))
        assert {a["id"] for a in observed["result"]} == ids
        assert (root / "home/registry.json").read_bytes() == registry

        # Carry the same data and enabled schedule across a real service restart
        # and a separate software installation. No browser/Harness/model is needed.
        with running_workbench(aw, root / "home", root, env) as request:
            state = request()
            installation = state["installation_id"]
            assert {a["id"] for a in state["agents"]} == ids
            plan = request("maintenance.schedule", {"workspace": "smoke", "enabled": True,
                                                    "interval": 30, "notify": False})
            deadline = time.monotonic() + 30
            while True:
                status = request("maintenance.status", {"workspace": "smoke"})
                if (status["worker_running"] and status["local_run"]
                        and status["local_run"]["generation"] == plan["generation"]
                        and status["local_run"].get("state") == "checked"):
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("Installed maintenance worker did not run the authorized schedule.")
                time.sleep(.1)
            assert status["local_run"]["state"] == "checked"
            previous_run = status["local_run"]
        stopped = json.loads(run(*args, "-w", "smoke", "maintenance", "status"))["result"]
        assert stopped["worker_running"] is False
        assert stopped["schedule"]["generation"] == plan["generation"]
        with running_workbench(second_aw, root / "home", root, env) as request:
            state = request()
            assert state["installation_id"] == installation
            assert {a["id"] for a in state["agents"]} == ids
            assert all(a["current"] is None for a in state["agents"])
            restored = request("maintenance.status", {"workspace": "smoke"})
            assert restored["schedule"]["generation"] == plan["generation"]
            assert restored["local_run"]["generation"] == previous_run["generation"]
            assert restored["local_run"]["last_run"] >= previous_run["last_run"]
            request("maintenance.schedule", {"workspace": "smoke", "enabled": False})
        assert (root / "home/registry.json").read_bytes() == registry
    print("PASS: installer recovery, real HTTP restart, durable maintenance, CLI, Git and resources")


if __name__ == "__main__":
    main()
