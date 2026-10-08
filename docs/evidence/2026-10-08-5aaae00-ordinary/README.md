# 普通原生会话：用户配合实机验收

2026-10-08，AgentWorkspace 固定基线 `5aaae00520374b022e0c38fa21f312f8e08629ba`；当前真实 Codex CLI `0.162.0-alpha.2`，既有 ChatGPT 登录、配置及界面显示 `gpt-6-luna / low`。本批使用新的空 ordinary-home 和虚构产品目录，没有修改产品源码。

**C 组所测主要路径通过：真实终端打开、两轮上下文对话、原请求防重、无隐含 Workspace 和正常退出。** 原生会话退出码0、进程消失、测试文件未变。工作台 Ctrl+C 后进程和端口关闭，但服务终端返回1，分别记录。

- [完整报告](reports/E2E-REPORT.md)：结果、证据、过程记录和未测边界。
- [检查点](reports/CHECKPOINT.md)：最终已停止，无继续运行的本轮服务或模型。
- [控制者复核](review/LEAD-REVIEW.md)：用户截图与文件、回执、OS进程交叉核对；没有冒称第二执行者独立复核。
- [启动兼容提示](reports/evidence/02-terminal-term-warning.json)、[第一轮](reports/evidence/03-first-native-response.json)、[第二轮](reports/evidence/04-second-native-response.json)、[防重复启动](reports/evidence/06-duplicate-request-check.json)、[正常退出](reports/evidence/08-native-exit.json)、[工作台收尾](reports/evidence/09-service-exit-audit.json)。

原请求为 `session-59f8b4bd-c11b-42d1-9a5a-016ac30d981e`。原生 session ID 未另行获取；请求ID和PID不替代它。用户确认 `TERM=dumb` 提示后完成两轮，提示留档；另两条瞬时 warnings 后来不再显示，详情未取得，不能推断与 TERM 相同或已经修复。

未新增 Desktop 自动化、项目手动准备、跨 Harness、远端 Git、自有模型服务、长期运行或完整 A–J 证明。未进行双击并发和丢失响应故障注入。两轮截图不等同精确 API 次数或账单；旧缺陷结论见[前一批修复回归](../2026-10-07-5aaae00/README.md)。当前登记见[实现进展](../../implementation.md)。

## 来源、脱敏与校验

[manifest.json](manifest.json)提供20份来源/归档文件的SHA256、字节数及处理说明，并为3张未公开原始截图保留来源摘要。机器路径替换为 `<E2E_ROOT>`、`<FIXED_INSTALL>`、`<USER_HOME>`、`<DEV_REPO>`；事件时间、请求ID、PID、状态、退出码、虚构测试内容及hash不变。可选UTF-8 BOM在归档副本中移除。

排除内容：含机器路径的原始截图、含本机控制Token的服务日志、运行home/锁、安装文件、认证文件及原生私人会话历史。截图内容的必要摘录与核对结果已入报告；原图本机保留，没有借脱敏修饰测试结果。仅归档普通启动请求的只读回执，不供导入或重放。

来源核对区分Windows安装CRLF和Git blob LF：七个相关文件的安装字节与工作树一致，规范化换行后与固定提交一致；两种原始摘要分列，不谎称它们字节相同。[初始来源](reports/evidence/00-preparation.json)中的模型轮次0及过程记录里的待执行状态均是当时事实，以最终报告为当前结果。

[SHA256SUMS](SHA256SUMS)覆盖自身之外全部归档文件，`.gitattributes` 保留提交字节。只读校验命令：

```sh
python docs/evidence/2026-10-08-5aaae00-ordinary/verify.py
```
