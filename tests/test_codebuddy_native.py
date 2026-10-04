"""Installed CodeBuddy CLI/SDK against a local Chat Completions fixture."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading

import pytest

from agent_workspace.harness_config import sdk_config
from agent_workspace.native_sdk import NativeSDK
from agent_workspace.messages import Messages


def test_installed_codebuddy_tools_and_two_turns_custom_endpoint(app, tmp_path, monkeypatch):
    executable = os.environ.get('AW_TEST_CODEBUDDY')
    if not executable or not Path(executable).is_file():
        pytest.skip('An explicitly supplied CodeBuddy CLI is required.')
    pytest.importorskip('codebuddy_agent_sdk')
    home = tmp_path / 'isolated-codebuddy-home'
    home.mkdir()
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('AW_TEST_CODEBUDDY_KEY', 'isolated-codebuddy-test-key')
    for name in ('CODEBUDDY_API_KEY', 'CODEBUDDY_AUTH_TOKEN', 'CODEBUDDY_BASE_URL', 'CODEBUDDY_INTERNET_ENVIRONMENT'):
        monkeypatch.delenv(name, raising=False)
    calls, tool_requests = [], []
    phase = [0]
    operations = [
        {"command": "checkpoint.create", "arguments": {"summary": "Checkpoint from the real CodeBuddy MCP client"}},
        {"command": "message.receive", "arguments": {"message_id": "native-message"}},
    ]

    class ModelFixture(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append((self.path, self.headers.get('Authorization'), body))
            if self.path.endswith('/chat/completions'):
                base = {'id': 'chatcmpl-fixture', 'object': 'chat.completion.chunk', 'created': 1, 'model': body.get('model')}
                chunks = [{**base, 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': 'Isolated native fixture completed.'}, 'finish_reason': None}]},
                          {**base, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}]
                if body.get('tools') and phase[0] not in tool_requests:
                    tool_requests.append(phase[0])
                    chunks = [{**base, 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'tool_calls': [{
                        'index': 0, 'id': 'call-checkpoint', 'type': 'function', 'function': {
                            'name': 'mcp__aw__aw_execute', 'arguments': json.dumps(operations[phase[0]])}}]},
                        'finish_reason': None}]},
                        {**base, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'tool_calls'}],
                         'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}]
                payload = (''.join('data: ' + json.dumps(item) + '\n\n' for item in chunks) + 'data: [DONE]\n\n').encode()
                content_type = 'text/event-stream'
            else:
                payload, content_type = b'{"error":{"message":"unexpected fixture endpoint"}}', 'application/json'
            self.send_response(200 if self.path.endswith('/chat/completions') else 404)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(('127.0.0.1', 0), ModelFixture)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    adapter = None
    try:
        app.create('sea', 'codebuddy-native')
        root = app.root('sea', 'codebuddy-native')
        config = sdk_config('codebuddy', model='gpt-4o', base_url=f'http://127.0.0.1:{server.server_port}/v1',
                            env_key='AW_TEST_CODEBUDDY_KEY', executable=executable)
        app.configure('sea', 'codebuddy-native', config)
        binding = app.reserve('sea', 'codebuddy-native')['binding']
        adapter = NativeSDK(app, 'sea', 'codebuddy-native', binding, root, config)
        adapter.connect()
        adapter.bootstrap('Explicit isolated test: save one checkpoint through the platform MCP tool.')
        first = adapter.completed.get(timeout=30)
        assert first['status'] == 'completed', (first, calls, adapter.record.read_text())
        session = adapter.session
        app.create('sea', 'sender')
        sender = app.reserve('sea', 'sender')['binding']
        app.bind('sea', 'sender', sender, 'sender-native-fixture')
        receipt = Messages(app).send('sea', 'sender', sender, 'codebuddy-native',
                                     'Explicit native Message fixture.', request_id='native-message')
        assert receipt['state'] == 'published'
        phase[0] = 1
        sent = adapter.notify('Explicit second protocol test: receive native-message through the platform tool.', 'normal')
        result = adapter.completed.get(timeout=30)
        assert result['status'] == 'completed' and result['id'] == sent['turn']['id']
        assert adapter.session == session and app.show('sea', 'codebuddy-native')['binding']['session'] == session
        model_calls = [(p, auth, body) for p, auth, body in calls if p.endswith('/chat/completions')]
        assert len(model_calls) >= 4
        assert tool_requests == [0, 1]
        assert Messages(app).show('sea', 'native-message')['ack'] == {'message_id': 'native-message'}
        assert (root / 'messages/native-message.json').is_file()
        points = app.checkpoints('sea', 'codebuddy-native')
        assert len(points) == 1, adapter.record.read_text()
        saved = app.checkpoint_show('sea', 'codebuddy-native', points[0]['id'])
        assert saved['record']['summary'] == 'Checkpoint from the real CodeBuddy MCP client'
        assert any(msg.get('role') == 'tool' and msg.get('tool_call_id') == 'call-checkpoint'
                   for _, _, body in model_calls for msg in body.get('messages', []))
        assert all(auth == 'Bearer isolated-codebuddy-test-key' for _, auth, _ in model_calls)
        assert all(body['model'] == 'gpt-4o' for _, _, body in model_calls)
        assert not (home / '.codebuddy/settings.json').exists()
    finally:
        if adapter:
            adapter.close()
        server.shutdown()
        server.server_close()
        worker.join(5)
