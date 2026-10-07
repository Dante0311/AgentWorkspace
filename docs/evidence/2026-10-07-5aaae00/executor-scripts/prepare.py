import json
from pathlib import Path
import secrets
from record import ROOT, HOME, WORKSPACE, aw, save

agent = 'repair-alpha'
aw('11-workspace-init','workspace.init',{'name':WORKSPACE,'directory':str(ROOT/'data/workspace.git')})
task = '''这是用户明确授权的隔离修复验收任务。只使用 aw_execute 平台工具，不运行 Shell、联网、外部渠道或子代理。
每次正常 boot：asset.read 读取 AGENTS.md 和 notes/source.md，在 notes/boot-<当前binding>.md 写下本次绑定和读到的随机标识，然后简短确认并等待输入，不自行创建后继、不自行停止。
收到平台正式 handoff 请求：保存真实 checkpoint，调用 agent.stop，结束响应；不得访问 .aw-local。
收到后续明确收尾指令：严格使用该指令给出的结果路径与 checkpoint_id，读取真实源资产、写验证结果、checkpoint.create、agent.stop。只报告实际已返回的结果。管理端核对真实完成/释放，你不需要读取受保护账本。
这是全新独立批次，不执行旧批次或生产业务。
'''
aw('12-alpha-create','agent.create',{'name':'修复后交接验收','agent_id':agent,'description':task,'request_id':'repair-alpha-create-001'})
current=aw('13-alpha-AGENTS-read','asset.read',{'agent_id':agent,'path':'AGENTS.md'})['result']
aw('14-alpha-task-save','asset.write',{'agent_id':agent,'path':'AGENTS.md','content':task,'revision':current['revision']})
marker=secrets.token_hex(16)
aw('15-new-source-asset','asset.write',{'agent_id':agent,'path':'notes/source.md','content':'修复后随机标识：'+marker+'\n本文件仅为新批次隔离验收资产。'})
exe=str(Path.home()/'AppData/Local/OpenAI/Codex/bin/5ea220ae823df3d7/codex.exe')
aw('16-configure-luna','agent.configure-codex',{'agent_id':agent,'model':'gpt-6-luna','effort':'low','executable':exe})
save('17-test-identity',{'workspace':WORKSPACE,'agent':agent,'marker':marker,'root':str(HOME/'instances'/WORKSPACE/agent),'request_prefix':'repair-','old_state_copied':False})
aw('18-first-start','agent.start',{'agent_id':agent,'open_app':False})
