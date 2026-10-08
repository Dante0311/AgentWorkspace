# 2026-10-08 自主验收结果

固定源基线5aaae00520374b022e0c38fa21f312f8e08629ba；重新验证 wheel SHA256 e9bcff1a015358643bafbc800d1beb7453dd36cbb8bd1c34a10e68d68ca309f7，独立安装、新 AW_HOME、新 Workspace/实例/数据。主仓现有HEAD62dba38626d6a191a146868e7346ffe82bb58821及用户未跟踪文件未改动。未提交、推送、合并、改产品源码或访问Desktop私有状态。

| 组 | 实际结果 | 原生模型轮次 |
| --- | --- | --- |
| [normal Watch](WATCH.md) | 两消息、顺序记录、ACK、同会话、两端自身cp/stop闭环通过；boot提前receive被拒绝，发送者笔记抄错第二条from.agent；原始平台记录正确，无纠偏 | Codex 4，started/completed各4 |
| [管家真实发布故障恢复](MAINTENANCE.md) | 真实故障、定时发现、模型维修消息、受限repair、published、独立复核及本人cp/stop闭环通过；Maintainer boot有3次Shell，工具限制未完全遵循 | Codex 5，started/completed各5 |
| tclaude无模型预检 | 同包装器原生exe与SDK握手connected；认证只到configured_unverified，不能声称模型调用可用 | query=0 |
| Codex→tclaude真实交接 | WAITING_USER_MODEL_SELECTION；未建立此组Workspace、未启动任何入口或transfer，不能归为兼容性失败 | 0 |

总计9个官方Codex gpt-6-luna/low真实轮次，started/completed各9。没有额外纠偏模型输入、全测试或完整方向矩阵重跑，未使用WeCom、WorkBuddy、生产或其他产品仓库。[原生实际工具/轮次汇总](evidence/66-watch-maintenance-proof.json)。两组失败与编排偏差分别保留，不覆盖原结论。Watch发送者模型笔记抄错第二条from.agent，真实发送回执/共享消息仍为watch-alpha；按平台原始事实判断路由，原笔记不改、不为此重跑。

管家组不具备strict-aw_execute-only证明：Maintainer boot发生3次只读Shell尝试，前两次失败，第3次读取实例Skill及AGENTS成功；违反明确工具限制。实际维修仍由受限平台命令完成，不把初始化限制偏差藏在维修通过结论中。[完整原生Shell事实](evidence/97-all-native-shell-calls.json)。

软件/依赖：[基线及wheel/Codex二进制hash](evidence/01-baseline.json)、[当前Codex版本](evidence/67-current-codex-version.json)、[tclaude/依赖版本与exe hash](evidence/20-tclaude-prerequisites.json)、[tclaude版本](evidence/21-tclaude-version.json)、[SDK源文件hash](evidence/69-sdk-source-checksums.json)。SDK固定0.2.163，安装于本轮app；tclaude0.1.8/b7d3493，上游Claude Code2.1.251。SDK握手仅启动临时RPC客户端、get_server_info，没有query、平台持久入口或全局配置变更。[握手结果](evidence/24-tclaude-sdk-handshake.json)分享时仅保留必要状态字段，完整catalog/账号字段排除。

清理：四个实际模型实例均current=null/released/runner_alive=false、Watch disabled；maintenance schedule disabled、grant为空、worker_running=false。临时Git本地receive.hideRefs已删除并核对。自有正式巡检终端Ctrl+C后exit1，exit码不证明优雅finally。已知本批Runner及启动PID均不再存活，[进程边界](evidence/68-final-native-process-boundaries.json)。未发现命令关联本轮ROOT的原生客户端。机器上另有tclaude/claude等原生服务，无法证明本轮独占，没有停止它们，不能宣称全局daemon或所有相关服务退出。

保留未启动steward的一条未读明确测试刺激；published只证明协议发布，不证明其业务处理。静态message.reconcile授权疑点在管家报告说明，未扩测或修复。不把后台CLI结果当Desktop；Lead另做Desktop只读验证，本包不纳入该目录。

原文件保留在本轮根内。分享包包含两组当前原生事件/实际工具结果、公开状态、资产/检查点、失败记录、版本/ID/hash与可审查编排脚本；JSON状态快照仅作证据，不能导入恢复运行。逐文件原始SHA与脱敏归档SHA及排除说明见包的manifest.json/EXCLUSIONS.md。不含凭据、授权头、账号、私密机器路径、完整聊天、native reasoning、完整工具或模型catalog、安装环境/缓存、运行锁/可运行完整AW_HOME或截图。

首次分享目录r1的路径扫描误把CLI帮助中Commands后面的JSON换行转义判作盘符路径；检查器加盘符前边界后归档r2。Lead随后指出Maintainer初始化Shell偏差，核对全部原生事件并补记，分享包证据AGENTS.md改名AGENTS.snapshot.md以免作为活动指令，新建最终r3。未覆盖r1/r2或原证据；r1/r2不是当前交付包。实际ZIP/hash与逐项核对结果见根目录PACKAGE-HANDOFF.md。

增量继续入口：仅当Lead另行转达用户明确模型/强度选择后，先校验现有SDK profile可表达该模型，再新建transfer-local；使用同一身份/工作根的正式agent.transfer-profile，旧入口自身交接，平台自动后继，实际随机资产读回、单次正常Message/ACK、新入口自身cp/stop。已准备tools/prepare_transfer.py供继续审查，尚未执行；不以直接CLI问答、默认替代模型或重建入口补证。本次已完成历史与失败证据保持不变，后续另加文件/版本归档。
