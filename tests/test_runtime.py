import json
from pathlib import Path
import sys
import threading
import time
import pytest
from agent_workspace import bridges, runtime
from agent_workspace.commands import execute
from agent_workspace.util import Conflict, Error, locked, read_json, write_json

NATIVE=Path(__file__).with_name('fake_native.py')
BRIDGE=Path(__file__).with_name('fake_bridge.py')


def test_desktop_uses_owner_mcp_only(app):
    app.create('sea','alice'); root=app.root('sea','alice')
    config={'kind':'desktop','command':[sys.executable,str(NATIVE),'desktop'],'pipe_path':'fixture','caller_thread':'caller'}
    desktop=runtime.Desktop(root,config,'existing-desktop-thread')
    try:
        assert desktop.status()=='idle'
        assert desktop.notify('a notification','normal')['threadId']=='existing-desktop-thread'
    finally:
        desktop.close()


def test_desktop_missing_config_is_not_cli_fallback(app):
    app.create('sea','alice')
    with pytest.raises(Error): runtime.Desktop(app.root('sea','alice'),{},'thread')
    app.configure('sea','alice',{'kind':'desktop'})
    result=runtime.start(app,'sea','alice')
    assert result['state']=='awaiting_new_session_bind'
    assert result['open_url'].startswith('codex://new?')
    assert app.show('sea','alice')['binding']['session'] is None
    assert 'fake' not in result['prompt']


def test_codex_protocol_records_actual_fixture_events(app):
    app.create('sea','alice'); root=app.root('sea','alice')
    app.configure('sea','alice',{'kind':'codex','command':[sys.executable,str(NATIVE),'codex']})
    b=app.reserve('sea','alice')['binding']
    adapter=runtime.Codex(app,'sea','alice',b,root,{'command':[sys.executable,str(NATIVE),'codex']})
    try:
        app.bind('sea','alice',b,adapter.session)
        assert adapter.notify('explicit test input','normal')['turn']['id']=='t1'
        assert adapter.completed.get(timeout=3)['status']=='completed'
        assert 'turn/completed' in root.joinpath('records',b,'runtime.jsonl').read_text()
        assert not app.work_list('sea')
    finally:
        adapter.close()


def test_runner_bootstrap_and_initial_checkpoint(app):
    app.create('sea','alice'); root=app.root('sea','alice')
    app.configure('sea','alice',{'kind':'codex','command':[sys.executable,str(NATIVE),'codex']})
    b=app.reserve('sea','alice')['binding']
    runner=runtime.Runner(app,'sea','alice')
    errors=[]
    def target():
        try: runner.run()
        except Exception as exc: errors.append(exc)
    t=threading.Thread(target=target);t.start()
    deadline=time.monotonic()+8
    try:
        while time.monotonic()<deadline:
            if app.checkpoints('sea','alice'): break
            time.sleep(.1)
        assert app.checkpoints('sea','alice')
        assert app.agent('sea','alice')['current']==b
        assert not app.work_list('sea')
    finally:
        runner.stop_event.set();t.join(timeout=5)
    assert not errors and not t.is_alive()


def test_watch_stop_does_not_release_entry(pair):
    app,ids=pair
    runtime.watch(app,'sea','alice','start',interval=1)
    assert runtime.watch(app,'sea','alice','status')['enabled']
    runtime.watch(app,'sea','alice','stop')
    assert app.agent('sea','alice')['current']==ids['alice']
    cp=app.checkpoint('sea','alice','handoff',binding=ids['alice'])
    app.stop('sea','alice',ids['alice'],cp['id'])
    with pytest.raises(Conflict): runtime.watch(app,'sea','alice','start')


def test_platform_stop_requires_observed_idle_for_desktop(app):
    app.create('sea','alice');app.configure('sea','alice',{'kind':'desktop'})
    b=app.reserve('sea','alice')['binding'];app.bind('sea','alice',b,'test-thread')
    cp=app.checkpoint('sea','alice','stop',binding=b)
    with pytest.raises(Error):
        execute(app,'agent.stop',{'workspace':'sea','agent_id':'alice','binding':b,'checkpoint':cp['id'],'confirm_stopped':True})
    assert app.agent('sea','alice')['current']==b


def test_os_lock_prevents_another_process(tmp_path):
    import subprocess
    path=tmp_path/'lock'
    code='from agent_workspace.util import locked; from pathlib import Path; import sys;\nwith locked(Path(sys.argv[1]),wait=0): print("unexpected")'
    with locked(path):
        result=subprocess.run([sys.executable,'-c',code,str(path)],capture_output=True,text=True)
    assert result.returncode!=0 and 'unexpected' not in result.stdout
    assert 'Resource is in use' in result.stderr


def test_bridge_explicit_send_and_disable(pair):
    app,ids=pair;root=app.root('sea','alice')
    bridges.configure(app,'sea','alice','chat',{'command':[sys.executable,str(BRIDGE)],'enabled':True})
    manager=bridges.BridgeManager(app,'sea','alice',ids['alice'],root)
    try:
        manager.tick()
        receipt=bridges.send(app,'sea','alice',ids['alice'],'chat','room','explicit reply',request_id='send-one')
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            manager.tick();time.sleep(.02)
            record=read_json(root/'.aw-local/bridge-sends/send-one.json')
            if record['state']=='sent':break
        assert record['state']=='sent'
        assert not list((root/'.aw-local/inputs').glob('*.json'))
        bridges.configure(app,'sea','alice','chat',{'command':[sys.executable,str(BRIDGE)],'enabled':False})
        manager.tick();assert not manager.processes
    finally: manager.stop_all()


def test_bridge_crash_backoff_and_handoff_no_restart(pair):
    app,ids=pair;root=app.root('sea','alice')
    bridges.configure(app,'sea','alice','bad',{'command':[sys.executable,str(BRIDGE),'crash'],'enabled':True,'max_restarts':1})
    manager=bridges.BridgeManager(app,'sea','alice',ids['alice'],root)
    try:
        manager.tick();manager.processes['bad'].wait(timeout=3);manager.tick()
        assert read_json(root/'.aw-local/bridges/status/bad.json')['restarts']==1
        manager.tick();assert not manager.processes
        cp=app.checkpoint('sea','alice','handoff',binding=ids['alice'])
        app.stop('sea','alice',ids['alice'],cp['id'])
        with pytest.raises(Conflict): manager.tick()
        assert not manager.processes
    finally:manager.stop_all()


def test_handoff_request_disables_automatic_restarts_immediately(pair):
    app,ids=pair;root=app.root('sea','alice')
    runtime.watch(app,'sea','alice','start')
    runtime.handoff_request(app,'sea','alice')
    assert read_json(root/'.aw-local/control.json')['handoff']==ids['alice']
    assert not read_json(root/'.aw-local/watch.json')['enabled']
    assert app.agent('sea','alice')['current']==ids['alice']


def test_shared_controller_prevents_duplicate_runner(app,tmp_path):
    from agent_workspace.app import App
    app.create('sea','alice');root=app.root('sea','alice')
    config={'kind':'codex','command':[sys.executable,str(NATIVE),'codex']}
    app.configure('sea','alice',config)
    binding=app.reserve('sea','alice')['binding']
    runner=runtime.Runner(app,'sea','alice');errors=[]
    def run():
        try:runner.run()
        except Exception as exc:errors.append(exc)
    thread=threading.Thread(target=run);thread.start()
    try:
        for _ in range(50):
            entry=app.store('sea').snapshot().json(f'bindings/{binding}.json')
            if entry.get('controller'):break
            time.sleep(.05)
        other=App(tmp_path/'other');other.workspace_connect('sea',app.store('sea').address)
        other.connect_agent('sea','alice',str(tmp_path/'copy'))
        other.configure('sea','alice',config)
        write_json(other.root('sea','alice')/'.aw-local/entry.json',{'binding':binding,'config':config})
        with pytest.raises(Conflict,match='runner'):
            runtime.Runner(other,'sea','alice').run()
    finally:runner.stop_event.set();thread.join(timeout=6)
    assert not errors


def test_repeated_manual_start_reuses_pending_binding(app):
    app.create('sea','alice')
    first=runtime.start(app,'sea','alice')
    second=runtime.start(app,'sea','alice')
    assert first['binding']==second['binding']
    app.bind('sea','alice',first['binding'],'actual')
    with pytest.raises(Conflict):runtime.start(app,'sea','alice')
