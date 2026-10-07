执行补充：本方案已按Lead授权完成，证据编号T；4轮、2消息、2ACK，结果及偏差见canonical报告/T15。没有后续自动任务。

### P独立复核与E2E-004（2026-10-07补充）

[P独立复核](../review/P-NORMAL-REVIEW.md)认可W/P限定业务和副作用证明，同时确认P2终态缺陷；Lead已在主仓登记E2E-004，执行方未改主仓。公共completed只在target仍active时计算，未保存，后继释放后回退starting；源码可确定后续新transfer会被旧未解决记录阻挡，该后果未另行实测。没有证据表明会重复启动，不据此推断自动重复行为。

beta旧transfer记录原样保留：不advance、不重试、不删记录/锁、不新transfer刷状态。已只读核对runtime.start：正常无current的start走sync/reserve/spawn_runner，不调用transfer.request/advance；Runner退出也只有当前binding等于旧transfer.old_binding时才推进该记录。因此后续Watch建议的普通新start从源码看不依赖旧transfer终态。这是代码判断，新的正常启动尚未实测；若真实执行遇阻碍，先保存事实，不绕过。

Q1/Q2均已收口，结果不因该复核改变。下一段Watch仅有建议与准备，尚未启动模型或发送消息。

# 下一段建议：两个normal消息的Watch自动唤醒与有序处理

2026-10-07，仅准备，模型0、消息0。文件名R-WATCH区分历史R最小真实模型批次，本段未开始。沿用现有覆盖表：M已经证明真实双方主动send/receive/ACK及回复，P证明真实外部企微自动续接，Q证明Fork静态数据合同；此段只补内部Message Watch与normal有序处理，并顺带取得Fork真实新会话的证据。

建议复用e2e-beta接收者、e2e-q-fork发送者；不新建身份、不用alpha旧HY、不启动管家/Work业务/企微/模拟观察器。两端仍官方登录Codex、gpt-6-luna/low。执行前各自任务AGENTS归档并CAS替换为这段明确临时职责，保持七Skill和真实来源历史；管理端为Fork配置已有实际Codex入口，但不改全局配置。来源P/Q资产和已交付Work保留。

预计4个真实原生轮次：

1. beta正常start，从现有P检查点进入，同一当前任务只记录待收两条通知，然后等待。Watch暂关闭。正常boot计一轮，不由控制者代receive或ACK。
2. Fork正常start，真实新Binding/session确认其新身份与来源，实际读Q核对资产；自身顺序发送两条normal Message给beta，使用全新固定request ID `r-watch-normal-001`、`r-watch-normal-002`，第二条message_refs引用第一条。正文是明确测试业务，例如两段虚构交接记录的“记录第一段”“补上第二段”，不安排构建/生产。发送者自己保存结果/checkpoint、正常stop。两条消息published和目标资格实际核对后再启用接收Watch，不需要外部用户交互。
3. 管理端用正常公开message.watch start启用beta（interval=1秒，非新增后台服务）。Runner自动通知第一条。beta亲自message.receive该ID发布ACK，再保存第一段记录；不提前主动receive第二条，不关闭Watch，不stop，结束这一轮。控制者只读实际共享dispatch/ACK和native事件。
4. Runner在第一轮结束后自动通知第二条；beta同一session/Binding自身receive/ACK，读回第一段记录、追加第二段，保存真实顺序结果/checkpoint、正常stop。产品stop自动关闭Watch；控制者核对两原生turn顺序、两消息/ACK、唯一session、真实释放和全部本轮进程退出。

公开源码已核对：Messages.poll选未ACK队头；normal且native busy返回waiting_idle，不steer；共享dispatch绑定当前Binding，通知不是授权；成功receive才有ACK。Watch默认通知间隔与重试参数不更改。原生轮次全部计入，不把自动输入当免费；模型所需正常收尾按实际必要动作完成，不升档/重跑业务。

正常观察中尝试记录第二条待队列且第一条仍busy时的waiting_idle，再结合第一turn completed在第二turn started之前的事件。如果未捕获busy窗口，只能证明正常顺序投递，不能声称已实测busy等待；不为捕获状态加模型sleep、生产钩子或人为延长业务。两条在Watch开启前发布，自然形成队列，不属于故障注入。

收口证据：Fork真实session/Binding与boot材料实际读取（补Q静态Fork未覆盖的relay）；消息原始ID、from/to/normal、publication receipts；Runner自动通知dispatch与对应turn；双方自身工具行为、ACK发布资格；接收者同会话两轮实际顺序记录；两端model checkpoint/stop和完整退出。不会因为没有回复消息重跑M既有往返；本段目标是自动顺序消费。

风险：先只读确认beta/Fork均无有效入口、两条ID未占用、无更早未ACK队头、Watch/所有Bridge关闭。若存在历史队头或未知结果，保留事实，不跳队/改ID/重放。若模型忘记ACK或提前stop导致等待，关闭本轮新触发并保存现场，按真实状态决定必要正常收尾；不能代ACK刷通过。E2E-001仍可能让stop输入账本submitted，保存native终态与释放证据，不改账本。两个真实实例启动会自然加载各自原生配置，不能把该结果外推Desktop或跨Harness。

预计新增模型4轮、内部Message2条、企微外发0、服务0。上述为供Lead内部核对的具体范围，尚未配置/启动/发送/开启Watch。管家受限授权与有限维修仍另段决定，不夹带执行。
