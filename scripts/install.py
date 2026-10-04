"""Install a downloaded build into an isolated directory, without a source checkout.

Requires Python 3.11+. Never installs Git/a Harness, logs in, starts a model,
changes PATH, or writes into the user's Workspace. Existing installs are kept.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def verify(wheel: Path, checksum: str | None) -> str:
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
    return actual


@contextlib.contextmanager
def installation_lock(destination):
    """Serialize attempts at one destination without relying on a stale PID."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    path = destination.with_name(destination.name + '.install.lock')
    if path.is_symlink():
        raise ValueError('Installation lock must not be a symlink.')
    with path.open('a+b') as stream:
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError('Another installer is running for this destination.') from exc
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def save_record(path, value):
    # An interrupted update must leave either the old record or the complete new one.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.aw-install-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(value, ensure_ascii=False).encode('utf-8'))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def install(wheel, destination, *, checksum=None, extras=(), open_setup=False):
    wheel, destination = Path(wheel).resolve(), Path(destination).expanduser()
    if destination.is_symlink():
        raise ValueError('Use a real installation directory, not a symlink.')
    destination = destination.resolve()
    if sys.version_info < (3, 11):
        raise ValueError('Install Python 3.11 or later, then retry.')
    if wheel.suffix != '.whl' or not wheel.name.startswith('git_native_agent_workspace-'):
        raise ValueError('Select the AgentWorkspace wheel from the verified build.')
    if not set(extras) <= {'claude', 'codebuddy', 'wecom'}:
        raise ValueError('Unknown optional integration.')
    expected = {'schema': 1, 'destination': str(destination),
                'sha256': verify(wheel, checksum), 'extras': sorted(set(extras)),
                'python': list(sys.version_info[:2])}
    binary = destination / ('Scripts' if os.name == 'nt' else 'bin')
    python = binary / ('python.exe' if os.name == 'nt' else 'python')
    aw = binary / ('aw.exe' if os.name == 'nt' else 'aw')
    env = {key: value for key, value in os.environ.items() if not key.startswith('AW_') and key not in ('PYTHONPATH', 'PYTHONHOME')}
    with installation_lock(destination):
        marker = destination / '.aw-install.json'
        if marker.is_symlink():
            raise ValueError('Installation record must not be a symlink.')
        if marker.exists():
            record = json.loads(marker.read_text(encoding='utf-8'))
            if not isinstance(record, dict) or record.get('state') not in ('installing', 'installed'):
                raise ValueError('Invalid installation record; preserve this directory and choose another.')
            if any(record.get(key) != value for key, value in expected.items()):
                raise ValueError('This directory belongs to a different installation. Use a new empty directory.')
        else:
            if destination.exists() and any(destination.iterdir()):
                raise ValueError('Use an empty installation directory. Existing software and data are never overwritten.')
            destination.mkdir(parents=True, exist_ok=True)
            record = {**expected, 'state': 'installing'}
            save_record(marker, record)
        if record['state'] == 'installing':
            # Resume in place. Venv scripts contain absolute paths, so never move a
            # prepared environment or delete a partial directory to retry it.
            venv.EnvBuilder(with_pip=True).create(destination)
            package = str(wheel) + ('[' + ','.join(expected['extras']) + ']' if extras else '')
            args = [str(python), '-m', 'pip', 'install', package]
            if not extras:
                args.extend(['--no-deps', '--no-index'])
            subprocess.run(args, env=env, cwd=destination, check=True, timeout=300)
        subprocess.run([str(aw), '--version'], env=env, cwd=destination, check=True, timeout=15)
        if record['state'] != 'installed':
            save_record(marker, {**expected, 'state': 'installed'})
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
