# 独立仓迁移验证

本记录对应从 Playbook `5022960e0509f5cc984ff19619ef8e8bf912c0fc` 迁入独立 `Dante0311/AgentWorkspace` 的初始化变更。软件仍为 `0.1.0a1`，本轮不是正式 V1 或外部 Runtime 的验收。

## 源码范围与完整性

原项目共 43 个受版本控制文件，来源目录为 `drafts/git-native-agent-workspace/`。迁移前将本地源码包按原路径构建 Git tree，其 SHA 与 GitHub 来源目录一致：

```text
source_tree   24e0154f9d3a65c3c1ecfc79c0f35cfd45f5dc62
src_tree      0469399f8adf5cfb59246ea84f9bc961176f1b7b
tests_tree    cfbe70ecb189377f6a7d205cb89c3364bc6b6930
```

本轮未修改 `src/` 的 25 个实现/资源文件、`tests/` 的 8 个测试文件及原 `scripts/check.py`。新仓的源码和测试 tree 与上述来源相同，包括七个 Skill、四份提示词及工作台 HTML。没有导入 Playbook 的其他项目、用户运行数据、凭据或整个仓库历史。

有意变化的内容是独立仓 README/开发入口、包元数据中的项目地址、源码发行包清单、迁仓文档、V3 多事务会话方向说明，以及 CI 和 wheel 安装检查。V3 内容仅为文档，不改变 V1 的唯一执行入口。

## 本轮实际执行

环境为 Linux、Python 3.13.5、Git 2.47.3。全部测试使用隔离临时目录及协议替身。

| 检查 | 结果 |
| --- | --- |
| 安装迁入项目后运行 `python scripts/check.py` | 编译通过，47 项测试通过，pytest 用时 42.09 秒。 |
| Wheel 构建 | 通过，运行时仍无必需第三方依赖。 |
| 独立安装检查 | 新建临时虚拟环境，无 PYTHONPATH/PYTHONHOME/AW_* 继承，在源码之外安装并调用 CLI，通过。 |
| 安装后资源 | 七个 Skill、四份提示词、工作台 HTML 可读取。 |
| 本地 Git 冒烟 | 安装后的 CLI 创建临时 Workspace、创建及列出实例，通过。 |

测试前必须安装项目。首次直接运行测试时，四个子进程测试因未安装包而找不到模块；完成开发安装后重新运行全部 47 项测试通过，没有以修改业务代码或忽略测试绕过环境问题。此要求已写入开发说明和 CI。

## 自动检查入口

新增 `scripts/smoke_wheel.py`，重复执行独立安装与资源检查；`MANIFEST.in` 确保源码发行包包含文档、测试协议替身及检查脚本。

GitHub Actions 配置覆盖 Linux/Windows、Python 3.11/3.13，并单独构建 sdist/wheel、执行独立安装检查。仅使用读取仓库权限，不注入生产模型或 Bot 凭据，不自动发布。**配置存在不等于远端已通过，实际状态以该提交的 Actions 结果为准。**

## 仍未证明的范围

本次没有重新验收真实 Codex Desktop、真实模型登录与调用、企业微信 Bot、生产 GitHub Message Backend 或长期断线恢复；也没有执行浏览器到本机工作台的新增端到端测试。旧版原始验证见 [validation.md](validation.md)，未验证边界继续保留。

代码迁仓写入 GitHub 不等于应用自身 GitHub Backend 已通过生产测试；Linux 本地测试不等于 Windows 实机接入已通过。仓库公开不替代许可证选择，也不表示已经发布 Release 或 PyPI 包。
