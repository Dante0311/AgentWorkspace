import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import urllib.request
import urllib.error
import pytest
from agent_workspace.server import make_server


def cli(app,*args):
    env=dict(os.environ)
    for key in ('AW_AGENT','AW_BINDING','AW_WORKSPACE'):env.pop(key,None)
    return subprocess.run([sys.executable,'-m','agent_workspace','--home',str(app.home),'--workspace','sea',*args],
                           capture_output=True,text=True,env=env,timeout=15)


def test_cli_create_work_show(app):
    result=cli(app,'agent','create','alice')
    assert result.returncode==0, result.stderr
    result=cli(app,'work','create','--owner','alice','--content','job')
    assert result.returncode==0, result.stderr
    work=json.loads(result.stdout)['result']
    result=cli(app,'work','show',work['id'])
    assert json.loads(result.stdout)['result']['content']=='job'
    result=cli(app,'work','create','--owner','alice')
    assert result.returncode==2 and json.loads(result.stderr)['ok'] is False


def test_cli_help_all_domains(app):
    for name in ('workspace','agent','message','work','checkpoint','runtime','bridge','asset'):
        assert cli(app,name,'--help').returncode==0


def test_mcp_no_work_read(app):
    lines=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},
           {'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}},
           {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'aw_execute','arguments':{'command':'workspace.list','arguments':{}}}}]
    result=subprocess.run([sys.executable,'-m','agent_workspace','--home',str(app.home),'mcp'],
        input=''.join(json.dumps(x)+'\n' for x in lines),capture_output=True,text=True,timeout=10)
    output=[json.loads(l) for l in result.stdout.splitlines()]
    assert result.returncode==0 and len(output)==3
    assert output[1]['result']['tools'][0]['name']=='aw_execute'
    assert 'sea' in output[2]['result']['content'][0]['text']


def test_workbench_auth_and_commands(app):
    server=make_server(app,0,'test-token');t=threading.Thread(target=server.serve_forever);t.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        assert b'Agent Workspace' in urllib.request.urlopen(base).read()
        with pytest.raises(urllib.error.HTTPError) as exc:urllib.request.urlopen(base+'/api/state')
        assert exc.value.code==401
        req=urllib.request.Request(base+'/api/execute',data=json.dumps({'command':'agent.create','arguments':{'workspace':'sea','name':'from-ui'}}).encode(),
            headers={'Authorization':'Bearer test-token','Content-Type':'application/json'})
        result=json.load(urllib.request.urlopen(req))
        assert result['ok'] and app.agent('sea','from-ui')['name']=='from-ui'
        req=urllib.request.Request(base+'/api/state',headers={'Authorization':'Bearer test-token','Origin':'https://untrusted.invalid'})
        with pytest.raises(urllib.error.HTTPError):urllib.request.urlopen(req)
    finally:server.shutdown();server.server_close();t.join()
