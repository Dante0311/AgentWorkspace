# 2026-10-08 桌面项目与分区手动验收

固定产品基线 `5aaae00520374b022e0c38fa21f312f8e08629ba`，复用前批隔离安装，新建独立数据、一个未运行 Agent 和虚构产品目录。

**限定通过：** 工作台本机引用保存、改名、刷新和旧 revision 冲突保护；用户实际建立的 Codex 项目保持原 ID、实例主目录和附加目录主次关系，并移入与引用名称一致的分区。最终测试根下只有一个原生项目。

- [最终结果与未测边界](reports/FINAL-RESULT.md)
- [完整阶段记录](reports/E2E-REPORT.md)
- [检查点](reports/CHECKPOINT.md)
- [控制者复核](review/LEAD-REVIEW.md)
- [原生项目与分区读回](reports/evidence/07-final-native-readback.json)
- [平台终态及文件核对](reports/evidence/08-final-platform-audit.json)
- [服务退出审计](reports/evidence/09-service-exit-audit.json)

平台自己的 `manual_setup_required` / `native_project_verified=false` 保持如实返回；人工结论不等同平台自动核验。附加目录完整路径、Desktop 应用版本号未独立取得。未启动原生 Desktop 会话、模型、Binding、handoff 或 relay，没有多会话复用及自动创建/交接证明。本组没有第二执行者独立复核。

服务 Ctrl+C 后终端返回 1，进程与监听端口已消失。测试项目、分区及数据保留；其他用户项目未被本轮控制者修改。

## 来源与脱敏

[manifest.json](manifest.json) 记录各文件源/归档 SHA256、字节数和处理方式，及三张本机原始截图摘要。[SHA256SUMS](SHA256SUMS) 覆盖全部归档文件（自身除外），可运行 [verify.py](verify.py) 校验完整性、格式与相对链接。历史阶段记录保留，最终状态单独列出。

绝对路径替换为 `<E2E_ROOT>`、`<FIXED_INSTALL>`、`<DEV_REPO>` 和 `<USER_HOME>`。JSON 可读化，字段值中的操作/实例/项目/分区 ID、时间、revision、结果和摘要保留。原图只留本机，不进入仓库；仅归档必要事实摘录和来源摘要。服务控制凭据日志、运行锁、安装包、运行目录、应用私有数据及无关原生项目/聊天记录排除。
