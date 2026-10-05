"""Ordinary native launch boundaries, not a model-quality or desktop acceptance test."""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from agent_workspace.app import App
from agent_workspace.commands import execute
from agent_workspace import sessions
from agent_workspace.util import Conflict, Error, Unavailable, read_json, write_json


@pytest.fixture
def ordinary(tmp_path):
    app = App(tmp_path / 'app')
    root = tmp_path / 'shared-project'
    root.mkdir()
    (root / 'AGENTS.md').write_text('Shared project rules.', encoding='utf-8')
    return app, root


def prepare(ordinary, **kw):
    app, root = ordinary
    return sessions.prepare(app, 'claude', str(root), executable=sys.executable,
                            request_id='ordinary-1', **kw)


def test_prepare_has_no_workspace_or_git_requirement(ordinary, monkeypatch):
    app, root = ordinary
    app.store = Mock(side_effect=AssertionError('No Workspace access'))
    monkeypatch.setattr(sessions.subprocess, 'Popen', Mock(side_effect=AssertionError('No process')))
    result = prepare(ordinary, prompt='Review only, do not edit.')
    assert result['state'] == 'prepared' and result['native_session'] == 'not_observed'
    assert not app.registry.exists() and app.workspace_list() == []
    assert list(root.iterdir()) == [root / 'AGENTS.md']
    assert (root / 'AGENTS.md').read_text() == 'Shared project rules.'
    assert result == sessions.show(app, result['id'])
    assert len(list((app.home / 'ordinary-sessions').glob('*.json'))) == 1


def test_retry_keeps_spec_and_never_reopens_terminal(ordinary, monkeypatch):
    app, root = ordinary
    prepare(ordinary, prompt='one task')
    monkeypatch.setattr(sessions, '_terminal', Mock(return_value=([sys.executable, '-c', 'pass'], {})))
    popen = Mock()
    monkeypatch.setattr(sessions.subprocess, 'Popen', popen)
    first = sessions.open_terminal(app, 'ordinary-1')
    assert first['state'] == 'terminal_requested'
    assert prepare(ordinary, prompt='one task')['state'] == first['state']
    sessions.open_terminal(app, 'ordinary-1')
    assert popen.call_count == 1
    with pytest.raises(Conflict):
        prepare(ordinary, prompt='different task')


def test_no_terminal_reports_exact_resume_without_replacing_mode(ordinary, monkeypatch):
    app, root = ordinary
    prepare(ordinary)
    monkeypatch.setattr(sessions, '_terminal', Mock(side_effect=Unavailable('No terminal')))
    result = sessions.open_terminal(app, 'ordinary-1')
    assert result['state'] == 'prepared' and result['terminal_available'] is False
    assert result['run_argv'][-3:] == ['session', 'run', 'ordinary-1']
    assert str(app.home) in result['run_argv']


@pytest.mark.parametrize('name', ['session.prepare', 'session.open', 'session.show'])
def test_model_cannot_launch_or_read_user_ordinary_sessions(ordinary, name):
    app, _ = ordinary
    with pytest.raises(Error, match='user-management'):
        execute(app, name, {}, actor=('sea', 'steward', 'old-binding'))
    assert not app.registry.exists()


def test_managed_instance_directory_cannot_bypass_binding(ordinary):
    app, root = ordinary
    (root / '.aw-local').mkdir()
    (root / '.aw-local/context.json').write_text('{}')
    child = root / 'notes'
    child.mkdir()
    for path in (root, child):
        with pytest.raises(Conflict, match='Agent instance'):
            sessions.prepare(app, 'codex', str(path), executable=sys.executable)


@pytest.mark.parametrize('kind', ['codex', 'claude', 'codebuddy'])
def test_credentials_and_platform_identity_not_copied_to_receipt(ordinary, kind, monkeypatch):
    app, root = ordinary
    for key in ('AW_HOME', 'AW_WORKSPACE', 'AW_AGENT', 'AW_BINDING', 'CODEX_THREAD_ID', 'CODEX_APP_TOOLS_PIPE_PATH'):
        monkeypatch.setenv(key, 'old-entry-secret')
    monkeypatch.setenv('TEST_LOCAL_KEY', 'fixture-secret')
    result = sessions.prepare(app, kind, str(root), base_url='http://192.0.2.1:4000/v1',
        allow_http=True, env_key='TEST_LOCAL_KEY', executable=sys.executable)
    profile = result['spec']['profile']
    env = sessions._environment(profile)
    assert not sessions._IDENTITY_ENV.intersection(env)
    assert 'fixture-secret' in env.values()
    assert 'fixture-secret' not in json.dumps(result)
    assert 'old-entry-secret' not in json.dumps(result)
    assert profile['allow_http'] is True


def test_task_is_one_literal_argument_not_shell_or_project_instruction(ordinary):
    task = '-p; $(echo injected) "quoted"\nReview only.'
    value = prepare(ordinary, prompt=task)
    argv = sessions._invocation(value['spec']['profile'], task)
    assert argv[-2:] == ['--', task]
    assert '--dangerously-skip-permissions' not in argv and '-p' not in argv
    assert 'app-server' not in argv and '--mcp-config' not in argv


def test_batch_wrapper_rejected_before_saved_launch(ordinary):
    app, root = ordinary
    wrapper = root / 'claude.cmd'
    wrapper.touch()
    with pytest.raises(Error, match='.cmd/.bat'):
        sessions.prepare(app, 'claude', str(root), executable=str(wrapper), prompt='one&two')
    assert not (app.home / 'ordinary-sessions').exists()


def test_native_failure_cannot_replay_original_task(ordinary, monkeypatch):
    app, root = ordinary
    prepare(ordinary)
    monkeypatch.setattr(sessions.sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr(sessions.subprocess, 'Popen', Mock(side_effect=OSError('fixture failure')))
    with pytest.raises(OSError):
        sessions.run(app, 'ordinary-1')
    assert sessions.show(app, 'ordinary-1')['state'] == 'outcome_unknown'
    with pytest.raises(Conflict, match='already attempted'):
        sessions.run(app, 'ordinary-1')


def test_worker_rechecks_missing_credentials_and_can_continue_before_spawn(ordinary, monkeypatch):
    app, root = ordinary
    monkeypatch.delenv('ORDINARY_MISSING_KEY', raising=False)
    prepare(ordinary, base_url='https://models.invalid', env_key='ORDINARY_MISSING_KEY')
    monkeypatch.setattr(sessions.sys.stdin, 'isatty', lambda: True)
    process = Mock(pid=123, wait=Mock(return_value=0))
    popen = Mock(return_value=process)
    monkeypatch.setattr(sessions.subprocess, 'Popen', popen)
    with pytest.raises(Unavailable, match='Credential'):
        sessions.run(app, 'ordinary-1')
    popen.assert_not_called()
    assert sessions.show(app, 'ordinary-1')['state'] == 'preflight_failed'
    monkeypatch.setenv('ORDINARY_MISSING_KEY', 'fixture-secret')
    assert sessions.run(app, 'ordinary-1') == 0
    assert sessions.show(app, 'ordinary-1')['state'] == 'native_exited'
    assert popen.call_args.kwargs['cwd'] == root


def test_cli_prepare_without_workspace(ordinary):
    app, root = ordinary
    env = {k: v for k, v in os.environ.items() if not k.startswith('AW_')}
    args = [sys.executable, '-m', 'agent_workspace', '--home', str(app.home), 'session', 'prepare',
            '--kind', 'claude', '--directory', str(root), '--executable', sys.executable, '--request-id', 'from-cli']
    result = subprocess.run(args, env=env, capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['result']['state'] == 'prepared'
    assert not app.registry.exists()


@pytest.mark.skipif(os.name == 'nt', reason='POSIX PTY transport fixture; Windows launch flags have separate tests.')
def test_real_interactive_worker_forwards_literal_task_and_environment(ordinary, monkeypatch):
    import pty
    app, root = ordinary
    output = app.home / 'native-fixture.json'
    fake = app.home / 'native-fixture'
    fake.write_text('#!' + sys.executable + '\nimport json,os,sys\nfrom pathlib import Path\n'
        'Path(os.environ["CAPTURE_FILE"]).write_text(json.dumps({"args":sys.argv[1:],"cwd":os.getcwd(),'
        '"has_binding":"AW_BINDING" in os.environ,"key":os.environ.get("ANTHROPIC_AUTH_TOKEN")}))\n')
    fake.chmod(0o755)
    sessions.prepare(app, 'claude', str(root), executable=str(fake), request_id='pty-launch',
        prompt='literal;& not a shell', base_url='http://127.0.0.1:1', env_key='TEST_NATIVE_KEY')
    env = {k: v for k, v in os.environ.items() if not k.startswith('AW_')}
    env.update(CAPTURE_FILE=str(output), TEST_NATIVE_KEY='fake-key-not-a-real-credential')
    master, slave = pty.openpty()
    try:
        result = subprocess.run(sessions.show(app, 'pty-launch')['run_argv'], env=env,
            stdin=slave, capture_output=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
    finally:
        os.close(slave)
        os.close(master)
    assert result.returncode == 0, result.stderr
    value = json.loads(output.read_text())
    assert value['args'][-2:] == ['--', 'literal;& not a shell']
    assert value['cwd'] == str(root) and value['has_binding'] is False and value['key'].startswith('fake-key')
    assert sessions.show(app, 'pty-launch')['state'] == 'native_exited'
    assert not app.registry.exists()


@pytest.mark.parametrize('kind,variable', [('codex', 'AW_TEST_CODEX'), ('claude', 'AW_TEST_CLAUDE'), ('codebuddy', 'AW_TEST_CODEBUDDY')])
def test_installed_cli_accepts_launch_configuration_flags(ordinary, kind, variable):
    executable = os.environ.get(variable)
    if not executable:
        pytest.skip('Explicit installed native test executable required.')
    app, root = ordinary
    value = sessions.prepare(app, kind, str(root), executable=executable, model='fixture-model', effort='low')
    argv = sessions._invocation(value['spec']['profile'], '') + ['--help']
    result = subprocess.run(argv, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert 'Usage:' in result.stdout
    assert value['state'] == 'prepared' and not app.registry.exists()


def test_windows_terminal_uses_direct_python_console_without_cmd(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(sessions, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(sessions.subprocess, 'CREATE_NEW_CONSOLE', 16, raising=False)
    argv = ['C:/Program Files/Python/python.exe', '-m', 'agent_workspace', '--home', 'D:/用户 & data', 'session', 'run', 'request-1']
    result, options = sessions._terminal(argv)
    assert result == argv and options == {'creationflags': 16}


def test_macos_terminal_only_contains_quoted_controller_not_prompt_or_credentials(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(sessions, 'os', SimpleNamespace(name='posix'))
    monkeypatch.setattr(sessions.sys, 'platform', 'darwin')
    argv = ['/opt/python', '-m', 'agent_workspace', '--home', '/Users/示例/aw\'s home', 'session', 'run', 'request-1']
    result, options = sessions._terminal(argv)
    assert result[:2] == ['/usr/bin/osascript', '-e']
    assert '示例' in result[-1] and '\\u' not in result[-1]
    assert 'do script' in result[-1] and options == {}
