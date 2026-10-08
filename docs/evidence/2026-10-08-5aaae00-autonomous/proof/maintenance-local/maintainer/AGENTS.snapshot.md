这是明确授权的隔离管家维修验收。只用 aw_execute；禁止 Shell、sleep、轮询、.aw-local、其他渠道、子代理、后继。
首次 boot：只读 AGENTS.md，简短 final 结束当前轮；不提前修复、收消息或 stop。
收到真实 Watch 通知 aw-maint-task-001：本人 message.receive 形成 ACK；读取 message.operation aw-maint-fault-001 和 workspace.doctor；仅对真实待补齐原操作调用 maintenance.repair，agent_id=sentinel、action=publication-reconcile、operation_id=aw-maint-fault-001、request_id=aw-maint-repair-001。不调用 message.reconcile、不重发原消息、不处理其他问题。
区分 repair.state=applied 与 result.state=published，再读取原 message.operation 和一次新的 workspace.doctor；如实记录 notes/maintenance-repair.md，报告目标 publication_pending 是否消失。亲自 message.send 给 sentinel，delivery=normal、request_id=aw-maint-result-001，message_refs=[aw-maint-task-001]，只发一次，正文记录实际结果和局限。checkpoint.create，然后 agent.stop 使用真实 checkpoint id，立即简短 final。
