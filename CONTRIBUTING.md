# 开发与验证

先阅读 [AGENTS.md](AGENTS.md) 和 [当前实现状态](docs/implementation.md)。产品行为以 [docs/design.md](docs/design.md) 为准，命令用法以 [docs/usage.md](docs/usage.md) 为准；发现不一致应修正或明确记录，不让文档和代码各自定义一套合同。

团队的问题、调查、交接和详细验收材料见 [AW-Workspace 开发入口](https://github.com/Dante0311/AW-Workspace/blob/main/development/README.md)。本机开发工作树放在该仓的 `.local/worktrees/`；产品功能、正式测试与构建变更仍提交本产品仓。

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
python scripts/build_npm.py dist
python scripts/smoke_npm.py dist
python scripts/smoke_wheel.py dist
```

npm 是正式用户安装路线，当前产物面向 Windows x64，需要 Node.js 22+ 和 npm。构建脚本把 wheel 与固定版本的 CPython 嵌入式运行时一起打包，先核对 Python 官方发布的 SHA-256；运行时缓存和最终产物不入 Git。包内保留 Python 的许可证文件，`build.json` 记录 wheel 与运行时的来源和校验值。模板使用 `private: true`，本轮只构建 `.tgz`，不向 npm Registry 发布，也不新增项目许可证。

npm 安装检查在源码外离线安装实际 `.tgz`，从 PATH 排除系统 Python，运行 CLI、隔离 Workspace 和真实 HTTP，再替换程序并确认原用户数据保留。wheel 检查仍用于底层 Python 包：创建临时虚拟环境、安装和核对资源。两者均核对七个 Skill；这些检查不代替真实 Desktop、模型、GitHub 或其他渠道验收。

CI 配置在 `.github/workflows/ci.yml`：当前只自动验证 Windows，包括 Python 3.11/3.13 的本地测试、Chromium 工作台测试、npm 与 wheel 构建及脱离源码安装。Linux 原生 SDK 工作流只保留手动入口，不随 PR 自动运行；当前不安排 Linux 兼容性回归。配置存在不代表远端作业已通过，应以对应 commit 的 Actions 结果为准。不向 CI 注入用户模型或 Bot 凭据，不自动发布。

## 变更范围

保持业务主流程直白，不为测试或未来扩展增加只转发的抽象层。修改公共命令时同步使用说明及对应 Skill；修改 Runtime 时保留 Desktop 与 CLI 的明确边界，不能静默改用另一执行者。

七个 Skill 随本包维护，业务自定义能力属于实例资产，不应随软件更新被重置。用户显式强制接手属于本轮范围；自动抢占、V2/V3、统一聊天与智能记忆管理不在当前实施范围。

提交前检查差异和私密信息，只暂存本次明确文件；不要提交 `.aw-local`、凭据、真实会话或打包产物。贡献说明应记录变更范围、实际测试、未验证项以及影响的用户操作。

报告问题时附脱敏的版本、操作步骤和错误信息即可，不要在公开 Issue 中上传 Token、Bot Secret、完整私密会话或生产目录快照。项目目前没有选择开源许可证，也没有通过本文件新增 CLA 或其他授权条款。
