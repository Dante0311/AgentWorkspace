# AgentWorkspace

**会话可以更换，Agent 的身份与工作资产持续存在。**

AgentWorkspace 是一个 Git-native 的持久 Agent 协作工作空间：每个实例拥有自己的职责、Skill、资料和历史，通过共享 Workspace 通信，并按需使用 Work / Delivery 组织正式工作。它连接用户选择的 Desktop、CLI 或其他运行入口，不要求用一个新聊天客户端替换原来的工作习惯。

> **当前版本：`0.1.0a1`，开发预览版。** 已有可安装代码、CLI、本机工作台和七个 Skill。真实 Codex Desktop、真实模型、企业微信及生产 GitHub Backend 尚未完成实机验收，请先用隔离数据试用。这不是正式 V1 Release，也未发布到 PyPI。

## 已确认的 V1 目标（待实现）

2026-10-02 确认：Workspace 创建时建立 Steward、Sentinel、Maintainer 三个真实管家实例。Steward 帮用户处理 Workspace 事务，巡检与维修由下属成员承担；不是业务中央调度者。小组与用户实例共用运行能力。

V1 就要支持“选择 Harness 与模型配置 → 创建真实会话 → 持续通信 → 自动交接”。首批目标为 Codex、Claude Code、WorkBuddy 的 Desktop/CLI，以及企业微信渠道；各入口分别验收。支持在协议兼容前提下使用自有模型服务，尤其是指定 URL/API 凭据但沿用 Codex Harness。手动 handoff/relay 是保底，不替代自动化；自己的统一聊天界面留到 V3。

这些是已确认目标，**当前预览版尚未实现管家小组和完整通用接入流程**。以下能力表、安装示例和 [使用说明](docs/usage.md) 仍描述当前实现；完整合同见 [设计基线](docs/design.md)，新增差距见 [实现进展](docs/implementation.md)。本次只落档，不添加运行依赖，也未选定 ACP、配置管理产品或模型网关。

## 核心能力

| 能力 | 当前范围 |
| --- | --- |
| 持久实例 | 独立工作根与 `AGENTS.md`，Definition 和 Work 均可选；支持从自然语言描述逐步完善。 |
| 轻量协作 | 不可变 Message、最小 ACK、按序 `normal / insert`、自动收件开关与 Git 发布补齐。 |
| 接续与分叉 | 检查点、`handoff → relay` 换新会话、从确定检查点 Fork；V1 同一实例最多一个有效入口。 |
| 工作资产 | 明确范围的文件导入、来源版本差异、受管材料更新、用户确认后的共享提升。 |
| 可选任务管理 | 轻量 Work 树、唯一负责人、正式 Delivery 与交付后封存，不强制工作方法。 |
| 接入 | CLI、HTTP、MCP、本机中文工作台；Desktop/托管 Codex 适配代码及可选企微文本桥接。 |

没有实际任务时，初始化只完善用户要求的基础材料、简短问候并保存初始检查点，不替用户分配试做任务。

## 安装与开始

需要 **Python 3.11+**。本地或普通 Git 远端需要安装 Git；`github:OWNER/REPO` 访问使用仓库 API。

当前从仓库安装，建议先创建虚拟环境。以下命令在仓库根目录执行：

```sh
git clone https://github.com/Dante0311/AgentWorkspace.git
cd AgentWorkspace
python -m pip install .
aw --help
aw serve --open
```

工作台只监听本机回环地址。启动地址含控制 Token，不要分享。默认数据目录为 `~/.agent-workspace/`；可用 `--home` 或 `AW_HOME` 指定。

也可在专门的试用目录运行最小 CLI 路径：

```sh
aw --home ./.aw-demo workspace init demo ./.aw-demo/demo.git
aw --home ./.aw-demo -w demo agent create helper --id helper --description "构建助手；没有任务时等待安排。"
aw --home ./.aw-demo -w demo agent show helper
aw --home ./.aw-demo serve --open
```

这些命令只创建和查看实例，不会调用模型。运行接入另按 [使用说明](docs/usage.md) 配置。**不要把本工具开发仓当作用户的 Shared Workspace，也不要在产品仓里初始化协作数据。**

安装 wheel 后不需要保留开发仓。构建方式见 [开发说明](CONTRIBUTING.md)，真实安装与测试结果见 [验证记录](docs/validation.md)。命令 `python -m agent_workspace` 可替代 `aw`。

## 三种空间

```text
AgentWorkspace                  软件开发仓：源码、Skill、测试和文档。
    ↓ 安装
Shared Workspace Repo           应用数据仓，每个 Workspace 一份。
    ├─ main                     共享登记、公共资产、Message、可选 Work。
    ├─ instance/A               A 自己的职责、Skill、资料和历史。
    └─ instance/B               B 自己的职责、Skill、资料和历史。
    ↓ 组织协作
Product Repo                    实际代码、设计及交付成果。
```

V1 的实例身份归属一个 Shared Workspace，但实例有独立的持久工作空间；App 可以管理多个 Workspace。目录或分支独立不等于权限/保密隔离。工具升级不覆盖用户资料，消息 ACK 不表示业务完成。

## 接入状态与限制

**Desktop：** 只连接桌面持有的原生会话，不另起 CLI 抢同一个 writer。现有版本可能仍需手动提供控制接口、捕获当前管道并绑定真实会话 ID，尚不承诺无配置的自动发现与重连。

**托管 Codex：** 已有 app-server 协议实现和隔离协议测试，真实模型、登录、Windows 行为及长期运行仍需实测。

**企业微信：** 可选文本桥接，不是核心依赖。需要使用者安装 SDK、配置 Bot 和凭据；不声称已支持全部多模态或企业微信功能。

**恢复与安全：** 有有限连接重试和发布补齐，但不自动接管失联实例、不重放结果不明的业务。没有完整权限系统或任意 Runtime 的物理隔离。生产环境前应完成相关验收。

详见 [使用与故障说明](docs/usage.md)、[实现状态](docs/implementation.md) 和 [迁仓验证](docs/validation-migration.md)。

## 文档与开发入口

| 文件 | 内容 |
| --- | --- |
| [docs/design.md](docs/design.md) | 唯一产品设计，包括 V1 合同和 V2/V3 后续方向。 |
| [docs/usage.md](docs/usage.md) | 实际命令、Runtime 配置、消息、资产与故障处置。 |
| [docs/implementation.md](docs/implementation.md) | 实现位置、当前限制与下一步验收。 |
| [docs/validation.md](docs/validation.md) | `0.1.0a1` 原始验证记录。 |
| [docs/migration.md](docs/migration.md) | Playbook 来源版本、迁仓范围与维护归属。 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 开发安装、检查、打包与变更边界。 |
| [AGENTS.md](AGENTS.md) | 开发本软件的 Agent 规则，不是产品实例的运行提示词。 |

七个 Skill 随软件在 `src/agent_workspace/resources/skills/` 中维护：`workspace`、`work`、`message`、`agent`、`handoff`、`relay`、`fork`。不在 Playbook 另维护一份。

后续按设计中的 V1 验收项实现管家小组、通用配置和真实会话自动化；V2 研究独立身份参与多个 Workspace，V3 研究统一工作台和同一身份的多事务会话。后两者没有在当前代码中实现，也不是 V1 自动化的前置条件，完整边界见 [设计后续方向](docs/design.md#14-后续方向与来源)。

## 项目归属与许可证

本仓是 AgentWorkspace 的设计、代码、Skill 和验证记录的唯一维护位置。项目从 Playbook 的独立目录迁入，Playbook 此后仅保留仓库入口，不再并行维护实现。

**许可证尚未确定，当前没有新增开源许可授权。** 仓库公开不等于已经采用 MIT、Apache 或其他许可证。尚未发布正式 Release 或 PyPI 包。
