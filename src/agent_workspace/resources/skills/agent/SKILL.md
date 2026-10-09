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
aw -w sea agent configure helper --config @native-connection.json
aw -w sea agent versions helper
aw -w sea agent update helper --revision SOURCE_COMMIT
aw -w sea agent sync helper
aw -w sea agent upgrade-tools helper
aw -w sea agent promote helper --path AGENTS.md --destination definitions/build-helper
aw -w sea agent archive helper
aw -w sea agent unarchive helper
```

Definition 可选，职责可在本目录逐步完善。没有来源是正常状态。自然语言初始化参见 `.aw/prompts/initialization.md`。

Codex 模型选择在实例根 `runtime.json` 的 `codex` 对象中保存 `model` 和 `effort`，自动启动要求两者明确填写。Definition 可提供此文件作为创建模板；实例此后独立维护。通用 configure 接收原生连接配置；原有 model / effort 参数会存入实例文件。不要将根配置当成本机连接文件，也不要从发起者设置补值。保存不启动模型，活动会话继续使用当前入口的采用记录。
工具升级不重置自有职责和资料。update 只更新选定来源；报告本地差异时先交由使用者处理，不自动合并。
提升只发布用户明确选择的文件，不整体合并实例分支，不删除原资料，不自动替别人更新。
归档前先 handoff；解除归档不自动进入。已有外部目录可用 agent import --from-directory --asset 明确导入选定文件，原目录不改变。
七个内置 Skill 不限制实例自己的 Skill 数量。

## 普通会话与桌面组织

持久实例的桌面项目准备先用 `agent.desktop-project`（当前身份可省略 workspace/agent_id）读取本机名称、主目录和随包手动步骤。桌面项目按 Agent 复用，Codex 分区按 Workspace 组织；本版只记录引用，不自动创建原生项目/分区，不把保存引用说成已创建。修改名称/产品目录由用户使用 `agent.desktop-project-save`，不改变身份或权限。不要把产品 AGENTS.md 复制为自己的职责。

无 Workspace 的普通会话由用户从工作台“新建普通会话”进入；它没有持久身份、平台 Message/ACK 或 handoff/relay 保证，不能借普通会话绕过当前 Binding。用户的会话要求不写进共享项目规则。
