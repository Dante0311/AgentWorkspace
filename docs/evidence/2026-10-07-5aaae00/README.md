# 修复后 Windows 真实定向验收

2026-10-07，批次 `2026-10-07-5aaae00-fa8c7261`。产品基线为已合并 PR #11 的 `5aaae00520374b022e0c38fa21f312f8e08629ba`；本批只测试和归档，没有修改产品源码。新隔离安装及新数据，官方登录 `gpt-6-luna/low`。

**结论：E2E-004 在本轮范围通过；E2E-001 普通停工通过但 busy insert/steer 仍有残余；E2E-002 实际 WorkBuddy 入口仍启动失败。** 不能把本批写成全部修复通过。

| 项目 | 实际结果 |
| --- | --- |
| E2E-004 | 两次同 Codex 自动交接在首次状态查询前已把 `completed`/session 写入磁盘；后继停工后保持终态，旧 ID 原结果和归档可读，新交接成功。 |
| E2E-001 普通路径 | boot/handoff/normal 完成事件、输入终态、显式检查点及释放一致；boot 自停复用显式检查点。 |
| E2E-001 busy insert 残余 | 一次真实 steer 返回顶层 `result.turnId`，完成收口只读 `result.turn.id`；匹配原生轮次已 completed，输入仍 submitted。idle 时走 turn/start 的 insert 不属于这个失败分支。 |
| E2E-002 | 原选 `resources/app.asar.unpacked/cli/bin/codebuddy` 是无扩展名 JS，未进入只识别 `.js/.cjs/.mjs` 的 Node 适配，实际 SDK connect 仍 WinError 193。控制握手及认证未到达，HY 业务未运行。 |
| Watch | 两消息、两 ACK、同 session 顺序资产及双方停工成立；第一通知轮经一次管理端 steer 澄清才结束，不能称无人介入自然流程完整通过。 |
| 收尾 | 13/13 原生轮次完成；12 个输入中 11 completed、1 submitted。两个测试实例 released，Runner 退出，最终进程审计无残留。外部业务消息为 0。 |

完整材料：

- [执行报告](reports/E2E-REPORT.md)与[最终检查点](reports/CHECKPOINT.md)：所有阶段、实际操作、ID、偏差、测试与未测项。
- [最终独立复核](review/FINAL-REVIEW.md)：从原始事件、输入、共享 Git、资产及源码核对结论，含两项残余的触发条件、影响、位置与修复边界；[静态预审](review/PREFLIGHT-REVIEW.md)保留当时结论。
- [逐轮与输入审计](reports/evidence/88-final-model-input-ledger.json)、[steer 终态不一致](reports/evidence/87-steer-terminal-ledger-mismatch.json)、[WorkBuddy 原入口失败](reports/evidence/24-workbuddy-real-js-control.json)、[Watch 介入记录](reports/evidence/84-watch-control-intervention-boundary.json)、[最终进程](reports/evidence/90-final-process-audit.json)。
- [测试计数](reports/evidence/91-final-test-accounting.json)：121 项首跑 120 passed / 1 环境导入失败，安装同一 wheel 后仅原失败项 1 passed；SDK 首跑 24 passed / 5 缺依赖 skipped，固定依赖补齐后仅原 5 项 5 passed。selector 错误零执行也保留，不能写成全部首跑无错。
- [源码来源](reports/evidence/00-source-origin.json)、[wheel 摘要](reports/evidence/05-wheel-origin.json)、[安装文件核对](reports/evidence/77-installed-fixed-source-byte-check.json)。

执行报告形成于独立复核之前，其中“复核待完成”“执行方未提交”等是报告保存时的事实；当前复核结果以本入口链接的最终复核为准。没有改写这些历史表述或原失败日志。

## 校验与隐私

[manifest.json](manifest.json)为每个来源文件保存原始及归档 SHA256、字节数、处理方式；原生事件筛选条目另列保留事件数和排除的方法计数。Lead 入仓前验证原证据包的 172 个来源/副本摘要，再加入两份独立复核。机器名以 `[TEST_HOST]` 替换；五份 JUnit 从未改动的原文件按 XML 字段脱敏、重新序列化，避免替换标记破坏 XML，测试结果保持原值。

[SHA256SUMS](SHA256SUMS)覆盖自身之外的全部归档文件，包含 manifest、说明和校验程序；`.gitattributes` 保留提交字节。可在仓库根执行以下只读校验，不启动模型、产品服务或测试实例：

```sh
python docs/evidence/2026-10-07-5aaae00/verify.py
```

[排除与脱敏说明](EXCLUSIONS.md)区分完整报告、筛选后的原生诊断事件及本机保留材料。`executor-scripts/` 是执行者管理步骤的脱敏记录，仅供审查，不是产品入口或可直接重跑的测试包。输入和 transfer 是新批次只读证据，不供导入运行状态。入仓副本不含真实凭据、私人会话、机器路径、未脱敏截图、软件安装目录或运行锁。

本轮未重跑完整 A–J、六向 Harness 矩阵、Desktop、企微、自有模型服务、生产 UE/CI、远端 Git 业务或长期运行；不沿用旧批次证明这些能力。旧失败与后续修复验证分别保存：[1258b62 原验收](../2026-10-06-1258b62/README.md)、[PR #11 开发回归](../2026-10-07-e2e-fixes/README.md)。当前实现登记见[实现进展](../../implementation.md)。
