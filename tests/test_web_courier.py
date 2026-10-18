import http.client
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import pytest

from agent_workspace import web_courier
from agent_workspace.messages import Messages
from agent_workspace.server import make_server
from agent_workspace.layout import shared_path
from agent_workspace.util import Conflict, Error, Uncertain, encode

TARGET = 'https://chatgpt.com/c/11111111-1111-4111-8111-111111111111'
EXTENSION = 'a' * 32


@pytest.fixture
def courier(app):
    for agent in ('sender', 'receiver'):
        app.create('sea', agent)
    sender = app.reserve('sea', 'sender')['binding']
    app.bind('sea', 'sender', sender, 'native-sender')
    receiver = app.reserve('sea', 'receiver')['binding']
    app.bind('sea', 'receiver', receiver, TARGET.rsplit('/', 1)[1])
    return app, sender, receiver


def connect(courier, name='connection-one'):
    app, _, receiver = courier
    return web_courier.connect(app, 'sea', 'receiver', receiver, TARGET, EXTENSION, name, port=8765)


def message(courier, mid='message-one'):
    app, sender, _ = courier
    Messages(app).send('sea', 'sender', sender, 'receiver', '第一行\n第二行', request_id=mid)


def request(courier, conn, action, **kwargs):
    return web_courier.handle(courier[0], conn['connection_id'], conn['token'],
                              'chrome-extension://' + EXTENSION, {'action': action, **kwargs})


def test_connect_requires_exact_current_manual_session(courier):
    app, _, receiver = courier
    before = app.store('sea').snapshot()
    with pytest.raises(Conflict):
        web_courier.connect(app, 'sea', 'receiver', receiver, 'https://chatgpt.com/c/another', EXTENSION, 'wrong')
    with pytest.raises(Error):
        web_courier.connect(app, 'sea', 'receiver', 'unknown-binding', TARGET, EXTENSION, 'unknown')
    assert not list((app.home / 'web-courier/connections').glob('*.json'))
    assert not list((app.home / 'web-courier/attempts').glob('*.json'))
    assert app.store('sea').snapshot().revision == before.revision
    conn = connect(courier)
    connection_path = app.home / 'web-courier/connections' / (conn['connection_id'] + '.json')
    original_connection = connection_path.read_bytes()
    assert conn['backend_url'] == 'http://127.0.0.1:8765'
    assert web_courier.status(app, conn['connection_id'])['eligible'] is True
    assert 'token' not in web_courier.status(app, conn['connection_id'])
    assert web_courier.connect(app, 'sea', 'receiver', receiver, TARGET, EXTENSION,
                               conn['connection_id'])['token'] == conn['token']
    with pytest.raises(Conflict):
        web_courier.connect(app, 'sea', 'receiver', receiver, TARGET, 'b' * 32,
                            conn['connection_id'])
    assert connection_path.read_bytes() == original_connection
    assert app.store('sea').snapshot().revision == before.revision


def test_released_binding_cannot_connect_in_place_of_its_successor(courier):
    app, _, receiver = courier
    checkpoint = app.checkpoint('sea', 'receiver', 'release original manual entry', binding=receiver)
    app.stop('sea', 'receiver', receiver, checkpoint['id'])
    app.finish_stop('sea', 'receiver', receiver, observed_idle=True)
    successor = app.reserve('sea', 'receiver')['binding']
    successor_target = 'https://chatgpt.com/c/22222222-2222-4222-8222-222222222222'
    app.bind('sea', 'receiver', successor, successor_target.rsplit('/', 1)[1])
    before = app.store('sea').snapshot()
    assert before.json(shared_path(before, f'bindings/{receiver}.json'))['phase'] == 'released'

    with pytest.raises(Conflict):
        web_courier.connect(app, 'sea', 'receiver', receiver, TARGET, EXTENSION, 'released')

    assert not list((app.home / 'web-courier/connections').glob('*.json'))
    assert not list((app.home / 'web-courier/attempts').glob('*.json'))
    assert app.store('sea').snapshot().revision == before.revision
    assert app.agent('sea', 'receiver')['current'] == successor
    conn = web_courier.connect(app, 'sea', 'receiver', successor, successor_target, EXTENSION, 'successor')
    assert conn['binding'] == successor and web_courier.status(app, conn['connection_id'])['eligible'] is True


def test_original_multiline_notification_claim_page_fact_and_real_ack(courier):
    app, _, binding = courier
    conn = connect(courier)
    message(courier)
    store = app.store('sea')
    snap = store.snapshot()
    path = shared_path(snap, 'messages/message-one.json')
    original = snap.json(path)
    original['future_field'] = {'keep': 'raw', 'nested': [1, 2]}
    store.change('main', {path: encode(original)}, {path: snap.entries[path]}, 'Add valid future field')
    preview = request(courier, conn, 'get')
    assert preview['state'] == 'ready' and '\n' in preview['prompt']
    assert 'future_field' in preview['prompt'] and 'nested' in preview['prompt']
    assert preview['notification']['binding'] == binding
    attempted = request(courier, conn, 'begin', message_id='message-one', attempt_id='attempt-one',
                        binding=binding, target_url=TARGET, prompt_digest=preview['prompt_digest'])
    assert attempted == {'state': 'claimed', 'message_id': 'message-one', 'attempt_id': 'attempt-one'}
    assert request(courier, conn, 'get')['state'] == 'attempt_exists'
    with pytest.raises(Conflict):
        request(courier, conn, 'begin', message_id='message-one', attempt_id='attempt-one',
                binding=binding, target_url=TARGET, prompt_digest=preview['prompt_digest'])
    second = connect(courier, 'connection-two')
    assert request(courier, second, 'get')['state'] == 'waiting_ack'
    adapter = type('Adapter', (), {'status': lambda self: 'idle',
                                   'notify': lambda self, *args: pytest.fail('second notification')})()
    assert Messages(app).poll('sea', 'receiver', binding, adapter=adapter,
                              retry_seconds=0)['state'] == 'waiting_ack'
    reported = request(courier, conn, 'report', message_id='message-one', attempt_id='attempt-one',
                       target_url=TARGET, web_fact='observed')
    assert reported['attempt']['web_fact'] == 'observed' and reported['ack'] is None
    assert app.store('sea').snapshot().json('.agentworkspace/acks/message-one.json') is None
    received = Messages(app).receive('sea', 'receiver', binding, 'message-one')
    assert received['publication']['state'] == 'published'
    final = request(courier, conn, 'status')
    assert final['ack'] == {'message_id': 'message-one'}
    assert final['attempt']['web_fact'] == 'observed'
    assert final['attempt']['claim_state'] == 'confirmed'
    assert 'token' not in final

    message(courier, 'message-two')
    notifications = []
    next_adapter = type('Adapter', (), {'status': lambda self: 'idle',
                                       'notify': lambda self, prompt, delivery: notifications.append((prompt, delivery))})()
    assert Messages(app).poll('sea', 'receiver', binding, adapter=next_adapter)['state'] == 'notified_waiting_ack'
    assert len(notifications) == 1
    # The shared dispatch now names message two; the original confirmed claim remains confirmed.
    assert request(courier, conn, 'status')['attempt']['claim_state'] == 'confirmed'


def test_unknown_claim_is_inspected_without_repeating_original(courier, monkeypatch):
    conn = connect(courier)
    message(courier)
    original = Messages.claim_manual
    calls = []
    def lost(self, *args):
        calls.append(args)
        original(self, *args)
        raise Uncertain('Fixture: reply lost after original Git claim')
    monkeypatch.setattr(Messages, 'claim_manual', lost)
    preview = request(courier, conn, 'get')
    with pytest.raises(Uncertain):
        request(courier, conn, 'begin', message_id='message-one', attempt_id='attempt-one',
                binding=courier[2], target_url=TARGET, prompt_digest=preview['prompt_digest'])
    status = request(courier, conn, 'status')
    assert status['attempt']['claim_state'] == 'confirmed'
    with pytest.raises(Conflict):
        request(courier, conn, 'begin', message_id='message-one', attempt_id='attempt-one',
                binding=courier[2], target_url=TARGET, prompt_digest=preview['prompt_digest'])
    assert len(calls) == 1


def test_changed_original_notification_refuses_claim(courier):
    app, _, binding = courier
    conn = connect(courier)
    message(courier)
    preview = request(courier, conn, 'get')
    store = app.store('sea')
    snap = store.snapshot()
    path = shared_path(snap, 'messages/message-one.json')
    changed = snap.json(path)
    changed['future_field'] = 'unexpected after fetch'
    store.change('main', {path: encode(changed)}, {path: snap.entries[path]}, 'Fixture: original changed')
    with pytest.raises(Conflict):
        request(courier, conn, 'begin', message_id='message-one', attempt_id='attempt-one',
                binding=binding, target_url=TARGET, prompt_digest=preview['prompt_digest'])
    assert web_courier.status(app, conn['connection_id'])['attempt'] is None


@pytest.mark.parametrize('logical', ['messages/message-one.json', 'message-index/message-one.json'])
def test_original_change_between_prompt_check_and_claim_denies_permission(courier, monkeypatch, logical):
    app, _, binding = courier
    conn = connect(courier)
    message(courier)
    preview = request(courier, conn, 'get')
    store_type = type(app.store('sea'))
    original_change = store_type.change
    injected = []

    def race(self, branch, changes, expected, description, **kwargs):
        if description == 'Claim notification attempt' and not injected:
            snap = self.snapshot()
            path = shared_path(snap, logical)
            updated = snap.json(path)
            updated['future_field'] = 'changed between check and claim'
            original_change(self, 'main', {path: encode(updated)},
                            {path: snap.entries[path]}, 'Fixture: original changed just before claim')
            injected.append(path)
        return original_change(self, branch, changes, expected, description, **kwargs)

    monkeypatch.setattr(store_type, 'change', race)
    with pytest.raises(Conflict):
        request(courier, conn, 'begin', message_id='message-one', attempt_id='attempt-one',
                binding=binding, target_url=TARGET, prompt_digest=preview['prompt_digest'])
    assert len(injected) == 1
    actual = web_courier.status(app, conn['connection_id'])
    assert actual['attempt']['claim_state'] == 'outcome_unknown'
    assert actual['ack'] is None
    assert app.store('sea').snapshot().json('.agentworkspace/dispatch/receiver.json') is None
    with pytest.raises(Conflict):
        request(courier, conn, 'begin', message_id='message-one', attempt_id='attempt-one',
                binding=binding, target_url=TARGET, prompt_digest=preview['prompt_digest'])


def test_two_connections_race_for_one_shared_message_claim(courier, monkeypatch):
    first, second = connect(courier, 'race-first'), connect(courier, 'race-second')
    message(courier)
    preview = request(courier, first, 'get')
    entered = threading.Barrier(2)
    original = Messages._dispatch
    def at_claim(self, *args, **kwargs):
        entered.wait(timeout=30)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Messages, '_dispatch', at_claim)
    def begin(conn, name):
        try:
            return request(courier, conn, 'begin', message_id='message-one', attempt_id=name,
                           binding=courier[2], target_url=TARGET,
                           prompt_digest=preview['prompt_digest'])['state']
        except Conflict:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [future.result(timeout=60) for future in (
            executor.submit(begin, first, 'attempt-first'),
            executor.submit(begin, second, 'attempt-second'))]
    assert sorted(outcomes) == ['claimed', 'conflict']
    dispatch = courier[0].store('sea').snapshot().json('.agentworkspace/dispatch/receiver.json')
    assert dispatch['manual_attempt_id'] in ('attempt-first', 'attempt-second')


def test_missing_original_body_never_becomes_index_only_web_send(courier):
    app, _, _ = courier
    conn = connect(courier)
    message(courier)
    store = app.store('sea')
    snap = store.snapshot()
    path = shared_path(snap, 'messages/message-one.json')
    store.change('main', {path: None}, {path: snap.entries[path]}, 'Fixture: body unavailable')
    with pytest.raises(Error, match='complete original Message'):
        request(courier, conn, 'get')


def test_malformed_ack_record_is_not_reported_as_real_ack(courier):
    app, _, binding = courier
    conn = connect(courier)
    message(courier)
    preview = request(courier, conn, 'get')
    request(courier, conn, 'begin', message_id='message-one', attempt_id='attempt-one',
            binding=binding, target_url=TARGET, prompt_digest=preview['prompt_digest'])
    store = app.store('sea')
    store.change('main', {'.agentworkspace/acks/message-one.json': encode({'message_id': 'wrong'})},
                 {'.agentworkspace/acks/message-one.json': None}, 'Fixture: malformed ACK')
    with pytest.raises(Error, match='malformed'):
        web_courier.status(app, conn['connection_id'])


def test_current_entry_released_after_connection_blocks_http_but_preserves_record(courier):
    app, _, binding = courier
    conn = connect(courier)
    message(courier)
    preview = request(courier, conn, 'get')
    request(courier, conn, 'begin', message_id='message-one', attempt_id='attempt-one',
            binding=binding, target_url=TARGET, prompt_digest=preview['prompt_digest'])
    checkpoint = app.checkpoint('sea', 'receiver', 'fixture stop', binding=binding)
    app.stop('sea', 'receiver', binding, checkpoint['id'])
    app.finish_stop('sea', 'receiver', binding, observed_idle=True)
    with pytest.raises(Conflict):
        request(courier, conn, 'status')
    recorded = web_courier.status(app, conn['connection_id'])
    assert recorded['eligible'] is False
    assert recorded['attempt']['claim_state'] == 'confirmed'


def test_unverifiable_entry_is_unknown_not_revoked(courier, monkeypatch):
    app, _, _ = courier
    conn = connect(courier)
    monkeypatch.setattr(app, 'require_binding', lambda *args, **kwargs: (_ for _ in ()).throw(Error('temporary fixture read failure')))
    observed = web_courier.status(app, conn['connection_id'])
    assert observed['eligible'] is None and observed['unknown_reason'] == 'current_entry_unavailable'


def test_revoked_connection_and_wrong_origin_or_token(courier):
    app, _, _ = courier
    conn = connect(courier)
    for origin in ('null', 'https://evil.test', 'chrome-extension://' + 'b' * 32):
        with pytest.raises(Conflict):
            web_courier.authorize(app, conn['connection_id'], conn['token'], origin)
        with pytest.raises(Conflict):
            web_courier.preflight(app, conn['connection_id'], origin)
    with pytest.raises(Conflict):
        web_courier.authorize(app, conn['connection_id'], 'wrong', None)
    with pytest.raises(Conflict):
        web_courier.authorize(app, conn['connection_id'], '非 ASCII', None)
    assert web_courier.authorize(app, conn['connection_id'], conn['token'], None)['id'] == conn['connection_id']
    revoked = web_courier.revoke(app, conn['connection_id'], 'revoke-original')
    assert revoked == web_courier.revoke(app, conn['connection_id'], 'revoke-original')
    with pytest.raises(Conflict):
        web_courier.authorize(app, conn['connection_id'], conn['token'], None)
    with pytest.raises(Conflict):
        connect(courier)
    assert web_courier.status(app, conn['connection_id'])['eligible'] is False
    assert 'token' not in web_courier.status(app, conn['connection_id'])


def test_insert_is_rejected_without_downgrading(courier):
    app, sender, _ = courier
    conn = connect(courier)
    Messages(app).send('sea', 'sender', sender, 'receiver', 'urgent', delivery='insert', request_id='insert-one')
    result = request(courier, conn, 'get')
    assert result['state'] == 'delivery_unsupported' and result['delivery'] == 'insert'
    with pytest.raises(Error, match='does not support insert'):
        request(courier, conn, 'begin', message_id='insert-one', attempt_id='attempt-one',
                binding=courier[2], target_url=TARGET)
    assert app.store('sea').snapshot().json('.agentworkspace/acks/insert-one.json') is None


def test_http_restricted_route_and_origin_preflight(courier):
    app, _, receiver = courier
    server = make_server(app, port=0, token='management-secret')
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    conn = web_courier.connect(app, 'sea', 'receiver', receiver, TARGET, EXTENSION,
                               'http-connection', port=server.server_port)
    message(courier)
    route = '/api/web-courier/' + conn['connection_id']
    origin = 'chrome-extension://' + EXTENSION
    def call(method, path, headers=None, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=15)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        raw = response.read()
        result = response.status, dict(response.getheaders()), json.loads(raw) if raw else None
        connection.close()
        return result
    try:
        options = {'Origin': origin, 'Access-Control-Request-Method': 'POST',
                   'Access-Control-Request-Headers': 'authorization, content-type'}
        code, headers, _ = call('OPTIONS', route, options)
        assert code == 204 and headers['Access-Control-Allow-Origin'] == origin
        assert headers['Access-Control-Allow-Methods'] == 'POST'
        assert call('OPTIONS', route, {**options, 'Origin':'https://evil.test'})[0] == 403
        post = {'Authorization':'Bearer '+conn['token'], 'Content-Type':'application/json', 'Origin':origin}
        code, headers, value = call('POST', route, post, json.dumps({'action':'get'}))
        assert code == 200 and value['result']['state'] == 'ready'
        assert headers['Access-Control-Allow-Origin'] == origin
        original = value['result']
        begin = {'action':'begin', 'message_id':original['message_id'], 'attempt_id':'http-attempt',
                 'binding':receiver, 'target_url':TARGET, 'prompt_digest':original['prompt_digest']}
        code, _, value = call('POST', route, post, json.dumps(begin))
        assert code == 200 and value['result']['state'] == 'claimed'
        assert call('POST', route, post, json.dumps(begin))[0] == 409
        report = {'action':'report', 'message_id':original['message_id'], 'attempt_id':'http-attempt',
                  'target_url':TARGET, 'web_fact':'observed'}
        code, _, value = call('POST', route, post, json.dumps(report))
        assert code == 200 and value['result']['attempt']['web_fact'] == 'observed'
        assert value['result']['ack'] is None
        Messages(app).receive('sea', 'receiver', receiver, original['message_id'])
        code, _, value = call('POST', route, post, json.dumps({'action':'status'}))
        assert code == 200 and value['result']['ack'] == {'message_id':original['message_id']}
        assert call('POST', route, {**post, 'Origin':'https://evil.test'}, '{}')[0] == 403
        assert call('POST', route, {**post, 'Authorization':'Bearer invalid'}, '{}')[0] == 403
        assert call('POST', '/api/execute', post, json.dumps({'command':'workspace.list'}))[0] == 403
        no_origin = {key:value for key,value in post.items() if key != 'Origin'}
        assert call('POST', '/api/execute', no_origin, json.dumps({'command':'workspace.list'}))[0] == 401
        assert call('POST', route, no_origin, json.dumps({'action':'status'}))[0] == 200
        server.stopping.set()
        assert call('POST', route, no_origin, json.dumps({'action':'status'}))[0] == 503
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=10)
