# 本包范围

仅2026-10-08 DeepSeek交接增量。旧query=0/待选型报告、r3包和旧测试均保留且未改。源文件SHA256及脱敏归档SHA256分别在manifest.json，字段筛选处理明确记录。

排除凭据/授权头/全局配置/账号、私密机器路径、整份聊天、thinking_tokens及native reasoning、stream deltas、完整工具/模型catalog、未筛选原生日志、截图、安装二进制/缓存、完整AW_HOME与运行锁。原始证据只在本轮根保留。JSON先解析成字段再脱敏，JSON/JSONL及内嵌JSON stdout/stderr均解析验证，避免换行与@tencent误判成邮件破坏JSON。

AGENTS.snapshot.md为证据而非活动指令；executor脚本和状态JSON只供审查，不作为产品或可运行恢复包。共享tclaude/Claude服务未证独占，未停止、不宣称全部退出。模型仅为包装器回报的路由标识，low仅证明已传递，无底层权重/effective-effort证明。便捷profile方括号拒绝仍开放，4次Read与2次参数错误保留。


## binary-artifacts

固定产品提交 5aaae00520374b022e0c38fa21f312f8e08629ba；wheel SHA256 e9bcff1a015358643bafbc800d1beb7453dd36cbb8bd1c34a10e68d68ca309f7。二进制及完整安装不入仓，安装源码与 wheel 的逐项核对另见执行报告所链接的软件审计证据。

最终仓库目录合并执行者增量包和独立复核。manifest.json 保留源/执行者归档/最终归档摘要；SHA256SUMS 覆盖除自身外的全部文件。复核中的相对链接映射到归档材料及未变的产品源码；原始报告及其 SHA256 保留在本机。本目录没有覆盖上一批 query=0 的历史证据。

参数错误计数补充：执行报告重点记录 tclaude 的 2 次错误；独立复核还核对到旧 Codex 及 peer 共 4 次，整个增量合计 6 次，相关原生工具记录保留。
