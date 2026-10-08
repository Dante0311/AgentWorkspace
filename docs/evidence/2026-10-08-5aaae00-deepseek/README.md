# Codex → tclaude / DeepSeek 实机交接（2026-10-08）

**公开完整配置路径的真实交接闭环限定通过。** 用户选择 DeepSeek 后，从已连接的 tclaude 目录选用 `claude-deepseek-v4.1-flash[1m]`，配置 `low`，沿用用户已登录的内部服务。固定产品仍为 `5aaae00`，复用隔离安装、新建测试 Workspace 和实例，未修改产品源码或全局配置。

本增量为 3 个 Codex 轮次和 2 次 tclaude query，均完成。Codex 保存随机资产并本人交接，平台自动启动 tclaude 后继；同一实例身份和工作根保持，新 Binding/native session 建立。后继读回旧检查点及资产、本人接收 normal 消息并发布 ACK，保存记录与检查点后自行停止。旧 Binding 写入被拒绝且操作未落账；两端 released、Runner 退出、Watch 关闭，transfer 终态仍为 completed。

原生 init 回报所选完整模型 ID，Assistant 回报 `deepseek/deepseek-flash`。这证明包装器回报的模型路由；`low` 只证明配置传递，没有服务端实际强度回报。

两项限制保留：便捷 `agent.configure-sdk` 入口会拒绝模型 ID 中的方括号，本次通过已有 `agent.configure(value)` / `agent.transfer(target_config)` 完整配置路径继续，该兼容问题未修复；后继首轮执行了 4 次原生 Read，因此严格仅使用 aw_execute 的指令遵循不通过。整组另有 6 次参数错误（Codex 4 次、tclaude 2 次），均在原轮自行纠正。部分中文工具输出乱码原因未定位。

- [完整执行报告](reports/TRANSFER-DEEPSEEK.md)与[检查点](reports/TRANSFER-CHECKPOINT.md)
- [第二执行者独立复核](review/DEEPSEEK-TRANSFER-REVIEW.md)
- [真实模型、工具和完成事件](reports/evidence/T39-deepseek-native-facts.json)
- [共享协议事实核对](reports/evidence/T40-independent-protocol-verification.json)
- [便捷配置实际拒绝](reports/evidence/T01-public-typed-model-rejected.json)
- [最终消息与 ACK](reports/evidence/T34-message-show.json)、[最终交接状态](reports/evidence/T33-transfer-final.json)

[前一批无模型预检](../2026-10-08-5aaae00-autonomous/README.md)是选型前的历史事实，保持不变。本次结果不证明 WorkBuddy 入口已修复，也不扩大为 Desktop、反向交接、完整矩阵或长期运行通过。

[manifest.json](manifest.json)、[SHA256SUMS](SHA256SUMS)及[排除说明](EXCLUSIONS.md)提供来源、归档摘要与处理范围。只读执行 `python docs/evidence/2026-10-08-5aaae00-deepseek/verify.py` 可核对归档格式、链接及完整性。
