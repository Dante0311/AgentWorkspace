---
name: workspace
description: 创建、接入与查看协作空间，维护产品和好友关联。
---

# workspace

新建 Workspace 会建立 Steward、Sentinel、Maintainer 三份管家身份，不启动模型、巡检或 Work。接入已有空间不会重建小组或启动会话。首次使用可运行 `aw setup --open`，自行安装缺失的 Git/Harness 后重新检测。

```sh
aw workspace init sea /path/to/sea.git
aw workspace connect sea /path/to/sea.git
aw workspace connect cloud github:OWNER/REPO
aw workspace list
aw -w sea workspace show
aw -w sea workspace read --path knowledge/team-rules.md
aw -w sea workspace skills
aw -w sea workspace friend add --alias sbp --address /path/to/sbp.git
aw -w sea workspace project add --alias product --address /path/to/product
```

本地 init 创建 bare 权威仓和管家小组；connect 不修改已有仓库。新远端空间请先自行准备空仓，再通过首次配置页面初始化；旧 bootstrap-remote 保留低层预览格式，不自动补建管家。
创建返回 pending 时，修复访问后使用原简称和地址继续，不删除创建记录、不改成新实例。读取成功不是写权限验证；密码、Token 和私钥不写入地址或共享文件。
好友双方分别登记；凭据只从运行环境取得，本机绝对路径不写入共享关系。
移除关联用 remove --alias，不删除仓库或已有记录。无需预先建立 Definition 或 Work。

## 共同职责读取

`workspace.read` 用 `paths` 数组读取所属共享 Git 材料，返回完整正文、文件摘要和同一 revision；可用 40 位提交固定版本。仓库是 bare 也可读，不能把 bare 路径当普通文件夹。不要读取协议状态或本机私有文件来替代共同职责。

AGENTS.md 中的独立 `@workspace-read` 行在每次新会话进入时必读，按进入材料的 `required_workspace_read` 参数调用，不依赖本 Skill 被选中。失败或正文不完整要报告，不能把预检、指引存在或自动检查点当作模型已阅读。新的共同版本不会自动进入已有会话上下文；需要明确重读。产品业务规则仍在产品仓。
