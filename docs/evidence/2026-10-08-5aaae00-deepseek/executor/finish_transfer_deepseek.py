import json,time
import observe as observer
from transfer_record import ROOT,HOME,aw,save,now
observer.WORKSPACE='transfer-local'
deadline=time.monotonic()+300
while time.monotonic()<deadline:
    observations=[observer.observe(a) for a in ('transfer-agent','transfer-peer')]
    if all(o.get('runtime') and o['runtime'].get('state')=='released' for o in observations):
        save('T31-final-native-observation',{'time':now(),'agents':observations});break
    time.sleep(3)
else:
    save('T31-final-observation-timeout',{'time':now(),'agents':observations})
    raise SystemExit('bounded Message/stop observation; no corrective query/replay')
for aid in ('transfer-agent','transfer-peer'):
    aw('T32-'+aid+'-show','agent.show',{'agent_id':aid})
aw('T33-transfer-final','agent.transfer-status',{'agent_id':'transfer-agent'})
aw('T34-message-show','message.show',{'message_id':'aw-transfer-message-001'})
aw('T35-ack-operation','message.operation',{'operation_id':'ack-aw-transfer-message-001'})
for label,aid,path in [('relay','transfer-agent','notes/tclaude-relay.md'),('message','transfer-agent','notes/tclaude-message.md'),('sender','transfer-peer','notes/transfer-sender.md')]:
    aw('T36-'+label+'-asset','asset.read',{'agent_id':aid,'path':path})
aw('T37-final-doctor','workspace.doctor',expected=None)
aw('T38-checkpoint-list','checkpoint.list',{'agent_id':'transfer-agent'})
print('actual relay/message/ACK/stop facts read; independent verification next',flush=True)
