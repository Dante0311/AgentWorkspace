# SBP Ops 最小模拟场景

这是隔离的虚构导航导出任务，不运行 SBP、UE 或 CI。唯一工作目录在本次 E2E 根下；不会读取生产归档。标准库驱动不调用模型、不连接企微。

只读来源已确认是 SVN `branches/ft_sbp_test_3/Sources/Tools/SceneBuildPipeline` 的本地工作副本，根目录 `svn info` 为 r1067288；这不等于远端最新版本或所有文件同 revision。参考 Operation/Event 字段、Stage/Job 的 success/failed 状态及归档证据定位方式。这里只提供标明 `simulation:true` 的代表性事实，未调用 SBP 序列化器或声称完整 schema 兼容。所有 build、job、输入和日志均为虚构数据。

过程只有一条：启动 → 已处理一个输入 → 因 `inputs/tile-B.txt` 缺失失败 → 再次观察仍是同一失败 → 经明确授权创建缺失文件 → 新 Build 重跑成功，实际产生 `navigation-export.txt`。失败 Build 和成功 Build 分开归档，保留原失败日志。修复只创建一份测试输入；undo 先核对修复内容 hash，再删除该文件，保留全部历史和成功产物。

## 已完成的驱动检查

`runs/driver-check-final/check-result.json` 是最终零模型、零外发检查：实际失败日志指出缺失文件，实际修复后产物内容匹配，失败和恢复各生成一个事件，两次重复观察未新增事件，修复已撤销。补充由 Agent 写文件后的修复记录保存逻辑后，重跑了同一检查；初次记录保留在 driver-check-01。此检查证明本场景驱动，不证明实际 Agent 调查/去重、AW Bridge 接入或企微收发。

## 操作

在隔离安装的 Python 下执行 `scenario.py ACTION --run-dir DIRECTORY`。DIRECTORY 必须位于本 E2E 根下，prepare/check 要求新目录：

- `prepare` 创建虚构输入并执行失败的第一轮；`observe` 生成待投递事件，再观察同一状态不新增事件。
- `repair` 创建缺失输入；`resume` 重新执行并保存成功归档；`undo` 撤销未被改动的修复文件。
- `bridge` 是供后续显式启用的 AW custom Bridge：stdout 使用既有 ready/input/sent JSONL 合同，stdin 只接受发到 simulation-outbox 的 send。它在事实失败时生成实际 input，发现授权修复文件后实际重跑并生成恢复 input。普通启动/进度写入事实，不消耗额外模型轮次。EOF 退出，没有自建后台服务。

Bridge 不接受修复指令，也不能扩大 Agent 权限。后续如授权实际 Agent 修复，先把新场景放进该实例根下，例如 `scenario/sbp-ops/`，让 Agent 在正常工具权限下仅写 `inputs/tile-B.txt`，内容为 `fictional navigation tile B` 加换行。驱动核对内容后才重新执行。未授权时只读日志、给出诊断。

Bridge 重启会重放已经保存的同 ID 事件，让 AW 使用现有 request ID 去重。驱动本身不提供通用可靠消息事务或队列；这一真实接入、重启与 Agent 行为尚未验证。simulation-outbox 只保存本地 JSONL，sent 回执明确 external_delivery=false，绝不能算企微送达。

## 准备时的后续建议（历史，真实执行结果以报告为准）

保持旧 alpha HY 资格不动，后续仅在已 released 的测试实例准备场景。最多新增 6 次 `gpt-6-luna/low`：初始化 1 次、事实驱动的失败调查 1 次、明确授权修复 1 次、事实驱动的成功收口 1 次、正常保存检查点/停止 1 次，另 1 次留给必要收口；不自动重试或升档。检查 Agent 实际读日志、诊断缺失文件、授权前未修复、授权后真实写文件、重复失败无新调查、真实产物与正常停止，不用自然语言答复代替副作用证据。

企微长连接保持独立的真实渠道验证：专用 Bot、仅用户所在 E2E_TEST_GROUP 群、最多 20 条外发仍是既有边界。此前误填 Webhook 已安全保存，不是 chatid；精确 chatid 未确认前不启用企微、不读取凭据、不发消息。如何拿到目标由 Lead 安排一次最小手动步骤。本场景准备不授权剩余模型轮次或企微发送。

现有 A–J/R/M 证据原样保留；准备阶段仅是业务场景准备，不能据此表述为完整 E2E、Desktop、生产 SBP 或企微通过。

2026-10-07执行更新：限定场景已完成真实AW/Luna/企微业务链，累计6轮、2条真实群消息且用户确认可见；细节见[最终报告](../../reports/E2E-REPORT.md)。最后一轮任务错误要求模型读取受保护.aw-local回执，导致模型自身停工未完成，随后按明确既有授权由管理端公开checkpoint/stop正常收尾，不当作同等的模型自停证据。跨入口恢复时使用observe_recovery.py，仅观察现有场景的新恢复，避免默认bridge重放旧Binding失败ID；不重写历史、不修改产品，也不宣称通用跨Binding回放已验证。
