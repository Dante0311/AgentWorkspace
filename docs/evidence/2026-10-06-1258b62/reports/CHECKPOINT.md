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

---

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

---

以下保留前段观察时事实，当前运行状态以上述T最终证据为准。

### P独立复核与E2E-004（2026-10-07补充）

[P独立复核](../review/P-NORMAL-REVIEW.md)认可W/P限定业务和副作用证明，同时确认P2终态缺陷；Lead已在主仓登记E2E-004，执行方未改主仓。公共completed只在target仍active时计算，未保存，后继释放后回退starting；源码可确定后续新transfer会被旧未解决记录阻挡，该后果未另行实测。没有证据表明会重复启动，不据此推断自动重复行为。

beta旧transfer记录原样保留：不advance、不重试、不删记录/锁、不新transfer刷状态。已只读核对runtime.start：正常无current的start走sync/reserve/spawn_runner，不调用transfer.request/advance；Runner退出也只有当前binding等于旧transfer.old_binding时才推进该记录。因此后续Watch建议的普通新start从源码看不依赖旧transfer终态。这是代码判断，新的正常启动尚未实测；若真实执行遇阻碍，先保存事实，不绕过。

Q1/Q2均已收口，结果不因该复核改变。下一段Watch仅有建议与准备，尚未启动模型或发送消息。

## Q批最终结果（2026-10-07，该批完成时补充）

Q1与Q2按顺序完成，新增模型0、外发0、服务0。P真实自动交接/群续接/模型自停及用户可见确认仍有效，见下面P记录；没有重跑P或改变原beta/alpha资格。完整A–J仍不全部通过。

| 新增正常覆盖 | 实测结果与证据边界 |
| --- | --- |
| I组Fork数据合同 | 从真实P checkpoint `c3788071b0e70473aa054a218b12688eb`/revision `36da4bc44cc714f5c442925d57814f3c46af60b3`创建新身份e2e-q-fork。新分支初始revision `8308658c1344bfe75fc99867e52e0b4f7519dda0`，父提交严格为来源revision。70个保存文件只`.aw/identity.json`必要变化，69个原文件blob相同。新实例current=null、has_run=false、无Binding/session，runtime=not_running；未继承.aw-local运行配置/Bridge/输入或private凭据。原beta/alpha与所有既有main记录不变。[Q1事实](evidence/Q08-Q1-final-facts.json)。这是实际管理Fork，不是Fork模型relay已通过。 |
| I组最小Work | 单个管理验收Work `w6e0f8c4a4a67405ea2fd4e0a11b95b13`，owner=e2e-q-fork。create revision `288b765f8095391679816cc1e0263dc9dd8be3cb` → 正常update revision `79daf01cc115a9f0fcd5038104557f2bc1a0d0be` →唯一Delivery，refs均有实际来源/hash。核对记录`notes/q-fork-verification.md`由公开asset.write保存为本机资产，未额外做Git checkpoint；Delivery对此明确标注。管理端真实完成数据核对，不冒充模型业务交付，不声称refs自动校验或并发CAS分支已实测。 |
| A组第二独立安装复用 | 同wheel/hash，经正常离线installer安装到q-second-app，无extra，源码外新绝对aw/Python模块确认来自该安装。显式指向同一workspace-home，读回Workspace/身份、P检查点、Fork材料、Work revision及Delivery。[Q2事实](evidence/Q13-Q2-final-facts.json)。前后registry与全部实例文件字节、共享Git所有refs完全相同。不是第二台机器、不同版本迁移、UI优雅重启或第二安装SDK/WeCom实际运行验证。 |

仅新增授权的1个Fork身份、1个管理Work、1份核对资产和1个独立安装目录，原位保留；没有配置或启动新Fork、Harness、管家、Watch或Bridge。模拟产物hash保持2ff4deccf19bcc95d68f8f048148578841e539999a3c73aa0535ddf3ee276c7b。alpha旧HY资格及历史submitted/transfer记录不修复、不重放。主仓仍仅Lead/user既有文档改动，执行方未改主仓。P累计17个Codex原生turn及群3/20计数不增加。

[同一覆盖表](P-COVERAGE-AND-PLAN.md)已补A/I实际结果；[后续最短Watch建议](R-WATCH-NEXT-STEP.md)只做准备，尚未执行。其余管家受限工具、普通TTY、远端Git和边界项仍保持未测或限制。当前Q收口，不自动启动下一段。

---

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

[完整事实与ID（含后到可见确认）](evidence/P18-final-facts-with-visibility.json)、[最终快照](evidence/P14-final-snapshot.json)、[最终资格](evidence/P15-final-beta-show.json)、[完整覆盖表](P-COVERAGE-AND-PLAN.md)。模拟产物hash仍2ff4deccf19bcc95d68f8f048148578841e539999a3c73aa0535ddf3ee276c7b。仅新增真实企微事件跨自动交接续接，不声称新模拟事件跨Binding自动输入验证。Message Watch、Fork/Work、管家授权维修、第二安装复用、普通TTY和远端Git等仍按覆盖表未测/限制，完整A–J尚未通过。alpha旧HY资格与历史未决输入未触碰。本段结束，不继续监控、连接、发送或启动新模型。

---

以下为既有阶段记录，当前结果以上述P批最终事实为准。

# CURRENT — 2026-10-07 W批限定真实业务链通过，管理端正常收尾完成

- 用户随后直接回答允许额外1轮仅模型正常收尾，但确认到达时管理端已按明确既有指示完成释放。W19-late-extra-stop-authorization.json保留该晚到授权，未使用：原入口已关闭，另开新入口不能补证明原第6轮模型自停。不为补证制造新入口，实际仍6轮，无第7轮。

- 最终W18-final-facts.json：本批native started/completed各6，Luna/low，企微2条sent/errcode0且用户确认均可见。真实企微授权入站、限定虚构tile-B修复、模拟实际重跑、恢复事实自动触发复核和群报告通过；不代表生产SBP/UE/CI或Desktop/跨Harness。
- 验收编排错误导致本轮模型自停未完成，管理端正常收尾。指引错误要求asset.read受保护.aw-local回执，被产品正常保护规则拒绝；不是产品bug或模型违反合同。Agent未编造回执/自停。按已明确的既有清理授权，通过公开checkpoint.create/agent.stop管理入口实际收尾，操作者明确为管理端；不追加第7轮、不强制清资格/删锁。不得把此项当成模型自身stop通过。
- 最终真实检查点c3a06c5a7b4ea4286bd358946c91bd271，revision5b74ff43ef0cba105edf710fe774b9c8686caab7已回读；W17-management-operation.json记录操作者。beta current=null，Binding b0ab72f3040a545a8a82320d01000f82c已released，handoff h0ab72f3040a545a8a82320d01000f82c，runner_alive=false，Watch关闭。
- W18-process-exit-confirmed.json核对本轮Runner/正式WeCom全部子进程/模拟观察器退出，两个Bridge配置disabled；无本轮残留连接/服务，无新输入或待发送。旧alpha HY资格未触碰。
- W16记录真实wecom事件87061719af64e13b06b1e5b7d3582ba5，23:58:56.623375入队，输入ie51d0f4ecb591fa255e7516481d0e587c79c2286对应第5轮；23:59:06.618233恢复入队iab5c77e7fb3fb7c9e62dfd3868331c542f65e16c对应第6轮。真实产物hash2ff4deccf19bcc95d68f8f048148578841e539999a3c73aa0535ddf3ee276c7b，失败归档/限定修复/成功产物均保留。
- 首次日志路径错误已补读；用户更正先前已发授权的说法，旧企微故障结论撤回并保留历史。23:51截图早于ready23:55:42，实际接收事件与截图对应关系未核实，不推断离线回放。用户手工消息证据，Lead未CUA代发；两图W09-first-report-visible.png、W12-recovery-report-visible.png已保存。
- 夹具本次以receive-only恢复观察器续读已有事实，不重放旧Binding失败ID；失败/恢复各1事件，重复观察没有增加轮次。不是通用跨Binding回放能力证明。S驱动可逆撤销证据不外推为本批Agent做了回滚。
- 旧首次stop输入w-ops-normal-stop-001仍submitted，E2E-001未修复；本次新入口3输入均completed，最终管理stop没有模型stop输入，不说明旧bug消失。所有原始失败/未知保留，不手改或重放。
- 产品/SBP源码未改，生产UE/CI未执行，未提交/发布。固定安装与A–J/R/M旧证据保留，主仓仅Lead/user文档变更。当前工作结束，不监控、不重连、不发消息或模型、不扩测。下一条安全操作仅Lead只读审阅最终证据并更新其拥有的验收登记。

## W 业务完成后的收尾判断（历史，既有授权已明确并执行）

- 用户已明确确认“已看到恢复成功报告”，Lead未CUA操作/代发。累计实际native started/completed各6，企微出站2条均sent/errcode0且人类可见（失败通知、恢复通知）。真实授权入站、模型限定修复、模拟实际重跑、自动恢复复核和群报告均有副作用证据。
- 实际wecom事件87061719af64e13b06b1e5b7d3582ba5，平台入队时间23:58:56.623375北京时间，输入ie51d0f4ecb591fa255e7516481d0e587c79c2286对应turn01a111f0-836b-7583-94a6-0417bfdeb80d。恢复输入iab5c77e7fb3fb7c9e62dfd3868331c542f65e16c在23:59:06.618233入队，对应turn01a111f0-da6b-74e1-a00d-a64ff35ee7a2。两者账本现completed。
- 23:51截图早于新ready23:55:42；实际收到事件未保留provider原发送时间，不能确定是否同一条或离线回放。旧“企微故障”推断撤回，保留用户先前确认/更正和各时点观察。
- W16-business-chain-proof.json回读实际两行产物，hash2ff4deccf19bcc95d68f8f048148578841e539999a3c73aa0535ddf3ee276c7b，tile-B限定修复；原失败归档保留，driver agent-events共2条（失败、恢复各1），重复观察/续读没有额外失败输入。
- 收尾未完成：第6轮按任务尝试asset.read .aw-local发送账本，公共relpath禁止本地运行状态，工具明确拒绝。Agent没有编造回执或ownerstop。控制者先前判断可在同轮这样读取有误（W15明确记录），不是产品入站故障。第6轮已结束，不能补做同轮。
- 已通过正常bridge stop关闭两路新触发，成功发送实际已确认，无队列丢失/重发；beta Binding b0ab72f3040a545a8a82320d01000f82c仍active/current，Runner尚在。未强行释放、未追加第7轮。已请求确认：保持6轮由正式管理入口创建检查点并正常stop（明确管理端操作），或另授权1个仅模型收尾轮；最新范围仍不追加模型，待明确管理端收尾许可。
- 下一步只完成已获明确许可的正常收尾，不新增业务、群消息、连接、测试或模型。旧alpha保持不动；本次6轮业务不是Desktop/跨Harness/生产SBP证明。旧首次stop输入submitted保留，不宣称修复E2E-001；当前恢复输入completed不等于stop输入bug修复。

## W 恢复事实与收尾尝试（历史）

- 正式wecom真实入站87061719af64e13b06b1e5b7d3582ba5，正文“@E2E_TEST_BOT 同意修复模拟tile-B”，目标为同一授权群。由正常Bridge自动进入新Binding的第5轮；controller未代造/重放。用户截图23:51早于新ready23:55:42，但平台随后实际收到授权；缺少provider原发送时间，不能确定这条入站是否对应旧截图或新发送，更不能认定故障。
- 真实Agent补读日志（第4轮）并在实际入站后创建虚构tile-B（第5轮），恢复观察器实际重跑成功，唯一新恢复事实自动进入第6轮。实际navigation-export.txt回读为tile A/tile B两行，不是口头成功。
- 第6轮Agent实际复核并发送w-ops-success-report-001；运行器真实记录sent/errcode0，23:59:50 provider接受。累计出站2/20（失败通知1、恢复通知1），旧通知未重发。恢复通知人类可见尚待Lead确认。
- 当前累计原生started6、completed5（第6轮正在checkpoint/stop），不得再开轮或让用户追加群消息。Agent须实际读发送记录确认sent后，关新触发、checkpoint和ownerstop；正在等待正式收口证据，不提前宣称进程退出。

## W 恢复准备与有界等待（历史）

- 用户新更正：此前误解回复要求，并未如先前确认那样发出授权；准备在连接恢复后真正回复。W10-human-correction.json以接收时间保留更正，旧W09确认不删除。先前零入站不能据此认定企微故障；历史“入站阻塞”仅是当时观察。
- 已确认上批beta released/runner已退出，未强行释放。正常start创建唯一新Binding b0ab72f3040a545a8a82320d01000f82c / session01a111ed-5f8a-74e2-b036-ae4481467f53，继承真实checkpoint c04877e9d873f4943a96b75ecf1975a61。现累计started4、completed3，剩余最多2轮实际业务（本次初始化算第4轮）；全部6轮上限不变，不重跑失败或已送达通知。
- 正式wecom ready且generation与配置匹配，PID271784；同一精确群白名单，不新识别目标。恢复观察器PID262696，仅观察现有场景的新恢复，不重放旧Binding失败ID，不改产品/历史事件。默认夹具启动会重放旧事件并与旧Binding冲突，所以本次环境使用observe_recovery.py；该限制如实记录。
- 新boot任务给出正确scenario/sbp-ops/archive/sim-build-1/job.log和job_summary.json，要求初始化补齐日志证据、写notes/ops-resume.md并等待；用户这次更正不是正式渠道授权，controller不代造授权或修复。
- 已在本聊天提示Lead：让用户在E2E_TEST_GROUP群实际选中@E2E_TEST_BOT，发送一次“同意修复模拟tile-B”。最长等待到北京时间2026-10-07 00:05:42；跨日时间已明确。CUA目前native不可用，本执行未用API/脚本冒充用户群消息；若未来由授权CUA代发须单独记录真实操作者。
- 剩余3轮路径：恢复初始化、实际授权入站/修复、恢复事件复核+发送确认+checkpoint/ownerstop。最后一轮须asset.read真实send记录为sent/errcode0再停新触发并stop，不拿queued冒充完成或为预算改产品。状态未知保留现场；不得自动升档/付费重跑。

## W 首次收尾（历史，用户后续更正并授权恢复）

- 本批真实原生started/completed各3：初始化、sim-build自动失败调查、正常收尾。gpt-6-luna/low；6轮上限未突破，没有自动付费重跑/升档。企微出站1/20，真实SDK errcode0，用户截图确认23:30:09的主动通知实际可见。
- 用户确认在E2E_TEST_GROUP群从成员列表实际选中@E2E_TEST_BOT发送授权。平台至23:41没有任何正式wecom入站文件；不能归因于未@。白名单与识别chatid一致，识别与正式Bridge均订阅message.text，但没有收到/拒绝帧证据，原因未知。W07只读边界、W09人类确认保留。
- 首轮真实Agent读operation/scenario、写调查记录并亲自bridge.send；日志与Job Summary路径漏了scenario/sbp-ops前缀，实际读取失败，不能追认完整调查通过。真实渠道授权入站、补读、修复、恢复自动复核未通过；tile-B仍不存在，没有sim-build-2，没有实际恢复产物。
- 相同失败再次观察无新事件/新模型轮次。已完成的S驱动失败/恢复/撤销检查仅PASS_DRIVER_ONLY，不升级为W真实闭环。
- 23:41关闭sim-build/wecom新触发，已知唯一发送此前已sent。真实Agent保存notes/ops-result.md、创建checkpoint c04877e9d873f4943a96b75ecf1975a61（revision862210bae2f9e9b45e83ccb87376864ce15d1ba0）并ownerstop；工具先awaiting_native_idle，随后运行器实际观察idle并释放。
- 最终beta current=null，Binding bf06398581b804f2c9da2134133b8d006 已released，handoff hf06398581b804f2c9da2134133b8d006，runner_alive=false，Watch关闭。两个Bridge配置enabled=false；W09进程审计确认本轮识别器、正式WeCom全部子进程、模拟Bridge、Runner已退出，本轮没有残留连接或后台。
- 回读notes/ops-result.md与真实检查点成功。初始化和sim-build入站账本completed；正常stop输入w-ops-normal-stop-001仍submitted，但对应原生turncompleted和释放副作用真实存在。旧E2E-001现象保留，不手改、不重放、不修代码。
- 最终证据：evidence/W09-final-facts.json、W09-process-exit-confirmed.json、W09-beta-final-state.json、W09b-checkpoint-readback.json、W09-human-confirmations.json；预算W-model-budget.json。产品/SBP源码未改，生产UE/CI未运行，未提交/发布，alpha旧HY资格未触碰。
- A–J/R/M旧证据保留；普通Desktop/TTY、跨Harness、生产能力保持原未验证边界。当前本批结束，不监控、重连、重发或自动继续。下一条安全操作仅由Lead只读审阅入站阻塞并另行明确后续授权；剩余3轮不是自动续跑安排。

## W 群内等待（历史）

- Lead已核对群内识别事件 d235456df8b636fe20216c525edfcb04，并确认用户说已在E2E_TEST_GROUP群发送。识别连接已正常关闭、两进程退出后，正式wecom Bridge只配置该精确chatid。
- 原Codex路径因本机版本变动已失效，W02配置失败时模型0；发现当前真实入口5ea220ae823df3d7并正常核对官方ChatGPT登录后配置。保持固定AW wheel和Luna/low，未登录/改认证/修产品。W02b保留结果。
- 新真实beta Binding bf06398581b804f2c9da2134133b8d006，session01a111d4-ae8d-7db0-aeb0-f936367da4e1；当前原生started/completed各2（初始化、sim-build自动失败调查）。wecom与sim-build都ready，alpha不动。W04快照与W-model-budget记录。
- Agent真实保存notes/ops-ready.md、ops-investigation.md，并用自己Binding发送w-ops-failure-report-001；wecom receipt errcode0，外发1/20（仅provider接受，未有人类可见确认）。controller没有代发调查或授权、未修输入。
- 证据缺口：本轮Agent读取operation/scenario，但archive日志/summary路径缺少scenario/sbp-ops前缀，实际读失败；不记完整根因调查PASS。已在当前聊天请Lead传达修复回复附正确日志路径，在同一真实用户入站轮补读，再授权修复，避免加付费重跑。原失败工具记录原样保留。
- 建议用户群内@Bot回复：同意修复模拟tile-B。修复前先读取 scenario/sbp-ops/archive/sim-build-1/job.log 和 scenario/sbp-ops/archive/sim-build-1/job_summary.json，核对根因后再修复。
- W05再次观察同一失败无新事件（仍1），tile-B仍不存在；尚未证明Agent补读/修复/成功复核。已用2/6轮，保留人类入站、恢复、正常收尾余量；不得controller冒充用户。等待窗口最多10分钟，目标23:41前若无人类回复则停止新渠道触发并走正常收尾，不无限常驻、不自动重连/重发。
- 下一步仅等待真实企微入站；随后核对实际文件与自动恢复轮，已知发送完成后关新触发并正常checkpoint/ownerstop。仍未验证Desktop、跨Harness、生产SBP/UE/CI。

## W 群识别准备（历史）

- 最新人工明确“可以，那开始吧”，已授权此前真实 Agent/企微/隔离模拟构建 E2E。本批最多新增6轮 Luna/low、最多20条企微出站；第5轮前留正常收尾余量，零自动重跑/升档。原填写单 execution_authorized=false 保留为旧时事实，不篡改。
- 企微依赖已在 ROOT/app 隔离安装：wecom-aibot-python-sdk1.0.2；产品 wheel/源码未修改。薄启动器仅本机从 DPAPI 取Bot凭据，传给企微子进程，未输出值/写公开文件/传入Codex Runner环境；没有使用Webhook。
- 只监听识别连接 authenticated，证据 `evidence/W01-identification-status.json`。启动器PID268268、识别子进程PID259804；最大重连0、外发0、模型0。识别短语 SBP验收识别-松鼠7462，只保存匹配群事件的chatid/目标类型/事件ID/时间，其他正文丢弃。
- 窗口截止2026-10-06 23:33:22北京时间，最长600秒；超时关闭，不自动重连。停止文件 `scenarios/sbp-ops/identify.stop` 可请求正常关闭。当前等待Lead确认用户已在E2E_TEST_GROUP群@Bot发送短语并核对匹配事件；未启用正式AW白名单/Bridge，不并行第二个Bot连接。
- 下一步：得到人类结果后正常关闭识别连接，确认退出，再将精确chatid写入正式Bridge白名单并继续真实旅程。不得在目标未知时启动模型或放宽正式入站范围；旧alpha HY资格不动。

## S 场景准备收口（历史；执行方向以 CURRENT 为准）

- 当前授权仅准备隔离模拟环境。新增模型调用/预留0、企微连接/外发0、后台服务0；未运行生产 SBP/UE/CI、未修改产品源码/配置/资格，不监控、自动续跑或跨会话发送报告。
- 已只读确认源工作副本属于 ft_sbp_test_3，根 svn info r1067288；S03 保存来源结果。不等于远端最新或全部文件同 revision，未更新 SVN、未读生产归档、未写该仓/全局配置。
- 交付 `scenarios/sbp-ops/README.md`、`scenario.py`。最终 S02 与 `runs/driver-check-final/check-result.json` 为 PASS_DRIVER_ONLY：真实缺失输入失败、具体日志、失败/恢复各1个事件、重复观察抑制2次、实际生成产物、修复已撤销、失败和成功历史保留。初次 S01 保留；补充修复记录逻辑后仅重跑同一驱动检查。
- custom Bridge 使用既有 stdin/stdout JSONL 已准备，未配置到实例或启动真实 Runner；simulation-outbox 回执 external_delivery=false。驱动去重不代表 Agent 调查去重、真实 AW 投递或企微收发已验证。A–J/R/M 证据不重跑、不升级为完整 E2E/Desktop/生产业务验收。
- 后续建议最多新增6轮 gpt-6-luna/low：初始化、事实触发失败调查、明确授权修复、事实触发成功收口、正常保存检查点/停止各1轮，另留1轮。本轮未执行/预留，不重试或升档。未来场景仅放在 released 测试实例的新目录，alpha旧HY资格保持不动。
- 企微专用长连接 Bot、E2E_TEST_GROUP群仅用户、最多20条外发为既有边界。误填 Webhook 已安全保存，不是 chatid；精确 chatid 尚缺。未读取 private 凭据/连接/发送。由 Lead 安排最小目标确认步骤并明确真实执行派发。
- 下一条安全操作：Lead只读审阅场景和最终驱动结果，再明确真实模型/渠道派发。当前没有本执行会话正在运行的任务。旧资格、账本、表单/停止状态沿用下方 M/N 证据，本轮未刷新，不声称最新实时进程状态。

## 上一检查点（历史，N批收口；后续等待方向以 CURRENT 为准）

- 用户最新目标已改为企业微信/SBP OpsAgent，立即停止N/Codex补测安排。N只完成只读预检和方案；新增模型调用0、预算预留0、原生session0、Fork/Work0、Watch/transfer0、服务0。原批准N最多新增6轮全部未使用，不能自行转成企微发送/业务授权。
- N-CODEX-PLAN.md保留明确标注未执行；N01-codex-login-status确认现有ChatGPT登录，N01-beta-state确认beta current=null/released、runner_alive=false、Watch关闭。证据N01*和N-model-budget.json。
- 固定软件SHA1258b622c474beb73f13234c0f00672d8d5b5bbb/wheel0.1.0a1、唯一正式根${E2E_ROOT}。当前源码用户docs/implementation.md的E2E-001/E2E-002登记与未跟踪规程保留；本执行会话未修改源码/文档、未修bug、未提交/发布。
- R/M既有真实读写/检查点、两实例通信自身ACK、同Codex接手保留，不重复。历史累计请求/预算预留7：2 Sol、4 Luna完成、1 HY认证失败；Codex原生started/completed各6，HYSDK报告usage/cost0。N新增为0，历史不重计。
- alpha旧HY Binding b75712931632c4f8da3a948ca9cb395f6仍active/current，runtime monitor_stopped、entry_still_owned=true、runner_alive=false，session01a10d5f-f98b-7300-a6f0-b73b738b5ed2；禁止改资格/删锁/重放或切换配置。旧submitted不一致及真实输入状态原样保留。
- beta无资格且已released；M运行器已停止、工作台36108已关闭、schedule禁用。独立表单服务220864及启动器191596此前保留，不是模型Runner；本轮不读private认证、不误停。未新增其他后台。
- 所有本轮测试文件/消息/检查点/报告与隔离CodeBuddy SDK保留。普通TTY/Desktop、N Watch自动推送/自动transfer、其他故障/远端能力未验证，不将方案当完成。
- 下一条安全操作：等待Lead只读调查GitHub SBP OpsAgent设计并明确派发企微测试。本会话不自行访问/发送企微消息、不启动SBP业务、不再开Codex测试、不新建thread/自动化或跨会话回报。当前没有本会话正在执行的任务。
