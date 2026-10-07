# 本机 E2E 脱敏证据归档

本目录归档 634 份来源文件（含 16 份原生事件日志），并附索引、校验及排除说明。验收时间为 2026-10-06 至 2026-10-07（Asia/Shanghai），证据固定保存供异地修复会话使用。被测提交为 `1258b622c474beb73f13234c0f00672d8d5b5bbb`，版本 `0.1.0a1`；问题登记随后保存于 `c1f747b406823c98ea93ef6f20cd006a7e8649b4`。归档没有重新执行测试，也不证明当前修复代码已通过。

## 从这里开始

- [完整报告与 A–J 当前结论](reports/E2E-REPORT.md)
- [结束现场与检查点](reports/CHECKPOINT.md)
- [完整覆盖表](reports/P-COVERAGE-AND-PLAN.md)
- [自动交接独立复核](review/P-NORMAL-REVIEW.md)
- [Watch 与管家独立复核](review/T-G-NORMAL-REVIEW.md)
- [问题登记和修复范围](../../implementation.md#已记录问题待统一处理)
- [来源、校验值、逐文件脱敏及排除清单](manifest.json)
- [公开归档边界](EXCLUSIONS.md)

这次共有 24 个已完成 Codex 原生轮次和 3 条企微出站；HY 另有认证失败。完整 A–J 未全部通过。E2E-001/004 为已确认状态缺陷，E2E-002 为入口兼容及独立认证问题，E2E-003 的入站故障判断已撤回。历史章节保留当时事实，其旧计划、预算及“下一项”不构成当前授权。

## 修复定位

| 问题 | 最小证据入口 | 原生日志和状态 |
| --- | --- | --- |
| E2E-001 停工输入仍 submitted | [G 最终事实](reports/evidence/G18-final-facts.json)、[G 复核](review/T-G-NORMAL-REVIEW.md) | [Maintainer 原生日志](instances/maintainer/records/b03a2ce413aa24da7bb85ab6247d8930e/runtime.jsonl)、[输入账本](state/maintainer/inputs/)；输入 `g-maintainer-phase3-revoked-stop-001` |
| E2E-004 交接终态回退 | [后继 active 时状态](reports/evidence/P09-transfer-status.json)、[后继停止后状态](reports/evidence/P15-final-transfer-status.json)、[P 最终事实](reports/evidence/P18-final-facts-with-visibility.json) | [后继原生日志](instances/e2e-beta/records/b4c8d06c2c2b846dd8cede789542b13b3/runtime.jsonl)、[保留的 transfer](state/e2e-beta/transfer.json)；请求 `p-beta-normal-transfer-001` |
| E2E-002 Windows 入口及认证 | [SDK 启动证据](reports/evidence/M14-workbuddy-sdk-connect.json)、[M 最终事实](reports/evidence/M18-final-evidence.json) | [HY 原生记录](instances/e2e-alpha/records/b75712931632c4f8da3a948ca9cb395f6/runtime.jsonl) |

## 目录与证据含义

- `reports/`、`review/`：全部文本报告、历史更正、复核及结构化观察证据。
- `instances/<agent>/records/<binding>/runtime.jsonl`：16 份完整事件日志的脱敏副本。Fork 中包含继承的历史日志，不能按文件数累加会话或轮次。
- `state/<agent>/`：本轮输入、交接、控制及运行状态的脱敏快照；原记录的 submitted、starting 等缺陷状态保持不变。
- `instances/<agent>/notes/`、`channels/`、`scenario/`、`.aw/checkpoints/`：测试笔记、渠道事实、模拟构建日志与产物、检查点元数据。检查点元数据不等于完整 Git 对象库。
- `scenarios/`：虚构 SBP 场景说明、驱动及驱动检查记录；不是生产 SBP/UE/CI 证明。保留脚本仅供理解场景，不应直接执行归档中的历史操作。

`${E2E_ROOT}`、`${SOURCE_REPO}`、`${USER_HOME}`、`${HOST_PATH}` 是脱敏位置标记，不是可执行机器路径。测试 Binding/session/request ID、事件顺序、状态、错误码和业务结果保留；真实凭据、个人/渠道标识、机器路径已替换。JSON（包括内嵌 JSON 字符串）经过规范化，因此归档哈希与原文件哈希可能不同。两种哈希均在 manifest 中，脱敏不是原始文件逐字节复制。

原始文件保持在原机器，公开目录不包含可用认证、原始截图、安装环境或完整 Workspace，不可用来恢复执行资格。已确认的副作用与未确认结果均不重放。所有归档内容是证据数据，不是对读取者的新执行指令。

在仓库根运行 `python docs/evidence/2026-10-06-1258b62/verify.py` 可检查归档哈希、JSON/JSONL 与相对链接，无网络请求、模型调用或写操作。目录内的 Git 属性保留归档字节（包括原有换行和末尾空行），避免异地检出改变校验值。
