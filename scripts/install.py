"""Install a downloaded build into an isolated directory, without a source checkout.

Requires Python 3.11+. Never installs Git/a Harness, logs in, starts a model,
changes PATH, or writes into the user's Workspace. Existing installs are kept.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import venv


def verify(wheel: Path, checksum: str | None) -> None:
    if checksum is None:
        manifest = wheel.parent / 'SHA256SUMS'
        if not manifest.is_file():
            raise ValueError('Provide the build SHA256SUMS file or --sha256 before installing.')
        checksums = dict((line.split(maxsplit=1)[1].lstrip('*'), line.split(maxsplit=1)[0])
                         for line in manifest.read_text(encoding='utf-8').splitlines() if line.strip())
        checksum = checksums.get(wheel.name)
    actual = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if not checksum or actual != checksum.lower():
        raise ValueError('Wheel checksum does not match. No installation was started.')


def install(wheel, destination, *, checksum=None, extras=(), open_setup=False):
    wheel, destination = Path(wheel).resolve(), Path(destination).expanduser().resolve()
    if sys.version_info < (3, 11):
        raise ValueError('Install Python 3.11 or later, then retry.')
    if wheel.suffix != '.whl' or not wheel.name.startswith('git_native_agent_workspace-'):
        raise ValueError('Select the AgentWorkspace wheel from the verified build.')
    if not set(extras) <= {'claude', 'codebuddy', 'wecom'}:
        raise ValueError('Unknown optional integration.')
    verify(wheel, checksum)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Use an empty installation directory. Existing software and data are never overwritten.')
    venv.EnvBuilder(with_pip=True).create(destination)
    binary = destination / ('Scripts' if os.name == 'nt' else 'bin')
    python = binary / ('python.exe' if os.name == 'nt' else 'python')
    env = {key: value for key, value in os.environ.items() if not key.startswith('AW_') and key not in ('PYTHONPATH', 'PYTHONHOME')}
    package = str(wheel) + ('[' + ','.join(sorted(set(extras))) + ']' if extras else '')
    args = [str(python), '-m', 'pip', 'install', package]
    if not extras:
        args.extend(['--no-deps', '--no-index'])
    # Extras download SDK libraries through pip; native programs remain user-installed.
    subprocess.run(args, env=env, cwd=destination, check=True, timeout=300)
    aw = binary / ('aw.exe' if os.name == 'nt' else 'aw')
    subprocess.run([str(aw), '--version'], env=env, cwd=destination, check=True, timeout=15)
    print(json.dumps({'installed': str(destination), 'start': [str(aw), 'setup', '--open'],
                      'workspace_data_changed': False}, ensure_ascii=False))
    if open_setup:
        subprocess.run([str(aw), 'setup', '--open'], env=env, cwd=destination, check=True)
    return aw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel', type=Path)
    parser.add_argument('--destination', type=Path, default=Path.home() / '.agent-workspace-app')
    parser.add_argument('--sha256')
    parser.add_argument('--extra', choices=['claude', 'codebuddy', 'wecom'], action='append', default=[])
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    try:
        install(args.wheel, args.destination, checksum=args.sha256, extras=args.extra, open_setup=args.open)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(2, f'Installation failed ({type(exc).__name__}). Existing Workspaces were not modified.\n{exc}\n')


if __name__ == '__main__':
    main()
