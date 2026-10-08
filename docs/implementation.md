# V1 实现进展

本页描述当前功能分支的实现事实，不替代 [design.md](design.md)。版本仍为 `0.1.0a1`，不是已完成全部目标和实机验收的正式 V1。实际恢复位置与逐次测试见 [development-checkpoint.md](development-checkpoint.md)，操作见 [runtime-and-maintenance.md](runtime-and-maintenance.md)。

2026-10-07 修复后 Windows 定向实测已完成：E2E-004 与 E2E-001 普通停工路径取得限定通过；E2E-001 busy insert/steer 残余、E2E-002 原 WorkBuddy 无扩展名入口启动失败仍待修。完整范围见下文“修复后 Windows 实机结果”和[新批次证据](evidence/2026-10-07-5aaae00/README.md)，历史登记不覆盖。

2026-10-08 用户配合补测：无 Workspace 普通会话在真实 Windows 终端完成两轮对话、原请求防重与退出核对，取得限定通过；启动兼容提示和未取得详情的瞬时警告保留。[本批完整证据](evidence/2026-10-08-5aaae00-ordinary/README.md)。

同日桌面项目补测：工作台引用保存、改名、刷新和冲突保护通过；用户实际建立的 Codex 项目保留实例主目录与同一项目 ID，并手动归入匹配分区。该结论不包含原生 Desktop 会话、Binding 或自动交接。[本批完整证据](evidence/2026-10-08-5aaae00-desktop/README.md)。

同日自主补测：无控制者纠偏的 normal Watch 与管家发布故障恢复取得限定实机通过，共 9 个 Codex 模型轮次；初始化工具约束、参数与笔记偏差保留。Desktop 真实控制连接和 busy 状态只读验证通过；该批 tclaude 为选型前的无模型 SDK 预检。[执行报告、独立复核与完整证据](evidence/2026-10-08-5aaae00-autonomous/README.md)。随后用户选择 DeepSeek，新增 3 个 Codex 轮次、2 次 tclaude query，公开完整配置路径的跨 Harness 交接、消息 ACK 与本人停工限定通过；便捷入口不接受模型 ID 方括号的问题及工具遵循偏差仍保留。[DeepSeek 增量报告与独立复核](evidence/2026-10-08-5aaae00-deepseek/README.md)。

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

## 后续体验补充（待统一实现）

2026-10-08 用户决定当前优先推进 Codex 桌面接入。WorkBuddy 桌面的接口可行性调查由另一个会话独立进行；[调查交接说明](workbuddy-desktop-investigation.md)列出已知事实、待确认能力及用户配合边界。该分工不代表 WorkBuddy 已支持，也不将其 CLI 启动缺陷与桌面调查混同。

### Codex 项目与分区的轻量自动准备（2026-10-08）

用户已确认记录此需求，后续统一补充；当前只登记，不代表已实现，不改变随包能力说明。它是首次使用的辅助准备，不替代持久 Agent 运行、通信、交接和恢复的核心验收。

- 首次从工作台选择 Codex 使用实例时，发现已有原生项目与分区。优先按已保存项目 ID、实例主目录明确匹配并复用；重名不能作为唯一依据，多候选或目录冲突才请用户选择。
- 没有对应项目时，预填建议项目名、实例主目录及所选产品目录，允许修改或选择已有项目；有可靠原生接口时提供一次“按建议创建并继续”。分区可复用或按建议新建，也可跳过，不应阻塞核心运行流程。
- 后续使用复用原项目；保存可靠的关联信息，用户自行改名或移动后保留其布局，不强行搬回默认分区，不为每次会话或所有 Harness 批量创建项目。
- 接口缺失时集中提供一次手动补齐说明，完成后统一核对实际结果；不逐按钮教学，不把填写本机引用写成原生创建成功。
- 接入前确认独立工作台可用的原生控制通道及实际接口。当前聊天可用的项目/分区读取、分区创建和项目移动工具不等于工作台已接通；项目创建、编辑及文件夹设置入口仍需核实。不读写应用私有数据库，不另建项目管理系统。
- 最小验收覆盖发现并复用、按建议创建或明确降级、重复操作不重复创建，以及实例主目录正确；原生会话与 Binding/交接仍分别验收。

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

## E2E 定向修复进展（2026-10-07）

上面的 E2E-001 至 E2E-004 保留为 `1258b62` 的历史登记，不改写原失败、撤回与验收结果。本轮基于已提交登记的 `c1f747b` 隔离副本，仅修本节列出的代码；不读取或改写用户旧账本、旧 transfer、锁、alpha 的 HY 资格，不运行完整 A–J。

- **E2E-004：代码已修，官方登录实机复测待执行。** 后继 Runner 在 boot 完成并具有已保存检查点后，主动通过原 `transfer.lock` 保存 `completed` 和真实 session。该锁避免快速后继被原启动步骤的 `starting` 回写覆盖；旧 Runner 不能写另一笔交接。查询仍只读；后继停工后终态保留，新的合法交接可归档旧请求，相同 ID 不重启。
- **E2E-001：代码已修，官方登录实机复测待执行。** 正常停工先关闭原生客户端，再写入按 turn ID 匹配的完成事件，最后执行原有释放步骤。失败事件仍记失败，无事件的 submitted、queued、未知结果及其他 Binding 不改写。若 boot 本轮自行停工，只在有成功完成事件时引用原显式停工检查点，不在关闭客户端后再创建一份自动初始快照。
- **开发验证：** 定向状态/运行器/防重做组 121 passed；另一个真实 Codex 客户端配合回环模型夹具的限定正常链路 1 passed，覆盖两次交接、后继读旧资产并自行停工、后续合法新交接、旧请求读回，以及对应输入/原生事件/释放一致。不是用户的官方 `gpt-6-luna/low` 验收，不外推到 Desktop 或 Windows。

- **E2E-002：启动适配已补，Windows / 认证 / 真实接手仍分项待验收。** 已核对固定 `codebuddy-agent-sdk==0.3.267` 的真实 options、Client 和 SubprocessTransport：原路径直接作为进程入口，没有解释器前缀选项。仅对 Windows 明确选择的 `.js/.cjs/.mjs` 入口，用 SDK 的公开 custom transport 接口复用其 SubprocessTransport，仅覆盖 Node 路径及 argv 前缀；未复制协议/环境/进程清理逻辑。Node 必须已在 PATH，缺失或只有批处理包装时，在预留 Binding / 发起 handoff 前报错。原 `.exe` 路径不改变；不换服务、不复制桌面凭据、不自动 `/login`。真实 SDK + Node 协议夹具及相邻回归 29 passed；当前 Linux 环境只模拟 Windows 的入口选择条件，不冒充 Windows 内核或 WorkBuddy 的真实认证。夹具中的 `/login` 结果仍失败且不自动释放资格，真实 HY 阻塞尚未解除。

复测范围与步骤见 [E2E 修复后定向验收](e2e-repair-acceptance.md)。未取得真实环境证据前，不关闭这两项验收登记。原始报告和日志仍留在用户本机，本轮依据已提交摘要及用户交接说明，不声称已经读取这些原始文件。

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

### 本批整合交付（2026-10-07）

用户随后授权将两项修复推送并合入 `main`。整合以 `5ea4605` 为基线，保留已归档的原始 E2E 报告/日志以及 E2E-003 更正；产品代码没有在整合中扩展。[本次修复与验证记录](evidence/2026-10-07-e2e-fixes/README.md)附上三组重新执行的结果、修复前失败、来源和归档校验。上述“待修复”是原验收时的历史状态；目前为代码已修、官方账号/Windows/认证真实复测待完成，不能把开发回归通过追写成原基线验收通过。

### 修复后 Windows 实机结果（2026-10-07）

用户授权拉取修复后继续独立测试。本批固定产品提交 `5aaae00520374b022e0c38fa21f312f8e08629ba`，使用新隔离安装、数据与请求 ID，官方登录 `gpt-6-luna/low`；没有修改产品源码、旧账本、旧交接或旧 HY 资格。上节“复测待完成”是合入时的状态，当前以本节和[完整执行报告及独立复核](evidence/2026-10-07-5aaae00/README.md)为准。

- **E2E-004：本轮同 Codex 范围通过。** 两笔自动交接均在首次公开状态查询前已持久保存 completed/session；后继自行停工后终态仍保留。相同旧 ID 仅读回原结果，没有额外输入/轮次；新合法入口与新交接成功，归档旧 ID 可读。未调用 advance/transfer-continue 推进结果。
- **E2E-001：普通路径通过，busy insert/steer 残余仍待修。** 普通 boot/handoff/normal 的匹配完成事件、输入终态、显式检查点及释放一致，boot 自停复用显式快照。但一次忙碌时的公开 insert 返回顶层 `result.turnId`，`runtime.py` 的 `_complete_inputs` 仅读 `result.turn.id`；该原生轮次已 completed，输入仍 submitted。不是所有 insert 都失败，也没有证据表明 submitted 被自动重放。保留现场，不手改或重发已执行输入。[回执与完成事件对照](evidence/2026-10-07-5aaae00/reports/evidence/87-steer-terminal-ledger-mismatch.json)。
- **E2E-002：实际入口启动失败，认证未到达。** 原选 WorkBuddy `resources/app.asar.unpacked/cli/bin/codebuddy` 是无扩展名 JS，未进入 `.js/.cjs/.mjs` 的 Node 适配。Node 已存在、固定 SDK 0.3.267 的真实 connect 仍 WinError 193；不能写成仅待登录或以 `.cjs` 协议夹具通过代替原入口启动。[真实控制连接](evidence/2026-10-07-5aaae00/reports/evidence/24-workbuddy-real-js-control.json)。
- **Watch：限定副作用成立，存在一次管理端介入。** 两条本人 send/receive/ACK、同 session 顺序资产及双方本人 checkpoint/stop 已核对。第一通知轮在同轮等待第二通知，管理端一次 steer 澄清后才结束；无人介入自然流程未取得完整通过证据，不将该等待直接归因平台延迟。
- **计数与收尾：** 13/13 原生轮次完成，12 个输入中 11 completed、1 submitted；两个测试实例 released、Runner 退出、最终进程审计无残留。121 项首跑 120 passed / 1 环境导入失败，安装同 wheel 后仅失败用例重查 1 passed；SDK 首跑 24 passed / 5 缺依赖 skipped，补固定依赖后仅原 5 项 5 passed。保留原失败、selector 零用例错误及模型参数/命名偏差，未重跑全部组制造首跑全绿。

报告、检查点、独立复核、操作/事件 ID、定向测试日志、来源与归档 SHA256 及脱敏排除说明已按批次入仓。没有新增 Desktop、企微、自有服务、跨 Harness 真实业务、生产 UE/CI、远端 Git 业务、长期运行或完整 A–J 的证明；历史失败不被本次限定通过覆盖。

### 无 Workspace 普通会话实机补测（2026-10-08）

同一固定产品基线 `5aaae00`，沿用已验证隔离安装，但使用新空 ordinary-home 与虚构产品目录；本机 Codex CLI 已更新为 `0.162.0-alpha.2`，版本与可执行文件摘要另记。用户亲自点击工作台启动，并在真实 Windows Terminal 完成 `gpt-6-luna / low` 两轮对话：第一轮读取随机标记文件，第二轮在同一终端依上下文返回正确组合，未见第二轮工具调用。测试文件内容及列表均未变，未创建 Workspace registry、实例或 Binding。

真实页面的只读刷新、继续原请求一次及整页刷新后，启动记录逐字节不变、请求总数1、原生PID保持。用户 `/quit` 后记录 `native_exited`、returncode=0，原生与包装进程均退出；随后工作台 Ctrl+C，进程和端口停止，但服务终端返回1，不混同原生会话的正常退出码。

启动时 `TERM=dumb` 兼容提示需用户确认，控制者启动环境确有该值，目标进程环境未直接检查；另两条瞬时 warnings 后来不再显示，详情未知，不登记为已定位产品缺陷或宣称已修复。原生 session ID未另取，工作台仍如实返回 `not_observed`，真实对话依据来自用户截图和控制者核对。本批无第二执行者独立复核；[完整报告、复核记录及脱敏证据](evidence/2026-10-08-5aaae00-ordinary/README.md)保留过程与校验值。未验证双击竞态、丢失响应故障注入、其他Harness、自有服务或Desktop自动化；前批两个残余缺陷不因本组通过而关闭。

### 桌面项目与分区手动补测（2026-10-08）

固定产品基线仍为 `5aaae00`，新建独立数据及一个未运行测试实例。真实工作台完成本机引用保存、整页刷新、改名和再次读回；旧 revision 的 HTTP 覆盖请求返回 409/conflict，最终引用不变。

用户手动建立 Codex 本地项目、关联文件夹并归入与引用名称一致的分区。原生只读接口确认最终项目 ID 与最初创建时一致、实例主目录保持、测试根下只有一个项目，目标分区包含该项目。用户截图显示实例目录为“主要”、产品目录作为另一文件夹；完整附加路径和 Desktop 应用版本号未独立取得。平台仍如实返回 `manual_setup_required` / `native_project_verified=false`，人工核对结论另列。

产品文件未变，实例 `current=null` / `has_run=false`；没有启动模型、原生 Desktop 对话、Binding、handoff 或 relay，也不将本次项目整理复用写成多会话运行证明。服务 Ctrl+C 返回1，进程/端口已停止；本机测试项目、分区和数据保留。本批为用户操作及控制者复核，无第二执行者独立复核；[完整报告与证据](evidence/2026-10-08-5aaae00-desktop/README.md)记录来源/归档摘要及排除范围。

### 自主通信、管家恢复与接入预检（2026-10-08）

用户授权补齐当前可自主运行的实机用例。本批仍固定产品 `5aaae00` 与同一已校验 wheel，但新建隔离安装、AW_HOME、两个 Workspace 及测试实例，未修产品或旧现场。官方 Codex `gpt-6-luna/low` 共 9 个原生轮次，started/completed 均为 9；[完整报告及独立复核](evidence/2026-10-08-5aaae00-autonomous/README.md)按新批次保留。

- **normal Watch：通信阶段无控制者纠偏，限定通过。** 4 轮完成两条 normal 消息、同一接收 session 的顺序资产、本人 ACK/checkpoint/stop。首次 boot 提前 receive 被拒绝、无效参数自行纠正、发送者笔记抄错第二条 from.agent 的偏差保留；真实消息/回执均为正确发送者，不以手抄笔记替代原始记录，也不称初始化严格遵循通过。
- **管家 publication-reconcile：真实故障恢复闭环限定通过。** 控制者在可丢弃 bare Git authority 临时拒绝 main 推送，单次公开测试消息自然留下 pending；恢复底层写入条件后，正式 30 秒巡检通知 Sentinel，模型发送维修任务，Maintainer 经限定命令/目标授权补齐原消息，Sentinel 本人重新核对 operation 和 doctor。5 轮完成，实际 result=published，目标异常消失，已知 applied 的同维修 ID 回读未重复动作。控制者恢复 Git 条件不冒称维修员修复权限；不外推 unknown 结果重试或其他维修动作。
- **工具遵循与清理：** Maintainer boot 的三次只读 Shell 尝试（两次失败、一次读取实例资料）及 Sentinel 初始化额外动作不符合严格测试指令，真正维修仍经受限平台工具完成。编排误判 pending 退出码的过程保留，接续未重发或重新注入。四个模型实例 released、Runner 退出，巡检关闭、授权撤销、临时 Git 配置恢复；给未启动 steward 的一条未读测试刺激保留，不代 ACK。共享原生服务归属未确认，不宣称全机服务清零。
- **Desktop：真实只读控制部分通过。** 固定产品适配器连接本机已校验的 App Tools 安装组件，发现创建聊天/读状态/发消息等接口并读回当前调用聊天 busy，所建 RPC 进程已退出；退出方式未留证。未创建原生聊天或 Binding，也未投递/交接。产品 Desktop start 仍仅准备提示和深链，自动 transfer 仍拒绝 Desktop；上游接口存在不等于产品已完成接入。
- **tclaude：无模型预检通过，真实交接未运行。** 用户指定已登录的内部包装器，使用其 Windows 原生入口，wrapper 0.1.8/upstream Claude Code 2.1.251、SDK 0.2.163 的 connect/get_server_info 成功，认证仍为 configured_unverified，query=0。等待用户模型选择后才增量执行 Codex → tclaude；该状态不是兼容性失败，更不证明 WorkBuddy 已修复。

独立复核另列 `message.reconcile` 授权与受限维修入口可能不一致的静态疑点，尚未做实际越权测试或修复，不将指定路径通过扩成所有补齐入口授权闭合。E2E-001 busy insert/steer 与 E2E-002 原 WorkBuddy 入口缺陷仍保留。新包提供源/中间/最终归档 SHA256、必要日志、原生事件和排除说明；不含凭据、完整私人聊天、机器路径或可运行测试状态。

### Codex → tclaude / DeepSeek 真实交接增量（2026-10-08）

用户随后选择 DeepSeek，从 tclaude 实际目录选用 `claude-deepseek-v4.1-flash[1m]`、配置 `low`，沿用已登录的内部包装器及服务。固定产品仍为 `5aaae00`，复用已核验隔离安装、新建 Workspace 和实例；未修改产品源码或全局配置。选型前的 query=0 报告保持历史事实，[本增量报告、独立复核与证据](evidence/2026-10-08-5aaae00-deepseek/README.md)另行归档。

公开 `agent.configure-sdk` 在模型调用前拒绝 ID 中的方括号，是已复现且未修复的便捷入口兼容问题。确认原操作未执行后，通过已有公开 `agent.configure(value)` / `agent.transfer(target_config)` 完整配置路径原样传入该 ID；这条成功路径不关闭便捷入口问题。原生 init 回报精确请求 ID，Assistant 回报 `deepseek/deepseek-flash`；只能证明包装器回报的路由，`low` 只确认配置传递，未取得服务端实际强度回报。

真实增量为旧 Codex boot/handoff 两轮、发送方 Codex 一轮及 tclaude boot/Watch 两次 query，均完成。旧模型本人保存随机资产、检查点并交接，平台自动启动后继；同一实例身份和工作根保持，新 Binding/session 建立。后继读回原检查点和资产、本人收信并发布 ACK、保存结果及检查点后自行停工。旧 Binding 写入被拒绝且操作未记录；两端 released、Runner 退出、Watch 关闭，transfer 完成状态在后继停止后仍保持。独立复核确认关键平台副作用和原生记录一致。

严格工具指令未通过：后继首轮有四次原生 Read；整组另有六次参数错误（Codex 四次、tclaude 两次），均在各自原轮自行纠正，无控制者追加提示或重放。部分中文工具输出乱码原因未定位。共享原生服务未证独占而保持不动，不宣称全机服务退出。本批没有修复或重测 WorkBuddy、busy insert/steer，也不扩展为 Desktop、反向交接、全矩阵或长期运行通过。
