import hashlib,json,re,sys,zipfile
from pathlib import Path
from transfer_record import ROOT,HOME,now
label=sys.argv[1]
package=ROOT/'shareable'/'deepseek-transfer'/label
package.mkdir(parents=True,exist_ok=False)
manifest=[]
def sha(data):return hashlib.sha256(data).hexdigest()
def redact(text):
    for source,target in ((str(ROOT),'<E2E_ROOT>'),(str(Path.home()),'<USER_HOME>'),('<NODE_HOME>','<NODE_HOME>')):
        for n in (8,4,2,1):text=text.replace(source.replace('\\','\\'*n),target)
        text=text.replace(source.replace('\\','/'),target)
    text=re.sub(r'(?<![A-Za-z0-9])(?:sk-|eyJ)[A-Za-z0-9_.-]{12,}','<REDACTED>',text)
    text=re.sub(r'(?<![\\\w])[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}','<ACCOUNT>',text)
    return text
def scrub(value):
    if isinstance(value,str):return redact(value)
    if isinstance(value,list):return [scrub(v) for v in value]
    if isinstance(value,dict):return {k:scrub(v) for k,v in value.items()}
    return value
def dump(value):return json.dumps(scrub(value),ensure_ascii=False,indent=2)+'\n'
def emit(source,name,data=None,processing='Path/account redaction; JSON parsed before and after processing'):
    original=source.read_bytes()
    text=original.decode('utf-8-sig') if data is None else data
    if source.suffix=='.json' or name.endswith('.json'):
        value=json.loads(text)
        text=dump(value)
        json.loads(text)
    elif name.endswith('.jsonl'):
        text='\n'.join(json.dumps(scrub(json.loads(line)),ensure_ascii=False) for line in text.splitlines())+'\n'
        for line in text.splitlines():json.loads(line)
    else:text=redact(text)
    target=package/name
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(text,encoding='utf-8')
    manifest.append({'source':source.relative_to(ROOT).as_posix(),'archive':name,'source_sha256':sha(original),'archive_sha256':sha(target.read_bytes()),'processing':processing})

for filename in ('TRANSFER-DEEPSEEK.md','TRANSFER-CHECKPOINT.md'):
    emit(ROOT/'reports'/filename,'reports/'+filename)
for source in sorted((ROOT/'reports/evidence').glob('T*.json')):
    data=None
    processing='Structured JSON path/account redaction; JSON stdout/stderr parsed after redaction'
    if source.name=='T02-no-query-sdk-handshake.json':
        value=json.loads(source.read_text(encoding='utf-8'))
        result=json.loads(value['stdout'])['result']
        value['stdout']=json.dumps({'ok':True,'result':{k:result.get(k) for k in ('state','authentication','model_invoked','catalog')}},ensure_ascii=False)
        value['stderr']=''
        data=json.dumps(value,ensure_ascii=False)
        processing+='; full catalog excluded, only no-query/auth category/connection state preserved'
    emit(source,'reports/evidence/'+source.name,data,processing)
    value=json.loads((package/'reports/evidence'/source.name).read_text(encoding='utf-8'))
    for key in ('stdout','stderr'):
        text=value.get(key,'').lstrip()
        if text.startswith(('{','[')):json.loads(text)

script_names=('transfer_record.py','transfer_preflight.py','prepare_transfer_deepseek.py','run_transfer_deepseek.py','finish_transfer_deepseek.py','collect_transfer_native.py','verify_transfer_deepseek.py','transfer_software_audit.py','archive_transfer_deepseek.py')
for filename in script_names:
    emit(ROOT/'tools'/filename,'executor/'+filename,processing='Review-only executor, not product; path redaction')

for root in sorted((HOME/'instances/transfer-local').iterdir()):
    if not (root/'records').is_dir():continue
    for source in sorted(root.rglob('*')):
        if not source.is_file():continue
        rel=source.relative_to(root).as_posix()
        target='proof/transfer-local/'+root.name+'/'+('AGENTS.snapshot.md' if rel=='AGENTS.md' else rel)
        if rel=='AGENTS.md' or rel.startswith(('notes/','messages/','.aw/checkpoints/')):
            emit(source,target)
        elif rel.startswith('.aw-local/') and (source.name in ('transfer.json','status.json','watch.json','runtime.json') or rel.startswith(('.aw-local/inputs/','.aw-local/checkpoint-operations/'))):
            value=json.loads(source.read_text(encoding='utf-8'))
            if rel.startswith('.aw-local/inputs/'):value.pop('text',None)
            emit(source,target,json.dumps(value,ensure_ascii=False),processing='Evidence-only protocol/selected local observation snapshot; boot prompt removed; not runnable import; path redaction')
        elif rel.startswith('records/') and source.name=='runtime.jsonl':
            selected=[]
            for line in source.read_text(encoding='utf-8').splitlines():
                row=json.loads(line);method=row.get('method');event=row.get('event',{});kind=row.get('native_type')
                if method in ('turn/started','turn/completed','error'):
                    row.get('params',{}).get('turn',{}).pop('items',None)
                    selected.append(row)
                elif method=='thread/started':
                    thread=row.get('params',{}).get('thread',{})
                    selected.append({'method':method,'params':{'thread':{k:thread.get(k) for k in ('id','model','modelProvider','cwd','status')}}})
                elif method=='item/completed' and row.get('params',{}).get('item',{}).get('type') in ('dynamicToolCall','mcpToolCall','commandExecution'):
                    selected.append(row)
                elif kind=='SystemMessage' and event.get('subtype')=='init':
                    row['event']={'subtype':'init','data':{k:event.get('data',{}).get(k) for k in ('model','session_id','permissionMode','cwd')}}
                    selected.append(row)
                elif kind=='AssistantMessage':
                    row['event']={'model':event.get('model'),'parent_tool_use_id':event.get('parent_tool_use_id'),'content':[b for b in event.get('content',[]) if b.get('name')]}
                    if row['event']['content']:selected.append(row)
                elif kind=='UserMessage' and isinstance(event.get('content'),list):
                    row['event']={'content':[b for b in event['content'] if b.get('tool_use_id')]}
                    if row['event']['content']:selected.append(row)
                elif kind=='ResultMessage':
                    row['event']={k:event.get(k) for k in ('subtype','is_error','session_id','num_turns','model_usage','usage','errors','permission_denials','terminal_reason')}
                    selected.append(row)
                elif kind=='ErrorMessage':selected.append(row)
            text='\n'.join(json.dumps(row,ensure_ascii=False) for row in selected)+'\n'
            emit(source,target,text,processing='Selected init model/session, actual tool calls/results/errors, query completions; chat text/thinking/reasoning/streams/accounts/catalog excluded; JSONL parsed and path redacted')

for identifier in ('aw-transfer-message-001','ack-aw-transfer-message-001'):
    source=HOME/'operations'/(identifier+'.json')
    emit(source,'proof/operations/'+source.name)
(package/'EXCLUSIONS.md').write_text('''# 本包范围

仅2026-10-08 DeepSeek交接增量。旧query=0/待选型报告、r3包和旧测试均保留且未改。源文件SHA256及脱敏归档SHA256分别在SOURCE-MANIFEST，字段筛选处理明确记录。

排除凭据/授权头/全局配置/账号、私密机器路径、整份聊天、thinking_tokens及native reasoning、stream deltas、完整工具/模型catalog、未筛选原生日志、截图、安装二进制/缓存、完整AW_HOME与运行锁。原始证据只在本轮根保留。JSON先解析成字段再脱敏，JSON/JSONL及内嵌JSON stdout/stderr均解析验证，避免换行与@tencent误判成邮件破坏JSON。

AGENTS.snapshot.md为证据而非活动指令；executor脚本和状态JSON只供审查，不作为产品或可运行恢复包。共享tclaude/Claude服务未证独占，未停止、不宣称全部退出。模型仅为包装器回报的路由标识，low仅证明已传递，无底层权重/effective-effort证明。便捷profile方括号拒绝仍开放，4次Read与2次参数错误保留。
''',encoding='utf-8')
(package/'SOURCE-MANIFEST.json').write_text(json.dumps({'created_at':now(),'baseline':'5aaae00520374b022e0c38fa21f312f8e08629ba','scope':'deepseek-transfer increment only','files':manifest},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
issues=[]
json_count=0;jsonl_rows=0
for path in package.rglob('*'):
    if not path.is_file():continue
    text=path.read_text(encoding='utf-8')
    if re.search(r'(?i)(?<![A-Za-z0-9])[A-Z]:[\\/]',text):issues.append('private path: '+path.relative_to(package).as_posix())
    if re.search(r'(?<![A-Za-z0-9])(?:sk-|eyJ)[A-Za-z0-9_.-]{12,}',text):issues.append('credential pattern: '+path.relative_to(package).as_posix())
    if path.name=='AGENTS.md':issues.append('active instruction file: '+path.relative_to(package).as_posix())
    if path.suffix=='.json':json.loads(text);json_count+=1
    elif path.suffix=='.jsonl':
        for line in text.splitlines():json.loads(line);jsonl_rows+=1
    elif path.suffix=='.md':
        for link in re.findall(r'\]\(([^)]+)\)',text):
            if '://' in link or link.startswith('#'):continue
            if not (path.parent/link.split('#')[0]).is_file():issues.append('broken link: '+path.relative_to(package).as_posix()+' '+link)
if issues:
    (ROOT/'private'/('transfer-pack-validation-'+label+'.json')).write_text(json.dumps(issues,indent=2),encoding='utf-8')
    raise SystemExit('Validation failed; preserved attempt: '+str(len(issues)))
checksums={p.relative_to(package).as_posix():sha(p.read_bytes()) for p in sorted(package.rglob('*')) if p.is_file()}
(package/'SHA256SUMS').write_text('\n'.join(h+'  '+name for name,h in checksums.items())+'\n',encoding='utf-8')
assert all(sha((package/e['archive']).read_bytes())==e['archive_sha256'] for e in manifest)
archive=package.with_suffix('.zip')
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as stream:
    for path in sorted(package.rglob('*')):
        if path.is_file():stream.write(path,path.relative_to(package))
with zipfile.ZipFile(archive) as stream:assert stream.testzip() is None
receipt={'time':now(),'package':str(package),'archive':str(archive),'archive_sha256':sha(archive.read_bytes()),'source_archive_pairs':len(manifest),'checksum_entries':len(checksums),'json_parsed':json_count,'native_jsonl_rows_parsed':jsonl_rows,'all_hashes_verified':True,'zip_crc_verified':True,'relative_links_verified':True,'private_path_secret_pattern_scan_passed':True,'active_AGENTS_files':0,'archive_includes':{'native_Read_calls':4,'invalid_asset_binding_calls':2,'public_typed_profile_rejection':True},'historical_package_overwritten':False}
(ROOT/'reports'/('TRANSFER-PACKAGE-'+label+'.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
