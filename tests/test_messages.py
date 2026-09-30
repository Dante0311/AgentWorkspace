import json
import pytest
from agent_workspace.messages import Messages
from agent_workspace.util import Conflict, Error

class Adapter:
    def __init__(self, state='idle'):
        self.state, self.calls = state, []
    def status(self): return self.state
    def notify(self, prompt, delivery): self.calls.append((prompt, delivery)); return {}


def test_send_show_receive_dedup(pair):
    app, ids = pair; messages = Messages(app)
    result = messages.send('sea','alice',ids['alice'],'bob','hello',request_id='m1')
    assert result['state'] == 'published' and messages.show('sea','m1')['ack'] is None
    assert messages.send('sea','alice',ids['alice'],'bob','hello',request_id='m1')['payload'] == result['payload']
    with pytest.raises(Conflict):
        messages.send('sea','alice',ids['alice'],'bob','changed',request_id='m1')
    received = messages.receive('sea','bob',ids['bob'],'m1')
    assert received['message']['content'] == 'hello'
    assert messages.show('sea','m1')['ack'] == {'message_id':'m1'}
    assert messages.receive('sea','bob',ids['bob'],'m1')['already_acknowledged']
    saved = app.root('sea','bob').joinpath('messages/m1.json').read_text()
    assert str(app.home) not in saved and 'publication' not in json.loads(saved)


def test_read_failure_still_ack(pair):
    app, ids = pair; messages = Messages(app)
    messages.send('sea','alice',ids['alice'],'bob','hello',request_id='m2')
    app.store('sea').change('main', {'messages/m2.json':b'invalid json'}, {}, 'fault injection')
    assert 'read_error' in messages.receive('sea','bob',ids['bob'],'m2')
    assert app.store('sea').snapshot().json('acks/m2.json') == {'message_id':'m2'}


def test_poll_fifo_and_ack_gate(pair):
    app, ids = pair; messages = Messages(app); adapter = Adapter('busy')
    messages.send('sea','alice',ids['alice'],'bob','normal',request_id='m3')
    messages.send('sea','alice',ids['alice'],'bob','insert',delivery='insert',request_id='m4')
    assert messages.poll('sea','bob',ids['bob'],adapter=adapter)['state'] == 'waiting_idle'
    assert not adapter.calls
    adapter.state='idle'
    assert messages.poll('sea','bob',ids['bob'],adapter=adapter)['state'] == 'notified_waiting_ack'
    assert messages.poll('sea','bob',ids['bob'],adapter=adapter)['state'] == 'waiting_ack'
    assert len(adapter.calls)==1
    messages.receive('sea','bob',ids['bob'],'m3'); adapter.state='busy'
    assert messages.poll('sea','bob',ids['bob'],adapter=adapter)['message_id']=='m4'
    assert adapter.calls[-1][1]=='insert'


def test_poll_retry_budget(pair):
    app, ids = pair; messages=Messages(app); adapter=Adapter()
    messages.send('sea','alice',ids['alice'],'bob','one',request_id='m5')
    for _ in range(2): messages.poll('sea','bob',ids['bob'],adapter=adapter,retry_seconds=0,max_attempts=2)
    assert messages.poll('sea','bob',ids['bob'],adapter=adapter,retry_seconds=0,max_attempts=2)['state']=='notification_retry_exhausted'
    assert len(messages.list('sea'))==1 and len(adapter.calls)==2


def test_old_entry_cannot_ack(pair):
    app, ids=pair; messages=Messages(app)
    messages.send('sea','alice',ids['alice'],'bob','one',request_id='m6')
    cp=app.checkpoint('sea','bob','handoff',binding=ids['bob'])
    app.stop('sea','bob',ids['bob'],cp['id']); app.finish_stop('sea','bob',ids['bob'],observed_idle=True)
    with pytest.raises(Conflict): messages.receive('sea','bob',ids['bob'],'m6')
    assert app.store('sea').snapshot().bytes('acks/m6.json') is None


def setup_friend(app,tmp_path):
    app.workspace_init('sbp',str(tmp_path/'sbp.git')); app.create('sbp','helper')
    app.relation('sea','friends','add','sbp',app.store('sbp').address)
    app.relation('sbp','friends','add','sea',app.store('sea').address)


def test_cross_workspace_dual_write(pair,tmp_path):
    app,ids=pair; setup_friend(app,tmp_path)
    binding=app.reserve('sbp','helper')['binding']; app.bind('sbp','helper',binding,'external-session')
    messages=Messages(app); messages.send('sea','alice',ids['alice'],'sbp/helper','question',request_id='cross')
    a,b=app.store('sea').snapshot(),app.store('sbp').snapshot()
    assert a.bytes('messages/cross.json')==b.bytes('messages/cross.json')
    assert app.store('sbp').address not in a.bytes('workspace.json').decode()
    messages.receive('sbp','helper',binding,'cross')
    assert app.store('sea').snapshot().bytes('acks/cross.json')==app.store('sbp').snapshot().bytes('acks/cross.json')


def test_partial_write_original_bytes(pair,tmp_path,monkeypatch):
    import agent_workspace.messages as module
    app,ids=pair; setup_friend(app,tmp_path); original=module.open_store
    def unavailable(address,home):
        if address==app.store('sbp').address: raise Error('temporarily offline')
        return original(address,home)
    monkeypatch.setattr(module,'open_store',unavailable)
    result=Messages(app).send('sea','alice',ids['alice'],'sbp/helper','one',request_id='partial')
    assert result['state']!='published'
    published=app.store('sea').snapshot().bytes('messages/partial.json')
    monkeypatch.setattr(module,'open_store',original)
    assert Messages(app).reconcile('partial')['state']=='published'
    assert published==app.store('sbp').snapshot().bytes('messages/partial.json')


def test_archived_no_new_message(pair):
    app,ids=pair; app.create('sea','closed'); app.archive('sea','closed')
    with pytest.raises(Error): Messages(app).send('sea','alice',ids['alice'],'closed','new')


def test_long_message_id_has_stable_ack_receipt(pair):
    app,ids=pair;messages=Messages(app);mid='m'*64
    messages.send('sea','alice',ids['alice'],'bob','hello',request_id=mid)
    assert messages.receive('sea','bob',ids['bob'],mid)['publication']['state']=='published'
