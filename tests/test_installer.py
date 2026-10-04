"""Installer validation is offline and never changes a user's data directory."""
import hashlib
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location("aw_installer", Path(__file__).parents[1] / "scripts/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def test_checksum_failure_never_creates_an_installation(tmp_path, monkeypatch):
    wheel = tmp_path / "git_native_agent_workspace-test.whl"
    wheel.write_bytes(b"isolated fixture")
    create = Mock()
    monkeypatch.setattr(installer.venv, "EnvBuilder", create)
    with pytest.raises(ValueError, match="checksum"):
        installer.install(wheel, tmp_path / "install", checksum="0" * 64)
    create.assert_not_called()


def test_existing_directory_is_preserved_before_running_pip(tmp_path, monkeypatch):
    wheel = tmp_path / "git_native_agent_workspace-test.whl"
    wheel.write_bytes(b"isolated fixture")
    target = tmp_path / "existing"
    target.mkdir()
    (target / "user-data").write_text("must survive")
    run = Mock()
    monkeypatch.setattr(installer.subprocess, "run", run)
    with pytest.raises(ValueError, match="empty"):
        installer.install(wheel, target, checksum=hashlib.sha256(wheel.read_bytes()).hexdigest())
    assert (target / "user-data").read_text() == "must survive"
    run.assert_not_called()


def test_installer_uses_offline_core_and_does_not_open_setup_by_default(tmp_path, monkeypatch):
    wheel = tmp_path / "git_native_agent_workspace-test.whl"
    wheel.write_bytes(b"isolated fixture")
    (tmp_path / "SHA256SUMS").write_text(hashlib.sha256(wheel.read_bytes()).hexdigest() + "  " + wheel.name + "\n")
    create, run = Mock(), Mock()
    monkeypatch.setattr(installer.venv, "EnvBuilder", create)
    monkeypatch.setattr(installer.subprocess, "run", run)
    monkeypatch.setenv("AW_BINDING", "not-for-installer")
    installer.install(wheel, tmp_path / "install")
    assert run.call_count == 2
    args = run.call_args_list[0].args[0]
    assert "--no-index" in args and "--no-deps" in args
    assert "AW_BINDING" not in run.call_args_list[0].kwargs["env"]
    assert all("setup" not in call.args[0] for call in run.call_args_list)
