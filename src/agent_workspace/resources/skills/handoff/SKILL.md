---
name: handoff
description: 保存实际工作事实，交出当前实例的执行权，不启动下一端。
---

# handoff

本操作只能由当前入口执行。不要把停止 watch、窗口关闭或单次停止生成当作交出。

1. 如实整理当前事实、累计摘要与未决结果，不替使用者决定哪些业务必须继续或放弃。
2. 保存当前需要接续的资料；外部文件、产品版本、未取得的原始记录写明范围。
3. 调用 checkpoint.create，保存确定版本。方法参见 `.aw/prompts/checkpoints.md`。
4. 调用 agent.stop，提供本入口 binding 和检查点。
5. 返回简短交出准备结果并结束当前 turn；不要在请求停工后继续执行业务。运行器观察原生入口 idle 后才发布交接点并释放资格。

```sh
aw -w sea checkpoint create helper --binding BINDING --summary "累计摘要" --content "阶段事实及不确定性"
aw -w sea agent stop helper --binding BINDING --checkpoint CHECKPOINT_ID
```

manual 入口仅由当前使用者明确确认已停止后，加 --confirm-stopped；这不是物理隔离证明，也不允许他人强制接管。
单独 handoff 不启动新入口。工作台换新会话是显式组合，后半段由运行器负责。
