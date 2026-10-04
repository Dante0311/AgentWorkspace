"""Explicit native metadata queries do not send prompts or expose account details."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from agent_workspace import commands, harness_config as hc
from agent_workspace.native_sdk import sdk_environment
from agent_workspace.util import Error


@pytest.fixture
def probe(tmp_path, monkeypatch):
    binary = tmp_path / 'claude'
    binary.write_text('not executed')
    for key in ('ANTHROPIC_BASE_URL', 'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY'):
        monkeypatch.delenv(key, raising=False)
    client = Mock()
    client.get_server_info = AsyncMock(return_value={
        'account': {'email': 'private@example.com', 'apiKey': 'do-not-expose'},
        'models': [{'value': 'native-model', 'displayName': 'Native model',
                    'supportedEffortLevels': ['low', 'high'], 'private': 'do-not-expose'}],
        'commands': [{'path': '/private/local/path'}],
    })
    context = Mock()
    context.__aenter__ = AsyncMock(return_value=client)
    context.__aexit__ = AsyncMock(return_value=False)
    sdk = SimpleNamespace(ClaudeAgentOptions=Mock(side_effect=lambda **kwargs: SimpleNamespace(**kwargs)),
                          ClaudeSDKClient=Mock(return_value=context))
    original_import = hc.importlib.import_module
    monkeypatch.setattr(hc.importlib, 'import_module',
                        lambda name, *args, **kw: sdk if name == 'claude_agent_sdk' else original_import(name, *args, **kw))
    return str(binary), sdk, client, context


def test_native_choices_are_returned_without_prompt_or_private_metadata(probe):
    binary, sdk, client, context = probe
    result = hc.inspect_sdk('claude', executable=binary)
    assert result['state'] == 'connected' and result['catalog'] == 'reported_by_claude'
    assert result['models'] == [{'id': 'native-model', 'model': 'native-model', 'displayName': 'Native model',
                                'supportedReasoningEfforts': [{'reasoningEffort': 'low'}, {'reasoningEffort': 'high'}]}]
    assert result['model_invoked'] is False
    assert not any(value in json.dumps(result) for value in ('private@example.com', 'do-not-expose', '/private/'))
    options = sdk.ClaudeAgentOptions.call_args.kwargs
    assert options['tools'] == [] and options['mcp_servers'] == {} and options['setting_sources'] == []
    client.query.assert_not_called()
    context.__aexit__.assert_awaited_once()


def test_custom_endpoint_uses_runtime_credential_routing_but_not_builtin_choices(probe, monkeypatch):
    binary, sdk, client, _ = probe
    monkeypatch.setenv('MY_CUSTOM_KEY', 'custom-secret')
    result = hc.inspect_sdk('claude', base_url='https://gateway.example', env_key='MY_CUSTOM_KEY', executable=binary)
    assert result['models'] == [] and result['catalog'] == 'custom_provider_unconfirmed'
    config = hc.sdk_config('claude', base_url='https://gateway.example', env_key='MY_CUSTOM_KEY', executable=binary)
    assert sdk.ClaudeAgentOptions.call_args.kwargs['env'] == sdk_environment(config)
    assert 'custom-secret' not in json.dumps(result)
    client.query.assert_not_called()


@pytest.mark.parametrize('variable', ['ANTHROPIC_BASE_URL', 'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY'])
def test_inherited_provider_cannot_claim_builtin_model_access(probe, monkeypatch, variable):
    binary, _, _, _ = probe
    monkeypatch.setenv(variable, 'https://gateway.example' if variable.endswith('URL') else '1')
    result = hc.inspect_sdk('claude', executable=binary)
    assert result['models'] == [] and result['catalog'] == 'custom_provider_unconfirmed'


def test_missing_credential_never_connects(probe, monkeypatch):
    binary, sdk, _, _ = probe
    monkeypatch.delenv('MISSING_TEST_KEY', raising=False)
    result = hc.inspect_sdk('claude', base_url='https://gateway.example', env_key='MISSING_TEST_KEY', executable=binary)
    assert result['state'] == 'credential_missing'
    sdk.ClaudeSDKClient.assert_not_called()


def test_codebuddy_without_verified_catalog_does_not_start_a_client(probe):
    binary, sdk, _, _ = probe
    result = hc.inspect_sdk('codebuddy', executable=binary)
    assert result['state'] == 'capability_unconfirmed' and result['catalog'] == 'unsupported'
    sdk.ClaudeSDKClient.assert_not_called()


@pytest.mark.parametrize('exception', [RuntimeError('secret-failure'), TimeoutError('secret-timeout')])
def test_probe_failure_closes_client_and_redacts_exception(probe, exception):
    binary, _, client, context = probe
    client.get_server_info.side_effect = exception
    result = hc.inspect_sdk('claude', executable=binary)
    assert result['state'] == 'capability_unconfirmed'
    assert 'secret-' not in json.dumps(result)
    context.__aexit__.assert_awaited_once()


def test_query_is_an_explicit_user_operation_not_a_model_tool(probe):
    binary, _, _, _ = probe
    app = Mock()
    with pytest.raises(Error, match='user-management'):
        commands.execute(app, 'setup.inspect-sdk', {'kind': 'claude', 'executable': binary}, actor=('sea', 'alice', 'binding'))
    app.require_binding.assert_not_called()
    result = commands.execute(app, 'setup.inspect-sdk', {'kind': 'claude', 'executable': binary})
    assert result['catalog'] == 'reported_by_claude'
