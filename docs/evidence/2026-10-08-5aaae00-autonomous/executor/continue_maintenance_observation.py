import json
import record
from record import ROOT,save,now
record.WORKSPACE='maintenance-local'
original=json.loads((ROOT/'reports/evidence/44-real-failed-publication.json').read_text(encoding='utf-8'))
receipt=json.loads(original['stdout'])['result']
assert original['exit_code']==2 and receipt['state']=='pending'
save('49-controller-exit-expectation-error',{'time':now(),'actual_exit':2,'actual_protocol_state':'pending','old_controller_expected_exit':0,'scope':'helper terminated after successful intended fault; finally rollback executed','side_effect_replayed':False,'fault_reinjected':False,'continuation':'readonly original receipt and doctor, then official worker'})
record.aw('48-original-still-pending','message.operation',{'operation_id':'aw-maint-fault-001'})
record.aw('45-fault-doctor-after-rollback','workspace.doctor')
print('actual pending verified after rollback; no resend or new fault',flush=True)
