# 启动 aw-team / Core Owner

请执行 Core Owner 的首次初始化（startup）。你是 AgentWorkspace 的 Core Owner，实例 ID 为 `core`。这份提示词在本机和云端使用相同规则，不执行 handoff 或 relay。用户已经要求修复日常使用发现的两个运行器 Bug；初始化完成后继续下述 Core 任务。

根据本会话实际能力选择工具：有正式 AW 工具就使用正式操作；没有时使用用户已选择且实际可用的 GitHub manual 路径。不因在本机或云端而假设能力，也不为使用这份提示词强制安装 AW。先读取：

- [本批共同操作说明](https://github.com/Dante0311/AgentWorkspace/blob/codex/cloud-owner-recovery-20261009/docs/evidence/2026-10-09-cloud-owner-startup/common.md)
- [创建参数与 GitHub 备用清单](https://github.com/Dante0311/AgentWorkspace/blob/codex/cloud-owner-recovery-20261009/docs/evidence/2026-10-09-cloud-owner-startup/bootstrap-manifests.json)，只使用 `roles.core`；正式 AW 创建不手工覆盖平台资源。
- [你的职责定义](https://github.com/Dante0311/AW-Workspace/blob/32fb3d000bb265452e04c3918862d0025b67d1ef/definitions/core/definition.md)。

读取启动材料时固定同一个产品资料提交，随后保留该提交来源。

协作仓为 `Dante0311/AW-Workspace`，Workspace 为 `aw-team`；你自己的资料分支是 `instance/core`。使用共同说明完成本次首次启动确实缺少的创建、来源核对、入口和初始化资料；平台已经替本会话完成的步骤只核验，不重复执行。已有他人的有效入口或该实例需要接手时，报告 startup 前提不符，不自动转为 relay。

产品仓为 `Dante0311/AgentWorkspace`。先读基线 `62760fae3df05b84766a35b24d3f4d31b1aeb63b` 上的 `AGENTS.md`、`README.md`、`docs/design.md`、`docs/implementation.md` 和 `docs/evidence/2026-10-09-caretaker-relay/README.md`。从该基线建立自己的代码分支 `codex/aw-runtime-core-20261009`，Draft PR 的目标是 `codex/cloud-owner-recovery-20261009`。

你本次负责的具体工作：

1. 沿 `gitstore.py`、`util.py` 与实际调用方核实 AW-RUNTIME-001 的错误传播。为运行器提供可靠的公共错误区分：只读时暂时网络不可用、缓存锁占用，与权限拒绝、损坏数据及真实执行权冲突不能混作同一类。采取最小必要修改，保留原始诊断，不把所有 Git 失败都包装成“可重试”。Runtime / Adapter 实现运行循环里的等待与恢复，你不再写一套运行器循环。
2. 配合 AW-RUNTIME-002，核查 `app.py` 中保存停止请求、检查点、`finish_stop`、handoff 消费和旧入口拒绝的条件写入规则。对恢复流程真正需要的核心缺口作必要修改；保留同一实例唯一入口，不因旧运行器消失而放宽接管条件。没有发现缺口则说明现有规则足够，不为交付凑改动。
3. 先把具体错误分类和停止确认接口建议发给已登记的 Runtime / Adapter，明确谁修改公共文件。完成本领域正常路径、冲突、重复或结果未知的重要验证；不重放业务写入，不用删除锁解决占用。

两个 Bug 的主负责人是 `runtime-adapter`。`communication-maintenance` 负责诊断和获准恢复入口；Lead 集成；E2E 保留独立验收结论。角色尚未登记时，不代建对方，不为等 ACK 暂停自己能完成的调查、实现与测试。

请保留日常三管家的 stopping 状态、检查点和失败证据；本轮是在产品代码上修复，不升级日常安装或直接释放任何现有 Desktop Binding。不顺带把 session=null 试验改造成完整云端接入项目。

首次汇报说明实际实例/B、职责来源和代码分支，并继续推进本任务。交付时给出提交或 Draft PR、具体行为变化、实际测试结果、未运行项和 E2E 步骤。没有运行环境就明确说明，并完成实际工具允许的工作。按共同说明保存自己的检查点、发布必要协作消息，并在本会话给用户可点击的成果链接；消息已发布不等于对方已收到。
