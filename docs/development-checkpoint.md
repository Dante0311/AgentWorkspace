# 开发接续 Checkpoint

本文件记录软件开发恢复点，不是产品实例 checkpoint，也不是第二份产品设计。先核对 GitHub 分支和测试结果，不从聊天中的“继续”推断功能完成。

## 恢复点

- 日期：2026-10-04。
- 唯一接续分支：`feat/native-runtime-maintenance`，对应草稿 [PR #4](https://github.com/Dante0311/AgentWorkspace/pull/4)。本次文档提交之前的代码为 `5da42d365d8af39d3ae897354ba6845cc73709ee`。
- PR #4 基于 PR #3 `feat/first-use-caretakers` / `b01afbdf9297371c8a256816dcb4006feb46e4c3`；PR #3 基于 PR #1 `fix/robust-local-state` / `4d8303433eef1e1018a82d7f96bd6c23e899cdaa`。均不擅自合并、重写或发布。
- 产品合同以 [PR #2](https://github.com/Dante0311/AgentWorkspace/pull/2) 的 `7cc281aa3b6f0f03250cdd8f43364dfb53357558` 为准。功能分支内旧版 design/AGENTS/README 尚需对齐，不能用旧初始化约定推翻新决定。
- 已关闭的重复制品草稿不再接续。不要为同一工作建立平行分支。

## 已确认需求

V1 自动选择 Harness/入口/模型服务/模型/强度，为持久实例创建真实会话、持续通信、跨 Harness handoff/relay。手动是保底，统一聊天界面和同身份多事务属于 V3。Desktop/CLI 分别验收，不互相冒充。

首批目标为 Codex、Claude Code、WorkBuddy 系列及企业微信。优先原生接口、SDK、薄适配；不强制 ACP、模型网关、完整第三方管理产品或复杂继承。

Workspace 创建 Steward、Sentinel、Maintainer 三个真实实例，共用普通创建、配置、通信和交接。管家处理 Workspace 事务，不担任用户业务上级；巡检员管理计划，程序计时和采集事实，维修员在授权内操作并复查。名字和提示词不授予权限。

首次使用只发现 Git/Harness，不代装、不登录、不扫描私密会话；用户填写本机目录或远端 Git 地址，认证复用本机机制。必须保留唯一入口、条件写入、用户资产、凭据引用、原操作追认与不明副作用不重放。

## 当前代码事实

| 范围 | 已提交内容 | 仍须注意 |
| --- | --- | --- |
| PR #1 | FIFO、去重、checkpoint 补齐、路径保护、命令分发与读取优化 | 不代表全部跨 Harness 验收 |
| PR #3 | setup 向导、Git/Harness 发现、只读 Git 检查、管家三实例、Codex 独立模型配置 | 不代装、不自动启用巡检 |
| PR #4 | 原生 `NativeSDK` 对接 Claude/CodeBuddy SDK；Runner 接入、固定 successor 的 `transfer.py`、`maintenance.py`、SDK 配置和隔离安装入口 | 模块存在不等于公共入口和维护闭环已接好 |
| 会话测试 | `test_native_sdk.py` 覆盖 SDK 持续会话与 Codex 到 SDK 交接 | 使用真实 SDK 加隔离 transport，不调用模型 |
| 待接线 | `commands.py`、`cli.py`、`server.py` 尚未完整暴露新 transfer/maintenance/SDK 配置能力；工作台也仍偏旧入口 | 下一单元优先完成这些可由开发者验证的缺口 |
| 企业微信 | 已有文本桥接和组件看护 | 真实 Bot/账号/收发待实机验收 |

此次环境未发现未提交的本地代码；已从最新成功 CI 制品恢复完整源码，未依赖聊天手工拼接。旧 checkpoint 的“PR #4 仅有制品准备”描述已过时，由此表替代。

## 验证及制品

- `5da42d3` 的 [CI 37168546582](https://github.com/Dante0311/AgentWorkspace/actions/runs/37168546582)：completed / success。
- 同一提交的 [Native SDK contracts 37168546579](https://github.com/Dante0311/AgentWorkspace/actions/runs/37168546579)：completed / success。这不证明真实模型、账号或 Desktop 通过。
- 源码/wheel 制品 ID `11290252176`，SHA256 `49e85b7761a3a474a42f6ee9481e476359e7b9c5a268555b363ecfe2755ec3eb`；已下载并验证。含 source-checkout、wheel、sdist 和安装脚本。到期以 GitHub 制品信息为准，长期恢复依靠 Git 提交。
- SDK 测试依赖制品 ID `11290682699`，SHA256 `63136e1021fa96af12458f8195ddfd41858697ca017363958d7b30f4c15cc777`；已下载、验证，并在隔离环境安装固定 SDK 版本。
- 已对源码关键文件核对 Git blob SHA，另保存全部原始文件 hash 供差异检查。本机完整基线测试已启动，结果未取得之前不写为通过。
- 不将临时签名下载地址、凭据、模型会话或本机路径提交到仓库。

## 接下来继续实现

1. 接通命令/CLI/HTTP/工作台中的 SDK 配置、自动交接、健康检查、巡检计划及受限维护；同一授权规则作用于各工具入口。
2. 用真实临时 Git 与故障注入验证接续：停止后不复活、定时任务不重复、跨 Workspace/实例越权被拒绝、未知启动不重复、维修前提变化不覆盖。
3. 检查原生 SDK 工具权限、绑定就绪、异常退出与完成事件保存；完善测试而不是扩大权限规避失败。
4. 完成安装脚本回归、使用说明、开发 checkpoint 和当前能力标识。只补所需代码，不建通用调度或权限平台。
5. 对每个 Desktop 明确具体支持及缺失接口。缺开发不能写成待用户验收；缺上游接口也不能写成已支持。

## 实机验收与不可越过的边界

对应代码完成后，才让用户验证已安装 Desktop、登录、自有 API、模型/强度实际生效、生产 Git 认证和策略、企业微信及新机器流程。不要在聊天索取密钥。

目前不能宣称“剩余都是用户验收”。用户已授权持续实现，无需逐批重新询问；每个可解释单元及时在 PR #4 提交，保存测试版本、结果与剩余开发项。正式合并、发布、许可证变更仍另需明确授权。
