"""Install a built wheel in a clean temporary environment, without source imports."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile


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
    print("PASS: recoverable installer, separate installations, CLI, local Git and bundled resources")


if __name__ == "__main__":
    main()
