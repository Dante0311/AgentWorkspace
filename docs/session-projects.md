# 普通会话、内网模型服务与桌面项目

这是 main `e55dfbf` 之后的独立功能批次，需安装包含本页的新构建；旧验收包不会自动拥有这些入口。当前支持范围以随包 [capabilities.md](../src/agent_workspace/resources/prompts/capabilities.md) 为准。

## 1. 内网 HTTP 模型服务

三种运行配置共用同一个地址检查。默认接受 HTTPS 和原有回环 HTTP；使用非本机 HTTP 时，由用户对当前配置明确勾选允许明文 HTTP，或传 `--allow-http`。地址或 Harness 变更后，界面清除确认。不按 IP 段猜测内网，不访问用户地址来“证明安全”。HTTP 会明文传输凭据和内容；允许 HTTP 不是网络安全、模型权限或协议兼容的证明。

```sh
aw -w demo agent configure-codex reviewer --model MODEL_ID --base-url http://gateway.internal:4000/v1 --env-key MY_MODEL_KEY --allow-http
aw -w demo agent configure-sdk reviewer --kind claude --model MODEL_ID --base-url http://gateway.internal:4000 --env-key MY_MODEL_KEY --allow-http
```

这是替代配置示例，请使用实际服务说明中的地址和模型 ID。Base URL 原样传递，不自动补 `/v1` 或 `/messages`。Codex 仍需 Responses，Claude 需原生 Messages，CodeBuddy 需其原生协议。密钥只从本机环境读取，不写进 Workspace、配置文件或命令参数。修改已运行持久实例的配置仍需显式交接；目标 `transfer-profile` 和元数据探测也使用同一 HTTP 确认规则。管家不能自行开启新 HTTP 传输确认。

## 2. 无 Workspace 的普通会话

打开工作台或首次配置页的“新建普通会话（无需 Workspace）”。选择 Codex / Claude Code / CodeBuddy **CLI**、已有工作目录、模型服务和本次任务，再点击“保存并打开原生 CLI”。该入口不要求 Git；仍需自行安装、登录 Harness。

软件直接启动交互式原生 CLI，不调用受管实例的 Agent Loop，不创建隐含 Workspace、管家、Agent、Binding 或 worktree。任务以一个原生输入参数传递，不把本次角色写入共享 AGENTS.md，不注入平台 MCP 或旧入口身份。原生工具、用户/项目配置和规则仍可能被 Harness 加载；这不是沙箱或指令隔离保证。文件修改权限由原生 CLI 确认，不自动打开“完全访问”。

CLI 也可使用同一流程：

```sh
aw session prepare --kind claude --directory /path/to/project --model MODEL_ID --request-id ordinary-001 --prompt "只审查登录模块，不修改文件。"
aw session open ordinary-001
aw session show ordinary-001
```

`prepare` 只固定本机启动请求，不开终端或调用模型。`open` 在 Windows 新控制台、macOS Terminal 或已安装的 Linux xterm/gnome-terminal/konsole 中请求打开。没有图形环境或支持的终端时返回说明与**原请求**启动命令：

```sh
aw session run ordinary-001
```

这条命令自动使用已经选择的工作目录，不要求用户手动 cd。只有真实交互终端才能执行 `run`，它不暴露给 HTTP/MCP。此启动器不执行 `.cmd/.bat` 包装脚本，需选择真实原生可执行程序；不为此自动安装软件或更换成 Desktop。macOS Terminal 或已有终端服务未必继承工作台的临时环境变量，凭据应在实际终端环境准备；缺失时在原生启动前停止。

**本机启动请求 ID 不是原生会话 ID。** `terminal_requested` 仅说明已请求终端，`native_running` 是原生进程启动后的最后观测，`native_exited` 仅表示进程退出，不代表业务完成；平台不解析终端画面来伪造原生会话确认。原生界面中的登录、信任确认和真正会话状态需在该界面核对。历史与续聊使用 Harness 自己的功能，不自动获得平台 Message/ACK 或跨 Harness handoff/relay。

重复点击、HTTP 响应丢失、刷新均沿用同一个固定请求。刷新只读，不启动。进程已尝试启动、已退出或结果不明时，不以同请求重开；使用原生历史继续，或由用户明确创建另一个会话。缺少凭据等原生启动前的错误可用同请求修正后继续。本机只保留 `ordinary-sessions/` 下的启动参数/观测，不保存凭据或复制原生对话历史。浏览器草稿按标签页和安装位置隔离，关闭标签页可能丢失草稿，本机原请求仍在。

持久 Agent 的实例目录及其子目录不能从普通会话入口直接启动，以免绕过已登记的执行权。要接手它，请使用 Agent 入口。普通会话与持久实例仍是不同产品对象，没有实现 V2 的独立持久身份。

## 3. 持久 Agent 的桌面项目与 Codex 分区

在 Agent 卡片选择“桌面项目”。选择实际桌面端后，平台展示实例主目录、建议项目名和 Codex 分区名；允许保存用户已有名称和显式选定的产品目录。这里只保存**本机引用**，不创建或修改原生项目、分区、权限、会话、实例职责或产品文件。

```sh
aw -w demo agent desktop-project reviewer --harness codex
aw -w demo agent desktop-project-save reviewer --harness codex --project-name "AW · demo · reviewer" --section-name "AW · demo" --product-path /path/to/product
```

首次保存可省略 `--revision`；以后修改先读取返回 revision，再原样传入，防止覆盖其他窗口的改动。用户调整名称或分区后，后续读取保持原设置，不自动搬回默认布局。多次新会话复用一个 Agent 项目；不提前为所有 Agent 在所有桌面端创建项目。

主目录指向 Agent 已有实例目录。产品目录作为附加工作对象按需关联，不复制代码，不在原生项目设置里再维护完整角色提示。Codex 分区按 Workspace 组织，只用于侧栏显示，不新增共享 AGENTS.md 或共同权限。普通会话使用已有项目目录，不归入 Agent 专属分区。

实际手动步骤只维护于随包 [desktop-projects.md](../src/agent_workspace/resources/prompts/desktop-projects.md)。`agent.desktop-project` 也向 Agent 返回当前安装的同一份说明，旧实例不必依赖过期副本。保存引用不是原生操作成功，当前始终明确 `native_project_verified=false`。桌面项目/分区自动管理未接入，不读写私有应用数据库，不暗中回退 CLI。项目容纳历史会话不改变持久 Agent 单一有效入口规则。

## 4. 验证范围与原生资料

自动测试应分别覆盖地址检查、凭据/身份不继承、原请求不重复启动、原生 argv 参数、HTTP/浏览器、项目引用不修改共享资产及安装资源。真实终端窗口、系统权限对话框、登录、自有 API 与各桌面版本仍需实机验收。原生 `--help` 参数检查不是已经完成真实对话的证明。

2026-10-05 核对的原生资料：

- [Codex CLI 参数](https://developers.openai.com/codex/cli/reference)：原生 CLI、配置覆盖、工作目录与权限。
- [Claude Code CLI](https://code.claude.com/docs/en/cli-reference)：交互输入、模型、强度与会话选项。
- [CodeBuddy CLI](https://www.codebuddy.ai/docs/cli/cli-reference)：交互入口与原生参数；不是 WorkBuddy Desktop。
- [Codex 本地项目](https://learn.chatgpt.com/docs/projects)：主/附加文件夹及自动规则发现；页面介绍功能不等于提供平台控制接口。
- [Codex 更新说明](https://learn.chatgpt.com/docs/changelog)：侧栏组织能力按用户安装版本核对，不据此推断外部可写接口。
