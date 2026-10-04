"""Exercise the actual OS lock, including simultaneous first use on Windows."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from agent_workspace.util import Conflict, locked


def test_empty_lock_file_needs_no_initialization_write(tmp_path, monkeypatch):
    path = tmp_path / 'first.lock'
    original_open = Path.open

    class NoWrites:
        def __init__(self, stream):
            self.stream = stream

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def write(self, data):
            pytest.fail('A lock file must not be written before acquiring its lock.')

    def open_lock(target, *args, **kwargs):
        stream = original_open(target, *args, **kwargs)
        return NoWrites(stream) if target == path else stream

    monkeypatch.setattr(Path, 'open', open_lock)
    with locked(path):
        assert path.stat().st_size == 0
    assert path.exists() and path.stat().st_size == 0


def test_existing_lock_file_is_not_replaced_or_truncated(tmp_path):
    path = tmp_path / 'existing.lock'
    path.write_bytes(b'existing lock file')
    with locked(path):
        with pytest.raises(Conflict):
            with locked(path, wait=0):
                pytest.fail('Second handle acquired an already held lock.')
    assert path.read_bytes() == b'existing lock file'


def test_thread_contention_on_new_lock(tmp_path):
    path = tmp_path / 'new.lock'
    barrier = threading.Barrier(6)
    counter = tmp_path / 'counter'
    counter.write_text('0')

    def increment(_):
        barrier.wait(timeout=10)
        for _ in range(5):
            with locked(path):
                current = int(counter.read_text())
                counter.write_text(str(current + 1))

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(increment, range(6)))
    assert counter.read_text() == '30'


def child_env():
    env = dict(os.environ)
    # Subprocesses must import this checkout, even without an editable install.
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1] / 'src')
    return env


def test_process_contention_on_new_lock(tmp_path):
    code = '''from pathlib import Path
import sys
from agent_workspace.util import locked
root = Path(sys.argv[1])
print('ready', flush=True)
sys.stdin.readline()
for _ in range(5):
    with locked(root / 'new.lock'):
        counter = root / 'counter'
        counter.write_text(str(int(counter.read_text()) + 1))
'''
    (tmp_path / 'counter').write_text('0')
    processes = []
    try:
        for _ in range(4):
            processes.append(subprocess.Popen([sys.executable, '-c', code, str(tmp_path)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, env=child_env()))
        # All writes contend on the same first-use path; no parent pre-creates it.
        for process in processes:
            process.stdin.write('start\n')
            process.stdin.flush()
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            assert process.returncode == 0, stderr
            assert stdout.strip() == 'ready'
        assert (tmp_path / 'counter').read_text() == '20'
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.communicate()


def test_exception_releases_lock(tmp_path):
    path = tmp_path / 'error.lock'
    with pytest.raises(ValueError):
        with locked(path):
            raise ValueError('test failure')
    with locked(path, wait=0):
        pass
