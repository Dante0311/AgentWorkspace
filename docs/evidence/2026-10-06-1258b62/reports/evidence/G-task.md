# G批一次性受限管家任务（当前明确授权）

用户/Lead明确授权在隔离Fork e2e-q-fork做正常权限与sync-idle验收，已授权操作不再另问。保持内置maintainer身份/定义。全部业务只用aw_execute，禁止shell、网络、OS/native权限代做。不要发Message/企微、启动Sentinel/巡检、实例或生产任务，不修alpha/beta历史未决记录。原职责保留，本段以下三个正常轮次优先；历史资料仅作来源。

身份以当前入口注入的workspace=e2e-local、agent_id=maintainer和真实binding为准。跨目标asset.write/maintenance.repair必须明确agent_id=e2e-q-fork。禁止用本管家身份替代目标。

第一boot轮：通过aw_execute asset.read读本AGENTS和当前能力说明，agent.show读自身/目标事实。对目标notes/g-maintenance-scope.md只尝试一次asset.write，agent_id=e2e-q-fork，revision=null，content="G测试未授权写入，预期应被拒绝。"。当前无授权，预期权限拒绝；不得换路径/重试/用shell绕过。随后仅写自己的notes/g-phase-1.md，记真实拒绝、目标状态与当前Binding，然后等待。不要stop或自行grant。

第二轮仅在正式normal授权输入后：对空闲Fork调用maintenance.repair，参数agent_id=e2e-q-fork、action=sync-idle、request_id=g-sync-idle-fork-001。查看真实result和verification；applied不等于healthy，如实保留degraded问题，不把无变化同步称异常恢复。仅当applied且结果已知，再以完全相同参数/ID调用一次，核对读回原结果相同，不换ID重做。attempting/outcome_unknown/失败时不重试动作，如实保存等待。

正常已知applied后，asset.write仅新增目标notes/g-maintenance-scope.md，revision=null，content="G批已授权的隔离维护笔记。sync-idle由maintainer真实受限工具完成；仅记录正常空闲同步，不代表故障恢复或Workspace全部健康。"。通过asset.read（agent_id=e2e-q-fork）亲自回读内容/revision；写自己的notes/g-phase-2.md，记实际repair ID/result/verification、同ID结果比较、目标笔记内容/revision、当前Binding，然后等待，不stop。写目标笔记必须在同步之后，不动其他目标文件/记录/Work。

第三轮仅在正式normal撤权输入后：用第二轮实际读得的revision，对相同目标笔记尝试一次asset.write替换，content="撤权后替换尝试，预期应被权限拒绝。"。应被权限拒绝，不重试/换路径/改本机文件。保存自己的notes/g-final.md，记录三阶段真实结果、正常同步而非故障恢复、撤权和当前Binding；创建真实checkpoint并agent.stop，awaiting_native_idle后结束。

工具签名：agent.show、asset.read、asset.write无binding；asset.write用真实revision。maintenance.repair使用action参数；checkpoint.create使用summary/content；agent.stop checkpoint使用真实返回ID。目标只读可见不等于写权限。未知结果不重放，不声称未验证的效果。
