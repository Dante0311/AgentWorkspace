# 当前实现与验证范围

版本仍为 `0.1.0a1` 开发预览。本文随产品源码维护当前能力、限制与验证层次；产品目标以 [design.md](design.md) 为准，操作见 [usage.md](usage.md) 和 [runtime-and-maintenance.md](runtime-and-maintenance.md)。

团队的问题登记、调查、验收脚本和详细报告在 [AW-Workspace 开发仓](https://github.com/Dante0311/AW-Workspace/blob/main/development/README.md)维护。历史结果只证明对应提交和测试范围，不替代当前版本的验收。

## 模块

| 文件 | 当前职责 |
| --- | --- |
| `app.py`、`gitstore.py` | 持久身份/资料、条件提交、可恢复创建、检查点、Binding、Work 和 Git 访问。 |
| `onboarding.py` | 只发现和引导的首次使用、只读 Git 检查、三份管家定义/实例和本机准备。 |
| `harness_config.py` | Codex/Claude 原生模型选项查询、三种受管入口的实例独立模型配置；凭据只保存引用。 |
| `model_profiles.py` | 实例根 Codex 模型选择、本机旧配置迁移、每入口采用快照、适用目录与请求事实。 |
| `runtime.py`、`rpc.py`、`native_sdk.py` | 实际原生入口、持续事件、工具边界、初始接入、独占 Runner 与停工观测。 |
| `transfer.py` | 原绑定和固定后继的持久 handoff/relay，结果未知不重新创建会话。 |
| `shared.py`、`skills.py` | 同一共享提交的职责材料读取，以及共享 Skill 发现、安装、来源比较与受保护更新。 |
| `desktop_projects.py` | 实例主目录匹配的原生项目发现/复用，按实际接口能力执行显式分区准备。 |
| `messages.py` | Message/ACK、Git 发布补齐、FIFO 与当前入口通知。 |
| `maintenance.py` | 作用域授权、健康观测、安装位置归属明确的巡检、有限维修和结果复查。 |
| `bridges.py`、`wecom.py` | 可选外部渠道、文本收发与组件看护。 |
| `commands.py`、`cli.py`、`server.py`、`resources/` | 共用 CLI/HTTP/MCP 分发、本机工作台、首次配置、定义和七个 Skill。 |
| `scripts/install.py`、CI | 可验证制品、空目录隔离安装、源码快照与 wheel/sdist。 |

没有引入通用调度平台、模型网关、ACP 依赖或新的 Agent Loop。SDK 是按需安装的原生客户端，不是我们自研 Harness。元数据探测与实际会话共用凭据路由；Claude 握手返回模型选项，无需发送提示词，自有服务不使用内置目录。

## 已实现的工作流程

创建/接入 Workspace → 选择并保存运行配置 → 为实例建立真实受管会话 → 平台 MCP/动态工具与持续通信 → 保存检查点、确认原端停妥 → 固定后继在同一实例目录接手 → 后续 Message 到达新入口。

Codex Desktop 和受管 CLI 使用[实例模型配置](instance-model-profiles.md)，创建、恢复与 normal 输入显式带模型和推理强度；实例文件的后续编辑不改变当前入口的采用值。缺项与已知不兼容值拒绝，未知能力记录未确认。这项参数合同由 Windows 的配置、Git 与协议测试验证；真实 Desktop 设置效果仍需受控复验，未升级日常安装。

Codex、Claude 和 CodeBuddy 的原生可执行程序已参与回环 API 测试，实际创建 Git 检查点；Claude/CodeBuddy 在同会话第二轮接收 Message 并生成 ACK。本轮还让原生 Codex 通过工具执行 checkpoint/stop，由真实 Runner 自动创建原生 Claude 后继，并验证 `Message.poll` 向后继投递。模型决策由协议夹具指定，不是付费模型质量测试。

三个管家共用普通实例与运行能力。Steward 处理 Workspace 请求，Sentinel 管理用户授权的巡检计划，程序计时和采集事实，Maintainer 只能执行被允许的维修。没有对应执行环境时，创建身份不会假装已启用巡检。

维修动作与复查分开持久记录：动作成功而复查失败时保留动作结果，同一请求仅补复查；不把整个操作降成未知后诱发重做。损坏的本机观测记录报告异常并保留，其他实例仍可检查。普通代理不能凭自己的 active Binding 写另一实例资产，管家也须有对应目标授权；这不是 OS 级隔离。

## 验证层次

- 默认 CI：仅 Windows，覆盖 Python 3.11/3.13、Chromium 工作台和独立 wheel 安装；安装检查包含内置资源和三实例创建。当前不自动运行 Linux 兼容性回归。
- `Native SDK contracts`：Linux 手动工作流，固定 SDK 版本、原生客户端回环 API、平台工具与自动交接；不随 PR 自动运行。实际测试范围以该提交的工作流和日志为准。
- 本机定向回归：恢复、并发前提、未知结果、撤销授权、重复调度、HTTP/CLI 和原生工具副作用。
- 用户实机：已安装 Desktop、真实登录、自有模型服务的实际能力、生产 Git 权限、企业微信、长期在线和新机器体验。

被跳过的原生测试不计为通过；分组有交叉时不累加数量；当前源码不能沿用旧提交的绿色 CI。源码制品只用于准确恢复，长期成果保存在 Git 提交中。

## 当前限制与待验证事项

| 类别 | 内容 |
| --- | --- |
| 已有实现，需实机验收 | 受管三种 CLI 的真实模型/账号、自己的 API、模型和强度生效；生产 Git/凭据；企业微信 Bot；隔离安装和持续运行体验。 |
| 接口仍需核实，不能伪装成只待验收 | Claude/WorkBuddy 原生 Desktop 自动创建、持续投递、停工观测。Codex Desktop 已接入真实控制接口，首次项目和连接仍需准备。 |
| 当前接入未实现的能力 | Claude/CodeBuddy SDK 的已验证 insert/steer；CodeBuddy 模型目录探测目前不提供，字段手工配置并注明 unchecked。不能用中断并重开轮次冒充 insert。 |
| 单独授权事项 | 合并 PR/main、正式版本发布、许可证、生产环境变更。 |

设计目标保留，当前未提供的 Claude/WorkBuddy Desktop 自动化、SDK insert 与 CodeBuddy 目录查询按本版公开限制交付，详见随包维护的[支持范围](../src/agent_workspace/resources/prompts/capabilities.md)。不是声称上游无接口，也不是仅待用户验收；不为补齐功能表强行扩展复杂度。获得可靠接口后再按同一执行权合同增加支持。不静默改用后台 CLI、不将发现程序当作具备控制权，不为绕过接口限制预建新的会话界面。统一聊天、多事务、V2 独立身份、强制接管和通用迁移仍未实现。

## 共同职责、共享 Skill 与桌面准备

共同职责使用 `@workspace-read` 指引并从所属 Workspace 的同一提交读取全文；预检可读不等于模型已读。共享 Skill 可在创建时选择或后续安装、更新，保留来源并保护实例修改；未完成的文件交换须恢复后才能快照、交出或启动。用法见 [共享资料](shared-materials.md)。

Codex 项目准备按可靠 ID 和实例主目录发现、复用已有项目，分区只在实际控制接口支持时显式处理并读回。原生项目创建、文件夹编辑仍需手动准备，不把保存引用或协议夹具当成桌面操作通过。

Windows 测试按文件分四片，保留选择清单与 JUnit。安装检查请求正常服务停机并等待本进程的 HTTP/巡检线程；清理仅对已确认的普通只读文件恢复写位并重试一次。AW 自有的裸仓库初始化明确禁用不需要的符号链接能力探测，修复本机系统临时目录中可复现的探测残留。该条件下的独立安装与清理已通过，但不据此推定所有历史 WinError 145 的根因。

原包 `57446de` 的开发结果和失败证据见 [归档报告](https://github.com/Dante0311/AW-Workspace/blob/5ec6e5e99dcc68b8ec58e701a7ff9d7b119974e8/development/archive/2026-10-10-unified-57446de/docs/evidence/2026-10-09-shared-materials/README.md)。这些结果只对应原包；当前候选的 Windows、浏览器、原生 Desktop 和真实模型效果分别报告。

## Codex Desktop 自动接入（2026-10-08）

已接入已有本地项目的自动创建会话、实例主目录核验、真实会话 ID 绑定、持续投递与同实例交接。项目可通过准备入口发现和复用，分区操作按实际控制接口确认；缺失项目与文件夹设置仍需手动补齐。运行器复用项目，不静默换用 CLI，也不读写应用私有数据库。

桌面发送回执只含聊天 ID，输入通过 `runtime.receive-input` 绑定执行时的真实轮次，再根据该轮原生结束状态保存完成和初始检查点。Desktop CLI 校验真实 `CODEX_THREAD_ID` 与当前 Binding；创建结果不明不另开聊天，停工要求原端 checkpoint、stop 和实际 idle。

Windows Codex Desktop 的限定实测覆盖自动创建、目录和身份绑定、normal Message/ACK、同实例 renew/transfer、新聊天读取旧资产、旧聊天写入被拒以及最终释放与 Runner 退出。失败、模型偏差和控制者干预保留在[完整报告](https://github.com/Dante0311/AW-Workspace/blob/c37ef2e92189adf357dc0e351aff48da9308377f/development/archive/2026-10-09-product-repository/docs/evidence/2026-10-08-codex-desktop-integration/README.md)。其他 Desktop、跨 Harness、busy insert、桌面重启与长期运行不由这次结果代验收。

## 已知异常恢复问题

日常使用曾确认共享仓库读取失败令运行器退出，以及运行器退出后 `stopping` 缺少继续确认交出的路径。当前代码已合入这两项的 Core、Runtime 和维护入口修复，并完成隔离故障与组合开发回归；原 Desktop 入口的恢复和后继接手仍待独立实机复验。正常路径的历史通过结果不替代异常路径复验。具体原因、修复范围和验收要求只在开发仓的 [AW-RUNTIME-001 / AW-RUNTIME-002 登记](https://github.com/Dante0311/AW-Workspace/blob/main/development/issues.md)维护。

当前公共存储已区分读取故障，并补齐停止条件。`RetryableRead` 只表示当前 Git 读取可重试，不能据此重跑投递或整个业务操作；缓存锁忙与普通运行锁冲突分开，权限、TLS、损坏和未知错误不默认重试。Git push 超时按原提交只读核对，确认原提交或其后继包含该提交才成功，否则保留 `outcome_unknown`。GitHub GET 的明确暂时故障采用同一分类，写入及其核对失败不会降成读取重试。

`finish_stop` 可接收 `expected_controller`、`expected_checkpoint` 和 `expected_session`。受管调用方应传入实际停止观测所对应的值，核心在同一共享快照中核对入口、检查点归属和材料，并将相关版本纳入条件提交。重复 stop 不改变原检查点，重复或并发确认只返回匹配的既有 handoff；原入口的已发布结果读回不会改变后继入口。发布结果核对包含快照及 Binding/handoff 内容读取；发布可能发生后的内容读取暂时失败保留 `outcome_unknown`，不能作为停止前读取重试。兼容旧调用方省略观测字段，但不把这一兼容路径当作实际原生观测证明。运行循环已对可恢复读取故障退避并保留原输入进度。独立停止观察过程只继续既有请求；正常启动、`agent.stop`、维护 `continue-stop` 与工作台均可复用该入口，仍须由真实 Harness 确认忙碌、空闲或未知，不以协议夹具代替 Desktop 实测。

[Workbench 0.4](workbench.md) 已接入真实公共操作，支持普通实例与首次三个管家的目录选择、原请求恢复和现有 Codex 项目复用。同一次状态响应的共享元数据、Agent 与 Binding 使用同一 Git 快照；本机观察另行标注。Windows 实际跨 C/D 盘创建、页面操作及独立安装检查已通过，真实账号、模型效果和长期运行仍在独立验收范围。

本批候选、逐次失败及开发验证见[固定版本集成报告](https://github.com/Dante0311/AW-Workspace/blob/a0a1ef18d27d4647ceb8b0807b65541487ebd01b/development/evidence/2026-10-10-unified-integration/README.md)。日常安装未随源码合并而升级。

## 历史验证与追溯

各批次的实际基线、测试数量、源码修复、限定通过、未测项和失败原文见[开发仓归档索引](https://github.com/Dante0311/AW-Workspace/blob/c37ef2e92189adf357dc0e351aff48da9308377f/development/archive/2026-10-09-product-repository/README.md)。旧开发检查点、定向验收规程及 WorkBuddy 接口调查也已迁入该仓；不在产品源码包中保留另一份过程记录。

源码测试、协议夹具、原生客户端回环、真实 Desktop、外部渠道与长期运行分别说明；不能把请求接受、CLI 成功、ACK 或模型回答当作完整业务效果已验证。
