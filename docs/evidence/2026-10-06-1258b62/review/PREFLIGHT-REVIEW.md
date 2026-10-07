# 第 0 组独立口径复核（用户规程确认版）

日期：2026-10-06（Asia/Shanghai）
Lead：01a10c7f-f772-7b00-b4d4-2730820e2d35
执行会话：01a10cd9-47eb-72b1-858b-c9fa3cb3004f
本复核配置：用户已由 Lead 指定 gpt-6.1-sol / high；不由本报告推断底层路由结果。

## 结论与范围

第 0 组口径复核完成，不构成本轮任何测试通过证明。

产品源码 ${SOURCE_REPO} 的本地 HEAD 为 1258b622c474beb73f13234c0f00672d8d5b5bbb，与固定基线一致。起始状态干净，收尾仅发现用户新增未跟踪的 docs/AgentWorkspace-local-E2E-prompt.md；本会话没有写入、暂存或修改它。

已完整阅读用户规程，SHA256 与 Lead 提供值一致：B3156C3BDDF9D2573F5A99B4FC120FA422283554E6369186EFAF66B379803575。它是验收要求的独立输入，不将它误认为固定提交的已跟踪文件。初始缺失规程的阻塞已解除。

已读 AGENTS.md、README、docs/implementation.md、docs/first-use.md、docs/runtime-and-maintenance.md、docs/session-projects.md、随包 capabilities.md，并按需核对设计、安装、客户端/交接/恢复测试入口。本轮未运行测试、安装、服务、真实终端或模型，没有访问密钥、外部渠道或应用私有数据库，没有修改产品源码、全局配置、生产数据。

当前仅执行会话获派发 A 组真实隔离安装和本机 UI/HTTP 检查，以及不调用模型的配置边界检查。真实模型闸门仍 CLOSED；本复核不能把“规程允许负责人执行”解释成自己获准重跑/安装/启动。A 组证据尚未派发给本会话，没有评判 A 组通过或失败。

## 路径和唯一事实源

- 正式根：${E2E_ROOT}。
- 执行真值：reports\E2E-REPORT.md、reports\CHECKPOINT.md、reports\evidence，由执行会话独占维护。
- 本复核仅写 review\PREFLIGHT-REVIEW.md 和 review\CHECKPOINT.md；不写执行方报告/检查点/数据。
- 旧根 ${SOURCE_REPO}-E2E\2026-10-06-1258b62 保留初期证据及旧 review，不删除、不搬已安装 venv。旧报告的“规程待提供”和旧根检查点建议已由本报告取代。
- 后续接续以正式根 reports\CHECKPOINT.md 为入口，不要求再维护根部另一份同义检查点。

## 一项实际静态发现

**首次配置文档的 HTTP 说明过期。** docs/first-use.md:55 写“HTTP 仅允许回环地址，其余使用 HTTPS”，与 docs/session-projects.md:7、随包 capabilities.md:38 的逐配置明确 allow_http 合同矛盾。src/agent_workspace/harness_config.py:22-41 也明确：非回环 HTTP 在 allow_http=false 时拒绝，确认后可继续配置。

影响：初次用户会被误导为内网 HTTP 根本不可使用。此项是已有文档矛盾，不是本轮实机失败；已经留证但未修复。B 组应沿用用户规程/已确认合同测试明确确认路径，不能因这段旧文字把它标为 UNSUPPORTED，不能迁就代码或旧文档改写验收标准。

## 用户规程与开发测试的关键差别

| 已读开发入口 | 真实覆盖/替身边界（静态核对） | 用户规程仍要求的实际证据 |
| --- | --- | --- |
| scripts/install.py:77-126；tests/test_installer.py | 安装器校验来源哈希、空目录和恢复标记；单元测试替换 venv/pip | A 组从固定 wheel 经分发安装器真正安装，源码目录外用绝对可执行文件运行，证明包/资源来自安装目录；安装恢复注入单列 |
| scripts/smoke_wheel.py:94-217 | 真 venv、HTTP、隔离 Git/巡检；有安装失败注入；普通会话只 prepare/show，executable 是测试解释器 | 实际页面 UI 与 API 分开记录；不能据 prepare/show 认定真实普通会话；第二安装复用测试数据前先停旧后台 |
| tests/conftest.py:12-18 | pair 直接 reserve/bind 构造 native-* Session | D/E 两个真实测试实例；目标真实模型在实例内 receive/ACK，控制者不可代收 |
| tests/test_native_sdk.py:67-86 | 使用实际安装 SDK client，但 transport 替换为 Peer 协议夹具 | 真实原生进程、服务请求和副作用，不仅 SDK 协议通过 |
| tests/test_native_transfer.py:144-165、176-204 | 真原生客户端 + 回环响应；Runner spawn 改为线程；发送者 Session 在 193-195 构造 | F 组真实 Runner 进程创建链、原端工具 checkpoint/stop、新端真实 Session/唯一 Binding/读取原笔记/后继 receive/ACK；不能用线程夹具或控制者代做冒充 |
| tests/test_sessions.py:165-214 | POSIX PTY + 伪程序，Windows 跳过；真实 CLI 项只 --help；Windows 项只校验启动参数 | C 组真 TTY/原生窗口、读取随机文件标记、同一原生会话第二轮；PID 或 terminal_requested 不能证明就绪 |
| .github/workflows/sdk-contract.yml | Ubuntu 原生客户端回环测试配置；版本固定 Claude SDK 0.2.163、CodeBuddy SDK 0.3.267、Codex 0.160.0 | 本轮实际 Windows/Harness/SDK 版本和执行结果；工作流文字不是当前提交 CI 成功，也不是本机 E2E |

缺依赖/原生程序的 skip 不计通过；本复核只是阅读，没有运行以上入口。夹具验证的真实 Git/工具副作用仍有价值，但整条混合路径须按规程记 PASS_SIMULATED，并说明哪些组件是真实的；不得替代真实服务 E2E。

## 各组证据口径（对应规程，不增加用例）

| 分组 | 复核要点 |
| --- | --- |
| A 安装/工作台/重启 | 固定提交、wheel 来源/校验值、安装绝对路径、源码外启动；四类页面实际可见；七个 Skill/内置定义随包；HTTP 无授权拒绝；同请求安装恢复不删除标记；第二安装启动前停旧服务，数据和身份保留 |
| B HTTP/配置 | 非回环 HTTP 拒绝/确认后接受，UI 换地址或 Harness 清除确认；URL 原样；配置保存、认证、实际请求、工具、模型/强度分栏；只记凭据引用，缺凭据的原请求保留；真实调用须先解闸 |
| C 普通会话 | 独立空 AW_HOME、虚构产品目录、随机标记；真终端及同会话第二轮；无 Workspace/管家/Agent/Binding/控制者身份；不写角色到产品规则；同请求不重复开窗/任务；不能绕过 TTY 或 .cmd/.bat 限制 |
| D 初始化/实例 | 首次配置 UI 建三份真实管家身份、角色映射/工作根/Skill，尚无会话/巡检/隐含 Work；重试/接入保留资料；两明确测试业务实例的真实 Session/Binding/初始检查点，工具读写的文件和 Git 证据 |
| E Message/ACK | 真实发送/接收/回复；目标 Agent 真实 receive 与 Backend ACK；ACK 只确认通知，不代表正文成功读取、认可或业务完成；两条 normal 保持顺序与持续 Session；查看/继续原请求和刷新不重放；insert 限制不静默降级 |
| F 交接 | 优先获授权的 Codex CLI → Claude CLI；只有一端就单列同端与跨端 BLOCKED；原端真实检查点/停工、旧 Binding 拒绝；新 Session/唯一 Binding、同身份目录资料、后继读笔记和 Message/ACK；继续原交接不生第三执行者 |
| G 管家维护 | 无模型巡检至少两个真实周期；计划/时间/安装位置/去重；关网页与停进程分开；权限经受限 Agent 工具入口测试；指定小范围维修先说明数据变化，动作与独立复查分开；未测维修 NOT_RUN；未知不重放、不复活停用入口 |
| H 桌面项目 | 平台引用/revision、用户真实手动准备、原生运行能力分列；原生项目未验证不能包装成自动创建；已有不支持能力维持 UNSUPPORTED，正确提示另设用例；手动接手须真实定位与停工确认 |
| I 资产/Fork/Work | 资产 revision 冲突、检查点文件、升级保留职责；Fork 身份变化但无执行权复制/历史任务自动运行；最小 Work revision/封存 |
| J 远端/企微 | 专用测试远端+写入授权、测试 Bot+接收目标分别是必要条件；缺项 BLOCKED；不向源码仓/其他群写数据，外发未知不重试 |

先最小真实路径，再扩展覆盖，不先启动全部模型/三管家/六向交接。CLI 与 Desktop 单列，CodeBuddy CLI 不等于 WorkBuddy。Codex Desktop 完整自动创建/跨端交接、Claude/WorkBuddy Desktop 自动控制、SDK insert/steer、CodeBuddy 目录、桌面项目自动管理按随包 capabilities.md 保留本版限制；不将未实现能力写成“只待账号”。

状态沿用 PASS_REAL / PASS_SIMULATED / FAIL / BLOCKED / UNSUPPORTED / NOT_RUN。PASS_REAL 注明哪些本机组件和外部服务真实；不支持项的正确拒绝可独立通过，能力本身仍 UNSUPPORTED。业务结果应有对应文件/工具/Git/渠道证据，不由模型完成文字、ACK 或应用启动成功替代。

## A 组当前准备与隔离复核边界

以下是执行方后续提供证据时的检查点，本轮尚未验证执行环境：

- 使用本轮安装可执行文件绝对路径及显式 --home；普通会话与持久 Workspace 分开空数据目录；虚构产品带随机标记和原文件哈希，不使用生产目录。
- 控制者不绑定测试实例；控制者 AW_AGENT/AW_BINDING 等旧身份不传给被测入口。只记录变量名/处理结果，不导出整份环境。
- AW_HOME 只隔离平台数据，不自动证明原生客户端配置/历史落点全部隔离。按实际 Harness 规则核对本轮进程配置，避免修改全局配置；这是用户规程隔离要求的核查，不断言目前已经发生污染。
- UI 需真实页面观察/操作证据；HTTP 返回只能证明 API。没有 UI/TTY 操作能力时列相关 BLOCKED，给用户具体步骤，不用 API、假截图或进程状态代替。
- Token、密钥、授权头、其他会话信息不进入报告/截图。非模型配置边界检查不升级为探测真实服务、原生会话或外部发送。
- request/operation ID、安装恢复标记、transfer/Binding/锁以及未知结果保留；查询不重放。故障注入先记录可丢弃对象和恢复方法，不破坏生产或测试控制会话。
- 结束只处理已确认属于本轮的进程：先停用巡检/桥接、正常 handoff，再停运行器/后台；保留数据与未知现场，未确认停妥/潜在费用如实列明。

## 需要用户的输入

规程已到位，不再索取文件。首次真实模型调用前由 Lead 集中确认：Harness、实际服务地址、模型/强度、凭据环境变量名、预算/允许轮次；非回环 HTTP 单独明确确认。凭据由用户本机准备，不提交聊天，不复用旧地址的推断授权。

仅相关场景再需要：缺失 Git/Harness 的用户安装/登录、真 TTY/UI 的用户操作、专用远端测试仓及写权限、测试 Bot/目标与渠道授权、Desktop 实际手动步骤。它们不是 A 组全部前置项；可本机发现的版本/路径不反复问用户。

## 下一步

等待 Lead 明确派发 A 组证据路径后复核；不持续轮询、不重跑、不自行调用模型。正式 reports\CHECKPOINT.md 应按规程记录版本/根、已完成与失败、仍运行进程、未决请求、下一条安全操作和证据入口，供执行方安全接续。本复核没有读取或写入它，不提前宣称足够。

