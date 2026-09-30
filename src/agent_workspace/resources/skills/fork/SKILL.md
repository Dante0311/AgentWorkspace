---
name: fork
description: 从已经保存的检查点创建另一个实例，保留资产与来源关系。
---

# fork

Fork 创建新身份，原实例不必停工。不从任意未保存的聊天位置分叉。

```sh
aw -w sea checkpoint list helper
aw -w sea checkpoint show helper --id CHECKPOINT_ID
aw -w sea agent fork helper --checkpoint CHECKPOINT_ID --name exploration
```

新实例分支从指定版本开始，保留全部已保存的来源文件和历史，不改写旧消息的身份或旧 Work 的负责人，不自动清空待办事实。
新实例不取得原实例的执行权或工单。需要正式工单才创建新 Work；普通协作无需 Work。
创建完成后通过 relay 进入，必为新原生会话。检查点只确定起始快照，不禁止使用方随后查阅来源的其他历史。
不自动合并回原实例，不把 Git 合并称为已实现的语义 Merge。
