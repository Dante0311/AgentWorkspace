"""Real native clients and platform lifecycle against isolated loopback model APIs."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading

import pytest


@pytest.mark.parametrize(('source', 'target'), [
    ('codex', 'codex'),  # E2E-004/001 focused normal lifecycle regression.
    ('codex', 'claude'), ('codex', 'codebuddy'),
    ('claude', 'codex'), ('claude', 'codebuddy'),
    ('codebuddy', 'codex'), ('codebuddy', 'claude'),
])
def test_native_transfer_and_message(app, tmp_path, monkeypatch, source, target):
    """Both clients are real; a local model fixture requests checkpoint, stop and ACK."""
    import time
    from agent_workspace import runtime, transfer
    from agent_workspace.harness_config import codex_config, sdk_config
    from agent_workspace.messages import Messages
    from agent_workspace.util import Conflict, read_json

    executables = {kind: os.environ.get('AW_TEST_' + kind.upper()) for kind in (source, target)}
    if not all(path and Path(path).is_file() for path in executables.values()):
        pytest.skip('Explicit native executables are required for this transfer pair.')
    for kind in (source, target):
        if kind != 'codex':
            pytest.importorskip(kind + '_agent_sdk')
    for variable, name in (('CODEX_HOME', 'codex-home'), ('CLAUDE_CONFIG_DIR', 'claude-home'),
                           ('HOME', 'native-home')):
        home = tmp_path / name
        home.mkdir()
        monkeypatch.setenv(variable, str(home))
    monkeypatch.setenv('AW_TEST_TRANSFER_KEY', 'isolated-transfer-key')
    for name in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN',
                 'CLAUDE_CODE_OAUTH_TOKEN', 'CLAUDECODE', 'ANTHROPIC_BASE_URL',
                 'CODEBUDDY_API_KEY', 'CODEBUDDY_AUTH_TOKEN', 'CODEBUDDY_BASE_URL',
                 'CODEBUDDY_INTERNET_ENVIRONMENT'):
        monkeypatch.delenv(name, raising=False)
    phase = {'handoff': False, 'step': 0, 'receive': False, 'acked': False, 'stop': False, 'stop_step': 0}
    stop_tools = []
    calls = {'codex': [], 'claude': [], 'codebuddy': []}
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
            if self.path.endswith('/count_tokens'):
                self.reply(b'{"input_tokens":1}', 'application/json')
                return
            kind = self.path.split('/')[1]
            if kind not in calls:
                self.send_error(404)
                return
            calls[kind].append(body)
            index = len(calls[kind])
            operation = None
            # Only main tool-capable requests drive platform effects, not auxiliary SDK calls.
            if body.get('tools') and (kind != 'claude' or body.get('stream')):
                if kind == target and phase['stop'] and phase['stop_step'] < len(stop_tools):
                    operation = stop_tools[phase['stop_step']]
                    phase['stop_step'] += 1
                elif kind == source and phase['handoff'] and phase['step'] < len(handoff_tools):
                    operation = handoff_tools[phase['step']]
                    phase['step'] += 1
                elif kind == target and phase['receive'] and not phase['acked']:
                    operation = {'command': 'message.receive', 'arguments': {'message_id': 'after-transfer'}}
                    phase['acked'] = True
            if kind == 'codex':
                item = {'id': f'msg-{index}', 'type': 'message', 'role': 'assistant', 'status': 'completed',
                        'content': [{'type': 'output_text', 'text': 'Explicit native fixture done.', 'annotations': []}]}
                if operation:
                    item = {'id': f'fc-{index}', 'type': 'function_call', 'call_id': f'call-{index}',
                            'name': 'aw_execute', 'arguments': json.dumps(operation), 'status': 'completed'}
                events = [
                    {'type': 'response.created', 'response': {'id': f'resp-{index}', 'status': 'in_progress', 'output': []}},
                    {'type': 'response.output_item.done', 'output_index': 0, 'item': item},
                    {'type': 'response.completed', 'response': {'id': f'resp-{index}', 'status': 'completed',
                     'output': [item], 'usage': {'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2}}},
                ]
            elif kind == 'claude':
                message = {'id': 'claude-transfer', 'type': 'message', 'role': 'assistant', 'model': body.get('model'),
                           'content': [{'type': 'text', 'text': 'Explicit relay fixture done.'}], 'stop_reason': 'end_turn',
                           'stop_sequence': None, 'usage': {'input_tokens': 1, 'output_tokens': 1}}
                if operation:
                    message['content'] = [{'type': 'tool_use', 'id': f'tool-{index}', 'name': 'mcp__aw__aw_execute',
                        'input': operation}]
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
            else:
                base = {'id': f'chatcmpl-{index}', 'object': 'chat.completion.chunk',
                        'created': 1, 'model': body.get('model')}
                delta = {'role': 'assistant', 'content': 'Explicit native fixture done.'}
                if operation:
                    delta = {'role': 'assistant', 'tool_calls': [{
                        'index': 0, 'id': f'call-{index}', 'type': 'function', 'function': {
                            'name': 'mcp__aw__aw_execute', 'arguments': json.dumps(operation)}}]}
                chunks = [
                    {**base, 'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]},
                    {**base, 'choices': [{'index': 0, 'delta': {},
                                         'finish_reason': 'tool_calls' if operation else 'stop'}],
                     'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}},
                ]
                payload = (''.join('data: ' + json.dumps(item) + '\n\n' for item in chunks)
                           + 'data: [DONE]\n\n').encode()
                self.reply(payload, 'text/event-stream')
                return
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
        def profile(kind):
            if kind == 'codex':
                return codex_config('offline-transfer-model', 'low', endpoint + '/codex/v1',
                                    'AW_TEST_TRANSFER_KEY', executables[kind])
            model = 'claude-sonnet-4-6' if kind == 'claude' else 'gpt-4o'
            url = endpoint + '/claude' if kind == 'claude' else endpoint + '/codebuddy/v1'
            return sdk_config(kind, model, base_url=url, env_key='AW_TEST_TRANSFER_KEY', executable=executables[kind])

        app.configure('sea', 'native-transfer', profile(source))
        runtime.start(app, 'sea', 'native-transfer')
        old = app.agent('sea', 'native-transfer')['current']
        wait_until(lambda: read_json(root / f'.aw-local/inputs/boot-{old}.json', {}).get('checkpoint_revision'))
        phase['handoff'] = True
        operation = transfer.request(app, 'sea', 'native-transfer', profile(target), request_id='native-transfer')
        wait_until(lambda: read_json(root / '.aw-local/transfer.json')['state'] == 'completed')
        current = app.show('sea', 'native-transfer')['binding']
        assert len(runners) == 2 and phase['step'] == 2
        assert current['id'] == operation['target_binding'] and current['kind'] == target
        assert app.store('sea').snapshot().json(f'bindings/{old}.json')['phase'] == 'released'
        assert not threads[0].is_alive()
        with pytest.raises(Conflict):
            app.require_binding('sea', 'native-transfer', old)
        assert any('Real native cross-Harness handoff fixture' in json.dumps(body) for body in calls[target])
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
        if source == target == 'codex':
            # E2E-004: no status/continue call is used to make completion durable.
            receipt_path = root / '.aw-local/transfer.json'
            finished = read_json(receipt_path)
            first_record = dict(finished)
            for cycle in (1, 2):
                binding = finished['target_binding']
                phase.update(stop=True, stop_step=0)
                stop_tools[:] = [
                    {'command': 'asset.read', 'arguments': {'path': 'user-note.md'}},
                    {'command': 'checkpoint.create', 'arguments': {
                        'checkpoint_id': f'successor-stop-{cycle}', 'summary': 'Explicit successor stop'}},
                    {'command': 'agent.stop', 'arguments': {'checkpoint': f'successor-stop-{cycle}'}},
                ]
                runtime.queue_input(app, 'sea', 'native-transfer', 'Read the old asset and stop normally.',
                                    request_id=f'successor-stop-{cycle}')
                wait_until(lambda: app.agent('sea', 'native-transfer')['current'] is None)
                wait_until(lambda: not threads[-1].is_alive())
                assert read_json(receipt_path) == finished
                assert transfer.status(app, 'sea', 'native-transfer') == finished
                assert transfer.advance(app, 'sea', 'native-transfer') == finished
                stop = read_json(root / f'.aw-local/inputs/successor-stop-{cycle}.json')
                assert stop['state'] == 'completed'
                events = [json.loads(line) for line in (root / 'records' / binding / 'runtime.jsonl').read_text().splitlines()]
                assert any(e.get('method') == 'turn/completed' and e['params']['turn']['id'] == stop['result']['turn']['id']
                           and e['params']['turn']['status'] == 'completed' for e in events)
                assert (root / 'user-note.md').read_text() == 'User-owned asset survives handoff.'
                assert transfer.request(app, 'sea', 'native-transfer', profile(target),
                                        request_id='native-transfer') == first_record
                if cycle == 1:
                    phase['stop'] = False
                    runtime.start(app, 'sea', 'native-transfer')
                    fresh = app.agent('sea', 'native-transfer')['current']
                    wait_until(lambda: read_json(root / f'.aw-local/inputs/boot-{fresh}.json', {}).get('checkpoint_revision'))
                    phase['step'] = 0
                    handoff_tools[0]['arguments']['checkpoint_id'] = 'transfer-cp-next'
                    handoff_tools[1]['arguments']['checkpoint'] = 'transfer-cp-next'
                    second = transfer.request(app, 'sea', 'native-transfer', profile(target), request_id='native-transfer-next')
                    assert second['old_binding'] == fresh
                    assert second['target_binding'] != first_record['target_binding']
                    wait_until(lambda: read_json(receipt_path)['state'] == 'completed')
                    finished = read_json(receipt_path)
            assert len(runners) == 4  # Two explicit starts, two fixed successors, no extras.
            assert all(not thread.is_alive() for thread in threads)
            for r in runners:
                handoff = read_json(root / f'.aw-local/inputs/handoff-{r.binding}.json')
                if handoff:
                    assert handoff['state'] == 'completed'
    finally:
        for runner in runners:
            runner.stop_event.set()
        for thread in threads:
            thread.join(timeout=15)
        server.shutdown()
        server.server_close()
        server_thread.join(5)
    assert not failures and not any(thread.is_alive() for thread in threads)
