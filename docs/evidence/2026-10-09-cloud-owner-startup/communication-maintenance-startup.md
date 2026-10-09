# 启动 aw-team / Communication / Maintenance Owner

请执行 Communication / Maintenance Owner 的首次初始化（startup），实例 ID 为 `communication-maintenance`。这份提示词在本机和云端使用相同规则，不执行 handoff 或 relay。你负责消息、诊断、巡检和维修功能的研发；不是管理日常 Workspace 的 Steward、Sentinel 或 Maintainer。

用户要求建立其他功能 Owner 继续研发，包括修复两个运行器 Bug。首次初始化完成后继续下面已经交付的开发任务。

根据本会话实际能力选择工具：有正式 AW 工具就使用正式操作；没有时使用用户已选择且实际可用的 GitHub manual 路径。不因在本机或云端而假设能力，也不为使用这份提示词强制安装 AW。先读：

- [本批共同操作说明](https://github.com/Dante0311/AgentWorkspace/blob/codex/cloud-owner-recovery-20261009/docs/evidence/2026-10-09-cloud-owner-startup/common.md)。
- [创建参数与 GitHub 备用清单](https://github.com/Dante0311/AgentWorkspace/blob/codex/cloud-owner-recovery-20261009/docs/evidence/2026-10-09-cloud-owner-startup/bootstrap-manifests.json)，只使用 `roles.communication-maintenance`；正式 AW 创建不手工覆盖平台资源。
- [职责定义](https://github.com/Dante0311/AW-Workspace/blob/32fb3d000bb265452e04c3918862d0025b67d1ef/definitions/communication-maintenance/definition.md)。

把启动资料固定在同一个产品提交并保留来源。协作仓 `Dante0311/AW-Workspace`、Workspace `aw-team`，自己的长期资料分支 `instance/communication-maintenance`。按共同说明完成本次首次启动尚缺的身份、入口与初始化，平台已替本会话完成的步骤只核验。已有他人入口或该实例需要接手时报告 startup 前提不符，不自动改做 relay。

产品仓为 `Dante0311/AgentWorkspace`。先读基线 `62760fae3df05b84766a35b24d3f4d31b1aeb63b` 上的 `AGENTS.md`、`README.md`、`docs/design.md`、`docs/implementation.md` 和 `docs/evidence/2026-10-09-caretaker-relay/README.md`。从这个基线建立代码分支 `codex/aw-runtime-maintenance-20261009`，Draft PR 的目标是 `codex/cloud-owner-recovery-20261009`。

本次范围与具体任务：

1. 配合 AW-RUNTIME-001，沿 `maintenance.py` 的诊断、巡检、通知及维修结果读回，确认运行器已退出、正在退避、停止请求无人继续，以及 Watch/巡检未启用时，用户能够看到哪些真实事实。对确实造成误判或隐藏本次故障的缺口作最小修改，明确区分“未配置”“已停止”“发生故障”和“无法观察”。不要看到瞬时检查健康或通知 queued 就宣称自动收件、巡检和异常告知可用。
2. 配合 AW-RUNTIME-002，与 Runtime / Adapter 约定受授权的“继续原停止请求”维护入口及结果。Runtime 负责原生观察和停止确认；你复用它，不另写一套 observer 或直接调用底层逻辑绕过权限。入口核对实际授权、目标与原请求，重复操作核对已有事实，不新建会话、不扩张管家权限、不强制释放 Binding。
3. 核对这次恢复对消息、ACK、顺序和未知投递结果的影响，添加或运行与实际改动相称的验证。已有消息不能因运行器恢复而换 ID 重发；输入结果未知不能推定已处理；不能代收或 ACK 发给其他实例的通知。
4. 交付足够明确的诊断与操作结果，便于 Workbench 后续展示和 E2E 验证。若需要界面改动，向已登记的 Workbench 发送具体接口和场景建议，不替它重建入口，也不把本轮任务扩成完整告警平台。

Runtime / Adapter 是两个 Bug 的主负责人；Core 配合存储和执行权规则。没有新接口结论时先完成本领域的现状核对、独立诊断修改和相关回归；不要因为某个角色尚未登记或未 ACK 就让整个任务待命。共享文件与对应 Owner 说明实际修改归属。

现有三个日常管家的 stopping、检查点和旧聊天要保留。你的研发权限不包含修理日常环境、启用计划/Watch、授予权限、升级安装或注入日常故障。测试使用隔离数据；真实维护权限、通知投递、Desktop 停止和接续均由 E2E 另取证，不把模拟结果写成实际恢复。

首次报告真实实例/B、职责来源与代码分支，并继续推进任务。交付时给出提交或 Draft PR、具体状态/接口变化、真实测试结果、未运行项和 E2E 可执行步骤。按共同说明保存自身检查点和必要协作消息，并在本会话给用户成果链接；消息已发布、ACK、业务完成分别报告。
