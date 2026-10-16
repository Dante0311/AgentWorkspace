"""Install the npm artifact outside the checkout and check data survives replacement."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request

from smoke_wheel import running_workbench, smoke_directory


def main():
    if sys.platform != "win32":
        raise SystemExit("The npm artifact currently supports Windows x64.")
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else "dist").resolve()
    artifacts = sorted(directory.glob("git-native-agent-workspace-*.tgz"))
    if len(artifacts) != 1:
        raise SystemExit(f"Expected one npm artifact in {directory}, found {len(artifacts)}")
    artifact = artifacts[0]
    with tarfile.open(artifact, "r:gz") as archive:
        caches = [name for name in archive.getnames() if name.startswith("package/app/")
                  and ("/__pycache__/" in name or name.endswith((".pyc", ".pyo")))]
    if caches:
        raise SystemExit("Application build caches were included in the npm package: " + ", ".join(caches))
    npm = shutil.which("npm.cmd")
    node = shutil.which("node")
    git = shutil.which("git")
    if not all((npm, node, git)):
        raise SystemExit("Node.js, npm and Git are required for this installation check.")

    with smoke_directory(prefix="aw-npm-") as root:
        prefix = root / "installation"
        home = root / "data"
        env = dict(os.environ)
        for key in list(env):
            if key.startswith("AW_") or key in {"PYTHONPATH", "PYTHONHOME"}:
                env.pop(key)
        # The installed program must work without a system Python on PATH.
        windows = Path(env["SYSTEMROOT"])
        env["PATH"] = os.pathsep.join([str(Path(node).parent), str(Path(git).parent),
                                       str(windows / "System32"), str(windows)])
        env["npm_config_cache"] = str(root / "npm-cache")
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_CONFIG_GLOBAL"] = os.devnull

        def run(*arguments):
            result = subprocess.run([str(argument) for argument in arguments], cwd=root, env=env,
                                    text=True, encoding="utf-8", capture_output=True, timeout=120)
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            return result.stdout

        install = (npm, "install", "--global", "--prefix", prefix, "--offline",
                   "--ignore-scripts", "--no-audit", "--no-fund", artifact)
        run(*install)
        aw = prefix / "aw.cmd"
        package = prefix / "node_modules/git-native-agent-workspace"
        python = package / "runtime/python.exe"
        build = json.loads((package / "build.json").read_text(encoding="utf-8"))
        run(aw, "--help")
        version = run(aw, "--version").strip()
        run(python, "-I", "-c", """
from importlib.resources import files
import sys
assert sys.version_info[:2] == (3, 13)
root = files('agent_workspace').joinpath('resources')
for name in ('workspace', 'work', 'message', 'agent', 'worker', 'handoff', 'relay', 'fork'):
    assert root.joinpath('skills', name, 'SKILL.md').read_text(encoding='utf-8')
for name in ('index.html', 'setup.html', 'sessions.html'):
    assert root.joinpath(name).read_text(encoding='utf-8')
""")
        args = (aw, "--home", home)

        def backend(command, *options):
            return json.loads(run(*args, "backend", command, *options))["result"]

        def wait_backend(predicate):
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                observation = backend("status")
                if predicate(observation):
                    return observation
                time.sleep(0.2)
            raise RuntimeError("Installed backend did not reach the expected state.")

        assert json.loads(run(*args, "workspace", "init", "smoke", root / "shared.git"))["ok"]
        assert json.loads(run(*args, "-w", "smoke", "agent", "create", "helper", "--id", "helper"))["ok"]
        agents = json.loads(run(*args, "-w", "smoke", "agent", "list"))["result"]
        assert {agent["id"] for agent in agents} == {"helper", "steward", "sentinel", "maintainer"}
        marker = home / "user-owned.txt"
        marker.write_text("preserve user data", encoding="utf-8")
        registry = (home / "registry.json").read_bytes()
        with running_workbench(aw, home, root, env) as request:
            assert request()["workspaces"]

        # Use the installed launcher to control a detached backend as a user would.
        assert backend("status")["state"] == "stopped"
        try:
            backend("start", "--port", "0")
            started = wait_backend(lambda item: item["ready"])
            repeated = backend("start")
            assert repeated["pid"] == started["pid"] and not repeated["start_requested"]
            connection = json.loads((home / "backend/connection.json").read_text(encoding="utf-8"))
            request = urllib.request.Request(started["url"] + "api/state",
                      headers={"Authorization": "Bearer " + connection["token"]})
            with urllib.request.urlopen(request, timeout=10) as response:
                assert json.load(response)["result"]["workspaces"]
            log = backend("log", "--lines", "20")
            assert log["source"]["kind"] == "backend" and connection["token"] not in log["content"]
            backend("restart")
            restarted = wait_backend(lambda item: item["ready"] and item["pid"] != started["pid"])
            assert restarted["home"] == started["home"]
            separate = json.loads(run(aw, "--home", root / "separate-data", "backend", "status"))["result"]
            assert separate["state"] == "stopped"
        finally:
            backend("stop")
            wait_backend(lambda item: item["state"] == "stopped")

        # Replace the actual installed package, then reuse the same data home.
        run(npm, "uninstall", "--global", "--prefix", prefix, "--ignore-scripts",
            "--no-audit", "--no-fund", "git-native-agent-workspace")
        run(*install)
        assert marker.read_text(encoding="utf-8") == "preserve user data"
        assert (home / "registry.json").read_bytes() == registry
        assert json.loads(run(*args, "-w", "smoke", "agent", "list"))["result"] == agents
        with running_workbench(aw, home, root, env) as request:
            assert request()["workspaces"]
        print(json.dumps({"ok": True, "artifact": artifact.name,
                          "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                          "npm_version": build["version"], "program_version": version,
                          "checks": ["no application build caches", "offline npm install", "bundled runtime", "eight Skills and web resources",
                                     "CLI and HTTP", "backend singleton, restart, logs and separate home",
                                     "package replacement preserves user data", "orderly shutdown"]}))


if __name__ == "__main__":
    main()
