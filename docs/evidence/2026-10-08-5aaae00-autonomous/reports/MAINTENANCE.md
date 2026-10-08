# 管家真实发布故障恢复

限定闭环通过。新的 maintenance-local，真实 Sentinel/Maintainer，官方 gpt-6-luna/low，started/completed 分别3/3、2/2，共5轮。steward 身份由 Workspace 初始化正常创建，本轮未启动模型。

工具限制未完全遵循：Maintainer首次boot实际出现3次原生commandExecution，不能声称strict-aw_execute-only通过。第1次尝试只读全局MEMORY.md，创建执行进程失败（exit -1，setup refresh error）；第2次只读猜测skills目录，路径不存在（exit1）；第3次成功只读实例内agent/SKILL.md及AGENTS.md（exit0）。没有在这些命令中写入文件或维修Git，但仍违反本轮禁止Shell的要求；实际维修业务经受限平台maintenance.repair完成。[全部真实Shell事件](evidence/97-all-native-shell-calls.json)及原生completed commandExecution归档保留，不省略或重跑求绿。

管理端先记录[可逆故障计划](evidence/40-fault-plan.json)，核对 bare authority 的解析路径在本轮根内、原 receive.hideRefs 不存在。仅本地配置临时 receive.hideRefs=refs/heads/main，公开 message.send 单次 request_id=aw-maint-fault-001，实际 Git push 拒绝，产品自然保存 pending，未手写操作账本。finally 删除此次设置，[恢复核对](evidence/47-rollback-verified.json)原配置仍不存在；未改全局 Git 或其他仓库。

控制脚本错误预期退出码0；CLI 正确以2表达 pending，脚本在已取得真实失败后提前结束观察。finally 实际执行。读取原输出/原 operation 接续，没有重发消息、重复注入或制造新失败。message.operation 同样以2表达 pending，其读取证据保留。[编排错误](evidence/49-controller-exit-expectation-error.json)、[真实失败](evidence/44-real-failed-publication.json)、[恢复后仍pending](evidence/48-original-still-pending.json)、[故障观察](evidence/45-fault-doctor-after-rollback.json)。

正式 aw maintenance run 在底层写入条件恢复后启动；真实30秒 schedule 检查发现 publication_pending，并自动将 health-f5242c08aae54c66a6807bbd32b81e20 交付 Sentinel。[定时检查事实](evidence/62-worker-real-timed-observation.json)。Sentinel 自己发送 aw-maint-task-001；Maintainer 本人 receive/ACK 后，经只授予 maintenance.repair、target=[sentinel] 的权限，执行原 operation 的 publication-reconcile。不是任意shell、OS/Git权限修复、sync-idle冒充恢复或控制器代repair。

[维修回执](evidence/59-repair-receipt.json)同时确认 state=applied、result.state=published、原 operation published。Maintainer 发 aw-maint-result-001 后，Sentinel 本人 receive/ACK、重新读取原 operation 与新的 doctor。[独立最终doctor](evidence/55-independent-doctor.json)healthy/issues=[]；目标 publication_pending 已消失。[实际维修笔记](evidence/57-maintainer-asset.json)、[实际复核笔记](evidence/57-sentinel-asset.json)、[任务](evidence/58-aw-maint-task-001-show.json)、[回复](evidence/58-aw-maint-result-001-show.json)。管理端恢复底层写入条件，模型补齐协议发布，两者证明边界明确。

同一维修request_id回读一次，原回执SHA256前后均792cc485e0978950711ec2cdb243f02e9e01ecf9b7aa227e7dabb8e457505d74，未再次发布。[幂等核对](evidence/61-repair-idempotence.json)。未测试 outcome_unknown 的重试，不扩大证明。

两位模型自身 checkpoint/stop，最终 released/runner_alive=false，Watch disabled。[最终原生观察](evidence/51-maint-final-observation.json)。管理端关闭 schedule、撤销 grant，再对自有正式巡检终端 Ctrl+C；终端exit1不是优雅finally的证明，但[进程审计](evidence/63-process-audit-after-maintenance.json)仅观察命令自身、无巡检/模型运行进程，[公开状态](evidence/65-maintenance-worker-final-status.json)worker_running=false，schedule disabled、授权为空。未强制释放 Binding、删运行锁或追加纠偏模型输入。

保留1个未读测试刺激消息给未启动的steward，不启动其业务模型、不代ACK以清零。修复只是发布原消息，不代表对方处理业务。静态相邻疑点：message.reconcile 的授权边界可能与受限 maintenance.repair 不一致；本批没有扩测该入口或修改源码，不能声称所有补齐入口都具备同样最小授权约束。

不代表 Desktop、远程服务、生产故障、外部渠道或所有维修类型。历史失败证据不覆盖。
