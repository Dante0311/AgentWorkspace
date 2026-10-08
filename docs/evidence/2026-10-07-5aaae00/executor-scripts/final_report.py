import json
from record import ROOT, EVIDENCE, save, now

def read(name):return json.loads((EVIDENCE/(name+'.json')).read_text(encoding='utf-8-sig'))

origin=read('00-source-origin');wheel=read('05-wheel-origin');ledger=read('88-final-model-input-ledger')
first=read('35-first-chain-proof');second=read('48-second-chain-proof');boot=read('55-terminal-repair-group-proof');watch=read('75-watch-final-proof');process=read('90-final-process-audit')
assert not process['remaining_batch_tree'] and not any(x['alive'] for x in process['tracked_watch_processes'])
lines=['# 修复后本机真实验收：最终报告','',now(),'','修复的普通输入收尾和交接持久终态在本机真实官方登录链中成立；尚不能将全部问题关闭。E2E-002原选WorkBuddy入口仍WinError193；额外纠偏steer暴露E2E-001的turnId返回形态残余。没有为通过测试修改产品或旧状态。','',
'## 软件与隔离范围','',f"软件提交 `{origin['commit']}`，fixed source archive SHA256 `{origin['source_tar_sha256']}`。wheel `0.1.0a1` SHA256 `{wheel['sha256']}`；不能单靠版本号识别修复。[来源](evidence/00-source-origin.json)、[制品](evidence/05-wheel-origin.json)、[六个相关模块在三个隔离安装的逐字节核对](evidence/77-installed-fixed-source-byte-check.json)。",
'',f'本机ROOT：`{ROOT}`。新home与Workspace `repair-local`，仅新实例 `repair-alpha`、`repair-beta` 执行测试；默认三管家身份建立但未启动。官方登录检查及模型目录为真实原生结果，模型 `gpt-6-luna/low`。无认证文件读取/复制/输出、无全局配置或服务更换。新源码来自已合并5aaae00，不应用历史补丁。旧1258b62批次仅按需只读，无旧账本/transfer/locks/HY资格迁入或修改。',
'','## 本轮结论','',
'| 项目 | 实际结果与边界 |','| --- | --- |',
'| E2E-004持久终态 | 两次正常同Codex自动transfer；每笔均在首次transfer-status前取得新磁盘completed/session证据。后继停工后仍completed/session保留；同旧ID重提无额外输入/turn，新合法入口和新transfer ID不被旧终态阻挡，旧ID归档可读。没有advance/transfer-continue或手改状态。 |',
'| E2E-001普通收尾 | 9个真实boot/handoff/normal轮次完成；输入按实际turn ID成为completed，显式checkpoint、released和Runner退出对应。另一个boot自身checkpoint/stop引用其显式快照，未在关闭后生成automatic initial checkpoint。 |',
'| E2E-001额外残余 | Watch纠偏insert/steer输入仍submitted，原生同turn已completed、实例released。实际返回result.turnId，_complete_inputs只取result.turn.id，无法关联。该新记录保留，不重放/手改；Lead负责登记与修复判断。普通链限定通过不等于该残余关闭。 |',
'| E2E-002实际入口 | 原选WorkBuddy bin/codebuddy是无扩展名JS。Node存在，固定SDK0.3.267真实connect仍WinError193，控制握手未到、认证未到、HY业务未运行。修复仅识别.js/.cjs/.mjs，原入口未走Node适配。不改名、不换SDK自带exe、不/login，不推断Desktop登录情况。 |',
'| normal Watch回归 | 两个本人send/receive/ACK、同session顺序资产、双方本人checkpoint/stop真实成立。但第一通知轮模型sleep/反复查询等第二消息，管理端一次正式steer纠偏后才结束，不能称无介入自然流程通过或把这段等待算产品投递延迟。 |',
'| 定向测试 | 原121项首跑120pass/1环境import failure；同固定wheel装入build-only环境，仅失败锁测试重查1pass。SDK原组24pass/5缺Claude SDK skip；固定0.2.163装入隔离sdk-app，仅原5项补跑5pass。保留初次失败与selector错误，不声称所有项目一次无错通过。 |',
'','## 交接、显式停工与身份ID','',
f"第一笔 `repair-transfer-001`：旧Binding `{read('26-first-disk-completed-before-query')['record']['old_binding']}` → 后继 `{first['binding']}`，session `{first['session']}`，后继本人checkpoint `{first['checkpoint']}`。后继stop输入 `repair-first-successor-stop-001`，原生turn `{first['stop_input']['result']['turn']['id']}`。[首次查询前磁盘](evidence/26-first-disk-completed-before-query.json)、[后继终态](evidence/35-first-chain-proof.json)。模型省略指定checkpoint_id，实际创建随机ID；管理按指定ID读回失败保留，改读真实ID，没有补跑或假造命名快照。[偏差](evidence/32-checkpoint-id-instruction-deviation.json)。",'',
f"第二笔 `repair-transfer-002`：旧 `{second['record']['old_binding']}` → 后继 `{second['record']['target_binding']}`，session `{second['record']['session']}`，checkpoint `{second['checkpoint']}`，stop输入 `repair-second-successor-stop-001`，turn `{second['native_turn']}`。[首次查询前磁盘](evidence/39-second-disk-completed-before-query.json)、[新事务与旧归档读回](evidence/48-second-chain-proof.json)。",'',
f"独立boot自停Binding `{boot['boot_binding']}`，显式checkpoint `{boot['explicit_checkpoint']['id']}`、revision `{boot['explicit_checkpoint']['revision']}`；boot输入completed的checkpoint_revision与此完全一致，无initial-<binding>自动快照。[明确分支证据](evidence/55-terminal-repair-group-proof.json)。",'',
'三个验证文件verify-first、verify-second、verify-boot-stop与新source字节一致，随机标识及hash见相应证据；checkpoint是模型本人调用，管理仅正式读回。阶段返回awaiting_native_idle不作released，后续正式show和原生完成记录才支持实际释放。',
'','## Watch与输入残余','',
f"sender repair-alpha Binding `{watch['bindings']['repair-alpha']}`，receiver repair-beta `{watch['bindings']['repair-beta']}`。新消息 `repair-watch-001/002`（均normal），第二引用第一；两ACK均published。两通知直接由Watch adapter.notify进入同一原生会话，没有伪造queue_input ID。[真实工具、事件、资产与checkpoint](evidence/75-watch-final-proof.json)、[busy只读观察](evidence/70-watch-current.json)。",'',
'第一消息模型在当前turn内等待第二条，原生sleep/agent.show反复调用保留。管理仅一次agent.input insert `repair-watch-clarify-first-end-001`，不发送替代消息、不重做第一条、不提前停工。两normal业务副作用由aw_execute产生；strict-aw_execute-only=false、unassisted-normal-flow=false。[介入](evidence/84-watch-control-intervention-boundary.json)。',
'','steer原生返回turnId，与已完成第一通知turn匹配，但输入仍submitted；普通输入与该残余分列。[输入/原生终态和源码依据](evidence/87-steer-terminal-ledger-mismatch.json)。模型asset.read/agent.show误加binding、agent.stop误用checkpoint_id等失败，随后在原轮内自行纠正；全部失败调用在最终审计及原生日志保留，不为抹去偏差重跑。',
'','## 测试与环境修正','',
'[121项原输出](evidence/10-terminal-regression.txt)、[原JUnit](evidence/10-terminal-regression.xml)包含真实120passed/1failed。锁测试子进程ModuleNotFoundError为隔离build-only环境未安装产品；安装同制品后仅该例通过：[单例结果](evidence/68-os-lock-clean-process-recheck.json)。无PYTHONPATH模块预注入、无生产代码或测试修改、没有重跑121组。',
'','[SDK24pass/5skip](evidence/43-windows-sdk-regression.json)及[固定Claude安装](evidence/80-isolated-claude-sdk-install.json)、[五项5pass](evidence/85-five-claude-cases.json)属于实际SDK/Node协议夹具。首次补跑selector拼接错误exit4没有执行用例，81记录保留，85只纠正文件路径后跑原5项，24已过不重跑。没有真实Claude模型或HY业务调用。冗余build环境SDK下载在已安装SDK完成测试后仅终止其拥有的两个下载进程，没有中断产品或测试。[完整计数](evidence/91-final-test-accounting.json)。',
'','[原WorkBuddy实际握手失败](evidence/24-workbuddy-real-js-control.json)与夹具分别记录。用户选定入口未改，Node版本与入口hash见66，未通过启动故不能验证认证或接手；不自动登录、不复制Desktop认证。',
'','## 最终计数、进程与未测项','',
'Codex原生started/completed=13/13：交接/普通收尾及boot-stop9，Watch sender1+receiver3=4。steer在已有turn内，不另计原生轮次。输入共12：11normal/boot/handoff completed，1insert submitted。内部业务消息2/ACK2、企微0、其他外部业务消息0。原生轮次不是精确模型API数，独立账单/总token与实付费用未核算，不填估算冒充实付。[逐Binding/session/turn及失败调用审计](evidence/88-final-model-input-ledger.json)。',
'','两个测试实例最终current=null、runtime=released、runner_alive=false，Watch关闭；没有启用Bridge、巡检计划或任何管家模型。OS最终batch tree=0，先前记录的Watch进程均退出，未强制终止产品进程。[最终进程审计](evidence/90-final-process-audit.json)、[管家与计划](evidence/89-maintenance-final.json)、[所有身份](evidence/89-final-agent-list.json)。新steer未决账本保留；无重放、删除锁、强制释放或替代后继。',
'','不重跑完整A–J/六向矩阵。自有服务、跨Harness真实业务、长期通信、远端Git、企微、生产SBP/UE/CI、其他产品目录与原生Desktop均NOT_RUN。旧批次历史结论不覆盖。本批独立复核由Lead安排，本文是执行事实，尚不能冒充独立复核通过。',
'','## 可入仓交接','',
'本机完整材料与私有原生日志继续保留。shareable目录提供仓库相对链接、脱敏日志、manifest与归档校验；执行方不写开发仓、不提交/push/merge。真实凭据、account/rateLimit事件、模型reasoning片段、机器路径、安装目录、锁与运行缓存不入包；必要的测试原生事件/工具失败与操作ID不删。归档后的报告与源报告hash分列，历史失败不覆盖。证据包清单生成后另附路径与SHA256。','']
report='\n'.join(lines)
(ROOT/'reports/E2E-REPORT.md').write_text(report,encoding='utf-8')
(ROOT/'reports/CHECKPOINT.md').write_text('# 最终CHECKPOINT\n\n本轮已收尾，不再启动任何模型/服务/渠道或重放未决记录。\n\n'+report,encoding='utf-8')
save('92-final-report-facts',{'finished_at':now(),'source_commit':origin['commit'],'wheel_sha256':wheel['sha256'],'normal_terminal_repair':'PASS_REAL scoped','transfer_terminal_repair':'PASS_REAL scoped','steer_terminal_residual':'OBSERVED submitted despite matching completed turn','original_workbuddy_js_entry':'BLOCKED WinError193 before authentication','codex_rounds':13,'external_messages':0,'remaining_batch_processes':0,'main_source_changed_by_executor':False,'independent_review':'Lead owned, pending','report':'E2E-REPORT.md'})
print('Final report/checkpoint saved with residuals and historical failures')
