---
name: message
description: 发送、查询、确认通知和控制自动投递，不强制业务回复。
---

# message

投递前读取 `.aw/prompts/capabilities.md`，核对目标的当前入口。`delivery_unsupported` 不是临时故障；告知用户并保留原消息，不自动改成 normal、重发副本或伪造 ACK。

from 使用当前实例，binding 使用本原生会话被明确授予的入口，不读取新入口冒充接手。

```sh
aw -w sea message send ui --binding BINDING --to core --delivery normal --content-file message.md --request-id OPTIONAL_STABLE_ID
aw -w sea message send ui --binding BINDING --to sbp/build --delivery insert --content "正文"
aw -w sea message list --agent ui --unacked
aw -w sea message show --id MESSAGE_ID
aw -w sea message receive ui --binding BINDING --id MESSAGE_ID
aw -w sea message poll ui --binding BINDING
aw -w sea message watch ui start --interval 5
aw -w sea message watch ui stop
aw -w sea message watch ui status
aw message reconcile OPERATION_ID
```

watch 的定时 poll 由运行器执行，使用 runtime start 启动本入口的监视器。manual 入口只支持主动 receive。
show 不 ACK；receive 尝试读取后保存单字段 ACK，正文失败也确认通知。ACK 不是已读或业务完成。
已确认通知不重复开展业务；需要回看用 show。ACK 未发布成功前保留工具结果，补齐原操作，不新增消息或盲目重复副作用。
normal 等队头可投递且入口空闲，insert 不因忙等待，但不越过队头。回复仍用 send --ref MESSAGE_ID。
跨 Workspace 的双写由 Git Backend 完成。工具返回 pending/outcome_unknown 时只补齐原 ID。
