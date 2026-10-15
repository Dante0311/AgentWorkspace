"""The public CLI keeps connection secrets and revocation under user control."""
import json
import os

import pytest

from agent_workspace import cli, commands
from agent_workspace.app import App
from agent_workspace.util import Error


@pytest.mark.parametrize('command', ['web-courier.connect', 'web-courier.status', 'web-courier.revoke'])
def test_model_cannot_manage_a_courier_connection(tmp_path, command):
    app = App(tmp_path / 'home')
    with pytest.raises(Error, match='explicit user operations'):
        commands.execute(app, command, {}, actor=('sea', 'steward', 'old-entry'))
    assert not (app.home / 'web-courier').exists()


def test_user_cli_connect_status_and_revoke_do_not_publish_agent_state(app, tmp_path, monkeypatch, capsys):
    target = 'https://chatgpt.com/c/11111111-1111-4111-8111-111111111111'
    app.create('sea', 'receiver')
    binding = app.reserve('sea', 'receiver')['binding']
    app.bind('sea', 'receiver', binding, target.rsplit('/', 1)[1])
    before = app.store('sea').head('main')
    for name in list(os.environ):
        if name.startswith('AW_'):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)

    def run(*arguments):
        assert cli.main(['--home', str(app.home), *arguments]) == 0
        return json.loads(capsys.readouterr().out)['result']

    connected = run('-w', 'sea', 'web-courier', 'connect', 'receiver', '--binding', binding,
                    '--target-url', target, '--extension-id', 'a' * 32,
                    '--request-id', 'connection-one', '--port', '18765')
    assert connected['connection_id'] == 'connection-one' and connected['token']
    assert connected['backend_url'] == 'http://127.0.0.1:18765'
    with pytest.raises(Error, match='explicit user operations'):
        commands.execute(app, 'web-courier.status', {'connection_id': 'connection-one'},
                         actor=('sea', 'another-agent', 'another-binding'))
    observed = run('web-courier', 'status', 'connection-one')
    assert observed['eligible'] is True and observed['attempt'] is None and observed['ack'] is None
    assert 'token' not in observed and connected['token'] not in json.dumps(observed)
    revoked = run('web-courier', 'revoke', 'connection-one', '--request-id', 'revoke-one')
    assert revoked['state'] == 'revoked'
    assert run('web-courier', 'revoke', 'connection-one', '--request-id', 'revoke-one') == revoked
    assert run('web-courier', 'status', 'connection-one')['eligible'] is False
    assert app.store('sea').head('main') == before
