# 当前检查点

固定 AgentWorkspace 5aaae00，现有已验证独立安装。新 ordinary-home，仅虚构 product，当前真实 Codex 0.162.0-alpha.2 / ChatGPT 登录 / gpt-6-luna / low。

工作台 http://127.0.0.1:21940/sessions 已在应用内打开，参数通过真实页面填写。已点击无模型目录检查；没有由控制者点击保存/启动，没有准备普通会话请求或启动模型。下一步由用户点击“保存并打开原生 CLI”一次并报告原生终端画面。

服务 exec session 12486，当前等待用户期间保留运行；服务 PID 见 evidence/01-workbench-ready.json。控制 URL 仅在 private/workbench.log，本机控制 Token 不进入报告或公开截图。不要重新创建普通会话或重复启动，先读本轮 ordinary-sessions 账本并检查原页面。

更新：用户已点击启动，真实 Windows Terminal 停在 TERM=dumb 的 Continue anyway? [y/N]。原请求及 PID 见 evidence/02-terminal-term-warning.json。下一步用户在同一终端输入 y 回车，观察后续原生提示；不新建请求，不自动接受权限或登录。尚无模型回答。

更新：第一轮真实终端回应已由截图和文件校验确认，证据03。当前原生 PID 48840、原请求不变。下一步用户在同一终端输入第二条只依赖上下文的简短请求；不新建/重开。终端底部有2条 warnings，后续收尾前按需要让用户展开查看，尚未确定含义。

更新：第二轮上下文回应已通过（证据04），只读刷新/继续原请求/整页刷新没有改变请求字节或PID，匹配原生进程仍1（证据05、06）。下一步用户在现有终端按F2展示2条warnings；不发第三条模型消息，不关闭终端，待核对后正常退出并停止本轮服务。

更新：用户反馈两条 warnings 不再显示，详情未取得（证据07），不扩大排查或重新启动。下一步用户正常退出当前原生会话；随后控制者只读核对 session-59f8b4bd-c11b-42d1-9a5a-016ac30d981e、PID48840及wrapper24280，再正常停止本轮工作台服务12486。

## FINAL：本组已完成

原生会话 native_exited，returncode=0；PID48840及包装24280消失。工作台exec12486已Ctrl+C退出，工具exit1，端口21940及本轮进程无残留，不假称退出码0。证据08、09。两轮对话/原请求防重/无Workspace/文件不变通过；TERM提示与两条未取得详情的warnings保留。没有后续运行或监控，旧数据未改。后续新测试需单列批次，本请求禁止重放。
