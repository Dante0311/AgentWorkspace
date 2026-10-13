# AgentWorkspace

**会话可以更换，Agent 的身份与工作资产持续存在。**

AgentWorkspace 在用户已有的 Agent 客户端之上提供协作：保存 Agent 的身份、职责、Skill、资料和历史，管理当前执行资格，并通过 Git Workspace 交换消息。它操作已有客户端的真实会话，不重写模型推理或工具循环，也不要求用户改用新的聊天客户端。Work / Delivery 按需使用。

2026-10-12 的[设计整理](docs/design.md#31-用户工作根与-aw-内部目录)已于 10 月 13 日进入实现：实例和共享仓的平台内部数据统一放入 `.agentworkspace/`，同一正式 `AW_HOME` 的实例共用平台程序和后台，基础检查及已授权恢复不依赖管家模型持续在线。当前正在集成迁移、后台与统一升级，尚未据此升级日常安装或迁移现有数据；验证范围以[当前实现](docs/implementation.md)为准。

> **开发预览。** npm 包版本为 `0.1.0-alpha.1`，Python 后端沿用 `0.1.0a1`。优先满足 Codex Desktop 与 ChatGPT Web；Web 当前手动收件，已有 Web Courier MVP 已纳入开发和独立 E2E，首批目标是人工确认的单条正式 Message，尚未完成真实浏览器验收。tclaude 待实际验证，其他 Harness、模型供应商与企业微信暂缓扩展。已有 npm、后台、三视图工作台、同机直发路径、显式强制接手及原操作继续的验证边界见[当前实现](docs/implementation.md)，不表示完整 V1 已完成。未发布 npm Registry 或正式 Release。

Codex Desktop 已有在本地项目中的自动创建、真实会话绑定、持续投递和同 Agent 交接；需要先准备项目并从真实桌面聊天取得控制连接。历史限定实测见 [实现进展](docs/implementation.md#codex-desktop-自动接入2026-10-08)，操作和限制见 [Codex Desktop](docs/usage.md#42-codex-desktop)。这些结果不代替本轮新增功能的验收。

## 已有共同职责与共享 Skill

共同职责可通过 AGENTS.md 的 `@workspace-read` 指引，从所属 Workspace 同一 Git 提交读取；共享 `skills/` 可在创建时选择、后续安装更新，Definition 自带 Skill 保留并保护私人修改。Codex 准备入口发现/复用真实项目，分区仅在实际接口 schema 相符时执行，项目创建及文件夹编辑仍明确手动降级。[使用说明](docs/shared-materials.md)和[统一验收](https://github.com/Dante0311/AW-Workspace/blob/5ec6e5e99dcc68b8ec58e701a7ff9d7b119974e8/development/archive/2026-10-10-unified-57446de/docs/shared-materials-acceptance.md)区分开发回归、原生协议与待执行实机验证。

## Agent、执行会话与本地副本

Agent 是属于一个 Workspace 的持久身份；执行会话是它当前使用的 Codex 或 ChatGPT 等聊天；运行环境是所在电脑或云端；本地副本是某台电脑上的资料目录。同一 Agent 换机器、换会话仍保留身份与 `instance/*` 分支，只有 create 或 Fork 才创建新 Agent。复制目录不会创建身份或取得执行权，旧副本和旧聊天可查看，但不能冒充当前有效入口。

正常 handoff/relay 保存资料并延续同一 Agent。用户显式强制接手可以撤销旧入口的 AW 资格；旧原生会话是否实际停止须另行核实，不做额度耗尽自动救援。Fork 失败后核对原目标并只继续缺失步骤，复用已有成果。原生项目发现、复用和分区准备仍以真实接口能力为准；已有普通会话与配置能力保留在底层，不进入近期工作台主流程，历史操作见 [普通会话与桌面项目](docs/session-projects.md)。

## 使用流程

**安装 npm 构建包 → 用户准备 Git 与原生客户端 → 创建/接入 Workspace 与 Agent → 在有效执行会话中协作 → 用工作台查看状态和历史。**

正式用户安装入口为 npm，当前先提供 Windows x64 构建。需要 Node.js 22+，无需系统 Python；包内携带固定 Python 3.13 运行时、后端 wheel、网页和七个 Skills。在所选提交的 GitHub Actions 或本地构建中取得 `.tgz` 与校验信息后安装：

```sh
npm install -g ./git-native-agent-workspace-0.1.0-alpha.1.tgz
aw backend start --open
```

当前未发布 npm Registry，不能省略文件路径当作 Registry 安装。以实际提交、构建来源和校验值区分产物，不能仅凭相同的预览版本号判断来源。wheel 和旧安装脚本保留为开发、底层构建与历史复现工具，不作为第二条正式用户路线。

一个正式 `AW_HOME` 下的后台管理本机现有 Runner 任务和 maintenance，提供状态、停止、重启和日志。后台停止后工作台连接也会关闭，重新启动使用 CLI。升级时先请求停止，再查看实际状态：

```sh
aw backend stop
aw backend status
```

确认状态为 `stopped` 后，再安装新包并启动同一个数据目录。页面断开或停止请求已接受不能代替这一步：

```sh
npm install -g ./git-native-agent-workspace-0.1.0-alpha.1.tgz
aw backend start --open
```

工作台地址含本机控制 Token，不要分享。Git 和所选 Harness 需要用户自行安装、登录，检测不代装、不改全局配置。支持仅本机 Git 或用户自己提供的远端仓库地址，远端认证复用本机 Git/SSH；读访问成功不等于已验证写权限。

上例安装时换成实际采用的新构建文件。`aw backend status`、`aw backend restart`、`aw backend log` 用于查看和控制，`aw backend run` 可前台运行；已有 `aw serve` 保留兼容。隔离测试数据不自动并入日常后台，停止 AW 后台不等于原生聊天已关闭或 Agent 已交出执行权。

本轮已完成隔离 npm 离线安装、使用包内 Python 运行 CLI/HTTP、七个 Skills 完整性、后台重复启动/重启/停止及卸载重装同包后原数据保留检查。工作台也已用真实浏览器和隔离后台检查启停与重连；这些结果不代替真实 Desktop、跨机器或跨数据格式升级验收。首次配置和底层 CLI 操作见[新机器配置](docs/first-use.md)与[运行与维护说明](docs/runtime-and-maintenance.md)。参与开发才需要 clone 源码，见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 当前能力

| 能力 | 实现范围 |
| --- | --- |
| 持久 Agent | 独立工作根、AGENTS.md、七个 Skills 和检查点；不强制 Definition 或 Work。 |
| 首次配置 | Git/Harness 发现、只读 Git 检查、可补齐的初始化；新空间为 Steward、Sentinel、Maintainer 分别选择本机实例目录，不隐式启动。 |
| 模型与会话 | 已有 Codex App Server、Claude/CodeBuddy SDK 和实例配置保留；近期优先 Codex Desktop，ChatGPT Web 手动接入，其余范围不继续扩展。 |
| 正式通信与交接 | 不可变 Message/ACK、当前 Binding、FIFO、有限通知重试和固定后继交接；跨 Harness 的回环测试不等于本轮实机验收。 |
| 同机原生直发 | 新方向：message Skill 每次核对双方 CURRENT 入口和同机 Codex 事实，其他情况走正式 Message；最终行为需单独验证。 |
| 管家维护 | 已有作用域委托、健康检查、持久巡检与有限维修保留；本轮统一到正式本机后台，未知业务不重放。 |
| 资产与工作 | 明确文件导入、来源差异与更新、选定共享提升、Fork、可选 Work/Delivery。 |
| 接口与安装 | CLI、HTTP、MCP 共用实现；npm 是用户入口，包内运行时、后台与保留数据的程序替换已做隔离检查，实际交付仍以提交和制品校验值为准。 |

工作台近期主入口仅为 Agent 与环境、消息历史、本机后台状态与停止/重启/日志，Workspace 仍用来选择查看范围。模型配置、创建与交接等操作通过现有 CLI/Skills 使用，复杂界面暂缓。统一聊天界面和同一身份的多事务会话仍留到 V3。

每次发送和回复先由 message Skill 判断路径：确认双方当前有效入口均为同机 Codex 时才原生直发；其他机器、跨 Harness、云端或事实不足时用正式 AW Message。原生发送已尝试但结果未知时只核对原发送，不能换路重发。直发的可选记录与回执独立保存，并标明 `codex` 等来源；保存失败不影响交流，也不触发正式索引、ACK 扫描或后台重投。工作台可合并历史，但必须标清来源。

## 运行边界

[当前版本支持范围与限制](src/agent_workspace/resources/prompts/capabilities.md)同时提供给用户和 Agent：工作台可查看本机说明，首次进入/relay 提示自动附带，实例 Skill 也指向同一份材料。当前不支持是明确的版本边界，不与尚未验证或临时故障混为一谈；设计目标不是支持承诺。

**Desktop 与 CLI 分开。** CodeBuddy 受管 CLI 不等于 WorkBuddy Desktop。Codex Desktop 仍需实际桌面控制连接和会话绑定，深链打开不代表会话已创建；Claude/WorkBuddy Desktop 自动控制尚未接通。具体缺口见 [能力矩阵](docs/runtime-and-maintenance.md#5-当前能力与验收边界)。

**发现、配置和实际运行分开。** 模型或强度字段保存成功不证明服务支持。SDK 原生工具默认收紧，用户按需明确允许；SDK insert/steer 未验证时明确拒绝，不偷偷改为 normal。

**管家身份和巡检启用分开。** 名字不授予管理员权限。程序负责计时，模型按事务处理；本轮后台统一管理本机维护任务，关闭网页不等于停止后台，停止后台也不等于关闭原生会话。关机/休眠不继续巡检，不自动注册开机任务。

**测试与生产验收分开。** 原生客户端测试使用回环模型协议夹具，验证真实 SDK、MCP 和 Git 副作用，不代表真实模型质量、账号权限、长期运行或 Desktop 验收。失败和未知结果保留，不以成功文本代替证据。

## 软件、Workspace 与产品资料

```text
AgentWorkspace 软件安装
    └─ 管理一个或多个 Shared Workspace
         ├─ main：登记、定义、Message、Work 等共享事实
         ├─ instance/steward、sentinel、maintainer：管家各自的持久资产
         └─ instance/<agent>：用户实例的独立资产
产品仓：实际代码、设计和交付成果，单独关联
```

默认本机数据目录为 `~/.agent-workspace/`，可用 `--home` 或 `AW_HOME` 指定。不要把软件开发仓或产品仓当作协作数据仓。目录或分支独立不等于保密隔离；仅本机 Git 不代表模型请求离线。升级不覆盖用户职责和资料，重新接入不重建管家或接管旧入口。

## 文档入口

| 文件 | 内容 |
| --- | --- |
| [产品设计](docs/design.md) | 唯一产品合同，V1 目标及 V2/V3 边界。 |
| [首次配置](docs/first-use.md) | 新机器准备、本机/远端 Git、三实例初始化。 |
| [运行与维护](docs/runtime-and-maintenance.md) | 当前操作入口、支持矩阵、限制和实机验收。 |
| [工作台](docs/workbench.md) | Agent 与环境、两类消息历史、本机后台控制，以及各项状态的依据。 |
| [基础使用](docs/usage.md) | 基础 CLI、消息、资产、Work 与旧入口说明。 |
| [实现状态](docs/implementation.md) | 当前模块、验证层次和剩余缺口。 |
| [开发协作仓](https://github.com/Dante0311/AW-Workspace/blob/main/development/README.md) | 团队问题、调查、试验代码、交接与详细验证证据。 |
| [开发说明](CONTRIBUTING.md) | 源码安装、测试、打包。 |
| [开发规则](AGENTS.md) | 开发本软件的约定，不是用户实例的职责文件。 |

历史验证和开发过程材料统一保存在 [AW-Workspace 归档](https://github.com/Dante0311/AW-Workspace/blob/c37ef2e92189adf357dc0e351aff48da9308377f/development/archive/2026-10-09-product-repository/README.md)，不拿旧测试结论代替当前提交验证。产品源码、正式测试、CI、安装打包、随包 Skill、设计和使用文档在本仓维护；团队任务、调查、试验与验收脚本、报告和日志在开发协作仓维护。Playbook 保留来源关系，见 [迁仓记录](docs/migration.md)。

## 许可证与发布

许可证尚未确定，没有新增开源许可授权；公开仓库不等于已采用 MIT/Apache 等许可证。npm 包保持 `private=true` 与 `UNLICENSED`，当前仅提供开发构建和 PR，正式合并、Registry/Release 发布和许可证变更须分别授权。
