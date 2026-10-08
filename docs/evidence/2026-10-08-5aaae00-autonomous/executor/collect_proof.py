import hashlib,json,sys
from pathlib import Path
from record import ROOT,HOME,save,now
import observe
suffix=sys.argv[1]
agents=[]
for ws in ('watch-local','maintenance-local','transfer-local'):
    observe.WORKSPACE=ws
    base=HOME/'instances'/ws
    if not base.exists():continue
    for root in sorted(base.iterdir()):
        if not (root/'records').is_dir():continue
        obs=observe.observe(root.name)
        tools=[];sdk_results=[];native_sessions=[]
        for path in sorted((root/'records').glob('*/runtime.jsonl')):
            for line in path.read_text(encoding='utf-8').splitlines():
                row=json.loads(line)
                item=row.get('params',{}).get('item',{})
                if row.get('method')=='thread/started':
                    thread=row.get('params',{}).get('thread',{})
                    native_sessions.append({k:thread.get(k) for k in ('id','model','modelProvider','cwd')})
                if row.get('method')=='item/completed' and item.get('type')=='dynamicToolCall':
                    args=item.get('arguments',{})
                    if isinstance(args,str):
                        try:args=json.loads(args)
                        except ValueError:args={'unparsed':args}
                    tools.append({'binding':path.parent.name,'id':item.get('id'),'tool':item.get('tool'),'command':args.get('command'),'arguments':args.get('arguments'),'success':item.get('success'),'status':item.get('status'),'contentItems':item.get('contentItems')})
                if row.get('native_type')=='ResultMessage':sdk_results.append(row)
        agents.append({'workspace':ws,'agent':root.name,'observation':obs,'codex_started':sum(t['method']=='turn/started' for t in obs['native_turns']),'codex_completed':sum(t['method']=='turn/completed' for t in obs['native_turns']),'codex_native_sessions':native_sessions,'codex_tool_calls':tools,'sdk_results':sdk_results})
save(suffix,{'time':now(),'agents':agents,'totals':{'codex_started':sum(a['codex_started'] for a in agents),'codex_completed':sum(a['codex_completed'] for a in agents),'sdk_terminal_results':sum(len(a['sdk_results']) for a in agents)}})
print(json.dumps({'totals':{'codex_started':sum(a['codex_started'] for a in agents),'codex_completed':sum(a['codex_completed'] for a in agents),'sdk_terminal_results':sum(len(a['sdk_results']) for a in agents)},'states':[(a['workspace'],a['agent'],(a['observation']['runtime'] or {}).get('state')) for a in agents]},ensure_ascii=False))
