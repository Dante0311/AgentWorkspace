# 可选原生直发记录

先按 message Skill 的发送判断核对资格。本文只说明留档；这些命令不发送原生输入，不证明双方同机，也不为本会话授予其他 Agent 的入口。

记录保存在调用方 Workspace `main` 的 `.agentworkspace/direct-messages/<id>.json`，不双写对方 Workspace，不进入正式 `.agentworkspace/messages/`、`.agentworkspace/message-index/`、`.agentworkspace/acks/` 或 `.agentworkspace/dispatch/`。布局依据同一提交的 `.agentworkspace/layout.json`；无标记的旧提交仍读取原根目录 `direct-messages/`，新版缺失不回退旧路径。迁移保留原 ID 和字节，不重发原生输入。它是调用方保存的观察，不证明原生工具接受、真人已读或业务完成。换机后可读取已经发布的记录；没保存的交流不会出现在这里。

`direct-message.record` 使用当前工具绑定的 `workspace/agent_id/binding`，传 `to/content/request_id`。`to` 与正式 Message 一样使用 Agent ID 或 `好友别名/Agent ID`。类型参数 `record_type` 当前为 `codex`。`result` 可保存实际原生工具返回的 JSON 对象；`receipt` 可保存实际收到的回执对象，两者都可省略。没有实际结果不要编造接受或已读；结果未知只保存未知事实并核对原发送。

目标已采用 Worker 时，必须同时传入当次原生发送实际使用的 `to_worker`，不能在留档时重新读取默认 Worker 来猜目标。来源 Worker 由调用者 Binding 确定。对已有直发记录的明确回复可传 `reply_to` 指向原直发记录；它与正式 Message 的 ID 各自独立。

记录 ID 在首次留档前固定，不是正式 Message ID，也不授予原生发送的幂等能力。重复保存相同内容返回已有记录和原时间。后来实际获得结果或可选回执时，可以用原 ID、相同目标和正文补缺字段；不覆盖已有字段，不为了更新历史重发原生输入。`created_at` 是第一次保存记录的实际时间。

留档返回 `recorded: true` 表示保存已确认；`false` 表示这次没有确认保存成功；`null` 表示写入结果未知。后两者都不改变原交流结果，不自动补正式 Message、不写 ACK、不重发。未知写入仅用 `direct-message.show` 核对原 ID；没有记录或没有回执不等于发送失败。

通过 AW MCP/HTTP 的公共 `aw_execute` / `/api/execute` 使用相同命令。CLI 复用已有 JSON 入口：

```sh
aw -w sea call direct-message.record --arguments @native-record.json
aw -w sea call direct-message.list --arguments '{"workspace":"sea"}'
aw -w sea call direct-message.show --arguments '{"workspace":"sea","record_id":"direct-example"}'
```

留档参数示例（CLI 需使用本会话真实获授的 Binding，不复制示例值）：

```json
{
  "agent_id": "alice",
  "binding": "GRANTED_BINDING",
  "to": "bob",
  "to_worker": "review",
  "content": "本次实际发送的正文",
  "request_id": "direct-example",
  "result": {"threadId": "ACTUAL_TARGET_THREAD"}
}
```

`direct-message.list {workspace, agent_id?, worker_id?, direction?}` 返回按记录时间和 ID 排序的记录数组；无 Agent 筛选时读取这个 Workspace 保存的全部直发记录，`direction` 为 in/out。每条记录有 `id/type/created_at/from/to/content`，可有 `result/receipt`，没有正式 ACK 字段。`direct-message.show {workspace, record_id}` 返回 `{record: ...}`；原 ID 没有记录时为 `{record: null}`。读取不执行正文，也不生成回执。

工作台与正式历史合并展示时注明“AW Message”或“Codex 直发记录”。缺回执中性显示；完全没有记录时只能说明该来源的历史可能不完整。直发记录 ID 不冒充正式 `message_refs`，回复需要转为正式 Message 时可在正文说明原生交流的来源。
