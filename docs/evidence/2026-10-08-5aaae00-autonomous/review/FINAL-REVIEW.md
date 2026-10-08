# 本批最终独立复核（已完成范围）

日期：2026-10-08。产品固定基线：5aaae00520374b022e0c38fa21f312f8e08629ba，版本 0.1.0a1。本次复核已完成的 normal Watch、管家发布恢复、Desktop 只读探针和 tclaude 无模型预检；不重新裁定历史批次，不把待用户选型的 tclaude 真实调用或交接计为通过。复核者未运行模型、测试、探针、Runner、RPC 或服务，只新增 review 下的 PARTIAL-REVIEW.md 和本文件。PARTIAL 原样保留，FINAL 纳入追加范围与 Lead 对 Desktop 退出措辞的修订。

## 结论

| 范围 | 独立判断 | 必须保留的限制 |
| --- | --- | --- |
| normal Watch | 通信开始后的无控制者纠偏闭环限定通过 | 首次 boot 提前 receive 被拒绝，初始化遵循不通过；有模型自行修正参数、发送者笔记抄录错误 |
| 管家 publication-reconcile | 实际发布故障、定时通知、模型诊断/维修/独立复查、本人停工限定通过 | 底层 Git 条件由管理端恢复；有编排错误、模型参数错误和 boot Shell 偏差；steward 未 ACK |
| Desktop 控制 | 真实继承调用上下文的连接、工具发现、当前调用聊天 busy 状态读取及所建 RPC 子进程退出，限定通过 | 未验证创建聊天、Binding、投递、交接、idle、原生停工；退出方式和协议自报版本未留证 |
| tclaude | 无模型 SDK 握手与目录预检通过 | 认证 configured_unverified；真实模型和交接未验证，等待用户选择 |
| message.reconcile 授权 | 静态相邻疑点，未实测 | 不作为本批已复现越权或产品修复结论 |

## A. normal Watch

已读取 [WATCH 报告](../reports/WATCH.md)、[基线记录](../reports/evidence/01-baseline.json)、任务配置、公开状态/消息/资产证据，并沿 [发送者原始记录](../proof/watch-local/watch-alpha/records/b1a328acff2754abcae00512d2036f112/runtime.jsonl) 与 [接收者原始记录](../proof/watch-local/watch-beta/records/b4912bc12d3554bf88cec14b919c5ad5f/runtime.jsonl) 核对实际工具参数和返回。不是以模型 final 文本替代副作用证据。

- 原始 thread/started 均为 gpt-6-luna / low。发送者 started/completed 为 1/1，接收者为 3/3，共 4 轮；接收者三轮都属于同一 session。接收者首轮为 boot，后两轮为真实 Watch 通知。
- 原始记录中发送者只有一次 boot 输入，接收者只有 boot 加两次平台消息通知。两端执行项目均为 aw_execute 动态工具，没有 Shell、sleep 或其他执行工具。结合 [控制脚本](../executor/run_watch.py)、[观察脚本](../executor/observe.py) 与 [最终观察](../reports/evidence/14-watch-final-observation.json)，支持通信开始后的 corrective_inputs=0；控制脚本没有代发消息、receive/ACK、写结果资产或停工。
- 发送者分别单次调用 message.send，aw-watch-001/002 实际返回 published，第二条引用第一条，两条都为 normal。最终 [消息一](../reports/evidence/16-aw-watch-001-show.json)、[消息二](../reports/evidence/16-aw-watch-002-show.json) 与原始返回一致，发送者均是 watch-alpha。
- 接收者在通知轮分别调用 message.receive，ACK publication 均为 published，receiver/binding 对应接收者。两次保存顺序为 A 后 B：首写 revision=null，首写返回 2c0207e12baad13e97558d546a4e1b95a185c35200e12057897aa570cdaa73b2；第二轮先读回 A 与该 revision，再按它追加 B。最终 [资产](../reports/evidence/17-order-asset.json) revision 为 994d1c8a59e8ec4645b52cc11a3f0e749a901feef32fcc2365ea5619c4509dbe，保留两条 message_id、message_refs 及同一随机标识。
- 两端模型各自 checkpoint.create，随后以实际返回 ID 调用 agent.stop：发送者 c7d7578ed1a994ed2a29d334dd387847d；接收者 c87f350e943324a6ea70990b85b2f77c5。stop 的即时返回均为 awaiting_native_idle；之后原生 turn/completed 与公开 [发送者状态](../reports/evidence/15-watch-alpha-show.json)、[接收者状态](../reports/evidence/15-watch-beta-show.json) 证明 current=null、released、runner_alive=false、Watch disabled。不是把 stop 请求视为已经退出。
- [最终 doctor](../reports/evidence/18-watch-health.json) 为 healthy、issues=[]、unacknowledged_notifications={}。结论仅限这组本机隔离 normal Watch，不扩为 Desktop、insert/steer、跨 Harness、企微或长期运行通过。

### 保留偏差

1. 接收者首次 boot 读完任务后，提前调用 message.receive aw-watch-001。该时间早于发送者启动及消息创建；平台返回 The notification does not target this instance.，未产生 ACK 或顺序资产。该轮随后结束，后续正常通知到来才成功接收。[首轮观察](../reports/evidence/11-receiver-boot-complete.json) 和原始日志保留失败。初始化“只读并结束、不提前 receive”不通过；不得将整体描述为零偏差，也不要求重跑求绿。
2. 原始日志还有四次不接受 binding 参数的调用：发送者 agent.show、asset.write，接收者 agent.show、asset.read。模型自行去掉 binding 后继续；发送者未重发消息，接收者未重发 ACK。这些是实际参数错误与自行恢复，不是控制者纠偏。新顺序文件首次读取的不存在错误属于任务允许的新文件分支。
3. [发送者笔记](../proof/watch-local/watch-alpha/notes/watch-sender.md) 的第二条“实际返回”把 payload.from.agent 抄成 watch-beta；真正 message.send 返回与共享消息记录都是 watch-alpha。不能把该模型手抄 JSON 当成原始回执。该抄录错误不否定真实通信与接收者顺序资产，但“完整准确记录发送返回”不能宣称完全通过。

## B. Desktop 控制只读探针

已读取独立目录的 [报告](../desktop-control/REPORT.md)、[事实 JSON](../desktop-control/desktop-control-result.json)、[探针源码](../desktop-control/probe.py)，未重运行或连接 RPC，未读取其他私人聊天或认证资料。

探针直接采用环境中已有的 pipe 和 caller，session 也取同一 caller；未构造其他聊天身份。通过产品 runtime.Desktop 的构造流程执行 initialize、notifications/initialized、tools/list；工具名称检查通过后，再读取目录并调用 Desktop.status。status 实际走 read_thread，只查询当前调用聊天，结果映射为 busy。事实 JSON 与调用源码一致，证明所列 create_thread、read_thread、send_message_to_thread、list_projects 等工具在本次发现结果中存在；探针没有调用 create_thread 或 send_message_to_thread。

源码没有模型输入、消息、Workspace 或 Binding 创建调用，也没有应用私有数据库访问；记录值分别为 0、0、false、false。只读 status 会在内存中收到当前调用聊天的有限返回，但探针不保存其内容或 ID；共享事实 JSON 只保存 busy，不能把该探针称为其他聊天内容审查。

独立计算的新固定安装 runtime/rpc 校验值与事实 JSON 一致；实际插件 server.mjs 校验值也一致。当前开发仓上述产品文件与 origin/main 无差异。产品 [Desktop 构造和状态代码](../../../../src/agent_workspace/runtime.py)、[自动交接预检](../../../../src/agent_workspace/transfer.py)、[RPC 清理](../../../../src/agent_workspace/rpc.py) 支持报告所列边界：

- runtime.start 的 Desktop 分支仍写进入提示、生成深链并返回 awaiting_new_session_bind；探针直接实例化控制适配器，未走完整持久 Agent 生命周期。
- transfer.preflight 只接受 codex/claude/codebuddy，Desktop 目标会被拒绝。本轮是静态确认，不声称真实发起过被拒绝的交接。
- 工具目录存在 create_thread 等不能等同于 AgentWorkspace 已接入自动创建、完整 Binding、消息投递、跨端交接或停止观测。上述能力和 idle 状态均未验证。
- finally 调用 adapter.close，随后 process.poll() is not None 得到 owned_rpc_process_exited=true，支持“本次所建 RPC 子进程已退出”。Rpc.close 可能在等待超时后 terminate/kill；未保存 returncode 或关闭路径，因此只能认定“已退出”，不能认定为自然或优雅退出。Lead 已把独立 Desktop 报告的原“正常退出”措辞改为上述限定，事实 JSON 未改、未重跑探针。
- JSON 的 server_version=0.1.5 是探针按安装路径写入的版本标识，并非保存的 initialize.serverInfo.version。可表述为“连接所校验的 0.1.5 安装组件”，不当作独立协议版本证明。

首次 distribution 名称错误按 Lead 过程说明发生在连接前；现存 probe.py 已使用 git-native-agent-workspace，其查询位于 Desktop 构造之前。提供的三份文件没有独立首败日志或初版脚本，故无法独立复核首败全过程；接受为测试脚本偏差说明，不登记为产品缺陷，也不要求再次运行。

## C. 管家真实发布故障恢复

已读取 [MAINTENANCE 报告](../reports/MAINTENANCE.md)、evidence/30—65、[准备脚本](../executor/prepare_maintenance.py)、[故障脚本](../executor/run_maintenance.py)、[接续说明脚本](../executor/continue_maintenance_observation.py)、[收口脚本](../executor/finish_maintenance.py)，并核对 [Sentinel 原始记录](../proof/maintenance-local/sentinel/records/b101bf7595cd04d4085f766211eb3933b/runtime.jsonl) 与 [Maintainer 原始记录](../proof/maintenance-local/maintainer/records/b152041300c694178936355ffa9acc8a9/runtime.jsonl)。实际出版恢复闭环限定通过；全程严格工具遵循不通过。

### 真实故障及回滚

authority 是本批新空间的 bare 仓库。脚本 resolve 后以 relative_to(ROOT.resolve()) 验证范围，原 receive.hideRefs 查询退出 1 且没有值；[计划](../reports/evidence/40-fault-plan.json) 明确只改变本地配置，不授予业务任务。临时写入 receive.hideRefs=refs/heads/main 后，[公开单次刺激消息](../reports/evidence/44-real-failed-publication.json) 返回 CLI exit=2、operation aw-maint-fault-001 的 state=pending、completed=[] 和 Git push rejected 错误。产品源 Messages.send 先生成本地 operation，再实际 reconcile；该链及现有原始回执支持真实失败，未以手写 pending 或告警替代故障。

原消息 from=sentinel、to=steward、normal，内容明确为隔离测试刺激。这个原始刺激由管理端调用公开 message.send，不冒称 Sentinel 模型自行制造故障。之后诊断消息与回复才由模型发送。

finally [撤销配置](../reports/evidence/46-fault-rollback.json) 只 unset 该精确值，exit=0；[恢复核对](../reports/evidence/47-rollback-verified.json) 再次 exit=1、无值。复核时只读实际 authority config 也无 receive.hideRefs。[恢复后 operation](../reports/evidence/48-original-still-pending.json) 仍 pending，[doctor](../reports/evidence/45-fault-doctor-after-rollback.json) degraded，唯一 issue 为 sentinel / aw-maint-fault-001 / publication_pending。恢复 Git 写条件没有替产品发布原消息。

[49 编排偏差](../reports/evidence/49-controller-exit-expectation-error.json) 记录控制脚本原来错误预期 exit=0，而 intended pending 的真实 CLI exit=2，导致观察提前结束；44 的原输出和 46/47 的时间顺序支持“先得到真实故障，finally 已回滚”。message.operation 读取 pending 也返回 2，48 保留。当前故障脚本已把发送预期改为 2，不能用当前脚本假装初版从无错误。接续依据原记录，未重发刺激、重复注入或启动新故障；该偏差属于编排，不登记为产品故障，也不否定之后真正发生的恢复链。

### 实际巡检、模型维修和独立复查

[41 配置](../reports/evidence/41-schedule-on.json) 为 enabled=true、interval=30、notify=true。[62 巡检快照](../reports/evidence/62-worker-real-timed-observation.json) 有真实 schedule generation、report、notice=health-f5242c08aae54c66a6807bbd32b81e20、Sentinel 原 Binding、queued 状态以及 next_due。下一到期值对应 30 秒间隔。它记录的是最后一次检查快照，不能误称该快照的 last_run 是第一次告警时刻，也不证明长期定时可靠性。

Sentinel 本地原始 input 的同一 health ID 于 12:58:59.674922+08:00 创建，purpose=maintenance、最终 completed；原始 userMessage 是产品标准巡检文本。之后模型读取 maintenance.status、workspace.doctor，见到原 publication_pending，再发送 aw-maint-task-001。结合公开 worker_running 曾为 true、定时快照和模型原始输入，支持正式 worker 驱动的真实通知，未调用直接 tick 或手写 notice 替代。

[34 授权](../reports/evidence/34-maint-grant.json) 只列 commands=[maintenance.repair]、targets=[sentinel]。Maintainer 在真实 Watch 通知轮自己 receive，ACK publication=published，先读原 operation=pending 和 doctor=degraded，再执行 maintenance.repair(action=publication-reconcile, agent_id=sentinel, operation_id=aw-maint-fault-001, request_id=aw-maint-repair-001)。原始动态调用返回和 [维修回执](../reports/evidence/59-repair-receipt.json) 同时为 repair.state=applied、result.state=published、verification healthy。没有走 message.reconcile、sync-idle、Shell 修复或控制器代repair。

实际 grant 的强制粒度是命令与 target，不是 action/operation_id；“只维修本 ID”来自显式测试任务，不能宣称 grant 在技术上锁住了该 ID。本批没有执行无 grant 的 repair 反例、撤权后模型写入反例或其他 action，因此只证明实际授权路径可用。

Maintainer 随后新读 operation=published、doctor=healthy，保存 [维修笔记](../reports/evidence/57-maintainer-asset.json)，以 aw-maint-result-001 给 Sentinel 发结果，引用 aw-maint-task-001。Sentinel 本人 receive/ACK，再读取原 operation 和一次新 doctor（revision=828d1b8aee003868f5506885f90d5d39b4098978），保存 [独立复查笔记](../reports/evidence/57-sentinel-asset.json)。[任务](../reports/evidence/58-aw-maint-task-001-show.json) 与 [回复](../reports/evidence/58-aw-maint-result-001-show.json) 的真实共享记录及 ACK 支持该链；不是以笔记代替原始结果。

管理端最后 [原 operation](../reports/evidence/54-original-operation-final.json) published，[独立 doctor](../reports/evidence/55-independent-doctor.json) healthy、issues=[]，目标 publication_pending 消失。它仍明确列 unacknowledged_notifications.steward=1：只是补齐协议发布，不证明未启动的 steward 已接收或完成业务，不代 ACK 清零。也不把这个正常保留项改名成修复失败。

### 幂等、本人停工和清理

[60 同 ID 回读](../reports/evidence/60-repeat-applied-repair-id.json) 仅在第一次结果已知 applied/published 后由管理端执行。[61 哈希](../reports/evidence/61-repair-idempotence.json) 前后相同，复核者只读真实维修回执也得到 SHA256 792cc485e0978950711ec2cdb243f02e9e01ecf9b7aa227e7dabb8e457505d74；回读 created_at、result 和 verification 均保留。[现有 repair 代码](../../../../src/agent_workspace/maintenance.py) 对已存在且请求一致的 ID 返回原回执，未重新执行 reconcile。因此限定支持已知 applied 的幂等回读，不证明 outcome_unknown 可重试；此回读在撤权、模型停工后由管理端发起，也不是撤权后的模型授权测试。

Sentinel 与 Maintainer 的原始 thread 均为 gpt-6-luna / low，started/completed 分别 3/3、2/2，共 5 轮。Sentinel 三轮为 boot、真实巡检、结果 Watch；Maintainer 两轮为 boot、维修任务 Watch，没有控制者追加的纠偏输入。与 Watch 共 9 个实际 Codex 完成轮次，不含 tclaude 模型轮次。

两端本人以实际 checkpoint ID 停工：Sentinel c5da8c6434ded4c83b7ce120d359a6b6c，Maintainer ce8bbf80896a1419981966b32de9905a1。即时 stop 都是 awaiting_native_idle；[51 最终原生观察](../reports/evidence/51-maint-final-observation.json) 及 [Sentinel 状态](../reports/evidence/53-sentinel-show.json)、[Maintainer 状态](../reports/evidence/53-maintainer-show.json) 才证明完成轮次后 current=null、released、runner_alive=false、Watch disabled。没有以控制器停工替代本人动作。

管理端 [50 关闭 schedule](../reports/evidence/50-schedule-off.json)、[52 撤销 grant](../reports/evidence/52-maint-revoke.json) 后，[56 状态](../reports/evidence/56-maintenance-status.json) 仍有 worker_running=true，不能当最终退出。[64 记录](../reports/evidence/64-worker-stop-observation.json) 说明向自有正式 worker 终端 Ctrl+C；[63 既有进程审计](../reports/evidence/63-process-audit-after-maintenance.json) 按本批根筛选，只剩审计命令本身；[65 最终状态](../reports/evidence/65-maintenance-worker-final-status.json) worker_running=false、schedule disabled、grant commands/targets 为空。限定支持该巡检 worker 和已知模型 Runner 已收口，不据终端 exit1 宣称优雅 finally，也不据本批路径筛选宣称所有共享服务都退出。

最终 maintenance.status.local_run 仍保留此前 degraded 报告/queued notice，是关闭巡检前的历史快照；当前健康用新的 55 doctor 判断，不覆盖或伪造旧巡检记录。

### 模型遵循偏差

- Maintainer boot 有 3 条 commandExecution 记录：第一次尝试读取机器级 memory 时进程启动失败（exit=-1）；第二次读取错误的机器级 skills 路径失败（exit=1）；第三次成功只读本实例 agent Skill 和 AGENTS.md（exit=0）。都发生于 boot，未用 Shell 实施维修，也未读 .aw-local 或改产品。仍违反本任务“只用 aw_execute、禁止 Shell”的明确要求，不能描述为全程严格遵循。原始记录保留，不重跑求绿。
- Sentinel boot 额外列资产、读 capabilities/initialization 并创建初始 checkpoint，超出测试描述的“只读 AGENTS.md 并结束”；没有提前诊断、发任务消息或 stop。该差异不覆盖真实维修链，但初始化严格遵循不能宣称通过。
- Sentinel 曾给 asset.list 多传 binding，给 maintenance.status 多传 agent_id/binding，并把消息目标写成 recipient；Maintainer 曾给 message.operation、workspace.doctor 多传身份参数、给 maintenance.repair 多传 binding、误用 agent.asset.write，以及把回复 sender 身份填成 sentinel。平台实际拒绝这些调用；后一次正确 send 仍因缺 to 被拒绝，随后才以本人身份和 to=sentinel 成功。原始日志记录失败与自行纠正，不能称零错误。错误调用均在执行副作用前被拒绝；原刺激、维修实际执行、任务和回复的成功副作用各一次，不是结果未知后的重放。
- 发布恢复场景的底层 Git 条件由管理端恢复；Maintainer 只补齐原消息。该实机结果不外推为自动修 Git 权限、生产故障、Desktop、外部渠道、bridge-retry 或其他维修类型。

## D. tclaude 无模型预检

只读 [预检脚本](../executor/probe_tclaude.py)、[组件记录](../reports/evidence/20-tclaude-prerequisites.json)、版本/help 和 [SDK 握手](../reports/evidence/24-tclaude-sdk-handshake.json)，没有运行它们。记录组件为 @tencent/tclaude 0.1.8（b7d3493），上游 Claude Code 2.1.251；本批 claude-agent-sdk 0.2.163。事实 JSON 的真实退出码为 0，state=connected、model_invoked=false、authentication=configured_unverified、catalog=reported_by_claude，返回 19 个目录项。

[产品 inspect-sdk 代码](../../../../src/agent_workspace/harness_config.py) 使用空 tools/mcp_servers、SDK 客户端 connect/get_server_info，再退出上下文；该路径没有 client.query。代码与记录支持 SDK 无模型连接和目录发现，不证明任何目录项实际可调用、认证有效、normal 持续通信、insert、真实模型行为或跨 Harness 交接。模型选择与真实调用仍等待用户决定，不替用户选型，也不将准备脚本算成已执行交接。本次不检查/控制共享 tclaude 服务，不宣称它们全部退出。

## 静态相邻疑点：message.reconcile

固定安装 [commands.py](../../../../src/agent_workspace/commands.py) 的 message.reconcile 映射到 Messages.reconcile(operation_id)，未归入 USER_MANAGEMENT 或 CALLER_BOUND。仅提供 operation_id 时，跨实例检查默认采用调用者自己的 workspace/agent_id；execute 只核验调用者 Binding 有效。[Messages.reconcile](../../../../src/agent_workspace/messages.py) 从本地 operation 回执取得所属空间、sender/receiver 和原 Binding；写入时验证原 Binding，却未比较调用 actor 与 operation 所有者，也未走 maintenance.repair 的 grant 校验。

静态路径提示：在同一 installation 中，持有有效 Binding 的其他 actor 若知道 operation_id，且原 operation 的前提仍满足，可能直接补齐它而绕过 maintenance.repair 的 scoped grant。尚未做实际越权调用，不记录为已复现。本次仅列边界，不修代码、不扩测试，也不据指定维修路径通过宣称所有 publication 入口授权已闭合。

## 证据与归档边界

只新增 review 文件，未修改 canonical 报告、模型资产、运行账本、锁或产品。本报告引用本轮 reports 为主，必要的原始测试记录只读追溯。Desktop 材料仍引用相邻独立批次目录，待 Lead 统一归档时替换为最终包内相对链接；其源文件哈希见下表。PARTIAL 保留初次复核时的源哈希，FINAL 表格反映本次读取时版本。

原始日志、探针和部分 CLI 证据含机器路径/测试 session，不能按原样入仓。未读取或复制真实认证、pipe 值或其他私人聊天正文。本文件不构成最终分享包完成或完全脱敏证明；Lead 应提供原始/归档文件哈希对应及排除说明，保留历史失败。产品 runtime/rpc/transfer 源文件哈希与固定安装及 Desktop JSON 一致；插件 server.mjs 独立复算 SHA256 为 264116eb1273ab0e36b177198540afe943b533b89a4f27abfd178f476a4b8afc。

### 本次读取源文件 SHA256

| 文件 | SHA256 |
| --- | --- |
| [../reports/WATCH.md](../reports/WATCH.md) | 5f2231451195beff0252d150053b922c33207b2ba7c4db381d0ba3f32ff2f43b |
| [../reports/evidence/01-baseline.json](../reports/evidence/01-baseline.json) | eda30fc4ac5dccfc2ce6e127534526790d6330666e6de08c6cf30085040a3ae4 |
| [../data/home/instances/watch-local/watch-alpha/records/b1a328acff2754abcae00512d2036f112/runtime.jsonl](../proof/watch-local/watch-alpha/records/b1a328acff2754abcae00512d2036f112/runtime.jsonl) | 2aea6d170bd52882b9049bc36595c827f766d99970a98c93697fc350f0b0db55 |
| [../data/home/instances/watch-local/watch-beta/records/b4912bc12d3554bf88cec14b919c5ad5f/runtime.jsonl](../proof/watch-local/watch-beta/records/b4912bc12d3554bf88cec14b919c5ad5f/runtime.jsonl) | 721753a2200f01449694d71b79e852abf5ba6bdeabcbbfd30ebb8ecbbd01e3e8 |
| [../tools/run_watch.py](../executor/run_watch.py) | 31036326926f8634597035c92a294b93ac277e89ed0983079e1e872e784f58a1 |
| [../tools/observe.py](../executor/observe.py) | edb8ee8f59e5ffeff9acb09af38fe8835413017817dd961eb896127ee629c185 |
| [../reports/evidence/14-watch-final-observation.json](../reports/evidence/14-watch-final-observation.json) | 80bc49442195f5079d1953acff1692200cc2838d64d9a3831e6b2cac366ec95d |
| [../reports/evidence/16-aw-watch-001-show.json](../reports/evidence/16-aw-watch-001-show.json) | 4a18d36a34d443dba962495ae198c09a7912e433440d5ffcdb4e20d14b1bce8e |
| [../reports/evidence/16-aw-watch-002-show.json](../reports/evidence/16-aw-watch-002-show.json) | b512edfc2e4bf65fd557d123d684b9c5302f6b4603ddde3cf388614379ae5fec |
| [../reports/evidence/17-order-asset.json](../reports/evidence/17-order-asset.json) | cea23bd6468e4fa312da13997d5466bd9e4197fbdc70b0cb5640ff8e25473f72 |
| [../reports/evidence/15-watch-alpha-show.json](../reports/evidence/15-watch-alpha-show.json) | 951786ea1fe19affe3d9b666e1098433fcd9c03c62d4cc541be84310d7e0c310 |
| [../reports/evidence/15-watch-beta-show.json](../reports/evidence/15-watch-beta-show.json) | 51b22a25f3ae2314799d2de2d30f77c8c2bf96bd78710658cc7c3eefde9e7364 |
| [../reports/evidence/18-watch-health.json](../reports/evidence/18-watch-health.json) | d613038010c5e86411985b5e516bbde76e46492ab855e2f34d2fc219f6da3873 |
| [../reports/evidence/11-receiver-boot-complete.json](../reports/evidence/11-receiver-boot-complete.json) | 3ac1f27f6034a99bb61eea37526ace83cab1f766bc6e7c9e118d865c7b3090ca |
| [../data/home/instances/watch-local/watch-alpha/notes/watch-sender.md](../proof/watch-local/watch-alpha/notes/watch-sender.md) | e5f4c5e2e8d05fd2b788e625d54e07526fb4ba5af4186ed8b35e5ec009330cb0 |
| [../../2026-10-08-desktop-control-0d31bfbb/REPORT.md](../desktop-control/REPORT.md) | 9f99d4a3d1108a48f085fc1447488c27dc2596dd986ba09d15a88c82339ee088 |
| [../../2026-10-08-desktop-control-0d31bfbb/desktop-control-result.json](../desktop-control/desktop-control-result.json) | 9d3b7effd77512479078bc7bd317971bdf2cbdd5598c834bfda0c0091322103a |
| [../../2026-10-08-desktop-control-0d31bfbb/probe.py](../desktop-control/probe.py) | 68e4aeebc01817335e93c2f5de4ed56602301303f4eb0db319473e69ceffdf88 |
| [../app/Lib/site-packages/agent_workspace/runtime.py](../../../../src/agent_workspace/runtime.py) | 700e2c7733a4e18d202b8050f54a6956b00fe49a81cd4bd5c949735b6f92b592 |
| [../app/Lib/site-packages/agent_workspace/transfer.py](../../../../src/agent_workspace/transfer.py) | 1776fa2d4de763f44486dab9012eab3dfe21af62176d3f97a0cb382da0d281a4 |
| [../app/Lib/site-packages/agent_workspace/rpc.py](../../../../src/agent_workspace/rpc.py) | 2fa8a36cf246826dcd9e13dadc9464797c67bdd517b399d247158966d33b1799 |
| [../reports/MAINTENANCE.md](../reports/MAINTENANCE.md) | d57d72fed4379fecf10ba9aee8149f655ee6622ce5ae532351db098fd20f0b51 |
| [../tools/prepare_maintenance.py](../executor/prepare_maintenance.py) | 245e6746706560996d08212159584d15da4d578bd53380c62995f4bc0193bb5f |
| [../tools/run_maintenance.py](../executor/run_maintenance.py) | 33afbb886c6f5c7f0dcf5fb00a66ce994cdf792ccf5fcd5c5e29091e4d614a72 |
| [../tools/continue_maintenance_observation.py](../executor/continue_maintenance_observation.py) | 0f3001f438e5d0b8d14589839c45d948f033a360851b82f88f9cfa0fe3359ee9 |
| [../tools/finish_maintenance.py](../executor/finish_maintenance.py) | 898ec6de63a3d00790b23e504bfc3e33da01dbe8a25685c04a680653d0b3699f |
| [../data/home/instances/maintenance-local/sentinel/records/b101bf7595cd04d4085f766211eb3933b/runtime.jsonl](../proof/maintenance-local/sentinel/records/b101bf7595cd04d4085f766211eb3933b/runtime.jsonl) | c1f485463b99eefabd56f70e1ba2f026632d770178b2631cf699f0fa44c45505 |
| [../data/home/instances/maintenance-local/maintainer/records/b152041300c694178936355ffa9acc8a9/runtime.jsonl](../proof/maintenance-local/maintainer/records/b152041300c694178936355ffa9acc8a9/runtime.jsonl) | c88214053dcea8037223e396d0f0d252bb01b751ef9e64d7f9c55c32558e6c28 |
| [../reports/evidence/40-fault-plan.json](../reports/evidence/40-fault-plan.json) | eaa18e21db3ac74d20199731a7a7e8f81372fae4104948a66823a30a29c6cbca |
| [../reports/evidence/44-real-failed-publication.json](../reports/evidence/44-real-failed-publication.json) | 3a437c5434cd97204fa345b7445289b2acb2f81b8346b655ba95f0ab962bd67f |
| [../reports/evidence/46-fault-rollback.json](../reports/evidence/46-fault-rollback.json) | db9b96c878d9b3aa9cee9df8b1ab8e87ee8fb75b0ba3e5f5b6a0fade313a4dd6 |
| [../reports/evidence/47-rollback-verified.json](../reports/evidence/47-rollback-verified.json) | 4fe7dded91dbfd5cb7787dc2220682b405eed9b5bd42ecf9cddbd57410b097d9 |
| [../reports/evidence/48-original-still-pending.json](../reports/evidence/48-original-still-pending.json) | 28eeb9aff021ad621a576779de69ed22ece078dcef73c8c575005dec3e7be5cd |
| [../reports/evidence/45-fault-doctor-after-rollback.json](../reports/evidence/45-fault-doctor-after-rollback.json) | 466e16cbbb0a29dcd40f69c1c3792a2ce1a5da8a951d1ba5839b5a44a7692831 |
| [../reports/evidence/49-controller-exit-expectation-error.json](../reports/evidence/49-controller-exit-expectation-error.json) | 3322449b0c2ff82ac68a48d5da8a76b0c99f1af578dc5b4ab8bc7ef0c436b5f1 |
| [../reports/evidence/41-schedule-on.json](../reports/evidence/41-schedule-on.json) | c2fc9176719f10a849aa2d810b425289dbea27aab4e47b96fa4717d26008fea9 |
| [../reports/evidence/62-worker-real-timed-observation.json](../reports/evidence/62-worker-real-timed-observation.json) | b4071bf75f61915fc4cbbd93565d386b70f794fc2ed7d68d49cda094f4fc691c |
| [../reports/evidence/34-maint-grant.json](../reports/evidence/34-maint-grant.json) | 48f2fe0d8f97f96589585737815fc0240a2bb538e3cccd081d899755d5b8914a |
| [../reports/evidence/59-repair-receipt.json](../reports/evidence/59-repair-receipt.json) | 30be4fa7b77996709c4b23ddb9a020708da601f90d9f53e79f7e7416611662c6 |
| [../reports/evidence/57-maintainer-asset.json](../reports/evidence/57-maintainer-asset.json) | 1bdeb4ac3fdf42ac76c19c2b3ae047a6915f7d677f2e13067fe32b1c09e94b80 |
| [../reports/evidence/57-sentinel-asset.json](../reports/evidence/57-sentinel-asset.json) | 90ce1eb102ba5458ad7a6c36e54fdc6dfad97b527f1c1fc5d77a82ae376596f5 |
| [../reports/evidence/58-aw-maint-task-001-show.json](../reports/evidence/58-aw-maint-task-001-show.json) | 7ec2249442c47a7bd72fa83c36fc4713a2a26563faeb7770bdedf9712617851d |
| [../reports/evidence/58-aw-maint-result-001-show.json](../reports/evidence/58-aw-maint-result-001-show.json) | caebe9799a29238f837b8ff7160f5bc6d069b740fbc9f6bbd1ee4f1609e5915d |
| [../reports/evidence/54-original-operation-final.json](../reports/evidence/54-original-operation-final.json) | 826730c799075d90d9273ce83e9068845dcda626ab7270ab5a2cbc7eae023ace |
| [../reports/evidence/55-independent-doctor.json](../reports/evidence/55-independent-doctor.json) | 38147a4f40cb51f43d39f21035fb4bf9a0a3d2961217b94ff60b547d798bc54c |
| [../reports/evidence/60-repeat-applied-repair-id.json](../reports/evidence/60-repeat-applied-repair-id.json) | 37ea5098df06d2b8f497292f3025e7308ee1cd6d44fa1223680fdc23f4f9f59a |
| [../reports/evidence/61-repair-idempotence.json](../reports/evidence/61-repair-idempotence.json) | 938c1c3d1d6644b1569a3c2e07784d8132f1c18a53209aca94fbaea7885dd21b |
| [../app/Lib/site-packages/agent_workspace/maintenance.py](../../../../src/agent_workspace/maintenance.py) | 6f5fb8b016317216b530063bd7355d5d5bbdda375b9fb099747554d334c3e437 |
| [../reports/evidence/51-maint-final-observation.json](../reports/evidence/51-maint-final-observation.json) | 2fe5ced59cd715c5f4fabc96397c45a0a73f0eb75c98f514e213912687e3793e |
| [../reports/evidence/53-sentinel-show.json](../reports/evidence/53-sentinel-show.json) | 1562328547ded111e26cd6d92b9cf42d9528098f27681bf7eb4949ca1aadd2da |
| [../reports/evidence/53-maintainer-show.json](../reports/evidence/53-maintainer-show.json) | 1baadd37088659588bb02f3a6e9496e88e356f52f5bd886a73a13a46de5b9003 |
| [../reports/evidence/50-schedule-off.json](../reports/evidence/50-schedule-off.json) | 0beddb4d6cb4cdcf14b3ffa5c4e1520e035b073fed33af81375d4f7a7246068a |
| [../reports/evidence/52-maint-revoke.json](../reports/evidence/52-maint-revoke.json) | a73b234bd0a6c071c035d75694e8fbf6a94df6e3e80a1006af1c7a8a48215356 |
| [../reports/evidence/56-maintenance-status.json](../reports/evidence/56-maintenance-status.json) | 42072c4bfbfd469a1596501555c8e633ea9277e62643047e89aa2400004e54de |
| [../reports/evidence/64-worker-stop-observation.json](../reports/evidence/64-worker-stop-observation.json) | 84b5c4259864a8d7baa11b5eb631ecd8f8f72a6411005ce55b536bc8617c01eb |
| [../reports/evidence/63-process-audit-after-maintenance.json](../reports/evidence/63-process-audit-after-maintenance.json) | 0ece15a60655cd767653037f60d40fd4944c7ad2e937e7cf55c28fe564658b97 |
| [../reports/evidence/65-maintenance-worker-final-status.json](../reports/evidence/65-maintenance-worker-final-status.json) | 48c8283e1408537368f5bd153fbae145130568eaab416fdcf5aa39cb5b9178a4 |
| [../tools/probe_tclaude.py](../executor/probe_tclaude.py) | 696a4f2e6066dd1b659514603ceed355838fc852c9bd09bb00b1b35eeebe62d8 |
| [../reports/evidence/20-tclaude-prerequisites.json](../reports/evidence/20-tclaude-prerequisites.json) | c00a6c78bc7178a809ecb72ae5b4556ec404032e48bdf55f3ba0c4363ca79bb8 |
| [../reports/evidence/24-tclaude-sdk-handshake.json](../reports/evidence/24-tclaude-sdk-handshake.json) | bc5f7b072427b3199e2b289b9872861b7740d0b982f65ae3afdd1b2557ac9223 |
| [../app/Lib/site-packages/agent_workspace/harness_config.py](../../../../src/agent_workspace/harness_config.py) | 4a4676093572a121540ab06982f8912094e18ee2e31698749ceeb4d309a257cc |
| [../app/Lib/site-packages/agent_workspace/commands.py](../../../../src/agent_workspace/commands.py) | 5461ccf3564338661107f36881fdbcd54a4dd2216d9416faa09662a89b1317ff |
| [../app/Lib/site-packages/agent_workspace/messages.py](../../../../src/agent_workspace/messages.py) | afad57ea012812b9635ab533a091f6ea71357b02ac86485211ab780be89ab8df |
| [../reports/evidence/30-maint-workspace-create.json](../reports/evidence/30-maint-workspace-create.json) | 694143dcd4344d004534eeefbbe3b75b80d31ed5541321ddddbf2cff806bb003 |
| [../reports/evidence/31-0-task-read.json](../reports/evidence/31-0-task-read.json) | 4b1ca4a082dc557419c402218ffa988ff63a5d62a53d07587ae257b178cbfdab |
| [../reports/evidence/31-1-task-read.json](../reports/evidence/31-1-task-read.json) | 7b0c2bb71636aeed338986033f76303717c038941569476bb22cf2ba8b5f730e |
| [../reports/evidence/32-0-task-write.json](../reports/evidence/32-0-task-write.json) | ffe1f8cd99004fc2d63905b03f87e96d6d9f0697856582687fc9919c79feb7ba |
| [../reports/evidence/32-1-task-write.json](../reports/evidence/32-1-task-write.json) | 60de3be3806eaf45b0bfb40268e4ed059424a4e4165dadb435c63e676463bc6e |
| [../reports/evidence/33-0-configure.json](../reports/evidence/33-0-configure.json) | fba1136a0e47a4bf1871c775c8bd13e85bf6d903cf9c65800ed89ce763c1261c |
| [../reports/evidence/33-1-configure.json](../reports/evidence/33-1-configure.json) | 61e4a9e23193820c5a050b450be19da5005c6237c94a5288f490771f1207945d |
| [../reports/evidence/35-0-start.json](../reports/evidence/35-0-start.json) | 3f265609cfbfd8d1163dcd1b7ee7c111de2d792f4e979778acf051a3a5f90f31 |
| [../reports/evidence/35-1-start.json](../reports/evidence/35-1-start.json) | 431555241ba78f97cdf3cdf7aaf765f1ee8b351426d13616ad90a95d8781fd97 |
| [../reports/evidence/36-maint-boots-ready.json](../reports/evidence/36-maint-boots-ready.json) | b16cfa952f7907a72aef5d2f201790e637b110dc981cfef75c6f9de8dd42bd9e |
| [../reports/evidence/37-0-watch.json](../reports/evidence/37-0-watch.json) | 40514ae955e9e98d3e963505a0b3f78e5c1428d422ef7663ad39662ad6c97607 |
| [../reports/evidence/37-1-watch.json](../reports/evidence/37-1-watch.json) | 24201ff9807fdebd2e13e662b7a967353e1c83371304c162a4b8cc366a6c82c9 |
| [../reports/evidence/38-authority-is-bare.json](../reports/evidence/38-authority-is-bare.json) | 2fca585dad81067d89f1a3a94d595905988dd4fa82913c25eea595c69f5f4596 |
| [../reports/evidence/39-authority-original-hideRefs.json](../reports/evidence/39-authority-original-hideRefs.json) | a47744f35d15a687ca99f4dea46b63d305d28aa4003f78fa1a3cc76d1c41ee0e |
| [../reports/evidence/42-sentinel-binding.json](../reports/evidence/42-sentinel-binding.json) | 9ff865f02b6fc1ed96b7a8f339fbeacd6910adbc88ff300891a969dcf5f4b80f |
| [../reports/evidence/43-fault-inject.json](../reports/evidence/43-fault-inject.json) | e81dd4b13e66305863c9fbeb45a2b8e594c568f2cdf541d7b7d55caa95c4f9ce |
| [../reports/evidence/21-tclaude-version.json](../reports/evidence/21-tclaude-version.json) | 1255bc45efe2fd7b94c00789b2bd0abcff001bd04c46d2eb45e792fa1e41f663 |
| [../reports/evidence/22-tclaude-wrapper-help.json](../reports/evidence/22-tclaude-wrapper-help.json) | c9e82d56d1801fa8a2f2f1dbdad8eb166db312bb9727f908069d5bbf089765d8 |
| [../reports/evidence/23-tclaude-upstream-help.json](../reports/evidence/23-tclaude-upstream-help.json) | c1b462d5d1ca12bc2d22b9e43cf29a50de1b3a8b2cd4d4b27302fb6275bbfae5 |
| [../dist/git_native_agent_workspace-0.1.0a1-py3-none-any.whl](../EXCLUSIONS.md#binary-artifacts) | e9bcff1a015358643bafbc800d1beb7453dd36cbb8bd1c34a10e68d68ca309f7 |
| [PARTIAL-REVIEW.md](PARTIAL-REVIEW.md) | be5eb74280a21d166baa49771a99cddb2742e4dd638a02594cf2b56e4f433415 |

本次已完成范围复核结束。真实 tclaude 调用/交接与最终分享包不在本报告的通过范围。
