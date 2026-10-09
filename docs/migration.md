# 从 Playbook 迁入独立仓

## 维护归属

目标仓库：[Dante0311/AgentWorkspace](https://github.com/Dante0311/AgentWorkspace)。本仓由用户创建，迁入时已为公开仓库；此次操作不改变可见性，不选择许可证，不创建正式 Release。

产品设计、源码、七个 Skill、使用文档、正式测试和构建文件在本仓维护。开发过程与详细验证记录现统一维护于 [AW-Workspace 开发仓](https://github.com/Dante0311/AW-Workspace/blob/main/development/README.md)，原始迁仓验证保留在该仓的历史归档。Playbook 在核对目标提交后收口为仓库入口和简短来源关系，不保留另一份活动实现。

## 来源快照

```text
source_repository          Dante0311/Playbook
source_commit              5022960e0509f5cc984ff19619ef8e8bf912c0fc
source_directory           drafts/git-native-agent-workspace/
source_tree                24e0154f9d3a65c3c1ecfc79c0f35cfd45f5dc62
source_files               43
target_initial_commit      687adb02634e99f256ebbea7582206dbd89d0bb7
implementation_version     0.1.0a1
```

[源目录固定版本](https://github.com/Dante0311/Playbook/tree/5022960e0509f5cc984ff19619ef8e8bf912c0fc/drafts/git-native-agent-workspace)是迁移依据。交付的源码 ZIP 解包并计算 Git 文件树后，与上述 source_tree 完全一致。迁仓保留目标仓原始初始化提交，在其后增加项目快照，不强推、不导入整个 Playbook 历史。

`src/` 与 `tests/` 逐字迁入，既有 `scripts/check.py` 不变；没有在迁仓过程中重构 Runtime 或修改控制权实现。调整仅涉及独立仓的 README、开发与迁仓说明、包链接和初始化检查配置，以及已讨论的 V3 方向。

## 文档与初始化调整

README 说明定位、预览状态、安装、三种空间、接入限制及开发入口。AGENTS.md 改为本仓开发规则，不依赖 Playbook 父路径。`pyproject.toml` 增加正式仓库、文档和 Issue 地址，保留包名、命令和版本。

增加开发指南、CI、本地 wheel 安装检查及源码分发清单。CI 仅执行隔离测试和构建，不自动发布；GitHub Actions 能否运行及结果需要实际核对。

V3 记录同一持久身份下的多事务会话方向。它没有放开 V1 唯一入口，也没有在代码中建立第二套身份或会话模型。原始 alpha 测试记录保留，迁仓重验另见 [validation-migration.md](https://github.com/Dante0311/AW-Workspace/blob/c37ef2e92189adf357dc0e351aff48da9308377f/development/archive/2026-10-09-product-repository/docs/validation-migration.md)。

## 更早来源

原设计来自 [Playbook f803dc64](https://github.com/Dante0311/Playbook/blob/f803dc64f82885999efde707e3d252815012c9c1/drafts/git-native-agent-workspace/README.md)。开发约定采纳自 [Code Style](https://github.com/Dante0311/Playbook/blob/f803dc64f82885999efde707e3d252815012c9c1/standards/code-style.md) 和 [Agent Rules](https://github.com/Dante0311/Playbook/blob/f803dc64f82885999efde707e3d252815012c9c1/AGENTS.md)，必要规则已在本仓表达，外部链接只用于追溯。

这些来源链接可能需要相应仓库访问权限；运行与开发本工具不需要访问它们。本次没有迁入 Playbook 的其他公共资产、源仓根 `.git`、NRCHome 上传包、SBP/Agent-Link 全套代码、用户会话、凭据或本机配置。

这是软件开发仓的迁移，不是用户 Shared Workspace 的迁移，也不是 V1 → V2 的身份迁移。后续归属、地址与数据格式变化仍需明确设计，不能借 App 更新静默转换。
