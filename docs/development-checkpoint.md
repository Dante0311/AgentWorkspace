# 开发接续 Checkpoint

软件开发恢复记录，不是产品实例 checkpoint，也不是第二份设计。

## 接续位置

日期：2026-10-04。唯一分支 `feat/native-runtime-maintenance`，草稿 PR #4，基于 PR #3。不合并 main、不重写历史、不发布版本。使用包含本文件的最新分支提交恢复，不从聊天或旧 PR 正文推断版本。

本轮从 `7be2eaf8ffbd48d3bf553453cf7e266b0232537a` 的 CI 源码制品恢复，核对树 `a4ec1fdfe09f07a922d80ae01adb0caaacedf41f`。已推送 `5e95bd14033163f770d9a3640690d44b1dc858f7`，保存安装恢复和 Windows 换行测试修复。此前提交、原生接口边界和验收证据保留在 Git 历史中。

## 本轮完成

- 安装器记录准确 wheel 摘要、目标、选装项、Python 版本与阶段，OS 锁排除并发安装。同一未完成安装可继续，已完成安装不重复 pip；不同包或位置、损坏记录、普通已有目录均不覆盖。不删除部分安装、不移动虚拟环境。
- 工作台发送先固定原请求 ID、正文与已观察 Binding，浏览器标签页按安装位置保存未确认请求。刷新不自动发送，查询只读；继续时发送尚未记录的原请求或补齐原回执，不能改内容、换 Binding 或新造 ID。关闭标签页可能丢失浏览器恢复记录，服务端回执仍在。不是所有高级命令的通用重放系统。
- 增加只读 `message.operation`，只读本机原回执并核对 Workspace；不联系远端、不创建消息，不暴露回执中的目标地址列表。实际补齐继续使用已有 reconcile。
- 发送方选择有效实例；管家授权读取真实可委托操作并勾选目标、显示已有授权与撤销；健康报告带入发布/桥接维修的原操作及 Binding/generation。服务端原权限和版本检查不减弱。
- 修复基线 Windows 两项测试的 CRLF/LF 比较问题，比较原始资源字节，不修改用户文件或生产编码。
- 新增真实 HTTP/Chromium 交互测试及独立 Linux CI job；浏览器库仅用于测试，不增加运行依赖。未增加 Harness、网关、调度框架或自动更新服务。

## 验证

- 本机完整套件启用 Codex、Claude、CodeBuddy 固定原生客户端：**281 passed、9 skipped、0 failed，271.79s**。9 项均为明确分开的浏览器测试，JUnit 与 pytest 输出一致，不累计重叠组。原生客户端使用回环模型夹具，不是付费模型、真实账号或 Desktop 验收。
- 安装/支持说明组 19 passed；将能力资源临时换为 CRLF 后支持说明 8 passed，结束后恢复原字节。消息/维护回归 36 passed；新回执及真实 CLI/HTTP 组 18 passed；这些已包含于完整结果，不相加。
- 从当前代码构建 wheel，通过扩展 smoke_wheel：真实 venv 建成后注入第一次包安装失败，用分发安装脚本恢复，重复安装不重建，第二个隔离安装读取原 Workspace 且 registry 字节不变。CLI、三管家、七 Skill、页面资源与巡检操作检查通过。
- 本机 Chromium 导航被管理员策略拒绝（ERR_BLOCKED_BY_ADMINISTRATOR），没有绕过。9 项真实浏览器测试将在 GitHub CI 的 Workbench / real HTTP and Chromium 执行，涵盖发送前/后的响应丢失、刷新、双击、只读查询、存储失败、授权撤销、维修版本变化和两个视口。当前尚不能宣称通过。
- Python 与页面 JavaScript 语法检查通过。上传前核对 Git blob 与本机已测试树；本提交 CI 独立检查，不沿用父提交结果。

## 接续

先核对本提交的浏览器、Linux/Windows、打包和 Native SDK 工作流；任何失败先定位，完成后将准确结果补到 PR，不把未验证说成已通过。操作步骤见 [运行与维护](runtime-and-maintenance.md)。未引入的新能力不扩大本轮范围。

已公开不支持的 Desktop 自动化、SDK insert 和 CodeBuddy 模型目录不在本轮扩展。支持范围仍只维护于随包 [capabilities.md](../src/agent_workspace/resources/prompts/capabilities.md)。真实账号、自有 API、生产 Git、企业微信、用户设备和长期运行需实机验收。正式合并、发布、许可证及生产变更另需授权。
