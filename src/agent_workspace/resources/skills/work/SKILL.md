---
name: work
description: 按需创建、修订、查看与交付正式工单，不规定业务工作流。
---

# work

只有使用者需要正式任务协调时使用，不为问答或运行平台补造工单。

```sh
aw -w sea work create --owner ui --content-file request.md
aw -w sea work list --owner ui
aw -w sea work show WORK_ID
aw -w sea work update WORK_ID --revision READ_REVISION --content-file revised.md
aw -w sea work deliver WORK_ID --revision READ_REVISION --content "完成依据" --ref "确定的产品版本或文件引用"
```

目标、接口、进度、方法均写正文。parent_id 表示拆分，不是所有依赖。
update/deliver 使用刚读取的对象 revision；冲突先重读，不覆盖他人正文。
交付前实际完成约定验收，工具不会替你发布产品。正式 Delivery 最多一份，交付后两者封存，变化使用新 Work。
