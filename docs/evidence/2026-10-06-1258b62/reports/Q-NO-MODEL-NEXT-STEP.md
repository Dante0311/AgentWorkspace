# 下一段建议：Fork与最小Work，随后第二独立安装复用

2026-10-07，Q1→Q2已按Lead核对顺序执行完成，新增模型/外发/服务均0。以下计划作为原安排保留，当前实际结果见文末。P已正常收尾且用户确认本次回复可见；P17保存直接确认，P18为含可见证据的最终事实。原P15定时快照保留不改。没有新增模型、企微或服务。

沿用P覆盖表，不建立另一份全新矩阵。建议先完成Q1，再独立收口Q2；两项都仅用真实公开管理CLI和本地Git，不调用模型、不启动运行器、不连接企微、不触碰alpha旧HY资格。

## Q1：从已保存检查点Fork，管理端最小Work正常生命周期

已读app.fork、work_create/update/deliver、公开CLI参数与随包fork使用说明。R/M/W/P已证明真实资产、检查点、正常接手与停止；不再重复创建原实例检查点。

1. 只读核对beta现已released、来源P检查点`c3788071b0e70473aa054a218b12688eb`和revision`36da4bc44cc714f5c442925d57814f3c46af60b3`；确认新ID尚未占用。
2. 单次公开`agent fork e2e-beta --checkpoint <上述ID> --name '隔离Fork合同验收' --new-id e2e-q-fork`，默认新实例目录仍在本隔离home。保留固定来源点，不从当前未保存目录临时复制。未确定操作结果时先查看既有身份，不能盲目重试。
3. 公开agent.show、asset.read/list核对新身份、forked_from、current=null、has_run=false、无session/执行权、来源材料与产物hash。用本地Git只读核对新实例分支父提交为指定checkpoint revision、完整保存树除`.aw/identity.json`外一致，新identity对应fork ID。核对旧beta与alpha登记不变，旧Message sender/ACK身份及既有Work owner不变，不为此重发消息。`.aw-local`运行配置/Bridge/旧输入不是保存资产，不应当继承；不启动fork验证“不会自动做历史任务”，本段仅证明创建操作没有启动/分配入口。
4. 为e2e-q-fork创建一个明确的管理验收Work：目标仅为核对Fork数据与来源，不安排模型业务。公开work.create→show取得真实Work ID与blob revision；将已经实际核对的事实写入新实例`notes/q-fork-verification.md`，以正常asset.write保存，原beta资产不改。
5. 用show返回的当前revision调用一次work.update，补充实际核对结果；重新show取得更新revision，再work.deliver，refs指向实际Fork来源检查点、保存的核对记录及产物hash。最后show核对owner、新revision和唯一Delivery。不同命令返回的Git commit与Work blob revision不能混用。
6. 保存原命令、Git来源/hash、Work前后revision/Delivery和最终无执行权状态。本地测试实例和Work原位保留，不删除/归档历史，不start，不改原beta任务，不配置Harness。

本段可标PASS_REAL_DATA_CONTRACT：真实Fork来源/身份/资产与管理端Work创建更新交付。**不能称模型完成Work、Fork真实relay新会话已通过、并发CAS冲突已通过，或交付引用自动验证已实现。** refs当前由使用方提供，源码只要求显式非空，不会替使用方验证业务结果。本段实际管理核对完成后才交付，不把旧P业务冒充新Fork执行成果。

不故意重复deliver、不制造旧revision冲突、不测试循环父工单，不加故障矩阵。预计1个新测试身份、1个管理验收Work、1份核对资产，模型0、外发0。

## Q2：第二独立程序安装，读取原有同一数据home

Q1收口后再做，来源相同固定wheel及已通过的校验manifest。新目录`<隔离根>/q-second-app`，必须不存在或为空；正常安装器默认无extra，不搬已有venv、不改变第一安装标记或选装项、不下载所有SDK。

1. 记录原数据registry、共享Git main与各实例branch revision、beta/alpha资格、来源检查点/关键资产hash、既有Work和Message/ACK事实。采用Q1结束后的数据状态作为基准。
2. 使用实际Python 3.11和dist/install.py，把既有wheel正常离线安装到q-second-app。无--open，无故障中断，无全局PATH或pip配置改动。
3. 在源码外cwd运行新绝对aw：version、workspace list/show、agent list/show、checkpoint show、asset.read、work.show。显式--home仍指向原workspace-home；新程序实际site-packages来自第二安装。比较同一Workspace/身份/目录/检查点/Work/资产/Message事实，不创建第二Workspace或重复身份。
4. 核对第二安装这些只读操作没有改变上述共享Git、registry、实例资格或关键资产；不启动服务、worker、模型或桥接。原alpha旧HY current与monitor_stopped现场保持。保存两个安装的程序来源与同数据读回证据。

本段补A组“第二独立安装复用现有身份/数据”的CLI事实；不是第二台机器、应用UI重开、不同版本迁移或旧本机服务优雅停止验收。无extras不影响只读现有Codex/WeCom配置，但不宣称第二安装已具备实际WeCom/SDK运行环境。预计只新增一个程序安装目录，无新业务数据，模型0、外发0。

## 留给之后的真实调用

内部Message Watch未测是此前范围/预算收缩及W企微优先，不是产品明确不支持。需要实际运行sender和receiver、normal消息队列、Watch唤醒与自身receive/ACK，且把boot和自动输入计入真实轮次。alpha HY未释放，不用它做sender；若选择本次fork作为独立sender，必须另行明确其测试职责并在实际新会话relay，不能以本段静态Fork证明替代。P只证明外部WeCom自动续接。

管家授权/撤销未测是R只执行无模型健康两周期。真正证明受限Agent工具边界，需要授权一个明确测试管家在自己的真实会话调用目标限定的管理工具，并核对授权、撤销后的实际结果；普通管理CLI的grant/show不能冒充模型权限校验。不能为凑通过启动全部管家或维修alpha HY/生产业务。有限维修可先选择明确的无有效入口测试目标，但是否需要模型通知/判断须另段安排。

当前仅交付具体范围供Lead内部核对；未执行上述Fork/Work/安装，不向用户再次索取模型预算。


## Q批最终结果（2026-10-07，当前最新补充）

Q1与Q2按顺序完成，新增模型0、外发0、服务0。P真实自动交接/群续接/模型自停及用户可见确认仍有效，见下面P记录；没有重跑P或改变原beta/alpha资格。完整A–J仍不全部通过。

| 新增正常覆盖 | 实测结果与证据边界 |
| --- | --- |
| I组Fork数据合同 | 从真实P checkpoint `c3788071b0e70473aa054a218b12688eb`/revision `36da4bc44cc714f5c442925d57814f3c46af60b3`创建新身份e2e-q-fork。新分支初始revision `8308658c1344bfe75fc99867e52e0b4f7519dda0`，父提交严格为来源revision。70个保存文件只`.aw/identity.json`必要变化，69个原文件blob相同。新实例current=null、has_run=false、无Binding/session，runtime=not_running；未继承.aw-local运行配置/Bridge/输入或private凭据。原beta/alpha与所有既有main记录不变。[Q1事实](evidence/Q08-Q1-final-facts.json)。这是实际管理Fork，不是Fork模型relay已通过。 |
| I组最小Work | 单个管理验收Work `w6e0f8c4a4a67405ea2fd4e0a11b95b13`，owner=e2e-q-fork。create revision `288b765f8095391679816cc1e0263dc9dd8be3cb` → 正常update revision `79daf01cc115a9f0fcd5038104557f2bc1a0d0be` →唯一Delivery，refs均有实际来源/hash。核对记录`notes/q-fork-verification.md`由公开asset.write保存为本机资产，未额外做Git checkpoint；Delivery对此明确标注。管理端真实完成数据核对，不冒充模型业务交付，不声称refs自动校验或并发CAS分支已实测。 |
| A组第二独立安装复用 | 同wheel/hash，经正常离线installer安装到q-second-app，无extra，源码外新绝对aw/Python模块确认来自该安装。显式指向同一workspace-home，读回Workspace/身份、P检查点、Fork材料、Work revision及Delivery。[Q2事实](evidence/Q13-Q2-final-facts.json)。前后registry与全部实例文件字节、共享Git所有refs完全相同。不是第二台机器、不同版本迁移、UI优雅重启或第二安装SDK/WeCom实际运行验证。 |

仅新增授权的1个Fork身份、1个管理Work、1份核对资产和1个独立安装目录，原位保留；没有配置或启动新Fork、Harness、管家、Watch或Bridge。模拟产物hash保持2ff4deccf19bcc95d68f8f048148578841e539999a3c73aa0535ddf3ee276c7b。alpha旧HY资格及历史submitted/transfer记录不修复、不重放。主仓仍仅Lead/user既有文档改动，执行方未改主仓。P累计17个Codex原生turn及群3/20计数不增加。

[同一覆盖表](P-COVERAGE-AND-PLAN.md)已补A/I实际结果；[后续最短Watch建议](R-WATCH-NEXT-STEP.md)只做准备，尚未执行。其余管家受限工具、普通TTY、远端Git和边界项仍保持未测或限制。当前Q收口，不自动启动下一段。

