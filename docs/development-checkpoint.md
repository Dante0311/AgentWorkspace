# 开发接续 Checkpoint

本文件是软件开发恢复记录，不是产品实例 checkpoint，也不是第二份设计。以实际 Git 提交和测试为准，不从聊天中的“继续”推断完成。

## 恢复位置

- 日期：2026-10-04。
- 唯一接续分支：`feat/native-runtime-maintenance`，草稿 [PR #4](https://github.com/Dante0311/AgentWorkspace/pull/4)。本检查点前的代码提交为 `17da4d05b5e93485586877c6780ccd01fb4dd2b7`。
- PR #4 基于 PR #3 `b01afbdf9297371c8a256816dcb4006feb46e4c3`；PR #3 基于 PR #1 `4d8303433eef1e1018a82d7f96bd6c23e899cdaa`。不合并、不改写已有 PR 或 main，不另开平行实现。
- 已确认产品合同在文档 [PR #2](https://github.com/Dante0311/AgentWorkspace/pull/2)，提交 `7cc281aa3b6f0f03250cdd8f43364dfb53357558`。功能分支的旧 design/README/AGENTS 仍须对齐，不能据旧约定削减新需求。

## 已有成果

- PR #1：输入顺序、去重、检查点补齐、路径保护、命令分发与重复读取修复。
- PR #3：首次配置、Git/Harness 发现、只读 Git 检查、三名管家实例和 Codex 独立模型配置。
- PR #4：Claude/CodeBuddy 原生 SDK 的持续会话、Runner 接入、固定后继 Binding 的持久自动交接；管家授权、健康检查、持久巡检计划与有限维修；隔离安装脚本和构建制品。
- `17da4d0` 已接通 CLI、HTTP 和工作台中的配置、交接、健康检查、巡检计划、授权和维修入口。旧版检查点中“待接线”的描述已经过时。
- 三套 Harness 不等价于三个 Desktop：Claude/CodeBuddy 当前是受管 CLI/SDK；Codex Desktop 仍依赖真实桌面控制接口及显式配置。不能用 CLI 冒充 Desktop。
- SDK 入口暂不提供已验证的 insert/steer，接口明确拒绝，不静默改为 normal。

## 本次已核实的验证

- `17da4d0` 的 [CI 37191490170](https://github.com/Dante0311/AgentWorkspace/actions/runs/37191490170) 与 [Native SDK contracts 37191490144](https://github.com/Dante0311/AgentWorkspace/actions/runs/37191490144) 均 completed / success。
- 从 CI 源码制品恢复完整源码，制品 ID `11299570873`，SHA256 `2a3d30f165c5faeb88008568072ea8307db89a0c65950cb17beef3371c3f6f88`，已校验。
- 固定 SDK 依赖制品 ID `11290682699`，SHA256 `63136e1021fa96af12458f8195ddfd41858697ca017363958d7b30f4c15cc777`，已校验，并安装在隔离环境。
- 本机完整源码基线：`219 passed, 3 skipped in 56.17s`。三项需显式原生可执行文件的测试被跳过，不记为通过。
- 已有原生二进制测试使用 loopback 模型协议夹具，验证真实客户端的通信，不是付费模型、真实账号或 Desktop 验收。
- 本次未发现旧环境的未提交代码；Git 提交与 CI 制品已保存成果。不提交临时下载凭据、本机路径或真实会话数据。

## 继续工作

1. 验证真实 SDK/Harness 经平台 MCP 调用工具产生的副作用，不只验证文本对话。
2. 检查跨实例授权、故障后的持久结果、巡检停止和维修前提，补针对性回归。
3. 对齐产品文档、当前使用说明与支持矩阵，区分已实现、缺开发、待实机验证和上游接口未确认。
4. 每个完成单元及时提交到 PR #4，更新本文件和 PR 正文；不要让检查点落后于代码。

## 不变边界

V1 必须支持指定 Harness 和模型配置、自动创建真实会话、持续通信及自动交接；手动仅保底，统一聊天与同身份多事务留到 V3。管家小组共用普通实例能力。首次使用只发现和引导，不代装 Git/Harness 或登录。复用原生接口/SDK，不重写 Harness，不强制 ACP 或模型网关。

保留唯一执行权、条件写入、用户资产、凭据引用、原操作追认和未知业务不重放。名字和提示词不授予管理权限。真实账号、自有 API、生产 Git 权限、企业微信、Desktop 和新机器体验须单独验收；缺少开发或上游接口不能伪装成“只等用户验收”。正式合并、发布、许可证变更另需授权。
