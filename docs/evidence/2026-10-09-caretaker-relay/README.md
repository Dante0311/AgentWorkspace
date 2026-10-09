# 三管家职责更新与换新会话试用

日期：2026-10-09。用户授权的顺序为：旧会话 handoff，同一实例的新会话 relay，确认新入口后再归档旧聊天。

## 结果

本轮受阻于旧入口的交出确认，未进入新会话 relay。三个旧会话各自更新了自己的职责文件、保存了检查点并调用 `agent.stop`；返回均为 `awaiting_native_idle`。三个原生会话随后结束轮次，但原运行器已经退出，平台入口仍未释放。未创建后继、未归档旧聊天、未修改 Binding 绕过交接。

本轮验证的是三个现有 Desktop 实例的真实操作，不是新建实例初始化验证，也不能证明巡检或自动收件已恢复。

## 版本与已完成的动作

- 日常安装来源：`00fb6bdb61f4accf47067b7acff48b9e5fc6284b`，本轮未替换运行程序。
- 职责模板来源：`76dc07653af27d763d00a4a9380eacda564bc159`。
- 三个旧会话通过 Codex 已有会话消息工具收到用户授权的交接任务；这次投递不算 AW Watch 验收。
- 每个实例使用自己的有效入口，通过 `asset.read` 和带 revision 的 `asset.write` 更新自身 `AGENTS.md`，随后创建检查点并请求 handoff。
- Steward、Maintainer 的职责文件与模板字节一致。Sentinel 仅换行格式和文件末尾换行不同，正文一致。
- 本轮只将角色职责写入三个现有实例。产品分支上的平台进入提示改动尚未随新安装部署，未声称已经验证所有启动模板。

| 实例 | 原 Binding | 已保存的检查点 | AGENTS.md revision |
| --- | --- | --- | --- |
| steward | `b9d900988bb6d414e9d8071a7cc1cbd80` | `c9acd3837f6ef44f28fabb8e5976d7395` | `65b5ffd81e683ddf6c952358d2b50b13a452a18dc70158335893da52f382f11a` |
| sentinel | `bfb3f0116aa244472916b2aff063caf79` | `ce87b07d071ab4f8eb22181d3e79c4caf` | `b7fa1293270aed248dcba22d2249ee74f1f6ccac968f170e8a7427488b879895` |
| maintainer | `b095e83b3d9654d16b1639c37e10c2b76` | `c934da4c2bce541e7900e271c583ed8af` | `7ec2cf2a0a6d808128b5ebeffaaed404dc7fe0a6776e2d0c067e3b4ceff16a04` |

检查点保留了后继需要主动完成的小组启动检查、尚未启用的 Watch 和定时巡检、运行器故障，以及权限不足时需要具体报告的事项。原始 `workbench → lead` 消息 `m4914c0f7229040be8bb1419fbc0c1994` 未代收或 ACK。

## 阻塞及依据

本轮开始前，实时 `agent.show` 返回三个运行器均为 `runner_alive=false`。历史失败记录分别为：Steward 无法解析 GitHub 域名，Sentinel 和 Maintainer 收到 GitHub 空回复。历史错误描述用于说明退出时的记录，不能据此宣称当前网络仍不可用。

真实旧会话已执行 `agent.stop` 并结束轮次；独立读取平台状态仍能看到原 Binding 为 `stopping`、`current` 未清空、`handoff` 未发布、运行器未存活。桌面会话结束和平台执行权释放是两件事。

检查已安装版本的实现发现：

1. `runtime.Runner._run_owned` 依赖运行器观察原生会话 idle 后调用 `finish_stop`。
2. 同一方法在启动时遇到 `phase=stopping` 会拒绝重启执行组件，错误为 `Handoff is already in progress; do not restart its execution components.`
3. `agent.start` 不接管现有有效入口；当前维修动作也没有仅恢复交出确认的操作。
4. 启动运行器属于用户管理操作，当前 Lead 与管家没有可用于该操作的授权路径。未通过改调用身份、改协议文件或直接调用 `finish_stop` 绕过此限制。

第 2、3 项是源码核对结果；本轮没有实际尝试在 `stopping` 状态重启运行器，也没有把源码判断记作真实恢复验收。

Lead 在确认三个运行器已停止后，未先解决恢复路径就下发了 handoff。这一顺序不妥，导致本次试用停在确认交出阶段。后续应同时处理运行器退出后的恢复能力和交接前检查，不能简单删除禁止重启执行组件的保护。

## 继续条件

保留现有检查点和旧聊天，先提供能核验原生停止事实并完成已有交接请求的正式恢复路径。该路径不能重放业务输入、启动第二个 writer 或伪造 idle。恢复后再验证三个原入口释放、新入口唯一且确实读取更新职责，最后归档旧聊天。

巡检、自动收件、异常通知与长期运行仍需各自取得实际运行证据；本次提示词更新和停止请求不替代这些结果。
