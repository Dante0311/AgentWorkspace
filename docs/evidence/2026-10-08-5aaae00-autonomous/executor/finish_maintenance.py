import hashlib,json,time
import record,observe as observer
from record import ROOT,HOME,save,now
record.WORKSPACE=observer.WORKSPACE='maintenance-local'
aw=record.aw
deadline=time.monotonic()+240
schedule_off=False
while time.monotonic()<deadline:
    source=HOME/'operations/aw-maint-fault-001.json'
    if source.exists() and json.loads(source.read_text(encoding='utf-8')).get('state')=='published' and not schedule_off:
        aw('50-schedule-off','maintenance.schedule',{'enabled':False,'interval':30,'notify':False})
        schedule_off=True
    observations=[observer.observe(a) for a in ('sentinel','maintainer')]
    if all(o['runtime'] and o['runtime'].get('state')=='released' for o in observations):
        save('51-maint-final-observation',{'time':now(),'agents':observations});break
    time.sleep(3)
else:
    save('51-maint-timeout-observation',{'time':now(),'agents':observations})
    print('bounded observation timeout; preserve state, no corrective input',flush=True)
if not schedule_off:aw('50-schedule-off','maintenance.schedule',{'enabled':False,'interval':30,'notify':False})
aw('52-maint-revoke','maintenance.grant',{'agent_id':'maintainer','commands':[],'targets':[]})
for aid in ('sentinel','maintainer'):
    aw('53-'+aid+'-show','agent.show',{'agent_id':aid})
aw('54-original-operation-final','message.operation',{'operation_id':'aw-maint-fault-001'},expected=None)
aw('55-independent-doctor','workspace.doctor',expected=None)
aw('56-maintenance-status','maintenance.status',expected=None)
for aid,path in [('maintainer','notes/maintenance-repair.md'),('sentinel','notes/maintenance-verification.md')]:
    aw('57-'+aid+'-asset','asset.read',{'agent_id':aid,'path':path},expected=None)
for mid in ('aw-maint-task-001','aw-maint-result-001'):
    aw('58-'+mid+'-show','message.show',{'message_id':mid},expected=None)
repair=HOME/'maintenance/maintenance-local/repairs/aw-maint-repair-001.json'
if repair.exists():
    value=json.loads(repair.read_text(encoding='utf-8'))
    save('59-repair-receipt',value)
    if value['state']=='applied' and value.get('result',{}).get('state')=='published':
        before=hashlib.sha256(repair.read_bytes()).hexdigest()
        aw('60-repeat-applied-repair-id','maintenance.repair',{'agent_id':'sentinel','action':'publication-reconcile','operation_id':'aw-maint-fault-001','request_id':'aw-maint-repair-001'},expected=None)
        save('61-repair-idempotence',{'before_sha256':before,'after_sha256':hashlib.sha256(repair.read_bytes()).hexdigest(),'same_request_id':True,'model_or_message_replay':False})
print('maintenance final observation saved; stop official worker separately',flush=True)
