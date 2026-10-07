# 脱敏与排除范围

本目录保存完整执行报告、检查点、两份独立复核、阶段操作回执、失败与更正记录、定向测试输出/JUnit、必要原生事件、消息/ACK、测试资产与检查点、最终输入和交接事务，以及执行管理脚本的脱敏副本。原始文件不改动，来源及归档摘要在 [manifest.json](manifest.json)分列。

## 内容变换

- 测试根、开发仓、用户目录、Node 安装目录替换为 `<E2E_ROOT>`、`<DEV_REPO>`、`<USER_HOME>`、`<NODE_HOME>`；机器名替换为 `[TEST_HOST]`，账号和凭据模式使用 `[ACCOUNT]`、`[REDACTED]`。替换标记不是可执行路径。
- 五份 JUnit 从原始 XML 解析后脱敏属性和文本，再序列化并保留结果；这修正执行方证据包中两份 XML 的替换转义问题。六文件中的机器名残留已清除；测试首跑失败、skip 和零用例 selector 错误均未删改。每项实际字节变化见 manifest。
- `native/` 为七个 Binding 的**筛选事件**，不是完整原始日志。保留 turn/thread 开始、turn 完成、error，以及 userMessage、agentMessage、dynamicToolCall、commandExecution、mcpToolCall、sleep 的开始/完成事件。保留失败工具调用、steer、状态和时间顺序；不把内容相同的流式增量当作额外轮次。
- 排除 account/rateLimits、tokenUsage、reasoning、流式重复、远程控制状态、MCP 启动状态及 thread/status 更新等非必要事件。实际每种方法排除数量见 manifest 的 `excluded_event_method_counts`。原始完整 runtime 留在本机，源摘要对应完整文件，归档摘要对应筛选脱敏结果。
- 源/归档 hash、事件、请求、操作、消息、Binding、session、turn、检查点及 Git revision 标识保留，便于交叉核对。保存它们不等于为其赋予新的运行权限。

## 不入仓的材料

凭据、认证文件、DPAPI vault、控制 Token、私人会话和附件、未脱敏截图；旧批次运行数据；完整原生日志；产品安装目录、可执行程序、wheel 和完整源码副本；缓存、运行锁、共享 Git 的完整对象库与运行 home。没有把原 `.aw-local` 整体复制为可运行目录；仅以新批次 `terminal-inputs/`、`terminal-transfers/` 保存终态及残余缺陷证据。

本批没有启动带 Token 的工作台，也没有发送企微或其他外部业务消息。旧批次完整证据已在其独立目录保存，不在此重复打包；原 WorkBuddy 文件保持原路径与字节，不随日志公开，也未重命名或替换。

`executor-scripts/` 仅便于审查观察顺序、管理端澄清及参数更正；包含写入测试资产、启动测试实例等动作，不应自动执行。原脚本中的路径已替换，不能将此目录当成复用运行环境。
