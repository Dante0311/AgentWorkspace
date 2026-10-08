# 排除与脱敏说明

本目录整合执行者 r3 子包、独立复核，以及 Lead 的 Desktop 只读探针。执行报告中的“本包”指执行者子包；最终仓库归档以本目录 manifest.json 与 SHA256SUMS 为准。

## 保留内容

保留完整执行报告、检查点、独立复核、平台操作/输入/事务/资产/检查点证据、原生完成事件与实际工具调用、失败和偏差、版本及组件摘要。四个原生日志按完成事件和工具调用筛选，含三次 Shell 尝试；不以模型文字替代操作证据。AGENTS.snapshot.md 是测试任务快照，不是目录开发规则。

## 排除内容

凭据、登录文件、授权头、账号、控制连接地址、其他私人聊天、模型 reasoning、流式重复事件、费率事件、完整工具/模型目录、安装环境、缓存、运行锁、完整可运行 AW_HOME 和截图不入仓。完整原始材料仅留本机。共享 tclaude/Claude 原生服务的全局进程清单和命令行排除，仅保留本轮归属核对结论。

机器路径替换为 E2E_ROOT、DESKTOP_PROBE_ROOT、USER_HOME、DEVELOPMENT_REPO、NODE_HOME 等占位符。tclaude 握手只保留连接、认证类别、未调用模型及目录类别；不保存完整内部目录。JSON 状态与 executor 脚本仅供审查，不应导入或执行为恢复任务。

## binary-artifacts

wheel、安装环境和原生二进制不入仓。固定产品提交为 5aaae00520374b022e0c38fa21f312f8e08629ba，wheel SHA256 为 e9bcff1a015358643bafbc800d1beb7453dd36cbb8bd1c34a10e68d68ca309f7。组件路径/摘要见 reports/evidence/01-baseline.json、20-tclaude-prerequisites.json、69-sdk-source-checksums.json。复核报告的产品源码链接指向仓库文件，固定源版本与安装字节摘要在报告中单列。

## 归档修正

执行者保留了 r1/r2/r3 归档过程。Lead 在入仓时发现 r3 的 21-tclaude-version.json 被全字符串邮箱脱敏规则破坏转义；本目录从原始 JSON 逐字段脱敏并重新序列化，不修改原始测试记录。manifest 同时保留原文件、执行者中间归档和最终仓库归档摘要，不能把中间候选的检查结果当成最终目录校验结果。

PARTIAL 是第一次复核，FINAL 是追加管家与预检范围后的结论；历史报告和源哈希保留，目录重排只更新相对链接。Desktop 首次测试脚本的 distribution 名称错误只由控制者过程说明，未保存独立首败日志，不冒称第二执行者复核了该失败全过程。
