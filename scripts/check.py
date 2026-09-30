"""Run the portable project's local checks without Playbook paths or private services."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
for args in ([sys.executable, '-m', 'compileall', '-q', 'src'],
             [sys.executable, '-m', 'pytest', '-q']):
    result = subprocess.run(args, cwd=root)
    if result.returncode:
        raise SystemExit(result.returncode)
