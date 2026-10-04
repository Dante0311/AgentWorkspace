# 开发接续 Checkpoint

软件开发恢复记录，不是产品实例 checkpoint，也不是第二份设计。先核对远端提交和实际测试，不从聊天中的“继续”推断完成。

## 接续位置

- 日期：2026-10-04。唯一实现分支 `feat/native-runtime-maintenance`，草稿 [PR #4](https://github.com/Dante0311/AgentWorkspace/pull/4)，基于 PR #3。不另开平行实现、不合并 main、不改写历史、不发布版本。
- 当前运行代码：`298c2ce674dbee2d7357666190f4e19fbad36312`。此前 `9c24ff807fb72cdde97147ee47644b677ab40bfd` 保存跨实例授权和原生 MCP 副作用测试；两个单元均已推送。
- 本次文档提交复制 PR #2 的 `docs/design.md` 与 `AGENTS.md` 确定版本，更新 README、首次使用、实现状态和基础说明，新增 `docs/runtime-and-maintenance.md`。不修改 PR #2 本身，也不把同步文档等同于合并 PR。
- 源码基线从 CI 制品 `11299570873` 恢复，SHA256 为 `2a3d30f165c5faeb88008568072ea8307db89a0c65950cb17beef3371c3f6f88`；固定 SDK 制品 `11290682699` 为 `63136e1021fa96af12458f8195ddfd41858697ca017363958d7b30f4c15cc777`。均已核对。制品有期限，长期恢复以 Git 提交为准。

## 已提交进展

- 原生 Codex、Claude、CodeBuddy 持续会话；实例独立模型配置；固定后继 Binding 的自动交接；CLI/HTTP/工作台入口；三名管家、作用域授权、持久巡检、有限维修和隔离安装入口。
- `9c24ff8`：所有跨实例写操作检查明确授权；`asset.write` 支持限定目标及撤销。Claude/CodeBuddy 的真实已安装客户端通过平台 stdio MCP 创建检查点、在同会话第二轮接收 Message，验证真实 Git 检查点、ACK 和消息副本。
- `298c2ce`：维修动作结果先保存再独立复查。复查失败、退出、复查落盘失败后，同一请求只补复查，不重做动作；未知副作用仍不自动重放。损坏的本机记录报告异常并保留，不阻断其他实例巡检。
- 真实 Codex → 真实 Claude 自动交接测试：原生 Codex 通过动态工具执行 checkpoint.create / agent.stop，Runner 确认停妥并创建固定后继；检查用户资料、交接摘要、新旧 Binding 和 Message.poll 向后继投递形成的实际 ACK。已进入 Native SDK CI。

## 验证证据

- 本机维护/恢复/HTTP/交接安全组：`33 passed in 26.03s`。
- 本机 Codex、Claude、CodeBuddy 原生工具及跨 Harness 交接组：`4 passed in 28.84s`。真实客户端和 SDK，模型响应来自回环 API 夹具，没有付费模型、真实账号或生产数据。
- 运行代码 `298c2ce` 的 [Native SDK contracts 37199759375](https://github.com/Dante0311/AgentWorkspace/actions/runs/37199759375) 已 completed / success。
- 同一代码的 [CI 37199759392](https://github.com/Dante0311/AgentWorkspace/actions/runs/37199759392)：Linux 3.11、3.13 与打包/隔离 wheel 安装已通过；已读取 Linux 3.13 日志，`221 passed, 14 skipped in 68.76s`。14 项按条件跳过不计通过，原生测试另外在 SDK 工作流执行。写本记录时 Windows 两组仍运行，之后须查该 run 的最终结果。
- 本机完整套件曾超时，不以分组结果冒充全套。文档围栏、空白、相对文件链接及 19 条新操作示例的 CLI 参数解析检查通过；不声称全部外部链接与网页锚点均已自动验证。
- 此文档提交不改运行代码、测试、依赖或版本；运行代码的验证证据明确绑定 `298c2ce`，文档提交自己的 CI 仍需单独查看。

## 剩余工作的分类

1. 已有实现待实机验收：真实账号、自有 API、实际模型/强度、生产 Git 认证与策略、企业微信 Bot、安装与长期运行。步骤见 [运行与维护](runtime-and-maintenance.md#6-实机验收顺序)。
2. 尚不能列为仅待验收：Claude/WorkBuddy Desktop 原生控制接口未接通；Codex Desktop 仍是显式控制连接和深链准备，不是完整自动创建/跨端接手。保留目标，不用 CLI 冒充。
3. 当前 SDK 入口未实现已验证 insert/steer 和模型目录探测；不将中断/重开轮次冒充 insert，不把手工配置 unchecked 当成服务能力已验证。
4. 查看上述 CI 的 Windows 结果及本次文档 CI，出现失败先定位；正式合并、发布、许可证或生产环境变更另需授权。

管家和用户 Agent 共用普通实例能力；首次使用只发现和引导，不代装 Git/Harness 或登录。不改全局模型配置，不重写 Harness，不强制 ACP/网关。保留唯一入口、用户资产、凭据引用与未知结果保护；权限检查不等于操作系统沙箱。新增功能及时验证并提交，不以“后续”代替明确阻塞原因。
