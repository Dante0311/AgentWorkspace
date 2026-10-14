# 当前实现与验证范围

版本仍为 `0.1.0a1` 开发预览。本文随产品源码维护当前能力、限制与验证层次；产品目标以 [design.md](design.md) 为准，操作见 [usage.md](usage.md) 和 [runtime-and-maintenance.md](runtime-and-maintenance.md)。

**2026-10-13 开发候选：** 当前源码已接入按版本选择的 `.agentworkspace/` 路径、显式可恢复迁移、实例模板配置映射、注册副本的统一材料更新、后台共同恢复和 Web Courier 的受限单条通知接口。软件安装不会自动迁移既有数据；已有 Workspace 继续按登记的布局版本访问，迁移须显式执行。源码回归、安装检查与真实 Desktop/浏览器 E2E 分开记录，历史结果不代表本轮候选已验收。软件维护不要求逐 Agent 在线授权，业务写入仍核对现有执行资格。

团队的问题登记、调查、验收脚本和详细报告在 [AW-Workspace 开发仓](https://github.com/Dante0311/AW-Workspace/blob/main/development/README.md)维护。历史结果只证明对应提交和测试范围，不替代当前版本的验收。

近期优先用户自己的 Codex Desktop 与 ChatGPT Web。Web 保留手动 Message 协议；Web Courier 候选经受限本机连接取得一条原通知，由用户确认后点击一次，网页观察与真实 AW ACK 分别记录。模拟 DOM 与隔离 HTTP 不代替真实 Chrome 加载、ChatGPT 页面及接收工具验收。tclaude 待实际验证。已有 CLI/SDK、模型配置和企业微信接口继续保留，但不作为本轮扩展目标。工作台集中显示 Agent 与环境、消息历史和本机后台；创建、配置和交接通过 CLI、Skills 与原生客户端操作。

## 共用项目与 worktree（2026-10-14 待实现）

用户已授权实现[设计第 3.1.3 节](design.md#313-实例分支与-worktree-自动准备2026-10-14)：保留独立项目选择，支持多个 Agent 共用 Codex 项目；个人资料使用各自实例分支的真实 Git worktree，平台在进入、保存和交接流程中检查并准备；首次进入、handoff、relay 和 fork 明确提供身份、职责及工作背景。工作台后续完善，本轮只使用隔离环境和新建测试实例，不迁移、升级、归档或删除现有 Agent 与资料。

当前代码仍按实例目录匹配 Desktop 项目和会话 cwd，`agent connect` 取得分支文件后准备普通目录，尚未创建 Git worktree。当前目录存在、旧接续测试或这次文档更新都不能证明新路径已实现。Core 负责 worktree、资料保存与同步；Runtime / Adapter 负责共用项目、真实会话识别和交接集成；独立 E2E 按最终提交验证两名 Agent 共用项目、资料分别保存、缺失目录自动准备以及同一 Agent 的正常 handoff/relay。真实跨机器结果另行记录，两个本地目录不算跨机器验收。

## 模块

| 文件 | 当前职责 |
| --- | --- |
| `app.py`、`gitstore.py` | 持久身份/资料、条件提交、可恢复创建、检查点、Binding 历史、本地副本观察、Work 和 Git 访问。 |
| `layout.py`、`migration.py` | 按整体布局版本解析路径，显式迁移共享记录与副本，保留原请求和未知结果，并在复制期间持续互斥。 |
| `software.py` | 统一检查和更新本机注册副本的内置材料；保护用户修改，继续原中断更新，不发布业务检查点。 |
| `onboarding.py` | 只发现和引导的首次使用、只读 Git 检查、三份管家定义/实例和本机准备。 |
| `harness_config.py` | Codex/Claude 原生模型选项查询、三种受管入口的实例独立模型配置；凭据只保存引用。 |
| `model_profiles.py` | `.agentworkspace/config.json` 中的 Codex 模型选择、本机旧配置迁移、每入口采用快照、适用目录与请求事实。 |
| `runtime.py`、`rpc.py`、`native_sdk.py` | 实际原生入口、持续事件、工具边界、初始接入、独占 Runner 与停工观测。 |
| `backend.py` | 每个 AW_HOME 的本机服务、Runner、消息检查与维护线程，原会话共同恢复，以及启停、重启和限定日志读取。 |
| `transfer.py` | 原绑定和固定后继的持久 handoff/relay，结果未知不重新创建会话。 |
| `shared.py`、`skills.py` | 同一共享提交的职责材料读取，以及共享 Skill 发现、安装、来源比较与受保护更新。 |
| `desktop_projects.py` | 实例主目录匹配的原生项目发现/复用，按实际接口能力执行显式分区准备。 |
| `messages.py` | Message/ACK、Git 发布补齐、FIFO 与当前入口通知；通知保留完整原始 JSON，正文异常时使用可信索引。 |
| `direct_messages.py` | 可选原生直发记录的保存、读取及补充缺失回执；不执行原生发送，不接入正式 Message 投递。 |
| `web_courier.py`、`extensions/web-courier/` | 与当前 manual Binding 和网页会话对应的受限连接、原通知单次尝试、网页观察与 ACK 查询；不另建消息队列。 |
| `maintenance.py` | 作用域授权、健康观测、安装位置归属明确的巡检、有限维修和结果复查。 |
| `bridges.py`、`wecom.py` | 可选外部渠道、文本收发与组件看护。 |
| `commands.py`、`cli.py`、`server.py`、`resources/` | 共用 CLI/HTTP/MCP 分发、本机工作台、首次配置、定义和七个 Skill；内置 Skill 的 references/scripts 及固定通知模板随包分发。 |
| `npm/`、`scripts/build_npm.py`、CI | 自带 Python 运行时的 Windows x64 npm 包、实际安装与替换检查、Web Courier 模拟测试和扩展 ZIP；wheel/sdist 和旧安装器保留为底层构建及开发工具。 |

没有引入通用调度平台、模型网关、ACP 依赖或新的 Agent Loop。SDK 是按需安装的原生客户端，不是我们自研 Harness。元数据探测与实际会话共用凭据路由；Claude 握手返回模型选项，无需发送提示词，自有服务不使用内置目录。

## 已实现的工作流程

安装 npm 包并启动本机后台 → 创建/接入 Workspace 与 Agent → 通过原生客户端和 Skills 进入真实会话 → 协作并查看历史 → 保存检查点、确认正常交出 → 后继继续同一 Agent。

本机后台按 AW_HOME 持有唯一服务锁，在同一进程内管理现有 Runner、消息检查与维护线程。重启复用能核对原 Binding、执行位置和原生会话的入口；从未尝试的 queued 输入仍按已有授权继续，已提交或结果未知的输入不重放。缺少来源、旧 controller 未释放或创建结果未知时保留原因，不重建聊天。用户暂停和巡检启停选择保留。后台停止请求与实际进程退出分别显示，停止后台不等于 Agent 已交出，也不证明原生聊天停止。

Agent 身份、执行会话、运行环境与本地副本分开表示。`agent.show` 保留所有已登记副本的本机观察，顶层当前观察必须匹配同一 Binding、原生会话和已知执行位置；旧副本不会覆盖当前会话。`agent.history` 返回同一共享快照中的 Binding 历史。新 Binding 保存实际安装位置与目录，旧记录缺失的来源保持未知；这些本机位置记录本身不证明两个聊天同机。

`agent.takeover` 是用户管理操作，必须指定当前 Binding、保存检查点并显式确认。它通过条件提交撤销旧资格并保存 forced handoff，后继复用 `agent.start`；不停止原生聊天，不自动启动后继，不搬迁未保存资料。重复原请求只读取原结果，普通 Agent 和管家不得调用。隔离 Git 用例覆盖旧入口失权、重复请求不影响后继和原写入未知；真实 Desktop 与跨机器效果仍须单独验收。

自动 renew/transfer 只能继续原正常交接：原 handoff ID 随同续接传到 Core 的条件写，不能消费其间另一次强制接手留下的新 handoff，也不能复用另一条 starting Binding。原并发失败场景已经独立复验，旧请求被拒、新 handoff 未消费，没有额外 Binding、原生创建或输入；这不等同于真实模型的自动交接验收。

`runtime.launch-show` 只读展示原创建回执中的有限字段。用户可通过 `runtime.reconcile-create` 认领原回执的真实 threadId，程序只读核对原 ID、本机目录、状态和已采用模型，再登记同一会话。丢失真实 ID、原 controller 未释放或来源不明时保留未知或拒绝；不会凭同目录候选猜测，不创建或发送原生输入。原 bind 回报丢失可读回同一结果，已有 boot 输入保持原字节。成功不自动开始观察，须由用户显式 `runtime.start`。隔离 Git 和只读原生协议夹具通过，真实 Desktop 故障恢复仍待实测。

`agent.fork --resume` 核对原来源、检查点、名称和目标 ID，复用已保存的目标分支与登记，只补目录等缺失步骤，不覆盖已有用户修改。新版分支 `.agentworkspace/fork.json` 保存来源，本机原发表凭据阻止未知写入被重放；它不是另一份 Agent 身份登记。隔离 Git 已验证分支、登记和目录阶段的失败继续。旧 Fork 未包含来源记录时不支持新 resume，已登记的旧目标仍可 `agent connect`，本轮不改写封存的历史分支。

Codex Desktop 和受管 CLI 使用[实例模型配置](instance-model-profiles.md)，创建、恢复与 normal 输入显式带模型和推理强度；实例文件的后续编辑不改变当前入口的采用值。缺项与已知不兼容值拒绝，未知能力记录未确认。这项参数合同由 Windows 的配置、Git 与协议测试验证；真实 Desktop 设置效果仍需受控复验，未升级日常安装。

历史开发验证中，Codex、Claude 和 CodeBuddy 的原生可执行程序参与回环 API 测试并实际创建 Git 检查点；Claude/CodeBuddy 在同会话第二轮接收 Message 并生成 ACK。原生 Codex 也曾通过工具执行 checkpoint/stop，由真实 Runner 自动创建原生 Claude 后继，并验证 `Message.poll` 向后继投递。模型决策由协议夹具指定，不是付费模型质量测试，也不代替当前源码的回归。

三个管家共用普通实例与运行能力。Steward 处理 Workspace 请求，Sentinel 管理用户授权的巡检计划，程序计时和采集事实，Maintainer 只能执行被允许的维修。没有对应执行环境时，创建身份不会假装已启用巡检。

维修动作与复查分开持久记录：动作成功而复查失败时保留动作结果，同一请求仅补复查；不把整个操作降成未知后诱发重做。损坏的本机观测记录报告异常并保留，其他实例仍可检查。普通代理不能凭自己的 active Binding 写另一实例资产，管家也须有对应目标授权；这不是 OS 级隔离。

Message 通知使用一份随包 JSON 模板，附完整存储原文并保留未知字段；缺失或损坏正文改附可信索引。正文暂时读取故障在登记投递尝试前返回，FIFO、忙时等待、insert、当前入口、有限重试与并发规则继续使用原实现。

message Skill 同时指导 AW 工具和手动 Git Backend 操作，包含精确协议、仓库工具步骤及可选的独立 Python/Git 脚本。脚本不依赖 AW，不创建身份或入口；对原操作保留字节、条件提交、部分成功与结果未知，不将私有操作文件冒充 AW receipt。新实例获得完整 Skill 树，工具升级沿用现有资源哈希保护，用户修改或新增同路径材料时停止覆盖。

每次发送与回复由 Skill 核对双方当前有效入口和当次本机 Codex 观察，再选择原生直发或正式 Message。`direct-message.record/list/show` 将可选直发历史单独保存在调用方 Workspace 的 `.agentworkspace/direct-messages/`，不双写收件方空间，不进入正式索引、ACK、FIFO 或重试。保存失败不影响交流；原生发送结果未知只核对原发送。保存和读取接口已有隔离 Git 验证，真实客户端中的发送及模型遵循新版 Skill 仍需按最终版本实测。

## 验证层次

- 默认 CI：仅 Windows，配置 Python 3.11/3.13、Chromium 工作台、独立 npm 与 wheel 安装检查；npm 检查使用包内运行时并移除 PATH 中的系统 Python，覆盖资源、CLI/HTTP 和替换程序后保留原数据。当前不自动运行 Linux 兼容性回归；配置了检查不等于该提交已通过 CI。
- `Native SDK contracts`：Linux 手动工作流，固定 SDK 版本、原生客户端回环 API、平台工具与自动交接；不随 PR 自动运行。实际测试范围以该提交的工作流和日志为准。
- 本机定向回归：恢复、并发前提、未知结果、撤销授权、重复调度、HTTP/CLI 和原生工具副作用。
- 近期用户实机：真实 Codex Desktop、ChatGPT Web 手动收件、生产 Git 权限、跨机器、长期在线和新机器体验。其他 Harness、自有模型服务和企业微信保留各自历史范围，不由本轮代验收。

被跳过的原生测试不计为通过；分组有交叉时不累加数量；当前源码不能沿用旧提交的绿色 CI。源码制品只用于准确恢复，长期成果保存在 Git 提交中。

2026-10-11 本机候选的实际安装包、校验值、独立浏览器与并发复验，以及历次失败见[固定版本实现与验证报告](https://github.com/Dante0311/AW-Workspace/blob/27eef03d5d23a18f5e7e232866261a77d8a182df/development/evidence/2026-10-11-focused-collaboration/README.md)。报告中的受测提交与产物各有明确来源；远端 CI、真实客户端和日常安装不沿用本机隔离检查的结论。

## 当前限制与待验证事项

| 类别 | 内容 |
| --- | --- |
| 近期需实机验收 | 当前产物的 Codex Desktop 同机协作、正常与异常交接、Web 手动收件、真实跨机器、生产 Git/凭据及持续运行体验。 |
| 保留的高级接口 | 受管三种 CLI、自己的 API、模型/强度、企业微信 Bot；已有开发测试不证明具体账号和服务可用，暂缓继续扩展。 |
| Message 手动路径待验证环境 | 隔离本地 Git 可验证协议和辅助脚本；真实云端 GitHub 工具权限、条件更新语义及 Harness/模型按新版通知与 Skill 收件，需要在具体环境单独验证。 |
| 接口仍需核实，不能伪装成只待验收 | Claude/WorkBuddy 原生 Desktop 自动创建、持续投递、停工观测。Codex Desktop 已接入真实控制接口，首次项目和连接仍需准备。 |
| 当前接入未实现的能力 | Claude/CodeBuddy SDK 的已验证 insert/steer；CodeBuddy 模型目录探测目前不提供，字段手工配置并注明 unchecked。不能用中断并重开轮次冒充 insert。 |
| 单独授权事项 | 合并 PR/main、正式版本发布、许可证、生产环境变更。 |

当前未提供的 Claude/WorkBuddy Desktop 自动化、SDK insert 与 CodeBuddy 目录查询按本版公开限制说明，详见随包维护的[支持范围](../src/agent_workspace/resources/prompts/capabilities.md)。这不是声称上游无接口，也不是仅待用户验收；不为补齐功能表强行扩展复杂度。后续如获授权并取得可靠接口，再按同一执行权规则增加支持。不静默改用后台 CLI，不将发现程序当作具备控制权，不为绕过接口限制预建新的会话界面。统一聊天、多事务、V2 独立身份和通用迁移仍留待后续。

## 共同职责、共享 Skill 与桌面准备

共同职责使用 `@workspace-read` 指引并从所属 Workspace 的同一提交读取全文；预检可读不等于模型已读。共享 Skill 可在创建时选择或后续安装、更新，保留来源并保护实例修改；未完成的文件交换须恢复后才能快照、交出或启动。用法见 [共享资料](shared-materials.md)。

Codex 项目准备按可靠 ID 和实例主目录发现、复用已有项目，分区只在实际控制接口支持时显式处理并读回。原生项目创建、文件夹编辑仍需手动准备，不把保存引用或协议夹具当成桌面操作通过。

Windows 测试按文件分八片，保留选择清单与 JUnit。安装检查请求正常服务停机并等待本进程的 HTTP/巡检线程；清理仅对已确认的普通只读文件恢复写位并重试一次。AW 自有的裸仓库初始化明确禁用不需要的符号链接能力探测，修复本机系统临时目录中可复现的探测残留。该条件下的独立安装与清理曾通过，但不据此推定所有历史 WinError 145 的根因，也不代替当前包的安装检查。

原包 `57446de` 的开发结果和失败证据见 [归档报告](https://github.com/Dante0311/AW-Workspace/blob/5ec6e5e99dcc68b8ec58e701a7ff9d7b119974e8/development/archive/2026-10-10-unified-57446de/docs/evidence/2026-10-09-shared-materials/README.md)。这些结果只对应原包；当前候选的 Windows、浏览器、原生 Desktop 和真实模型效果分别报告。

## Codex Desktop 自动接入（2026-10-08）

已接入已有本地项目的自动创建会话、实例主目录核验、真实会话 ID 绑定、持续投递与同实例交接。项目可通过准备入口发现和复用，分区操作按实际控制接口确认；缺失项目与文件夹设置仍需手动补齐。运行器复用项目，不静默换用 CLI，也不读写应用私有数据库。

桌面发送回执只含聊天 ID，输入通过 `runtime.receive-input` 绑定执行时的真实轮次，再根据该轮原生结束状态保存完成和初始检查点。Desktop CLI 校验真实 `CODEX_THREAD_ID` 与当前 Binding；创建结果不明不另开聊天，停工要求原端 checkpoint、stop 和实际 idle。

Windows Codex Desktop 的限定实测覆盖自动创建、目录和身份绑定、normal Message/ACK、同实例 renew/transfer、新聊天读取旧资产、旧聊天写入被拒以及最终释放与 Runner 退出。失败、模型偏差和控制者干预保留在[完整报告](https://github.com/Dante0311/AW-Workspace/blob/c37ef2e92189adf357dc0e351aff48da9308377f/development/archive/2026-10-09-product-repository/docs/evidence/2026-10-08-codex-desktop-integration/README.md)。其他 Desktop、跨 Harness、busy insert、桌面重启与长期运行不由这次结果代验收。

## 已知异常恢复问题

日常使用曾确认共享仓库读取失败令运行器退出，以及运行器退出后 `stopping` 缺少继续确认交出的路径。当前代码已合入这两项的 Core、Runtime 和维护入口修复，并完成隔离故障与组合开发回归；原 Desktop 入口的恢复和后继接手仍待独立实机复验。正常路径的历史通过结果不替代异常路径复验。具体原因、修复范围和验收要求只在开发仓的 [AW-RUNTIME-001 / AW-RUNTIME-002 登记](https://github.com/Dante0311/AW-Workspace/blob/main/development/issues.md)维护。

当前公共存储已区分读取故障，并补齐停止条件。`RetryableRead` 只表示当前 Git 读取可重试，不能据此重跑投递或整个业务操作；缓存锁忙与普通运行锁冲突分开，权限、TLS、损坏和未知错误不默认重试。Git push 超时按原提交只读核对，确认原提交或其后继包含该提交才成功，否则保留 `outcome_unknown`。GitHub GET 的明确暂时故障采用同一分类，写入及其核对失败不会降成读取重试。

`finish_stop` 可接收 `expected_controller`、`expected_checkpoint` 和 `expected_session`。受管调用方应传入实际停止观测所对应的值，核心在同一共享快照中核对入口、检查点归属和材料，并将相关版本纳入条件提交。重复 stop 不改变原检查点，重复或并发确认只返回匹配的既有 handoff；原入口的已发布结果读回不会改变后继入口。发布结果核对包含快照及 Binding/handoff 内容读取；发布可能发生后的内容读取暂时失败保留 `outcome_unknown`，不能作为停止前读取重试。兼容旧调用方省略观测字段，但不把这一兼容路径当作实际原生观测证明。运行循环已对可恢复读取故障退避并保留原输入进度。独立停止观察过程只继续既有请求；正常启动、`agent.stop`、维护 `continue-stop` 与工作台均可复用该入口，仍须由真实 Harness 确认忙碌、空闲或未知，不以协议夹具代替 Desktop 实测。

[工作台](workbench.md) 的共享元数据、Agent 与 Binding 使用同一次 Git 快照，本机观察另行标注。精简后的主界面保留原请求读取与已有服务能力，具体界面范围以该说明为准。旧 Workbench 0.4 的 Windows 跨 C/D 盘创建、页面操作和独立安装曾通过限定检查，不能据此把当前界面或新增后台判为已验收。

上一批候选、逐次失败及开发验证见[固定版本集成报告](https://github.com/Dante0311/AW-Workspace/blob/a0a1ef18d27d4647ceb8b0807b65541487ebd01b/development/evidence/2026-10-10-unified-integration/README.md)。日常安装未随源码合并而升级。

## 历史验证与追溯

各批次的实际基线、测试数量、源码修复、限定通过、未测项和失败原文见[开发仓归档索引](https://github.com/Dante0311/AW-Workspace/blob/c37ef2e92189adf357dc0e351aff48da9308377f/development/archive/2026-10-09-product-repository/README.md)。旧开发检查点、定向验收规程及 WorkBuddy 接口调查也已迁入该仓；不在产品源码包中保留另一份过程记录。

源码测试、协议夹具、原生客户端回环、真实 Desktop、外部渠道与长期运行分别说明；不能把请求接受、CLI 成功、ACK 或模型回答当作完整业务效果已验证。
