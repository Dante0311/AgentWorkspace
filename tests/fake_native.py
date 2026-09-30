"""An isolated protocol peer, NOT a Codex implementation or a live model test."""
import json
import sys

mode = sys.argv[1]
session = 'fake-native-session'
turn = 0

def out(value):
    print(json.dumps(value), flush=True)

for line in sys.stdin:
    request = json.loads(line)
    if 'id' not in request:
        continue
    method, params = request.get('method'), request.get('params', {})
    result = {}
    event = None
    if mode == 'desktop':
        assert request.get('jsonrpc') == '2.0'
        if method == 'tools/list':
            result = {'tools':[{'name':'read_thread'},{'name':'send_message_to_thread'}]}
        elif method == 'tools/call':
            assert params['_meta']['openai/threadId'] == 'caller'
            if params['name'] == 'read_thread':
                value = {'thread':{'id':params['arguments']['threadId'],'status':{'type':'idle'}}, 'turns':[]}
            else:
                value = {'threadId':params['arguments']['threadId'],'sent':True}
            result = {'content':[{'type':'text','text':json.dumps(value)}]}
    elif mode == 'codex':
        if method == 'thread/start':
            assert params['cwd'] and params['dynamicTools'][0]['name'] == 'aw_execute'
            result = {'thread':{'id':session}}
        elif method == 'thread/read':
            result = {'thread':{'id':session,'status':{'type':'idle'},'turns':[]}}
        elif method == 'turn/start':
            turn += 1
            result = {'turn':{'id':f't{turn}','status':'inProgress'}}
            event = {'method':'turn/completed','params':{'threadId':session,'turn':{'id':f't{turn}','status':'completed'}}}
    out({'jsonrpc':'2.0','id':request['id'],'result':result})
    if event:
        out(event)
