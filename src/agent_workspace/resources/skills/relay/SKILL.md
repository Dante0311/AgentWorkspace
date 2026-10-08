---
name: relay
description: 首次进入或接手同一实例，加载必要材料，不抢占已有入口。
---

# relay

先读取 `.aw/prompts/capabilities.md` 或本次入口提示中的当前版本说明。只使用已支持的接入方式；能力未确认时先说明，不把打开窗口当成接手成功，不自动换成 CLI。

首次进入无须历史交接点；已运行实例必须已经明确 handoff。两者均不要求 Work 或共享 Definition。

```sh
aw -w sea agent start helper
aw -w sea agent start helper --open
```

本工具在尚无入口时预留唯一 binding。已捕获控制连接并准备项目的 Codex Desktop 由运行器创建、核验和绑定真实新聊天。manual 或尚未捕获连接的 Desktop 会返回手动入口提示词，用户在新原生会话中发送后，按提示绑定真实会话 ID。不要把已有/历史会话登记成新入口。Codex ID 可从真实 CODEX_THREAD_ID 取得，不编造 ID。桌面实例的平台操作使用进入材料提供的 `aw call --desktop-agent` 前缀，不能自行替换调用身份。
Desktop 自动投递需按 `.aw/prompts/entry.md` 与安装文档配置真实桌面 MCP 控制连接，不能用 exec resume 抢原生 writer。
取得资格后读取自己的 AGENTS.md、必要能力入口和给定的交接检查点/摘要。相关 Work 存在时再读，其余资料按需追溯。
没有实际任务的首次进入只简单问候，保存初始检查点，不主动分析产品、跑示例或安排 Work。
start 返回 starting/awaiting_new_session_bind 不表示已经运行。失败从实际停留步骤继续，不新造实例、不恢复已交出的旧入口。
