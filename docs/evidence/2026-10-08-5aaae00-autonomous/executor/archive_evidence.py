import hashlib,json,re,sys,zipfile
from pathlib import Path
from record import ROOT,HOME,now

label=sys.argv[1]
package=ROOT/'shareable'/label
package.mkdir(parents=True,exist_ok=False)
entries=[]
def sha(data):return hashlib.sha256(data).hexdigest()
replacements=[(str(ROOT),'<E2E_ROOT>'),(str(Path.home()),'<USER_HOME>'),('<DEVELOPMENT_REPO>','<DEVELOPMENT_REPO>'),('<NODE_HOME>','<NODE_HOME>')]
def redact(text):
    for source,target in replacements:
        for multiplier in (8,4,2,1):text=text.replace(source.replace('\\','\\'*multiplier),target)
        text=text.replace(source.replace('\\','/'),target)
    text=re.sub(r'(?<![A-Za-z0-9])(?:sk-|eyJ)[A-Za-z0-9_.-]{12,}','<REDACTED>',text)
    text=re.sub(r'(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,\"}]+',r'\1<REDACTED>',text)
    text=re.sub(r'[\w.+-]+@[\w.-]+','<ACCOUNT>',text)
    return text
def emit(source,destination,data=None,processing='UTF-8 path/account redaction'):
    original=source.read_bytes()
    archive=redact((data if data is not None else original.decode('utf-8-sig'))).encode('utf-8')
    target=package/destination
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(archive)
    entries.append({'source':source.relative_to(ROOT).as_posix(),'archive':destination,'source_sha256':sha(original),'archive_sha256':sha(archive),'processing':processing})
def dump(value):return json.dumps(value,ensure_ascii=False,indent=2)+'\n'

for source in sorted((ROOT/'reports').rglob('*')):
    if not source.is_file() or source.suffix not in ('.md','.json'):continue
    destination=source.relative_to(ROOT).as_posix()
    data=None;processing='UTF-8 path/account redaction'
    if source.name=='24-tclaude-sdk-handshake.json':
        original=json.loads(source.read_text(encoding='utf-8-sig'))
        result=json.loads(original['stdout'])['result']
        original['stdout']=dump({'ok':True,'result':{key:result.get(key) for key in ('state','authentication','model_invoked','catalog')}})
        original['stderr']=''
        data=dump(original);processing='Only handshake state/auth category/query=false/catalog category; model catalog and raw diagnostics excluded; path redaction'
    elif source.name=='23-tclaude-upstream-help.json':
        original=json.loads(source.read_text(encoding='utf-8-sig'))
        help_text=original['stdout']
        original['stdout']=dump({'model_query':False,'documented_flags_present':{flag:flag in help_text for flag in ('--model','--resume','--setting-sources','--tools','--strict-mcp-config','--permission-mode')},'documented_auth_command_present':'auth ' in help_text})
        original['stderr']=''
        data=dump(original);processing='Selected documented compatibility flags only; full help/internal URLs excluded; path redaction'
    elif source.name in ('63-process-audit-after-maintenance.json','68-final-native-process-boundaries.json'):
        original=json.loads(source.read_text(encoding='utf-8-sig'))
        if isinstance(original,list):
            original={'source_observations':len(original),'batch_native_clients':[],'excluded':'observer shell commandline; process inventory, no batch client present'}
        elif source.name.startswith('68-'):
            records=original.pop('relevant_native_processes',[])
            original['native_names_count']={name:sum(p['name']==name for p in records) for name in sorted({p['name'] for p in records})}
            original['tclaude_or_claude_ownership_observation']=[{k:p[k] for k in ('pid','name','command_mentions_batch','ownership')} for p in records if p['name'] in ('tclaude.exe','claude.exe')]
        else:
            original={'source_observation':'observer shell only','batch_native_clients':[],'commandlines_excluded':True}
        data=dump(original);processing='Ownership/count summary only; unrelated process IDs/images/commandlines excluded; path redaction'
    emit(source,destination,data,processing)

for source in sorted((ROOT/'tools').glob('*.py')):
    emit(source,'executor/'+source.name,processing='Review-only executor script; path redaction; not part of product or a delivery task')

for ws in ('watch-local','maintenance-local'):
    base=HOME/'instances'/ws
    for root in sorted(base.iterdir()):
        if not (root/'records').exists():continue
        for source in sorted(root.rglob('*')):
            if not source.is_file():continue
            relative=source.relative_to(root).as_posix()
            destination='proof/'+ws+'/'+root.name+'/'+('AGENTS.snapshot.md' if relative=='AGENTS.md' else relative)
            if relative=='AGENTS.md' or relative.startswith(('notes/','messages/','.aw/checkpoints/')):
                emit(source,destination)
            elif relative.startswith('records/') and source.name=='runtime.jsonl':
                selected=[]
                for line in source.read_text(encoding='utf-8').splitlines():
                    row=json.loads(line);method=row.get('method');item=row.get('params',{}).get('item',{})
                    if method in ('turn/started','turn/completed','error'):
                        row.get('params',{}).get('turn',{}).pop('items',None)
                        selected.append(row)
                    elif method=='thread/started':
                        thread=row.get('params',{}).get('thread',{})
                        selected.append({'method':method,'params':{'thread':{k:thread.get(k) for k in ('id','model','modelProvider','cwd','status')}}})
                    elif method=='item/completed' and item.get('type') in ('dynamicToolCall','mcpToolCall','commandExecution'):
                        selected.append(row)
                emit(source,destination,'\n'.join(json.dumps(r,ensure_ascii=False) for r in selected)+'\n',processing='Selected session/turn terminal facts, completed platform/tool calls and errors only; reasoning, chat text, deltas, accounts/rate limits/catalog excluded; path redaction')
            elif relative.startswith('.aw-local/') and (source.name in ('status.json','watch.json','transfer.json') or relative.startswith(('.aw-local/inputs/','.aw-local/checkpoint-operations/'))):
                value=json.loads(source.read_text(encoding='utf-8'))
                if relative.startswith('.aw-local/inputs/'):value.pop('text',None)
                emit(source,destination,dump(value),processing='Read-only evidence snapshot; queued prompt text excluded; cannot import as runnable state; path redaction')

for source in sorted((HOME/'operations').glob('*.json')):
    emit(source,'proof/operations/'+source.name)
for name in ('run.json','grants.json','schedule.json'):
    source=HOME/'maintenance/maintenance-local'/name
    if source.exists():emit(source,'proof/maintenance/'+name)
for source in sorted((HOME/'maintenance/maintenance-local/repairs').glob('*.json')):
    emit(source,'proof/maintenance/repairs/'+source.name)

manifest={'created_at':now(),'baseline':'5aaae00520374b022e0c38fa21f312f8e08629ba','files':entries,'purpose':'Review evidence only; original failure evidence retained; no runnable imported state'}
(package/'SOURCE-MANIFEST.json').write_text(dump(manifest),encoding='utf-8')
(package/'EXCLUSIONS.md').write_text('''# 分享边界

排除凭据/auth/config、账号/授权头、私密机器路径、截图、整份聊天、native reasoning、stream deltas、rate limits、完整模型/工具catalog、原生未筛选日志、安装环境/二进制/缓存、完整AW_HOME、所有运行锁。不纳入Lead独立Desktop目录。

原始文件只在本轮根保存。SOURCE-MANIFEST逐项记录源SHA256与脱敏归档SHA256；筛选日志明确标注处理方法，二者可不同。路径替换为E2E_ROOT/USER_HOME/DEVELOPMENT_REPO/NODE_HOME标识。账号标识脱敏。JSON运行快照和executor脚本只供审查，不作为产品、恢复包或用户Agent任务。

tclaude仅无query预检；共享daemon归属未确认，不停止也不声称全部退出。模型选择后由Lead明确授权增量继续，新包另建，不覆盖本批证据。
''',encoding='utf-8')

issues=[]
for path in package.rglob('*'):
    if not path.is_file():continue
    content=path.read_text(encoding='utf-8')
    if re.search(r'(?i)(?<![A-Za-z0-9])[A-Z]:[\\/]',content):issues.append('machine path: '+path.relative_to(package).as_posix())
    if re.search(r'(?<![A-Za-z0-9])(?:sk-|eyJ)[A-Za-z0-9_.-]{12,}',content):issues.append('credential pattern: '+path.relative_to(package).as_posix())
    if path.suffix=='.md':
        for link in re.findall(r'\]\(([^)]+)\)',content):
            if '://' in link or link.startswith('#'):continue
            target=(path.parent/link.split('#')[0]).resolve()
            if not target.is_file():issues.append('broken link: '+path.relative_to(package).as_posix()+' '+link)
if issues:
    (ROOT/'private'/('package-validation-'+label+'.json')).write_text(dump(issues),encoding='utf-8')
    raise SystemExit('Package validation failed; preserved attempt: '+str(len(issues)))
checksums={p.relative_to(package).as_posix():sha(p.read_bytes()) for p in sorted(package.rglob('*')) if p.is_file()}
(package/'SHA256SUMS').write_text('\n'.join(value+'  '+name for name,value in checksums.items())+'\n',encoding='utf-8')
for name,value in checksums.items():assert sha((package/name).read_bytes())==value
archive=ROOT/'shareable'/(label+'.zip')
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as stream:
    for path in sorted(package.rglob('*')):
        if path.is_file():stream.write(path,path.relative_to(package))
with zipfile.ZipFile(archive) as stream:assert stream.testzip() is None
receipt={'created_at':now(),'package':str(package),'archive':str(archive),'archive_sha256':sha(archive.read_bytes()),'source_archive_pairs':len(entries),'checked_files':len(checksums),'all_hashes_verified':True,'zip_crc_verified':True,'relative_links_verified':True,'privacy_pattern_scan_passed':True}
(ROOT/'reports'/('PACKAGE-'+label+'.json')).write_text(dump(receipt),encoding='utf-8')
print(dump(receipt))
