---
name: relay
description: 首次进入或接手同一 Agent，加载必要材料，不抢占已有入口。
---

# relay

先读取 `.agentworkspace/prompts/capabilities.md` 或本次入口提示中的当前版本说明。只使用已支持的接入方式；能力未确认时先说明，不把打开窗口当成接手成功，不自动换成 CLI。

首次进入无须历史交接点；已运行 Agent 必须已有明确交接点。正常交接由 handoff 保存并释放资格；用户强制接手由 agent takeover 撤销旧资格，并保留旧聊天是否停止尚未观测的事实。两者均不要求 Work 或共享 Definition。

```sh
aw -w sea agent start helper
aw -w sea agent start helper --open
```

本工具在尚无入口时预留唯一 binding。已捕获控制连接并准备项目的 Codex Desktop 由运行器创建、核验和绑定真实新聊天。manual 或尚未捕获连接的 Desktop 会返回手动入口提示词，用户在新原生会话中发送后，按提示绑定真实会话 ID。不要把已有/历史会话登记成新入口。Codex ID 可从真实 CODEX_THREAD_ID 取得，不编造 ID。桌面 Agent 的平台操作使用进入材料提供的 `aw call --desktop-agent` 前缀，不能自行替换调用身份。

进入沿用同一 Agent 和实例分支。先由公共准备操作核对本机资料副本；支持 worktree 的版本在 Workspace 内自动准备或复用，缺少时由工具取得分支并创建，不把手动 clone 或建目录交给用户作为前置步骤。Workspace 尚未接入时，使用已经明确的访问地址和权限接入；缺失的是访问条件才询问。当前安装尚未提供自动准备时如实说明限制，不强制覆盖旧目录或假报成功。

一次有效执行入口由当前 Binding 指向具体原生会话，目录存在、项目相同、历史聊天可打开或本地状态文件仍在都不能代替当前资格。使用用户已选的独立或共用项目；用户已在新聊天发起 relay 时绑定这条真实会话，不额外创建第二条。强制接手后也必须核验新会话，不能把尚在运行的旧聊天重新绑定。
Desktop 自动投递需按 `.agentworkspace/prompts/entry.md` 与安装文档配置真实桌面 MCP 控制连接，不能用 exec resume 抢原生 writer。
取得资格后按本次进入材料的明确路径读取自己的 AGENTS.md、必要 Skill 和给定的交接检查点/摘要，确认所属 Workspace、Agent、实例分支、个人资料根、本次实际 cwd 与工作位置。先恢复身份和职责，再接续任务、已做工作、决定和下一步；相关 Work 存在时再读。跨机器使用本机重新解析的路径，旧路径只说明来源，不复用旧 Binding。共同项目不会自动加载所有成员的私人 Skills，按进入材料读取自己的入口，其余资料按需追溯。
检查点中旧入口的“本轮 renew”“下一步 stop”等安排属于旧入口的交出过程，不自动成为新入口的停工任务。只接续明确交给本入口的未完成业务，不重复已完成的控制动作。
完成接手、保存检查点或结束当前轮次，都不释放当前执行资格；没有明确安排给本入口的停工或交出任务时，保留入口等待后续输入，不调用 agent.stop。需要正式交出时再按 handoff Skill 执行。
没有实际任务的首次进入只简单问候，保存初始检查点，不主动分析产品、跑示例或安排 Work。
start 返回 starting/awaiting_new_session_bind 不表示已经运行。失败从实际停留步骤继续，不新造实例、不恢复已交出的旧入口。

新会话仍须读取 AGENTS.md 中 @workspace-read 的共同资料；使用当次进入材料给出的同一共享 revision。旧检查点的摘要不代替本次共同职责正文，读取失败要报告。
