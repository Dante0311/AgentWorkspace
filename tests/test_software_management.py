"""Local software control stays available independently of Agent business authority."""
import json
from pathlib import Path
import time

import pytest

from agent_workspace import backend, cli
from agent_workspace.app import App
from agent_workspace.commands import execute
from agent_workspace.util import Error


def wait_for(read, check):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        result = read()
        if check(result):
            return result
        time.sleep(.05)
    pytest.fail(f"The original backend operation did not finish: {result}")


def test_local_software_control_with_stale_inherited_identity(tmp_path, monkeypatch, capsys):
    app = App(tmp_path / "software-home")
    monkeypatch.setenv("PYTHONPATH", str(Path(backend.__file__).parents[1]))
    monkeypatch.setenv("AW_AGENT", "previous-agent")
    monkeypatch.setenv("AW_BINDING", "previous-binding")
    monkeypatch.setenv("AW_WORKSPACE", "no-longer-connected")
    monkeypatch.setenv("CODEX_THREAD_ID", "previous-chat")
    try:
        assert cli.main(["--home", str(app.home), "backend", "start", "--port", "0"]) == 0
        assert json.loads(capsys.readouterr().out)["ok"]
        original = wait_for(lambda: backend.status(app), lambda value: value["ready"])
        result = execute(app, "backend.restart", {},
                         actor=("no-longer-connected", "previous-agent", "previous-binding"))
        assert result["restart_requested"]
        renewed = wait_for(lambda: backend.status(app),
                           lambda value: value["ready"] and value.get("pid") != original["pid"])
        assert renewed["runners"] == []
        assert app.local()["workspaces"] == {}
        assert cli.main(["--home", str(app.home), "backend", "log", "--lines", "5"]) == 0
        assert json.loads(capsys.readouterr().out)["result"]["source"]["kind"] == "backend"
        assert cli.main(["--home", str(app.home), "backend", "stop"]) == 0
        stopped = json.loads(capsys.readouterr().out)["result"]
        assert stopped["stop_requested"] and not stopped["agent_bindings_released"]
        wait_for(lambda: backend.status(app), lambda value: not value["running"])
    finally:
        backend.stop(app)
        wait_for(lambda: backend.status(app), lambda value: not value["running"])


@pytest.mark.parametrize("command", ["backend.attach", "backend.cancel", "runtime.start", "runtime.stop"])
def test_agent_operations_still_need_management_authority(pair, command):
    app, bindings = pair
    with pytest.raises(Error):
        execute(app, command, {"workspace": "sea", "agent_id": "bob"},
                actor=("sea", "alice", bindings["alice"]))
    assert app.agent("sea", "bob")["current"] == bindings["bob"]
