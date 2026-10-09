# 启动 aw-team / Runtime / Adapter Owner

请执行 Runtime / Adapter Owner 的首次初始化（startup）。实例 ID 为 `runtime-adapter`；这份提示词在本机和云端使用相同规则，不执行 handoff 或 relay。用户要求修复日常使用发现的 AW-RUNTIME-001、AW-RUNTIME-002，你是这两个 Bug 的主负责人。初始化完成后继续下述修复任务。

根据本会话实际能力选择工具：有正式 AW 工具就使用正式操作；没有时使用用户已选择且实际可用的 GitHub manual 路径。不因在本机或云端而假设能力，也不为使用这份提示词强制安装 AW。先读取：

- [本批共同操作说明](https://github.com/Dante0311/AgentWorkspace/blob/codex/cloud-owner-recovery-20261009/docs/evidence/2026-10-09-cloud-owner-startup/common.md)。
- [创建参数与 GitHub 备用清单](https://github.com/Dante0311/AgentWorkspace/blob/codex/cloud-owner-recovery-20261009/docs/evidence/2026-10-09-cloud-owner-startup/bootstrap-manifests.json)，只使用 `roles.runtime-adapter`；正式 AW 创建不手工覆盖平台资源。
- [职责定义](https://github.com/Dante0311/AW-Workspace/blob/32fb3d000bb265452e04c3918862d0025b67d1ef/definitions/runtime-adapter/definition.md)。

读取启动材料时固定同一个产品资料提交并保存来源。协作仓为 `Dante0311/AW-Workspace`，Workspace 为 `aw-team`，自己的长期资料分支为 `instance/runtime-adapter`。按共同说明完成本次首次启动仍缺的身份、入口与初始化；平台已替本会话完成的步骤只核验，不重复执行。已有他人入口或需要接手时报告 startup 前提不符，不自动改做 relay。

产品仓为 `Dante0311/AgentWorkspace`。先读固定基线 `62760fae3df05b84766a35b24d3f4d31b1aeb63b` 的 `AGENTS.md`、`README.md`、`docs/design.md`、`docs/implementation.md` 和 `docs/evidence/2026-10-09-caretaker-relay/README.md`。从该基线建立代码分支 `codex/aw-runtime-recovery-20261009`，Draft PR 的目标是 `codex/cloud-owner-recovery-20261009`。

两个 Bug 的真实背景：日常安装来自 `00fb6bdb61f4accf47067b7acff48b9e5fc6284b`。共享 Git 读取异常导致运行器退出，而 Desktop 聊天仍可接受输入。三个旧管家随后各自保存检查点并请求 handoff，返回 `awaiting_native_idle`；原生轮次结束后仍停留在 stopping，原运行器不能确认交出，现有启动逻辑又拒绝 stopping。新会话尚未建立，旧会话没有归档。完整事实与证明边界以报告为准。

你的具体任务：

1. 修复 AW-RUNTIME-001：沿 `Runner._run_owned` 与退出清理链路确认故障点。与 Core 使用同一套公共错误分类，使确定无副作用的临时读取失败能够保留原会话与 Binding，退避重试；持续错误明确可见。无法取得最新执行权登记时暂停依赖它的新投递和状态转换。权限、损坏数据、真实执行权冲突保持正确失败语义。不得通过重跑整轮业务来恢复，不重复发送输入、创建会话或发布未知结果。
2. 修复 AW-RUNTIME-002：为原 Binding 的既有停止请求恢复实际停止观测。stopping 路径只能观察原会话并完成原请求，不能启动模型业务、Watch、Bridge 或第二个 writer。忙则等待，未知则明确报告，确认空闲且原检查点与归属有效后按核心规则发布唯一 handoff。重复或并发恢复必须核对既有结果；released 不复活。
3. 让 `agent.stop` 在保存请求后保证存在能够完成交出确认的过程：复用可用运行器；缺失时在本次操作权限内恢复仅确认交出的过程。不要把“用户再手动 runtime.start 一次”作为正常操作要求，也不要简单删掉 stopping 保护后启动完整运行器。各 Harness 使用自己的有效观察接口；新启动执行进程不能冒充停止观测。
4. 与 Core 确认错误和条件提交规则，与 Communication / Maintenance 确认诊断及受授权的“继续已有停止请求”入口。你负责真实运行和观测逻辑，其他 Owner 不应各自实现一份。

先核实基线中的实际实现；若部分问题已有修复，检查对应证明后集中处理剩余缺口。共享文件按真实责任协商归属。不要因某个 Owner 暂未登记或未 ACK 就停掉全部工作；可以先完成调用链、独立改动、隔离复现和验证步骤。

验证重点是原会话与 Binding 保持、故障解除后恢复、不重复副作用、持续故障可见，以及 busy/unknown/检查点缺失/归属变化/重复并发恢复均不误释放。使用隔离数据完成当前环境能运行的验证；真实 Desktop 的停止确认、唯一后继 relay 和自动投递交给 E2E 单独复验，不用 Mock 或源码检查宣称通过。

本轮不更新日常安装、不对日常 Workspace 注入故障、不直接改三管家 Binding 或检查点、不启动付费模型。先交付代码、验证与恢复操作材料，后续真实恢复由 Lead 按实际授权安排。

首次汇报提供真实实例/B、职责来源和代码分支，随后继续任务。最终给 Lead、相关 Owner 和 E2E 提交或 Draft PR、可观察行为变化、测试结果、明确未测项及可执行复验步骤；按共同说明保存检查点并发布必要消息，同时在本会话让用户看到成果链接。不要将消息发布或工具接受请求写成验收完成。
