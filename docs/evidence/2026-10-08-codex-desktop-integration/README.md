# Codex Desktop 自动接入：实现与限定验收

2026-10-08，基线 `5aaae00520374b022e0c38fa21f312f8e08629ba`，产品提交 `d9f66f96ae3a3134b17b39a4e174860c4f6e2766`。本批由开发控制者执行和复核，无第二执行者独立复核。采用隔离安装及测试资料，复用用户此前准备的本地桌面项目；没有改生产 Workspace、全局配置或应用私有数据库。

**结果：Codex Desktop 指定路径已接入并取得真实副作用证据，但不是无干预的完整通过。** 自动创建、绑定、normal 投递、同实例交接、旧入口失权和最终释放均有记录。实测中修复两个产品问题；模型抄错 ID、忽略已返回正文及一次控制者纠偏原样保留。两次最终 wheel 冒烟均在 Windows 临时目录清理阶段失败，不计为整项通过。

## 实际改动

- 已捕获连接的 Desktop 通过实际 `list_projects` / `create_thread` 在主目录精确匹配的已有本地项目开新聊天，读回目录和真实 ID 后才绑定。首先只发连接提示，再发正式进入材料，避免绑定前执行业务。创建前保存尝试；未知结果不自动再开聊天。
- `runtime.receive-input` 由实际 `CODEX_THREAD_ID` 取得当前执行轮次；发送回执或 idle 本身不算输入完成。完成判断只针对已登记的原生轮次，保存轮次元数据。`entry_mode` 区分 initial / relay / fork，内部的启动记账字段不再返回给模型。
- 桌面平台命令使用当前安装解释器并校验聊天身份，普通 CLI/MCP 也保留推导出的身份；旧聊天不能通过省略参数冒充管理端或接手新 Binding。它是可信本机协作边界，不是阻止任意 Shell 或篡改环境的 OS 安全沙箱。
- renew/transfer 复用现有 checkpoint、stop、idle、release 合同。旧聊天保留可查看，但失去平台执行权。CLI、工作台、随包提示及七个 Skill 的使用说明同步更新。

## 原生会话和过程

Windows，实际 Codex App Tools `0.1.5`，请求模型 `gpt-6-luna`、强度 `low`；未取得服务端独立强度回报。五个测试聊天共 21 个原生轮次，记录中均为 completed；该状态只证明轮次结束，不证明业务成功。完整导出由公开 `read_thread` 提供，均无下一页、无截断输出，移除了 reasoning 类型项目。

| 会话 | 原生 ID | 轮次 | 实际结果 |
| --- | --- | --- | --- |
| 连接探针 | `01a11a5e-7955-7570-b1db-a3290e8c9a3f` | 3 | 新聊天目录、后续输入及真实会话内捕获连接；闲置后连接仍可控制测试聊天。 |
| A | `01a11a6e-2e37-7860-a43a-5fa7fe6230df` | 6 | 自动创建、首次资产、normal 自发消息和 Watch/ACK、handoff；之后从该旧聊天发起写入，被真实身份校验拒绝。 |
| B | `01a11a7e-1ce6-7d42-ae31-680f622f587d` | 3 | renew 自动创建并绑定，但模型误走初始化，缺少要求的 relay 资产；业务接手未通过。 |
| C | `01a11a86-3ca7-7db3-b40d-e169baa58724` | 3 | 显式 entry_mode 后仍被返回的 purpose=initial 干扰；业务接手未通过，由此定位并修复接口字段冲突。 |
| D | `01a11a8d-4410-7472-9db4-bc5d7f05b30f` | 6 | 修复后按 relay 读取旧检查点、旧资产；后续更正 ID、normal Watch/ACK/资产、最后 handoff/stop。 |

逐项原生记录：[探针](native/probe.json)、[A](native/A.json)、[B](native/B.json)、[C](native/C.json)、[D](native/D.json)。绑定及交接事实保存在 [共享快照](snapshot/shared/agents/desktop-probe.json) 和该目录的 bindings / handoffs 文件。

1. round1 的完成查询错误使用 `turnLimit=20`，桌面拒绝；[失败记录](reports/03-round1-query-limit-failure.json)保留。修为实际允许的 10 后，仅重启监控连接，恢复同一个 A 聊天并完成原输入，没有重建或重发初始化。
2. A 的 Message/ACK 和实际聊天 ID 资产见 [消息证据](reports/06-message-ack-and-asset.json)。测试早期提示使用裸 `aw`，环境找不到命令，模型改用正式入口的安装路径；产品随后统一为精确解释器路径。
3. B/C 平台转移状态虽结束，业务接手仍失败，见 [B](reports/10-first-renew-and-missing-relay-asset.json)、[C](reports/13-purpose-conflict-state.json)。不拿自动检查点替代任务副作用。
4. round5 去除返回正文之外的内部 purpose 后，D 实际读取旧资料，但手抄了错误 UUID。原生命令输出、平台 Binding 均为正确 ID；[原始错误](reports/15-final-relay-native-observation.json)及旧检查点保留。追加纠正输入已经返回正文，模型却误报无输出并结束，[原生证据](reports/18-post-relay-model-ignored-result.json)保留。控制者确认消息和目标资产不存在后，仅补一次[明确纠偏](reports/20-controller-correction.json)，没有把未知副作用重放。
5. D 随后使用环境变量修正资产，发送唯一的 post-relay normal 消息。Watch 自动唤起 D，实际 receive/ACK、读旧启动资产、写入含正确 D ID 的新资产及 checkpoint 均完成，见 [最终消息与停机请求](reports/21-final-message-ack-and-stop-request.json)。没有向 A/B/C 路由该消息。
6. 旧 A 本人执行普通 CLI 写入一次，返回 `conflict: The real Desktop session does not own this execution entry.`，见 [原生拒绝证据](reports/19-old-session-denial-native.json)。最终 sentinel 文件不存在。

## 最终状态与清理

[最终状态](reports/22-final-state.json)记录四个 Binding 均 released、实例 current=null、Watch 关闭、最后 transfer=completed、产品两个原始文件 SHA256 不变。D 本人保存检查点、请求 stop 后结束；运行器观察 idle 并释放，未强制清锁或杀写入进程。最后 Runner PID 98932 已退出，[进程审计](reports/23-process-audit.json)当时仅剩另行执行的 wheel 安装检查子进程；其结果见下方，不能将这张审计解释成整机进程清零。

安装检查结束后的[最终进程审计](reports/25-final-process-audit.json)确认本批隔离路径及两次冒烟临时路径没有残余 Python/Node/aw 进程。本机测试项目、分区、聊天和原始资料保留供查看，没有替用户归档聊天。两次失败冒烟的临时目录保留，未递归删除含 reparse point 的剩余目录。

## 源码、构建与测试

| 检查 | 结果与证据 |
| --- | --- |
| 第一组相关回归 | [23 passed / 7 skipped](reports/unit-round1.log)；需要额外原生环境的跳过项不计通过。此前一次未正确安装项目的启动被中止，没有测试汇总，不计通过。 |
| Runtime / transfer / setup / desktop / 支持说明 | [48 passed](reports/unit-round2.log)，771.87 秒。 |
| Desktop 与进入说明增量 | [10 passed](reports/unit-final.log)，185.74 秒。 |
| 最后三个修正 | [3 passed](reports/unit-final-fixes.log)，35.23 秒；手动 bootstrap 限制、MCP 身份、去除 purpose。分组重叠不累加。 |
| 编译、差异、前端语法、打包资源 | [通过](reports/24-final-source-checks.json)：七个 Skill、desktop-connect 提示及 Node 语法；不是新增 UI 实机验收。 |
| 最终构建 | 无隔离构建先因本机 setuptools 版本失败；[标准隔离构建](reports/build-final-isolated.log)成功生成 wheel/sdist。 |
| 最终 wheel 冒烟 | [首次](reports/smoke-final.log)与[重试](reports/smoke-final-retry.log)均 exit=1，堆栈位于 TemporaryDirectory 清理的 WinError 145；不宣称安装检查整项通过，未据此修改无关生产逻辑或掩盖失败。 |

真实模型运行使用 round1–round5 的独立安装，未就地覆盖运行器。round5 wheel SHA256 为 `36ca556d98e7c15ba8eb2732e2116f1bd8ffa1648293ae95dd58c63143a14de7`。最终构建为 `d05c7d9d43f2383631d17b50ea6c8f1b8c2b40803dbbe66f3678c6c00e1b76fd`；两者逐个 package payload 比较仅 capabilities.md 的验收措辞变化，生产 Python/HTML 一致。其他各轮 hash 见最终状态，不按相同版本号冒充同一构建。最终 PR 的 CI 以对应提交的远端结果为准。

## 未测与使用条件

首次仍需用户准备主目录匹配的本地 Codex 项目，并在真实桌面聊天捕获当前控制连接；复用已有项目，不自动创建项目/分区。连接随桌面环境有效，桌面重启后可能需重新捕获。只验证上述 Windows、App Tools 版本和模型选择，不外推跨 Harness、busy insert/steer、桌面重启恢复、多主机、原生审批、长期在线、自有模型服务或其他 Desktop。详细操作见 [使用说明](../../usage.md#42-codex-desktop)。

## 归档和复核

[manifest.json](manifest.json)按文件记录原始来源 SHA256/字节数及脱敏后 SHA256/字节数；来源使用 `<TEST_ROOT>` 等占位符。`reports/` 保留各轮观察与测试日志，`native/` 保留这五个显式测试聊天的工具和消息记录，`snapshot/` 保留选定共享事实、输入回执、轮次元数据、检查点和标记。控制脚本仅供追溯，路径已替换，不能原样作为新环境启动命令。

排除真实 pipe 端点、凭据、reasoning 项、无关私人聊天、截图、Git 数据库、运行锁和二进制包。路径（包括多层 JSON 转义）替换为占位符；文本统一 UTF-8/LF，原本不可解码的日志字节使用替代字符，原字节 hash 保留。没有改写旧失败结论或错误 UUID。`.gitattributes` 保持归档字节不受 checkout 换行转换影响。

在本目录执行 `python verify.py` 可检查全量 [SHA256SUMS](SHA256SUMS)、来源清单、JSON 格式和相对链接。源文件仍在执行环境；脱敏归档无法独立还原原文，应将来源 hash 与执行环境核对，不能声称仅凭归档已重新验证原始字节。
