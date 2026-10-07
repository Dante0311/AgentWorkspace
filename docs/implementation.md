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

## 已记录问题（待统一处理）

以下来自 2026-10-06 至 2026-10-07 的本机真实 E2E 及后续只读代码核对，基线为 `1258b622c474beb73f13234c0f00672d8d5b5bbb`（`0.1.0a1`）。本节登记问题与证据更正，尚未实施产品修复，不改变已有能力边界。

本机隔离验收批次 `2026-10-06-1258b62-d1e005bf` 的[脱敏证据归档](evidence/2026-10-06-1258b62/README.md)已随本仓保存，供异地修复会话读取。归档包含完整报告、复核、事件及输入状态、原生运行日志与模拟场景记录，并附校验清单和排除说明。原始凭据、私人资料及未脱敏图片留在本机，不属于公开归档。下文 `reports/`、`review/` 证据文件名均相对于该归档。

### E2E-001：正常停工后输入状态仍为 submitted

**状态：已确认，待修复；优先处理。**

- 现象：受管 Codex 会话在本轮内保存检查点并调用 `agent.stop` 后，原生 turn 已 `completed`，Binding 也已 `released`，但对应输入记录仍为 `submitted`。三次正常停工均出现：`e2e-alpha-second-stop-001`、`M09-beta-stop`、`M10-alpha-reply-stop`，覆盖 Sol 和 Luna。
- 原因：[runtime.py](../src/agent_workspace/runtime.py) 的 `Runner._run_owned` 在 Binding 进入 `stopping` 后，走等待空闲、关闭客户端、`finish_stop` 并退出的分支，跳过后续 `_complete_inputs`，没有将已收到的完成事件写回输入状态。
- 影响：输入状态与实际完成结果不一致，影响状态查询和恢复判断。本次文件、消息、检查点及正常交出已验证；没有证据表明发生业务丢失或重复执行。
- 修复范围：在停工收尾时持久化已确认的输入完成结果，保持检查点和执行权释放顺序。不重放业务，不把未确认或失败的输入一律标成成功；历史记录的处理须依据原生事件单独判断。
- 验证标准：正常会话内停工后，输入状态与对应原生 turn 的真实终态一致，原有检查点和交出结果保持正确。
- 证据：`reports/evidence/R13-final-runtime.json`、`reports/evidence/M18-final-evidence.json`，以及两实例对应 Binding 的原始 `records/<binding>/runtime.jsonl`。

### E2E-002：WorkBuddy Windows 入口与 SDK 启动方式不兼容

**状态：已观察到的接入缺口，待调查；尚未确定具体修复方案。**

- 现象：WorkBuddy 自带 JS CLI 经 Node 启动能够返回帮助和 HY 模型列表，但 `codebuddy-agent-sdk==0.3.267` 直接连接该入口时返回 `WinError 193`（不是有效的 Win32 应用程序）。失败发生在连接前置阶段，未发送模型请求，也未预留 Agent Binding。
- 相关位置：[native_sdk.py](../src/agent_workspace/native_sdk.py) 的 `sdk_options` 将配置的 `executable` 直接传给 SDK；实际可支持的 Windows 入口和启动方式需要核实，不把直接启动 JS 失败泛化为所有 CodeBuddy 入口不可用。
- 独立阻塞：随后使用 SDK 自带 Windows 可执行程序，选择 `hunyuan-2.0-instruct-ioa`，实际请求返回需要 `/login`，未完成业务接手。这只能证明该入口当前要求登录，不能推断 WorkBuddy Desktop 未登录或 HY 不支持。
- 后续范围：先确认并处理所选入口的启动兼容性，再通过该入口的真实认证验证接手。不得静默更换入口、服务或复制桌面凭据；不为适配增加新的聊天客户端。
- 验证标准：受支持的 Windows 入口按用户选择启动，并在有效认证下实际读回旧检查点/资产；仅 help 成功、进程启动或配置保存不算接手通过。
- 证据：`reports/evidence/M14-workbuddy-sdk-connect.json`、`reports/evidence/M18-final-evidence.json`。

HY 失败后停止 Runner 但保留 Binding 执行资格，是当前合同下保留现场的行为，不另记为释放缺陷，也不通过删锁或强制释放处理。模型猜错工具名和尚未实测的 Desktop 不据此登记为已确认 bug。Watch 自动推送与忙时 normal 顺序随后已在 T 批取得真实证据，见下文。

### E2E-003：企微入站误判已撤回，限定模拟业务链通过

**状态：本次入站故障判断不成立，已关闭该问题登记；真实企微授权、模拟修复及恢复报告随后通过，最终由管理端正常收尾。**

- 历史现场：W 批隔离模拟构建失败自动触发真实 Luna 会话，Agent 主动发送的企微通知获得 SDK `errcode=0`，用户截图确认实际可见。正式 Bridge 在等待窗口内没有形成企微入站记录，未执行修复；当时依据用户的发送确认记录为入站阻塞。
- 后续更正：用户说明误解了先前确认的问题，并提出实际回复后继续。因此原发送确认不足以证明授权消息已发出，零入站记录不能认定渠道或产品故障。历史记录与用户更正均保留，没有为此修改产品。
- 真实续测：恢复原实例的合法入口后，Agent 实际读取正确的失败日志和 Job Summary，补齐首轮路径错误造成的证据缺口。2026-10-06 23:58:56（Asia/Shanghai）平台收到真实企微授权；Agent 随后仅创建限定的虚构 tile-B 输入。模拟观察器实际重跑成功，恢复事件再次唤醒 Agent，Agent 回读产物并发送恢复报告；两条群通知均有服务端回执和用户可见确认。
- 证据边界：截图中的 23:51 授权早于正式连接恢复，但平台缺少该消息的原始发送时间，不能断言后来收到的是离线重放。模拟观察器恢复时沿已有事实继续观察新事件，没有重放旧 Binding 的失败事件；不据此声称通用跨 Binding 重放已验证。
- 收尾差异：最后一轮验收指令错误地要求 Agent 通过 `asset.read` 读取受保护的 `.aw-local` 发送账本，导致模型未自行停工。这是验收编排错误，不是已确认产品缺陷。管理端依据真实发送结果和用户确认，经公开入口保存真实检查点并正常停止；没有伪称模型自停、强行释放或新增第 7 轮。
- 最终结果：累计 6 轮 `gpt-6-luna/low`、2 条企微出站；真实授权入站、限定模拟修复、恢复复核和主动汇报通过。Binding 已释放，本轮 Runner、企微及模拟 Bridge 进程均已退出。既有 E2E-001 的历史 `submitted` 状态未修改；不外推为生产 SBP/UE/CI、Desktop 或全部功能验收。
- 证据：`reports/evidence/W10-human-correction.json`、`reports/evidence/W16-business-chain-proof.json`、`reports/evidence/W18-final-facts.json`、`reports/evidence/W18-management-checkpoint-readback.json`、`reports/evidence/W18-process-exit-confirmed.json`；两张群通知截图为 `W09-first-report-visible.png`、`W12-recovery-report-visible.png`，同在 `reports/evidence/`。

### E2E-004：自动交接完成终态未保存，后继停工后回退 starting

**状态：已确认，待修复；P2。**

- 触发与现象：正常自动 transfer 已建立唯一后继并完成 boot；后继仍为当前入口时，公开 `transfer-status` 返回 `completed`，但持久记录仍为 `starting`。后继随后正常停工、释放后，同一公开查询回退为 `starting`。P 批真实交接、渠道续接、业务处理及模型停工均有证据，不能将状态回退误记为接手失败。
- 原因：[transfer.py](../src/agent_workspace/transfer.py) 的 `status` 只在当前 Binding 等于目标时计算完成状态，没有保存结果；自动路径在旧 Runner 退出后调用 `advance`，写入后继启动状态，但没有在后继完成 boot 后自动保存已确认的完成终态。开发仓与固定安装源码一致。
- 影响：已完成事务显示为未完成，完成查询中观察到的 session 信息也随当前入口变化消失。`request` 会据此以旧交接尚未解决为由拒绝新的 request ID；这一后果由调用链确认，未追加真实请求重现。没有证据表明会自动重复创建后继。
- 修复范围：持久保存已经证实的完成终态，使其不依赖当前入口仍然 active；保留唯一固定后继、未知结果不重建和正常停工顺序。不得以手改历史状态、删锁或重新执行业务作为修复。
- 验证标准：真实自动接手完成后，目标停工或后续合法入口变化不使旧事务终态回退；新交接不会被已完成的旧记录阻挡。结果未知的交接仍保持原防重做边界。
- 证据：`reports/evidence/P09-transfer-status.json`、`reports/evidence/P15-final-transfer-status.json`、`reports/evidence/P18-final-facts-with-visibility.json`、`review/P-NORMAL-REVIEW.md`。独立复核认可 P 的限定业务副作用，并单列这一状态缺陷；既有 E2E-001 也仍未修复。

## 本轮新增的正常路径证据

同一固定基线在上述隔离批次继续验证正常使用路径，没有修改产品源码或通过重放未知结果消除失败记录。以下是真实本机验证的限定范围，不代表完整 A–J、所有 Harness 或生产业务已通过：

- **P：同 Codex 自动交接与企微续接。** 原模型自行保存检查点并停工，产品自动启动唯一固定后继；后继实际读取旧材料，接收新群查询并回复，随后自行保存、停工。新增 5 轮 Luna、1 条群回复，具有服务端回执和用户可见确认；不改变 W 最终由管理端收尾的历史事实。证据：`reports/evidence/P18-final-facts-with-visibility.json`。
- **Q：Fork、最小 Work 与第二独立安装。** 从真实检查点创建新身份，保留来源资产而不复制执行权；管理端创建、更新并交付一个最小 Work。同 wheel 的第二独立安装从源码目录外读回同一数据，前后身份、实例文件和共享 refs 不变。此项不冒充模型完成 Work 或新机器迁移。证据：`Q08-Q1-final-facts.json`、`Q13-Q2-final-facts.json`，均位于 `reports/evidence/`。
- **T：Fork 实际会话与 Watch 顺序投递。** Fork 模型亲自发送两条带引用关系的 normal 消息，Watch 自动通知同一接收会话，目标亲自 receive/ACK 并按序保存结果；自然观察到第一轮忙时第二条等待，双方最终自行保存检查点并停工。新增 4 轮 Luna。接收端 boot 有一次原生只读 Shell，未完全遵守测试的 aw_execute-only 指令；消息和保存、停工副作用均有真实平台工具记录。证据：`reports/evidence/T15-final-facts-with-native-trigger.json`。
- **G：管家最小授权与正常维护。** 内置 Maintainer 在真实受限工具中完成未授权拒绝、指定目标授权后写入、撤权后再次拒绝；目标原有资产和撤权后的笔记字节保持不变。一次 `sync-idle` 及相同请求 ID 的读回保留原动作结果，独立复查仍报告既有 `transfer_pending`。这是无远端新变化的正常空闲同步，不是异常恢复证明；目标新笔记仅为本机资产，未进入 Fork 检查点。新增 3 轮 Luna，Maintainer 自行保存检查点、停工，临时授权已撤销，进程已退出。证据：`reports/evidence/G18-final-facts.json`。
- **H/A：项目引用与同数据重启。** 在真实工作台保存并改名 Fork 的项目、分区与虚构产品目录引用，刷新及第二独立安装均读回相同结果。保存只改变本机引用，`native_project_verified=false`；未创建原生项目。两份服务均在各自终端 Ctrl+C 后退出，进程及端口已停止，但工具退出码为 1，未证明 CLI 完整执行了优雅关闭流程。新增模型和群消息均为 0；未另做过期 revision 边界测试。证据：`reports/evidence/H10-final-facts.json`、`reports/evidence/H08-close-and-process-audit.json`。

`review/T-G-NORMAL-REVIEW.md` 独立认可 T/G 的上述限定结果，未发现需新增登记的缺陷；H/A 不属于该次独立复核。上述续测没有修复 E2E-001、E2E-002 或 E2E-004，也没有启动生产 SBP/UE/CI、验证自有模型服务或取得远端 Git 写入证明。原始证据、当前运行状态和完整未测项继续由该批次的验收报告与检查点维护。

## 设计和历史归属

本分支同步文档 PR #2 已确认的产品设计与开发约定，不再保留旧的“初始化不创建管家”作为当前产品合同。底层预览 `App.workspace_init`/旧远端入口仍保留原始行为，用户创建路径使用 onboarding 包装；既有空间不会因接入或升级被隐式迁移。

原始 `0.1.0a1` 的迁仓和验证记录保持原文，分别见 [migration.md](migration.md)、[validation.md](validation.md) 和 [validation-migration.md](validation-migration.md)。不要把当前接入进展回写成历史已经通过的证据。

## 普通会话与项目组织补充

`sessions.py` 复用运行配置生成原生交互 CLI 参数，保存不可变的本机启动回执，不创建 Workspace/持久身份，不解析终端画面或新增对话循环。`desktop_projects.py` 只保存每实例每桌面端的项目/分区名称和产品目录引用，返回同一份随包手动说明。内网 HTTP 配置通过明确的 `allow_http` 共用检查。界面、CLI、权限边界和包装资源同步更新；未提供的原生项目/分区控制仍公开说明。具体操作见 [session-projects.md](session-projects.md)。
