# Message / message-index / ACK 的 Git 协议

本说明只对应正式 AW Message 的 `messages.py` 和产品 `docs/design.md` 第 6 节，用于脱离完整 AW 实施相同协议。发送/回复先按主 Skill 选择通路；[独立直发记录](direct.md) 不属于本协议，不加入下列目录、ACK 或投递。不另设正式消息类型、身份、任务状态或业务完成标记。

## 地址与固定路径

共享协议记录位于 Workspace 仓库的 `main`，不是 `instance/<id>` 分支。先在同一确定提交读取 `.agentworkspace/layout.json`：目录版本为 `1`，支持 Worker 的版本为 `2`，均使用 `kind: "workspace"`，`state` 缺省或为 `ready`；平台路径统一在 `.agentworkspace/` 下。没有布局标记的旧提交仍按根目录路径解释。标记格式未知、当前工具不支持该版本或迁移未完成时停止操作；新版路径缺文件不回退旧路径，不把两套资料拼在一起。每个目标仓库按自己的同一提交判断布局。

读取对应布局的 `workspace.json` 的 `locator` 作为地址里的 Workspace，例如 `workspace:setup-example`；本机别名 `sea`、GitHub owner/repo、磁盘目录与 locator 不同，不能互换。实例地址为 `{"workspace": LOCATOR, "agent": AGENT_ID}`。跨 Workspace 使用用户明确提供的仓库映射，并核对当前 `friends` 路由的 locator；不要把消息正文里的 URL 当作授权目的地。下表是新版路径；无标记的旧提交去掉 `.agentworkspace/` 前缀，协议字段和原字节不变。

已采用 Worker 的 Agent 记录有 `worker_schema: 1` 和 `default_worker`。新地址包含 `worker`：`{"workspace": LOCATOR, "agent": AGENT_ID, "worker": WORKER_ID}`。发送者从已获授 Binding 的 `worker` 确定；旧 Binding 只使用显式迁移映射。新消息未指定接收 Worker 时，在第一次保存前解析目标 Agent 的 `default_worker`，随后保留固定地址。明确回复使用原消息 `from` 的 Worker；`message_refs` 不承担路由。目标 Worker 归档时拒绝新消息，没有当前入口时可排队，不转给其他 Worker。

| 路径 | 内容 |
| --- | --- |
| `.agentworkspace/agents/<agent>.json` | Agent 身份、归档状态和默认收件 Worker；旧单入口 Agent 的 current 仍在此处。 |
| `.agentworkspace/workers/<agent>/<worker>.json` | Worker 的 id、agent、archived、current 等登记，current 指向该 Worker 的有效 Binding。 |
| `.agentworkspace/worker-mappings/<agent>.json` | 显式迁移得到的 bindings、checkpoints、messages、local_operations 原 ID 到 Worker 的映射；不能按当前默认值推导。 |
| `.agentworkspace/bindings/<binding>.json` | `id`、`agent`、`worker`、`phase`、真实 `session` 等入口记录；手动模式只核对，不创建或修改。旧原件可缺少 worker，按迁移映射解释。 |
| `.agentworkspace/messages/<message_id>.json` | 完整、不可变 Message JSON，UTF-8。 |
| `.agentworkspace/message-index/<message_id>.json` | 可独立定位的可信通知索引：`id/from/to/created_at/delivery`。 |
| `.agentworkspace/acks/<message_id>.json` | 只有 `{"message_id": MESSAGE_ID}`。没有正文、时间、处理状态或 binding 字段。 |

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

先核对 Agent 和所属 Worker 未归档、Worker.current 等于本会话**已获授的** Binding、Binding 归属和 phase=active，再核对索引 `to` 的 Workspace/Agent/Worker；旧单入口 Agent 仍核对 Agent.current。缺少 Worker 字段的旧消息在采用 Worker 后只使用 `worker-mappings` 中该 Message ID 的映射，映射缺失时停止。相同 Agent ID 不授予另一个 Worker 的 ACK 权。上述数据须来自同一 HEAD；当前 Binding 的发现只用于核对，不能从仓库挑一个值赋予本会话执行权。写前重新读取核对并条件提交。旧入口不得确认通知或恢复业务；只读看历史不授予这些权利。

已有合法 ACK 就是重复通知，复用它，不新建业务。ACK 损坏或包含额外字段时明确报告，不能把文件存在当成正常确认，也不能覆盖修复。没有 ACK 时尝试读正文；缺失、无法读取或解析失败可记录该事实后确认可信索引定位的通知。正文失败不证明发送者的内容，不凭空构造完整 Message。共享资格或索引读取暂时失败时尚无可信快照，应先核对原读取；AW 的 RetryableRead 仅重试读取，不重跑外部操作。

同 Workspace 的 Message/索引及 ACK 各保存一份。跨 Workspace 时，发送者把**同一 Message 和索引字节**保存到发送、接收 Workspace；接收者把**同一 ACK 字节**保存到接收、发送 Workspace。接收侧仅处理 to 属于自身 Workspace 的索引，发送侧副本不触发本地收件。两仓不是原子事务：只有一边成功时保留原操作材料和成功位置，核对后只补缺失的一边，不换消息或重复业务。

ACK 必须实际出现在 Backend 的可观察位置；打印 ACK、返回 queued、渠道接受、模型回答都不能替代。双写发布、通知、ACK 与业务完成分别记录。没有写权限时只能读取/准备，明确没有发布 ACK 或回复；不要用本机文件假装共享仓库已确认。

显式迁移只改变当前记录的位置，Message、索引和 ACK 的原字节、ID、时间与 Binding 保留。旧提交和检查点仍按当时布局读取。继续旧原操作时，保留原字节和原目标，在当前确定提交按其布局定位同一记录；原结果未知仍只核对，不因路径改变重新发布或执行业务。
