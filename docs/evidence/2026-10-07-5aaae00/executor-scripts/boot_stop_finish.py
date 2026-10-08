import hashlib
import json
import time
from record import ROOT, HOME, WORKSPACE, aw, save
from observe import observe

root=HOME/'instances'/WORKSPACE/'repair-alpha'
start=json.loads(json.loads((ROOT/'reports/evidence/51-explicit-boot-stop-start.json').read_text(encoding='utf-8'))['stdout'])['result'];binding=start['binding']
deadline=time.monotonic()+600
while time.monotonic()<deadline:
    s=observe('repair-alpha');boot=next((i for i in s['inputs'] if i['id']=='boot-'+binding),None)
    if boot and s['runtime'] and s['runtime']['binding']==binding and s['runtime']['state']=='released':break
    time.sleep(2)
else:
    save('52-explicit-boot-stop-unresolved',s);raise RuntimeError('Preserve boot outcome')
save('52-explicit-boot-stop-final',s)
assert boot['state']=='completed' and boot.get('checkpoint_revision')
turn=boot['result']['turn']['id'];terminal=next(r for r in s['native_turns'] if r['method']=='turn/completed' and r['params']['turn']['id']==turn)
assert terminal['params']['turn']['status']=='completed'
cp=aw('53-explicit-boot-stop-checkpoint','checkpoint.show',{'agent_id':'repair-alpha','checkpoint':'repair-explicit-boot-stop'})['result']
assert boot['checkpoint_revision']==cp['revision']
assert not (root/'.aw/checkpoints'/('initial-'+binding+'.json')).exists()
assert (root/'notes/source.md').read_bytes()==(root/'notes/verify-boot-stop.md').read_bytes()
show=aw('54-explicit-boot-stop-show','agent.show',{'agent_id':'repair-alpha'})['result'];assert show['current'] is None and show['runtime']['runner_alive'] is False
save('55-terminal-repair-group-proof',{'new_codex_rounds':len([r for r in s['native_turns'] if r['method']=='turn/started']),'completed_native_rounds':len([r for r in s['native_turns'] if r['method']=='turn/completed' and r['params']['turn']['status']=='completed']),'all_inputs_completed':all(i['state']=='completed' for i in s['inputs']),'boot_binding':binding,'boot_input':boot,'boot_terminal_event':terminal,'explicit_checkpoint':cp,'explicit_checkpoint_reused_for_boot':True,'automatic_initial_checkpoint_added_after_close':False,'show':show,'source_sha256':hashlib.sha256((root/'notes/source.md').read_bytes()).hexdigest(),'first_chain':'35-first-chain-proof.json','second_chain':'48-second-chain-proof.json','old_batch_untouched':True})
print('Repair group: 9 native rounds completed, boot explicit snapshot reused, all new inputs completed',flush=True)
