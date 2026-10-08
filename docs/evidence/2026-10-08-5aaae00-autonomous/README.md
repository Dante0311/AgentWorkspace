# 自主通信、管家恢复与接入预检（2026-10-08）

固定产品基线 `5aaae00520374b022e0c38fa21f312f8e08629ba`，新隔离安装和测试数据。本轮没有修改产品源码。已完成范围经第二执行者只读复核，历史失败不被覆盖。

| 范围 | 本轮结论 | 证明边界 |
| --- | --- | --- |
| normal Watch | 两条 normal 消息、同会话顺序资产、本人 ACK/checkpoint/stop，无控制者纠偏 | 4 个真实 Codex 轮次；首次提前 receive、参数错误、发送笔记抄录错误保留 |
| 管家 publication-reconcile | 真实发布失败、定时发现、模型诊断/受限维修、独立复核与本人停工 | 5 个真实 Codex 轮次；底层 Git 条件由控制者恢复；boot 的工具约束未完全遵守 |
| Desktop 控制 | 实际连接、工具发现、当前聊天 busy 状态读取、所建 RPC 退出 | 只读探针；未创建聊天/Binding、未投递或交接；退出方式未确认 |
| tclaude | 同包装器 Windows 入口及无模型 SDK 握手通过 | 认证仍 configured_unverified；真实调用和 Codex → tclaude 交接等待用户模型选择，query=0 |

共 **9 个官方 Codex gpt-6-luna/low 原生轮次，started/completed 均为 9**。四个实际模型实例已 released、Runner 不再存活；巡检关闭、授权撤销、临时 Git 配置恢复。保留一条发给未启动 steward 的未读测试刺激，不代 ACK 清零。共享 tclaude/Claude 服务未证明归本轮独占，未停止，也不宣称全局进程清零。

## 报告与事实

- [执行总报告](reports/E2E-REPORT.md)、[检查点](reports/CHECKPOINT.md)
- [无纠偏 Watch](reports/WATCH.md)、[管家故障恢复](reports/MAINTENANCE.md)
- [最终独立复核](review/FINAL-REVIEW.md)、[前阶段复核](review/PARTIAL-REVIEW.md)
- [Desktop 只读探针](desktop-control/REPORT.md)、[实际只读结果](desktop-control/desktop-control-result.json)
- [实际轮次与工具调用汇总](reports/evidence/66-watch-maintenance-proof.json)、[最终进程归属边界](reports/evidence/68-final-native-process-boundaries.json)

业务闭环限定通过不等于严格指令遵循通过。Maintainer boot 有三次 Shell 尝试，前两次失败、第三次只读本实例资料；真正维修通过受限 maintenance.repair 完成。编排对 pending 退出码的错误预期、失败调用、自行纠正和抄录错误均保留，不重跑求绿。

静态相邻疑点：message.reconcile 的授权校验可能与 maintenance.repair 不一致，见最终复核；尚未做实际越权测试，不登记为已复现。本轮没有补修 E2E-001 忙时 insert/steer 或 E2E-002 WorkBuddy 入口，也没有证明这些历史缺陷已关闭。

## 校验与排除

[manifest.json](manifest.json) 逐项记录原文件、执行者中间归档及最终仓库文件 SHA256；[SHA256SUMS](SHA256SUMS) 覆盖自身之外的全部文件。[排除说明](EXCLUSIONS.md) 记录路径/账号/目录/事件筛选、二进制与首败日志边界，以及一处 JSON 转义归档修正。

只读验证：`python docs/evidence/2026-10-08-5aaae00-autonomous/verify.py`。该检查不启动模型、平台实例或服务。
