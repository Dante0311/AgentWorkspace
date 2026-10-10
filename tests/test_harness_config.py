"""Native configuration and metadata contracts; no installed model service required."""
import json
import os
from pathlib import Path
import tomllib
from unittest.mock import Mock

import pytest

from agent_workspace import harness_config as hc
from agent_workspace.util import Conflict, Error


@pytest.fixture
def executable(tmp_path):
    binary = tmp_path / "codex"
    binary.write_text("not executed", encoding="utf-8")
    return str(binary)


def overrides(config):
    args = config["command"]
    assert args[-1] == "app-server"
    assert all(args[i] == "-c" for i in range(1, len(args) - 1, 2))
    return tomllib.loads("\n".join(args[2:-1:2]))


def test_native_model_provider_and_effort_are_process_local(executable, monkeypatch):
    monkeypatch.setenv("CUSTOM_KEY", "never-serialize-this-secret")
    config = hc.codex_config("model-one", "high", "https://gateway.example/v1", "CUSTOM_KEY", executable)
    value = overrides(config)
    provider = value["model_providers"]["aw_custom"]
    assert value["model"] == "model-one" and value["model_reasoning_effort"] == "high"
    assert provider["base_url"] == "https://gateway.example/v1"
    assert provider["env_key"] == "CUSTOM_KEY" and provider["wire_api"] == "responses"
    assert not provider["requires_openai_auth"]
    assert config["modelProvider"] == "aw_custom" and config["sandbox"] == "workspace-write"
    assert "never-serialize-this-secret" not in json.dumps(config)


@pytest.mark.parametrize("url", ["https://user:secret@host/v1", "https://host/v1?api_key=secret",
                                 "http://remote.example/v1", "https://host/v1&command", "https://host/v1\n"])
def test_provider_urls_reject_credentials_and_unsafe_syntax(executable, url):
    with pytest.raises(Error):
        hc.codex_config(base_url=url, executable=executable)


def test_local_service_can_omit_api_key(executable):
    config = hc.codex_config(base_url="http://127.0.0.1:1234/v1", executable=executable)
    assert "env_key" not in overrides(config)["model_providers"]["aw_custom"]


def test_empty_configuration_preserves_native_defaults(executable):
    config = hc.codex_config(executable=executable)
    assert config["command"] == [str(Path(executable).resolve()), "app-server"]
    assert "model" not in config and "modelProvider" not in config


def test_metadata_probe_has_no_session_or_turn_creation(executable, monkeypatch):
    rpc = Mock()
    rpc.request.side_effect = [{}, {"account": {"email": "private@example.com"}},
                              {"data": [{"id": "m", "model": "m", "supportedReasoningEfforts": [
                                  {"reasoningEffort": "medium"}], "private": "redact"}], "nextCursor": None}]
    monkeypatch.setattr(hc, "Rpc", Mock(return_value=rpc))
    result = hc.inspect_codex(executable=executable)
    assert [call.args[0] for call in rpc.request.call_args_list] == ["initialize", "account/read", "model/list"]
    assert not result["model_invoked"] and result["models"][0]["model"] == "m"
    assert "private@example.com" not in json.dumps(result) and "redact" not in json.dumps(result)
    rpc.close.assert_called_once()


def test_custom_service_does_not_inherit_unverified_native_model_catalog(executable, monkeypatch):
    rpc = Mock()
    rpc.request.side_effect = [{}, {"account": None, "requiresOpenaiAuth": False}]
    monkeypatch.setattr(hc, "Rpc", Mock(return_value=rpc))
    result = hc.inspect_codex(base_url="http://localhost:1234/v1", executable=executable)
    assert result["models"] == [] and result["catalog"] == "custom_provider_unconfirmed"
    assert [call.args[0] for call in rpc.request.call_args_list] == ["initialize", "account/read"]


def test_missing_credential_does_not_start_control_process(executable, monkeypatch):
    monkeypatch.delenv("CUSTOM_KEY", raising=False)
    launch = Mock(side_effect=AssertionError("must not run"))
    monkeypatch.setattr(hc, "Rpc", launch)
    assert hc.inspect_codex(base_url="https://example.com/v1", env_key="CUSTOM_KEY", executable=executable)["state"] == "credential_missing"
    launch.assert_not_called()


def test_launch_failure_is_reported_without_native_credentials(executable, monkeypatch):
    monkeypatch.setattr(hc, "Rpc", Mock(side_effect=OSError("private native details")))
    result = hc.inspect_codex(executable=executable)
    assert result["state"] == "capability_unconfirmed"
    assert "private native details" not in json.dumps(result)


def test_save_does_not_start_or_replace_active_session(executable, tmp_path):
    app = Mock()
    app.root.return_value = tmp_path
    app.agent.return_value = {"current": "active"}
    with pytest.raises(Conflict):
        hc.configure_codex(app, "sea", "worker", executable=executable)
    app.configure.assert_not_called()
    app.agent.return_value = {"current": None}
    app.configure.return_value = {"configured": True, "entry_changed": False}
    result = hc.configure_codex(app, "sea", "worker", executable=executable)
    assert not result["sessions_started"] and not result["global_configuration_changed"]
    assert result["model_access"] == "unchecked"


@pytest.mark.parametrize('kind', ['codex', 'claude', 'codebuddy'])
def test_model_context_suffix_is_preserved_for_profiles_and_ordinary_sessions(app, executable, tmp_path, kind):
    from agent_workspace import commands, sessions
    from agent_workspace.util import read_json
    model = 'claude-deepseek-v4.1-flash[1m]'
    app.create('sea', 'model-test')
    args = {'workspace': 'sea', 'agent_id': 'model-test', 'model': model, 'effort': 'low', 'executable': executable}
    command = 'agent.configure-codex' if kind == 'codex' else 'agent.configure-sdk'
    if kind != 'codex':
        args['kind'] = kind
    result = commands.execute(app, command, args)
    assert result['sessions_started'] is False and result['model_access'] == 'unchecked'
    profile = read_json(app.root('sea', 'model-test') / '.aw-local/runtime.json')
    if kind == 'codex':
        assert read_json(app.root('sea', 'model-test') / 'runtime.json')['codex']['model'] == model
        assert 'model' not in profile and 'model' not in overrides(profile)
    else:
        assert profile['model'] == model
    project = tmp_path / 'ordinary'
    project.mkdir()
    prepared = sessions.prepare(app, kind, str(project), model=model, effort='low',
                                executable=executable, request_id='same-model')
    argv = sessions._invocation(prepared['spec']['profile'], 'literal task')
    if kind == 'codex':
        assert 'model=' + json.dumps(model) in argv
    else:
        assert argv[argv.index('--model') + 1] == model
    assert prepared['state'] == 'prepared'
    assert app.agent('sea', 'model-test')['current'] is None


@pytest.mark.parametrize('kind', ['codex', 'claude', 'codebuddy'])
def test_model_context_suffix_reaches_transfer_profile_unchanged(app, executable, monkeypatch, kind):
    from agent_workspace import transfer
    from agent_workspace.util import read_json
    app.create('sea', 'alice')
    binding = app.reserve('sea', 'alice')['binding']
    app.bind('sea', 'alice', binding, 'source-session')
    preflight = Mock(return_value=None)  # Only test routing; do not open a native client.
    monkeypatch.setattr(transfer, 'preflight', preflight)
    model = 'claude-deepseek-v4.1-flash[1m]'
    result = transfer.request_profile(app, 'sea', 'alice', kind, model=model, effort='low',
                                      executable=executable, request_id='model-transfer')
    saved = read_json(app.root('sea', 'alice') / '.aw-local/transfer.json')
    assert saved['target_config']['model'] == model
    assert preflight.call_args.args[3]['model'] == model
    assert result['old_binding'] == binding and app.agent('sea', 'alice')['current'] == binding


@pytest.mark.parametrize('kind', ['codex', 'claude', 'codebuddy'])
@pytest.mark.parametrize('model', ['m\n--flag', 'm\0x', 'm;cmd', 'm&cmd', 'm|cmd', 'm"quote', 'm%PATH%', 'm!x'])
def test_model_validation_still_rejects_controls_and_shell_syntax(executable, kind, model):
    with pytest.raises(Error):
        if kind == 'codex':
            hc.codex_config(model=model, executable=executable)
        else:
            hc.sdk_config(kind, model=model, executable=executable)


@pytest.mark.parametrize('kind', ['codex', 'claude', 'codebuddy'])
def test_model_suffix_support_does_not_change_effort_or_credential_validation(executable, kind):
    factory = hc.codex_config if kind == 'codex' else lambda **kw: hc.sdk_config(kind, **kw)
    with pytest.raises(Error):
        factory(effort='low[1m]', executable=executable)
    with pytest.raises(Error):
        factory(env_key='KEY[1m]', base_url='https://fixture.invalid', executable=executable)
