"""E2E-002: pinned SDK + real Node protocol fixture, not WorkBuddy login acceptance."""
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent_workspace import native_sdk, runtime, transfer
from agent_workspace.harness_config import sdk_config
from agent_workspace.util import Unavailable, read_json


@pytest.fixture
def windows_js(app, tmp_path, monkeypatch):
    pytest.importorskip("codebuddy_agent_sdk")
    node = shutil.which("node")
    if not node:
        pytest.skip("Installed Node required for the JS transport contract")
    # Only platform selection is simulated on POSIX; SDK process/stdio are real.
    monkeypatch.setattr(native_sdk, "os", SimpleNamespace(**{**vars(os), "name": "nt"}))
    folder = tmp_path / "WorkBuddy fixture 空格 & name"
    folder.mkdir()
    script = folder / "cli.cjs"
    capture = folder / "capture.json"
    script.write_text('''const fs = require('node:fs');
const rl = require('node:readline').createInterface({input: process.stdin});
const capture = {argv: process.argv.slice(2), cwd: process.cwd(), users: [],
  key: process.env.CODEBUDDY_API_KEY, endpoint: process.env.CODEBUDDY_BASE_URL,
  environment: process.env.CODEBUDDY_INTERNET_ENVIRONMENT};
const save = () => fs.writeFileSync(process.env.AW_FIX_CAPTURE, JSON.stringify(capture));
const send = v => process.stdout.write(JSON.stringify(v) + '\\n');
save();
rl.on('line', line => {
  const q = JSON.parse(line);
  if (q.type === 'control_request') send({type:'control_response', response:{
    subtype:'success', request_id:q.request_id, response:{}}});
  if (q.type === 'user') {
    capture.users.push(q.message.content); save();
    send({type:'system',subtype:'init',session_id:'js-protocol-fixture'});
    const error = process.env.AW_FIX_LOGIN === 'required';
    send({type:'result',subtype:error?'error_during_execution':'success',is_error:error,
      session_id:'js-protocol-fixture',duration_ms:1,duration_api_ms:1,num_turns:1,
      result:error?'Please run /login.':'Fixture only',errors:error?['Please run /login.']:[],usage:{}});
  }
});
''', encoding="utf-8")
    monkeypatch.setenv("AW_FIX_CAPTURE", str(capture))
    monkeypatch.delenv("AW_FIX_LOGIN", raising=False)
    app.create("sea", "alice")
    config = sdk_config("codebuddy", executable=str(script), model="fixture-model")
    app.configure("sea", "alice", config)
    return app, config, script, capture, node


@pytest.mark.parametrize("needs_login", [False, True])
def test_selected_js_runs_via_node_and_auth_result_stays_separate(windows_js, monkeypatch, needs_login):
    app, config, script, capture, node = windows_js
    monkeypatch.setenv("CODEBUDDY_API_KEY", "fixture-key")
    monkeypatch.setenv("CODEBUDDY_BASE_URL", "https://fixture.invalid")
    monkeypatch.setenv("CODEBUDDY_INTERNET_ENVIRONMENT", "ioa")
    if needs_login:
        monkeypatch.setenv("AW_FIX_LOGIN", "required")
    binding = app.reserve("sea", "alice")["binding"]
    root = app.root("sea", "alice")
    adapter = native_sdk.NativeSDK(app, "sea", "alice", binding, root, config)
    try:
        adapter.connect()
        adapter.bootstrap("Literal task; not a shell & no login automation")
        completion = adapter.completed.get(timeout=10)
        adapter.completed.put(completion)
        runner = runtime.Runner(app, "sea", "alice")
        runner.binding, runner.adapter = binding, adapter
        runner._complete_inputs()
        assert adapter.session == "js-protocol-fixture"
        boot = read_json(root / f".aw-local/inputs/boot-{binding}.json")
        assert boot["state"] == ("failed" if needs_login else "completed")
        assert bool(boot.get("checkpoint_revision")) is not needs_login
        data = read_json(capture)
        assert data["cwd"] == str(root) and len(data["users"]) == 1
        assert "--input-format=stream-json" in data["argv"]
        assert data["key"] == "fixture-key" and data["endpoint"] == "https://fixture.invalid"
        assert data["environment"] == "ioa"
        assert adapter.client._transport._get_cli_path() == str(Path(node).resolve())
        assert Path(adapter.client._transport._build_args()[0]) == script
        if needs_login:
            assert "/login" in adapter.record.read_text(encoding="utf-8")
            assert not app.checkpoints("sea", "alice")
    finally:
        adapter.close()
    assert not adapter.thread.is_alive()
    assert app.agent("sea", "alice")["current"] == binding  # No implicit release on error/close.


def test_missing_node_fails_preflight_without_binding_or_handoff(windows_js, monkeypatch):
    app, config, script, capture, _ = windows_js
    monkeypatch.setattr(shutil, "which", lambda name: None)
    spawn = Mock(return_value={"state": "starting_runner"})
    monkeypatch.setattr(runtime, "spawn_runner", spawn)
    with pytest.raises(Unavailable, match="Node"):
        runtime.start(app, "sea", "alice")
    assert app.agent("sea", "alice")["current"] is None
    spawn.assert_not_called()
    assert not capture.exists()
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "old-fixture-session")
    with pytest.raises(Unavailable, match="Node"):
        transfer.request(app, "sea", "alice", config, request_id="target-js")
    assert not (app.root("sea", "alice") / ".aw-local/transfer.json").exists()
    assert app.agent("sea", "alice")["current"] == binding


def test_native_executable_keeps_original_sdk_client(app, monkeypatch):
    import sys
    monkeypatch.setattr(native_sdk, "os", SimpleNamespace(**{**vars(os), "name": "nt"}))
    sdk = pytest.importorskip("codebuddy_agent_sdk")
    config = sdk_config("codebuddy", executable=sys.executable)
    _, client_type, _, options = native_sdk.sdk_options(config, app, "sea", "alice", "b", app.home)
    assert client_type is sdk.CodeBuddySDKClient
    assert options["codebuddy_code_path"] == str(Path(sys.executable).resolve())
