import hashlib,json
from pathlib import Path
from agent_workspace.app import App
import observe as observer
from transfer_record import ROOT,HOME,save,now
observer.WORKSPACE='transfer-local'
def result(name):return json.loads(json.loads((ROOT/'reports/evidence'/name).read_text(encoding='utf-8'))['stdout'])['result']
old=result('T21-old-identity-binding.json');new=result('T26-new-identity-binding.json');final=result('T32-transfer-agent-show.json');peer=result('T32-transfer-peer-show.json');transfer=result('T33-transfer-final.json');msg=result('T34-message-show.json');ack=result('T35-ack-operation.json');native=json.loads((ROOT/'reports/evidence/T39-deepseek-native-facts.json').read_text(encoding='utf-8'))['bindings'][0]
snapshot=App(HOME).store('transfer-local').snapshot()
old_binding=snapshot.json('bindings/'+old['current']+'.json')
new_binding=snapshot.json('bindings/'+transfer['target_binding']+'.json')
final_handoff=snapshot.json('handoffs/'+final['handoff']+'.json')
old_handoff=snapshot.json('handoffs/'+new['binding']['handoff']+'.json')
cp=result('T38-checkpoint-list.json')
marker=json.loads((ROOT/'reports/evidence/T12-transfer-marker.json').read_text(encoding='utf-8'))['marker']
notes={name:(HOME/'instances/transfer-local/transfer-agent/notes'/name).read_text(encoding='utf-8') for name in ('source.md','codex-origin.md','tclaude-relay.md','tclaude-message.md')}
checks={
 'same_identity':old['id']==new['id']==final['id']=='transfer-agent',
 'same_root':old['directories']==new['directories']==final['directories'],
 'native_session_changed':old['binding']['session']!=new['binding']['session']==native['init'][0]['session_id'],
 'transfer_completed':transfer['state']=='completed',
 'old_binding_released':old_binding['phase']=='released',
 'new_binding_released':new_binding['phase']=='released' and final['current'] is None,
 'peer_released':peer['current'] is None and not peer['runtime']['runner_alive'],
 'target_runner_exited':not final['runtime']['runner_alive'],
 'old_binding_probe_absent':result('T28-old-binding-operation-absent.json')['state']=='not_recorded',
 'message_published':msg['message']['id']=='aw-transfer-message-001' and msg['message']['from']['agent']=='transfer-peer',
 'message_marker_matches':marker in msg['message']['content'],
 'ack_published':ack['state']=='published' and ack['agent']=='transfer-agent' and ack['binding']==new_binding['id'] and msg['ack']['message_id']=='aw-transfer-message-001',
 'notes_markers_match':all(marker in text for text in notes.values()),
 'relay_old_checkpoint_matches':old_handoff['checkpoint'] in notes['tclaude-relay.md'],
 'native_exact_init':all(i['model']=='claude-deepseek-v4.1-flash[1m]' for i in native['init']),
 'native_assistant_route':native['assistant_models']==['deepseek/deepseek-flash'],
 'native_two_success_results':len(native['results'])==2 and all(r['event']['subtype']=='success' and not r['event']['is_error'] and r['completion']['status']=='completed' for r in native['results']),
 'result_model_usage_exact':all('claude-deepseek-v4.1-flash[1m]' in (r['event'].get('model_usage') or {}) for r in native['results']),
 'watch_disabled':not final['watch']['enabled'],
 'doctor_healthy':result('T37-final-doctor.json')['state']=='healthy',
}
codex_counts={aid:{kind:sum(t['method']==kind for t in observer.observe(aid)['native_turns']) for kind in ('turn/started','turn/completed')} for aid in ('transfer-agent','transfer-peer')}
parsed=[]
for path in sorted((ROOT/'reports/evidence').glob('T*.json')):
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    for field in ('stdout','stderr'):
        text=value.get(field,'').lstrip()
        if text.startswith(('{','[')):json.loads(text)
    parsed.append(path.name)
save('T40-independent-protocol-verification',{'time':now(),'checks':checks,'all_passed':all(checks.values()),'old_binding':old_binding,'new_binding':new_binding,'old_handoff':old_handoff,'final_handoff':final_handoff,'checkpoint_pointers':cp,'codex_counts':codex_counts,'sdk_query_terminal_count':len(native['results']),'parsed_json_records':parsed,'marker':marker,'claim':'Platform effects and native wrapper route verified; not independent model weights verification','strict_aw_only':False})
print(json.dumps({'all_checks_passed':all(checks.values()),'failed':[k for k,v in checks.items() if not v],'codex_counts':codex_counts,'sdk_terminal_count':len(native['results']),'json_parsed':len(parsed)},ensure_ascii=False))
if not all(checks.values()):raise SystemExit('Independent transfer check failed; preserve facts')
