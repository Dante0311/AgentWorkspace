"""First-use behavior with real temporary Git, never real models or credentials."""
import json
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest

from agent_workspace.app import App
from agent_workspace import onboarding
from agent_workspace.gitstore import GitStore, git_env
from agent_workspace.util import Conflict, Error, Uncertain, read_json


@pytest.fixture
def fresh(tmp_path):
    return App(tmp_path / "home"), tmp_path / "workspace.git"


def create(fresh, **kwargs):
    app, path = fresh
    return onboarding.create_workspace(app, "demo", str(path), **kwargs)


def test_missing_dependencies_do_not_run_or_install_programs(monkeypatch):
    monkeypatch.setattr(onboarding.shutil, "which", lambda _: None)
    run = Mock(side_effect=AssertionError("must not execute"))
    monkeypatch.setattr(onboarding.subprocess, "run", run)
    result = onboarding.scan()
    assert result["git"]["state"] == "missing"
    assert not result["can_create_workspace"] and not result["model_invoked"]
    assert result["suggested_first_harness"] == "codex-cli"
    run.assert_not_called()


def test_discovered_harness_is_not_executed_or_reported_authenticated(monkeypatch):
    monkeypatch.setattr(onboarding.shutil, "which", lambda name: "/installed/" + name)
    run = Mock(return_value=subprocess.CompletedProcess([], 0, b"git", b""))
    monkeypatch.setattr(onboarding.subprocess, "run", run)
    result = onboarding.scan()
    assert result["can_create_workspace"]
    assert all(item["authentication"] == "unchecked" for item in result["harnesses"])
    run.assert_called_once()
    assert run.call_args.args[0] == ["/installed/git", "--version"]


@pytest.mark.parametrize("address", ["-u", "https://user:secret@example.com/repo", "https://token@example.com/r",
    "https://example.com/r?token=secret", "https://example.com/r#secret", "ext::command", "file:///tmp/r",
    "github:owner/repo", "ssh://u:secret@host/r", "https://host/r\n--upload-pack=evil"])
def test_reject_unsafe_addresses_without_echoing_secrets(address):
    with pytest.raises(Error) as error:
        onboarding.git_address(address)
    assert "secret" not in str(error.value)


def test_https_and_ssh_use_git_credentials_not_embedded_passwords():
    for address in ("https://example.com/owner/repo.git", "git@example.com:owner/repo.git", "ssh://git@example.com/r"):
        assert onboarding.git_address(address) == (address, True)
    env = git_env({"SSH_AUTH_SOCK": "agent-socket"})
    assert env["SSH_AUTH_SOCK"] == "agent-socket"
    assert env["GIT_TERMINAL_PROMPT"] == "0" and env["GCM_INTERACTIVE"] == "never"
    assert "StrictHostKeyChecking=yes" in env["GIT_SSH_COMMAND"]


def test_access_probe_does_not_write_or_claim_write_permission(fresh):
    app, path = fresh
    GitStore.initialize(path)
    before = sorted(str(p.relative_to(path)) for p in path.rglob("*"))
    result = onboarding.check_git(str(path))
    assert result["state"] == "accessible" and result["empty"]
    assert result["write_access"] == "unchecked"
    assert before == sorted(str(p.relative_to(path)) for p in path.rglob("*"))


def test_probe_redacts_native_errors(monkeypatch):
    monkeypatch.setattr(onboarding.shutil, "which", lambda _: "git")
    monkeypatch.setattr(onboarding.subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 1, b"", b"secret-password")))
    result = onboarding.check_git("https://example.com/private.git")
    assert result["state"] == "unavailable"
    assert "secret-password" not in json.dumps(result)


def test_create_three_real_identities_without_model_or_work(fresh):
    app, _ = fresh
    result = create(fresh)
    assert result["state"] == "created" and not result["sessions_started"]
    assert not result["monitoring_changed"]
    agents = app.agents("demo")
    assert {a["id"] for a in agents} == set(onboarding.ROLES)
    assert all(a["current"] is None and not a["has_run"] for a in agents)
    assert app.work_list("demo") == []
    for role in onboarding.ROLES:
        root = app.root("demo", role)
        assert read_json(root / "source.json")["definition"] == "definitions/caretaker/" + role
        assert len(list((root / ".agents/skills").glob("*/SKILL.md"))) == 7
        assert not (root / ".aw-local/runtime.json").exists()
        assert not (root / ".aw-local/watch.json").exists()


def test_repeat_preserves_assets_config_and_branch_heads(fresh):
    app, _ = fresh
    assert create(fresh)["state"] == "created"
    root = app.root("demo", "steward")
    (root / "notes.md").write_text("user asset", encoding="utf-8")
    app.configure("demo", "steward", {"kind": "manual"})
    heads = {branch: app.store("demo").head(branch) for branch in ["main", "instance/steward"]}
    assert create(fresh)["state"] == "created"
    assert (root / "notes.md").read_text() == "user asset"
    assert read_json(root / ".aw-local/runtime.json") == {"kind": "manual"}
    assert heads == {branch: app.store("demo").head(branch) for branch in heads}


def test_connect_existing_workspace_does_not_create_caretakers_or_take_over(tmp_path):
    first = App(tmp_path / "first")
    first.workspace_init("old", str(tmp_path / "old.git"))
    first.create("old", "worker")
    b = first.reserve("old", "worker")["binding"]
    first.bind("old", "worker", b, "original-session")
    second = App(tmp_path / "second")
    result = onboarding.create_workspace(second, "copy", first.store("old").address, "connect")
    assert result["state"] == "connected" and result["instances_created"] == []
    assert [a["id"] for a in second.agents("copy")] == ["worker"]
    assert second.agent("copy", "worker")["current"] == b
    onboarding.prepare_instance(second, "copy", "worker")
    assert second.root("copy", "worker").is_dir()
    assert second.agent("copy", "worker")["current"] == b


def test_remote_mode_uses_existing_empty_git_repo(fresh):
    _, path = fresh
    GitStore.initialize(path)
    assert create(fresh, mode="remote")["state"] == "created"


def test_nonempty_other_branch_is_not_initialized(fresh):
    app, path = fresh
    GitStore.initialize(path)
    store = GitStore(str(path), app.home)
    head = store.branch("master", {"user.txt": b"keep"})
    with pytest.raises(Error):
        create(fresh, mode="remote")
    assert store.head("master") == head and store.head("main") is None


def test_branch_published_but_registration_failed_is_resumed(fresh, monkeypatch):
    app, _ = fresh
    change = GitStore.change
    failed = False

    def fail_registration(self, branch, changes, *args, **kwargs):
        nonlocal failed
        if "agents/sentinel.json" in changes and not failed:
            failed = True
            raise Error("registration interrupted")
        return change(self, branch, changes, *args, **kwargs)

    monkeypatch.setattr(GitStore, "change", fail_registration)
    result = create(fresh)
    assert result["state"] == "pending" and result["stage"] == "caretaker/sentinel"
    original = app.store("demo").head("instance/sentinel")
    assert original and len(app.agents("demo")) == 1
    assert create(fresh)["state"] == "created"
    assert app.store("demo").head("instance/sentinel") == original
    assert len(app.agents("demo")) == 3


def test_initial_branch_success_with_lost_reply_is_not_recreated(fresh, monkeypatch):
    branch = GitStore.branch
    failed = False

    def lose_reply(self, name, *args, **kwargs):
        nonlocal failed
        revision = branch(self, name, *args, **kwargs)
        if name == "main" and not failed:
            failed = True
            raise Uncertain("server reply lost")
        return revision

    monkeypatch.setattr(GitStore, "branch", lose_reply)
    assert create(fresh)["state"] == "pending"
    assert create(fresh)["state"] == "created"
    assert len(fresh[0].agents("demo")) == 3


def test_creation_conflict_never_adopts_an_existing_user_agent(fresh):
    app, _ = fresh
    create(fresh)
    app.create("demo", "user", agent_id="user")
    with pytest.raises(Conflict):
        app.create("demo", "user", agent_id="user", request_id="setup-user")
    assert app.agent("demo", "user")["name"] == "user"
    with pytest.raises(Conflict):
        app.create("demo", "different", agent_id="steward", request_id="other-setup")


def test_same_setup_alias_cannot_change_target(fresh, tmp_path):
    app, _ = fresh
    create(fresh)
    target = tmp_path / "other.git"
    with pytest.raises(Conflict):
        onboarding.create_workspace(app, "demo", str(target))
    assert not target.exists()


def test_failed_directory_copy_leaves_no_partial_target(fresh, monkeypatch, tmp_path):
    from agent_workspace import app as app_module
    app, _ = fresh
    create(fresh)
    target = tmp_path / "copy"
    write = app_module.write_bytes

    def fail(path, data):
        if path.name == "AGENTS.md":
            raise OSError("disk failure")
        write(path, data)

    monkeypatch.setattr(app_module, "write_bytes", fail)
    with pytest.raises(OSError):
        app.connect_agent("demo", "steward", target)
    assert not target.exists()
    monkeypatch.setattr(app_module, "write_bytes", write)
    app.connect_agent("demo", "steward", target)
    assert read_json(target / ".aw-local/context.json")["agent"] == "steward"


def test_import_keeps_requested_destination_after_resumable_create_refactor(fresh, tmp_path):
    app, _ = fresh
    create(fresh)
    source = tmp_path / "source"
    source.mkdir()
    (source / "notes.txt").write_text("keep", encoding="utf-8")
    target = tmp_path / "imported"
    result = app.create("demo", "imported", directory=target, import_directory=source, assets=["notes.txt"])
    assert result["directory"] == str(target.resolve())
    assert (target / "notes.txt").read_text() == "keep"
