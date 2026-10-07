# M 组正常旅程最终复核

2026-10-06（Asia/Shanghai），gpt-6.1-sol / high。只读当前执行报告/检查点、M 组必要证据及实例原始 runtime.jsonl/操作回执/共享 Git；R 组结论直接复用。未重跑、调用被测模型、启动服务、改源码或执行方文件。

## 结论

认可主报告的限定结论：真实两实例通信往返、双方自身 receive/ACK、同 Codex 承接 R 组交接并回读资产已取得 PASS_REAL 证据；HY 跨 Harness 业务接手为登录条件 BLOCKED，最终运行器已停止但 HY Binding 执行资格保留。未发现影响上述结论的重要偏差，无需追加测试或修复。

## 核对依据

1. **消息与 ACK。** 两个实例的原始 runtime.jsonl 共记录一次成功 alpha message.send（m-e2e-luna-request-001）、一次 beta message.receive 和一次成功 beta reply send（m-e2e-luna-reply-001）、一次 alpha message.receive。回复引用原请求 ID。实际 Git main:messages 只有这两条消息；两 ACK 操作回执均 published，receiver/binding 分别为 beta/b99b412cfc3794314a231f5090250ac1f 与 alpha/b89818d3a91bf4545b646a68571aaf6b8，并与真实原生工具返回一致。不是控制者代收或口头确认；本轮是明确输入下的主动 receive，不升级为 Watch 自动推送已验证。
2. **真实同 Codex 接手。** M04 新 Binding b89818d3a91bf4545b646a68571aaf6b8/native thread 01a10d58-3ea5-7753-9956-10acbe8f175b 与 R 组入口不同。共享 Git Binding 的 handoff 指向 R 组 hdd3cb0600def4dc6874145a6f5db8385；M04 实际 boot 带旧检查点 caf0b25b7b708492d8765c94c21b1ddd3 与其内容。新原生 turn 01a10d58-5b17-7183-8701-691d11eb2758 成功 asset.read 旧 notes/result.md，标记和 hash 与 R 组相同，并成功 checkpoint.create 得到 c5f7451ea85324705a183fd4bae1e2358。因此认可已接手并继续任务，不仅是存在交接记录，也不声称另行执行过 checkpoint.show。
3. **轮次。** 独立扫描 alpha/beta 全部现有 runtime.jsonl：R alpha 2 started/2 completed；M alpha Luna 2/2，beta Luna 2/2；累计 Codex 6/6，与原始事件、model-budget.json 的 2 Sol + 4 Luna 一致，没有发现额外原生 turn。HY 只有唯一 local_submission_id s0b8479d871e943afb628c2277efa3a68、一个错误 ResultMessage；WinError193 的 JS 连接前置失败未发送 query，不计另一次模型提交。SDK num_turns=2 不等于两次成功模型执行。7/8 是保守请求预留；费用无独立账单，原生 turn 也不是精确模型 API 请求次数。
4. **HY 阻塞与停止边界。** 原始 SDK 记录模型为 hunyuan-2.0-instruct-ioa，真实 Session 01a10d5f-f98b-7300-a6f0-b73b738b5ed2 返回 Authentication required /login，ResultMessage.error_during_execution/is_error=true，报告 tokens/cost 为 0。只能确定这个 SDK 自带原生入口目前要求登录，不能泛化为 WorkBuddy Desktop 未登录、HY 服务或该模型永久不支持；无业务工具/资产接手证据。M17 runtime.stop 明确 execution_right_released=false，M18 alpha current=b75712931632c4f8da3a948ca9cb395f6、Binding.phase=active、runtime.monitor_stopped/entry_still_owned=true/runner_alive=false；M12 的两个 Luna 入口则已 released。报告准确保留这一区别，不能写成所有资格正常释放。
5. **现场与限制。** M19 记录三个本批 Runner 均退出、36108 无监听，独立表单启动器/服务保留；这是记录时事实，不是整个正式根零进程。源码 HEAD 仍指定基线，status 仅用户规程未跟踪；M03 配置回执 global_configuration_changed=false，选中 SDK 仅在独立 codebuddy-app 安装，未见本批为验收改产品/全局配置的证据。本次未访问私有全局认证资产做审计。实际 R 输入 e2e-alpha-second-stop-001 仍 submitted；M stop 输入状态亦按原记录保留。现有完成副作用不能因账本未收口而自动重放。

## 收口

不重放历史或 HY 请求，不删除锁/Binding，不伪造 owner stop、检查点或账本 completed。HY 继续需要解决该原生入口的真实登录，并由产品合同判断原资格恢复；此处不提供强制接管办法或擅自执行。普通 TTY/Desktop、Watch、其他边界/故障/远端能力继续按未测范围保留。执行主报告已把 R 历史与 M 当前状态明确区分，可直接采用现有限定结论。本复核结束，不持续轮询。
