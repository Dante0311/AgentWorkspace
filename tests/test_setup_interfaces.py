"""Integration checks use the real dispatcher, CLI and local HTTP server."""
import json
import os
import subprocess
import sys
import threading
import urllib.request
import urllib.error

import pytest

from agent_workspace.app import App
from agent_workspace.commands import execute
from agent_workspace.server import make_server
from agent_workspace.util import Error


def test_first_use_page_and_scan_without_git(tmp_path, monkeypatch):
    app = App(tmp_path / "home")
    monkeypatch.setattr("agent_workspace.onboarding.shutil.which", lambda _: None)
    server = make_server(app, 0, "test-token")
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        for page in ("/", "/setup"):
            with urllib.request.urlopen(base + page) as response:
                assert "首次配置" in response.read().decode()
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base + "/api/commands")
        request = urllib.request.Request(base + "/api/execute", data=json.dumps({
            "command": "setup.scan", "arguments": {}}).encode(),
            headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"})
        with urllib.request.urlopen(request) as response:
            result = json.load(response)["result"]
        assert result["git"]["state"] == "missing" and not result["can_create_workspace"]
        assert app.workspace_list() == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_setup_cli_does_not_require_workspace_selection(tmp_path):
    env = dict(os.environ)
    for key in ("AW_AGENT", "AW_BINDING", "AW_WORKSPACE"):
        env.pop(key, None)
    command = [sys.executable, "-m", "agent_workspace", "--home", str(tmp_path / "home")]
    result = subprocess.run(command + ["call", "setup.scan"], env=env, capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert result.returncode == 0, result.stderr
    assert not json.loads(result.stdout)["result"]["model_invoked"]
    assert subprocess.run(command + ["setup", "--help"], env=env, capture_output=True, timeout=20).returncode == 0


def test_public_workspace_init_creates_group_via_same_dispatcher(tmp_path):
    app = App(tmp_path / "home")
    result = execute(app, "workspace.init", {"name": "new", "directory": str(tmp_path / "new.git")})
    assert result["state"] == "created"
    assert {a["id"] for a in app.agents("new")} == {"steward", "sentinel", "maintainer"}
    assert not result["sessions_started"]


@pytest.mark.parametrize("command", ["workspace.init", "setup.scan", "setup.create", "setup.check-git",
                                      "setup.inspect-codex", "setup.prepare-instance", "agent.configure-codex"])
def test_model_identity_does_not_gain_new_management_permissions(tmp_path, command):
    app = App(tmp_path / "home")
    with pytest.raises(Error, match="user-management"):
        execute(app, command, {}, actor=("sea", "steward", "binding"))
    assert app.workspace_list() == []
