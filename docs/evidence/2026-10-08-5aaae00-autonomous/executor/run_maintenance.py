import json,time,subprocess
from pathlib import Path
import record,observe as observer
from record import ROOT,HOME,run,save,now
record.WORKSPACE=observer.WORKSPACE='maintenance-local'
aw=record.aw
def observed():return [observer.observe(a) for a in ('sentinel','maintainer')]
deadline=time.monotonic()+180
while time.monotonic()<deadline:
    observations=observed()
    if all(o['inputs'] and o['inputs'][0]['state']=='completed' and o['inputs'][0].get('checkpoint_revision') for o in observations):
        save('36-maint-boots-ready',observations);break
    time.sleep(3)
else:
    save('36-maint-boots-timeout',observations);raise SystemExit('caretaker boots incomplete; no fault')
for i,aid in enumerate(('sentinel','maintainer')):
    aw(f'37-{i}-watch','message.watch',{'agent_id':aid,'operation':'start','interval':3})
authority=(ROOT/'data/maintenance.git').resolve()
authority.relative_to(ROOT.resolve())
run('38-authority-is-bare',['git','--git-dir',authority,'rev-parse','--is-bare-repository'])
original=run('39-authority-original-hideRefs',['git','--git-dir',authority,'config','--local','--get-all','receive.hideRefs'],expected=None)
if original['exit_code']!=1 or original['stdout'].strip():raise SystemExit('unexpected existing hideRefs; no injection')
save('40-fault-plan',{'time':now(),'authority':str(authority),'resolved_within_root':True,'operation':'temporary local receive.hideRefs=refs/heads/main','original_values':[],'effect':'readable main; actual push to main rejected','rollback':'unset only our exact hideRefs value in finally','scope':'disposable test authority only','maintenance_claim':'repair publication; controller restores Git write condition','model_or_ledger_fabrication':False})
aw('41-schedule-on','maintenance.schedule',{'enabled':True,'interval':30,'notify':True})
show=aw('42-sentinel-binding','agent.show',{'agent_id':'sentinel'})['result']
binding=show['current']
if not binding:raise SystemExit('sentinel binding missing; no fault')
try:
    run('43-fault-inject',['git','--git-dir',authority,'config','--local','--add','receive.hideRefs','refs/heads/main'])
    result=aw('44-real-failed-publication','message.send',{'agent_id':'sentinel','binding':binding,'to':'steward','content':'Explicit isolated publication fault stimulus; no production task.','delivery':'normal','request_id':'aw-maint-fault-001'},expected=2)['result']
    aw('45-fault-doctor','workspace.doctor')
finally:
    run('46-fault-rollback',['git','--git-dir',authority,'config','--local','--unset-all','receive.hideRefs','^refs/heads/main$'])
    run('47-rollback-verified',['git','--git-dir',authority,'config','--local','--get-all','receive.hideRefs'],expected=1)
aw('48-original-still-pending','message.operation',{'operation_id':'aw-maint-fault-001'})
if result['state']!='pending':raise SystemExit('actual known pending failure not established; no repair run')
print('real pending publication preserved; Git condition restored; ready for official worker',flush=True)
