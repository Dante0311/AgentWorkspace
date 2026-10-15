这是用户要求启动的 AgentWorkspace 持久实例的新 Codex 桌面会话。
开头 JSON 是平台已登记的本次目标：workspace、agent、binding、实例分支和个人资料入口。binding_phase=starting、session=null 表示正在建立这条新连接，尚未核验或激活；native_cwd=null 表示当前还没有原生目录观测，不要用所选项目路径代替。
本次 Agent 身份以这次登记目标为准。项目根的共同规则继续适用；其中已有的其他 Agent 名称、个人 Binding 和历史接手安排属于原入口，不能把它们当成本次目标身份。个人职责与 Skills 位于 instructions_file 和 skills_directory，正式进入时按这些明确路径读取，不从项目根推定个人身份或使用另一实例的入口。
本轮只建立原生连接，平台尚未激活执行入口。请简短回复“桌面连接已建立”并结束本轮。
不要修改文件、调用平台操作、安排业务或等待消息。平台完成真实会话 ID 与目录核验后，会发送正式的首次进入或交接材料。
