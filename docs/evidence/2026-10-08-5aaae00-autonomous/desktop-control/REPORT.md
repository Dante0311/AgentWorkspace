# Desktop 控制接口只读实测

本次使用固定 5aaae00520374b022e0c38fa21f312f8e08629ba 安装中的 `runtime.Desktop`，连接本机实际安装的 Codex App Tools 0.1.5。调用方标识与连接地址直接继承当前真实聊天的环境，不构造或替换其他调用方身份。

## 实际结果

- MCP 初始化和工具发现成功。实际工具目录包含 `create_thread`、`read_thread`、`send_message_to_thread`、项目查询和分区管理工具。
- 产品现有 `Desktop.status()` 对当前真实调用聊天返回 `busy`；此时控制者确在执行本轮任务。
- 产品调用关闭方法后，确认本次创建的 RPC 子进程已退出。未记录退出码或关闭方法内部是否使用终止回退，因此不宣称自然退出。
- 模型输入 0、消息发送 0、Workspace 创建 0、Binding 创建 0；未读取应用私有数据库，也未保存或导出其他聊天正文。

证据：[脱敏事实与组件校验](desktop-control-result.json)。该 JSON 不含连接地址、真实聊天 ID 或机器路径。测试脚本只保存在本地，入仓前须将其中机器路径转换为占位符。

## 尚未验证与当前产品缺口

本次只证明真实连接、工具发现和活动状态读取，不能证明新聊天创建、完整 Binding、投递、交接、空闲状态或原生停工。没有把当前控制者绑定为被测 Agent。

固定基线 `runtime.start` 的 Desktop 分支只生成进入提示和深链，返回 `awaiting_new_session_bind`；`transfer.preflight` 的自动交接目标只接受 codex/claude/codebuddy，明确拒绝 Desktop。上游已暴露创建聊天工具，不等于 AgentWorkspace 已接入此工具或已验证完整生命周期。

后续产品工作应按真实接口完成集成及相应用例；本轮不修改产品源码、不新建原生聊天来替代尚未实现的产品动作。

## 测试过程偏差

首个探针在连接前，因测试脚本使用错误的 Python distribution 名称 `agent-workspace` 而退出。该次未启动 RPC、模型或任何产品操作。查明实际名称为 `git-native-agent-workspace` 后，仅修正测试脚本并执行一次连接测试；不能将第一次测试脚本错误登记为产品缺陷。

凭据、控制连接地址、会话正文、完整工具目录和运行缓存不进入可共享材料。原始组件 SHA256 见事实 JSON，报告与证据归档时另生成源文件及归档文件校验值。
