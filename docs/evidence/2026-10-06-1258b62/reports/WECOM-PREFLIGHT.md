# 企业微信最小准备核对

2026-10-06（Asia/Shanghai）。本次仅只读检查固定 wheel 的正式安装：`1258b622c474beb73f13234c0f00672d8d5b5bbb` / `0.1.0a1`。没有连接企微、发送消息、启动模型/服务、安装依赖或修改配置/代码。只新增本文件；旧 alpha 的 HY active 资格和所有历史状态保持不动。N 批实际仍为 0/6，未使用预算不构成 Bot/目标的发送授权。

场景采用 Lead 已读的 SBP OpsAgent 设计摘要：人从同一长连接智能机器人发起输入，负责的原生会话处理，同一 Bot 回原群/私聊，支持连续追问；Webhook 只是旁路告警。使用 AgentWorkspace 现有 `wecom.py`、`BridgeManager`，不恢复退役 SBP Agent 框架，不接生产构建或真实运维操作。

## 当前入口与缺项

正式 `app` 中 `aibot` 模块及 `wecom-aibot-python-sdk` distribution 均不存在。固定包的 `wecom` extra 为 **`wecom-aibot-python-sdk>=1.0,<2`**，实际代码导入 `from aibot import WSClient, WSClientOptions`。此前 CodeBuddy extra 不是企微依赖。本次未安装；获准后应使用独立 wecom 安装目标，保留原核心安装的标记/选项和现有数据，不重装全机客户端。

已有正常入口如下（均为待执行模板）：

```text
<本轮aw.exe> --home <正式workspace-home> -w e2e-local bridge configure e2e-beta --name wecom --config @<仅非密钥配置JSON>
<本轮aw.exe> --home <正式workspace-home> -w e2e-local call bridge.switch --arguments <含workspace/agent_id/name/enabled的JSON>
```

`bridge.configure` 的实际参数是 `agent_id: string`、`name: string`、`value: object`，可选 `directory: string`、`expected_generation: string`；CLI 的 `--config` 对应 value。模型调用 `bridge.send` 参数为 `name: string`、`target: string`、`text: string`、可选 `request_id: string`，身份/binding 由真实运行器注入；管理 CLI 则还需对应 `agent_id`、真实 `--binding`。name/request ID 使用不超过64字符的字母、数字、下划线或连字符，不把未经校验的企微 msgid直接拼成此ID。发送必须由目标测试 Agent 的真实模型调用，不由控制者代发。

非密钥配置最小形状：

```json
{
  "command": ["<已具有wecom依赖的隔离python.exe>", "-m", "agent_workspace.wecom"],
  "enabled": false,
  "bot_id_env": "WECOM_BOT_ID",
  "secret_env": "WECOM_BOT_SECRET",
  "allowed_chat_ids": ["<唯一明确授权的真实目标ID>"],
  "max_restarts": 1
}
```

`command` 是非空 `list[str]`，`enabled` 是 bool，两个 `*_env` 是环境变量名字符串，`allowed_chat_ids` 是非空 `list[str]`，`max_restarts` 为非负 int。这里设1，按当前 supervisor 的比较逻辑允许首次启动，失败后不再重启；设0会在首次启动前满足退出条件，不能用它表达“连接一次、不重试”。SDK 本身还设置 `max_reconnect_attempts=0`。不要在配置JSON中放真实 secret，也不要添加代码根本不读取的 `env` 字段冒充子进程专属凭据。

当前 beta 已 released、无 current Binding、原生 Runner 不在运行，可用于这条简单验收；alpha 不适合继续，旧 HY 资格必须保留。这里不创建新业务身份、不启用 Message Watch、不开展模型之间通信/transfer/Fork或管家巡检。Bridge 由 beta 的正常 Runner 管理，不能用“只关网页”代替停连接。

## 用户最少需要提供的内容

| 字段 | 精确类型与用途 |
| --- | --- |
| 测试机器人类型与发送授权 | 明确为**长连接智能机器人**，允许本次两次文本问答并由同一 Bot 回指定目标；Webhook URL不能替代。 |
| Bot ID | 非空 string；在本机赋给选定的 bot_id_env。无需进入模型提示词。 |
| Bot Secret | 非空 secret string；用户在本机安全输入到临时启动环境，不粘贴聊天/配置文件/命令参数/报告。执行者只需变量名，不读取或复制值。 |
| 测试目标 | 一个 `allowed_chat_ids: list[str]`；推荐只有1项。按当前代码，群聊用入站 body.chatid，私聊用 body.from.userid（没有 chatid 时）；需确切ID，群名称/邀请链接不足。群/私聊语义来自当前映射，真实 SDK/服务是否接受该目标仍需实测，不能预先宣称成功。 |
| 用户实际操作 | 能在该目标发送两条明确文本输入，收到第一条后再追问，并反馈是否看见两条指定标记回复。群场景按实际机器人要求 @Bot。 |

确切目标ID尚未给出；当前没有现成的安全自助目标ID发现入口，不能为了取ID放宽全部会话白名单或连接生产群。可由用户/管理员在既有可信平台取得该群 chatid 或测试私聊 userid。普通渠道文本会存入本轮 `channels/wecom` 与输入日志，因此测试输入只放随机标记与虚构文本，不发送真实构建资料或其他私密业务内容。

## 凭据继承范围：执行前必须明确

Bot凭据没有被当前 `wecom.py` 主动写入提示词/共享 Git，也有 QuietLogger 避免输出SDK payload；但这不等于只对 Bridge 可见：`spawn_runner` 仅剔除四个旧 AW 身份变量，保留其余环境；`Codex.__init__` 和 `BridgeManager.tick` 又分别继承整个 `os.environ`。因此临时环境中的 `WECOM_BOT_SECRET` **同时进入 Runner、原生 Codex app-server 和企微子进程**，不必要地扩大了进程可读取范围。本次没有提供/传递任何真实凭据，不能据此断言已发生泄漏或云端上传。

现有 `bridge.configure.value` 没有单独凭据env注入合同，不能靠额外JSON字段实现 Bridge-only 隔离。仅在提示词要求“不要读环境”也不是隔离保证。Lead 在执行前需说明此实际范围；若必须保证凭据仅进入 Bridge，则当前原版启动路径无法满足，需要另行决定/授权处理，不能本轮偷偷写启动适配、复制Desktop令牌或修产品代码。临时进程环境可避免永久全局设置，但不能消除上述继承。

## 最短真实旅程：计划4轮，最多6轮（目前0）

1. **初始化1轮。** 经明确 Bot/目标与凭据范围确认、依赖准备后，beta 用现有官方登录 + `gpt-6-luna/low` 正常 start，任务只限两次企微测试问答、笔记和停工。先保持Bridge关闭；配置/启用后观察 `bridge.status` 的真实 ready（来自SDK authenticated），不发连通试跑、不发送欢迎消息。ready 只证明握手，不是收发验收通过。
2. **用户第一输入→模型1轮。** 用户在唯一授权目标发随机标记。`message.text` 事件必须同时有 `msgid`、text、允许目标；代码原样保存源事件，然后 `queue_input` 到 beta 的当前 Binding。无需 Message Watch。记录源msgid、sender/target、输入ID、原生thread/turn。模型保存笔记并仅调用一次 `bridge.send` 回复原目标，固定短发送ID和标记，结束后等待。控制者不代发。
3. **用户追问→模型1轮。** 第一条实际可见后，用户问“刚才的标记是什么，请读回笔记后回复”。仍落入**同一真实 thread/Binding**；模型实际读前笔记并仅发送一次第二回复，结束后等待。这样证明原会话持续处理，而不是每条新建会话。若意外新输入/自动轮次发生，也计入总上限，立即停止增加测试输入。
4. **正常收尾1轮。** 两次 provider receipt 与用户可见均核对后，管理入口先禁用这个 Bridge，避免后续输入产生额外轮次；再正常 handoff 请求，模型保存累计检查点并 owner stop，确认released、Runner退出、Bridge进程退出。**不要让模型在 `bridge.send` 返回queued后同轮立即stop**，当前异步发送可能尚未取得receipt/未发完。最多另留2轮给确有必要的正常收尾，零控制器重试、不升档；不足则保留真实未决状态、关自动触发并报告，绝不伪造释放。

无本地模型代替企微入站，无 controller 代 `bridge.send`，不恢复SBP业务，不用Webhook实现相似效果，也不把群聊和私聊同时扩成测试矩阵。更换服务、目标、Bot或新增权限/费用都必须由Lead明确安排。

## 通过证据与发送未知的处理

- 入站：真实 `channels/wecom/<源事件hash>.json` 的 msgid/sender/target/text，与 `.aw-local/inputs/i<hash>.json`、同一 Binding 原生 `turn/started`/工具/`turn/completed` 对得上；两条输入ID不同但原生session不变。
- 出站：模型的真实 `bridge.send` → 本地 `.aw-local/bridge-sends/<request_id>.json` queued/dispatching → SDK成功回执 → state=sent、receipt.errcode=0，并在 `channels/wecom/sent` 保存。固定基线只保留成功 errcode，不保留完整外部出站msgid；报告不能虚构该ID。
- 真实到达：`sent + errcode=0` 是**provider接受**，不是用户已看见、已读或业务完成。用户需在**授权原群/私聊**实际看到含随机标记的两条回复，提供文字确认或不含凭据的局部截图，配合目标/时间/文本对应。模型自然语言“发送成功”和queued记录都不算。
- 限制：本桥只接 `message.text`、输出markdown；每次回复UTF-8不超过4000 bytes。其他类型、完整Desktop自动化不在本轮。`send_unknown/outcome_unknown` 只查看原发送ID与用户实际界面，不重发/换ID来刷绿；transport重连不等于业务重放授权。

当前结论：静态正常路径存在，但企微SDK、测试Bot/精确目标、凭据继承范围和真实用户可见证据尚未具备。等待Lead具体安排，不安装、不连接、不监控、不发消息。
