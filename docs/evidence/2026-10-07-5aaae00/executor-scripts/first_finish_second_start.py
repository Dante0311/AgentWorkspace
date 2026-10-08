import hashlib
import json
from pathlib import Path
import time
from record import ROOT, HOME, WORKSPACE, aw, save
from observe import observe

root=HOME/'instances'/WORKSPACE/'repair-alpha'
deadline=time.monotonic()+600
while time.monotonic()<deadline:
    s=observe('repair-alpha')
    if s['runtime'] and s['runtime']['state']=='released':break
    time.sleep(2)
else:
    save('31-first-stop-unresolved',s);raise RuntimeError('Preserve unresolved stop; no new entry')
if not (ROOT/'reports/evidence/31-first-stop-final-observed.json').exists():
    save('31-first-stop-final-observed',s)
item=next(i for i in s['inputs'] if i['id']=='repair-first-successor-stop-001')
turn=item['result']['turn']['id']
assert item['state']=='completed'
assert any(r['method']=='turn/completed' and r['params']['turn']['id']==turn and r['params']['turn']['status']=='completed' for r in s['native_turns'])
assert (root/'notes/source.md').read_bytes()==(root/'notes/verify-first.md').read_bytes()
saved=ROOT/'reports/evidence/32-first-final-show.json'
show=json.loads(json.loads(saved.read_text(encoding='utf-8'))['stdout'])['result'] if saved.exists() else aw('32-first-final-show','agent.show',{'agent_id':'repair-alpha'})['result']
assert show['current'] is None and show['runtime']['runner_alive'] is False
stops=[]
for line in (root/'records'/show['runtime']['binding']/'runtime.jsonl').read_text(encoding='utf-8').splitlines():
    row=json.loads(line);tool=row.get('params',{}).get('item',{})
    if row.get('method')=='item/completed' and tool.get('type')=='dynamicToolCall' and tool.get('success') and tool.get('arguments',{}).get('command')=='agent.stop':
        stops.append(tool)
actual_checkpoint=stops[-1]['arguments']['arguments']['checkpoint']
aw('32-first-actual-explicit-checkpoint','checkpoint.show',{'agent_id':'repair-alpha','checkpoint':actual_checkpoint})
save('32-checkpoint-id-instruction-deviation',{'requested_checkpoint_id':'repair-first-successor-stop','actual_checkpoint_id':actual_checkpoint,'model_omitted_checkpoint_id':True,'stop_used_actual_saved_checkpoint':True,'management_named_readback_failed':'Unknown saved checkpoint; original error retained','repair_goal_terminal_events_and_checkpoint_verified':True,'no_model_replay':True})
record=s['transfer'];assert record['state']=='completed' and record['session']
result=aw('33-first-completed-status-after-stop','agent.transfer-status',{'agent_id':'repair-alpha'})['result']
assert result['state']=='completed' and result['session']==record['session']
before=observe('repair-alpha')
exe=str(Path.home()/'AppData/Local/OpenAI/Codex/bin/5ea220ae823df3d7/codex.exe')
repeat=aw('34-first-identical-transfer-readback','agent.transfer-profile',{'agent_id':'repair-alpha','kind':'codex','model':'gpt-6-luna','effort':'low','executable':exe,'request_id':'repair-transfer-001'})['result']
after=observe('repair-alpha')
assert repeat==record
assert before['inputs']==after['inputs'] and before['native_turns']==after['native_turns'] and before['transfer']==after['transfer']
save('35-first-chain-proof',{'binding':show['runtime']['binding'],'session':record['session'],'checkpoint':actual_checkpoint,'stop_input':item,'native_terminal_event':next(r for r in s['native_turns'] if r['method']=='turn/completed' and r['params']['turn']['id']==turn),'asset_sha256':hashlib.sha256((root/'notes/verify-first.md').read_bytes()).hexdigest(),'disk_completed_before_query':True,'completed_persists_after_stop':True,'same_request_no_new_input_or_native_turn':True,'show':show})
new=aw('36-second-original-start','agent.start',{'agent_id':'repair-alpha','open_app':False})['result']
save('36-second-entry',new)
print('First chain verified; legitimate new entry started, no old transaction obstruction',flush=True)
