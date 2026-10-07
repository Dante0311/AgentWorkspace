# AgentWorkspace 本地 E2E 阶段报告

2026-10-06 00:34（Asia/Shanghai）。**环境组与 A 组当前无模型部分完成；完整 A 组和真实模型 E2E 尚未完成。模型闸门 CLOSED。**

固定提交：`1258b622c474beb73f13234c0f00672d8d5b5bbb`，版本 `0.1.0a1`。正式根：`${E2E_ROOT}`。

源码起初干净，最终仅用户新增 `docs/AgentWorkspace-local-E2E-prompt.md` 未跟踪；本会话未修改、暂存或提交源码。规程已完整读取，[副本](evidence/AgentWorkspace-local-E2E-prompt.md) SHA256 为 `b3156c3bddf9d2573f5a99b4fc120fa422283554e6369186efaf66b379803575`，不属于产品基线，也未进入构建。

旧准备根 `${SOURCE_REPO}-E2E\2026-10-06-1258b62` 原位保留。正式根调整发生在任何真实模型请求前；没有搬动 venv。固定源码归档和 wheel 校验后复用，在正式根重新隔离安装。来源与旧证据路径/hash见 [00-provenance.json](evidence/00-provenance.json)。

## 实际用例

| 编号 | 预期与实际结果 | 状态 | 原始证据 |
| --- | --- | --- | --- |
| G0-01 | 基线 SHA 一致；隔离目录归属确认；源码最终只多用户规程；未写生产数据 | PASS_REAL | 00-provenance、A17、A22；初检在旧根 evidence |
| G0-02 | 只读发现 OS/Python/Git/Harness/SDK/Desktop/终端/浏览器；安全版本命令通过，无登录或模型调用 | PASS_REAL | 00-provenance 引用旧根 04–11、25–26 |
| A-01 | 固定快照构建 wheel；分发 installer 安装到正式 app；源码外 version/help/scan/list 成功，模块来自正式 site-packages，非 editable | PASS_REAL | A01–A06、A19–A20 |
| A-02 | 七个 Skill、三份定义及全部随包资源与固定源码一致 | PASS_REAL | A14-package-resources |
| A-03 | 绝对 aw 路径、显式 ordinary-home，setup --port 0 --open 实际打开 Chrome；首次配置、普通会话、支持说明和空数据工作台可访问 | PASS_REAL | A07、A09–A12 DOM/JPG |
| A-04 | UI 明确提示 CodeBuddy PATH 未发现、Claude/CodeBuddy SDK 缺失与 Desktop 限制，没有自动调用模型 | PASS_REAL | A09、A10 |
| A-05 | 无授权 GET state/commands、无授权 POST setup.scan、错误 Token 均 401；有效 Token+外部 Origin 为403；合法只读 state及静态页面200 | PASS_REAL | A08-http-boundaries；真实本机 HTTP |
| A-06 | 同 wheel/目标/选项重复安装成功，标记字节不变，未再运行 pip 安装 | PASS_REAL | A13、A14 |
| A-07 | 仅 disposable/recovery-app 内真实 installer PID 220788 在 installing+pyvenv.cfg 后被定向终止；保留记录，同请求原位续装成功，测试保留文件仍在 | PASS_REAL | A15a–A15d；真实组件的受控故障注入，非 Mock，仅覆盖此中断点 |
| A-08 | 测试服务与标签页清理；最终正式根无存活可执行进程，59076 无监听 | PASS_REAL | A16、A17；清理通过不代表优雅退出 |
| A-09 | 正常停止、第二独立安装复用已创建身份/数据 | NOT_RUN | 本组未创建身份；隐藏控制台 CTRL_BREAK 未能停止，最终定向终止本轮进程树，不算正常停止通过 |
| B–J | 模型、真实终端对话、Workspace/Agent、Message/ACK、交接、管家、资产/Work、远端 Git、企微 | NOT_RUN | 按 Lead 下一组派发；未用模拟结果代替 |

本组无已确认产品 FAIL，也无 PASS_SIMULATED 用例。完整 Desktop 自动化、Claude/WorkBuddy Desktop 自动控制、SDK insert、CodeBuddy 模型目录等依随包说明为 UNSUPPORTED；本次仅证明说明可见。一次 full-page 截图超时后 viewport 截图成功，未将工具观测问题记为产品缺陷。

所有命令、退出码、时间与原始输出见 [command-index.json](evidence/command-index.json)。浏览器证据为实际 DOM/截图。安装中断的非零退出为刻意注入；服务最终退出1为定向清理结果，均未包装成正常退出。

## 版本、安装与可用性

| 项目 | 实测事实 |
| --- | --- |
| OS / Shell | Windows x64 10.0.22621.0；PowerShell 7.6.5 |
| Python / Git / Node | 本轮 Python 3.11.4；Git 2.52.0.windows.1；Node 22.19.0。另发现 Python 3.12，未切换 |
| wheel | `dist/git_native_agent_workspace-0.1.0a1-py3-none-any.whl`，SHA256 `0ec257b1ffc14ede077f023415fa52f013f2a83ed04042d31be1baa9eeafb048` |
| 安装来源 | 固定提交 Git archive；旧根独立构建环境从 PyPI 下载 setuptools 84.0.0；正式安装通过 dist/install.py + SHA256SUMS，核心离线无运行时依赖 |
| 正式安装 | `app/Scripts/aw.exe`；包0.1.0a1、venv自带pip23.1.2/setuptools65.5.0；pip check通过；未装extras |
| Codex | npm CLI 0.129.0，PATH首选.cmd；已发现并验证包内真实exe。App内另有0.160.0，分开记录、不混用 |
| Claude | npm CLI 2.1.11，bin=cli.js、PATH为.cmd。普通启动器不执行.cmd/.bat，尚未确认该普通入口可用的Claude原生exe |
| CodeBuddy / SDK | CodeBuddy CLI在PATH未发现；所查全局Python与正式app均缺Claude/CodeBuddy SDK，不推断全机无其他安装 |
| Desktop / Terminal | 系统包发现Codex26.930.3930.0、Claude2.2553.1.0、Windows Terminal1.21.2911.0；未做Desktop控制/真实TTY验收。WorkBuddy未确认 |
| 浏览器 | Chrome实际UI访问通过；Edge文件版本144.0.3719.82，未操作Edge |
| 磁盘 | 初检C约469GiB、D约715GiB可用，属于当时快照 |
| 认证 | NOT_RUN / unchecked；未读auth/config正文、未登录或查询模型目录 |

实际外部服务仅 PyPI 构建依赖下载。没有被测模型、Git远端或企微请求。没有改全局Python、PATH、Git/Harness配置；未对全机配置做独立前后哈希审计。控制Token未输出或持久保存，截图URL无Token。

## 当前现场

服务曾使用 PID226972、`127.0.0.1:59076`；现在已停，端口已关闭，浏览器测试标签页已关。没有未决 request ID、原生 session、Binding、模型巡检或桥接。

`data/ordinary-home` 仅有installation/maintenance运行痕迹，workspace list为空，无registry/ordinary-sessions。持久测试另预留 `data/workspace-home`，尚未创建。`fixtures/fictional-product` 已有中性AGENTS和随机标记README，文件哈希见A21，尚未被模型读取。正式app、一次性恢复安装、旧根安装与全部证据原位保留。

## Lead 收口复核

独立复核已完成，见 [A-EVIDENCE-REVIEW.md](../review/A-EVIDENCE-REVIEW.md)。复核方抽查来源哈希、安装输出、页面截图、HTTP 拒绝、中断续装和清理证据，认可上表已完成项目的范围。Lead 已核对最终主报告：正常关闭、第二安装复用数据均保留 NOT_RUN，未把 A 整组或完整 E2E 标为通过。无需重跑已完成项目。

另有一处静态文档矛盾：固定基线 docs/first-use.md:55 仍写 HTTP 仅限回环，与 docs/session-projects.md 及首次配置页面允许逐配置明确确认非回环 HTTP 的说明不一致。记录在 [PREFLIGHT-REVIEW.md](../review/PREFLIGHT-REVIEW.md)，本轮未修改源码或文档；这不等同于本次 HTTP 控制接口测试失败。

执行会话 gpt-6.1-sol / medium；复核会话 gpt-6.1-sol / high。两者本组工作已结束，等待 Lead 获得用户的被测服务、模型和预算确认后继续，不自动升级模型。
## 给 Lead 集中确认的下一步

建议先选 Codex 普通CLI，在虚构产品目录做**最多两轮只读短任务、零自动重试**：第一轮读取README并报告随机标记，第二轮在同一原生会话复述。此建议尚未获得模型调用授权。

已验证版本0.129.0的真实入口候选：

```text
${USER_HOME}\AppData\Roaming\npm\node_modules\@openai\codex\node_modules\@openai\codex-win32-x64\vendor\x86_64-pc-windows-msvc\codex\codex.exe
```

需要用户集中确认/准备：

1. Harness及确切入口、服务Base URL原样值或明确官方账号、模型ID、推理强度、凭据环境变量名、两轮与费用预算；非回环HTTP另行明确同意明文传输。
2. 密钥由用户在实际启动工作台/原生CLI的本机终端设置，只提供变量名，不粘贴聊天；不能把已有官方账号令牌自动发送到自有网关。所选Harness需由用户自行完成必要登录。
3. Windows Terminal已安装，但本轮只能控制浏览器，原生终端的信任/登录/真实响应核对可能需要用户实际操作反馈，不能以PID代替。
4. 若下一组选择Codex→Claude，在新的隔离安装目标按项目固定extra补 `claude-agent-sdk==0.2.163`；不要改变现有app安装标记选项。若选择CodeBuddy，用户先提供/安装其真实CLI，再按需补 `codebuddy-agent-sdk==0.3.267`。当前不代装所有Harness。

这些缺项使相关后续用例 BLOCKED，不是产品“不支持模型”的结论。B及后续由Lead下一组派发，不继续扩测。执行会话沿用最新设置 gpt-6.1-sol / medium，与被测模型配置分开。

![空Workspace工作台实机截图](evidence/A12-root.jpg.omitted.md)


## H/A最终补充（2026-10-07）

H已通过本机引用真实UI保存/改名/刷新/第二安装保留；两服务Ctrl+C后exit1，随后进程0/端口关闭。A09优雅finally退出仍NOT_VERIFIED，未补适配，不登记为新产品缺陷。原A阶段定向清理记录不改写。见[H事实](evidence/H10-final-facts.json)、[最终当前汇总](E2E-REPORT.md)。
