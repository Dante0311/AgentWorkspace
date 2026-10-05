# 开发接续 Checkpoint

这是软件开发恢复记录，不是产品实例 checkpoint，也不是第二份设计。

## 接续位置

日期：2026-10-05。本批分支 `feat/session-launch-and-desktop-projects`，基于 main `e55dfbf0f1cb2baf9e7c6bd0799a4f813c3d173d`，基线文件树 `e02a1b65df36015ee97e509fe3f28b654902cf41`。从已上传的 `deecc78` 源码检查点恢复，重建并核对完整 Git 文件树；main 的合并没有改变该文件树。

用户正在验收旧基线，本批只提交独立分支/PR，不合并 main、不发布版本、不改真实用户 Workspace。实际恢复请使用包含本文件的远端最新提交，不从聊天或旧 PR 推断进度。此前 HTTP 补丁已在本批整合，不需要再次套用。

## 本批确认范围与完成内容

1. 内网 HTTP 模型地址：通用模型配置、元数据探测和交接配置接受明确的 `allow_http`；CLI 提供 `--allow-http`，工作台按当前地址确认，地址或 Harness 改变后重新确认。共享校验拒绝 URL 凭据、查询参数、非法端口和控制字符，不按 IP 段猜测可信网络，不改 URL 后缀。只保存凭据环境变量名，不修改全局配置；HTTP 授权不能由管家扩大。
2. 无 Workspace 普通会话：`session.prepare/open/show` 与用户终端的 `session run` 复用原生配置并打开交互 CLI。界面 `/sessions` 在零 Workspace、无 Git 情况下可用；任务只传给原生进程，不写 AGENTS.md，不建 Workspace、管家、Binding 或平台 Message。原生客户端负责历史和交互权限，未自研会话循环或聊天界面。
3. 启动恢复边界：先持久保存固定请求，再打开系统终端；刷新只读、重复点击/回复丢失不另开终端。进程启动前失败可修正环境后继续原请求，启动已尝试或结果不明时不重放。普通会话启动记录不是原生 session ID。拒绝 `.cmd/.bat` 包装以避免任意任务经过 cmd 解释；无支持终端时返回原请求命令，不安装软件或静默换 Harness。
4. 持久 Agent 桌面项目与 Codex 分区：每个实际使用的桌面端保存一份本机显示/目录引用，默认 `AW · Workspace · Agent` 和 Codex 的 `AW · Workspace`。主目录始终是已有实例根，产品目录按需关联；不复制产品、不按每次会话创建项目、不覆盖用户布局。修改采用原 revision 核对。
5. 项目与分区的原生写接口当前未接入。界面和 `agent.desktop-project` 为用户与 Agent 返回同一份随包手动说明，明确 `manual_setup_required` 和 `native_project_verified=false`；保存本机引用不冒充桌面创建成功。不读写应用私有数据库，不把 CLI 当 Desktop，不以项目组织绕过单一 Binding。

只新增普通启动器和本机桌面引用两个小模块，CLI/HTTP 仍共用原命令分发。没有新增运行依赖、模型网关、通用插件/权限框架或自动更新服务。完整用法见 [session-projects.md](session-projects.md)，支持范围只维护在随包 [capabilities.md](../src/agent_workspace/resources/prompts/capabilities.md)。

## 开发验证

- 本机完整套件启用固定 Codex、Claude、CodeBuddy 原生客户端：**385 passed、14 skipped、0 failed，225.90s**。JUnit 与 pytest 一致；14 项是明确由独立 CI 执行的浏览器测试，不把重叠分组相加。最后另修正 macOS 终端参数测试的 OS 替身，使 Windows CI 不误走 Windows 分支；未改生产代码。
- 原生客户端参与既有工具/六向交接回归，模型响应来自回环协议夹具。本批普通会话还核对三个真实 CLI 的交互参数；仅 `--help` 参数接受检查，不把它称作完整对话验收。PTY 子进程测试使用明确的协议替身，验证真实 CLI 启动、目录、参数和凭据传递，Windows 单独检查直接 console 参数。
- 新回归覆盖 HTTP 确认/非法地址、模型配置/交接授权、普通请求重复启动和未知结果、实例目录拒绝、原生环境身份移除、项目引用竞争及不修改 Git/用户资料。
- wheel 构建与扩展 `scripts/smoke_wheel.py` 的真实隔离安装、零 Workspace 普通请求、HTTP 服务、安装恢复/重启、管家与新页面资源检查通过。Python/JavaScript 语法及文档检查在上传前再次核对。
- 本机 Chromium 导航被管理员策略阻止（ERR_BLOCKED_BY_ADMINISTRATOR），未绕过，也未宣称通过。新增 HTTP 确认、普通会话丢失回复/重复提交/刷新和桌面项目表单测试将与既有浏览器组在 GitHub CI 执行，当前提交结果必须单独读取。
- 已核对旧开发基线 `deecc78` 的 CI `37217477457` 和 Native SDK contracts `37217477463` 均为 success；这是旧基线，不代替新分支的 Windows/原生/浏览器验证。

## 提交与后续验证

上传时逐文件核对 Git blob，生成完整树并以真实 main SHA 为父提交；本机恢复用的临时提交不是可推送历史。先核对本 PR head 与 CI，失败先定位，不将取消/跳过当作通过。阶段成果需要同时保存 Git 提交和本文件。

本批需用户实机验证：Linux/macOS/Windows 的实际终端程序、原生登录与信任提示、自有 HTTP 网关兼容性、真实模型/强度、已有全局与项目配置继承，以及各 Desktop 中的手动项目/分区布局。没有访问用户截图里的网关、使用真实密钥或付费模型。macOS Terminal/已有终端服务可能不继承工作台临时环境变量，需在实际终端设置凭据；执行前仍检查，不将密钥放进脚本。

普通会话不具备平台持久身份、正式 Message/ACK 或跨 Harness 接续保证。完整 Desktop 自动化、SDK insert、CodeBuddy 模型目录仍按公开限制处理，不扩大本批范围。现有 Agent 与用户工作资料不自动升级覆盖；正式合并、发布、许可证及生产变更仍须另行明确授权。
