# 开发接续 Checkpoint

软件开发恢复记录，不是产品实例 checkpoint，也不是第二份设计。先核对远端提交和实际测试，不从聊天中的“继续”推断完成。

## 接续位置

- 日期：2026-10-04。唯一实现分支 `feat/native-runtime-maintenance`，草稿 [PR #4](https://github.com/Dante0311/AgentWorkspace/pull/4)，基于 PR #3。不另开平行实现、不合并 main、不改写历史、不发布版本。
- 本次基线 `d2edfacc8742e1b2fb9c41916a367658e4197fb8` 已同步文档 PR #2 的确定设计与开发约定。此前 `9c24ff8` 保存跨实例授权及原生 MCP 测试，`298c2ce` 保存维修恢复及原生 Codex → Claude 自动交接；均已推送。
- 本提交增加 Claude 原生模型/强度元数据查询，复用 SDK 初始化握手和已有凭据路由，接入首次配置页面和统一命令分发。没有新增运行依赖、网关或架构层。
- 源码恢复制品 `11299570873` SHA256：`2a3d30f165c5faeb88008568072ea8307db89a0c65950cb17beef3371c3f6f88`；固定 SDK 制品 `11290682699` SHA256：`63136e1021fa96af12458f8195ddfd41858697ca017363958d7b30f4c15cc777`。已校验。制品有期限，长期恢复以 Git 提交为准。

## 已完成与本轮补齐

已有三种受管 CLI 持续会话、独立模型服务配置、真实 Binding、Message/ACK、固定后继自动交接、三名管家、作用域授权、持久巡检、有限维修和隔离安装入口。运行说明在 [runtime-and-maintenance.md](runtime-and-maintenance.md)。

本轮四个单元：

1. 所有跨实例写操作检查明确授权，`asset.write` 可限定目标且可撤销。原生 Claude/CodeBuddy 通过平台 MCP 创建 Git 检查点，并在同会话第二轮接收 Message，形成真实 ACK 和本机副本。
2. 维修动作成功先保存，再独立健康复查；复查失败、退出或复查落盘失败不重做动作。损坏本机记录报告并保留，不阻断其他实例巡检。
3. 原生 Codex 通过动态工具执行 checkpoint/stop，Runner 确认停妥并创建原生 Claude 后继；用户资产和接手材料保留，旧 Binding released，后续自动 Message 投递到新会话并保存 ACK。对齐产品设计、README、操作和验收文档。
4. Claude SDK 握手返回实际模型/强度选项，无需模型输入。探测明确由用户触发，不暴露账号详情或密钥，不使用内置目录冒充自有服务模型。CodeBuddy 未验证目录接口时明确报告 unsupported，不启动探测客户端。首次配置支持三种受管配置，并复用相同候选展示逻辑。

## 本提交验证

- 本机完整套件，启用固定三种真实原生客户端：**248 passed in 199.86s，0 skipped / 0 failed / 0 errors**。JUnit 与 pytest 输出一致。
- 此前同一代码未设置原生可执行文件测试变量时：243 passed，5 skipped；已通过上项完整组合覆盖跳过项，不将两个结果相加。
- 定向元数据/配置/SDK 组：35 passed；真实 Claude 客户端工具与无模型调用的元数据测试：2 passed；分发/配置/HTTP 组：85 passed。均已包含于完整结果，不额外累加。
- 原生测试使用真实 Codex 0.160.0、Claude SDK 0.2.163、CodeBuddy SDK 0.3.267 及对应客户端，模型响应来自回环协议夹具。验证真实 SDK、平台工具、Runner 与 Git 副作用；不是付费模型、真实账号、Desktop 或生产服务验收。
- Python 编译、setup 页面 JavaScript 语法、Markdown 围栏/空白/相对文件链接及 20 条新 CLI 示例参数解析检查通过。没有把静态语法检查冒充完整浏览器验收。
- 所有上传的生产代码和测试内容按 Git blob SHA 对照本机已测试副本。完整本机运行的结果取代此前因命令执行超时而未取得全套结论的状态。
- 基线 d2edfac 的 Native SDK 工作流 `37200646955` 已成功；CI `37200646887` 最后读取仍在运行。本提交的 GitHub CI/Windows 和 SDK 工作流必须单独查看，不能沿用基线成功结论。

## 剩余事项

- 已有实现待实机验收：真实账号、自有 API 的模型/强度能力、生产 Git 凭据与分支策略、企业微信 Bot、新机器安装和长期运行体验。
- 仍需开发/核实原生接口：Claude/WorkBuddy Desktop 的会话创建、持续投递和停工观测；Codex Desktop 从深链准备到完整自动建立/跨端接手。不把 CLI 当作 Desktop，不把缺接口称作仅待用户验收。
- 当前 SDK 入口未实现已验证 insert/steer；CodeBuddy 目录查询仍不提供。不能以中断/重开轮次冒充 insert，不将 unchecked 配置当成服务支持。
- 查看当前提交 CI，失败先定位。正式合并、发布、许可证和生产变更仍需单独授权。

首次使用只发现和引导，不代装 Git/Harness 或登录。管家和普通实例共用运行能力；不改全局模型配置、不重写 Harness、不强制 ACP/网关。保留唯一入口、用户资产、凭据引用与未知结果保护；工具授权不等于 OS 沙箱。每个可验证单元及时提交并更新此文件，避免成果只留在临时环境。
