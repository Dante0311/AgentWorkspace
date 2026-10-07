import json
import time
from record import ROOT, aw, save
from observe import observe

start=json.loads(json.loads((ROOT/'reports/evidence/62-watch-receiver-start.json').read_text(encoding='utf-8'))['stdout'])['result'];binding=start['binding']
deadline=time.monotonic()+600
while time.monotonic()<deadline:
    s=observe('repair-beta');boot=next((i for i in s['inputs'] if i['id']=='boot-'+binding),None)
    if boot and boot['state']=='completed' and boot.get('checkpoint_revision'):break
    time.sleep(2)
else:
    save('63-watch-receiver-boot-unresolved',s);raise RuntimeError('Preserve original receiver')
save('63-watch-receiver-boot-completed',s)
aw('64-normal-watch-enable','message.watch',{'agent_id':'repair-beta','operation':'start','interval':3})
aw('65-watch-sender-start','agent.start',{'agent_id':'repair-alpha','open_app':False})
print('Normal Watch enabled; real sender boot started',flush=True)
