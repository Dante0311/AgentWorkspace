import json,time
import observe as observer
from transfer_record import ROOT,HOME,aw,save,now
observer.WORKSPACE='transfer-local'
def obs():return observer.observe('transfer-agent')
deadline=time.monotonic()+180
while time.monotonic()<deadline:
    value=obs()
    if value['inputs'] and value['inputs'][0]['state']=='completed' and value['inputs'][0].get('checkpoint_revision'):
        save('T19-codex-boot-complete',value);break
    if value.get('runtime',{}).get('state') in ('failed','connection_failed'):break
    time.sleep(3)
else:
    save('T19-codex-boot-timeout',value);raise SystemExit('original boot incomplete; no handoff request')
if not value['inputs'] or value['inputs'][0]['state']!='completed':
    save('T19-codex-boot-failed',value);raise SystemExit('original boot failed; no handoff')
aw('T20-codex-origin-read','asset.read',{'agent_id':'transfer-agent','path':'notes/codex-origin.md'})
baseline=aw('T21-old-identity-binding','agent.show',{'agent_id':'transfer-agent'})['result']
profile=json.loads((ROOT/'reports/evidence/T00-authorized-profile.json').read_text(encoding='utf-8'))['Lead_exact_profile']
transfer=aw('T22-public-exact-profile-transfer','agent.transfer',{'agent_id':'transfer-agent','target_config':profile,'request_id':'deepseek-transfer-001'})['result']
save('T23-request-boundary',{'time':now(),'old_agent_identity':baseline['id'],'old_root':baseline['directories'],'old_binding':baseline['current'],'old_session':baseline['binding']['session'],'transfer_request':transfer,'model_queries_before_target_boot':0,'controller_started_successor':False})
print('formal transfer requested once; platform owns successor launch',flush=True)
deadline=time.monotonic()+240
while time.monotonic()<deadline:
    value=obs();record=value.get('transfer') or {}
    boot=[i for i in value['inputs'] if i.get('binding')==transfer['target_binding'] and i.get('purpose')=='initial']
    if record.get('state')=='completed' and boot and boot[0]['state']=='completed' and boot[0].get('checkpoint_revision'):
        save('T24-target-relay-completed',value);break
    if record.get('state') in ('outcome_unknown','relay_failed') or (boot and boot[0]['state']=='failed'):
        save('T24-target-relay-failed',value);raise SystemExit('target failure preserved; no replacement/replay')
    time.sleep(3)
else:
    save('T24-target-relay-timeout',value);raise SystemExit('bounded target observation; no replay or manual successor start')
aw('T25-tclaude-relay-asset','asset.read',{'agent_id':'transfer-agent','path':'notes/tclaude-relay.md'})
aw('T26-new-identity-binding','agent.show',{'agent_id':'transfer-agent'})
aw('T27-old-binding-write-rejected','message.send',{'agent_id':'transfer-agent','binding':baseline['current'],'to':'transfer-peer','content':'Must be rejected before recording any operation: old released binding.','delivery':'normal','request_id':'deepseek-old-binding-invalid-001'},expected=2)
aw('T28-old-binding-operation-absent','message.operation',{'operation_id':'deepseek-old-binding-invalid-001'},expected=None)
aw('T29-target-watch-on','message.watch',{'agent_id':'transfer-agent','operation':'start','interval':3})
aw('T30-peer-start','agent.start',{'agent_id':'transfer-peer','open_app':False})
print('target relay complete; real peer message stage started',flush=True)
