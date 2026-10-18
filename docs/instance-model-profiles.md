# 实例的 Codex 模型选择

持久实例在 `.agentworkspace/config.json` 保存自己的 Codex 模型和推理强度。Codex Desktop 和受管 Codex CLI 共用这一选择，AW 在创建、恢复和发送 normal 输入时显式传入，不沿用发起者的设置。旧实例在明确迁移前仍按原布局读取根 `runtime.json`。无 Workspace 的普通会话仍使用原生配置，不受本文件影响。

Worker 数据版本使用这份 Agent 配置作为默认值。Worker 可在 `.agentworkspace/workers/<worker>/config.json` 保存自己的完整 `codex` 选择；未保存该节时采用 Agent 默认值，保存了不完整的覆盖则明确报错。Worker 的连接覆盖、采用配置和运行记录位于 `.agentworkspace/local/workers/<worker>/`，不会覆盖其他 Worker。

```json
{
  "codex": {
    "model": "YOUR_NATIVE_MODEL_ID",
    "effort": "YOUR_NATIVE_EFFORT"
  }
}
```

两个值都必须是明确的非空字符串。模型可以带原生的上下文后缀，例如 `[1m]`；明确的 `none` 是一个值，不会当作缺失。身份可以先创建而不配置运行，但自动启动在创建原生会话和发送模型输入之前拒绝缺项或结构错误。没有采用记录的旧会话不能因新增此文件而直接切换，需先完成交接。

## 模板、实例与本机连接

共享 Definition 可包含 `definitions/<role>/runtime.json`。创建时将其导入实例 `.agentworkspace/config.json`，与 `AGENTS.md`、其他资产一起保存。模板是创建材料；修改模板不会覆盖已有实例。实例文件随资产、检查点和 Fork 保存；产品的通用角色不预设具体模型和强度。

`.agentworkspace/local/runtime/runtime.json` 只维护当前机器的入口、原生程序命令、Desktop 管道与项目、服务及凭据引用。它不是另一份模型选择。`agent configure-desktop`、`agent configure-codex` 及通用 `agent configure` 仍接受原有的 `model` / `effort` 参数；对 Codex 入口，保存时将它们放入实例文件，连接信息留在本机文件。只更新连接、不提供模型字段时保留实例选择。

旧本机配置的顶层 `model`、`effort` 和 Codex 命令中的模型、推理强度覆盖会迁入实例文件。只迁移已有的值；缺少强度仍然缺少。冲突的旧值会报错，原文件保留。迁移来源及原字段保存在 `codex.migrated_from`。实例已经有选择时，迁移不会覆盖它；被移除的旧选择及来源留在 `.agentworkspace/local/operations/model-migration.json`。重复迁移不覆盖用户修改，也不改变连接、服务或凭据引用。

## 保存与生效

新的执行入口在 `.agentworkspace/local/runtime/entry.json` 保存采用的 `model_profile`，包含模型、强度和实例文件的 SHA-256 来源。这是本入口的采用事实，不是新的可编辑配置。运行中修改实例文件只影响后续明确启动的入口；当前会话的后续输入和恢复仍使用原采用值。Desktop 重新 capture 连接不会重选模型，renew / relay 在交接完成后采用实例当时的选择。transfer 在请求时保存目标选择，后续应用不受中途文件编辑影响。

保存 profile 不启动模型。旧单入口版本的 `configure-desktop` / `configure-codex` 管理命令仍要求活动实例先交接；用户或实例可按既有资产规则编辑实例配置，为下一次入口准备选择。AW 不因此重启或恢复用户已停止的会话。直接调用原生工具的操作不在这项保证范围内。

Worker 的 `worker configure`、`configure-desktop`、`configure-codex` 只修改指定 Worker，要求它先正常交出；其他 Worker 可继续工作。Worker 版本中的 `agent configure*` 修改 Agent 默认值，已有入口仍使用各自启动时保存在 `entry.json` 的配置。运行中改变默认值只影响后续明确启动的入口；重新捕获连接不改写当前入口的模型采用值。

Desktop 的 `create_thread` 和 `send_message_to_thread` 都带 `model` / `thinking`。本机控制端返回参数 schema 时，AW 按该 schema 拒绝已知不支持的字段或值；未返回模型目录时标记未确认，不用 CLI 或另一个账户的目录补证。Codex CLI 在同一 app-server 上查询 `model/list`；原生目录不可用或自有服务未提供适用目录时，明确填写的值仍以未确认状态使用。已知不支持的模型或组合报错，不换模型、强度或服务。

受管 CLI 的 `thread/start` / `thread/resume` 使用模型和 `config.model_reasoning_effort`，每次 `turn/start` 再带 `model` / `effort`。已有 `turn/steer` 接口不能覆盖这两个值，仍定位当前明确的 `expectedTurnId` 并使用该轮采用的选择；不把中断重开当作 insert。其他 Harness 的不支持路径保持原拒绝行为。本次没有增加新的 insert 能力。

## 如何核对

### 由 Agent 准备、用户确认后保存

用户明确要求代办模型设置时，当前有效 Agent 可用 `agent.model-change-request` 准备一次变更。请求只接受同一 Workspace 中 Codex / Desktop 实例的 `model` 和 `effort`；不会获得通用 `agent.configure` 权限或长期管家授权。真实调用者、目标实例、原配置和新值保存在本机请求中。

```sh
aw -w sea call agent.model-change-request --arguments '{"request_id":"model-choice-1","changes":[{"agent_id":"helper","model":"YOUR_NATIVE_MODEL_ID","effort":"high"}]}'
aw -w sea model-review model-choice-1
aw -w sea call agent.model-change-show --arguments '{"request_id":"model-choice-1"}'
```

Desktop Agent 使用进入材料提供的真实 `--desktop-agent` 命令前缀提交请求，也可用同一前缀调用 `agent.model-change-review`。`model-review` 只打开该请求的 Windows 原生确认框，不启动后台、Runner 或巡检。用户核对全部目标的旧值和新值后选择“是”保存；默认选项为“否”，“否”或“取消”均保持配置不变。只有系统确认框返回“是”后才执行内部保存，公共命令不接受 `confirmed` 参数或无确认保存操作。Agent 不得代点击、模拟按键或绕开该入口。

自然语言里的批准由 Agent 理解，但当前宿主没有向 AW 提供绑定具体参数的批准凭据，因此仍需这一次系统弹窗确认。目前只支持 Windows 交互桌面；其他平台明确报不支持。AW 不把聊天文本、其他 Agent 转述或调用参数里的“用户已同意”当作批准证明。不解析私人会话文件，也不新增通用审批系统；仍沿用可信本机协作模型，不提供操作系统级隔离。

确认框一次最多展示 5 个目标、2000 字符；超过时会提示拆成小批次，不隐藏或截断待批准内容。

确认前工具再次检查发起者当前资格、目标登记、Binding 和原配置。任一目标已变化则整批不写入，须重新查看并准备新请求。相同请求 ID 不得更换目标或新值；已经完成的请求只返回原状态，中途写入结果不明的请求只读核对实际配置，不自动重放。保存只更新实例模型选择，保留连接、现有入口采用值和巡检选择；是否已经在原生会话中生效仍按下面的证据分别判断。

`agent show` 的 `model_selection` 表示实例当前希望下一入口采用的配置；`runtime.model_profile` 表示本入口最近一次原生请求的事实。launch 和 input 记录也保存 `model_profile`，分别包含 `requested`、`validation`、`native_accepted`、`effective` 和原生返回的有限设置字段。

Worker 版本用 `agent show <agent> --worker <worker>` 和 `runtime status <agent> --worker <worker>` 查看指定入口。`worker show` 只读 Worker 登记和 revision；默认收件 Worker 发生变化不会改变当前调用者或已有入口的采用配置。

- `requested` 说明 AW 实际传入的值及来源；参数保存不能证明原生已执行。
- `native_accepted=true` 说明接口返回成功；未知结果保留原尝试，不自动重发创建请求。
- `effective=unconfirmed` 表示原生没有同时返回模型和强度。`native_reported` 仅表示原生返回值与请求一致，不代替真实模型服务或 Desktop 设置验收。

原生明确返回不同值时记录 `effective=mismatch` 并报错，保留请求及返回事实，不把它当作成功采用。

本次 Windows 自动化测试覆盖配置解析、真实本地 Git 的模板/检查点/交接和协议夹具。真实 Desktop 的模型与强度效果需另行受控验收，不能用夹具或 CLI 成功代替。
