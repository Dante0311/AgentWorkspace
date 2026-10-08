# 修复后定向验收最终独立复核

2026-10-07（Asia/Shanghai）。批次 `2026-10-07-5aaae00-fa8c7261`，固定产品提交 `5aaae00520374b022e0c38fa21f312f8e08629ba`。本复核只读新批次原始 runtime、输入账本、transfer 记录、共享 Git、资产、测试原日志及必要源码；没有运行测试、模型、服务或渠道，没有修改产品、执行报告或任何平台状态。完成原始核对后读取执行方最终报告，结论及边界与其相符。

## 结论

| 项目 | 独立判断 |
| --- | --- |
| E2E-004 | 两次同 Codex 自动 transfer 的完成终态持久化、释放后 session 保留、新请求不被旧完成记录阻挡、旧 ID 原结果/归档读回，取得限定 PASS_REAL 证据。 |
| E2E-001 | 普通 boot、handoff、normal 停工及 boot 自停分支收口成立；但忙碌时 insert/steer 的返回形态仍导致输入留在 submitted。只能确认普通路径修复，不能关闭整项。 |
| E2E-002 | 原选 WorkBuddy 无扩展名 JS 入口仍在进程启动阶段报 WinError 193，启动修复未覆盖该真实入口。认证未到，真实 HY 业务未运行；不是“仅待登录”。 |
| Watch | 两个真实业务消息、本人 receive/ACK、同 session 顺序资产及本人停工成立；第一通知轮有一次管理端 steer 澄清，不是无人介入自然流程完整通过。 |
| 验证与收尾 | 13/13 原生 turn 完成；11 个经 turn.id 关联输入 completed，另一个 steer 输入仍 submitted。定向测试环境修正及原失败保留，最终测试实例 released、Runner 退出，进程审计无残留。 |

不新增 E2E-005：以下发现属于原 E2E-001 残余和 E2E-002 未覆盖入口。通过部分不能掩盖未修部分；也不把模型参数自纠、测试指令偏差或缺包环境错误登记成新的产品缺陷。

## 两项仍需修复的问题

### E2E-001 残余：忙碌 insert/steer 返回 turnId 无法收口（P2）

**实际触发。** beta Binding `b90eb318a30e84c78a80a1ba2d03ccd18` 在处理第一条 Watch 通知期间，管理端通过公开 agent.input 一次投递 `delivery=insert`、ID `repair-watch-clarify-first-end-001`。真实输入结果是顶层 `result.turnId=01a11662-e04e-7c02-bcda-8b58360e5761`；本复核直接读取对应 Binding 的原始 runtime，存在该 turn 的 `turn/completed`、status=completed。最终实例已 released，但直接读账本仍为 submitted。原始澄清 userMessage 也进入同一 turn，并未另开一个原生 turn。[原始操作回执](../reports/evidence/84-watch-first-turn-steer-clarification.json)、[账本/事件对照](../reports/evidence/87-steer-terminal-ledger-mismatch.json)。

**源码与影响。** `src/agent_workspace/runtime.py:141-150` 对 busy+insert 返回原生 turn/steer 结果；`_complete_inputs` 在 `:559` 仅读取 `item.result.turn.id`，无法关联顶层 turnId，虽已有匹配完成事件也不会更新状态。输入终态和诊断持续错误，修复“停止时完成事件收口”仍缺少该返回形态。当前 submitted 不会被现有 queued 调度自动重发，不能从此推断发生重复业务；也不能为修账本重放已执行输入。完成事件表明该原生 turn 已结束，不等于每份插入指令都单独拥有一轮或独立业务完成证明。

**准确边界。** 不是所有 delivery=insert 都失败：本批两条 handoff 输入是在 idle 时经 turn/start 得到嵌套 turn.id，已 completed。确定残余是 busy 时走 turn/steer 的形态；普通路径的成功不能替它验证。建议在负责的原生返回/输入收口边界支持这两种真实结果，并以匹配完成事件决定终态；本复核没有实施修复或补测。

### E2E-002：真实 WorkBuddy 无扩展名 JS 不走 Node 适配（P2）

实际入口为 WorkBuddy 的 `resources/app.asar.unpacked/cli/bin/codebuddy`，无后缀。本复核只读文件首行 `#!/usr/bin/env node`，hash 与启动记录一致：`8df0f1c7bc6535e5df0b626450228241d874867023adb6c9c8f7b1a882590bf4`。Node v22.19.0 存在，固定 SDK 为 0.3.267；真实控制连接仍为 OSError/WinError 193，query_sent=false，native_events=[]，disconnect 已返回。[实际入口结果](../reports/evidence/24-workbuddy-real-js-control.json)、[Node 版本](../reports/evidence/24-node-version.json)。

核对保存的 sdk_probe 执行源：它确实调用修复后的 `_codebuddy_client`，尝试原 SDK connect/控制请求，没有 query，没有绕过产品适配去直接用另一个 Client。`src/agent_workspace/native_sdk.py:53-54` 仅识别 .js/.cjs/.mjs；无扩展名直接返回原 Client，因此原 SDK 仍将 JS 当可执行程序交给 Windows。Node 和 .cjs 协议夹具测试成功不能证明用户原选入口可启动。该分项为启动失败，认证 NOT_REACHED、真实接手 NOT_RUN；不能改写成 /login 阻塞，也不能推断 Desktop 登录情况。建议覆盖用户实际选定的入口形态，保留其路径和固定 SDK 契约；本复核不改名、不换入口、不尝试登录。

## 通过部分的关键独立证据

**自动持久完成先于状态查询。** 第一笔 `repair-transfer-001`：旧 `b5c3219661559459fa9a25989219ece5e`，唯一后继 `b6e03436a69484d6a8dfd22c5767b8dd2`，session `01a11657-dd6a-7e20-8f00-7c254dd4e6aa`。26 的磁盘 completed 捕获在 20:31:15.014153，首次 28 状态查询在 20:31:15.018666。第二笔 `repair-transfer-002`：旧 `b5498a27dda6b403fb6a077e641c861f7`，后继 `ba21c526be5c24387927df1e2897c7949`，session `01a1165d-1adc-7a70-9b75-9599ea71aba0`；39 的 completed 捕获在 20:36:49.613212，首次 41 查询在 20:36:49.615204（均 +08）。保存的 first_successor/second_transfer 观察代码只读磁盘和原事件，未调用 advance/transfer-continue；observe 读取 transfer.json，不经公共 status 计算。因此证据支持由后继 Runner 自行持久化，而非查询推动完成。[第一磁盘记录](../reports/evidence/26-first-disk-completed-before-query.json)、[第二磁盘记录](../reports/evidence/39-second-disk-completed-before-query.json)。

**本人保存、停止与旧结果读回。** 原始工具事件确认两端旧模型 handoff 的 checkpoint/stop；两个后继也分别本人 checkpoint/stop，并有 matching completed 事件。第一后继输入 `repair-first-successor-stop-001`、turn `01a11658-bfc2-7a83-9fea-f49337649bb6`，模型漏传指定 checkpoint_id，真实生成 `c6116971e054a4e9195cbd8baa5a006d2`，并以该真实 ID stop。这是明确指令偏差，不称指定命名检查点通过；原指定 ID 读回失败保留，未补造。第二后继输入 `repair-second-successor-stop-001`、turn `01a1165d-dbea-7003-8da1-b1db7ba1c36f`，真实保存并 stop `repair-second-successor-stop`。[第一链](../reports/evidence/35-first-chain-proof.json)、[命名偏差](../reports/evidence/32-checkpoint-id-instruction-deviation.json)、[第二链](../reports/evidence/48-second-chain-proof.json)。

33/46 公共查询在释放后仍返回 completed/session；34 同 ID 重提和 47 已归档旧 ID 重提返回第一原结果。保存的观察前后输入/native_turns 没有增加；独立扫原始记录仅存在本批七个 Codex Binding、13 个 started/completed，没有额外替代后继。直接读当前 transfer.json 和 transfers/repair-transfer-001.json，第二终态与第一归档的 session、目标 Binding 均保留。第二新合法入口和新 transfer 已实际成功，不只根据源码推测未阻挡。

**资产与 boot 自停。** source、verify-first、verify-second、verify-boot-stop 字节 hash 相同，`1626a2844b024787867af11fa3ee873702e64e785e2a192e7c3c5f1b23159ab3`；独立读本机文件并比对共享 Git 最终实例分支的对应 blob，资产真实保存。独立 boot Binding `bd880ba2ec26541f189adcd456e6f7c67` 的原生 turn `01a1165e-e176-7203-a629-c6632026a26e` 本人保存 `repair-explicit-boot-stop` 并 stop。boot.state=completed，checkpoint_revision 等于该显式检查点 revision `c314439a453a198fb73585a913554d33545556ac`，没有新增 initial-<binding> 自动检查点。共享 Git Binding 也为 released，checkpoint 指向该显式 ID。[boot 分支](../reports/evidence/55-terminal-repair-group-proof.json)。

**输入与原生轮次分别计数。** 本复核直接扫描七个 Binding 的完整 runtime.jsonl，started/completed=13/13，无失败终态：前两次交接/收尾和独立 boot-stop 共9，通信 sender1+receiver3 共4。读取全部12个输入，每个真实 turn ID 都有一份匹配的 completed 事件；11个嵌套 turn.id 输入已 completed，唯一顶层 turnId 的 steer 输入仍 submitted。两次通知不经过 queue_input，不伪造其输入ID；一次 steer 不增加新的 native turn。普通完成证据不能被“输入仍 submitted”否定，账本残余也不能被“原生已完成”隐藏。[逐轮账本](../reports/evidence/88-final-model-input-ledger.json)。

## Watch 的真实结果及介入边界

repair-alpha `b9b67ff957706480899d041a2d36aca28` 的同一原生 turn 本人发送 `repair-watch-001/002`，两条均 normal/published，第二引用第一。repair-beta `b90eb318a30e84c78a80a1ba2d03ccd18` 在 session `01a11661-bd46-7020-9fb1-6c1ed672dd4c` 收到两个真实平台通知，分别在 `01a11662-e04e-7c02-bcda-8b58360e5761`、`01a11669-47be-7593-ba2c-600e3561c8c1` 本人 receive，ACK 均 published、Binding 匹配。共享 Git main 的两消息/两ACK与原生返回一致。最终 watch-order.md 记录先001后002及相同随机标识，hash=`e00f5abe8108533bc03a2715725587431ed6957ea187cb39a5b7d0ba997e0a9e`，实际文件与共享 Git blob一致。sender/receiver 分别保存 `repair-watch-sender-stop`、`repair-watch-receiver-stop`，本人 stop 后最终 released。[Watch 证据](../reports/evidence/75-watch-final-proof.json)。

第一轮模型在 ACK/记录后仍在同 turn 内等待第二条通知；原始 item/completed 有12次 native sleep，并有 agent.show 查询和参数自纠。第二条 normal 必须等该 turn 空闲，不能把这段等待直接归因平台投递延迟。管理端84通过一次公开 insert 澄清结束当前 turn，真实澄清 userMessage 与第一条通知处于同 turn；随后才进入第二通知轮。[介入边界](../reports/evidence/84-watch-control-intervention-boundary.json)。

业务 send/receive/ACK/资产/checkpoint/stop 的平台副作用均来自 aw_execute；原生 Shell commandExecution 数为0，但有 native sleep，因此严格 aw_execute-only=false。无介入自然 Watch 完整流程未取得通过证据。错误参数在同轮内纠正，失败调用保留；不是产品替模型伪造工具返回，也无需为抹去偏差再跑模型。

## 定向测试日志、软件来源与收尾

独立核对原 stdout/错误和 JUnit 用例名：

- 第一组121项首跑120 passed、1 failed；失败是 OS 锁测试子进程 ModuleNotFoundError，隔离 build-only 环境未安装产品。安装同一固定 wheel 后仅原失败用例重查1 passed；没有重跑整121组，不把首跑写成121全绿。[首次原输出](../reports/evidence/10-terminal-regression.txt)、[单例重查](../reports/evidence/68-os-lock-clean-process-recheck.json)。
- SDK 原组29项是24 passed、5 skipped，五项均缺 Claude SDK。隔离 sdk-app 安装固定0.2.163后，85的五个用例名与原 skipped 完全对应，5 passed，没有重复计算原24。81是 selector 拼接错误、exit4、零执行用例，不能计为测试通过或额外测试数。[原SDK结果](../reports/evidence/43-windows-sdk-regression.json)、[selector错误](../reports/evidence/81-five-claude-cases.json)、[五项补测](../reports/evidence/85-five-claude-cases.json)。

这是Windows本机执行的定向测试和真实 SDK/Node 协议夹具；不能外推为有效 HY/Claude认证、真实WorkBuddy接手或官方模型业务。官方登录 Luna 的13轮与这些夹具结果单独记录。

来源记录固定提交，wheel SHA256=`e9bcff1a015358643bafbc800d1beb7453dd36cbb8bd1c34a10e68d68ca309f7`。独立计算固定source与app/sdk-app/build-app中runtime.py/transfer.py/native_sdk.py的字节hash，九个对应关系均一致，和77记录相符；版本0.1.0a1不是修复版身份依据。三个源码hash依次为 `700e2c7733a4e18d202b8050f54a6956b00fe49a81cd4bd5c949735b6f92b592`、`1776fa2d4de763f44486dab9012eab3dfe21af62176d3f97a0cb382da0d281a4`、`c9bb50a64ca1c73debb6e166e028d195686839471e4c82ce75cddbe4284237d1`。[制品来源](../reports/evidence/05-wheel-origin.json)、[安装字节核对](../reports/evidence/77-installed-fixed-source-byte-check.json)。

72的正式show与共享Git Binding均支持两个测试实例current=null/released/runner_alive=false、Watch关闭；90的最终OS审计remaining_batch_tree为空、21个tracked Watch进程全部不存活，forced_product_termination_used=false。本复核不另启进程检查，不将记录时间的进程审计升级为持续观测或旧批次资格全部释放。企微及其他外部业务消息新增0；原生turn不是精确收费API次数，无独立账单不报告实付金额。[最终审计](../reports/evidence/90-final-process-audit.json)。

## 收口和交接

执行方最终canonical结论与独立核对一致。可以据本轮证据认可 E2E-004 和 E2E-001 普通路径的限定修复，继续保留 E2E-001 steer 残余、E2E-002 原入口启动失败与 Watch 介入限制。无需扩大测试矩阵、恢复旧未决输入或改现场证明通过。

本复核仅写 review/FINAL-REVIEW.md，未改 canonical报告、主仓或旧现场。采用相对证据链接，不含真实机器路径/账户/凭据，便于随同 reports 目录归档；本复核未生成或验证shareable压缩包与脱敏manifest，入仓前由Lead整合本文件并更新清单/校验。历史失败及修复验证分别保留，不覆盖旧结论。Desktop、企微、生产UE/CI、自有服务、远端Git业务、跨Harness真实业务和长期运行没有新增证明。本轮结束，不自动继续或向其他聊天发信。
