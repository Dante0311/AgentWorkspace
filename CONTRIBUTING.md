# 开发与验证

先阅读 [AGENTS.md](AGENTS.md) 和 [当前实现状态](docs/implementation.md)。产品行为以 [docs/design.md](docs/design.md) 为准，命令用法以 [docs/usage.md](docs/usage.md) 为准；发现不一致应修正或明确记录，不让文档和代码各自定义一套合同。

## 本地环境

需要 Python 3.11+ 与 Git。在仓库根创建虚拟环境，激活后安装开发依赖：

```sh
python -m venv .venv
# macOS / Linux
. .venv/bin/activate
# Windows PowerShell 使用：.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python scripts/check.py
```

必须先安装项目再运行测试：部分测试启动独立 Python 子进程，不能只依赖 pytest 的源码路径配置。

`check.py` 执行编译检查和 pytest。测试使用临时 Git 仓库与协议替身，不需要生产凭据，也不应修改用户真实 Workspace 或触发真实模型任务。

## 构建与安装检查

```sh
python -m pip install build
python -m build
python scripts/smoke_wheel.py dist
```

安装检查会在临时目录创建新的虚拟环境，以无依赖模式安装 wheel，再在源码之外运行 CLI、创建隔离 Workspace 和实例，并核对七个 Skill 与提示词资源。它不是 Desktop、模型、GitHub 或企微的实机验收。

CI 配置在 `.github/workflows/ci.yml`：Linux/Windows、Python 3.11/3.13 的本地测试，以及 wheel 构建和脱离源码安装。配置存在不代表远端作业已通过，应以对应 commit 的 Actions 结果为准。不向 CI 注入用户模型或 Bot 凭据，不自动发布。

## 变更范围

保持业务主流程直白，不为测试或未来扩展增加只转发的抽象层。修改公共命令时同步使用说明及对应 Skill；修改 Runtime 时保留 Desktop 与 CLI 的明确边界，不能静默改用另一执行者。

七个 Skill 随本包维护，业务自定义能力属于实例资产，不应随软件更新被重置。V2/V3、自动接管、统一聊天与智能记忆管理不在当前实施范围。

提交前检查差异和私密信息，只暂存本次明确文件；不要提交 `.aw-local`、凭据、真实会话或打包产物。贡献说明应记录变更范围、实际测试、未验证项以及影响的用户操作。

报告问题时附脱敏的版本、操作步骤和错误信息即可，不要在公开 Issue 中上传 Token、Bot Secret、完整私密会话或生产目录快照。项目目前没有选择开源许可证，也没有通过本文件新增 CLA 或其他授权条款。
