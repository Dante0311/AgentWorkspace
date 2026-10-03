# 开发接续 Checkpoint

本文件是软件开发进度与恢复入口，不是产品实例的运行 checkpoint，也不是第二份产品设计。先按下述版本恢复代码，再核对分支是否已有新提交；不要从聊天中的“继续”推断功能已实现。

## 1. 固定恢复点与分支关系

- 仓库：`Dante0311/AgentWorkspace`。
- 当前唯一继续开发的分支：`feat/native-runtime-maintenance`，对应 [PR #4](https://github.com/Dante0311/AgentWorkspace/pull/4)，保留草稿状态。
- 本 checkpoint 之前的代码提交：`404c82ad3a8a8cdece2b857ad87626cb984ab5a3`。
- PR #4 基于 [PR #3](https://github.com/Dante0311/AgentWorkspace/pull/3)：`feat/first-use-caretakers`，提交 `b01afbdf9297371c8a256816dcb4006feb46e4c3`。
- PR #3 基于 [PR #1](https://github.com/Dante0311/AgentWorkspace/pull/1)：`fix/robust-local-state`，提交 `4d8303433eef1e1018a82d7f96bd6c23e899cdaa`。
- 已确认的产品合同在独立 [PR #2](https://github.com/Dante0311/AgentWorkspace/pull/2)，提交 `7cc281aa3b6f0f03250cdd8f43364dfb53357558` 的 `docs/design.md`；当前功能分支中的旧版 design/AGENTS/README 尚未与该文档 PR 合并，不能以旧的初始化边界推翻用户新决定。
- 本次核对时 `main` 仍为 `fb119bd9879bfd9a3f363426d0cc61d740a3a241`。PR #1、#2、#3、#4 均未合并。未经用户明确授权，不合并、重写历史、发布版本或变更许可证。
- PR #5、#6、#7 是已关闭、未合并的重复制品准备草稿；其说明均要求继续使用 PR #4。不要再建立同用途的平行实现分支，也不要删除这些恢复线索。

## 2. 已确认的需求，不再退回讨论

V1 必须支持：选择 Harness、Desktop/CLI 入口、模型服务、模型和推理强度，为持久实例创建真实会话，持续收发消息，并自动 handoff/relay 到新会话。手动在实例目录打开会话是保底，不是自动化的替代；统一聊天界面与同身份多事务留到 V3。

首批目标是 Codex、Claude Code、WorkBuddy 系列的 Desktop/CLI，以及企业微信渠道。各实际入口分别验证；CLI 成功不冒充 Desktop。Harness 控制和模型服务配置是不同维度，企业微信是独立渠道。优先原生接口、SDK 和薄适配，不预设 ACP、CC Switch、模型网关或复杂继承体系为依赖。

新建 Workspace 建立 Steward、Sentinel、Maintainer 三个真实实例，与用户 Agent 共用创建、配置、通信和交接机制。管家处理 Workspace 管理事务；巡检员维护计划，程序计时及采集健康事实，维修员在明确授权内修复并复查。名字或提示词不授予管理权限。

首次使用只发现 Git 与 Harness，不代装、不替用户登录、不扫描私密会话。用户自行安装 Git/Harness、提供本地数据目录或远端 Git 地址。认证复用本机机制，不保管 Git 密码；检查连接不能伪装成已验证写权限。软件、共享 Workspace、实例资产及产品仓保持分离。

必须保留：单实例唯一有效入口、条件写入、资产保护、实际授权、原操作追认、结果不明不自动重放。不用“简化”削减上述已确认功能，也不以“以后可能有用”为由增加层次、常驻进程或配置。

## 3. 真实实现进度

| 范围 | 已提交事实 | 状态边界 |
| --- | --- | --- |
| 基础可靠性 | 输入 FIFO、原请求去重、初始 checkpoint 补齐、受管路径保护、参数分发和重复读取优化 | PR #1；不是跨 Harness 完整验收 |
| 首次使用 | `aw setup --open`、依赖发现、只读 Git 检查、本地/远端创建及接入 | PR #3；不代装、不启动模型 |
| 管家身份 | 三份内置定义、三个真实实例、部分创建失败按原请求补齐 | 身份已实现；管理授权、巡检与维修运行仍需开发 |
| 模型配置 | Codex CLI 独立配置、模型/强度、自有 URL 和凭据环境变量引用、显式元数据探测 | 配置能力已有；自有服务和真实模型尚未验收 |
| 现有 Runtime | Codex app-server / Desktop 控制客户端、输入队列、同实例交接等预览代码 | 不代表 Claude/WorkBuddy 或跨 Harness 自动接手已完成 |
| 企业微信 | 可选文本桥接与受管组件看护代码 | 真实 Bot、账号及外部收发未验收 |
| PR #4 新增 | 构建制品上传、准确源码归档、原生 SDK 公共类型/签名检查 | 相对 PR #3 仅 3 个文件、71 行新增；尚未新增 Runtime/维护生产实现 |

这次恢复环境没有发现更晚的本地未提交源代码，不能确认未落盘的工作。已下载远端构建源码用于接续，不能把源码恢复或依赖准备计作新增产品能力。

## 4. 已取得的验证证据

- [CI run 37052102430](https://github.com/Dante0311/AgentWorkspace/actions/runs/37052102430)，关联 `404c82a`：Linux/Windows × Python 3.11/3.13 四个测试 job 均成功，Build and isolated wheel install 成功。
- [Native SDK contracts run 37052102283](https://github.com/Dante0311/AgentWorkspace/actions/runs/37052102283)，同一 head：成功。只证明脚本检查到的 SDK 类型/签名，不证明真实 Harness、账号、模型或 Desktop 可用。
- [PR #3 验证记录](https://github.com/Dante0311/AgentWorkspace/pull/3#issuecomment-5957582908)：当时 Ubuntu Python 3.13 为 171 passed；这是该次日志的结果，不与其他 job 数字相加，也不替代新提交验收。
- 本次已通过连接器下载 `agent-workspace-build`，artifact ID `11247570586`，ZIP SHA256 为 `92608b8bbf883c46eacaa26a968866c38d00928bf42d7c38fc016b8bee404e80`，本机核对一致。包含 wheel、sdist、`source-checkout.tar.gz`。
- 源码归档来自该 run 的 PR 测试 checkout；恢复后修改前应核对目标 head 的 Git blob，不能把归档所在 merge ref 当作主分支已合并。
- 该构建制品标示到期 `2026-10-09T19:08:25Z`。长期恢复以 Git 提交为准，不能仅依赖 Actions 临时制品；不要将有签名的临时下载 URL 写入仓库。
- 本次本机 editable 安装成功；全套检查在执行时间上限内未结束，不能声明本次本机全套通过。后续测试应保存日志、退出码和准确代码版本。

## 5. 仍需开发，不得转嫁为用户实机验收

1. 使用真实原生 SDK/API 完成 Claude Code 与 CodeBuddy/WorkBuddy 实际入口的持续会话适配，接入既有 Runner、输入队列及 Message。先验证两条可控入口，再固化薄接口；不为每种模型服务新增子类。
2. 建立持久的跨 Harness 自动交接操作：预检新端配置，旧端保存并释放，新端创建并绑定，加载 relay；各失败点记录已完成事实，重试不重复交出或创建未知结果会话。
3. 管家管理操作的明确授权、可停止且可恢复的 Sentinel 定时执行、确定性健康报告、Maintainer 受限维修和结果复查。无授权不写、不自动接管、不重放未知业务。
4. 各 Desktop 自动创建/定位/控制能力逐项核实。缺接口属于上游能力限制，需要具体说明缺哪一步及证据；缺实现属于开发工作，不能笼统写成“只待用户验收”。
5. 新机器安装入口、使用说明和隔离安装回归；正式 Release/PyPI 发布及许可证决定与开发分开，需要明确授权。
6. 对齐 PR #2 的唯一产品文档、当前实现状态、打包 Skill 和 UI 能力标识，不把目标写成当前能力。

## 6. 需要用户环境的验证

在上述对应功能完成后，再验证用户的已安装 Desktop、登录与自有模型服务、模型/强度实际生效、生产 HTTPS/SSH 凭据和仓库策略、企业微信 Bot 收发，以及新机器完整使用流程。凭据通过本机引用提供，不提交或在聊天中索取明文密钥。

当前绝不能宣称“剩余项都只需要用户实机验收”。用户已授权继续实现既定 V1，无需逐批重新征求相同确认；遇到真正的账号、上游接口或授权阻塞时，给出具体证据与最小所需条件。

## 7. 恢复与下一步

先读取本文件、[首次使用实现说明](first-use.md)、上面固定版本的产品设计，以及目标分支当前代码。确认仍在 PR #4，检查最新 head 和工作区差异，保留用户已有变更。完整源码可从正常 Git checkout 恢复；受限环境可通过连接器取得上述源码制品，不要再次逐文件拼凑或重复建立制品 PR。

下一开发单元聚焦实际会话闭环，不再新增外围配置页面：先核对 `runtime.py` / `harness_config.py` 的配置传递和完成事件，再接入一个原生 SDK，覆盖创建、两轮输入、消息送达、明确停止、失败不重放。测试使用隔离数据，不创建用户生产实例，不调用真实付费模型。

每个可解释的开发单元及时提交到同一分支，更新本文件的代码恢复点、实际测试结果和未完成项。大改动前先保存可恢复点；不要把唯一成果留在临时容器或未提交 diff 中。
