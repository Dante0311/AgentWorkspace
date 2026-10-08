# 本批修复检查点

基线：`Dante0311/AgentWorkspace@71bd0581a0c509c2ddc9daa2b8e545891cedc4b0`。版本 `0.1.0a1`。本地工作分支 `fix/e2e-residuals-20261008`，仅保存本地成果，没有推送、合并、发布或操作用户电脑。

## 已保存的独立代码提交

| 本地提交 | 内容 |
| --- | --- |
| `45a35fd` | 直接 reconcile 的调用身份和原回执归属核对。 |
| `886755e` | busy steer 的顶层 turnId 与完成事件匹配。 |
| `b55b606` | 明确 Node hashbang 的无扩展名 Windows CLI 识别。 |
| `79fef1a` | 便捷配置接受并保留模型 ID 的方括号。 |

这些是本地验证分支上的提交号，不是已经上传的远端提交。源/测试/脚本已按真实 upstream Git 子树校验；为离线验证构建的起始快照没有完整历史证据，不能把它推送为 main 或整树替换仓库。交付使用四笔修复及文档的 format-patch，在真正的 upstream 独立 worktree 应用；原有验收文件和其他人提交均保留。`implementation.md` 只增加开头的本批状态链接，文档补丁使用窄上下文，已核对当前远端文件的对应头部。

## 实际已运行

以下均在安装好的测试环境执行；源码子进程能正确导入该隔离副本。固定 SDK：Claude 0.2.163、CodeBuddy 0.3.267。没有访问真实模型服务。

```sh
python -m pytest tests/test_reconcile_authority.py tests/test_messages.py tests/test_maintenance.py tests/test_dispatch_efficiency.py -q
python -m pytest tests/test_local_state.py tests/test_e2e_terminal_state.py tests/test_runtime.py tests/test_transfer_safety.py tests/test_desktop_runtime.py -q
python -m pytest tests/test_codebuddy_windows_entry.py tests/test_native_sdk.py tests/test_native_failure.py tests/test_sdk_metadata.py -q
python -m pytest tests/test_harness_config.py tests/test_http_model_profiles.py -q
python -m pytest tests/test_support_guidance.py -q
```

结果分别为 101、84、39、117、8 passed。原生链通过 `AW_TEST_CODEX` 明确指定离线原生客户端后，单独执行 `tests/test_native_transfer.py::test_native_transfer_and_message[codex-codex]`，1 passed。该客户端的模型响应是回环测试夹具，不使用官方登录。打包与 `scripts/smoke_wheel.py` 的 Linux 隔离安装通过。最后仅 message Skill 的授权说明变化，最终 wheel 的全部 Python 和其他资源与成功冒烟构建一致；精确差异见 `wheel-payload.json`，未重复跑整套测试。

## 剩余项

1. 新 Windows 隔离数据上的真实 busy steer 回执/事件/终态核对，使用原有批准配置；不修写旧账本来制造通过。
2. WorkBuddy 原选无扩展名入口只读首行确认，再分别检查启动兼容、同入口认证及真实接手；没有原文件首行和 Windows 执行证据时不宣称 E2E-002 关闭。不得复制桌面凭据或释放旧 HY 资格。
3. 带方括号模型 ID 的便捷入口实际选用验证；不为测试改模型名称或服务。
4. Windows 清理失败的现场目录条目、链接属性和自有进程证据；原因仍未确定。不要先删目录、加忽略异常或重跑 A–J。
5. 共同职责引用、共享 Skill、项目分区自动准备另批实施；V2 独立 Agent 不在本批。

复测报告按新批次写入仓库，保持旧失败、撤回结论及未验收项原样。不将测试代码的模拟 Windows 平台选择当成 Windows 内核验收。
