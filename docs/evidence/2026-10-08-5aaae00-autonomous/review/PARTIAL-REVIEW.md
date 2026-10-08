# 本批窄范围独立复核

日期：2026-10-08。产品固定基线：5aaae00520374b022e0c38fa21f312f8e08629ba，版本 0.1.0a1。本次只复核 normal Watch 与 Desktop 控制只读探针；不裁定尚在执行的管家维修、tclaude，也不重新裁定历史批次。复核者未运行模型、测试、探针、Runner、RPC 或服务；仅新建本文件。

## 结论

| 范围 | 独立判断 | 必须保留的限制 |
| --- | --- | --- |
| normal Watch | 通信开始后的无控制者纠偏闭环限定通过 | 首次 boot 提前 receive 被拒绝，初始化遵循不通过；有模型自行修正参数、发送者笔记抄录错误 |
| Desktop 控制 | 真实继承调用上下文的连接、工具发现、当前调用聊天 busy 状态读取及所建 RPC 子进程退出，限定通过 | 未验证创建聊天、Binding、投递、交接、idle、原生停工；退出方式和协议自报版本未留证 |
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
- finally 调用 adapter.close，随后 process.poll() is not None 得到 owned_rpc_process_exited=true，支持“本次所建 RPC 子进程已退出”。Rpc.close 可能在等待超时后 terminate/kill；未保存 returncode 或关闭路径，因此报告的“正常退出”应按“已退出”理解，不能认定为自然或优雅退出。
- JSON 的 server_version=0.1.5 是探针按安装路径写入的版本标识，并非保存的 initialize.serverInfo.version。可表述为“连接所校验的 0.1.5 安装组件”，不当作独立协议版本证明。

首次 distribution 名称错误按 Lead 过程说明发生在连接前；现存 probe.py 已使用 git-native-agent-workspace，其查询位于 Desktop 构造之前。提供的三份文件没有独立首败日志或初版脚本，故无法独立复核首败全过程；接受为测试脚本偏差说明，不登记为产品缺陷，也不要求再次运行。

## 静态相邻疑点：message.reconcile

固定安装 [commands.py](../../../../src/agent_workspace/commands.py) 的 message.reconcile 映射到 Messages.reconcile(operation_id)，未归入 USER_MANAGEMENT 或 CALLER_BOUND。仅提供 operation_id 时，跨实例检查默认采用调用者自己的 workspace/agent_id；execute 只核验调用者 Binding 有效。[Messages.reconcile](../../../../src/agent_workspace/messages.py) 从本地 operation 回执取得所属空间、sender/receiver 和原 Binding；写入时验证原 Binding，却未比较调用 actor 与 operation 所有者，也未走 maintenance.repair 的 grant 校验。

静态路径提示：在同一 installation 中，持有有效 Binding 的其他 actor 若知道 operation_id，且原 operation 的前提仍满足，可能直接补齐它而绕过 maintenance.repair 的 scoped grant。尚未做实际越权调用，不记录为已复现。本次仅列边界，不修代码、不扩测试，也不据指定维修路径通过宣称所有 publication 入口授权已闭合。

## 证据与归档边界

以下为本次读取源文件的 SHA256，复核者只新增本报告。原始测试日志和探针仍是本机材料，含测试 session、工具配置或机器路径的文件不得按原样入仓；探针源码含机器路径。未读取或复制认证、pipe 值、私人聊天正文。此文件不构成最终脱敏归档完成证明；Lead 后续应保留这些源哈希、对应归档哈希及脱敏/排除说明。Desktop 三份材料以相邻批次相对链接引用；最终包若重排目录，需要同步这些链接，不能静默丢失证据。

### 本次读取源文件 SHA256

| 文件 | SHA256 |
| --- | --- |
| [../reports/WATCH.md](../reports/WATCH.md) | ae87e6ca42736a9368526533ac503f2666e7add95e7023b4c030c09f2fe64073 |
| [../reports/evidence/01-baseline.json](../reports/evidence/01-baseline.json) | eda30fc4ac5dccfc2ce6e127534526790d6330666e6de08c6cf30085040a3ae4 |
| [../reports/evidence/11-receiver-boot-complete.json](../reports/evidence/11-receiver-boot-complete.json) | 3ac1f27f6034a99bb61eea37526ace83cab1f766bc6e7c9e118d865c7b3090ca |
| [../reports/evidence/14-watch-final-observation.json](../reports/evidence/14-watch-final-observation.json) | 80bc49442195f5079d1953acff1692200cc2838d64d9a3831e6b2cac366ec95d |
| [../reports/evidence/15-watch-alpha-show.json](../reports/evidence/15-watch-alpha-show.json) | 951786ea1fe19affe3d9b666e1098433fcd9c03c62d4cc541be84310d7e0c310 |
| [../reports/evidence/15-watch-beta-show.json](../reports/evidence/15-watch-beta-show.json) | 51b22a25f3ae2314799d2de2d30f77c8c2bf96bd78710658cc7c3eefde9e7364 |
| [../reports/evidence/16-aw-watch-001-show.json](../reports/evidence/16-aw-watch-001-show.json) | 4a18d36a34d443dba962495ae198c09a7912e433440d5ffcdb4e20d14b1bce8e |
| [../reports/evidence/16-aw-watch-002-show.json](../reports/evidence/16-aw-watch-002-show.json) | b512edfc2e4bf65fd557d123d684b9c5302f6b4603ddde3cf388614379ae5fec |
| [../reports/evidence/17-order-asset.json](../reports/evidence/17-order-asset.json) | cea23bd6468e4fa312da13997d5466bd9e4197fbdc70b0cb5640ff8e25473f72 |
| [../reports/evidence/18-watch-health.json](../reports/evidence/18-watch-health.json) | d613038010c5e86411985b5e516bbde76e46492ab855e2f34d2fc219f6da3873 |
| [../tools/prepare_watch.py](../executor/prepare_watch.py) | 252b1d51e2b70d01ae5d7d54f6494b83db52a5b2ca3c20c59e80403b32566837 |
| [../tools/run_watch.py](../executor/run_watch.py) | 31036326926f8634597035c92a294b93ac277e89ed0983079e1e872e784f58a1 |
| [../tools/observe.py](../executor/observe.py) | edb8ee8f59e5ffeff9acb09af38fe8835413017817dd961eb896127ee629c185 |
| [../data/home/instances/watch-local/watch-alpha/records/b1a328acff2754abcae00512d2036f112/runtime.jsonl](../proof/watch-local/watch-alpha/records/b1a328acff2754abcae00512d2036f112/runtime.jsonl) | 2aea6d170bd52882b9049bc36595c827f766d99970a98c93697fc350f0b0db55 |
| [../data/home/instances/watch-local/watch-beta/records/b4912bc12d3554bf88cec14b919c5ad5f/runtime.jsonl](../proof/watch-local/watch-beta/records/b4912bc12d3554bf88cec14b919c5ad5f/runtime.jsonl) | 721753a2200f01449694d71b79e852abf5ba6bdeabcbbfd30ebb8ecbbd01e3e8 |
| [../data/home/instances/watch-local/watch-alpha/notes/watch-sender.md](../proof/watch-local/watch-alpha/notes/watch-sender.md) | e5f4c5e2e8d05fd2b788e625d54e07526fb4ba5af4186ed8b35e5ec009330cb0 |
| [../app/Lib/site-packages/agent_workspace/runtime.py](../../../../src/agent_workspace/runtime.py) | 700e2c7733a4e18d202b8050f54a6956b00fe49a81cd4bd5c949735b6f92b592 |
| [../app/Lib/site-packages/agent_workspace/rpc.py](../../../../src/agent_workspace/rpc.py) | 2fa8a36cf246826dcd9e13dadc9464797c67bdd517b399d247158966d33b1799 |
| [../app/Lib/site-packages/agent_workspace/transfer.py](../../../../src/agent_workspace/transfer.py) | 1776fa2d4de763f44486dab9012eab3dfe21af62176d3f97a0cb382da0d281a4 |
| [../app/Lib/site-packages/agent_workspace/commands.py](../../../../src/agent_workspace/commands.py) | 5461ccf3564338661107f36881fdbcd54a4dd2216d9416faa09662a89b1317ff |
| [../app/Lib/site-packages/agent_workspace/messages.py](../../../../src/agent_workspace/messages.py) | afad57ea012812b9635ab533a091f6ea71357b02ac86485211ab780be89ab8df |
| [../dist/git_native_agent_workspace-0.1.0a1-py3-none-any.whl](../EXCLUSIONS.md#binary-artifacts) | e9bcff1a015358643bafbc800d1beb7453dd36cbb8bd1c34a10e68d68ca309f7 |
| [../../2026-10-08-desktop-control-0d31bfbb/REPORT.md](../desktop-control/REPORT.md) | 9f99d4a3d1108a48f085fc1447488c27dc2596dd986ba09d15a88c82339ee088 |
| [../../2026-10-08-desktop-control-0d31bfbb/desktop-control-result.json](../desktop-control/desktop-control-result.json) | 9d3b7effd77512479078bc7bd317971bdf2cbdd5598c834bfda0c0091322103a |
| [../../2026-10-08-desktop-control-0d31bfbb/probe.py](../desktop-control/probe.py) | 68e4aeebc01817335e93c2f5de4ed56602301303f4eb0db319473e69ceffdf88 |
插件 server.mjs 独立复算 SHA256：264116eb1273ab0e36b177198540afe943b533b89a4f27abfd178f476a4b8afc，与 Desktop 事实记录一致；其本机安装路径不进入本报告。

本轮复核至此结束，管家维修与 tclaude 留待 Lead 明确安排后另审。
