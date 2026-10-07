# 最终当前汇总（2026-10-07，Asia/Shanghai）

本轮限定正常链路验收已收口，完整A–J并非全部通过。基线1258b622c474beb73f13234c0f00672d8d5b5bbb、wheel 0.1.0a1不变。执行方只改隔离验收数据/材料，没有修改产品代码、提交或发布。以下是唯一当前汇总；后续历史章节的轮次、计划、待授权及“下一项”只描述当时状态，不构成当前执行指令。本轮不再启动模型、渠道、服务或补测。

| 原规程 | 当前实测结论 | 尚缺与证明边界 |
| --- | --- | --- |
| A 安装与首次使用 | PASS_REAL：固定wheel、隔离安装/源码外运行、七Skill、真实浏览器与HTTP授权、重复安装和一次原位续装；Q2第二安装同home读回；H第二安装实际UI保留引用 | 两服务终端Ctrl+C后退出码1、进程/端口均关闭；CLI finally及优雅清理 NOT_VERIFIED，未作关闭适配 |
| B 服务/模型配置 | PASS_REAL：官方ChatGPT登录、Sol/low与Luna/low真实执行；HY真实认证失败留档 | 自有模型服务协议/强度效果 NOT_RUN；HY业务接手 BLOCKED，JS入口WinError193为E2E-002 |
| C 普通原生会话 | 普通页及无Workspace UI可见 | 真实TTY两轮、同会话和重复点击窗口行为 NOT_RUN；受管app-server不能替代 |
| D 持久身份与真实模型 | PASS_REAL：UI创建Workspace/三个内置管家身份、测试实例真实session/Binding；G真实maintainer运行 | steward/sentinel真实模型运行 NOT_RUN；初始化没有暗派业务 |
| E 持续通信 | PASS_REAL：M自身消息往返/ACK；T内部Watch自动唤醒、自然busy等待、两normal同session顺序receive/ACK | 未知发送恢复、insert边界及长期运行 NOT_RUN；T boot一次只读原生Shell违反严格仅aw_execute指令，已单列 |
| F 自动交接 | PASS_REAL：R/M正常接手；P同Codex固定唯一后继自动transfer、旧资产接手、真实企微续接和后继本人stop | 跨Harness因认证 BLOCKED；E2E-004终态未持久化、释放后starting，后续transfer阻挡为源码判断，未补测 |
| G 管家巡检/授权/维修 | PASS_REAL：R无模型健康两周期/禁用；G真实maintainer grant/deny/revoke、限定目标写入、同ID正常sync-idle、本人checkpoint/stop | G无新远端变化，不能称故障恢复；verification=degraded/transfer_pending；目标笔记仅本机，未进Fork checkpoint；异常通知/维修链 NOT_RUN |
| H 项目与分区 | PASS_REAL：既有Fork真实UI默认读取、保存、改名、刷新、第二安装重启后保留项目/分区/既有虚构产品目录及revision | 仅local_reference_only，manual_setup_required、native_project_verified=false；原生项目手动建立/复用 NOT_RUN，自动控制本版UNSUPPORTED；旧revision冲突可选项未测 |
| I 资产/检查点/Fork/Work | PASS_REAL：真实资产/hash/Git checkpoint；Q明确Fork来源、新身份及管理Work create/update/Delivery；T Fork新会话/自身工具 | Q Work是管理动作，模型Work NOT_RUN；CAS并发边界 NOT_RUN；模拟撤销仅驱动验证 |
| J 远端与企微 | PASS_REAL限定链：W真实群授权→模型修复虚构tileB→模拟恢复自动入站→实际产物核对→自身群通知；P后继真实群结果查询续接，provider接受且用户确认可见 | 专用远端Git写入 NOT_RUN；生产SBP/UE/CI未执行；W第6轮未本人stop，管理收尾不能替代 |

累计真实Codex原生轮次24（R2+M4+W6+P5+T4+G3），H新增0；HY另有1次认证失败请求，记录tokens/cost为0，不计作Codex轮次或业务成功。原生轮次不等于精确模型API次数。没有独立账单，实际费用、paid API调用次数与全程token总量未核算，不填写估算作实付。企业微信累计3/20条；内部业务Message累计4、ACK4（M2+T2），不含企微。H外发0。

[T/G独立复核](../review/T-G-NORMAL-REVIEW.md)认可限定真实链，无新增产品缺陷；T只读Shell指令偏差、G正常空闲同步/degraded及目标本机笔记边界均保留。[P独立复核](../review/P-NORMAL-REVIEW.md)确认P限定业务与E2E-004。未为复核重跑T/G/P。

E2E-001（停工输入submitted与原生完成不一致）、E2E-002（HY接入/认证）、E2E-004（transfer终态）保持；E2E-003故障推断已撤回。未知/未决输入不重放，beta旧transfer不advance/重试/删除，alpha旧HY有效资格不强制释放。

H实际只保存e2e-q-fork本机Codex引用：项目“AW E2E H · Fork 项目（改名）”，分区“AW E2E · e2e-local”，产品目录fixtures/fictional-product，实例主目录仍为该Fork实例根。首次revision a6f303929380a293f380ff74647c461d155b7e8382da84d13ff0c74ead929d1f，改名/刷新/第二安装读回revision 791c95b9610426afa6557351ce74311ab89ae8794890085d1890ae7ce1433972。没有原生项目、分区、Binding或产品文件副作用。[H最终事实](evidence/H10-final-facts.json)、[表单DOM读回](evidence/H05-second-install-ui.txt)、[正式读回](evidence/H06-desktop-project-readback.json)。[截图](evidence/H05-second-install-ui.png.omitted.md)实际捕获第二安装实例卡片，早于异步表单绘制，不用它证明项目名/目录；[视觉核对更正](evidence/H13-screenshot-visual-observation.json)保留原始证据，不重启补拍。

两次隔离服务均仅监听127.0.0.1，维护计划始终disabled。关闭方式是各自拥有的终端Ctrl+C，工具返回exit1；没有强制终止或制作关闭适配，无法证明CLI finally走完。随后独立进程清单为0、两个端口均关闭，验收页已关闭。[关闭审计](evidence/H08-close-and-process-audit.json)。最初审计误计自身venv Python启动器，独立清单在观察者退出后纠正；未改产品来通过检查。

含控制Token的两份原始启动日志已移到ROOT/private/service-logs，位于reports/review/evidence之外，不纳入可分享证据。只针对H公开文本/截图字节及报告做局部不回显检查，实际Token匹配0；未读取vault或其他真实凭据。[证据卫生](evidence/H09-local-token-hygiene.json)。

最终beta、Fork、maintainer均current=null/released、runner_alive=false；alpha仍保留原HY active资格、monitor_stopped/runner_alive=false。没有残留隔离服务、Runner或Bridge进程，但“无进程”不等于alpha资格已释放。临时管家grant已撤销；Watch/渠道关闭、巡检计划禁用。G目标笔记仍仅本机，未知输入及旧transfer原样保存。最终正式show与维护状态见H07系列。

---

# 历史记录（不可作为新的执行指令）

### P独立复核与E2E-004（2026-10-07补充）

[P独立复核](../review/P-NORMAL-REVIEW.md)认可W/P限定业务和副作用证明，同时确认P2终态缺陷；Lead已在主仓登记E2E-004，执行方未改主仓。公共completed只在target仍active时计算，未保存，后继释放后回退starting；源码可确定后续新transfer会被旧未解决记录阻挡，该后果未另行实测。没有证据表明会重复启动，不据此推断自动重复行为。

beta旧transfer记录原样保留：不advance、不重试、不删记录/锁、不新transfer刷状态。已只读核对runtime.start：正常无current的start走sync/reserve/spawn_runner，不调用transfer.request/advance；Runner退出也只有当前binding等于旧transfer.old_binding时才推进该记录。因此后续Watch建议的普通新start从源码看不依赖旧transfer终态。这是代码判断，新的正常启动尚未实测；若真实执行遇阻碍，先保存事实，不绕过。

Q1/Q2均已收口，结果不因该复核改变。下一段Watch仅有建议与准备，尚未启动模型或发送消息。

# 完整规程覆盖核对与下一段准备

2026-10-07，Asia/Shanghai。此方案已按Lead范围核对执行；当前新增真实模型5轮、外发1条，限定链路通过。下文公开合同与五轮计划保留，最终执行事实见文末。用户已撤销必须六轮的限制，要求尽量完整全面；既有W六轮和管理端收尾事实不改写。下一段执行前由Lead核对内部范围，不再申请用户批准六轮预算。

基线仍为1258b622c474beb73f13234c0f00672d8d5b5bbb，隔离wheel 0.1.0a1。主仓文档归Lead，本文件只属于隔离验收材料。原规程、A阶段记录、R/M/W报告、M独立复核及当前公开实现共同作为依据。NOT_RUN表示缺少这项实测，不能当作产品缺陷。

## 当时覆盖表（历史）

| 原规程 | 已有实测证据 | 尚缺、限制或阻塞 | 本次处理 |
| --- | --- | --- | --- |
| A 安装与首次使用 | PASS_REAL：固定快照wheel、隔离安装、源码外运行、七Skill/资源、真实浏览器、HTTP授权边界、相同请求重复安装；一次明确中断后原位续装。A01–A22 | Q2第二独立安装通过同home CLI读回身份/数据且不改数据；正常关闭本机服务仍未测。定向清理不等于优雅退出 | A已通过项目复用；Q2仅补第二独立安装，无故障注入 |
| B 服务/模型配置 | PASS_REAL：官方ChatGPT登录、原生模型元数据，Sol/low及Luna/low真实执行；HY真实错误保留。R01–R03、M18 | 自有服务的HTTP确认与真实协议/强度效果未测；HY SDK入口要求登录；JS入口WinError193为已观察接入缺口E2E-002 | 沿用官方账号Luna/low，不换服务、不复制凭据 |
| C 普通原生会话 | 普通页/空Workspace UI可见，A09–A12 | 真实TTY两轮、同会话、重复点击不新增窗口尚未实测；当时原生控制能力不足。受管app-server证据不能替代 | NOT_RUN/当时环境BLOCKED，下一段不扩到TTY |
| D 持久身份/真实模型 | PASS_REAL：正常UI创建Workspace与三个内置管家身份，两测试实例、真实session/Binding、资产与检查点，R05–R13/M18 | 三个管家真实模型运行未测；没有为初始化偷偷分派业务 | 复用beta，不新增实例或管家任务 |
| E 持续通信 | PASS_REAL：两实例自身发送/receive/ACK/回复，同一原生会话追加输入，M18及独立复核 | T已证明内部Watch自动唤醒、自然busy等待与两normal同会话有序处理/自身ACK；未知发送恢复及insert边界仍未测 | M往返复用；T用既有Fork/beta补Watch，无新身份或故障矩阵 |
| F 自动交接 | PASS_REAL：旧入口正常自停、正常start接手旧检查点并实际读旧资产，R/M；W恢复也读既有材料 | P批自动transfer固定后继、实际材料接手与真实企微续接PASS_REAL；跨Harness业务接手因HY认证BLOCKED，不能改称永不支持 | P批已补同Codex自动transfer与渠道续接；停止后的transfer终态显示不一致单列 |
| G 管家巡检/授权/维修 | PASS_REAL：无模型健康计划两周期、五实例healthy、正常禁用，R11–R12 | G已证明真实maintainer未授权/授权/撤权、目标限定写入和同ID正常sync-idle；异常通知与故障恢复仍NOT_RUN。正常同步不证明恢复 | G已独立收口，临时授权撤销；不制造异常，不扩大历史维修 |
| H 项目/分区 | 随包限制说明/UI可见 | 平台原生项目/分区自动控制本版UNSUPPORTED；本机引用保存、用户真实手动准备及复用未实测 | 保留独立证明边界，不修改私有数据库 |
| I 资产/检查点/Fork/Work | PASS_REAL：实际读写/回读/hash、真实Git检查点、接手材料保留，R/M/W | Q1真实管理Fork来源/新身份/无执行权和管理Work create/update/Delivery已通过；T已补Fork真实新会话/自身工具；模型Work及CAS并发分支仍未测；S撤销仅驱动检查 | P交接不夹带Fork/Work；Q1独立补实际管理数据合同，不冒充模型业务 |
| J 远端/企微 | PASS_REAL限定链：真实群授权→模型限定修复→模拟事实恢复自动入站→实际产物复核→两条自身群通知，回执与用户可见，W16/W18 | 真实专用远端Git写入NOT_RUN；生产SBP/UE/CI不在范围；W最终模型自停未完成，是错误编排，管理正常收尾不能替代 | P批新增专用群1条结果回复，provider接受且用户明确确认可见；不启用远端Git写入 |

结论：已有安装、持久实例、主动通信、资产/检查点、正常手动接手和限定企微业务链证明；完整A–J尚未全部通过。E2E-001停工输入账本submitted与真实完成不一致仍为已确认缺陷，不能因继续验收忽略或手改。E2E-003入站故障推断已撤回，不重新登记。

## 已核实公开合同

- `agent transfer-profile`先预检目标程序/SDK/凭据，固定原Binding、target_binding和request ID；相同请求返回原记录，不产生替代后继。选择codex、gpt-6-luna、low和现有官方登录，不填自有base URL。
- `runtime.handoff_request`关闭Watch并投递真实handoff提示。旧Runner在handoff期间停止Bridge触发；旧模型自身创建checkpoint并`agent.stop`，等待native idle、关闭原客户端、发布handoff、释放资格。
- 旧Runner释放运行器锁并清理后调用`transfer.advance`，产品自动启动固定target Binding。控制者不手工start后继。后继boot携带交接检查点及材料；只有观察真实boot完成后的checkpoint revision，transfer才达到completed。这个初始checkpoint可能由Runner创建，不能冒充模型主动调用checkpoint.create。
- Bridge配置保留在同实例。只要启用且未耗尽重启额度/处于fatal状态，新Runner会启动同一Bridge；这是源码路径，实际新连接ready和旧连接退出仍需记录，不能仅凭配置宣称已续接。
- `bridges._event(sent)`将实际provider结果同时写入`channels/wecom/sent/<发送ID>.json`。本轮通过正式`asset.read`成功读到W旧成功回执：state=sent、receipt.errcode=0、revision=1ba41aa59ce94e27cfb1fe865f6daf55ff915a8aa302170680cc6dd01836d81a。此为真实平台写出的可读资产，无复制、伪造或改受保护目录。
- `bridge.send`同Binding、渠道、目标、文本及ID完全一致时返回原记录，但要求渠道仍启用。不同Binding不能借旧ID重新发送。下一段优先读公开sent资产，不重复调用发送。
- `.aw-local`始终不是asset.read允许范围。停止前等待实际回执落盘；queued不是送达，未知结果不重发。用户可见确认与SDK接受分别记证据。

核对位置：src/agent_workspace/transfer.py，runtime.py的handoff_request/Runner.run/_run_owned/_complete_inputs，bridges.py的send/BridgeManager._event，commands.py的assets，随包handoff/capabilities提示及docs/runtime-and-maintenance.md。transfer/runtime/bridges/util与隔离固定源码hash一致；正式安装asset.read实测成功，不仅静态推断。第一次管理只读探针误用agent字段被拒，随后按实际签名agent_id读成功，零模型。

## 下一段最短自然旅程：预计5轮，外发1条

目标是同一beta的正常自动交接后，后继接到新的真实群业务查询，读已有模拟结果并汇报，最后自身保存检查点和正常停止。不是追补旧W已关闭入口。

1. **原端初始化1轮。** 正常start beta，从现有真实W检查点读取任务材料；写一个明确的后续验收任务资产，说明“查询原模拟结果，不重跑、不修复、不发送初始化通知”。原模拟Bridge保持disabled，不重放旧失败/恢复ID。模型读成功产物和摘要，保存当前阶段信息后等待。
2. **原端handoff 1轮。** 管理端只调用一次稳定ID的transfer-profile，目标同Codex/Luna/low。真实handoff输入唤醒原模型；模型自己保存检查点并stop。预期由产品自动启动唯一后继，控制者只读记录。
3. **后继boot 1轮。** 后继读原端材料与实际模拟结果，记录继承证明并等待。允许启用的正式WeCom Bridge随新Runner连接；控制者确认旧进程退出、新Binding/session唯一及新ready，再由Lead协调用户发送新群查询。若渠道尚未ready，不要求用户提前发送，也不推断离线回放。
4. **后继真实群查询1轮。** 用户仅在专用E2E_TEST_GROUP群@Bot询问“请核对上次模拟导航导出的结果与产物”。真实Bridge自动入队，新模型实际读Operation/Job Summary/产物，回复限定结论一次，使用全新固定发送ID。模型记录该ID后等待，不靠循环读未落盘回执强求同轮停工。
5. **正常收尾1轮。** 观察真实公开sent资产落盘后，用正式normal输入要求完成既定收尾。模型自身`asset.read channels/wecom/sent/<新ID>.json`核对本次回执，关闭渠道新触发、保存结果与检查点、调用agent.stop并结束。控制者核对实际native完成、释放/退出；不代模型checkpoint/stop冒充成功。

五轮是预计，不是硬凑轮数。所有boot/handoff/外部自动输入都计入真实轮次；按实际原生started/completed记录。若模型多一轮才能完成正常收尾，先说明原因与剩余必要动作，不升档、重做业务或为了控制轮数注入受保护读取。无新增自动巡检、内部Watch、第二测试身份、生产任务或群消息矩阵。

模拟事实的覆盖复用W已证明的自动失败/恢复输入；本段后继读真实既有模拟事实，并由真实群查询触发业务续接。**本段不新增模拟事件，不把读取旧结果称为新模拟事件跨Binding自动投递通过。** 若Lead认为必须补一个新模拟业务阶段，应先单独明确自然业务和独立新事件，再调整夹具；不能换ID重放旧失败骗取证明。

## 风险与前提

- 已读当前beta AGENTS.md：仍含历史W的六轮上限、旧修复任务及错误的.aw-local回执读取要求。执行前必须先归档该历史文件，再通过公开asset.write和已读revision换成本段明确测试职责；否则正常boot会再次继承错误指令。只改隔离测试实例任务，不改随包提示或产品代码。新的任务声明历史W已结束、当前只是结果查询与handoff；两次boot都读同一当前任务，以实际handoff材料区分原端/后继。
- 启动前只读确认当前beta空闲、实际Codex exe/官方登录仍有效、Luna/low配置、未决transfer不存在，旧alpha HY资格不动；不复制认证。
- 正式WeCom沿用DPAPI薄启动器和同一白名单群；仅在原端初始化后启用已配置渠道，交接窗口不安排群输入。源码预期关闭再连接，不保证上游离线消息保留。若旧连接子进程未退出或新连接非ready，停止推进并保留现场，不开并行Bot。
- max_restarts=1允许首次启动；0会跳过首次启动。handoff后状态/额度若阻止续接，记录真实状态并按公开配置入口决定正常重启，不能暗改账本或宣称无缝续接。
- 原模拟observe_recovery夹具现已成功，不能原样重启其失败断言或历史事件回放。当前无需修改夹具或启动它。
- E2E-001可能使handoff/stop输入仍submitted，即使原生完成和实际资格释放。保存原生证据、保持旧记录，不重放或修代码。
- `outcome_unknown`、relay_failed或旧端未交出时只查看原记录；不删锁、不强制释放、不另start successor。transfer源码的前置检查不能保证实际账号模型调用成功。
- 预计新增企微出站1条，累计由2/20增至3/20。真实模型费用没有独立账单；原生轮次不是API调用次数或精确费用。

本准备交付后等待Lead内部范围核对；当前没有新模型启动、群发送、WeCom连接或任何产品源码/主仓文档改动。


## P批最终结果（2026-10-07，该批完成时）

同Codex正常自动transfer、后继真实企微查询续接与模型自行停工取得限定PASS_REAL。新增gpt-6-luna/low原生started/completed各5；企微新增1条，累计3/20。没有控制器代发、代checkpoint/stop、手动start后继、重配渠道恢复、模拟新事件、生产业务、主仓源码或文档改动。W原有六轮与管理端收尾事实保持历史，不能用本段追补W第6轮自停。

| 目标 | 实际证据 |
| --- | --- |
| 自动交接 | 稳定请求p-beta-normal-transfer-001，固定后继b4c8d06c2c2b846dd8cede789542b13b3；原Binding ba97e52906d19449b8313aa9c053f57b7/session 01a11205-93c8-7d22-b148-efef0937bc65。原模型checkpoint cf9b87354efef429c8b4df26a15eb38ae、revision d47d006a03b8f7f6cbe2f770ae806d83ecd99b2b，自身stop后旧完整进程树均退出；产品自动创建后继session 01a11207-e5fd-7790-9bc5-4a68dd05a153，同目录实际读交接checkpoint与模拟摘要/产物。P06–P09、P07旧退出审计。 |
| 渠道自动续接 | 同一WeCom配置generation gefc2a448231a453499f4fb46f80bf95a，原连接ready 00:22:57.749、新连接ready 00:24:41.211（北京时间）；原所有子进程退出后新连接，无手动重配。原模拟Bridge始终disabled。 |
| 后继真实查询/回复 | 用户实际手动@，Lead确认发送且未CUA代发；正式事件b2d2731ee2919eaf6a965dcf53174946于00:26:58.506入队ia066e81877d136b7f5bbf42e6876df41822cc53f，对应真实turn 01a1120a-2cfe-72f2-8e91-3a0573e23779。模型实际回读sim-build-2结果与两行产物，自身唯一发送p-ops-result-query-reply-001，00:27:39.832真实sent/errcode0。P11公开回执、P15真实事件/工具证明。用户随后明确确认“已看到结果核对回复”；P17保存该独立可见证据，Lead未CUA或代发。服务端接受与用户可见分别记录。 |
| 后继模型正常停止 | normal收尾输入p-beta-model-normal-stop-001对应turn 01a1120b-8118-7622-84bb-a9fe5df96b30；模型自己asset.read公开channels/wecom/sent回执、关新触发、保存checkpoint c3788071b0e70473aa054a218b12688eb/revision 36da4bc44cc714f5c442925d57814f3c46af60b3、agent.stop。最终handoff h4c8d06c2c2b846dd8cede789542b13b3，current=null/released/runner_alive=false，完整后继进程树退出。P14–P15；没有管理端代收尾。 |

**状态显示问题单列：** P09公开transfer-status在后继active且boot完成时返回completed；原持久transfer记录仍starting。P15后继正常释放后，公开transfer-status回退到starting。源码status只在当前Binding等于target时计算observed_target，未持久保存completed，因此原记录失去终态展示。实际自动接手/渠道续接/停工已证明；这个状态不一致不能隐去，也不能当作可重新启动的许可。未修产品、改账本或重试，交Lead独立判断登记。既有E2E-001仍在：原handoff和本次stop输入submitted，native均completed且Binding真实释放；不手改或重放。

原生5轮：原端boot、handoff、后继boot、真实群查询、正常收尾。模型误加agent.show/bridge.switch binding、bridge.send漏text的工具拒绝均保留，随后在原轮内按真实签名纠正；失败调用没有额外发送，不描述成无错误通关。P12观察器曾按Windows默认编码读中文回执产生显示乱码，只修隔离观察器UTF-8读取；公开回执、原文件和P15最终证据正确，产品数据未修改。

[完整事实与ID（含后到可见确认）](evidence/P18-final-facts-with-visibility.json)、[最终快照](evidence/P14-final-snapshot.json)、[最终资格](evidence/P15-final-beta-show.json)、[完整覆盖表](P-COVERAGE-AND-PLAN.md)。模拟产物hash仍2ff4deccf19bcc95d68f8f048148578841e539999a3c73aa0535ddf3ee276c7b。仅新增真实企微事件跨自动交接续接，不声称新模拟事件跨Binding自动输入验证。此句为P当时观察：后续Q补静态Fork/管理Work/第二安装复用，T补Watch及Fork真实relay；管家授权维修、普通TTY和远端Git等仍未测/限制，完整A–J尚未通过。alpha旧HY资格与历史未决输入未触碰。本段结束，不继续监控、连接、发送或启动新模型。



## Q批最终结果（2026-10-07，该批完成时补充）

Q1与Q2按顺序完成，新增模型0、外发0、服务0。P真实自动交接/群续接/模型自停及用户可见确认仍有效，见下面P记录；没有重跑P或改变原beta/alpha资格。完整A–J仍不全部通过。

| 新增正常覆盖 | 实测结果与证据边界 |
| --- | --- |
| I组Fork数据合同 | 从真实P checkpoint `c3788071b0e70473aa054a218b12688eb`/revision `36da4bc44cc714f5c442925d57814f3c46af60b3`创建新身份e2e-q-fork。新分支初始revision `8308658c1344bfe75fc99867e52e0b4f7519dda0`，父提交严格为来源revision。70个保存文件只`.aw/identity.json`必要变化，69个原文件blob相同。新实例current=null、has_run=false、无Binding/session，runtime=not_running；未继承.aw-local运行配置/Bridge/输入或private凭据。原beta/alpha与所有既有main记录不变。[Q1事实](evidence/Q08-Q1-final-facts.json)。这是实际管理Fork，不是Fork模型relay已通过。 |
| I组最小Work | 单个管理验收Work `w6e0f8c4a4a67405ea2fd4e0a11b95b13`，owner=e2e-q-fork。create revision `288b765f8095391679816cc1e0263dc9dd8be3cb` → 正常update revision `79daf01cc115a9f0fcd5038104557f2bc1a0d0be` →唯一Delivery，refs均有实际来源/hash。核对记录`notes/q-fork-verification.md`由公开asset.write保存为本机资产，未额外做Git checkpoint；Delivery对此明确标注。管理端真实完成数据核对，不冒充模型业务交付，不声称refs自动校验或并发CAS分支已实测。 |
| A组第二独立安装复用 | 同wheel/hash，经正常离线installer安装到q-second-app，无extra，源码外新绝对aw/Python模块确认来自该安装。显式指向同一workspace-home，读回Workspace/身份、P检查点、Fork材料、Work revision及Delivery。[Q2事实](evidence/Q13-Q2-final-facts.json)。前后registry与全部实例文件字节、共享Git所有refs完全相同。不是第二台机器、不同版本迁移、UI优雅重启或第二安装SDK/WeCom实际运行验证。 |

仅新增授权的1个Fork身份、1个管理Work、1份核对资产和1个独立安装目录，原位保留；没有配置或启动新Fork、Harness、管家、Watch或Bridge。模拟产物hash保持2ff4deccf19bcc95d68f8f048148578841e539999a3c73aa0535ddf3ee276c7b。alpha旧HY资格及历史submitted/transfer记录不修复、不重放。主仓仍仅Lead/user既有文档改动，执行方未改主仓。P累计17个Codex原生turn及群3/20计数不增加。

[同一覆盖表](P-COVERAGE-AND-PLAN.md)已补A/I实际结果；[后续最短Watch建议](R-WATCH-NEXT-STEP.md)只做准备，尚未执行。其余管家受限工具、普通TTY、远端Git和边界项仍保持未测或限制。当前Q收口，不自动启动下一段。



## T批内部Watch最终结果（2026-10-07，该批完成时）

正常Watch自动唤醒、两个normal消息在同会话有序接收/ACK、Fork真实新会话和双方自身停工取得限定PASS_REAL。新增gpt-6-luna/low原生started/completed各4，内部消息2、ACK2、企微0；累计Codex原生turn21，群发送仍3/20。未新建身份/Work，未启动管家、Bridge、生产任务或额外服务；beta旧transfer文件hash保持，alpha HY现场未改变，主仓未改。

| 本段覆盖 | 实际证明 |
| --- | --- |
| Fork真实新会话 | e2e-q-fork Binding bf000d594021742cea71d260e2399277f，session 01a1121b-af94-7e13-9035-fbdaf72ded67，boot turn 01a1121b-cb0b-7442-b170-2e2b85301d76。模型自身读新identity和Q核对资产，确认来源不是当前身份，亲自发送两条消息，保存自己的记录、checkpoint cc2e9fab3e2a1422cb3c6c9c084e8c93e/revision 0f8c6a54a861563a41ef982bc78d62d26d17ca63并stop。补Q此前仅静态Fork的实际relay证明，不改写Q管理Work为模型完成。 |
| 两条消息真实发布 | r-watch-normal-001、r-watch-normal-002均来自真实Fork模型，to=e2e-beta，delivery=normal，publication published；第二条message_refs引用第一条。没有第三条消息/额外回复、控制者代send/receive/ACK或手动receiver业务input。 |
| Watch自动唤醒与同会话 | 管理端只开启message.watch；Runner原生通知文本真实进入beta session 01a1121a-7b6d-7f70-aa94-d40cd3afbe8e、Binding bfe56718746f34061bcf4334d686d159a。两通知各自对应turn 01a1121d-2d4b-74d3-adba-e65e721a87ca与01a1121d-8e97-7322-ba91-1a8be0038f27；模型逐条message.receive，两个ACK均published且receiver/Binding匹配。Watch直接adapter.notify，不经queue_input，不能虚构通知输入账本ID。 |
| 自然busy等待及实际业务顺序 | 00:47:58.099、00:48:01.103、00:48:04.106自然观察第二条waiting_idle，均在第一条turn完成00:48:04.268之前；第二条turn开始00:48:09.384之后。未加sleep、钩子或延长业务。notes/t-watch-order.md实际保留第一段再追加第二段，hash 4e4d21bfa748a956a58246686785aec351e711ddb5c6df26875d22cdf4291f35。ACK表示通知接收；有序资产是本段虚构业务完成的独立证据。 |
| 模型自停与清理 | beta在第二条通知轮自己保存checkpoint c7c9aa716dfb045c9beabb5f40c5e0db0/revision ede83b0d747379d97863c41df5af3ab7fc878d80并stop。两端native均completed，最终current=null/released/runner_alive=false、Watch关闭、所有Bridge关闭，已记录39个本轮进程全退出。没有管理端代checkpoint/stop。 |

**测试指令偏差单列：** beta boot在真实原生会话中执行过一次只读Shell命令，读取实例内capabilities、AGENTS、P checkpoint和notes/p-final.md（exit0，source=unifiedExecStartup）。因此不能宣称全段严格“仅aw_execute”。消息发送/receive/ACK、资产写入、checkpoint和stop均实际由模型aw_execute完成，不是控制者Shell假原生会话或代造副作用；未见该命令写文件、读凭据或碰生产。另有一次asset.write误加binding被拒，随后按真实签名在原轮内纠正。事实原样保留，不为刷无错重跑。

原Fork boot保存checkpoint并stop后，输入账本仍submitted；beta boot为completed。Watch通知本身无queue_input账本。native终态和真实释放已确认，E2E-001未修复、未手改/重放。E2E-004旧transfer原记录未变，本次只是普通start和Watch成功，不声称transfer状态已恢复。[T最终事实](evidence/T15-final-facts-with-native-trigger.json)、[通知与busy证据](evidence/T14-native-watch-trigger-and-busy-proof.json)、[原生最终快照](evidence/T11-final-snapshot.json)、[退出审计](evidence/T11-process-exit-audit.json)、[轮次与消息账](evidence/T-model-budget.json)。

同一覆盖表已补E/I。剩余主要真实正常路径为G组管家受限工具授权/撤销及有限维修；普通TTY/UI正常重启、自有模型服务、跨Harness认证、远端Git和边界项按原状态保留。下一段应单独界定测试目标与授权，再做真实管家调用，不把普通管理CLI当模型权限证据。本轮只收口Watch，不启动管家或下一模型任务。



## G批受限管家最终结果（2026-10-07，该批完成时）

已完成3轮gpt-6-luna/low真实受限管家链：未授权写入拒绝→仅授权目标的正常sync-idle与笔记写入→撤权替换拒绝→模型自身保存checkpoint/stop。新增模型3轮，内部消息0、企微0、服务0；累计Codex原生turn24，群仍3/20。未启动巡检计划/Sentinel、制造故障、修旧记录或改产品/主仓。

真实maintainer Binding b03a2ce413aa24da7bb85ab6247d8930e、session 01a11225-0f4b-7423-93b7-ae3107f47105；三个turn分别为01a11225-3009-75f0-b370-661f3cfb75e2、01a11229-048d-7203-af29-eeb8a0e8f5a0、01a1122c-c753-7ed3-9d13-e085bce9d34f。[完整事实](evidence/G18-final-facts.json)。

- 原grants为空；第一轮实际目标asset.write拒绝，笔记不存在。管理端仅授予asset.write/maintenance.repair、targets=[e2e-q-fork]，没有'*'或OS/native权限。
- 第二轮模型对空闲Fork执行sync-idle，固定唯一g-sync-idle-fork-001，state=applied，result为正常同步到原分支；verification=degraded、issue=transfer_pending。同ID第二次调用返回完全相同的已存回执，源码缓存路径不重做动作。此次没有新的远端变化或异常，不能称故障恢复/整个Workspace健康。
- 前置“全部本机文件等于checkpoint”检查发现停工后native日志正常追加；来源分支与context基线一致，现有三方同步合同没有重叠修改。保留原日志，不清理它；实际同步后所有既有目标资产hash不变，随后只新增notes/g-maintenance-scope.md。
- 模型实际写入并asset.read回读目标笔记；SHA256 0dd0390cf8293c2a337b718217b1690aac44453d5bbb2d882068adafe6d36a5f。该笔记是Fork本机资产，没有进入新的Fork checkpoint，不能称目标快照已发布。
- 管理端正常撤销commands/targets为空。第三轮模型用实际revision替换相同笔记被权限门拒绝，字节保持第二轮结果；不重试、换路径或绕过。
- 模型自身保存checkpoint c6267872ca59048a2ae88d100f9c8faa6/revision 357d69abde5000badb426a05e6bfb4f2b1f6296d，再agent.stop。native completed3/3，current=null/released/runner_alive=false、19个记录进程退出；临时授权已撤销。maintainer内置身份、source定义及Workspace角色映射不变，alpha/beta元数据与beta旧transfer文件不变。

本段native commandExecution为0，业务全由aw_execute执行。保留首次agent.show误加binding以及只读确认目标不存在时asset.read失败；它们与两次预期权限拒绝分列，不包装无错误通关。初始观测脚本的文件完全一致断言过严，最终Workspace完整对象比较也因正常main revision前进而调整为业务字段比较；仅调整只读证据核对，没有改变产品或既有数据来让测试通过。

G最后stop输入仍submitted，boot与第二轮输入completed；原生3/3完成和实际释放已证明，E2E-001保留不改/重放。E2E-004旧transfer记录保持，复查degraded也不触发维修它。[前置差异解释](evidence/G01-sync-precondition-clarified.json)、[未授权拒绝](evidence/G06-phase1-denial-proof.json)、[授权正常同步/笔记](evidence/G11-phase2-authorized-proof.json)、[撤权拒绝与字节](evidence/G13-revoked-denial-and-note-proof.json)、[退出审计](evidence/G16-process-exit-confirmed.json)、[模型checkpoint回读](evidence/G17-model-checkpoint-readback.json)。

同一覆盖表G已补实际受限工具授权/撤销与一次正常sync-idle；异常发现→模型通知→故障恢复完整链仍NOT_RUN，基础健康两周期只复用R。下一项H已由Lead授权，仅工作台UI引用与可达正常关闭/重启，无新模型。G本段结束，H结果另记，不提前宣称完成。

