# 团队会话提示词已迁移到 AW-Workspace

这批供 aw-team 使用的初始化、handoff 和 relay 提示词属于协作空间资料，已通过 AW 的共享发布操作迁移到 [AW-Workspace 的会话操作入口](https://github.com/Dante0311/AW-Workspace/blob/ab2d71a47eccb61f6d8dae6192d7215df7b87498/knowledge/session-prompts/README.md)。

正式使用位置为 `Dante0311/AW-Workspace/main:knowledge/session-prompts/`，协作仓首页也提供入口。三份 startup、handoff、relay 及配套操作资料在该处维护；本产品分支原路径只保留迁移指引，不再维护操作正文。

AgentWorkspace 产品仓继续维护产品源码、通用随包 Skill/模板、正式设计和开发验证证据。这次没有修改运行程序、安装、实例入口或其他 Agent 的资产，也没有执行 handoff/relay。

## 可直接复制的入口

- [Core startup](https://github.com/Dante0311/AW-Workspace/blob/ab2d71a47eccb61f6d8dae6192d7215df7b87498/knowledge/session-prompts/core-startup.md)
- [Runtime / Adapter startup](https://github.com/Dante0311/AW-Workspace/blob/ab2d71a47eccb61f6d8dae6192d7215df7b87498/knowledge/session-prompts/runtime-adapter-startup.md)
- [Communication / Maintenance startup](https://github.com/Dante0311/AW-Workspace/blob/ab2d71a47eccb61f6d8dae6192d7215df7b87498/knowledge/session-prompts/communication-maintenance-startup.md)
- [handoff](https://github.com/Dante0311/AW-Workspace/blob/ab2d71a47eccb61f6d8dae6192d7215df7b87498/knowledge/session-prompts/handoff.md)
- [relay](https://github.com/Dante0311/AW-Workspace/blob/ab2d71a47eccb61f6d8dae6192d7215df7b87498/knowledge/session-prompts/relay.md)

## 保留的产品证据

- [原创建清单验证](validation.json)：对应原材料的隔离记录兼容性核对。
- [三类入口核对](lifecycle-validation.json)：对应迁移前提交 `a9d429d3c9b1cee32ab4061491fee6b4d74f0fc6` 的文档检查和隔离协议复验。
- [位置修正记录](relocation.json)：记录实际来源、共享发布版本、校验和本轮未改变的状态。
- [共享发布来源](https://github.com/Dante0311/AW-Workspace/blob/ab2d71a47eccb61f6d8dae6192d7215df7b87498/knowledge/session-prompts/provenance.json)：由正式发布工具生成的来源实例版本及选定文件校验值。

历史提交保留，验证记录不改写为真实会话已经通过；当前操作入口以协作仓为准。
