---
name: handoff
description: 保存实际工作事实，交出当前 Agent 的执行权，不启动下一端。
---

# handoff

本操作只能由当前入口执行。不要把停止 watch、窗口关闭或单次停止生成当作交出。
只有明确安排给当前入口的停工或交出任务才执行以下步骤。读取本 Skill、handoff 操作说明或旧检查点，不会产生新的停工安排；完成接手、保存检查点和结束当前轮次也不代表要交出入口。

1. 如实整理当前事实、累计摘要与未决结果，不替使用者决定哪些业务必须继续或放弃。
2. 保存当前需要接续的资料；外部文件、产品版本、未取得的原始记录写明范围。
3. 调用 checkpoint.create，保存确定版本。方法参见 `.agentworkspace/prompts/checkpoints.md`。
4. 调用 agent.stop，提供本入口 binding 和检查点。
5. 返回简短交出准备结果并结束当前 turn；不要在请求停工后继续执行业务。运行器观察原生入口 idle 后才发布交接点并释放资格。

```sh
aw -w sea checkpoint create helper --binding BINDING --summary "累计摘要" --content "阶段事实及不确定性"
aw -w sea agent stop helper --binding BINDING --checkpoint CHECKPOINT_ID
```

manual 入口仅由当前使用者明确确认已停止后，加 --confirm-stopped；这不是平台观测到原生进程退出的证明，他人不能代替当前使用者作停工确认。
单独 handoff 不启动新入口。用户通过 CLI、Skills 或原生客户端明确请求换新会话时，才组合交出与接续，后半段由运行器负责。

用户强制接手另用 agent takeover，明确选择当前 Binding 和已保存检查点并确认撤销执行资格，不能冒充正常停工。只有用户管理入口可以执行；它保留原生状态未观测、旧聊天可能仍运行的事实，也不迁移未保存资料或自动启动下一端。后续进入仍是同一持久 Agent 的新会话，原聊天与本地副本保留在历史中。
