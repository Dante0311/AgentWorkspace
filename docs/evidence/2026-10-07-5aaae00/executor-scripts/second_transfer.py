import hashlib
import json
from pathlib import Path
import time
from record import ROOT, aw, save, now
from observe import observe

new=json.loads((ROOT/'reports/evidence/36-second-entry.json').read_text(encoding='utf-8'))
binding=new['binding']
deadline=time.monotonic()+600
while time.monotonic()<deadline:
    s=observe('repair-alpha');boot=next((i for i in s['inputs'] if i['id']=='boot-'+binding),None)
    if boot and boot['state']=='completed' and boot.get('checkpoint_revision'):break
    time.sleep(2)
else:
    save('37-second-original-unresolved',s);raise RuntimeError('Preserve original outcome')
save('37-second-original-boot-completed',s)
exe=str(Path.home()/'AppData/Local/OpenAI/Codex/bin/5ea220ae823df3d7/codex.exe')
aw('38-second-transfer-request','agent.transfer-profile',{'agent_id':'repair-alpha','kind':'codex','model':'gpt-6-luna','effort':'low','executable':exe,'request_id':'repair-transfer-002'})
deadline=time.monotonic()+600
while time.monotonic()<deadline:
    s=observe('repair-alpha');record=s['transfer']
    if record['id']=='repair-transfer-002' and record['state']=='completed':break
    time.sleep(2)
else:
    save('39-second-transfer-unresolved',s);raise RuntimeError('Preserve original second transfer')
save('39-second-disk-completed-before-query',{'observed_at':now(),'record':record,'second_transfer_status_calls_before_capture':0})
save('40-second-successor-boot-completed',s)
aw('41-second-transfer-status','agent.transfer-status',{'agent_id':'repair-alpha'})
text='本次第二后继明确收尾，只用 aw_execute：asset.read notes/source.md，将完整原文写入 notes/verify-second.md。调用 checkpoint.create 时请在arguments对象明确带 "checkpoint_id":"repair-second-successor-stop"，同时带当前binding及真实summary；勿省略checkpoint_id。用返回的实际id调用 agent.stop，结束响应。禁止访问.aw-local或启动新会话。'
aw('42-second-successor-stop-input','agent.input',{'agent_id':'repair-alpha','text':text,'delivery':'normal','request_id':'repair-second-successor-stop-001'})
print('Second unique transfer persisted completed; successor stop input sent',flush=True)
