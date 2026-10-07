from pathlib import Path
from record import ROOT, aw, save

receiver='repair-beta';sender='repair-alpha'
receiver_task='''这是明确授权的隔离normal Watch回归，只用aw_execute，不运行Shell、外部渠道、子代理或后继。
首次boot：读取AGENTS.md，简短确认并等待，不自行stop。后续由Watch送入的两条真实normal通知：严格先处理repair-watch-001，再处理repair-watch-002；逐条message.receive形成真实ACK。
第一条：将消息ID和随机标识记入notes/watch-order.md，读取现有revision再追加，保留顺序，随后等待第二条。
第二条：先读取notes/watch-order.md与第一条记录，再追加第二消息ID/引用和随机标识；按真实revision写回。保存checkpoint.create，arguments明确checkpoint_id=repair-watch-receiver-stop，使用返回的实际id agent.stop，结束响应。两条通知是测试任务，不重放任何旧消息。
'''
aw('56-watch-receiver-create','agent.create',{'name':'修复后Watch接收实例','agent_id':receiver,'description':receiver_task,'request_id':'repair-beta-create-001'})
old=aw('57-watch-receiver-task-read','asset.read',{'agent_id':receiver,'path':'AGENTS.md'})['result']
aw('58-watch-receiver-task-save','asset.write',{'agent_id':receiver,'path':'AGENTS.md','revision':old['revision'],'content':receiver_task})
exe=str(Path.home()/'AppData/Local/OpenAI/Codex/bin/5ea220ae823df3d7/codex.exe')
aw('59-watch-receiver-configure','agent.configure-codex',{'agent_id':receiver,'model':'gpt-6-luna','effort':'low','executable':exe})
old=aw('60-watch-sender-task-read','asset.read',{'agent_id':sender,'path':'AGENTS.md'})['result']
sender_task='''这是新的隔离normal Watch发送任务，旧boot-stop/交接职责仅为历史。只用aw_execute，不运行Shell、外部渠道、子代理或新后继。
本次boot读取notes/source.md，取得真实随机标识。随后亲自message.send两条normal消息给repair-beta：第一条request_id=repair-watch-001，content包含顺序A与该随机标识；第二条request_id=repair-watch-002，content包含顺序B与同标识，message_refs=[repair-watch-001]。只发送各一次，不查询未知记录后重发。
写notes/watch-sender.md记录两个实际返回消息结果，保存checkpoint.create，arguments明确checkpoint_id=repair-watch-sender-stop，然后使用返回的实际id agent.stop并结束响应。
'''
aw('61-watch-sender-task-save','asset.write',{'agent_id':sender,'path':'AGENTS.md','revision':old['revision'],'content':sender_task})
aw('62-watch-receiver-start','agent.start',{'agent_id':receiver,'open_app':False})
print('Watch receiver boot started, sender not yet started',flush=True)
