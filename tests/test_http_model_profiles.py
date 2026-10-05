"""Explicit plaintext model-service consent, with no external network/model calls."""
import json
from pathlib import Path
import sys
import threading
import tomllib
from unittest.mock import Mock
import urllib.error
import urllib.request

import pytest

from agent_workspace import harness_config as hc, maintenance, transfer
from agent_workspace.cli import parser
from agent_workspace.native_sdk import sdk_environment
from agent_workspace.server import make_server
from agent_workspace.util import Error, read_json


KINDS = ('codex', 'claude', 'codebuddy')
# Documentation-only address, deliberately not assumed to be a private IP.
URL = 'http://192.0.2.75:4000'


def profile(kind, **kwargs):
    kwargs.setdefault('executable', sys.executable)
    return hc.codex_config(**kwargs) if kind == 'codex' else hc.sdk_config(kind, **kwargs)


def saved_url(config):
    if config['kind'] != 'codex':
        return config['provider']['base_url']
    args = config['command']
    return tomllib.loads('\n'.join(args[2:-1:2]))['model_providers']['aw_custom']['base_url']


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('url', [URL + '/v1', 'http://models.internal:4000', 'http://[fd00::25]:4000/v1'])
def test_http_requires_explicit_consent_and_keeps_exact_path(kind, url):
    with pytest.raises(Error, match='allow-http'):
        profile(kind, base_url=url)
    config = profile(kind, base_url=url, allow_http=True, env_key='LOCAL_MODEL_KEY')
    assert config['allow_http'] is True
    assert saved_url(config) == url
    # No global allowlist or IP classification: each new configuration defaults closed.
    with pytest.raises(Error, match='allow-http'):
        profile(kind, base_url=url)


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('url', ['https://models.example/v1', 'http://localhost:4000/v1', 'http://127.0.0.1:4000', 'http://[::1]:4000'])
def test_https_and_existing_loopback_defaults_are_unchanged(kind, url):
    config = profile(kind, base_url=url)
    assert saved_url(config) == url and 'allow_http' not in config


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('url', ['http://user:secret@models.internal:4000', 'http://models.internal:4000?key=secret', 'file:///tmp/model'])
def test_consent_does_not_relax_credential_or_scheme_checks(kind, url):
    with pytest.raises(Error):
        profile(kind, base_url=url, allow_http=True)


@pytest.mark.parametrize('value', ['false', 'true', 1, None])
@pytest.mark.parametrize('kind', KINDS)
def test_json_consent_requires_a_real_boolean(kind, value):
    with pytest.raises(Error, match='boolean'):
        profile(kind, base_url=URL, allow_http=value)


@pytest.mark.parametrize('kind', KINDS)
def test_metadata_probe_requires_consent_before_launch(kind, monkeypatch):
    rpc = Mock(side_effect=AssertionError('No native launch'))
    load_sdk = Mock(side_effect=AssertionError('No SDK import'))
    monkeypatch.setattr(hc, 'Rpc', rpc)
    monkeypatch.setattr(hc.importlib, 'import_module', load_sdk)
    probe = hc.inspect_codex if kind == 'codex' else lambda **kw: hc.inspect_sdk(kind, **kw)
    with pytest.raises(Error, match='allow-http'):
        probe(base_url=URL, executable=sys.executable)
    monkeypatch.delenv('AW_TEST_MISSING_MODEL_KEY', raising=False)
    result = probe(base_url=URL, env_key='AW_TEST_MISSING_MODEL_KEY', executable=sys.executable, allow_http=True)
    assert result['state'] == 'credential_missing' and result['model_invoked'] is False
    rpc.assert_not_called()
    load_sdk.assert_not_called()


@pytest.mark.parametrize('kind', KINDS)
def test_http_api_saves_one_profile_without_launching_or_publishing_credentials(app, kind, monkeypatch):
    app.create('sea', 'http-user')
    monkeypatch.setenv('LOCAL_MODEL_KEY', 'fixture-secret-never-publish')
    server = make_server(app, 0, 'test-token')
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    command = 'agent.configure-codex' if kind == 'codex' else 'agent.configure-sdk'
    arguments = {'workspace': 'sea', 'agent_id': 'http-user', 'base_url': URL + ('/v1' if kind == 'codex' else ''),
                 'executable': sys.executable, 'env_key': 'LOCAL_MODEL_KEY', 'model': 'test-model'}
    if kind != 'codex':
        arguments['kind'] = kind

    def post():
        request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/execute',
            data=json.dumps({'command': command, 'arguments': arguments}).encode(),
            headers={'Authorization': 'Bearer test-token', 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)['result']

    try:
        config_path = app.root('sea', 'http-user') / '.aw-local/runtime.json'
        with pytest.raises(urllib.error.HTTPError) as exc:
            post()
        assert 'allow-http' in exc.value.read().decode()
        assert not config_path.exists()
        arguments['allow_http'] = True
        result = post()
        assert result['sessions_started'] is False
        config = read_json(config_path)
        assert config['allow_http'] is True and saved_url(config) == arguments['base_url']
        assert 'fixture-secret-never-publish' not in config_path.read_text(encoding='utf-8')
        assert app.agent('sea', 'http-user')['current'] is None
        assert (app.root('sea', 'http-user') / 'AGENTS.md').is_file()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
        assert not thread.is_alive()


@pytest.mark.parametrize('kind', KINDS)
def test_transfer_requires_consent_before_requesting_old_handoff(kind, monkeypatch):
    request = Mock(return_value={'state': 'test-only'})
    monkeypatch.setattr(transfer, 'request', request)
    app = Mock()
    args = dict(kind=kind, base_url=URL, executable=sys.executable, request_id='same-transfer')
    with pytest.raises(Error, match='allow-http'):
        transfer.request_profile(app, 'sea', 'alice', **args)
    request.assert_not_called()
    transfer.request_profile(app, 'sea', 'alice', **args, allow_http=True)
    config = request.call_args.args[3]
    assert config['allow_http'] is True and saved_url(config) == URL
    assert request.call_args.args[4] == 'same-transfer'


@pytest.mark.parametrize('kind', ('claude', 'codebuddy'))
def test_sdk_receives_exact_gateway_address_and_isolated_credential(kind, monkeypatch):
    monkeypatch.setenv('LOCAL_MODEL_KEY', 'custom-test-key')
    config = profile(kind, base_url=URL, env_key='LOCAL_MODEL_KEY', allow_http=True)
    env = sdk_environment(config)
    assert env['ANTHROPIC_BASE_URL' if kind == 'claude' else 'CODEBUDDY_BASE_URL'] == URL
    assert 'custom-test-key' not in json.dumps(config)


@pytest.mark.parametrize('action', ('configure-codex', 'configure-sdk', 'transfer-profile'))
def test_cli_exposes_explicit_http_flag(action):
    args = ['agent', action, 'alice', '--base-url', URL, '--allow-http']
    if action != 'configure-codex':
        args += ['--kind', 'claude']
    assert parser().parse_args(args).allow_http is True
    assert parser().parse_args([a for a in args if a != '--allow-http']).allow_http is False


@pytest.mark.parametrize('command', ('agent.configure-codex', 'agent.configure-sdk', 'agent.transfer-profile'))
def test_caretaker_cannot_grant_itself_new_plaintext_consent(command):
    app = Mock()
    assert maintenance.allowed(app, ('sea', 'steward', 'binding'), command, {'allow_http': True}) is False
    app.store.assert_not_called()


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('url', ['http://127.0.0.1:bad', 'http://models.internal:70000', 'http://[broken', 'https://models.internal:0'])
def test_invalid_model_url_fails_before_runtime_launch(kind, url):
    with pytest.raises(Error, match='URL|port'):
        profile(kind, base_url=url, allow_http=True)
