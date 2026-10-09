# 通过 GitHub 工具继续进入 workbench：本轮执行说明

这份说明用于已经创建、尚未进入的 aw-team/workbench。它给执行会话实际读写步骤，不要求安装或调用 aw。

本轮用户已同意按 AW 操作规则直接使用 GitHub，并允许手动入口缺少原生会话 ID。本轮仅对 kind=manual 使用 session=null：Binding 是 AW 自己的操作入口标识，不冒充 ChatGPT/Codex 的原生会话 ID。现有 0.1.0a1 的 agent.bind 命令仍要求真实 Session ID；本文是经用户选择的协议扩展试验，不表示该命令、工作台和自动运行器已经更新。

**本次执行到第 4 节结束：进入、初始检查点、向 Lead 发布一条消息。第 5、6 节是后续说明，收到用户继续指令再执行。**

## 0. 固定对象、前提与本轮标识

- 协作仓：Dante0311/AW-Workspace。
- Workspace 别名：aw-team。消息中的 workspace 字段必须使用 main:workspace.json 的 locator。
- 目标实例：workbench；实例分支：instance/workbench。
- 唯一消息对端：lead。不要操作其他实例的状态或发送外部消息。
- 已验收的创建快照：6fcad5f267f2d40e17cab7ca66ef378abed1a524。
- 已验收的登记提交：18a986bb1a1cfb20b0e7a45f8cb4f5c056862ca5。
- 后续操作必须读取当前远端版本；以上两项用于追溯，不是强制把分支退回旧版本。

先读取当前 main 的 workspace.json、agents/workbench.json、agents/lead.json，以及当前实例分支的 AGENTS.md、source.json、.aw/identity.json。核对身份和目标，保留原有文件。

首次执行预期 workbench 为 archived=false、current=null、has_run=false、handoff=null。若状态已变化，先说明并核对，不覆盖、不自行清空。只有本会话已有真实工具记录证明是自己的本轮操作，才能续接；不能读取一个现成的 Binding 后直接冒充其拥有者。

为本轮一次性选择并记下：
- B：以 b 开头的唯一 Binding ID。
- C：以 c 开头的唯一检查点 ID。
- M：以 m 开头的唯一消息 ID。
- T：实际操作时的 UTC ISO 8601 时间。

ID 只用 1–64 个字母、数字、下划线或短横线。不要把这些 ID 当作原生 Session ID。失败或结果未知时沿用本轮原 ID，先核对远端实际结果，不生成另一套 ID 重做。

## 1. 所有写入共用的方法

下面的工具名是功能后缀，使用当前会话实际提供的对应 GitHub 工具。全部操作只针对上述协作仓。

1. 用 github_fetch 读取目标分支：
   - main：GET https://api.github.com/repos/Dante0311/AW-Workspace/git/ref/heads/main
   - 实例分支：GET https://api.github.com/repos/Dante0311/AW-Workspace/git/ref/heads/instance/workbench
   记下 object.sha 为 H。
2. 用 github_fetch 读取 GET https://api.github.com/repos/Dante0311/AW-Workspace/git/commits/H，取得 tree.sha 为 TREE。
3. 用 github_fetch_file 按 ref=H 读取本步需要检查的文件。检查不能使用混合版本。
4. 用 github_create_tree，以 base_tree_sha=TREE 保留整棵原树，只列出本步实际改变的路径。文本文件使用如下条目：
   ~~~json
   {"path":"本步路径","mode":"100644","type":"blob","content":"完整 UTF-8 文本"}
   ~~~
5. 用 github_create_commit，以 parent_sha=H、tree_sha=新树 SHA 创建提交 NEW。
6. 用 github_update_ref，以 branch_name=目标分支、sha=NEW、expected_sha=H、force=false 发布。
7. 读回分支和相关文件，确认 NEW 已成为分支历史的一部分，且内容正确。远端已经前进时，核对 NEW 是否已发布，不把正常的后续提交误判为本次失败。

JSON 用 UTF-8、两个空格缩进、末尾一个换行；同一不可变记录补写时保留原字段顺序和文本。

版本冲突时，重新读取分支并重新检查本步前提，再基于新版本制作提交。不得 force push。若调用结果未知，先检查分支、原 ID 对应记录及原提交，无法确定则报告已有事实并停止本步。

同一步里需要共同成立的多个文件必须放在同一个 tree/commit 中，不能逐个 create_file 造成半份登记。首次新增路径必须确认不存在；已存在且内容完全相同视为已完成，内容不同则停止，不覆盖不可变记录。

## 2. 进入当前手动入口

### 2.1 预留入口

在同一个 main 快照检查 workbench 满足第 0 节的首次执行前提，且 bindings/B.json 不存在。

一次提交同时完成：

1. 新增 bindings/B.json：
   ~~~json
   {
     "id": "<B>",
     "agent": "workbench",
     "kind": "manual",
     "phase": "starting",
     "session": null,
     "created_at": "<本步实际 UTC 时间>",
     "handoff": null
   }
   ~~~
2. 读取并保留 agents/workbench.json 的全部原字段，只改：
   ~~~json
   {
     "current": "<B>",
     "has_run": true,
     "handoff": null
   }
   ~~~

上面的第二段是修改字段集合，不能用它替换整个 agents/workbench.json。

发布后读回两份记录。它们同时存在且对应 B，才算预留完成。此时还没有取得 active 操作资格。

### 2.2 确认当前会话进入

重新读取 main，确认：
- workbench.current == B，且实例未归档；
- bindings/B.json 的 agent、id、kind 正确，phase == starting；
- B 确实是本会话在本轮选择并预留的入口。

将同一份 bindings/B.json 的 phase 改为 active，其他字段保持不变，按第 1 节提交并读回。

本轮 session 保持 null，不生成 sessions/manual/* 索引，不填写虚构原生 ID。对外报告“当前会话已登记为手动操作入口；原生会话 ID 不可获取”，不能报告“已由原生平台核验会话”或“自动推送已启用”。

以后每次发消息、确认通知、发布检查点和交出前，都重新确认 main 中 current == B、绑定属于 workbench 且 phase 允许当前操作。换了入口后，旧会话不能继续写。

## 3. 保存初始资料和检查点

确认 B 仍 active，然后读取当前 instance/workbench 分支。

一次实例分支提交新增：
1. notes/startup.json：记录实际采用的职责来源、B、C、M、当前工具、session=null 的事实、已完成步骤和尚未验证事项。不要保存凭据、机器路径或私有会话全文。
2. .aw/checkpoints/C.json：
   ~~~json
   {
     "id": "<C>",
     "created_at": "<本步实际 UTC 时间>",
     "summary": "Workbench 已按 GitHub 手动操作方式进入；原生会话 ID 不可获取。",
     "content": "已读取职责并登记手动入口；本检查点保存实例 Git 资产，不包含原生会话历史。测试消息尚待发送。",
     "record_refs": [],
     "scope": "Instance Git assets only; native conversation export unavailable."
   }
   ~~~

保留原 AGENTS.md、source.json、.aw/creation.json、全部技能及其他资产。创建记录保持最初内容，不随运行状态改写。

记下此次实例提交的实际 SHA 为 R。重新读取 main 并确认 B 仍 active，然后新增 checkpoints/workbench/C.json：

~~~json
{
  "id": "<C>",
  "agent": "workbench",
  "revision": "<R>",
  "path": ".aw/checkpoints/<C>.json",
  "created_at": "<检查点正文中同一个时间>",
  "excluded": []
}
~~~

本轮仅保存 Git 分支现有文件，excluded=[] 不代表导出了本机或原生会话内容。正文已经说明保存范围。

读回指针，再按指针中的 revision=R 读取检查点正文和 notes/startup.json，确认一致。普通实例提交只有完成这份共享登记后才计作本轮已发布检查点。

如果实例提交成功而 main 登记失败，保留原 C、R 和正文，只补同一指针；不重新生成检查点或混入后来文件。找不回确定的 R 时先报告，不拿当前 HEAD 猜测代替。

## 4. 向 Lead 发布一条测试消息，然后结束本轮

重新读取 main，确认 B 仍 active、lead 存在且未归档，并读取 workspace.json 的真实 locator。

在同一份 main 提交中新增以下两份记录。

messages/M.json：

~~~json
{
  "id": "<M>",
  "from": {"workspace": "<真实 locator>", "agent": "workbench"},
  "to": {"workspace": "<真实 locator>", "agent": "lead"},
  "created_at": "<本步实际 UTC 时间>",
  "message_refs": [],
  "delivery": "normal",
  "content": "Workbench 已完成本轮 GitHub 手动进入。Binding=<B>，checkpoint=<C>，instance revision=<R>，原生 Session ID 不可获取。请用 AW 读取本消息和检查点，回复本消息以验证两种操作方式互通。"
}
~~~

message-index/M.json：

~~~json
{
  "id": "<M>",
  "from": {"workspace": "<同一个真实 locator>", "agent": "workbench"},
  "to": {"workspace": "<同一个真实 locator>", "agent": "lead"},
  "created_at": "<与消息正文相同的时间>",
  "delivery": "normal"
}
~~~

消息内容中的 B/C/R 用本轮实际结果替换。消息已存在时不覆盖、不改正文。不要替 Lead 创建 acks/M.json。

读回两份记录，确认本轮消息发布结果。然后返回 B、C、R、M、各次实际提交和链接，说明 session=null、尚未取得 Lead 回复，结束本轮等待用户继续。不轮询，不重发，不自动 handoff。

## 5. 后续收到用户“继续收件”指令时

在同一个 main 快照确认 B 仍 active。查 message-index 中 to 为本 Workspace/workbench 的未确认消息，按 created_at、id 顺序处理；只处理本轮 Lead 回复，不自行开展其他业务。

先检查索引确实指向 workbench，再尝试读取 messages/回复ID.json。实际结果需如实记录，包括正文读取失败。随后重新确认入口资格，新增单字段确认：

~~~json
{"message_id": "<实际回复消息 ID>"}
~~~

保存到 acks/回复ID.json，按第 1 节提交并读回。已存在同一确认则不重复处理；需要回看正文只读即可。ACK 只表示确认通知，不表示业务完成。

如已有消息但没有实际尝试读取，不能先写 ACK。保留回复对原消息的 message_refs，以及真实处理事实；必要时按第 3 节创建新的检查点，旧检查点不可修改。

## 6. 后续用户安排交出和新会话接手时

这一节不能提前执行，也不能由旧会话自行扮演后继。

1. 保存交接资料并发布新的检查点 C2/R2。
2. 确认 current == B、phase == active；更新 bindings/B.json 为 phase=stopping，增加 checkpoint=C2、stop_requested_at=实际时间，然后结束当前轮次。
3. 仅在用户明确确认旧会话已经停工后，才发布释放；不能把普通回复结束、超时或窗口关闭当成自动停工观测。
4. 手动确认后的同一 main 提交同时完成：
   - agents/workbench.json：current=null、handoff=H，保留 has_run=true 和其他字段；
   - bindings/B.json：phase=released、stopped_at=实际时间，保留检查点和原始字段；
   - handoffs/H.json：id=H、agent=workbench、entry=B、checkpoint=C2、created_at=实际时间、consumed_by=null。
   H 按现有规则取 "h" + B 去掉第一个字符后的内容。
5. 用户打开另一个真实会话，提供本说明、实例地址和交接点。新会话选择新 Binding B2。
6. 新会话在同一个 main 快照检查 current=null、has_run=true、handoff=H，H 指向 workbench 和可读检查点，且 consumed_by=null。一次条件提交将 H.consumed_by=B2、实例 current=B2/handoff=null，并新增 phase=starting、handoff=H 的 manual Binding B2。之后按第 2.2 节激活 B2。
7. 新会话按固定检查点读取原资产，完成一次新的消息往返。旧会话不得继续使用 B。

这才构成跨会话手动接手续验；不代表自动创建、自动唤醒或平台观察原生停工已经实现。

## 本轮证据范围

本说明配套的 verify_protocol.py 只在临时的本地 Git 仓中构造协议记录，并让现有 AW 读取检查点、接收消息和发送回复。它验证记录互通及旧入口拒绝，不证明真实 GitHub API 的并发行为、目标会话遵循情况或原生会话控制能力。真实结果需要目标会话按第 0–4 节执行后独立核验。

本轮不修改产品程序，不更新已安装版本，不改写历史，不清理既有实例或消息。协议扩展试验通过后，再决定怎样同步正式文档、CLI 和工作台。
