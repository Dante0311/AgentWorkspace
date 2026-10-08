import json,collections
from transfer_record import ROOT,HOME,save,now

root=HOME/'instances/transfer-local/transfer-agent'
native=[]
for path in sorted((root/'records').glob('*/runtime.jsonl')):
    rows=[json.loads(l) for l in path.read_text(encoding='utf-8').splitlines()]
    if not any(r.get('native_type') for r in rows):continue
    tools=[];results=[];init=[];models=[];errors=[]
    for row in rows:
        event=row.get('event',{});kind=row.get('native_type')
        if kind=='SystemMessage' and event.get('subtype')=='init':
            init.append({k:event.get('data',{}).get(k) for k in ('model','session_id','permissionMode','cwd')})
        if kind=='AssistantMessage':
            if event.get('model') and event['model'] not in models:models.append(event['model'])
            for block in event.get('content',[]):
                if block.get('name'):tools.append({'observed_at':row['observed_at'],'submission':row.get('local_submission_id'),'id':block.get('id'),'name':block['name'],'input':block.get('input')})
        if kind=='UserMessage':
            for block in event.get('content',[]) if isinstance(event.get('content'),list) else []:
                if block.get('tool_use_id'):tools.append({'observed_at':row['observed_at'],'submission':row.get('local_submission_id'),'tool_use_id':block['tool_use_id'],'is_error':block.get('is_error'),'content':block.get('content')})
        if kind=='ResultMessage':
            results.append({'observed_at':row['observed_at'],'submission':row.get('local_submission_id'),'completion':row.get('completion'),'event':{k:event.get(k) for k in ('subtype','is_error','session_id','num_turns','usage','model_usage','modelUsage','errors')}})
        if kind=='ErrorMessage':errors.append(row)
    native.append({'binding':path.parent.name,'source':path.relative_to(ROOT).as_posix(),'event_type_counts':dict(collections.Counter(r.get('native_type') for r in rows)),'init':init,'assistant_models':models,'tool_calls_and_results':tools,'results':results,'errors':errors,'thinking_content_excluded':True})
save('T39-deepseek-native-facts',{'time':now(),'bindings':native,'claim':'Wrapper-reported model route, not independent underlying weights verification'})
print(json.dumps({'native_bindings':len(native),'init':[n['init'] for n in native],'assistant_models':[n['assistant_models'] for n in native],'results':[len(n['results']) for n in native],'native_tool_names':[sorted({t.get('name') for t in n['tool_calls_and_results'] if t.get('name')}) for n in native]},ensure_ascii=False))
