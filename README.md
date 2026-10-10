# AgentWorkspace

**会话可以更换，Agent 的身份与工作资产持续存在。**

AgentWorkspace 为持久 Agent 管理独立工作根、职责、Skill、资料和历史，通过 Git Workspace 通信，并按需使用 Work / Delivery。它操作已有 Harness 的真实会话，不重写模型推理或工具循环，也不要求用户改用新的聊天客户端。

> **`0.1.0a1` 开发预览。** 当前代码已有首次配置、三名管家、受管 Codex/Claude/CodeBuddy、自动交接与维护工具。本批已接入并实测 Windows Codex Desktop 的指定路径，具体结果及限制见下方记录；不代表其他 Desktop、自有模型服务、生产 Git、企业微信或长期运行已经验收。尚未发布正式 Release 或 PyPI 包。

Codex Desktop 已增加在已有本地项目中的自动创建、真实会话绑定、持续投递和同实例交接；需要先准备实例项目并从真实桌面聊天捕获控制连接。操作和限制见 [Codex Desktop](docs/usage.md#42-codex-desktop)，验证范围见 [实现进展](docs/implementation.md#codex-desktop-自动接入2026-10-08)。Claude/WorkBuddy Desktop 本批未接入。

## 本批新增：共同职责与共享 Skill

共同职责可通过 AGENTS.md 的 `@workspace-read` 指引，从所属 Workspace 同一 Git 提交读取；共享 `skills/` 可在创建时选择、后续安装更新，Definition 自带 Skill 保留并保护私人修改。Codex 准备入口发现/复用真实项目，分区仅在实际接口 schema 相符时执行，项目创建及文件夹编辑仍明确手动降级。[使用说明](docs/shared-materials.md)和[统一验收](https://github.com/Dante0311/AW-Workspace/blob/5ec6e5e99dcc68b8ec58e701a7ff9d7b119974e8/development/archive/2026-10-10-unified-57446de/docs/shared-materials-acceptance.md)区分开发回归、原生协议与待执行实机验证。

## 普通会话与桌面项目

工作台和首次配置页可进入“新建普通会话”，在已有目录启动 Codex/Claude Code/CodeBuddy 交互 CLI，无需 Workspace 或 Git。对明确的内网 HTTP 模型地址提供逐配置确认，不保存密钥。持久 Agent 的桌面项目默认按 Agent 复用，Codex 分区按 Workspace 组织；当前提供本机引用、真实项目发现/复用与按实际接口提供的分区准备，不宣称已自动创建原生项目或编辑文件夹。操作及终端限制见 [普通会话与桌面项目](docs/session-projects.md)。

## 使用流程

**安装软件 → 检测 Git 和 Harness → 用户自行补齐 → 创建/接入 Workspace → 配置实例 → 明确启动真实会话。**

普通用户不必下载源码。在所选提交的 GitHub Actions `CI` 中获取 `agent-workspace-build` 制品，解压后使用其中的 wheel、`install.py` 和 `SHA256SUMS`：

```sh
python install.py git_native_agent_workspace-0.1.0a1-py3-none-any.whl --destination ./aw-app
```

需要 Python 3.11+。脚本校验构建包，在空目录隔离安装，不改 PATH，不安装/登录 Git 或 Harness，不改 Workspace 数据。Claude、CodeBuddy 和企业微信分别按需添加 `--extra claude`、`--extra codebuddy`、`--extra wecom`，这会下载对应 SDK 依赖。制品有有效期，不能仅凭相同的预览版本号区分提交；以提交、CI 和校验值为准。

按安装器输出的命令打开本机工作台，例如 POSIX 的 `./aw-app/bin/aw setup --open`，Windows 的 `aw-app\Scripts\aw.exe setup --open`。已有 `aw` 命令时直接运行：

```sh
aw setup --open
```

工作台地址含本机控制 Token，不要分享。Git 和所选 Harness 需要用户自行安装、登录，检测不代装、不改全局配置。支持仅本机 Git 或用户自己提供的远端仓库地址，远端认证复用本机 Git/SSH；读访问成功不等于已验证写权限。

首次使用见 [新机器配置](docs/first-use.md)，受管会话、指定模型服务、自动交接、维护授权和验收步骤见 [运行与维护说明](docs/runtime-and-maintenance.md)。参与开发才需要 clone 源码，见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 当前能力

| 能力 | 实现范围 |
| --- | --- |
| 持久实例 | 独立工作根、AGENTS.md、七个 Skill 和检查点；用户实例不强制 Definition 或 Work。 |
| 首次配置 | Git/Harness 发现、只读 Git 检查、可补齐的初始化；新空间为 Steward、Sentinel、Maintainer 分别选择本机实例目录，不隐式启动。 |
| 模型与会话 | Codex App Server、Claude/CodeBuddy 原生 SDK；实例独立的服务地址、凭据引用、模型/强度配置，持续会话与原生事件。 |
| 通信与交接 | 不可变 Message/ACK、当前 Binding 路由、固定后继的跨 Harness 自动交接；原生客户端对回环 API 的工具与接手测试。 |
| 管家维护 | 明确作用域的委托、健康检查、持久巡检、去重通知、有限维修及独立复查；不强制接管或重放未知业务。 |
| 资产与工作 | 明确文件导入、来源差异与更新、选定共享提升、Fork、可选 Work/Delivery。 |
| 接口与安装 | 一份实现的 CLI、HTTP、MCP、本机工作台和隔离 wheel 安装入口。 |

正常交接不改变 Agent 身份：原会话保存检查点并停工，新会话在同一实例空间接手。手动 handoff/relay 是保底，不是 V1 自动化的替代。统一聊天界面和同一身份的多事务会话仍留到 V3。

## 运行边界

[当前版本支持范围与限制](src/agent_workspace/resources/prompts/capabilities.md)同时提供给用户和 Agent：工作台可查看本机说明，首次进入/relay 提示自动附带，实例 Skill 也指向同一份材料。当前不支持是明确的版本边界，不与尚未验证或临时故障混为一谈；设计目标不是支持承诺。

**Desktop 与 CLI 分开。** CodeBuddy 受管 CLI 不等于 WorkBuddy Desktop。Codex Desktop 仍需实际桌面控制连接和会话绑定，深链打开不代表会话已创建；Claude/WorkBuddy Desktop 自动控制尚未接通。具体缺口见 [能力矩阵](docs/runtime-and-maintenance.md#5-当前能力与验收边界)。

**发现、配置和实际运行分开。** 模型或强度字段保存成功不证明服务支持。SDK 原生工具默认收紧，用户按需明确允许；SDK insert/steer 未验证时明确拒绝，不偷偷改为 normal。

**管家身份和巡检启用分开。** 名字不授予管理员权限。程序负责计时，模型按事务处理；巡检需要 `aw serve`、`aw setup` 或 `aw maintenance run` 进程持续运行，关闭网页不等于停止服务。关机/休眠不继续巡检，不自动注册开机任务。

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
| [Workbench 0.4](docs/workbench.md) | 工作台信息架构、状态依据、目录选择、部分成功与恢复语义。 |
| [基础使用](docs/usage.md) | 基础 CLI、消息、资产、Work 与旧入口说明。 |
| [实现状态](docs/implementation.md) | 当前模块、验证层次和剩余缺口。 |
| [开发协作仓](https://github.com/Dante0311/AW-Workspace/blob/main/development/README.md) | 团队问题、调查、试验代码、交接与详细验证证据。 |
| [开发说明](CONTRIBUTING.md) | 源码安装、测试、打包。 |
| [开发规则](AGENTS.md) | 开发本软件的约定，不是用户实例的职责文件。 |

历史验证和开发过程材料统一保存在 [AW-Workspace 归档](https://github.com/Dante0311/AW-Workspace/blob/c37ef2e92189adf357dc0e351aff48da9308377f/development/archive/2026-10-09-product-repository/README.md)，不拿旧测试结论代替当前提交验证。产品源码、正式测试、CI、安装打包、随包 Skill、设计和使用文档在本仓维护；团队任务、调查、试验与验收脚本、报告和日志在开发协作仓维护。Playbook 保留来源关系，见 [迁仓记录](docs/migration.md)。

## 许可证与发布

许可证尚未确定，没有新增开源许可授权；公开仓库不等于已采用 MIT/Apache 等许可证。当前仅提供开发构建和 PR，正式合并、Release/PyPI 发布和许可证变更须分别授权。
