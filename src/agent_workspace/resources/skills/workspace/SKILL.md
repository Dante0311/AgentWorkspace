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
aw -w sea workspace friend add --alias sbp --address /path/to/sbp.git
aw -w sea workspace project add --alias product --address /path/to/product
```

本地 init 创建 bare 权威仓和管家小组；connect 不修改已有仓库。新远端空间请先自行准备空仓，再通过首次配置页面初始化；旧 bootstrap-remote 保留低层预览格式，不自动补建管家。
创建返回 pending 时，修复访问后使用原简称和地址继续，不删除创建记录、不改成新实例。读取成功不是写权限验证；密码、Token 和私钥不写入地址或共享文件。
好友双方分别登记；凭据只从运行环境取得，本机绝对路径不写入共享关系。
移除关联用 remove --alias，不删除仓库或已有记录。无需预先建立 Definition 或 Work。
