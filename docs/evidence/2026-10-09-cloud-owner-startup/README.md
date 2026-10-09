# 三个云端功能 Owner 的启动材料

打开下表对应文件，将全文分别粘贴到三个具备 GitHub 工具的新云会话。每个会话只使用自己的那一份；提示词会让它读取共同说明、建立自己的实例与手动入口，并开始本次研发。

| 新会话 | 启动提示词 | 第一项研发任务 |
| --- | --- | --- |
| Core | [core-startup.md](core-startup.md) | 公共存储错误分类，停止与释放的核心约束 |
| Runtime / Adapter | [runtime-adapter-startup.md](runtime-adapter-startup.md) | 主修 AW-RUNTIME-001、AW-RUNTIME-002：读取异常后恢复、继续确认既有 handoff |
| Communication / Maintenance | [communication-maintenance-startup.md](communication-maintenance-startup.md) | 如实展示相关故障，提供有授权检查的停止恢复入口 |

Workbench 已有实例和有效入口，这次不重写它的启动或继续提示词，也不创建替代会话。Lead、E2E 与三个管家沿用现有身份；本材料不重建它们。

准备时三个新 Owner 尚无实例分支；启动时必须重新核对真实登记。这里保存的是启动材料，没有因为发布这些文件就创建会话、登记实例、派发消息或启动修复。

产品研发从 `62760fae3df05b84766a35b24d3f4d31b1aeb63b` 建各自代码分支，Draft PR 提交到 `codex/cloud-owner-recovery-20261009`。该基线包含已记录的两个 Bug 和真实失败报告；日常运行安装没有升级。

[共同操作说明](common.md)提供 GitHub 条件写入、18 文件实例创建、手动 Binding、消息、检查点与交付步骤；[创建清单](bootstrap-manifests.json)预先列出三个角色的实际职责来源、资源 blob 和创建记录，避免会话自行猜字段或复制其他实例。

普通云会话需要实际可用的 GitHub 写工具。材料不赋予缺失的工具，也不提供自动唤醒。已确认的手动协议互通不等于 AW 自动收件已恢复；自动投递和三管家恢复仍待后续修复与实际验证。

本批材料的核对范围与结果见 [validation.json](validation.json)。检查只验证材料及隔离实例记录兼容性，不代表三个云会话已经启动或 Bug 已修复。
