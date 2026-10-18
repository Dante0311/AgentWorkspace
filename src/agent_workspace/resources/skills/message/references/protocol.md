# Message / message-index / ACK 的 Git 协议

本说明只对应正式 AW Message 的 `messages.py` 和产品 `docs/design.md` 第 6 节，用于脱离完整 AW 实施相同协议。发送/回复先按主 Skill 选择通路；[独立直发记录](direct.md) 不属于本协议，不加入下列目录、ACK 或投递。不另设正式消息类型、身份、任务状态或业务完成标记。

## 地址与固定路径

共享协议记录不在 `instance/<id>`。布局由 `.agentworkspace/layout.json` 明确选择，`kind: "workspace"`，`state` 缺省或为 `ready`：

- 无标记的旧提交使用 main 根目录；版本 `1` 和支持 Worker 的版本 `2` 使用 main 的 `.agentworkspace/`。
- 消息布局版本 `3` 的 main 标记指定 `messages_branch: "aw-messages"`、`platform_prefix`（空字符串或 `.agentworkspace`）与 `worker_support`。实例资料格式保持原样；启用消息分支不要求旧 Agent 迁为 Worker。
- `aw-messages` 有自己的版本 `3` 标记，`role: "messages"` 与自己的 `platform_prefix`。Message、ACK、message-index、dispatch 只从这个消息快照读取。Agent、Worker、Binding、Work、原生 direct-messages 与职责资料保持 main/instance 原归属。

先固定 `aw-messages` 的消息提交 `M`，再读取 main 的资格提交 `H`。在 `H` 判断布局；旧布局的消息快照就是 `H`。新版必须有 `M`，其标记须为消息角色；读取 `M` 的 `.agentworkspace/message-permissions.json`，其中 `main_revision` 必须属于 `H` 的祖先或等于 `H`。该文件保存权限版本及不可复用的 nonce，不复制权限数据；普通消息保留整个原标记，不能只比较 main_revision 或自行生成 nonce。它的路径和布局标记路径固定，不随 `platform_prefix` 移动。缺分支、缺权限标记、角色不符、未知格式或迁移未完成都停止操作；新版缺消息不回 main 找同名文件。

资格变化由平台在一次真正原子更新中推进 main 和消息分支标记。普通消息只改消息分支，保留原标记，并比较采样时的标记和业务条件；不能在读取 main 后用一个新取得的消息 HEAD 普通推送来绕过这次比较。不支持所需原子更新的服务器应明确失败，不能降为两次写入。每个 Workspace 独立取得这两份真实快照，不拼成一个 revision。

从 main 的 `H` 按其布局读取 `workspace.json` 的 `locator`，例如 `workspace:setup-example`；本机别名 `sea`、GitHub owner/repo、磁盘目录与 locator 不同，不能互换。实例地址为 `{"workspace": LOCATOR, "agent": AGENT_ID}`。跨 Workspace 使用用户明确提供的仓库映射，并核对当前 `friends` 路由；不把正文 URL 当作授权目的地。下表展示常见 `.agentworkspace` 前缀：旧根布局去掉此前缀；版本 `3` 的每份快照分别采用自己的 `platform_prefix`，不能假定 main 与消息分支前缀相同。

已采用 Worker 的 Agent 记录有 `worker_schema: 1` 和 `default_worker`。新地址包含 `worker`：`{"workspace": LOCATOR, "agent": AGENT_ID, "worker": WORKER_ID}`。发送者从已获授 Binding 的 `worker` 确定；旧 Binding 只使用显式迁移映射。新消息未指定接收 Worker 时，在第一次保存前解析目标 Agent 的 `default_worker`，随后保留固定地址。明确回复使用原消息 `from` 的 Worker；`message_refs` 不承担路由。目标 Worker 归档时拒绝新消息，没有当前入口时可排队，不转给其他 Worker。

| 路径 | 版本 3 所属分支 | 内容 |
| --- | --- | --- |
| `.agentworkspace/agents/<agent>.json` | main | Agent 身份、归档状态和默认收件 Worker；旧单入口的 current 仍在此处。 |
| `.agentworkspace/workers/<agent>/<worker>.json` | main | Worker 的 id、agent、archived、current 等登记。 |
| `.agentworkspace/worker-mappings/<agent>.json` | main | bindings、checkpoints、messages、local_operations 原 ID 的显式 Worker 映射，不能按当前默认值推导。 |
| `.agentworkspace/bindings/<binding>.json` | main | 归属、phase、真实 session 等入口；缺 worker 的旧原件按映射解释。 |
| `.agentworkspace/messages/<message_id>.json` | aw-messages | 完整、不可变 Message JSON，UTF-8。 |
| `.agentworkspace/message-index/<message_id>.json` | aw-messages | 可信通知索引：id/from/to/created_at/delivery。 |
| `.agentworkspace/acks/<message_id>.json` | aw-messages | 只有 `{"message_id": MESSAGE_ID}`，没有正文、时间、处理状态或 binding 字段。 |
| `.agentworkspace/dispatch/<agent>/<worker>.json` | aw-messages | 同一 Worker 的投递次数与人工尝试；旧单入口路径为 dispatch/<agent>.json。与 ACK 在同一消息分支条件提交。 |

ID 与实例/Worker/Binding 名使用 1–64 个 ASCII 字母、数字、下划线或连字符，首字符为字母/数字。Message ID 在首次准备时固定；请求重复、响应丢失和部分发布不换 ID。新消息时间使用实际带时区时间，例如 UTC ISO 8601 微秒时间，首次保存后不改；不要复制旧消息时间或编造过去/未来时间。按 `created_at`、`id` 排序推进同一接收 Worker 的队列。

## 完整 Message

```json
{
  "id": "m-example",
  "from": {"workspace": "workspace:sender", "agent": "alice", "worker": "design"},
  "to": {"workspace": "workspace:receiver", "agent": "bob", "worker": "review"},
  "created_at": "2026-10-10T07:00:00.000000+00:00",
  "message_refs": ["m-original"],
  "delivery": "normal",
  "content": "完整 Markdown 正文，含换行、引号、代码围栏和中文。"
}
```

这是 Worker 格式示例，实际发送必须用本会话真实获授的地址和实际时间；旧单入口地址没有 worker 字段。`message_refs` 是可选的关联 ID 数组，AW 创建时默认 `[]`；回复/更正引用原 ID。显式 `reply_to` 可记录唯一回复的原 Message ID，其 from 决定路由。不增加 repo_refs、必须回复或必须创建 Work 等字段。合法未知字段和原正文保留；通知和跨仓库补齐均复制存储原字节，不能解析后只挑已知字段重建完整 Message。

索引是上述五字段的投影，不含 content 或 message_refs。从存储创建新 Message 时一起创建其索引；跨仓库原样复制两份文件。已经有完整 Message 但索引缺失时，只按原记录补索引；已有不同字节的同 ID 文件不能覆盖。

新 AW/辅助脚本记录采用 `json.dumps(..., ensure_ascii=False, indent=2) + "\n"` 的 UTF-8 字节。手动准备可按该编码生成，之后保存原字节/Base64，跨仓库、重试和补齐复用这份材料。不要让编辑器换行转换、摘要或不同序列化改变已经保存的记录。

## ACK、去重与双写

从资格快照 `H` 核对 Agent/所属 Worker 未归档、current 等于本会话**已获授的** Binding、Binding 归属和 phase=active，再从消息快照 `M` 核对索引 `to` 的 Workspace/Agent/Worker；旧单入口仍核对 Agent.current。缺 Worker 的历史记录只使用 `H` 中的显式迁移映射，缺映射就停止。相同 Agent ID 不授予另一个 Worker 的 ACK 权，不能从 current 抄值赋权。写前重新取得完整消息/资格状态并核对；新布局在消息分支比较原权限标记，旧布局在同一 main 快照条件提交。

领取通知的 dispatch 必须在一次消息提交中保护 ACK 不存在、原 Message 与索引未变、原 dispatch 版本及本次权限标记。ACK 与 dispatch 同处消息分支，不能靠不同分支上的普通读取保证这一竞态。normal/insert 规则、每 Worker FIFO、人工投递尝试不重复和有限自动重试保持；消息布局不能授权直接执行其他 Worker 的业务。

已有合法 ACK 就是重复通知，复用它，不新建业务。ACK 损坏或包含额外字段时明确报告，不能把文件存在当成正常确认，也不能覆盖修复。没有 ACK 时尝试读正文；缺失、无法读取或解析失败可记录该事实后确认可信索引定位的通知。正文失败不证明发送者的内容，不凭空构造完整 Message。共享资格或索引读取暂时失败时尚无可信快照，应先核对原读取；AW 的 RetryableRead 仅重试读取，不重跑外部操作。

同 Workspace 的 Message/索引及 ACK 各保存一份。跨 Workspace 时，发送者把**同一 Message 和索引字节**保存到发送、接收 Workspace；接收者把**同一 ACK 字节**保存到接收、发送 Workspace。接收侧仅处理 to 属于自身 Workspace 的索引，发送侧副本不触发本地收件。两仓不是原子事务：只有一边成功时保留原操作材料和成功位置，核对后只补缺失的一边，不换消息或重复业务。

ACK 必须实际出现在 Backend 的可观察位置；打印 ACK、返回 queued、渠道接受、模型回答都不能替代。双写发布、通知、ACK 与业务完成分别记录。没有写权限时只能读取/准备，明确没有发布 ACK 或回复；不要用本机文件假装共享仓库已确认。

显式迁移只改变当前记录的位置，Message、索引、ACK 和已有 dispatch 原字节、ID、时间与 Binding 保留。旧提交仍按当时布局读取。继续旧原操作时保留原字节与目标，按当前明确布局定位同一记录；原结果未知仍只核对，不因换分支、缺文件或暂时读失败而重新发布。消息分支和日常安装的切换由获准管理操作完成，Skill 不手动迁移或编辑权限标记。
