"""Real native clients and platform lifecycle against isolated loopback model APIs."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading

import pytest


def test_native_codex_to_claude_transfer_and_message(app, tmp_path, monkeypatch):
    """Both clients are real; a local model fixture requests checkpoint, stop and ACK."""
    import time
    from agent_workspace import runtime, transfer
    from agent_workspace.harness_config import codex_config, sdk_config
    from agent_workspace.messages import Messages
    from agent_workspace.util import Conflict, read_json

    codex, claude = os.environ.get('AW_TEST_CODEX'), os.environ.get('AW_TEST_CLAUDE')
    if not all(path and Path(path).is_file() for path in (codex, claude)):
        pytest.skip('Explicit Codex and Claude executables are required for native transfer.')
    pytest.importorskip('claude_agent_sdk')
    for variable, name in (('CODEX_HOME', 'codex-home'), ('CLAUDE_CONFIG_DIR', 'claude-home')):
        home = tmp_path / name
        home.mkdir()
        monkeypatch.setenv(variable, str(home))
    monkeypatch.setenv('AW_TEST_TRANSFER_KEY', 'isolated-transfer-key')
    for name in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN',
                 'CLAUDE_CODE_OAUTH_TOKEN', 'CLAUDECODE'):
        monkeypatch.delenv(name, raising=False)
    phase = {'handoff': False, 'codex_step': 0, 'receive': False, 'acked': False}
    codex_calls, claude_calls = [], []
    handoff_tools = [
        {'command': 'checkpoint.create', 'arguments': {'checkpoint_id': 'transfer-cp',
         'summary': 'Real native cross-Harness handoff fixture'}},
        {'command': 'agent.stop', 'arguments': {'checkpoint': 'transfer-cp'}},
    ]

    class ModelFixture(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path == '/v1/responses':
                codex_calls.append(body)
                index = len(codex_calls)
                item = {'id': f'msg-{index}', 'type': 'message', 'role': 'assistant', 'status': 'completed',
                        'content': [{'type': 'output_text', 'text': 'Explicit native fixture done.', 'annotations': []}]}
                step = phase['codex_step']
                if phase['handoff'] and step < len(handoff_tools):
                    phase['codex_step'] += 1
                    item = {'id': f'fc-{index}', 'type': 'function_call', 'call_id': f'call-{index}',
                            'name': 'aw_execute', 'arguments': json.dumps(handoff_tools[step]), 'status': 'completed'}
                events = [
                    {'type': 'response.created', 'response': {'id': f'resp-{index}', 'status': 'in_progress', 'output': []}},
                    {'type': 'response.output_item.done', 'output_index': 0, 'item': item},
                    {'type': 'response.completed', 'response': {'id': f'resp-{index}', 'status': 'completed',
                     'output': [item], 'usage': {'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2}}},
                ]
            else:
                claude_calls.append(body)
                if self.path.endswith('/count_tokens'):
                    payload, content_type = b'{"input_tokens":1}', 'application/json'
                    self.reply(payload, content_type)
                    return
                message = {'id': 'claude-transfer', 'type': 'message', 'role': 'assistant', 'model': body.get('model'),
                           'content': [{'type': 'text', 'text': 'Explicit relay fixture done.'}], 'stop_reason': 'end_turn',
                           'stop_sequence': None, 'usage': {'input_tokens': 1, 'output_tokens': 1}}
                if body.get('stream') and body.get('tools') and phase['receive'] and not phase['acked']:
                    phase['acked'] = True
                    message['content'] = [{'type': 'tool_use', 'id': 'tool-receive', 'name': 'mcp__aw__aw_execute',
                        'input': {'command': 'message.receive', 'arguments': {'message_id': 'after-transfer'}}}]
                    message['stop_reason'] = 'tool_use'
                if not body.get('stream'):
                    self.reply(json.dumps(message).encode(), 'application/json')
                    return
                block = message['content'][0]
                start = {**block, 'input': {}} if block['type'] == 'tool_use' else {'type': 'text', 'text': ''}
                delta = ({'type': 'input_json_delta', 'partial_json': json.dumps(block['input'])}
                         if block['type'] == 'tool_use' else {'type': 'text_delta', 'text': block['text']})
                events = [
                    {'type': 'message_start', 'message': {**message, 'content': [], 'stop_reason': None}},
                    {'type': 'content_block_start', 'index': 0, 'content_block': start},
                    {'type': 'content_block_delta', 'index': 0, 'delta': delta},
                    {'type': 'content_block_stop', 'index': 0},
                    {'type': 'message_delta', 'delta': {'stop_reason': message['stop_reason']}, 'usage': {'output_tokens': 1}},
                    {'type': 'message_stop'},
                ]
            payload = ''.join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events).encode()
            self.reply(payload, 'text/event-stream')

        def reply(self, payload, content_type):
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(('127.0.0.1', 0), ModelFixture)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    runners, threads, failures = [], [], []
    app.create('sea', 'native-transfer')
    root = app.root('sea', 'native-transfer')
    (root / 'user-note.md').write_text('User-owned asset survives handoff.', encoding='utf-8')

    def spawn(app, workspace, agent_id, directory):
        runner = runtime.Runner(app, workspace, agent_id, directory)
        runners.append(runner)
        def target():
            try:
                runner.run()
            except Exception as exc:
                failures.append(exc)
        thread = threading.Thread(target=target, daemon=True)
        threads.append(thread)
        thread.start()
        return {'state': 'starting_runner'}

    def wait_until(predicate):
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline and not failures:
            if predicate():
                return
            time.sleep(.05)
        pytest.fail(f'Native transfer failed: {failures}; {read_json(root / ".aw-local/status.json")}')

    monkeypatch.setattr(runtime, 'spawn_runner', spawn)
    try:
        endpoint = f'http://127.0.0.1:{server.server_port}'
        app.configure('sea', 'native-transfer', codex_config('offline-transfer-model', 'low', endpoint + '/v1',
                                                            'AW_TEST_TRANSFER_KEY', codex))
        runtime.start(app, 'sea', 'native-transfer')
        old = app.agent('sea', 'native-transfer')['current']
        wait_until(lambda: read_json(root / f'.aw-local/inputs/boot-{old}.json', {}).get('checkpoint_revision'))
        phase['handoff'] = True
        operation = transfer.request(app, 'sea', 'native-transfer', sdk_config('claude', 'claude-sonnet-4-6', 'low',
                                     endpoint, 'AW_TEST_TRANSFER_KEY', claude), request_id='native-transfer')
        wait_until(lambda: transfer.status(app, 'sea', 'native-transfer')['state'] == 'completed')
        current = app.show('sea', 'native-transfer')['binding']
        assert len(runners) == 2 and phase['codex_step'] == 2
        assert current['id'] == operation['target_binding'] and current['kind'] == 'claude'
        assert app.store('sea').snapshot().json(f'bindings/{old}.json')['phase'] == 'released'
        assert not threads[0].is_alive()
        with pytest.raises(Conflict):
            app.require_binding('sea', 'native-transfer', old)
        assert any('Real native cross-Harness handoff fixture' in json.dumps(body) for body in claude_calls)
        assert (root / 'user-note.md').read_text() == 'User-owned asset survives handoff.'
        # Message.poll must use the successor's live adapter, not create a third session.
        app.create('sea', 'sender')
        sender = app.reserve('sea', 'sender')['binding']
        app.bind('sea', 'sender', sender, 'native-test-sender')
        phase['receive'] = True
        messages = Messages(app)
        messages.send('sea', 'sender', sender, 'native-transfer', 'Explicit post-transfer notification.', request_id='after-transfer')
        runtime.watch(app, 'sea', 'native-transfer', 'start', interval=.5)
        wait_until(lambda: messages.show('sea', 'after-transfer')['ack'])
        assert messages.show('sea', 'after-transfer')['ack'] == {'message_id': 'after-transfer'}
        assert (root / 'messages/after-transfer.json').is_file()
        assert app.show('sea', 'native-transfer')['binding']['session'] == current['session']
        assert len(runners) == 2
    finally:
        for runner in runners:
            runner.stop_event.set()
        for thread in threads:
            thread.join(timeout=15)
        server.shutdown()
        server.server_close()
        server_thread.join(5)
    assert not failures and not any(thread.is_alive() for thread in threads)
