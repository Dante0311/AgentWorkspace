# V1 实现进展

本页描述当前功能分支的实现事实，不替代 [design.md](design.md)。版本仍为 `0.1.0a1`，不是已完成全部目标和实机验收的正式 V1。实际恢复位置与逐次测试见 [development-checkpoint.md](development-checkpoint.md)，操作见 [runtime-and-maintenance.md](runtime-and-maintenance.md)。

## 模块

| 文件 | 当前职责 |
| --- | --- |
| `app.py`、`gitstore.py` | 持久身份/资料、条件提交、可恢复创建、检查点、Binding、Work 和 Git 访问。 |
| `onboarding.py` | 只发现和引导的首次使用、只读 Git 检查、三份管家定义/实例和本机准备。 |
| `harness_config.py` | Codex/Claude 原生模型选项查询、三种受管入口的实例独立模型配置；凭据只保存引用。 |
| `runtime.py`、`rpc.py`、`native_sdk.py` | 实际原生入口、持续事件、工具边界、初始接入、独占 Runner 与停工观测。 |
| `transfer.py` | 原绑定和固定后继的持久 handoff/relay，结果未知不重新创建会话。 |
| `messages.py` | Message/ACK、Git 发布补齐、FIFO 与当前入口通知。 |
| `maintenance.py` | 作用域授权、健康观测、安装位置归属明确的巡检、有限维修和结果复查。 |
| `bridges.py`、`wecom.py` | 可选外部渠道、文本收发与组件看护。 |
| `commands.py`、`cli.py`、`server.py`、`resources/` | 共用 CLI/HTTP/MCP 分发、本机工作台、首次配置、定义和七个 Skill。 |
| `scripts/install.py`、CI | 可验证制品、空目录隔离安装、源码快照与 wheel/sdist。 |

没有引入通用调度平台、模型网关、ACP 依赖或新的 Agent Loop。SDK 是按需安装的原生客户端，不是我们自研 Harness。元数据探测与实际会话共用凭据路由；Claude 握手返回模型选项，无需发送提示词，自有服务不使用内置目录。

## 已实现的闭环

创建/接入 Workspace → 选择并保存运行配置 → 为实例建立真实受管会话 → 平台 MCP/动态工具与持续通信 → 保存检查点、确认原端停妥 → 固定后继在同一实例目录接手 → 后续 Message 到达新入口。

Codex、Claude 和 CodeBuddy 的原生可执行程序已参与回环 API 测试，实际创建 Git 检查点；Claude/CodeBuddy 在同会话第二轮接收 Message 并生成 ACK。本轮还让原生 Codex 通过工具执行 checkpoint/stop，由真实 Runner 自动创建原生 Claude 后继，并验证 `Message.poll` 向后继投递。模型决策由协议夹具指定，不是付费模型质量测试。

三个管家共用普通实例与运行能力。Steward 处理 Workspace 请求，Sentinel 管理用户授权的巡检计划，程序计时和采集事实，Maintainer 只能执行被允许的维修。没有对应执行环境时，创建身份不会假装已启用巡检。

维修动作与复查分开持久记录：动作成功而复查失败时保留动作结果，同一请求仅补复查；不把整个操作降成未知后诱发重做。损坏的本机观测记录报告异常并保留，其他实例仍可检查。普通代理不能凭自己的 active Binding 写另一实例资产，管家也须有对应目标授权；这不是 OS 级隔离。

## 验证层次

- 默认 CI：Linux/Windows、Python 3.11/3.13 的完整安装与测试；独立 wheel 安装检查内置资源和三实例创建。
- `Native SDK contracts`：固定 SDK 版本、原生客户端回环 API、平台工具与自动交接。实际测试范围以该提交的工作流和日志为准。
- 本机定向回归：恢复、并发前提、未知结果、撤销授权、重复调度、HTTP/CLI 和原生工具副作用。
- 用户实机：已安装 Desktop、真实登录、自有模型服务的实际能力、生产 Git 权限、企业微信、长期在线和新机器体验。

被跳过的原生测试不计为通过；分组有交叉时不累加数量；当前源码不能沿用旧提交的绿色 CI。源码制品只用于准确恢复，长期成果保存在 Git 提交中。

## 剩余事项的性质

| 类别 | 内容 |
| --- | --- |
| 已有实现，需实机验收 | 受管三种 CLI 的真实模型/账号、自己的 API、模型和强度生效；生产 Git/凭据；企业微信 Bot；隔离安装和持续运行体验。 |
| 接口仍需核实，不能伪装成只待验收 | Claude/WorkBuddy 原生 Desktop 自动创建、持续投递、停工观测；Codex Desktop 从准备深链到完全自动建会话/跨端接手。 |
| 当前接入未实现的能力 | Claude/CodeBuddy SDK 的已验证 insert/steer；CodeBuddy 模型目录探测目前不提供，字段手工配置并注明 unchecked。不能用中断并重开轮次冒充 insert。 |
| 单独授权事项 | 合并 PR/main、正式版本发布、许可证、生产环境变更。 |

设计目标保留，当前未提供的 Desktop 自动化、SDK insert 与 CodeBuddy 目录查询按本版公开限制交付，详见随包维护的[支持范围](../src/agent_workspace/resources/prompts/capabilities.md)。不是声称上游无接口，也不是仅待用户验收；不为补齐功能表强行扩展复杂度。获得可靠接口后再按同一执行权合同增加支持。不静默改用后台 CLI、不将发现程序当作具备控制权，不为绕过接口限制预建新的会话界面。统一聊天、多事务、V2 独立身份、强制接管和通用迁移仍未实现。

## 设计和历史归属

本分支同步文档 PR #2 已确认的产品设计与开发约定，不再保留旧的“初始化不创建管家”作为当前产品合同。底层预览 `App.workspace_init`/旧远端入口仍保留原始行为，用户创建路径使用 onboarding 包装；既有空间不会因接入或升级被隐式迁移。

原始 `0.1.0a1` 的迁仓和验证记录保持原文，分别见 [migration.md](migration.md)、[validation.md](validation.md) 和 [validation-migration.md](validation-migration.md)。不要把当前接入进展回写成历史已经通过的证据。
