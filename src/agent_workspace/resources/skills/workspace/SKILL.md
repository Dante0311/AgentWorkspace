---
name: workspace
description: 创建、接入与查看协作空间，维护产品和好友关联。
---

# workspace

环境级操作不隐式创建实例、会话或 Work。

```sh
aw workspace init sea /path/to/sea.git
aw workspace connect sea /path/to/sea.git
aw workspace connect cloud github:OWNER/REPO
aw workspace list
aw -w sea workspace show
aw -w sea workspace friend add --alias sbp --address /path/to/sbp.git
aw -w sea workspace project add --alias product --address /path/to/product
```

本地 init 创建 bare 权威仓；connect 不修改已有仓库。远端 GitHub 仓须先存在，空仓通过 workspace bootstrap-remote 初始化。
好友双方分别登记；凭据只从运行环境取得，本机绝对路径不写入共享关系。
移除关联用 remove --alias，不删除仓库或已有记录。无需预先建立 Definition 或 Work。
