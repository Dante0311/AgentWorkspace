# 正常真实旅程结果复核

2026-10-06（Asia/Shanghai），gpt-6.1-sol / high。仅复核收口后的 reports/E2E-REPORT.md、reports/CHECKPOINT.md 和必要原始证据/测试资产；未重跑测试、调用模型、启动服务、改产品或执行方文件。

## 结论

认可主报告对“受管 Codex 同会话两轮正常业务执行、文件读写/回读、真实检查点/Git 保存、owner stop、无模型健康巡检”的 PASS_REAL 范围；没有发现需要改写这些业务结果的重要问题。

输入账本收口尚不一致：第二输入仍 submitted，不可认定平台输入状态完整闭环已通过。主报告已将业务执行与该限制分开，保留根因未知和禁止重放，口径准确。普通真实 TTY/Desktop、Message/ACK、后继接手、跨 Harness 均未由本轮证明；主报告的 BLOCKED/NOT_RUN 区分符合实际范围。两轮是两个原生 turn，不代表仅发生两次模型 API 请求，费用未独立观测。

## 关键证据

- R13-final-runtime 的 turn/started 与 turn/completed 成对出现：同一个 thread 01a10d4c-1d08-78d2-b234-4a3832669356，turn 01a10d4c-3982-7711-8f46-067827ec9089 和 01a10d4e-19b4-7032-8c1f-a54d97b10a40 均 completed、error=null；成功动态工具事件记录第一轮 asset.read/write/read、checkpoint.create，以及第二轮回读、checkpoint.create、agent.stop。支持真实两轮执行，未借模型口头回答替代副作用。
- 直接读取实际 notes/result.md，随机标记一致，实算 SHA256 为 207c643a6d338891f16460ec3ef0f38b41f81dddd107386bd5928ba6e830d2a3，与工具返回和报告相同。两检查点文件 c1734abfa27974d11acf36f53d27c7147、caf0b25b7b708492d8765c94c21b1ddd3 实际存在，内容对应两轮。
- 只读检查测试 Git 仓 data/workspace.git：8270672e454e088019cc5ed8caaca87695af48ec 与 523ff305c37781c442495c781336c9d375f0f37f 均为实际 Checkpoint 提交，与原生工具返回 revision 相同；第一提交内 notes/result.md 标记一致，第二提交内对应检查点存在。支持文件与 Git 保存事实。
- agent.stop 在第二 turn 内成功返回 awaiting_native_idle；之后 R12-alpha-final-show 退出 0，current=null、binding=null、runtime.state=released、runner_alive=false、watch.disabled。R13 状态为同一 Binding bdd3cb0600def4dc6874145a6f5db8385 的 released，存在 handoff hdd3cb0600def4dc6874145a6f5db8385。可认定 owner stop 已完成，不能把 handoff 记录当成新端接手已完成。
- 实际 .aw-local/inputs/e2e-alpha-second-stop-001.json 与 R13 都保留 state=submitted、原 turn ID、旧响应 inProgress；事件却证明该 ID 已 completed，并已创建检查点/调用 stop。故“状态不一致”有直接证据，“不重放”合理；没有足够依据认定具体原因，也没有修改账本或源码将其变绿。
- R11-health-cycle-one/R12-health-cycle-two 的同计划 last_run 为 02:23:04 与 02:23:36，均 checked/healthy、issues=[]、覆盖五实例、notify=false；R12-health-disable 明确 enabled=false。三个管家及 beta 实例均无 runtime status/records，最终 DOM 未绑定，R06-selected-route 记未启动管家；支持正常程序巡检、没有运行管家模型的限定结论，不支持异常通知/维修已验证。
- model-budget.json 记录最多/预留 2 turn、控制器自动重试 0，与最终两 turn 相符。报告保留模型内部错误工具尝试，因此“零控制器重试”没有被误写成全程无错误。
- R04-workbench-stop 记录本轮工作台进程树定向终止；R14 02:27:09 观测无工作台监听，保留收集表单启动器 PID191596、intake_process_alive=true。主报告正确说明它不是模型 Runner，没有宣称整个正式根零进程，也没有把定向终止称为优雅退出。本次未重查实时进程，认可的是记录时状态。

## 收口

本次结论无需新增测试或扩大根因审查。保留第二输入状态问题、原 ID 和所有副作用，不重放。2/2 轮已使用后停止新增模型任务；若以后接续，由 Lead 在新的明确范围/预算下派发。未补原规程故障与边界矩阵，符合用户已缩到正常真实旅程的要求。
