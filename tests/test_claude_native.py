"""Installed Claude CLI and SDK against a loopback Messages fixture, without a model."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading

import pytest

from agent_workspace.harness_config import sdk_config
from agent_workspace.native_sdk import NativeSDK
from agent_workspace.messages import Messages


def test_installed_claude_tools_and_two_turns_custom_endpoint(app, tmp_path, monkeypatch):
    executable = os.environ.get('AW_TEST_CLAUDE')
    if not executable or not Path(executable).is_file():
        pytest.skip('An explicitly supplied Claude CLI is required.')
    pytest.importorskip('claude_agent_sdk')
    config_home = tmp_path / 'isolated-claude-config'
    config_home.mkdir()
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', str(config_home))
    monkeypatch.setenv('AW_TEST_CLAUDE_KEY', 'isolated-native-test-key')
    for name in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'CLAUDE_CODE_OAUTH_TOKEN', 'CLAUDECODE'):
        monkeypatch.delenv(name, raising=False)
    calls, tool_requests = [], []
    phase = [0]
    operations = [
        {"command": "checkpoint.create", "arguments": {"summary": "Checkpoint from the real Claude MCP client"}},
        {"command": "message.receive", "arguments": {"message_id": "native-message"}},
    ]
    class ModelFixture(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append((self.path, self.headers.get('Authorization'), body))
            message = {'id': 'msg-fixture', 'type': 'message', 'role': 'assistant', 'model': body.get('model'),
                       'content': [{'type': 'text', 'text': 'Isolated native fixture completed.'}],
                       'stop_reason': 'end_turn', 'stop_sequence': None, 'usage': {'input_tokens': 1, 'output_tokens': 1}}
            if body.get('stream') and body.get('tools') and phase[0] not in tool_requests:
                tool_requests.append(phase[0])
                message['content'] = [{'type': 'tool_use', 'id': 'tool-checkpoint',
                    'name': 'mcp__aw__aw_execute', 'input': operations[phase[0]]}]
                message['stop_reason'] = 'tool_use'
            block = message['content'][0]
            if block['type'] == 'tool_use':
                start = {**block, 'input': {}}
                delta = {'type': 'input_json_delta', 'partial_json': json.dumps(block['input'])}
            else:
                start = {'type': 'text', 'text': ''}
                delta = {'type': 'text_delta', 'text': block['text']}
            if body.get('stream'):
                events = [
                    {'type': 'message_start', 'message': {**message, 'content': [], 'stop_reason': None}},
                    {'type': 'content_block_start', 'index': 0, 'content_block': start},
                    {'type': 'content_block_delta', 'index': 0, 'delta': delta},
                    {'type': 'content_block_stop', 'index': 0},
                    {'type': 'message_delta', 'delta': {'stop_reason': message['stop_reason'], 'stop_sequence': None}, 'usage': {'output_tokens': 1}},
                    {'type': 'message_stop'},
                ]
                payload = ''.join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()
                content_type = 'text/event-stream'
            else:
                payload, content_type = json.dumps(message).encode(), 'application/json'
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
    server = ThreadingHTTPServer(('127.0.0.1', 0), ModelFixture)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    adapter = None
    try:
        app.create('sea', 'claude-native')
        root = app.root('sea', 'claude-native')
        config = sdk_config('claude', model='claude-sonnet-4-6', effort='low',
                            base_url=f'http://127.0.0.1:{server.server_port}', env_key='AW_TEST_CLAUDE_KEY', executable=executable)
        app.configure('sea', 'claude-native', config)
        binding = app.reserve('sea', 'claude-native')['binding']
        adapter = NativeSDK(app, 'sea', 'claude-native', binding, root, config)
        adapter.connect()
        adapter.bootstrap('Explicit isolated test: save one checkpoint through the platform MCP tool.')
        assert adapter.completed.get(timeout=45)['status'] == 'completed'
        session = adapter.session
        app.create('sea', 'sender')
        sender = app.reserve('sea', 'sender')['binding']
        app.bind('sea', 'sender', sender, 'sender-native-fixture')
        receipt = Messages(app).send('sea', 'sender', sender, 'claude-native',
                                     'Explicit native Message fixture.', request_id='native-message')
        assert receipt['state'] == 'published'
        phase[0] = 1
        response = adapter.notify('Explicit second protocol test: receive native-message through the platform tool.', 'normal')
        result = adapter.completed.get(timeout=45)
        assert result['status'] == 'completed' and result['id'] == response['turn']['id']
        assert adapter.session == session and app.show('sea', 'claude-native')['binding']['session'] == session
        model_calls = [(p, auth, body) for p, auth, body in calls if p.startswith('/v1/messages')]
        assert len(model_calls) >= 4
        assert tool_requests == [0, 1]
        assert Messages(app).show('sea', 'native-message')['ack'] == {'message_id': 'native-message'}
        assert (root / 'messages/native-message.json').is_file()
        points = app.checkpoints('sea', 'claude-native')
        assert len(points) == 1, adapter.record.read_text()
        saved = app.checkpoint_show('sea', 'claude-native', points[0]['id'])
        assert saved['record']['summary'] == 'Checkpoint from the real Claude MCP client'
        assert any(block.get('type') == 'tool_result' and not block.get('is_error')
                   for _, _, body in model_calls for msg in body.get('messages', [])
                   for block in msg.get('content', []) if isinstance(block, dict))
        assert all(auth == 'Bearer isolated-native-test-key' for _, auth, _ in model_calls)
        assert all(body['model'] == 'claude-sonnet-4-6' for _, _, body in model_calls)
        assert not (config_home / 'settings.json').exists()
    finally:
        if adapter:
            adapter.close()
        server.shutdown()
        server.server_close()
        worker.join(5)
