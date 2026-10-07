import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile
from record import ROOT, save, now

package=ROOT/'shareable'/(ROOT.name+'-r2')
assert not package.exists(), 'Never overwrite a prior evidence archive'
package.mkdir(parents=True)
user=Path.home()
maps=[(str(ROOT),'<E2E_ROOT>'),(r'<DEV_REPO>','<DEV_REPO>'),(str(user),'<USER_HOME>'),(r'<NODE_HOME>','<NODE_HOME>')]
replacements=[]
for original,label in maps:
    replacements.append((original.replace('\\','/'),label))
    for count in [1,2,4,8]: replacements.append((original.replace('\\','\\'*count),label))
replacements.sort(key=lambda x:len(x[0]),reverse=True)

def sanitize(text):
    for original,label in replacements:text=re.sub(re.escape(original),lambda m:label,text,flags=re.I)
    text=re.sub(r'[\w.+-]+@[\w.-]+','[ACCOUNT]',text)
    text=re.sub(r'(?<![A-Za-z0-9])(?:sk-|eyJ)[A-Za-z0-9_.-]{12,}','[REDACTED]',text)
    return text

entries=[]
def add(src,relative,*,content=None,method='machine paths/account identifiers redacted; event/state/IDs preserved'):
    raw=src.read_bytes();dest=package/relative;dest.parent.mkdir(parents=True,exist_ok=True)
    text=raw.decode('utf-8-sig') if content is None else content
    out=sanitize(text).encode('utf-8');dest.write_bytes(out)
    entries.append({'source_file':sanitize(str(src.relative_to(ROOT))),'archive_file':str(relative).replace('\\','/'),'source_sha256':hashlib.sha256(raw).hexdigest(),'archive_sha256':hashlib.sha256(out).hexdigest(),'source_bytes':len(raw),'archive_bytes':len(out),'processing':method})

for src in sorted((ROOT/'reports').glob('*.md')):add(src,Path('reports')/src.name)
for src in sorted((ROOT/'reports/evidence').iterdir()):
    if src.suffix in ('.json','.txt','.xml'):add(src,Path('reports/evidence')/src.name)
for src in sorted((ROOT/'tools').glob('*.py')):
    add(src,Path('executor-scripts')/src.name,method='machine paths redacted; execution harness for review only; no product source changes')
ledger=json.loads((ROOT/'reports/evidence/88-final-model-input-ledger.json').read_text(encoding='utf-8'))
for info in ledger['rounds']:
    agent=info['agent'];binding=info['binding'];root=ROOT/'data/home/instances/repair-local'/agent
    source=root/'records'/binding/'runtime.jsonl';raw_copy=ROOT/'private/native-raw'/agent/binding/'runtime.jsonl';raw_copy.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,raw_copy)
    selected=[];excluded={}
    for line in source.read_text(encoding='utf-8').splitlines():
        row=json.loads(line);method=row.get('method');item=row.get('params',{}).get('item',{});typ=item.get('type')
        keep=method in ('turn/started','turn/completed','thread/started','error') or (method in ('item/started','item/completed') and typ in ('dynamicToolCall','userMessage','agentMessage','commandExecution','mcpToolCall','sleep'))
        if keep:selected.append(row)
        else:excluded[method or row.get('kind','other')]=excluded.get(method or row.get('kind','other'),0)+1
    content='\n'.join(json.dumps(r,ensure_ascii=False) for r in selected)+'\n'
    add(source,Path('native')/agent/binding/'runtime-events.jsonl',content=content,method='selected necessary test turn/tool/sleep/error events; account/rateLimit, reasoning and streaming duplicates omitted; machine paths redacted')
    entries[-1]['selected_event_count']=len(selected);entries[-1]['excluded_event_method_counts']=excluded
for agent in ['repair-alpha','repair-beta']:
    root=ROOT/'data/home/instances/repair-local'/agent
    for pattern in ['AGENTS.md','notes/*.md','messages/*.json','.aw/checkpoints/*.json']:
        for src in sorted(root.glob(pattern)):add(src,Path('instances')/agent/src.relative_to(root))
    for src in sorted((root/'.aw-local/inputs').glob('*.json')):
        add(src,Path('terminal-inputs')/agent/src.name,method='readonly copies of new batch inputs only; preserved completed/submitted evidence, not executable state migration; paths redacted')
for src in sorted((ROOT/'data/home/operations').glob('repair-watch-*.json')):add(src,Path('operations')/src.name)
for src in sorted((ROOT/'data/home/operations').glob('ack-repair-watch-*.json')):add(src,Path('operations')/src.name)
for src in [ROOT/'data/home/instances/repair-local/repair-alpha/.aw-local/transfer.json',ROOT/'data/home/instances/repair-local/repair-alpha/.aw-local/transfers/repair-transfer-001.json']:
    add(src,Path('terminal-transfers')/src.name,method='readonly new-batch final/archived transaction; not copied into another live data home; paths redacted')

readme='''# 修复后本机证据包

批次：2026-10-07-5aaae00-fa8c7261。软件基线5aaae00520374b022e0c38fa21f312f8e08629ba，官方登录gpt-6-luna/low。

普通boot/handoff/normal输入终态及两笔同Codex交接持久completed取得限定真实证明。不能关闭全部问题：原WorkBuddy无扩展名JS仍WinError193；Watch纠偏steer已completed但输入仍submitted，返回turnId与完成匹配的turn.id不一致。13原生轮完成，外发0，最终进程树0。

完整事实见[执行报告](reports/E2E-REPORT.md)、[最终CHECKPOINT](reports/CHECKPOINT.md)、[软件逐字节校验](reports/evidence/77-installed-fixed-source-byte-check.json)、[逐Binding/session/turn/错误审计](reports/evidence/88-final-model-input-ledger.json)、[最终进程](reports/evidence/90-final-process-audit.json)。[manifest.json](manifest.json)提供源文件与归档文件的SHA256和处理说明；SHA256SUMS覆盖manifest及全部归档文件，ZIP另有外部SHA256。

本包保持原120pass/1环境失败、单项重查、SDK24pass/5skip与补5pass、selector错误、模型checkpoint ID偏差、无效参数、sleep/轮内等待及steer残余。没有把历史失败覆盖为成功；普通链和需介入Watch分开。独立复核由Lead安排，本包不冒充复核通过。

脱敏替换仅针对机器路径和账号标识，不改事件ID、Binding/session/checkpoint、状态、原生完成顺序、业务标识与原始结果SHA256。必要的原生测试事件采用筛选日志；account/rateLimit、reasoning、流式重复事件在本机private/native-raw保留，不入仓。报告中<E2E_ROOT>/<USER_HOME>/<NODE_HOME>/<DEV_REPO>是替换标记，不是真实路径。

排除：凭据与登录文件、DPAPI vault、控制Token、未脱敏截图、旧批次运行数据、软件安装目录/可执行文件、完整源码快照与wheel、运行锁/缓存、原始完整native记录。本轮未启动带Token工作台，因此无新的控制Token日志。输入与transfer仅作为新批次只读证据，不是供导入的运行状态。

executor-scripts只供复核管理步骤，未写产品源码；不要作为自动执行入口。开发仓由Lead维护，本执行者没有提交/push/merge。可将整包归入docs/evidence/<批次>/，内部均用仓库相对链接；此说明不表示已入仓。
'''
(package/'README.md').write_text(readme,encoding='utf-8')
(package/'manifest.json').write_text('{"state":"building"}',encoding='utf-8')
machine=[];secrets=[];missing=[]
for f in package.rglob('*'):
    if not f.is_file():continue
    text=f.read_text(encoding='utf-8')
    if re.search(r'(?i)\b[A-Z]:[\\/]',text):machine.append(str(f.relative_to(package)))
    if re.search(r'#token=[A-Za-z0-9_-]{12,}|(?<![A-Za-z0-9])(?:sk-|eyJ)[A-Za-z0-9_.-]{12,}|https?://[^\s/:]+:[^\s/@]+@',text):secrets.append(str(f.relative_to(package)))
    if f.suffix=='.md':
        for link in re.findall(r'\]\(([^)]+)\)',text):
            target=link.split('#')[0].strip('<>')
            if target and '://' not in target and not (f.parent/target).exists():missing.append({'file':str(f.relative_to(package)),'target':target})
assert not machine, 'Machine paths remain in archive: '+str(machine)
assert not secrets, 'Potential credential patterns in archive file names: '+str(secrets)
assert not missing,missing
manifest={'created_at':now(),'source_commit':'5aaae00520374b022e0c38fa21f312f8e08629ba','source_archive_sha256':json.loads((ROOT/'reports/evidence/00-source-origin.json').read_text(encoding='utf-8'))['source_tar_sha256'],'files':entries,'machine_path_matches':machine,'credential_pattern_file_matches':secrets,'missing_relative_links':missing,'independent_review':'pending Lead','not_importable_runtime_state':True}
(package/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
all_files=sorted(f for f in package.rglob('*') if f.is_file())
checks=''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f.relative_to(package)).replace('\\','/')+'\n' for f in all_files)
(package/'SHA256SUMS').write_text(checks,encoding='utf-8')
for item in entries:assert hashlib.sha256((package/item['archive_file']).read_bytes()).hexdigest()==item['archive_sha256']
archive=ROOT/'shareable'/(ROOT.name+'.zip')
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
    for f in sorted(package.rglob('*')):
        if f.is_file():z.write(f,str(Path(package.name)/f.relative_to(package)).replace('\\','/'))
sha=hashlib.sha256(archive.read_bytes()).hexdigest();(archive.parent/(archive.name+'.sha256')).write_text(sha+'  '+archive.name+'\n',encoding='utf-8')
save('93-shareable-package-manifest',{'created_at':now(),'directory':str(package),'zip':str(archive),'zip_sha256':sha,'file_count':len(all_files)+1,'source_archive_entry_count':len(entries),'credential_pattern_matches':0,'machine_path_matches':0,'missing_relative_links':0,'product_source_or_old_state_changed':False,'repository_imported':False,'independent_review':'Lead owned, pending'})
print(json.dumps({'package':str(package),'zip':str(archive),'sha256':sha,'files':len(all_files)+1,'paths_or_credential_patterns':0},ensure_ascii=False))
