# 实例的 Codex 模型选择

持久实例在根目录的 `runtime.json` 保存自己的 Codex 模型和推理强度。Codex Desktop 和受管 Codex CLI 共用这一选择，AW 在创建、恢复和发送 normal 输入时显式传入，不沿用发起者的设置。无 Workspace 的普通会话仍使用原生配置，不受本文件影响。

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

共享 Definition 可包含 `definitions/<role>/runtime.json`。创建时现有导入机制将其复制到实例根，与 `AGENTS.md`、其他资产一起保存。模板是创建材料；修改模板不会覆盖已有实例。实例文件随资产、检查点和 Fork 保存；产品的通用角色不预设具体模型和强度。

`.aw-local/runtime.json` 只维护当前机器的入口、原生程序命令、Desktop 管道与项目、服务及凭据引用。它不是另一份模型选择。`agent configure-desktop`、`agent configure-codex` 及通用 `agent configure` 仍接受原有的 `model` / `effort` 参数；对 Codex 入口，保存时将它们放入实例文件，连接信息留在本机文件。只更新连接、不提供模型字段时保留实例选择。

旧本机配置的顶层 `model`、`effort` 和 Codex 命令中的模型、推理强度覆盖会迁入实例文件。只迁移已有的值；缺少强度仍然缺少。冲突的旧值会报错，原文件保留。迁移来源及原字段保存在 `codex.migrated_from`。实例已经有选择时，迁移不会覆盖它；被移除的旧选择及来源留在 `.aw-local/model-migration.json`。重复迁移不覆盖用户修改，也不改变连接、服务或凭据引用。

## 保存与生效

新的执行入口在 `.aw-local/entry.json` 保存采用的 `model_profile`，包含模型、强度和实例文件的 SHA-256 来源。这是本入口的采用事实，不是新的可编辑配置。运行中修改实例文件只影响后续明确启动的入口；当前会话的后续输入和恢复仍使用原采用值。Desktop 重新 capture 连接不会重选模型，renew / relay 在交接完成后采用实例当时的选择。transfer 在请求时保存目标选择，后续应用不受中途文件编辑影响。

保存 profile 不启动模型。已有的 `configure-desktop` / `configure-codex` 管理命令仍要求活动实例先交接；用户或实例可按既有资产规则编辑根文件，为下一次入口准备选择。AW 不因此重启或恢复用户已停止的会话。直接调用原生工具的操作不在这项保证范围内。

Desktop 的 `create_thread` 和 `send_message_to_thread` 都带 `model` / `thinking`。本机控制端返回参数 schema 时，AW 按该 schema 拒绝已知不支持的字段或值；未返回模型目录时标记未确认，不用 CLI 或另一个账户的目录补证。Codex CLI 在同一 app-server 上查询 `model/list`；原生目录不可用或自有服务未提供适用目录时，明确填写的值仍以未确认状态使用。已知不支持的模型或组合报错，不换模型、强度或服务。

受管 CLI 的 `thread/start` / `thread/resume` 使用模型和 `config.model_reasoning_effort`，每次 `turn/start` 再带 `model` / `effort`。已有 `turn/steer` 接口不能覆盖这两个值，仍定位当前明确的 `expectedTurnId` 并使用该轮采用的选择；不把中断重开当作 insert。其他 Harness 的不支持路径保持原拒绝行为。本次没有增加新的 insert 能力。

## 如何核对

`agent show` 的 `model_selection` 表示实例当前希望下一入口采用的配置；`runtime.model_profile` 表示本入口最近一次原生请求的事实。launch 和 input 记录也保存 `model_profile`，分别包含 `requested`、`validation`、`native_accepted`、`effective` 和原生返回的有限设置字段。

- `requested` 说明 AW 实际传入的值及来源；参数保存不能证明原生已执行。
- `native_accepted=true` 说明接口返回成功；未知结果保留原尝试，不自动重发创建请求。
- `effective=unconfirmed` 表示原生没有同时返回模型和强度。`native_reported` 仅表示原生返回值与请求一致，不代替真实模型服务或 Desktop 设置验收。

原生明确返回不同值时记录 `effective=mismatch` 并报错，保留请求及返回事实，不把它当作成功采用。

本次 Windows 自动化测试覆盖配置解析、真实本地 Git 的模板/检查点/交接和协议夹具。真实 Desktop 的模型与强度效果需另行受控验收，不能用夹具或 CLI 成功代替。
