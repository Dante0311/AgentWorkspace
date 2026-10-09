# 本机与云端通用的复制提示词

这些提示词分别起首次初始化、handoff、relay 的作用，方便没有斜杠技能入口的会话直接执行同样的操作。本机和云端使用同一份，不维护两个版本；选择哪种工具由实际能力决定，生命周期动作由用户选择的入口决定。

| 用途 | 可复制的提示词 | 发到哪里 |
| --- | --- | --- |
| Core 首次初始化 | [core-startup.md](core-startup.md) | Core 的首次会话 |
| Runtime / Adapter 首次初始化 | [runtime-adapter-startup.md](runtime-adapter-startup.md) | Runtime / Adapter 的首次会话 |
| Communication / Maintenance 首次初始化 | [communication-maintenance-startup.md](communication-maintenance-startup.md) | Communication / Maintenance 的首次会话 |
| handoff | [handoff.md](handoff.md) | 当前拥有实例执行资格的旧会话 |
| relay | [relay.md](relay.md) | 新的真实会话，并提供已经完成的 handoff 结果 |

打开对应文件，复制全文。三份 startup 带有角色、资料来源及用户这次交付的 Bug 研发任务；不包含接手流程。handoff、relay 是独立通用入口，不复制首次初始化或当初的任务分派。handoff 真正完成后会给出一段带实际身份和检查点的 relay 内容，可以直接复制到新会话。

Workbench 已有启动材料和云会话，本轮不重写它的 startup、不创建替代入口。Lead、E2E 与三个管家的现有身份和交接状态也保持原样。

执行方式见 [access.md](access.md)：有正式 AW 工具时按实例 Skill 调用相应操作；没有时，在用户已选择的 manual 范围内参照 [GitHub 操作细节](github-operations.md)。工具拒绝、缺失或结果不明都如实报告，不通过换访问方式绕过权限，不把提示词当作已经实现的运行能力。

首次初始化的共同步骤与本批任务范围见 [common.md](common.md)。[bootstrap-manifests.json](bootstrap-manifests.json)保存三个角色的创建参数，以及 GitHub 备用路径的 18 文件创建清单；正式 AW 工具创建时由实际安装版本生成平台资源。发布这些材料不等于创建了实例或会话。

本批研发从 `62760fae3df05b84766a35b24d3f4d31b1aeb63b` 创建各自产品分支，Draft PR 目标为 `codex/cloud-owner-recovery-20261009`。Runtime / Adapter 主修两个 Bug，Core 与 Communication / Maintenance 按职责配合；日常运行安装没有因本次文档调整而升级。

[原创建清单验证](validation.json)保留旧版材料的隔离核对结果；[本次三类入口核对](lifecycle-validation.json)记录修订范围与验证。前者不代表本机/云端真实启动，后者也不代表运行器 Bug、自动通信或日常管家交接已经修复。
