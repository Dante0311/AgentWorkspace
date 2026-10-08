import time
from pathlib import Path
import record
from record import ROOT,HOME,save,now
record.WORKSPACE='maintenance-local'
aw=record.aw
EXE=Path.home()/'AppData/Local/OpenAI/Codex/bin/9691020b546a15b2/codex.exe'
aw('30-maint-workspace-create','workspace.init',{'name':record.WORKSPACE,'directory':str(ROOT/'data/maintenance.git')})
sentinel_task='''这是明确授权的隔离管家真实故障恢复验收。只用 aw_execute；禁止 Shell、sleep、轮询、.aw-local、其他渠道、子代理、后继。
本次首次 boot：只读 AGENTS.md，简短 final 结束当前轮。不主动诊断、发消息或 stop。后续由平台真实定时巡检输入及 Watch 通知触发。
收到巡检输入：读取 maintenance.status、workspace.doctor。只有真实 issue code=publication_pending、operation=aw-maint-fault-001 时，亲自 message.send 给 maintainer，delivery=normal、request_id=aw-maint-task-001，说明对发送者 sentinel 的原操作执行 maintenance.repair action=publication-reconcile，operation_id=aw-maint-fault-001、request_id=aw-maint-repair-001，只此一项，不重发原消息、不修 OS/Git 权限。随后立即简短 final，禁止等回复或轮询。
收到 Watch 通知 aw-maint-result-001：本人 message.receive 形成 ACK；读取 message.operation aw-maint-fault-001 和一次新的 workspace.doctor，独立核对原操作 published、目标 publication_pending 消失。写 notes/maintenance-verification.md 如实记录；checkpoint.create，然后 agent.stop 使用真实返回 checkpoint id，简短 final。异常保存真实结果 final，不新开轮或重复副作用。
'''
maintainer_task='''这是明确授权的隔离管家维修验收。只用 aw_execute；禁止 Shell、sleep、轮询、.aw-local、其他渠道、子代理、后继。
首次 boot：只读 AGENTS.md，简短 final 结束当前轮；不提前修复、收消息或 stop。
收到真实 Watch 通知 aw-maint-task-001：本人 message.receive 形成 ACK；读取 message.operation aw-maint-fault-001 和 workspace.doctor；仅对真实待补齐原操作调用 maintenance.repair，agent_id=sentinel、action=publication-reconcile、operation_id=aw-maint-fault-001、request_id=aw-maint-repair-001。不调用 message.reconcile、不重发原消息、不处理其他问题。
区分 repair.state=applied 与 result.state=published，再读取原 message.operation 和一次新的 workspace.doctor；如实记录 notes/maintenance-repair.md，报告目标 publication_pending 是否消失。亲自 message.send 给 sentinel，delivery=normal、request_id=aw-maint-result-001，message_refs=[aw-maint-task-001]，只发一次，正文记录实际结果和局限。checkpoint.create，然后 agent.stop 使用真实 checkpoint id，立即简短 final。
'''
for i,(aid,task) in enumerate((('sentinel',sentinel_task),('maintainer',maintainer_task))):
    old=aw(f'31-{i}-task-read','asset.read',{'agent_id':aid,'path':'AGENTS.md'})['result']
    aw(f'32-{i}-task-write','asset.write',{'agent_id':aid,'path':'AGENTS.md','revision':old['revision'],'content':task})
    aw(f'33-{i}-configure','agent.configure-codex',{'agent_id':aid,'model':'gpt-6-luna','effort':'low','executable':str(EXE)})
aw('34-maint-grant','maintenance.grant',{'agent_id':'maintainer','commands':['maintenance.repair'],'targets':['sentinel']})
for i,aid in enumerate(('sentinel','maintainer')):
    aw(f'35-{i}-start','agent.start',{'agent_id':aid,'open_app':False})
print('caretaker boots started; fault not injected',flush=True)
