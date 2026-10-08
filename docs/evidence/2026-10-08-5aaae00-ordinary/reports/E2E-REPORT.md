# 普通原生会话实机验收：最终报告

2026-10-08（Asia/Shanghai），批次 `2026-10-08-5aaae00-ordinary-0391c317`。**C 组主要路径取得 PASS_REAL：用户打开真实终端，完成两轮对话，原请求防重与正常退出通过。** 本批没有修改产品源码，没有重跑旧交接或外部消息。

| 验证项 | 实际结果与证据 |
| --- | --- |
| 固定软件 | AgentWorkspace `5aaae00520374b022e0c38fa21f312f8e08629ba`，沿用前批固定 wheel 安装；七个相关安装文件与工作树逐字节一致，规范化 CRLF/LF 后与固定 Git blob 一致。[来源核对](evidence/00-preparation.json)。 |
| 当前 Harness | 本机原生 Codex 已更新为 `0.162.0-alpha.2`，旧入口不再存在；记录新的可执行文件 hash，既有 ChatGPT 登录确认。配置及真实终端均显示 `gpt-6-luna / low`，不把客户端界面当服务端独立模型身份证明。 |
| 真实打开 | 用户点击已填好的“保存并打开原生 CLI”，Windows Terminal 实际打开。先出现 `TERM=dumb` 兼容提示，用户确认继续；没有跳过 TTY 检查、扩大权限或更改全局环境。[提示记录](evidence/02-terminal-term-warning.json)。 |
| 第一轮 | 真实终端显示读取 `test-note.txt`，返回正确随机标记 `ordinary-babe4683ba4b`、样本名 `blue-lantern` 及用途；与文件核对一致。[第一轮核对](evidence/03-first-native-response.json)。 |
| 第二轮 | 用户在同一终端追加上下文问题，返回 `blue-lantern / ordinary-babe4683ba4b`；截图包含连续两轮，第二轮没有可见工具调用。[第二轮核对](evidence/04-second-native-response.json)。 |
| 防重复 | 真实工作台只读刷新、继续原请求一次、整页刷新后，原请求文件字节不变，请求仍1，原生 PID仍48840且匹配测试任务的进程只有该PID。[操作前回执](evidence/05-before-duplicate-request.json)、[核对结果](evidence/06-duplicate-request-check.json)。未测试双击并发竞态或丢失响应故障注入。 |
| 普通会话边界 | 新空 ordinary-home 没有 Workspace registry、持久实例或 Binding；测试目录三个文件及其 hash 全程不变。原生 Harness 自身仍可保存历史、加载用户规则，不宣称完整规则隔离。 |
| 正常退出 | 用户通过 `/quit` 退出；原请求 `native_exited`、returncode=0，原生PID48840及包装PID24280均消失。[退出回执](evidence/08-native-exit.json)、[最终启动记录](evidence/08-final-launch-receipt.json)、[进程核对](evidence/08-native-exit-processes.json)。 |
| 工作台收尾 | 原生退出后，对本轮服务终端 Ctrl+C；进程和端口21940均无残留。服务终端返回1，不能称退出码为0的优雅关闭；没有强制杀进程。[服务审计](evidence/09-service-exit-audit.json)。 |

原启动请求 `session-59f8b4bd-c11b-42d1-9a5a-016ac30d981e` 全程复用。原生 session ID 未另行获取，工作台持续如实返回 `not_observed`；不用请求ID或PID冒充原生会话ID。真实对话依据来自用户截图及文件/进程/启动回执核对，而非 `native_running` 一项。

截图观察到2个完成的模型轮次，不等于精确 API 请求数或付费账单。没有第三条模型测试消息、平台 Message/ACK、企微或其他外部业务消息。没有新增或启动 Workspace、Agent、管家、Binding、业务巡检或 Bridge。

## 提示与未验证边界

控制者启动环境中 `TERM=dumb` 已查到，原生终端也显示同名兼容提示；尚未直接检查目标进程环境，不把继承来源推断升级为已定位产品缺陷。用户确认后两轮任务正常完成，原提示仍保留。

两次对话截图右下角另有2条 warnings。用户随后表示已看不到，详情未取得：[用户反馈记录](evidence/07-warnings-no-longer-visible.json)。不认定它们与 TERM 提示相同，不宣称警告已修复，也不为追赶临时提示重启或追加模型轮次。

本批没有验证其他 Harness、自有模型服务、Desktop 自动建会话/交接、桌面项目手动准备、远端 Git、长期运行或完整 A–J；没有改变 E2E-001 busy steer 残余和 E2E-002 WorkBuddy 启动失败的上批结论。

复核见[控制者核对记录](../review/LEAD-REVIEW.md)。本批是用户参与、控制者核对，没有安排第二执行者独立复核。用户原始截图含机器路径，保留在本机 private 并记录 hash；公开归档提供内容摘录和核对结果，不放未脱敏图片。控制 Token 日志排除。

## 过程记录（以下保留各阶段当时状态）

# 普通会话人工配合验收

基线 5aaae00；沿用已验证隔离安装。七个相关文件安装字节与工作树一致，规范化换行后与固定 Git 提交一致（Git LF、安装 CRLF）。新空 ordinary-home、新虚构 product。当前原生 Codex CLI 0.162.0-alpha.2，既有 ChatGPT 登录确认。普通会话预计两轮 gpt-6-luna/low，仅只读测试目录。

当前 PREPARED：未创建普通会话请求，模型调用 0，尚未取得真实终端证据。未创建 Workspace、管家、持久 Agent 或 Binding。

## 真实终端已打开，等待兼容确认

用户点击原页面启动后提供 Windows Terminal 截图：Codex 提示 TERM=dumb、TUI 可能不正常，等待 y/N。启动回执与当前 PID 已保存于 evidence/02-terminal-term-warning.json。该截图证明真实窗口及兼容提示，不证明已请求模型或模型就绪。控制者当前命令环境 TERM=dumb；可能由启动链继承，尚未直接核对目标进程环境。保留原请求，不重开或绕过 TTY 检查。

## 第一轮真实原生回应

用户提供同一测试目录的 Codex CLI 截图，显示真实 Get-Content 读取 test-note.txt，以及正确 verification_code、sample_name 和用途。两字段与文件内容一致；三个初始测试文件摘要及文件列表未改变。原启动请求仍 native_running。界面显示 GPT-6-Luna low，两条 warnings 详情尚未查看，不推断原因。未创建 Workspace/Agent 目录。第一轮读文件取得实机证据，第二轮及重复点击防重尚待验证。

## 第二轮上下文延续

用户在原终端输入第二条请求后，返回 blue-lantern / ordinary-babe4683ba4b，与第一轮一致。截图同时包含前后两轮，第二轮未显示新的工具调用。原请求/PID保持，测试文件列表和摘要未改变，未创建 Workspace/Agent。两轮真实交互已取得限定通过；原生 session ID 未另行获取，不伪造其值。两条终端 warnings 尚待展开。

## 原请求重复操作

管理端在真实工作台依次点击只读刷新、继续原请求一次、整页刷新；原请求 ID、native_running、PID 48840 保留。操作前后本机启动记录字节不变，请求总数仍1，OS匹配本次测试任务的原生进程仍只有48840。没有创建另一请求或记录新的启动尝试。证据05、06。工作台继续保留 native_session=not_observed，没有把 PID 当原生会话 ID。

## 临时警告的证据边界

用户反馈“看不到了，没警告了”。此前两条 warnings 的内容未取得；仅记录其随后不再显示，不推断警告原因或已经修复。TERM=dumb 的启动兼容提示有独立截图，仍保留；不擅自认定它与这两条 warnings 相同。两轮对话和原请求防重的已验证结果保持。下一步正常退出原生会话并核对启动记录及进程。
