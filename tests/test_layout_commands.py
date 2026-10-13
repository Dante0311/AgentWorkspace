"""Migration stays explicit and public recovery preserves unrelated controls."""
import json
from types import SimpleNamespace

import pytest

from agent_workspace import backend, cli, commands, layout
from agent_workspace.app import App
from agent_workspace.util import Error, read_json, write_json


def test_layout_plan_cli_limits_instances_without_writing(app, monkeypatch, capsys):
    app.create('sea', 'alice')
    app.create('sea', 'bob')
    before = {branch: app.store('sea').snapshot(branch).revision
              for branch in ('main', 'instance/alice', 'instance/bob')}
    for name in ('AW_AGENT', 'AW_BINDING', 'AW_WORKSPACE'):
        monkeypatch.delenv(name, raising=False)
    assert cli.main(['--home', str(app.home), '-w', 'sea',
                     'layout', 'plan', '--agent', 'alice']) == 0
    result = json.loads(capsys.readouterr().out)['result']
    assert result['writes_performed'] is False
    assert [item['agent_id'] for item in result['instances']] == ['alice']
    assert {branch: app.store('sea').snapshot(branch).revision for branch in before} == before


def test_agent_cannot_perform_shared_layout_migration(tmp_path):
    app = App(tmp_path / 'home')
    with pytest.raises(Error, match='explicit user operation'):
        commands.execute(app, 'layout.migrate', {
            'workspace': 'sea', 'request_id': 'migration', 'migrate_shared': True,
        }, actor=('sea', 'steward', 'old-entry'))


def test_explicit_runtime_start_uses_recovery_and_preserves_watch_pause(app):
    app.create('sea', 'alice')
    binding = app.reserve('sea', 'alice')['binding']
    app.bind('sea', 'alice', binding, 'manual-session')
    root = app.root('sea', 'alice')
    control = layout.local_path(root, 'control.json')
    write_json(control, {'stop': binding, 'other_control': 'keep'})
    watch = layout.local_path(root, 'watch.json')
    write_json(watch, {'enabled': False})
    app.backend = backend.Backend(app, SimpleNamespace(server_port=12345))
    try:
        assert backend.recover(app, 'sea', 'alice')['state'] == 'recovery_paused'
        result = commands.execute(app, 'runtime.start', {'workspace': 'sea', 'agent_id': 'alice'})
        assert result['state'] == 'recovery_blocked'
        assert result['reason_code'] == 'independent_observation_unavailable'
        assert read_json(control) == {'stop': None, 'other_control': 'keep'}
        assert read_json(watch) == {'enabled': False}
        assert not app.backend.runners
    finally:
        del app.backend
