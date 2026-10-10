"""Workbench 0.4 contracts: explicit directories and truthful state projection."""
from pathlib import Path
import shutil
import subprocess

import pytest

from agent_workspace.app import App
from agent_workspace import onboarding
from agent_workspace.server import build_state
from agent_workspace.util import Conflict, Error, read_json


@pytest.fixture
def created(tmp_path):
    app = App(tmp_path / "home")
    repository = tmp_path / "workspace.git"
    directories = {
        "steward": str((tmp_path / "agents" / "steward").resolve()),
        "sentinel": str((tmp_path / "other-drive" / "sentinel").resolve()),
        "maintainer": str((tmp_path / "agents" / "maintainer").resolve()),
    }
    result = onboarding.create_workspace(app, "demo", str(repository), directories=directories)
    assert result["state"] == "created", result
    return app, repository, directories, result


def test_directory_helper_defaults_and_rejects_relative(tmp_path):
    app = App(tmp_path / "home")
    assert onboarding.instance_directory(app, "demo", "worker") == str(
        (app.home / "instances" / "demo" / "worker").resolve()
    )
    explicit = tmp_path / "separate" / "worker"
    assert onboarding.instance_directory(app, "demo", "worker", str(explicit)) == str(explicit.resolve())
    with pytest.raises(Error, match="绝对路径"):
        onboarding.instance_directory(app, "demo", "worker", "relative/worker")
    with pytest.raises(Error, match="不能共用"):
        onboarding.instance_directories(app, "demo", {
            "steward": str(explicit), "sentinel": str(explicit), "maintainer": str(tmp_path / "m")
        })
    with pytest.raises(Error, match="未知"):
        onboarding.instance_directories(app, "demo", {"other": str(explicit)})


def test_workspace_creation_uses_selected_directories_and_returns_real_revisions(created):
    app, _, directories, result = created
    assert result["directories"] == directories
    assert {entry["role"] for entry in result["caretakers"]} == set(onboarding.ROLES)
    for entry in result["caretakers"]:
        role = entry["role"]
        assert entry["directory"] == directories[role]
        assert len(entry["revision"]) == 40
        root = app.root("demo", role)
        assert str(root) == directories[role]
        assert read_json(root / ".aw-local/context.json")["revision"] == entry["revision"]
    assert all(app.agent("demo", role)["current"] is None for role in onboarding.ROLES)


def test_setup_retry_keeps_original_directories_and_does_not_recreate(created, tmp_path):
    app, repository, directories, _ = created
    heads = {name: app.store("demo").head(name) for name in ["main", *["instance/" + r for r in onboarding.ROLES]]}
    repeated = onboarding.create_workspace(app, "demo", str(repository), directories=directories)
    assert repeated["state"] == "created" and repeated["directories"] == directories
    assert heads == {name: app.store("demo").head(name) for name in heads}
    changed = dict(directories, steward=str((tmp_path / "moved" / "steward").resolve()))
    with pytest.raises(Conflict, match="沿用原路径"):
        onboarding.create_workspace(app, "demo", str(repository), directories=changed)
    assert app.root("demo", "steward") == Path(directories["steward"])


def test_prepare_existing_identity_accepts_another_explicit_empty_directory(created, tmp_path):
    app, repository, _, _ = created
    second = App(tmp_path / "second-home")
    second.workspace_connect("copy", str(repository))
    target = tmp_path / "external" / "steward-copy"
    result = onboarding.prepare_instance(second, "copy", "steward", str(target))
    assert result["directory"] == str(target.resolve())
    assert result["sessions_started"] is False
    assert read_json(target / ".aw-local/context.json")["agent"] == "steward"
    assert second.agent("copy", "steward")["current"] is None


def test_workbench_state_labels_shared_revision_and_local_directory(created):
    app, _, directories, _ = created
    value = build_state(app)
    assert value["installation_id"].startswith("host-")
    assert value["default_instance_root"] == str((app.home / "instances").resolve())
    workspace = value["workspaces"][0]
    assert workspace["alias"] == "demo" and len(workspace["snapshot_revision"]) == 40
    agents = {item["id"]: item for item in value["agents"]}
    assert set(agents) == set(onboarding.ROLES)
    assert agents["steward"]["directory"] == directories["steward"]
    assert agents["steward"]["local_ready"] is True
    assert agents["steward"]["observation_source"]["kind"] == "local_registry_and_runtime"
    assert agents["steward"]["snapshot_revision"] == workspace["snapshot_revision"]


def test_workbench_assets_are_real_command_ui_not_demo_gateway():
    root = Path(__file__).parents[1] / "src" / "agent_workspace" / "resources"
    index = (root / "index.html").read_text(encoding="utf-8")
    setup = (root / "setup.html").read_text(encoding="utf-8")
    assert "DemoGateway" not in index + setup
    assert "WORKBENCH 0.4" in index + setup
    for text in ("操作与恢复", "状态依据", "本机实例目录", "继续原请求"):
        assert text in index + setup
    for identifier in ("dir-steward", "dir-sentinel", "dir-maintainer", "instance-directory"):
        assert f'id="{identifier}"' in setup
    assert "args.directories" in setup
    assert "directory:values.directory" in index
    assert index.count('<a href="/sessions">普通会话</a>') == 1
    assert "session=null" in index


def test_inline_scripts_parse_when_node_is_available():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable; browser CI still parses these scripts in Chromium.")
    root = Path(__file__).parents[1] / "src" / "agent_workspace" / "resources"
    for name in ("index.html", "setup.html"):
        text = (root / name).read_text(encoding="utf-8")
        script = text.split("<script>", 1)[1].rsplit("</script>", 1)[0]
        result = subprocess.run([node, "--check", "-"], input=script, text=True, encoding="utf-8", capture_output=True)
        assert result.returncode == 0, result.stderr
