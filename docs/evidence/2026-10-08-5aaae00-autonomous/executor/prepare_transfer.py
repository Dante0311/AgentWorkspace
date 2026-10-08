import sys,uuid
from pathlib import Path
import record
from record import ROOT,save,now
from agent_workspace.harness_config import sdk_config
record.WORKSPACE='transfer-local'
aw=record.aw
model=sys.argv[1]
effort=sys.argv[2] if len(sys.argv)>2 else ''
exe=Path.home()/'AppData/Roaming/npm/node_modules/@tencent/tclaude/node_modules/@tencent/tclaude-win32-x64/tclaude.exe'
sdk_config('claude',model=model,effort=effort,executable=str(exe))
save('70-transfer-authorized-profile',{'time':now(),'model':model,'effort':effort,'native_executable':str(exe),'route':'same tclaude native exe via platform ClaudeSDKClient','authorization':'Lead relays direct human model selection; not inferred from catalog','base_url_override':False,'auth_copied':False})
aw('71-transfer-workspace','workspace.init',{'name':record.WORKSPACE,'directory':str(ROOT/'data/transfer.git')})
token=uuid.uuid4().hex
save('72-transfer-marker',{'marker':token})
task='''这是明确授权的同一实例 Codex→tclaude 真实交接验收。仅用 aw_execute 平台工具；禁止 Shell、原生Read/Write、sleep、轮询、.aw-local、外部渠道、子代理、后继。
读取 AGENTS.md 与 notes/source.md。根据当前入口提示中的 runtime_kind 区分阶段，不能根据名字猜身份：
1. 首次 runtime_kind=codex boot：读取随机标识，写 notes/codex-origin.md 记录实际标识与本入口 Binding，然后立即简短 final 结束轮，不自行stop。仅等待平台明确handoff请求。
2. 明确handoff输入：checkpoint.create 保存本次真实资产，agent.stop 使用实际返回 checkpoint id，简短 final。不要创建后继，平台自动接续。
3. 后继 runtime_kind=claude boot：读取入口提供的真实交接检查点、notes/codex-origin.md 与 notes/source.md；确认相同标识，写 notes/tclaude-relay.md，记录读取的实际检查点ID、旧Codex资产标识与当前新Binding。立即简短 final 结束轮，不stop、不sleep、不提前receive。平台稍后开启Watch并送入消息。
4. 仅收到真实 normal Watch 通知 aw-transfer-message-001：本人 message.receive 形成ACK；读取 notes/tclaude-relay.md 与实际消息，核对同一标识，写 notes/tclaude-message.md，checkpoint.create，agent.stop 用真实返回 checkpoint id，立即简短 final。失败保留实际结果，不重试发送、不自助新增轮或后继。
'''
peer_task='''这是隔离交接后的单次真实Message测试，只有当前boot一轮。只用aw_execute；禁止Shell、sleep、轮询、.aw-local、其他渠道、子代理、后继。读AGENTS.md与notes/source.md；本人message.send给transfer-agent，delivery=normal、request_id=aw-transfer-message-001，内容包含真实随机标识。只发一次，不等ACK或重发。记录notes/transfer-sender.md，checkpoint.create，agent.stop使用真实返回checkpoint id，简短final。
'''
codex=Path.home()/'AppData/Local/OpenAI/Codex/bin/9691020b546a15b2/codex.exe'
for i,(aid,instructions) in enumerate((('transfer-agent',task),('transfer-peer',peer_task))):
    aw(f'73-{i}-create','agent.create',{'name':aid,'agent_id':aid,'description':'明确授权的隔离同身份自动交接/真实消息测试','request_id':aid+'-create'})
    old=aw(f'74-{i}-read','asset.read',{'agent_id':aid,'path':'AGENTS.md'})['result']
    aw(f'75-{i}-task','asset.write',{'agent_id':aid,'path':'AGENTS.md','revision':old['revision'],'content':instructions})
    aw(f'76-{i}-source','asset.write',{'agent_id':aid,'path':'notes/source.md','revision':None,'content':'random marker: '+token+'\n'})
    aw(f'77-{i}-codex','agent.configure-codex',{'agent_id':aid,'model':'gpt-6-luna','effort':'low','executable':str(codex)})
aw('78-transfer-codex-start','agent.start',{'agent_id':'transfer-agent','open_app':False})
print('initial Codex boot started; no transfer/peer launched yet',flush=True)
