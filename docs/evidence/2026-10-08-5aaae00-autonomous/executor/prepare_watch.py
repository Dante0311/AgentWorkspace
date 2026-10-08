import hashlib, json, uuid
from pathlib import Path
from record import ROOT, HOME, aw, run, save, now

EXE=Path.home()/'AppData/Local/OpenAI/Codex/bin/9691020b546a15b2/codex.exe'
run('00-codex-login',[EXE,'login','status'])
save('01-baseline',{'time':now(),'commit':'5aaae00520374b022e0c38fa21f312f8e08629ba','root':str(ROOT),'home':str(HOME),'aw':str(ROOT/'app/Scripts/aw.exe'),'wheel_sha256':hashlib.sha256((ROOT/'dist/git_native_agent_workspace-0.1.0a1-py3-none-any.whl').read_bytes()).hexdigest(),'codex_executable':str(EXE),'codex_sha256':hashlib.sha256(EXE.read_bytes()).hexdigest(),'model':'gpt-6-luna','effort':'low'})
aw('02-workspace-create','workspace.init',{'name':'watch-local','directory':str(ROOT/'data/watch.git')})
token=uuid.uuid4().hex
save('03-random-marker',{'marker':token})
receiver='watch-beta';sender='watch-alpha'
receiver_task='''这是明确授权的隔离 normal Watch 测试。只用 aw_execute；禁止 Shell、sleep、轮询、读取 .aw-local、其他渠道、子代理、后继。
首次 boot 读取 AGENTS.md，简短 final 结束当前轮，不 stop，不等待工具或 sleep；让 Runner 后续交付通知。
仅处理两条真实 normal Watch 通知，按消息 aw-watch-001、aw-watch-002 顺序，逐条 message.receive 形成真实 ACK。不要提前接收第二条。
第一条通知：message.receive aw-watch-001；asset.read notes/watch-order.md（不存在时按新文件）；记录 A、真实 message_id、内容中的随机标识。asset.write 使用真实返回 revision，新文件 revision=null。随后立即用简短 final 结束当前轮。禁止等待第二条、sleep、agent.show 轮询。
第二条通知：message.receive aw-watch-002；asset.read notes/watch-order.md，保留 A 并追加 B、真实 message_id、message_refs 与随机标识；使用真实 revision 写回。checkpoint.create 保存真实结果，然后 agent.stop（checkpoint 参数使用返回的真实 id，身份自动注入）；简短 final 结束当前轮。
异常时如实记录并 final，不重试发送、不请求自助新轮。
'''
sender_task='''这是明确授权的隔离 normal Watch 发送测试。只用 aw_execute；禁止 Shell、sleep、轮询、读取 .aw-local、其他渠道、子代理、后继。
本次 boot 读取 AGENTS.md、notes/source.md；亲自发送两条 normal Message 给 watch-beta，各发送一次：第一条 request_id=aw-watch-001，内容包含 A 和 source 中随机标识；第二条 request_id=aw-watch-002，内容包含 B 和相同标识，message_refs=[aw-watch-001]。不要读取接收方或代它 ACK。
asset.write notes/watch-sender.md 保存实际发送返回结果。checkpoint.create 保存本次结果，然后 agent.stop（checkpoint 使用返回真实 id，身份自动注入），简短 final 结束当前轮。不等待 ACK、不重试发送。
'''
for i,(aid,task) in enumerate(((receiver,receiver_task),(sender,sender_task))):
    aw(f'04-{i}-create','agent.create',{'name':aid,'agent_id':aid,'description':'隔离正常Watch验收','request_id':aid+'-create'})
    old=aw(f'05-{i}-task-read','asset.read',{'agent_id':aid,'path':'AGENTS.md'})['result']
    aw(f'06-{i}-task-write','asset.write',{'agent_id':aid,'path':'AGENTS.md','revision':old['revision'],'content':task})
    aw(f'07-{i}-configure','agent.configure-codex',{'agent_id':aid,'model':'gpt-6-luna','effort':'low','executable':str(EXE)})
aw('08-source-write','asset.write',{'agent_id':sender,'path':'notes/source.md','revision':None,'content':'random marker: '+token+'\n'})
aw('09-receiver-start','agent.start',{'agent_id':receiver,'open_app':False})
print('receiver boot started; sender not started')
