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


@pytest.fixture
def setup_install(tmp_path, monkeypatch):
    wheel = tmp_path / "git_native_agent_workspace-test.whl"
    wheel.write_bytes(b"isolated fixture")
    checksum = hashlib.sha256(wheel.read_bytes()).hexdigest()
    target = tmp_path / "install"

    def prepare(path):
        path.mkdir(parents=True, exist_ok=True)
        (path / "pyvenv.cfg").write_text("test environment")

    builder = Mock()
    builder.create.side_effect = prepare
    monkeypatch.setattr(installer.venv, "EnvBuilder", Mock(return_value=builder))
    run = Mock()
    monkeypatch.setattr(installer.subprocess, "run", run)
    return wheel, target, checksum, builder, run


def test_failed_pip_can_resume_same_verified_installation(setup_install):
    wheel, target, checksum, builder, run = setup_install
    run.side_effect = installer.subprocess.CalledProcessError(1, "pip")
    with pytest.raises(installer.subprocess.CalledProcessError):
        installer.install(wheel, target, checksum=checksum)
    evidence = target / "failure-evidence.txt"
    evidence.write_text("keep existing content")
    run.side_effect = None
    installer.install(wheel, target, checksum=checksum)
    assert evidence.read_text() == "keep existing content"
    assert builder.create.call_count == 2


def test_interrupted_environment_creation_is_resumable(setup_install):
    wheel, target, checksum, builder, run = setup_install
    prepare = builder.create.side_effect
    builder.create.side_effect = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        installer.install(wheel, target, checksum=checksum)
    builder.create.side_effect = prepare
    installer.install(wheel, target, checksum=checksum)
    assert run.call_count == 2


def test_completed_install_is_not_reinstalled(setup_install):
    wheel, target, checksum, builder, run = setup_install
    first = installer.install(wheel, target, checksum=checksum)
    second = installer.install(wheel, target, checksum=checksum)
    assert first == second
    assert builder.create.call_count == 1
    assert len([c for c in run.call_args_list if "pip" in c.args[0]]) == 1


def test_different_wheel_or_extras_cannot_reuse_partial_install(setup_install):
    wheel, target, checksum, builder, run = setup_install
    run.side_effect = installer.subprocess.CalledProcessError(1, "pip")
    with pytest.raises(installer.subprocess.CalledProcessError):
        installer.install(wheel, target, checksum=checksum)
    run.reset_mock(side_effect=True)
    with pytest.raises(ValueError, match="different|match"):
        installer.install(wheel, target, checksum=checksum, extras=["claude"])
    wheel.write_bytes(b"different release")
    with pytest.raises(ValueError, match="different|match"):
        installer.install(wheel, target, checksum=hashlib.sha256(wheel.read_bytes()).hexdigest())
    run.assert_not_called()


def test_corrupt_install_record_is_preserved(setup_install):
    wheel, target, checksum, builder, run = setup_install
    run.side_effect = installer.subprocess.CalledProcessError(1, "pip")
    with pytest.raises(installer.subprocess.CalledProcessError):
        installer.install(wheel, target, checksum=checksum)
    marker = target / ".aw-install.json"
    marker.write_text("{broken")
    run.reset_mock(side_effect=True)
    with pytest.raises(ValueError):
        installer.install(wheel, target, checksum=checksum)
    assert marker.read_text() == "{broken"
    run.assert_not_called()


def test_installation_lock_prevents_second_writer(setup_install):
    wheel, target, checksum, builder, run = setup_install
    errors = []
    prepare = builder.create.side_effect

    def contend(path):
        prepare(path)
        try:
            installer.install(wheel, target, checksum=checksum)
        except ValueError as exc:
            errors.append(str(exc))

    builder.create.side_effect = contend
    installer.install(wheel, target, checksum=checksum)
    assert len(errors) == 1 and "running" in errors[0]
    assert builder.create.call_count == 1


def test_copied_partial_install_is_not_reused(setup_install):
    import shutil
    wheel, target, checksum, builder, run = setup_install
    run.side_effect = installer.subprocess.CalledProcessError(1, "pip")
    with pytest.raises(installer.subprocess.CalledProcessError):
        installer.install(wheel, target, checksum=checksum)
    copied = target.with_name("copied")
    shutil.copytree(target, copied)
    run.reset_mock(side_effect=True)
    with pytest.raises(ValueError, match="different"):
        installer.install(wheel, copied, checksum=checksum)
    run.assert_not_called()


def test_symlink_destination_is_rejected_without_touching_target(setup_install):
    wheel, target, checksum, builder, run = setup_install
    actual = target.with_name("actual")
    actual.mkdir()
    try:
        target.symlink_to(actual, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks are unavailable in this environment")
    with pytest.raises(ValueError, match="symlink"):
        installer.install(wheel, target, checksum=checksum)
    assert list(actual.iterdir()) == []
    run.assert_not_called()
