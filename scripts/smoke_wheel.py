"""Install a built wheel in a clean temporary environment, without source imports."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import venv


def main() -> None:
    directory = Path(sys.argv[1] if len(sys.argv) > 1 else "dist").resolve()
    wheels = sorted(directory.glob("git_native_agent_workspace-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"Expected one project wheel in {directory}, found {len(wheels)}")

    with tempfile.TemporaryDirectory(prefix="aw-wheel-") as temporary:
        root = Path(temporary)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
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

        run(str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheels[0]))
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
    print("PASS: clean wheel install, CLI, local Git, seven skills and bundled resources")


if __name__ == "__main__":
    main()
