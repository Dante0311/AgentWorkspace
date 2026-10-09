"""Owned smoke cleanup handles only confirmed Windows read-only regular files."""
import importlib.util
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location('smoke_script', Path(__file__).parents[1] / 'scripts/smoke_wheel.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_remove_ordinary_owned_tree(smoke, tmp_path):
    root = tmp_path / 'smoke'; root.mkdir(); (root / 'file').write_bytes(b'asset')
    smoke.remove_smoke_tree(root)
    assert not root.exists()


@pytest.mark.skipif(os.name != 'nt', reason='Actual Windows read-only file semantics')
def test_real_windows_git_readonly_cleanup(smoke, tmp_path):
    root = tmp_path / 'smoke'; root.mkdir(); path = root / 'git-object'; path.write_bytes(b'object')
    path.chmod(stat.S_IREAD)
    smoke.remove_smoke_tree(root)
    assert not root.exists()


def test_unknown_cleanup_errors_are_not_retried_or_ignored(smoke, tmp_path, monkeypatch):
    root = tmp_path / 'smoke'; root.mkdir(); path = root / 'file'; path.write_bytes(b'asset')
    error = OSError('unknown removal error')
    def fail(directory, onerror): onerror(os.unlink, str(path), (type(error), error, None))
    monkeypatch.setattr(smoke.shutil, 'rmtree', fail)
    with pytest.raises(OSError, match='unknown'): smoke.remove_smoke_tree(root)
    assert path.read_bytes() == b'asset'
