---
name: relay
description: 首次进入或接手同一实例，加载必要材料，不抢占已有入口。
---

# relay

首次进入无须历史交接点；已运行实例必须已经明确 handoff。两者均不要求 Work 或共享 Definition。

```sh
aw -w sea agent start helper
aw -w sea agent start helper --open
```

本工具在尚无入口时预留唯一 binding。Desktop/manual 会返回新会话入口提示词，用户在新原生会话中发送后，按提示绑定真实会话 ID。不要把已有/历史会话登记成新入口。Codex ID 可从真实 CODEX_THREAD_ID 取得，不编造 ID。
Desktop 自动投递需按 `.aw/prompts/entry.md` 与安装文档配置真实桌面 MCP 控制连接，不能用 exec resume 抢原生 writer。
取得资格后读取自己的 AGENTS.md、必要能力入口和给定的交接检查点/摘要。相关 Work 存在时再读，其余资料按需追溯。
没有实际任务的首次进入只简单问候，保存初始检查点，不主动分析产品、跑示例或安排 Work。
start 返回 starting/awaiting_new_session_bind 不表示已经运行。失败从实际停留步骤继续，不新造实例、不恢复已交出的旧入口。
