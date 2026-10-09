# 可直接复制：relay

请在这个新的真实会话中执行 relay，接手我提供的交接材料所指向的同一个实例。这条指令与实例 `/relay` 的接手用途相同，不执行首次初始化，不重新创建身份或套用新的角色 Definition。

目标 Workspace、协作仓、Agent、handoff 和 checkpoint 从我随本指令提供的真实交接结果取得。若没有明确的目标，只询问必要信息，不遍历后随便挑一个实例。本材料用于 `aw-team`（协作仓 `Dante0311/AW-Workspace`）；实际交接目标与此不同则先说明。

先读取目标实例 `.agents/skills/relay/SKILL.md`、当前能力说明，以及 [本机和云端共同的工具选择说明](https://github.com/Dante0311/AgentWorkspace/blob/codex/cloud-owner-recovery-20261009/docs/evidence/2026-10-09-cloud-owner-startup/access.md)。根据本会话实际工具执行正式 AW 进入流程，或使用用户已经选择的 GitHub manual 路径；不按本机/云端标签决定身份和权限。

请依次完成：

1. 核对实例未归档、旧入口确已释放、指定 handoff 属于该实例且尚未被别的入口消费；读取它指向的检查点和固定 revision。仅有旧会话的摘要、checkpoint 或停止请求，不能代替已完成 handoff。
2. 经正式操作为这个真实新会话取得唯一的新 Binding。若平台已经替本会话预留/绑定后继，核对真实 Session、handoff 与本会话的对应关系，继续这个确定的操作，不再创建第二个入口。不借用远端已有 Binding，不复活旧会话。
3. 只有新入口实际 active 后，加载本实例原有的 AGENTS.md、必要 Skill、固定交接检查点、累计资料和实际任务关联。按需追溯原始材料；保留实例资产，不重新初始化职责，不覆盖后来新增或本地未提交的文件。
4. 核对产品分支、提交、未决操作和验证范围，明确本环境能执行什么。继承用户已授权且仍未完成的任务；用户本轮只要求接手待命时就待命，不从角色名称制造新任务。
5. 保存本次实际接手记录与必要检查点，报告真实的新 Binding、所消费的 handoff、读取的固定版本、已加载材料、未解决问题及下一步。若具备明确可继续的任务和工具，按原授权推进。

GitHub manual 路径的 `session=null` 只是已选择的协议试验，不等于核验了原生会话或启用了自动通信。正式工具返回 starting、待绑定或权限/能力错误时，报告停在哪一步，不声称接手成功，也不转用 GitHub 绕过拒绝。

如果没有合法 handoff、旧入口仍 active/stopping、检查点不可读或请求结果未知，请保留已有记录，指出未满足的具体条件；不要自动切换为 startup、清空 current、补造 handoff 或重建同名实例。
