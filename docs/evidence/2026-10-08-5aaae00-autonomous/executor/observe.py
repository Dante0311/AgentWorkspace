import json
import sys
from pathlib import Path
from record import ROOT, HOME, WORKSPACE, save, now

def observe(agent):
    root=HOME/'instances'/WORKSPACE/agent
    local=root/'.aw-local'
    out={'time':now(),'agent':agent,'transfer':None,'runtime':None,'inputs':[],'native_turns':[]}
    for name in ['transfer','status']:
        p=local/(name+'.json')
        if p.exists():out['transfer' if name=='transfer' else 'runtime']=json.loads(p.read_text(encoding='utf-8'))
    for p in sorted((local/'inputs').glob('*.json')):
        item=json.loads(p.read_text(encoding='utf-8'));out['inputs'].append(item)
    for p in sorted((root/'records').glob('*/runtime.jsonl')):
        for line in p.read_text(encoding='utf-8').splitlines():
            row=json.loads(line)
            if row.get('method') in ('turn/started','turn/completed'):
                out['native_turns'].append({'binding':p.parent.name,**row})
    return out

if __name__=='__main__':
    name=sys.argv[1];out=observe(sys.argv[2] if len(sys.argv)>2 else 'repair-alpha');save(name,out)
    print(json.dumps({'time':out['time'],'agent':out['agent'],'transfer':out['transfer'], 'runtime':out['runtime'], 'inputs':[{'id':i['id'],'state':i['state'],'turn':i.get('result',{}).get('turn',{}).get('id'),'checkpoint_revision':i.get('checkpoint_revision')} for i in out['inputs']], 'turns':out['native_turns']},ensure_ascii=False)[:11000])
