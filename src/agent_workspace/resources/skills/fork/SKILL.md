---
name: fork
description: 从已经保存的检查点创建另一个 Agent，保留资产与来源关系。
---

# fork

Fork 创建一个新的持久 Agent 身份，原 Agent 不必停工。本地目录只是这个 Agent 的一份资料副本，准备目录不会启动原生会话或取得执行权。不从任意未保存的聊天位置分叉。

```sh
aw -w sea checkpoint list helper
aw -w sea checkpoint show helper --id CHECKPOINT_ID
aw -w sea agent fork helper --checkpoint CHECKPOINT_ID --name exploration
```

如果新分支已经保存，但 Agent 登记或本地目录准备未完成，明确继续原目标：

```sh
aw -w sea agent fork helper --checkpoint CHECKPOINT_ID --name exploration --new-id exploration --resume
```

继续时保留原来源 Agent、检查点、名称和目标 ID。平台核对检查点资料版本、原目标身份与来源，只补尚未完成的登记或目录准备；已有目录中的用户修改不会覆盖。普通 Fork 遇到已有目标仍拒绝创建。已经登记的目标只准备或复用本地副本，不另建身份。

原发表结果未知时先读取原分支和登记；仍不能确认结果就保留未知，不重放。当前 `AW_HOME` 保存一份原发表凭据，避免登记尚未可见时重复发表；它不是 Agent 身份记录。换机器或换 `AW_HOME` 前，应先在原环境核实尚未确认的发表，不能把新环境没有凭据当作原操作未发生。来源检查点版本或目标身份不匹配时，先检查原操作，不能换目标掩盖失败。

新 Agent 的资料分支从指定版本开始，保留全部已保存的来源文件和历史，不改写旧消息的身份或旧 Work 的负责人，不自动清空待办事实。
新 Agent 不取得来源 Agent 的执行权或工单。需要正式工单才创建新 Work；普通协作无需 Work。
创建完成后通过 relay 进入，必为新原生会话。使用新 Agent 自己的分支和资料根；支持 worktree 的版本复用公共目录准备能力，不要求用户先建目录。独立或共用项目都须重新提供新身份、职责、资料位置和待接续工作，来源检查点的旧身份、路径和 Binding 不成为新入口资格。检查点只确定起始快照，不禁止使用方随后查阅来源的其他历史。
不自动合并回原实例，不把 Git 合并称为已实现的语义 Merge。
