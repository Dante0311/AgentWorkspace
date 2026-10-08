import json,time
from record import ROOT, HOME, aw, save, now
from observe import observe

deadline=time.monotonic()+180
while time.monotonic()<deadline:
    obs=observe('watch-beta')
    if obs['inputs'] and obs['inputs'][0]['state']=='completed' and obs['inputs'][0].get('checkpoint_revision'):
        save('11-receiver-boot-complete',obs)
        break
    time.sleep(3)
else:
    save('11-receiver-boot-timeout',obs)
    raise SystemExit('receiver boot not complete; no sender launch')
aw('12-watch-enable','message.watch',{'agent_id':'watch-beta','operation':'start','interval':3})
aw('13-sender-start','agent.start',{'agent_id':'watch-alpha','open_app':False})
deadline=time.monotonic()+240
while time.monotonic()<deadline:
    observations=[observe(a) for a in ('watch-alpha','watch-beta')]
    if all(o['runtime'] and o['runtime'].get('state')=='released' for o in observations):
        save('14-watch-final-observation',{'observed_at':now(),'agents':observations,'corrective_inputs':0})
        print('both endpoints released',flush=True)
        break
    time.sleep(3)
else:
    save('14-watch-timeout-observation',{'observed_at':now(),'agents':observations,'corrective_inputs':0})
    print('bounded Watch observation ended; preserved real state',flush=True)
for aid in ('watch-alpha','watch-beta'):
    aw('15-'+aid+'-show','agent.show',{'agent_id':aid})
for mid in ('aw-watch-001','aw-watch-002'):
    aw('16-'+mid+'-show','message.show',{'message_id':mid},expected=None)
aw('17-order-asset','asset.read',{'agent_id':'watch-beta','path':'notes/watch-order.md'},expected=None)
aw('18-watch-health','workspace.doctor')
