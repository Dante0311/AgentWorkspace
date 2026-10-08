import hashlib
import json
import time
from record import ROOT, HOME, WORKSPACE, aw, save
from observe import observe

root=HOME/'instances'/WORKSPACE/'repair-alpha'
deadline=time.monotonic()+600
while time.monotonic()<deadline:
    s=observe('repair-alpha')
    item=next((i for i in s['inputs'] if i['id']=='repair-second-successor-stop-001'),None)
    if item and s['runtime'] and s['runtime']['state']=='released':break
    time.sleep(2)
else:
    save('44-second-stop-unresolved',s);raise RuntimeError('Preserve unresolved stop')
save('44-second-stop-final-observed',s)
assert item['state']=='completed'
turn=item['result']['turn']['id']
assert any(r['method']=='turn/completed' and r['params']['turn']['id']==turn and r['params']['turn']['status']=='completed' for r in s['native_turns'])
assert (root/'notes/source.md').read_bytes()==(root/'notes/verify-second.md').read_bytes()
record=s['transfer'];assert record['state']=='completed' and record['session']
show=aw('45-second-final-show','agent.show',{'agent_id':'repair-alpha'})['result']
assert show['current'] is None and show['runtime']['runner_alive'] is False
tools=[]
for line in (root/'records'/record['target_binding']/'runtime.jsonl').read_text(encoding='utf-8').splitlines():
    row=json.loads(line);tool=row.get('params',{}).get('item',{})
    if row.get('method')=='item/completed' and tool.get('type')=='dynamicToolCall' and tool.get('success') and tool.get('arguments',{}).get('command')=='agent.stop':tools.append(tool)
cp=tools[-1]['arguments']['arguments']['checkpoint']
aw('45-second-model-checkpoint','checkpoint.show',{'agent_id':'repair-alpha','checkpoint':cp})
aw('46-second-transfer-after-stop','agent.transfer-status',{'agent_id':'repair-alpha'})
old=aw('47-first-archived-id-readback','agent.transfer-profile',{'agent_id':'repair-alpha','kind':'codex','model':'gpt-6-luna','effort':'low','executable':record['target_config']['command'][0],'request_id':'repair-transfer-001'})['result']
assert old['state']=='completed' and old['id']=='repair-transfer-001' and old['session']
after=observe('repair-alpha');assert after['inputs']==s['inputs'] and after['native_turns']==s['native_turns'] and after['transfer']==s['transfer']
save('48-second-chain-proof',{'stop_input':item,'native_turn':turn,'checkpoint':cp,'requested_checkpoint_id':'repair-second-successor-stop','requested_checkpoint_id_honored':cp=='repair-second-successor-stop','record':record,'first_archived_record':old,'old_request_no_extra_execution':True,'new_transfer_not_blocked':True,'show':show,'result_sha256':hashlib.sha256((root/'notes/verify-second.md').read_bytes()).hexdigest()})
agents=aw('49-current-task-read','asset.read',{'agent_id':'repair-alpha','path':'AGENTS.md'})['result']
task='''这是本批次最后一个独立的boot自行停工分支验收，用户已授权；旧职责/旧检查点只作为历史，不再等待新输入。只用 aw_execute，禁止Shell、联网、消息和后继。
在本次boot中，asset.read读取notes/source.md，将完整原文通过asset.write写到notes/verify-boot-stop.md。
checkpoint.create 的 arguments 必须明确含 checkpoint_id=repair-explicit-boot-stop，以及当前workspace、agent_id、binding、真实summary。保存后使用返回的实际id调用agent.stop，结束当前turn。不要再创建其他checkpoint，不读取.aw-local，不自行继续。
'''
aw('50-boot-stop-task-save','asset.write',{'agent_id':'repair-alpha','path':'AGENTS.md','revision':agents['revision'],'content':task})
aw('51-explicit-boot-stop-start','agent.start',{'agent_id':'repair-alpha','open_app':False})
print('Both transfers verified; last short explicit boot-stop branch started',flush=True)
