import hashlib
import json
import time
from record import ROOT, HOME, WORKSPACE, aw, save, now
from observe import observe

def start_binding(name):
    return json.loads(json.loads((ROOT/'reports/evidence'/name).read_text(encoding='utf-8'))['stdout'])['result']['binding']
bindings={'repair-alpha':start_binding('65-watch-sender-start.json'),'repair-beta':start_binding('62-watch-receiver-start.json')}
journal=[];deadline=time.monotonic()+600
while time.monotonic()<deadline:
    data={a:observe(a) for a in bindings}
    journal.append({'time':now(),'status':{a:s['runtime'] for a,s in data.items()}})
    if all(s['runtime'] and s['runtime']['binding']==bindings[a] and s['runtime']['state']=='released' for a,s in data.items()):break
    time.sleep(3)
else:
    save('71-watch-unresolved',{'snapshots':data,'journal':journal});raise RuntimeError('Preserve outcomes; no message replay')
if not (ROOT/'reports/evidence/71-watch-final-observation.json').exists():
    save('71-watch-final-observation',{'snapshots':data,'journal':journal})
marker=json.loads((ROOT/'reports/evidence/17-test-identity.json').read_text(encoding='utf-8'))['marker']
order=HOME/'instances'/WORKSPACE/'repair-beta/notes/watch-order.md';text=order.read_text(encoding='utf-8')
assert 'repair-watch-001' in text and 'repair-watch-002' in text and text.index('repair-watch-001')<text.index('repair-watch-002') and marker in text
for a,s in data.items():
    saved=ROOT/'reports/evidence'/('72-final-'+a+'.json')
    show=json.loads(json.loads(saved.read_text(encoding='utf-8'))['stdout'])['result'] if saved.exists() else aw('72-final-'+a,'agent.show',{'agent_id':a})['result']
    assert show['current'] is None and show['runtime']['runner_alive'] is False
    assert all(i['state']=='completed' for i in s['inputs'] if i['id']!='repair-watch-clarify-first-end-001')
    assert all(r['params']['turn']['status']=='completed' for r in s['native_turns'] if r['method']=='turn/completed')
steer=next(i for i in data['repair-beta']['inputs'] if i['id']=='repair-watch-clarify-first-end-001')
assert steer['state']=='submitted'
steer_turn=steer['result']['turnId']
terminal=next(r for r in data['repair-beta']['native_turns'] if r['method']=='turn/completed' and r['params']['turn']['id']==steer_turn)
save('87-steer-terminal-ledger-mismatch',{'input':steer,'native_terminal':terminal,'show_state':'released','source':'runtime._complete_inputs derives item.result.turn.id, actual Codex turn/steer result has turnId','normal_inputs_completed':True,'classification':'E2E-001 residual insert-result shape; Lead owns defect registration','ledger_changed_or_replayed':False})
ops=[]
for identifier in ['repair-watch-001','repair-watch-002','ack-repair-watch-001','ack-repair-watch-002']:
    p=HOME/'operations'/(identifier+'.json');o=json.loads(p.read_text(encoding='utf-8'));ops.append(o);assert o['state']=='published'
events={}
for a,b in bindings.items():
    p=HOME/'instances'/WORKSPACE/a/'records'/b/'runtime.jsonl';rows=[json.loads(line) for line in p.read_text(encoding='utf-8').splitlines()]
    events[a]=[r for r in rows if r.get('method') in ('turn/started','turn/completed') or (r.get('method')=='item/completed' and r.get('params',{}).get('item',{}).get('type') in ('dynamicToolCall','userMessage','commandExecution','agentMessage','sleep'))]
    assert not any(r.get('params',{}).get('item',{}).get('type')=='commandExecution' for r in rows)
aw('73-receiver-final-order-readback','asset.read',{'agent_id':'repair-beta','path':'notes/watch-order.md'})
points={}
for a,b in bindings.items():
    stops=[r['params']['item'] for r in events[a] if r.get('method')=='item/completed' and r.get('params',{}).get('item',{}).get('arguments',{}).get('command')=='agent.stop' and r['params']['item'].get('success')]
    cp=stops[-1]['arguments']['arguments']['checkpoint'];points[a]=aw('74-checkpoint-'+a,'checkpoint.show',{'agent_id':a,'checkpoint':cp})['result']
save('75-watch-final-proof',{'finished_at':now(),'bindings':bindings,'events':events,'operations':ops,'snapshots':data,'checkpoints':points,'order_sha256':hashlib.sha256(order.read_bytes()).hexdigest(),'normal_notification_inputs_not_queued':'Watch calls native adapter.notify; receiver boot and one corrective steer are in input ledger, two notifications have no queue_input IDs','manual_business_input_sent':False,'control_steer_used':True,'unassisted_normal_receiver_flow_pass':False,'strict_aw_execute_only':False,'native_sleep_call_count':sum(r.get('params',{}).get('item',{}).get('type')=='sleep' for rows in events.values() for r in rows),'first_message_before_second_record':True,'new_codex_rounds':4,'business_platform_tools_only':True,'external_messages':0,'prior_busy_observation':'70-watch-current.json','intervention_record':'84-watch-control-intervention-boundary.json'})
print('Watch: two real sends/receives/ACKs, same-session order and both self-stop completed',flush=True)
