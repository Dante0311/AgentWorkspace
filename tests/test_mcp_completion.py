"""Real stdio and Git protocol fixtures; no cloud or native model session is created."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

import pytest

from agent_workspace import layout
from agent_workspace.commands import execute
from agent_workspace.mcp_completion import CompletionMCP
from agent_workspace.util import Conflict, read_json, write_json


@pytest.fixture
def endpoint(pair, tmp_path):
    app, bindings = pair
    path = 'knowledge/completion-brief.md'
    app.store('sea').change('main', {path: b'Isolated completion task: return nonce MCP-LOCAL-001.'},
                            {path: None}, 'Protocol fixture completion brief')
    config = tmp_path / 'completion.json'
    write_json(config, {'enabled': True, 'workspace': 'sea', 'agent_id': 'alice',
                       'binding': bindings['alice'], 'recipient': 'bob', 'material_paths': [path]})
    return app, bindings, config


class StdioClient:
    def __init__(self, app, config, inherited=None):
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'src'))
        for key in ('AW_AGENT', 'AW_BINDING', 'AW_WORKSPACE', 'CODEX_THREAD_ID', 'CODEX_APP_TOOLS_PIPE_PATH'):
            env.pop(key, None)
        env.update(inherited or {})
        self.process = subprocess.Popen([sys.executable, '-m', 'agent_workspace', '--home', str(app.home),
            'mcp', '--completion-config', str(config)], cwd=config.parent, env=env, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        self.responses = queue.Queue()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        self.sequence = 0

    def _read(self):
        for line in self.process.stdout:
            self.responses.put(json.loads(line))

    def request(self, method, params=None):
        self.sequence += 1
        self.process.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': self.sequence,
                                  'method': method, 'params': params or {}}) + '\n')
        self.process.stdin.flush()
        result = self.responses.get(timeout=30)
        assert result['id'] == self.sequence
        return result['result']

    def call(self, name, **arguments):
        result = self.request('tools/call', {'name': name, 'arguments': arguments})
        return result, json.loads(result['content'][0]['text'])

    def close(self):
        self.process.stdin.close()
        self.process.wait(timeout=10)
        self.reader.join(2)
        assert self.process.returncode == 0, self.process.stderr.read()


@pytest.fixture
def client(endpoint):
    app, _, config = endpoint
    connection = StdioClient(app, config)
    try:
        yield connection
    finally:
        connection.close()


def test_stdio_report_readback_receipt_and_receiver_reply(endpoint, client):
    app, bindings, _ = endpoint
    assert client.request('initialize', {'protocolVersion': '2024-11-05'})['capabilities'] == {'tools': {}}
    assert {tool['name'] for tool in client.request('tools/list')['tools']} == {
        'aw_report_completion', 'aw_report_status', 'aw_read_materials'}
    result, materials = client.call('aw_read_materials')
    assert not result.get('isError') and materials['complete']
    assert materials['files'][0]['content'].endswith('MCP-LOCAL-001.')
    result, report = client.call('aw_report_completion', request_id='report-001', content='Report nonce MCP-LOCAL-001.')
    assert not result.get('isError') and report['state'] == 'published'
    received = execute(app, 'message.receive', {'message_id': 'report-001'}, actor=('sea', 'bob', bindings['bob']))
    assert received['message']['content'] == 'Report nonce MCP-LOCAL-001.'
    reviewed = {'request_id': 'report-001', 'content': received['message']['content'], 'verified': True}
    execute(app, 'asset.write', {'path': 'reviews/completion.json', 'content': json.dumps(reviewed)},
            actor=('sea', 'bob', bindings['bob']))
    reply = execute(app, 'message.send', {'to': 'alice', 'content': 'Reviewed MCP-LOCAL-001.',
        'request_id': 'reply-001', 'message_refs': ['report-001']}, actor=('sea', 'bob', bindings['bob']))
    assert reply['state'] == 'published'
    result, status = client.call('aw_report_status', request_id='report-001')
    assert not result.get('isError') and status['notification_acknowledged']
    assert read_json(app.root('sea', 'bob') / 'reviews/completion.json') == reviewed
    assert execute(app, 'message.show', {'message_id': 'reply-001'}, actor=('sea', 'alice', bindings['alice']))[
        'message']['message_refs'] == ['report-001']


def test_lost_report_reply_queries_original_id_without_sending_again(endpoint, client):
    app, _, _ = endpoint
    # Discard the successful response, as a caller with an unknown transport result would.
    client.call('aw_report_completion', request_id='reply-lost', content='Original completion report.')
    receipt_path = app.home / 'operations/reply-lost.json'
    original = receipt_path.read_bytes()
    _, status = client.call('aw_report_status', request_id='reply-lost')
    assert status['state'] == 'published' and status['payload']['content'] == 'Original completion report.'
    assert receipt_path.read_bytes() == original
    snap = app.store('sea').snapshot()
    assert len([p for p in snap.entries if p == layout.shared_path(snap, 'messages/reply-lost.json')]) == 1


@pytest.mark.parametrize('name,arguments', [
    ('aw_execute', {'command': 'agent.create', 'arguments': {'name': 'outsider'}}),
    ('aw_report_completion', {'request_id': 'forbidden', 'content': 'report', 'to': 'outsider'}),
    ('aw_report_completion', {'request_id': None, 'content': 'report'}),
    ('aw_read_materials', {'paths': ['knowledge/not-granted.md']}),
])
def test_endpoint_rejects_management_scope_override_and_unstable_ids(endpoint, client, name, arguments):
    app, _, _ = endpoint
    result, error = client.call(name, **arguments)
    assert result['isError'] and error['code'] == 'operation_failed'
    assert not list((app.home / 'operations').glob('*.json'))
    assert [item['id'] for item in app.agents('sea')] == ['alice', 'bob']


def test_disabled_or_changed_configuration_rejects_existing_process(endpoint, client):
    app, _, config = endpoint
    original = read_json(config)
    write_json(config, {**original, 'enabled': False})
    result, _ = client.call('aw_report_completion', request_id='disabled', content='report')
    assert result['isError']
    write_json(config, {**original, 'recipient': 'alice'})
    result, _ = client.call('aw_report_completion', request_id='changed', content='report')
    assert result['isError'] and not list((app.home / 'operations').glob('*.json'))


def test_old_binding_cannot_write_but_can_inspect_its_original_receipt(endpoint, client):
    app, bindings, _ = endpoint
    client.call('aw_report_completion', request_id='original', content='Original report.')
    receipt = (app.home / 'operations/original.json').read_bytes()
    cp = app.checkpoint('sea', 'alice', 'Protocol fixture handoff', binding=bindings['alice'])
    app.stop('sea', 'alice', bindings['alice'], cp['id'])
    app.finish_stop('sea', 'alice', bindings['alice'], observed_idle=True)
    successor = app.reserve('sea', 'alice')['binding']
    app.bind('sea', 'alice', successor, 'fixture-successor')
    result, _ = client.call('aw_report_completion', request_id='stale', content='Must not publish.')
    assert result['isError'] and not (app.home / 'operations/stale.json').exists()
    result, status = client.call('aw_report_status', request_id='original')
    assert not result.get('isError') and status['binding'] == bindings['alice']
    assert (app.home / 'operations/original.json').read_bytes() == receipt
    result, _ = client.call('aw_read_materials')
    assert result['isError']


def test_status_cannot_read_another_senders_operation(endpoint, client):
    app, bindings, _ = endpoint
    execute(app, 'message.send', {'to': 'alice', 'content': 'Other operation.', 'request_id': 'other'},
            actor=('sea', 'bob', bindings['bob']))
    result, error = client.call('aw_report_status', request_id='other')
    assert result['isError'] and error['code'] == 'conflict'
    assert 'Other operation.' not in json.dumps(result)


def test_configuration_cannot_replace_inherited_identity(endpoint):
    app, bindings, config = endpoint
    with pytest.raises(Conflict):
        CompletionMCP(app, config, actor=('sea', 'bob', bindings['bob']))
    with pytest.raises(Conflict):
        CompletionMCP(app, config, workspace='different')
