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

# AgentWorkspace 本地 E2E 报告

2026-10-07（Asia/Shanghai）。**W批限定模拟业务的真实AW/Luna/企微链路通过：累计6个原生轮次、2条企微出站，均有人类可见确认；真实授权后限定修复、模拟重跑、自动恢复复核已完成。验收编排错误导致本轮模型自停未完成，最终由管理端通过公开入口正常收尾，不能当作模型自身stop通过。beta已released，全部本轮Runner/Bridge/企微子进程退出，当前无继续执行或监控。**

以下R/M/N及W各阶段记录保留为历史；当前结果以文末“W最终收口”及CHECKPOINT.md为准。A–J既有同基线证据无需重跑，alpha旧HY资格未触碰。

固定提交 `1258b622c474beb73f13234c0f00672d8d5b5bbb`，安装版本 `0.1.0a1`。唯一正式根 `${E2E_ROOT}`。沿用已验证 wheel 与隔离 app，不重跑 A 组、不改生产源码。完整 A 组历史与原始证据见 [A-STAGE-HISTORY.md](A-STAGE-HISTORY.md)；其中当时的模型闸门与下一步建议已经由本报告当前状态取代。

## 本轮结果

| 范围 | 实际结果 | 判定与证据 |
| --- | --- | --- |
| Workspace/实例 | 正常工作台创建 e2e-local，生成 steward/maintainer/sentinel；正常产品命令创建 alpha/beta 两个明确测试实例，无 Work 要求 | PASS_REAL；R05 UI、R06 创建/配置证据 |
| Harness/认证 | 复用 Codex App 自带真实 exe 0.160.0；login status 确认现有官方 ChatGPT 登录；原生目录确认 gpt-6.1-sol/low | PASS_REAL；R01–R03、R06。未改全局模型或登录配置 |
| 第一轮 | 实际读取随机标记，写 notes/result.md、回读一致，创建真实 checkpoint，收到原生完成与回复 | PASS_REAL；[R09](evidence/R09-initial-result.json)、[最终事件](evidence/R13-final-runtime.json) |
| 第二轮同会话 | agent.input 进入同一原生 thread，回读保存标记、创建第二检查点，调用 agent.stop；原生 turn/completed 与真实回复已收到 | PASS_REAL（业务执行）；R10、R13。输入账本收口限制单列如下 |
| owner stop | 工具先返回 awaiting_native_idle，之后真实 Binding 释放，current=null，runner_alive=false；未创建后继 | PASS_REAL；[最终状态](evidence/R12-alpha-final-show.json)、R13、[界面](evidence/R13-final-dom.txt) |
| 定时健康检查 | 30 秒正常 schedule，notify=false；02:23:04 与 02:23:36 两次 last_run 不同，均 healthy、issues=[]、覆盖五实例；之后正常禁用 | PASS_REAL（无异常路径）；[第一周期](evidence/R11-health-cycle-one.json)、[第二周期](evidence/R12-health-cycle-two.json)、R12-health-disable。未启动管家模型 |
| UI/清理 | 刷新工作台可见 released 历史、当前未绑定；资料列出 result 与两检查点。关闭标签页和本轮工作台进程树，36108 无监听 | PASS_REAL（清理）；R13 DOM/JPG、R04-workbench-stop、[R14](evidence/R14-cleanup.json)。服务定向终止不算优雅退出 |
| 通信/ACK/跨 Harness | 两輪预算用于最小正常闭环，没有发送 Message/ACK，没有启动 beta 或接手者 | NOT_RUN；下一批需追加预算 |
| 普通原生 TTY/Desktop | 本轮操作环境只支持浏览器控制；本次真实模型属于产品管理的 Codex 原生 app-server 会话 | BLOCKED（本轮操作能力）；不冒充 Desktop/真实终端验证 |
| 其他边界、故障矩阵、Work/Fork、远端 Git、企微 | 最新范围收缩后未扩测 | NOT_RUN |

## 真实副作用与状态问题

原生 thread：`01a10d4c-1d08-78d2-b234-4a3832669356`。两轮 turn：`01a10d4c-3982-7711-8f46-067827ec9089`、`01a10d4e-19b4-7032-8c1f-a54d97b10a40`，均有 completed；耗时约 54 秒与 30 秒。Binding `bdd3cb0600def4dc6874145a6f5db8385` 已释放，handoff `hdd3cb0600def4dc6874145a6f5db8385` 仅代表释放后的持久交接记录，不代表接手验证通过。

真实文件 notes/result.md 为 55 bytes，UTF-8 无替代字符，SHA256 `207c643a6d338891f16460ec3ef0f38b41f81dddd107386bd5928ba6e830d2a3`；标记 `AW-E2E-d723faeb0af548dab83cadb7b8327110`。检查点 `c1734abfa27974d11acf36f53d27c7147`、`caf0b25b7b708492d8765c94c21b1ddd3` 均有实际文件与 Git revision。控制台一度出现乱码，是父进程输出编码显示问题，实际文件检查不支持产品内容损坏结论。

**需后续定位的状态不一致：** 第二条输入 `e2e-alpha-second-stop-001` 最终账本仍为 submitted，保存的响应仍为 inProgress；同一原生 turn 的 completed、真实回读/检查点/停止副作用已经确认，运行器随后停止。不能把平台输入账本写成 completed，也不能将它自动重放。本轮只保留证据，未修源码，根因尚未定位。

第一轮模型曾试用不存在的 binding.show/help/agent.binding，并给 asset.read 多传 binding，工具明确拒绝；模型随后通过实际资源和正确命令完成任务。零自动重试指控制器没有追加模型 turn 或重放请求，不能理解为模型内部没有错误工具尝试。原始事件保留这些失败，未包装成全程无错误。

## R 组收口时的现场与当时后续建议（历史）

模型预算 [model-budget.json](evidence/model-budget.json) 为 2/2；不再输入、重试、交接启动或调用管家。正式根保留全部资产与记录。测试工作台、模型运行器均已停止，schedule 已禁用。此前独立收集表单服务 PID220864 及其 pythonw 启动器 PID191596 保留；它们不是模型运行器，本轮未代用户填写/读取凭据。R14 中唯一正式 app 路径进程是该表单启动器，因此不宣称整个正式根零进程。

源码 HEAD 与固定提交一致，status 仅用户新增 `docs/AgentWorkspace-local-E2E-prompt.md` 未跟踪；本轮没有暂存、提交或发布。旧准备根与隔离安装原位保留。此次复用官方认证进行真实模型请求，未记录认证内容、未向自建网关发送令牌；实际金额未观测。

下一批最小通信+接手验收预估需要额外 4–6 轮真实模型预算（不是成功保证）：alpha/beta 显式测试消息、实际投递/读取/ACK、保存检查点并交出、真实后继读取标记与未决状态，最后停止。跨 Harness 还需先确认另一 Harness 的可靠原生入口、现有登录与所需 SDK；当前 Claude 认证未确认，CodeBuddy npm CLI 的 help 报缺少 dist/codebuddy。不能因 Desktop 已安装就断言这些路径可用。若仅验证同 Codex 接手，必须与跨 Harness 分开标注。不新增故障矩阵或重跑已通过的 A 组。

![停止后的实际工作台](evidence/R13-final.jpg.omitted.md)

## M 组新增事实、缺陷与阻塞（当前最终状态）

本批未新增 Sol 调用。用户改选低档模型后，正常产品配置改为原生目录确认的 `gpt-6-luna/low`；先前两轮 Sol/low 原样保留。目录没有价格字段，不宣称已证明所有模型中绝对最便宜。Lead 本批执行上限为新增 6 轮、累计 8 轮，不把这个数写成用户原话。本批实际 4 个 Luna turn + 1 个 HY 正常请求，没有控制器重试、自动 Watch turn、升档或重复接手测试。核对完整原生记录：累计 6 个 Codex turn 的 started/completed 各 6 个；SDK HY 只有 1 个本地提交，认证失败、报告 input/output=0 与 cost=0。SDK 内部 num_turns 字段为 2，不能当成两个成功模型轮次。预算保守预留累计 7/8，停止新增请求；未观测 Codex 实际金额。

| 新结果 | 真实证据与范围 |
| --- | --- |
| 一次通信往返 PASS_REAL | alpha 在新原生 thread `01a10d58-3ea5-7753-9956-10acbe8f175b` 发 `m-e2e-luna-request-001`；beta 在真实 thread `01a10d59-9416-7631-b530-a9387f8003f8` 用自己的 Binding `b99b412cfc3794314a231f5090250ac1f` receive/ACK，并仅回复 `m-e2e-luna-reply-001`，引用原 ID。alpha 在同一自己的原生 thread、Binding `b89818d3a91bf4545b646a68571aaf6b8` receive 回复并发布 ACK。两 ACK 均 published，receipt 的 receiver/binding 对应实际接收者；控制者只 show，没有代 ACK。beta 的接收发生在明确启动任务内，未将主动 receive 冒充 Watch 自动推送验证。 |
| 同 Codex 接手 PASS_REAL | 复用 M04 的正常 start：R 组旧入口先已释放，新 Binding 与原生 thread 均不同且唯一；平台在真实 boot 输入中传入旧检查点 `caf0b25b7b708492d8765c94c21b1ddd3` 及其内容；新模型实际回读旧 notes/result.md、核对同一标记，再保存 `c5f7451ea85324705a183fd4bae1e2358`。这证明旧资产/检查点进入新入口并继续任务，不声称模型另行调用了 checkpoint.show。没有为了重复得到一条接手记录再开 Luna 会话。 |
| Luna 正常停止 PASS_REAL | beta 首轮猜错多次 checkpoint/stop 操作，通信成功但没有停止；增加一轮仅补正常收口，没有重发消息。beta 成功保存 `ca852aad8af3641858e16f345eaffc35c`、owner stop 后 released。alpha 收到回复后保存 notes/communication.md 与 `c6dd384ea79af4f528f4d92f9b98c101e`、owner stop 后 released。具体工具失败保留为模型操作现象，不自动归咎产品或升档刷通过。 |
| HY 跨 Harness 接手 BLOCKED | WorkBuddy 自带 JS CLI 的 help 实测成功，列出 `hy3-preview-ioa`、`hunyuan-2.0-thinking-ioa`、`hunyuan-2.0-instruct-ioa`；没有因为旧 npm 包缺 dist 就泛化全部入口不可用。只在新的 `codebuddy-app` 隔离安装固定 `codebuddy-agent-sdk==0.3.267`。该 SDK 直接连接 WorkBuddy JS 入口报 WinError193，需要适配才能用，不改客户端/源码。随后改用 SDK 官方自带真实 Windows CLI，经正常产品配置选择 WorkBuddy 已列出的 `hunyuan-2.0-instruct-ioa`，不设 fallback/custom service/API key；真实新 session `01a10d5f-f98b-7300-a6f0-b73b738b5ed2` 产生 `Authentication required. Please use /login command to sign in to your account`，ResultMessage 为 error_during_execution。该请求未调用业务工具，未读检查点/笔记，不算跨端接手通过；只说明这个原生入口当前要求登录，不能泛化 Desktop 未登录或 HY 服务不支持。未新登录、读取/复制令牌或改服务。 |

最终 [M18-final-evidence.json](evidence/M18-final-evidence.json) 集中保存真实消息/ACK、资格、输入账本、文件哈希、原生 turn 与 SDK 失败；细节按 M01–M18 的原始命令/事件保留。先前 `e2e-alpha-second-stop-001` 的 submitted 不一致保留；本批 Luna stop 后的输入账本也保留实际状态，没有手改 completed/重放。notes/result.md 原标记与 hash 不变，新增 notes/communication.md、beta 的 notes/received.md、各检查点原位保留。

HY 失败后调用正常 `runtime.stop`，工具明确 `execution_right_released=false`；最终 alpha 的 HY Binding `b75712931632c4f8da3a948ca9cb395f6` 仍 active/current，runtime=monitor_stopped、entry_still_owned=true、runner_alive=false。这是保留现场，不是 owner stop 成功；没有强行清资格、假检查点/会话或切回 Codex 规避失败。beta current=null，Luna 两入口已正常释放。后续若要继续 HY，需先在这个原生入口完成真实登录并按产品实际恢复原资格；不能仅凭 Desktop 登录就重放启动或删锁接管。本轮不再自动继续。

[M19-cleanup.json](evidence/M19-cleanup.json) 确认三个本批运行器 PID 均已退出、36108 无监听，正式根仅保留独立表单启动器 PID191596，表单服务 PID220864 仍保留。没有新工作台服务、生产职责/源码修改、提交或发布；HEAD 仍固定基线，status 仅用户规程未跟踪。选中 SDK 安装及所有测试资产原位保留。普通 TTY/Desktop、Watch 自动推送、其他边界/故障/远端能力保持未测，不扩项。

## N 批准备与执行前收口

用户曾确认现有登录、`gpt-6-luna/low`、最多新增6轮；完成正常 Codex自动投递/transfer的具体 [N-CODEX-PLAN.md](N-CODEX-PLAN.md)，但用户随后明确优先企业微信与 GitHub SBP OpsAgent，因此在执行前停止本批。只读 `login status` 成功，beta仍 current=null/released/runner_alive=false/Watch关闭；alpha旧HY资格仍原样保留。没有新的模型/session、Fork身份、Work、Watch、transfer、配置变更或服务。模型新增实际调用和预留均0，6轮未使用；不能把这笔未使用预算自动转为企微发送或SBP业务授权。[预算收口](evidence/N-model-budget.json)、[预检](evidence/N01-baseline.json)。

已通过R/M证据不重跑；N方案仅保留准备记录，不记PASS_REAL。用户在源码 `docs/implementation.md` 登记E2E-001/E2E-002的改动保留，本执行会话没有改源码/修bug。下一条安全操作是等待Lead完成SBP OpsAgent设计只读调查并明确派发企微测试范围；当前不自主访问/发送企微或启动SBP业务，不继续N链路。仍保留的HY资格、submitted记录、表单和历史证据见M组最终状态。

## S 场景准备收口（最新；不是模型或渠道 E2E）

按最新派发，只读核对用户指定 SBP 工作副本，确认 URL 属于 ft_sbp_test_3，根 svn info r1067288；未更新 SVN、未读取生产归档、未执行 SBP/UE/CI。参考 Build Operation/Event、Stage/Job Summary 事实格式，创建独立虚构导航导出场景。来源记录见 [S03](evidence/S03-sbp-source-info.json)。这是本地工作副本证据，不是远端最新状态或整个工作副本同 revision 的证明。

交付 [场景说明](../scenarios/sbp-ops/README.md) 和 [标准库驱动](../scenarios/sbp-ops/scenario.py)。实际缺少 tile-B.txt 导致失败，日志可定位原因；重复观察同一失败不再生成调查事件；隔离补齐后重跑成功并生成真实虚构产物；核对 hash 后撤销修复文件，失败/成功历史均保留。最终 [S02 驱动记录](evidence/S02-final-driver-check.json) 与 [结果](../scenarios/sbp-ops/runs/driver-check-final/check-result.json) 为 PASS_DRIVER_ONLY。初次 S01 也保留，补充修复记录逻辑后仅重跑同一驱动检查，没有扩测。

新增模型调用0、外发0、企微连接0、产品源码/配置/资格改动0。custom Bridge 已准备但未接入实际 AW Runner；驱动去重不等于 Agent 调查去重已验证，模拟 sent 明确 external_delivery=false，不是企微送达。A–J/R/M 既有覆盖原样保留，不升级为完整 E2E/Desktop/生产业务验收。

README 提出后续最多新增6轮 Luna/low 的短闭环（初始化、自动失败调查、明确授权修复、自动恢复收口、正常停止各1轮，保留1轮），本轮未执行或预留。专用企微群和20条上限仍保留；误填 Webhook 不作为 chatid，精确 chatid 尚缺。未读取 private 凭据或接通渠道，后续由 Lead 明确派发。当前停止在准备阶段，不轮询、不自动续跑、不跨会话发送报告。

## W 真实旅程启动（最新：等待目标识别）

用户明确“可以，那开始吧”后，开始真实E2E授权范围；旧填写单待讨论状态原样保留。第一步仅建立专用Bot短时只监听识别连接，未启动模型或正式AW渠道。ROOT/app安装官方SDK1.0.2及其依赖，不改产品源码/wheel。凭据在本机薄启动器中从DPAPI读取，仅传给企微子进程，未暴露到报告、命令行或Codex Runner环境。

`W01-identification-status.json` 记录真实 authenticated；北京时间23:23:22起最长10分钟，截止23:33:22。仅匹配本轮识别短语的群文本，保存所需目标/事件/时间元数据，过滤其他正文。最大重连0、外发0、模型0。当前等待Lead带来人类发送确认；正式白名单仍未配置，不放开全部会话，不与正式Bridge并行连接。超时或失败正常关闭并保留最小证据，不盲目重连。随后再确认目标、正常关闭识别器并推进实际模型闭环，本批预算最多6轮和20条外发。

W01匹配群事件经Lead核对且用户确认后，识别连接正常关闭，两识别进程退出，正式Bridge仅允许这个chatid。启动前旧Codexexe已失效，W02配置失败但没有模型请求；W02b用本机当前入口5ea220ae823df3d7正常核对ChatGPT登录并配置，AW固定wheel未变。W03真实beta Binding/session及初始化完成，正式wecom ready后W04启用sim-build，其真实缺失输入失败自动生成唯一入站。

截至W04/W05：原生turnstarted/completed各2，Agent自行读operation/scenario、写调查记录、bridge.send w-ops-failure-report-001，真实企微errcode0，外发1，未修复输入。重复失败观察没有新增驱动事件；W05记录tile-B不存在。**未满足完整调查证据**：Agent读archive日志/summary时漏了scenario/sbp-ops前缀，真实工具返回不存在；调查笔记和回答如实记录了失败，不伪造读到日志。当前请Lead把用户真实修复授权回复附正确两条证据路径，在同一入站轮先补读再修复，不额外controller付费重跑/代授权。provider接受尚不等于用户看到消息，仍待人类反馈。

## W 最终结果（已收尾，完整闭环未通过）

用户截图经Lead核对，确认23:30:09的主动通知实际可见；用户同时确认已从群成员列表实际选中@E2E_TEST_BOT发送带正确证据路径的授权回复。[人类确认](evidence/W09-human-confirmations.json)保留，不能把阻塞归因于未@机器人。正式Bridge直至23:41未产生企微入站文件，因此没有修复或恢复Build。只读核对[W07](evidence/W07-readonly-inbound-boundary.json)确认精确白名单匹配、固定wecom源码未改、两个listener都订阅message.text；已有材料没有收到/拒绝帧元数据，不能定位到投递、消息类型、缺字段或过滤拒绝。不新连、重连、改日志/源码或要求盲目重发。

| 证据层 | 最终判定 |
| --- | --- |
| 隔离模拟驱动 | S检查实际失败、恢复、产物与可逆撤销PASS_DRIVER_ONLY；W实际执行只到缺失输入失败，不触碰生产。 |
| 真实AW/Agent自动触发 | sim-build事实自动产生唯一失败入站、同一真实会话读operation/scenario并写笔记、重复观察无额外事件/模型轮次。首轮日志路径读错，完整调查未通过。 |
| 真实企微主动通知 | Agent自身发送，SDK errcode0，用户截图确认实际可见：PASS_REAL_DELIVERY，出站1条。simulation-outbox没有参与。 |
| 真实用户授权入站/修复闭环 | 用户确认实际@并发出；平台未观测入站，BLOCKED/NOT_PASSED。无补读日志、无tile-B修复、无sim-build-2或恢复汇报。 |
| 正常停止 | 关闭两个Bridge新触发、唯一发送已完成后，Agent真实保存结果/检查点并ownerstop；原生idle后Binding释放、Runner/本轮WeCom全部子进程/模拟Bridge退出：PASS_REAL_STOP。 |

本批原生started/completed各3（初始化、自动失败调查、正常停止），使用gpt-6-luna/low，低于6轮；企微1/20条，没有自动付费重跑、升档或控制器代调查/代发/代授权/代修复。[最终事实](evidence/W09-final-facts.json)、[预算](evidence/W-model-budget.json)、[退出审计](evidence/W09-process-exit-confirmed.json)集中记录。beta真实session01a111d4-ae8d-7db0-aeb0-f936367da4e1，Binding bf06398581b804f2c9da2134133b8d006已released/current=null/runner_alive=false；检查点c04877e9d873f4943a96b75ecf1975a61、revision862210bae2f9e9b45e83ccb87376864ce15d1ba0已正常回读。

正常stop输入w-ops-normal-stop-001账本仍submitted，尽管对应原生completed和实际释放已确认；初始化和失败自动入站账本completed。保留已有E2E-001现象，不手改、不重放。alpha旧HY资格未触碰。产品/SBP源码未改、未运行生产UE/CI、未提交/发布；既有A–J/R/M证据保留，Desktop/TTY、跨Harness和生产能力不能由本批外推。当前结束，无残留本轮服务/连接，不自动消费剩余3轮继续测试。

## W 用户更正后的正常恢复（最新，执行中）

用户随后明确纠正：之前误解了实际回复要求，准备连接恢复后真正回复。以[带时间更正](evidence/W10-human-correction.json)覆盖“已发授权”的当前解释，保留W09历史确认及当时零入站事实；不能因此判定企微故障或未@。用户授权继续剩余最多3轮。上批已正常退出，beta通过正常start从真实检查点接手为新Binding/session；W10保持原场景、不重跑失败、不重发已可见的首条通知，不触碰alpha资格。

既有模拟夹具默认启动会重放旧失败事件，而平台input ID归旧Binding，正常新入口不能重放这个旧ID。本次只在环境增加receive-only恢复观察器observe_recovery.py：复用既有execute/observe逻辑，保留事实、ID和历史，只观察授权修复后的新恢复。没有改产品逻辑或把跨Binding重放宣称已支持。正式企微仍原精确白名单，ready/gen匹配；当前等待用户真正群内@Bot发“同意修复模拟tile-B”，截至2026-10-07 00:05:42北京时间。模型初始轮补读正确失败日志，用户更正本身不能当企微正式入站授权。

3轮安全路径依据现有合同：恢复初始化1、真实入站修复1、恢复复核1；最后一轮bridge.send后通过asset.read读取本地真实发送账本，确认sent/errcode0，再关闭两个Bridge新触发、检查点和ownerstop。queued不是完成，未知结果不重发或伪造收尾。真实桌面CUA目前native disabled，本执行未API代发；如以后授权CUA实际代操作须明确标注操作者。

随后正式wecom实际收到事件87061719af64e13b06b1e5b7d3582ba5，正文“@E2E_TEST_BOT 同意修复模拟tile-B”，唯一授权群，正常Bridge将其自动入队到新Binding第5轮。用户提供的23:51截图确实早于新ready23:55:42，但已有真实入站；[W12时间关系及现场](evidence/W12-human-send-before-ready.json)记录当时已启动第6轮、tile-B已存在，不能继续当零入站或要求重发。正式记录未保留provider原发送时间，与旧截图对应关系未知。操作来源为用户手工群消息证据，Lead未CUA代操作，controller没有代造授权。

[W13](evidence/W13-real-repair-recovery.json)记录第4轮真实补读正确日志，第5轮真实授权后仅创建虚构输入，第6轮由唯一恢复事件自动触发实际产物复核。navigation-export.txt实际为tile A/tile B两行；sim-build-1原失败归档保留，sim-build-2真实模拟重跑成功。Agent自身w-ops-success-report-001已sent/errcode0，累计企微出站2条；恢复通知目前只证明provider接受，仍待人类可见确认。第6轮正在正常收尾，不追加模型或群输入。

## W 恢复业务结果与收尾约束（最新）

用户随后明确“已看到恢复成功报告”，两条群通知均有用户可见确认。真实wecom入站event87061719af64e13b06b1e5b7d3582ba5在23:58:56.623375平台入队，对应正常输入ie51d0f4ecb591fa255e7516481d0e587c79c2286、turn01a111f0-836b-7583-94a6-0417bfdeb80d；真实恢复事实23:59:06.618233入队，对应iab5c77e7fb3fb7c9e62dfd3868331c542f65e16c、turn01a111f0-da6b-74e1-a00d-a64ff35ee7a2，现均completed。截图23:51早于ready23:55:42，但实际事件无provider原发送时间，不能推断二者同一或上游离线回放。Lead未CUA代发，controller未造入站。[W16业务证明](evidence/W16-business-chain-proof.json)保存实际事件、时间、输入/turn、产物hash和人类确认。

累计6个native turn started/completed各6，出站2/20，真实限定模拟业务链通过：第一次调查日志路径错误在恢复初始化补读补齐；实际群授权后Agent只写虚构tile-B，驱动真实复验成功，恢复事实自动唤醒同一新会话，Agent复核产物并亲自群汇报。失败/恢复两条事件保留，重复失败/续读没有新失败输入，源仓/生产未触碰。先前零入站不能判定故障，用户更正与历史判断原样保留。

**当前正常收尾未完成。** 第6轮尝试按控制者给的指引读取.aw-local投递账本，被公共relpath拒绝“Git internals and local runtime state are not publishable assets”；Agent如实记录未确认，没有ownerstop。前面对该工具可读性的合同判断有误，已记录[W15](evidence/W15-known-send-and-stop-block.json)，不把它归为企微入站故障。控制者真实回读确认成功发送sent/errcode0后，正常关闭两路Bridge新触发；本轮beta资格仍active、Runner尚未退出，不能宣称完整停止或伪造第6轮内stop。请求明确保持6轮由正式管理端checkpoint/stop收尾，或新授权1个仅模型收尾轮；当前遵守不追加模型。旧E2E-001首次stop输入submitted保留，现恢复输入completed不代表该stop账本问题已修复。

## W 最终收口（2026-10-07，当前结果）

真实AW/Luna/企微在明确隔离模拟业务上的链路已通过：失败事实自动入站、模型调查与主动群通知、用户真实授权入站、限定创建虚构tile-B、驱动实际重跑、恢复事实自动唤醒、模型复核实际产物并主动群汇报。初次日志路径读错已在恢复初始化补齐；此前入站故障结论已撤回，用户更正与23:51截图/23:55:42 ready/23:58:56实际接收的时间边界保留，不推断离线回放。两条通知均由用户确认可见，Lead未CUA代发：[首条截图](evidence/W09-first-report-visible.png.omitted.md)、[恢复截图](evidence/W12-recovery-report-visible.png.omitted.md)。

**验收编排错误导致本轮模型自停未完成，管理端正常收尾。** 错误来自控制者注入“asset.read读取受保护.aw-local发送账本”的任务，不是产品bug或模型违反合同。第6轮Agent如实停在回执不可读，没有自身stop。按既有明确正常清理授权，管理端确认真实发送/用户可见、关闭新触发后，通过公开checkpoint.create/agent.stop正常停止当前beta；没有第7轮、强制清资格、删锁或伪造完成。管理端正常停止的证明不能与模型自身stop混同；此前首次W收尾的模型stop证据仍原样保留。

管理端检查点 `c3a06c5a7b4ea4286bd358946c91bd271`、revision `5b74ff43ef0cba105edf710fe774b9c8686caab7` 已真实回读。[W17操作记录](evidence/W17-management-operation.json)明确操作者；[W18最终事实](evidence/W18-final-facts.json)、[最终状态](evidence/W18-beta-final-state.json)、[退出审计](evidence/W18-process-exit-confirmed.json)确认Binding b0ab72f3040a545a8a82320d01000f82c released/current=null，handoff h0ab72f3040a545a8a82320d01000f82c，runner_alive=false，两路Bridge disabled，本轮企微全部子进程/模拟观察器/Runner退出。

本批累计native started/completed各6、企微出站2/20，真实授权事件1、失败/恢复事件各1，自动事件全计入预算，无重发、升档或自动付费重跑。[W16](evidence/W16-business-chain-proof.json)记录实际输入/turn关联和产物hash `2ff4deccf19bcc95d68f8f048148578841e539999a3c73aa0535ddf3ee276c7b`。原失败归档、修复文件和成功产物保留；可逆撤销已由S驱动检查证明，本批真实Agent修复未撤销或另开回滚测试。续读观察器只消费新恢复，不重放旧Binding ID；通用夹具跨Binding回放未验证。

旧W首次stop输入w-ops-normal-stop-001仍submitted，E2E-001未修复/未手改/未重放；新恢复入口3个输入均completed，本次最终管理stop不产生模型stop输入，不能据此认定E2E-001修复。保留首次模型工具参数错误、路径错误、受保护回执读取失败，不能写成无错误通关。产品/SBP源码未改、生产UE/CI未运行、未提交/发布；源仓仅Lead/user文档变更保留。A–J/R/M历史证据复用，Desktop/TTY、跨Harness、生产能力不由本批外推。当前结束，不监控、不重新连接或发送、不继续测试。

用户对先前异步问题的直接回答“允许额外1轮，仅让模型自身正常收尾”随后到达；此时管理端已按明确既有指示完成公开正常stop、原入口已释放并退出。[W19](evidence/W19-late-extra-stop-authorization.json)保留授权及到达时点，未使用。另开新入口不能追补原第6轮自停证据，未为补证制造新入口或消耗第7轮，实际计数与上述证明边界不变。
