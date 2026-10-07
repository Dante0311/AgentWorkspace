# N 批 Codex 正常链路方案（执行前已撤回安排）

2026-10-06（Asia/Shanghai）。用户随后把优先目标改为企业微信/SBP OpsAgent，本方案未执行；新增模型轮次、实例、Watch、transfer和服务均为0。以下保留曾批准的具体方案，不构成继续执行入口。

准备时用户已确认：现有 ChatGPT 登录、`gpt-6-luna/low`、最多新增 6 轮。所有 start 初始化、Watch 自动输入、transfer 停工/后继和收尾均计入；模型内部 API 次数与实际金额不等同于这些原生 turn，金额仍未观测。零控制器重试，不升档、不换服务、不修代码。

预检：既有 Codex App exe `0.160.0` 的 `login status` 返回 `Logged in using ChatGPT`；beta 当前无 Binding、已 released、runner_alive=false、Watch 关闭。固定 wheel SHA256 为 `0ec257b1ffc14ede077f023415fa52f013f2a83ed04042d31be1baa9eeafb048`，基线仍为 `1258b622c474beb73f13234c0f00672d8d5b5bbb`。证据：[N01 登录](evidence/N01-codex-login-status.json)、[beta 状态](evidence/N01-beta-state.json)、[基线](evidence/N01-baseline.json)。不读取认证正文。

复用 A/R/M 的隔离安装、首次配置、基础读写、检查点、主动通信/ACK与手动同 Codex 接手；不重跑。旧 alpha 的 HY active Binding、旧 submitted 记录、表单及用户 docs/implementation.md 的 E2E-001/E2E-002 登记原样保留。

| 轮次 | 具体正常任务与收尾 |
| --- | --- |
| 1 | beta 正常 start 接手已有 M 检查点；创建一个明确验收用最小 Work，保存标记、Work ID和状态笔记；等待，Watch 先关闭。 |
| 2 | 从 beta 已保存 M 检查点正常 Fork `e2e-n-peer`，确认新身份/来源/无执行权且不自动启动历史任务；单次真实初始化按新测试职责发送两条 normal 消息（交接前、交接后各一条），保存检查点并 owner stop。只启动这一必要通信身份，不启动管家。 |
| 3 | 目标 beta 启用真实 Watch，Runner 自动投递第一条通知产生一轮；beta 自身先关 Watch、receive/ACK、保存阶段成果并更新同一个 Work，保留第二条消息待后继处理，等待产品 transfer。控制者不代 receive/ACK或代做业务。 |
| 4 | 用户管理入口调用一次 `agent transfer-profile`（Codex→Codex、同模型/强度、稳定 request ID）；产品自动给旧入口发送 handoff 输入，旧模型保存真实检查点并 owner stop。 |
| 5 | 原 Runner 清理后，产品按持久 transfer 中固定 target Binding 自动启动唯一后继；后继实际读旧笔记/Work/交接检查点，保存继承证明，启用新入口 Watch后等待。控制者不手工另开 successor。 |
| 6 | 新入口 Watch 自动投递第二条通知；新模型自身 receive/ACK、完成后续笔记和同一 Work 的 Delivery，保存检查点并 owner stop。这一轮同时用于正常最终停工，不再安排额外回复或模型任务。 |

第二条消息提前排队，只由新入口处理，验证 normal 顺序与 Binding 变化；不是故障注入、重发或 insert 测试。旧入口第一轮 Watch 输入内关闭 Watch，transfer 自身也正常关闭旧 Watch；新入口只有一条待处理消息。运行前为自动触发轮次预留预算，逐个核对真实 `turn/started`，自动输入不得计为免费。Watch 若提前多触发、模型提前停工/工具失败或轮次不足，则先关本轮 Watch并保留现场，缩减尚未执行步骤；不突破 6 轮，不用 controller 假停工/假 ACK刷通过。无法正常交出的资格按合同保留并单列。

验收证据：两个实例真实 session/Binding；Fork 来源检查点、文件hash与无执行权；Message/ACK及投递回执；旧/新 Runner 事件；稳定 transfer ID/target Binding/session/boot checkpoint；同实例目录、笔记继承和后续变化；Work revision/唯一 Delivery；Watch关闭、正常释放与进程停止。E2E-001 停工后账本 submitted 与原生完成不一致仍按真实结果记录，绝不改账本或修代码。

边界：本批是受管 Codex CLI/app-server 自动链路，不能称 Desktop 自动创建/自动交接通过。完整 Desktop自动控制是本版公开限制，不能通过填凭据解除。普通原生 TTY 仍缺本轮原生界面控制，若单独验收，用户需在真实终端执行普通会话原请求的 `aw --home <ordinary-home> session run <真实request-id>`，并反馈真实文件标记与同会话追加响应；本批不另造请求/后台冒充。跨 Harness、HY登录、Git远端、企微、故障矩阵、复杂权限/管家修复不在本批。

N 批完成后停止所有本轮 Runner/Watch；如未开工作台则无新服务需停。保留所有资产、失败和未知状态，结束等待只读复核，不持续自行测试。
