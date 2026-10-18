---
name: worker
description: 按需建议、创建和管理同一 Agent 下的持久 Worker。适用于可独立推进、需要保留各自上下文的工作；先考虑复用已有 Worker，由用户决定是否新增。
---

# worker

Agent 保存共同身份、职责、Skills 和长期资料；Worker 保存自己负责的事项、进展和接续材料。一名 Agent 默认只用一个 Worker 也完全正常。不要把每条消息、每项 Work 或一次短操作都拆成 Worker。

## 先判断是否值得拆分

当一项工作能独立推进、预计持续较久，或频繁切换会让两件事的上下文互相干扰时，可以主动建议。先查看已有 Worker 的负责事项和状态，合适时继续使用已有 Worker。紧密相连、很快完成的工作通常留在当前 Worker。

已有 Worker 正在处理其他事项时，先判断新工作是否属于它的职责、会不会打断原安排；复用不等于覆盖或取消它已有的任务。职责合适且没有冲突时，沿正常消息与输入队列交给它。

建议时用几句话说明准备拆出的事项、当前 Worker 继续负责什么、收益和增加的模型资源或协作成本，并说明本次是只建立 Worker，还是同时启动会话推进。用户决定是否创建，也可以调整范围；批准覆盖方案中明确的创建和启动安排。尚未同意时继续原工作；用户拒绝后不反复催问。同一方案已经获得明确授权时直接执行，不重复确认。

新建 Worker 不扩大原任务授权，不自动继承来源 Worker 的全部待办。不要为拆分强制建立 Work、固定上下级或定期汇报。

## 创建和继续工作

使用当前安装实际提供的 Worker 工具，先核对 Agent、已有 Worker 和操作范围。创建时给出简短名称、负责事项、必要背景、材料引用及未决事实。Worker ID 用于稳定寻址，名称用于阅读；名称可改，换原生聊天后仍是同一 Worker。

原生聊天标题采用 `Workspace 简称 · Agent 名称 · Worker 名称`，例如 `SBP · Lead · 开发推进`。默认 Worker 也使用实际工作名称或“日常工作”。工具返回的真实聊天、Binding 和 Worker 关联分别核对，不把创建记录、打开窗口或请求已接受当作已经开始工作。

创建记录和启动原生入口是两步。按本次明确授权启动或接续所选 Worker；已有入口时不抢占、不重复建聊。需要换聊天继续同一件事时使用 handoff / relay；需要独立 Agent 身份时才使用 fork。临时子代理不能代替持久 Worker。

使用同一套 CLI / MCP 公共命令。以下名称和 ID 替换为本次真实方案；中文名称另给稳定的 ASCII ID：

```sh
aw -w sea worker list core
aw -w sea worker create core "战斗规则" --id combat --description "整理并验证已批准的战斗规则" --reference docs/combat.md
aw -w sea worker show core combat
aw -w sea worker start core combat
```

MCP 对应 `worker.list/create/show/start`，参数使用 `workspace/agent_id/worker_id`；当前工具身份会填入自身 Workspace 与 Agent。Worker 继承 Agent 默认配置，专用配置使用 `worker.configure` 或已有 Harness 配置入口。创建命令不启动会话；没有包含启动的授权时止于读回创建结果。旧数据明确要求迁移时，不擅自迁移日常实例，先说明当前安装或数据尚未准备好。

## 工作资料和协作

从本次进入材料确认自己的 Workspace、Agent、Worker、Binding、个人资料根和工作目录。共同职责与 Skills 按需读取，过程文件放在自己的 `workers/<worker-id>/`。产品代码需要并行修改时使用产品仓的任务 worktree。

检查点只保存当前 Worker 的材料和本次明确选定的共同文件；不要顺手提交其他 Worker 的未完成修改。共同文件发生冲突时保留现有内容并处理真实冲突，不覆盖同伴成果。接续引用适用的检查点，不回滚整个 Agent。

需要交流时按 message Skill 核对实际来源和目标 Worker。明确回复回到原消息来源；仅指定 Agent 的新消息进入默认收件 Worker。默认 Worker 只是未指定目标时的收件位置，没有管理其他 Worker 的地位。不能替同伴确认 ACK，结果未知只核对原操作。

完成后整理有价值的成果到 Agent 共同资料，保留来源和必要过程。空闲不等于完成，完成不自动归档。归档前处理该 Worker 自己的有效入口，不能停止同一 Agent 的其他 Worker；归档整个 Agent 时须处理全部 Worker。
