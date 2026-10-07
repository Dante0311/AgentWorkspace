# W/P 组正常旅程最终复核

2026-10-07（Asia/Shanghai），gpt-6.1-sol / high。固定产品基线 1258b622c474beb73f13234c0f00672d8d5b5bbb。R/M 结论沿用已有复核；本次只读新增 W/P 证据、必要实例事实及 transfer 状态链路，未重跑、调用模型、发送消息、启动服务、改产品或执行方文件。

## 结论

认可 W/P 的限定真实旅程证据：W 完成真实企微授权下的虚构 tile-B 修复、模拟重跑和可见恢复回复；P 完成产品自动交接、同配置企微续接、真实用户查询进入唯一后继、旧产物回读及群回复，并由后继本人读取公开发送回执、保存检查点和正常停工。

W 最后收尾是管理端清理，不能记为模型自行停工。P 的业务交接和停工成功不代表 transfer 状态正确：确认一项新增 P2 产品缺陷，完成状态只在读取时计算、未持久化，后继释放后公共状态从 completed 回退 starting。后续新 transfer 被旧未解决记录阻挡是源码可确定的后果，未额外执行请求验证。没有证据表明它会自动重复启动后继。

## W 的证据和边界

- W18-final-facts.json 与 W16-business-chain-proof.json 记录真实企微授权事件 87061719af64e13b06b1e5b7d3582ba5，内容明确同意修复模拟 tile-B。授权和恢复输入进入真实原生 turn 并完成；六个原生 turn 均 started/completed，两个企微发送均取得提供方成功回执及人工可见确认。
- 修复仅涉及隔离虚构场景。失败归档保留，模拟执行产生失败和恢复两条事件；恢复产物包含 tile A、tile B。本复核直接读取 sim-build-2/navigation-export.txt，SHA256 为 2ff4deccf19bcc95d68f8f048148578841e539999a3c73aa0535ddf3ee276c7b，与 P 原生回读内容一致。不能把模拟成功升级为 UE、真实 CI 或生产业务验证。
- 最后一轮测试指令误让模型读受保护的 .aw-local 回执，访问被拒绝，因此 model_self_stop_completed=false。W18 的最终管理端清理覆盖 W16 尚待清理的历史状态；当前资格释放、运行器停止不等于模型完成了自己的停工链路。这是测试指令边界，不能据此认定产品自停缺陷。未追加第七轮。
- 保留此前撤回的入站故障推断，不从旧观察记录推断离线重放；接收型模拟 fixture 的限制也不泛化为产品通用能力结论。

## P 的真实副作用

1. **产品自动接手。** P06 的正常 transfer-profile 请求 p-beta-normal-transfer-001 返回 handoff_requested，原 Binding ba97e52906d19449b8313aa9c053f57b7，预定唯一后继 b4c8d06c2c2b846dd8cede789542b13b3。原模型实际 checkpoint.create 得到 cf9b87354efef429c8b4df26a15eb38ae（revision d47d006a03b8f7f6cbe2f770ae806d83ecd99b2b），随后 agent.stop 引用该检查点，返回 awaiting_native_idle。runtime.py 的原运行器释放后 advance 路径与随后新 Binding 的原生启动吻合；证据中没有控制者手工 start 后继或替代模型 checkpoint/stop。P14 原始事件只出现这两个 Binding，合计五个 gpt-6-luna/low 原生 turn，started/completed 为 5/5；turn 数不等于精确模型 API 次数或费用。
2. **后继实际读取交接和资产。** 后继 native thread 01a11207-e5fd-7790-9bc5-4a68dd05a153 的 boot turn 成功读取原检查点 JSON、notes/p-continuation-ba97e52906d19449b8313aa9c053f57b7.md，以及 sim-build-2 的操作记录、job_summary、navigation-export 和既有结果笔记。这是工具返回和旧产物证据，不仅是启动提示词或自然语言声称继承。
3. **同配置企微自动续接。** 原端和后继的 ready 记录使用相同 generation gefc2a448231a453499f4fb46f80bf95a，分别对应旧 PID 260180、新 PID 219092，时间为 00:22:57 和 00:24:41（+08）。没有后继手工渠道重配或重启证据。P07 旧进程审计 23 条、alive_count=0。sim-build 在 P 期间保持 disabled，旧 ready 字段是历史状态；不能将其误记为新模拟连接或跨 Binding 新模拟事件。
4. **真实用户消息和回复。** 企微事件 b2d2731ee2919eaf6a965dcf53174946 请求核对上次模拟导航导出结果；它生成输入 ia066e81877d136b7f5bbf42e6876df41822cc53f，进入后继查询 turn 01a1120a-2cfe-72f2-8e91-3a0573e23779 并完成。该 turn 实际回读上述旧产物，bridge.send 使用 p-ops-result-query-reply-001。queued 本身不是已发送；随后回执 state=sent、errcode=0、Binding 为该后继。P17 保存经 Lead 转述的用户确认“已看到结果核对回复”，并声明没有控制者代发；这是人工可见确认，区别于提供方接受回执，本复核没有自行登录群独立观察。
5. **模型本人收尾。** P11 验证公开 channels/wecom/sent/p-ops-result-query-reply-001.json 可经 asset.read 读取。后继最后的真实 turn 再次读取同一公开回执，确认 sent/errcode=0，关闭 wecom 与 sim-build，checkpoint.create 得到 c3788071b0e70473aa054a218b12688eb（revision 36da4bc44cc714f5c442925d57814f3c46af60b3），随后 agent.stop 引用它，返回 awaiting_native_idle。P15 agent show 最终 current=null、binding=null、state=released、runner_alive=false；P14 后继进程审计 25 条、alive_count=0。P18 management_checkpoint_or_stop=false。因此 P 的最终停工有完整后继模型副作用链，不能与 W 管理端清理混记。

P 未增加模拟事件或生产调用，只增加一次真实企微结果回复。旧 handoff 输入和后继 cleanup 输入仍 submitted，而对应 native turn 及停工副作用已完成，这是既有 E2E-001 账本问题的再次表现；保留原状态，不编辑或重放。

## 新增确定缺陷：完成 transfer 未持久化，后继释放后回退 starting（P2）

**触发条件与观测。** 正常自动路径完成后继启动和 boot 检查点，目标仍 current 时读取状态；之后目标正常停工释放，其间没有显式 advance 保存完成记录。P09 transfer-status 返回 completed；P14 快照和直接读取实例 .aw-local/transfer.json 仍为 starting；P15 目标 current=null 后 transfer-status 返回 starting。这不是未知结果或停工失败，而是已完成事务的终态回退。

**源码依据。** 开发仓与正式安装的 transfer.py SHA256 相同：4c32a128b9f6c455a79c07b181b145287c43cea9ec2cd2c18bb941065a031a5f。

- src/agent_workspace/transfer.py:128-135 的 status 仅在 current==target 时 return observed_target(...)，没有 write_json。observed_target 在目标 active 且 boot.checkpoint_revision 存在时计算 completed（117-126）。目标释放后条件不再成立，status 原样返回持久 starting。
- advance 在启动返回后写入 starting（112-113），在目标仍 current 时才会把 observed_target 结果写回（87-91）。src/agent_workspace/runtime.py:366-369 的自动 advance 由旧运行器释放后触发；未见目标完成 boot 后自动保存 transfer 完成记录的路径。
- request 在读到非 completed 旧记录时调用 status，再以旧记录未完成为由拒绝新请求（45-53）。因此后继已释放后，新的 request id 会被“Another transfer is unresolved”阻挡；这是沿源码得出的影响，未为复核新增模型或 transfer 请求。

**影响和证据范围。** 公共状态错误地显示未完成，丢失完成时计算出的 session，并阻碍后续正常 transfer。continue 路径另有旧交接检查和 launching/starting/outcome_unknown 的防替代启动约束（94-99）；不能从状态回退直接推论自动重复创建后继。建议产品修复保证已证实的完成终态持久且不随 current 变化消失，具体实现由负责人决定；本复核不改产品、不用手改状态掩盖问题。

## 收口

本次只写 review/P-NORMAL-REVIEW.md 与 review/CHECKPOINT.md。源码 HEAD 未变；当前 docs/implementation.md 修改属于 Lead 的问题登记，未跟踪 docs/AgentWorkspace-local-E2E-prompt.md 属于既有用户规程，均未修改或暂存。R/M 的既有限制、HY 原资格未释放和 E2E-001 保留；P beta 的最终释放不能泛化为所有历史实例已释放。真实 Desktop/TTY、跨 Harness 成功接手、生产 UE/CI 等未获新增证明。无需为上述限定旅程重复测试；本轮复核结束，不持续轮询或跨聊发信。
