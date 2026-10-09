# 可直接复制：handoff

请对我当前正在使用的实例执行 handoff。这条指令与实例的 `/handoff` Skill 含义相同：保存实际工作事实并交出当前执行资格，不创建后继，不自动归档聊天，也不继续新的业务工作。

先从本会话已经验证的进入材料和平台记录确定 Workspace、Agent 与当前 Binding；不要仅凭角色名称选择实例。若缺少唯一明确的目标，只询问缺失的身份信息。当前材料用于 `aw-team`（协作仓 `Dante0311/AW-Workspace`）；与本会话实际身份不符时不要套用。

读取本实例 `.agents/skills/handoff/SKILL.md`、`.aw/prompts/checkpoints.md`，以及 [本机和云端共同的工具选择说明](https://github.com/Dante0311/AgentWorkspace/blob/codex/cloud-owner-recovery-20261009/docs/evidence/2026-10-09-cloud-owner-startup/access.md)。有正式 AW 工具就调用相应操作；只有已授权的 GitHub 手动能力时，按其链接的操作细节执行。不要因为在云端就改写 Desktop/CLI 的停止规则。

请依次完成：

1. 核对本会话确实拥有当前入口。整理累计事实、已完成和未完成的任务、用户约束、产品分支/提交、未提交变化、验证与未决结果，以及后继需要的原始资料和路径。不要替我筛掉历史、决定任务作废或把未知结果写成失败/成功。
2. 保存应当延续的实例资产并创建实际检查点。说明检查点保存范围，产品工作区、原生会话和外部资料未包含时给出实际来源；保留原文件与其他人的改动。按检查点指针的固定 revision 读回，确认可用。
3. 使用当前 Binding 和该检查点请求交出。正式工具使用 `agent.stop`；GitHub manual 路径按同一停止请求与确认规则保存。之后停止业务执行并结束当前轮次。
4. `awaiting_native_idle`、stopping 或等待使用者确认均只表示尚未完成交出。Desktop/CLI 必须由实际适配器确认；manual 仅在当前使用者明确确认业务已停止后完成释放。不要用结束回复、超时、窗口关闭或自然语言承诺代替依据。没有所需确认时，把问题和已经保存的检查点告诉我，等待该确认。

报告真实检查点、停止请求和当前结果。若本次请求已经完成，只读核对已有结果，不再请求另一轮交出。单独 handoff 不启动、预留或控制后继。

**只有读回确认旧 Binding 已 released、handoff 已发布且可供新会话消费时**，再附一段我可以直接复制到新会话的 relay 内容：包含下方 relay 提示词的固定提交链接、真实 Workspace/仓库/Agent、handoff ID、checkpoint ID、固定实例 revision、必要资料位置与已有任务说明。

[relay 提示词](https://github.com/Dante0311/AgentWorkspace/blob/codex/cloud-owner-recovery-20261009/docs/evidence/2026-10-09-cloud-owner-startup/relay.md)

生成复制内容时先解析并使用该材料的实际提交 SHA，不填写占位符或虚构结果。若交出仍待确认，就明确报告等待状态，不给出声称“已经可以接手”的内容。
