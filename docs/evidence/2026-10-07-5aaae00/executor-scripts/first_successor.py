import hashlib
import json
import time
from record import ROOT, HOME, WORKSPACE, aw, save, now
from observe import observe

root=HOME/'instances'/WORKSPACE/'repair-alpha'
path=root/'.aw-local/transfer.json'
deadline=time.monotonic()+600
while time.monotonic()<deadline:
    raw=path.read_bytes();record=json.loads(raw)
    if record['state']=='completed':break
    time.sleep(2)
else:
    save('26-first-transfer-no-completion',observe('repair-alpha'))
    raise RuntimeError('Original transfer incomplete; preserve, no replay')
save('26-first-disk-completed-before-query',{'observed_at':now(),'record':record,'sha256':hashlib.sha256(raw).hexdigest(),'transfer_status_calls_before_capture':0,'observer_only':True})
s=observe('repair-alpha');save('27-first-successor-boot-completed',s)
boot=next(i for i in s['inputs'] if i['id']=='boot-'+record['target_binding'])
assert boot['state']=='completed' and boot.get('checkpoint_revision')
result=aw('28-first-transfer-status-after-disk','agent.transfer-status',{'agent_id':'repair-alpha'})['result']
assert result['state']=='completed' and result['session']==record['session']
assert path.read_bytes()==raw, 'Read-only status must not mutate completed file'
text='本轮明确收尾：只用 aw_execute，asset.read 读取 notes/source.md，把完整原文写入 notes/verify-first.md，禁止访问.aw-local。用 checkpoint.create 保存 checkpoint_id=repair-first-successor-stop，summary写明真实读取与保存结果。再用 agent.stop 引用这个真实checkpoint，结束响应，不发送消息、不启动后继。'
aw('29-first-successor-stop-input','agent.input',{'agent_id':'repair-alpha','text':text,'delivery':'normal','request_id':'repair-first-successor-stop-001'})
print('Disk completed captured BEFORE first status; successor normal stop input submitted',flush=True)
