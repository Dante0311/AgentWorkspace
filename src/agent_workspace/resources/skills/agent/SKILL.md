---
name: agent
description: 创建、完善和管理持久实例，以及显式发布选定的共享资产。
---

# agent

工作根属于本实例，不是产品目录。创建和取得执行权是两件事。

```sh
aw -w sea agent create helper --description "构建排错助手"
aw -w sea agent create ui --definition definitions/ui
aw -w sea agent connect helper --directory /path/to/another-copy
aw -w sea agent list
aw -w sea agent show helper
aw -w sea agent configure helper --config @runtime.json
aw -w sea agent versions helper
aw -w sea agent update helper --revision SOURCE_COMMIT
aw -w sea agent sync helper
aw -w sea agent upgrade-tools helper
aw -w sea agent promote helper --path AGENTS.md --destination definitions/build-helper
aw -w sea agent archive helper
aw -w sea agent unarchive helper
```

Definition 可选，职责可在本目录逐步完善。没有来源是正常状态。自然语言初始化参见 `.aw/prompts/initialization.md`。
工具升级不重置自有职责和资料。update 只更新选定来源；报告本地差异时先交由使用者处理，不自动合并。
提升只发布用户明确选择的文件，不整体合并实例分支，不删除原资料，不自动替别人更新。
归档前先 handoff；解除归档不自动进入。已有外部目录可用 agent import --from-directory --asset 明确导入选定文件，原目录不改变。
七个内置 Skill 不限制实例自己的 Skill 数量。
