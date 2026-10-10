# 0.1.0a1 使用说明

首次安装见 [新机器配置](first-use.md)；当前受管 Codex/Claude/CodeBuddy、跨 Harness 自动交接、管家授权、巡检与维修见 [运行与维护说明](runtime-and-maintenance.md)。本页保留基础命令与旧入口说明，支持边界以上述当前能力矩阵为准。

本文件描述实际代码，不替代 [产品合同](design.md)。这是开发预览版本，先使用隔离 Workspace；真实外部 Runtime 和渠道的验收范围见 [验证记录](https://github.com/Dante0311/AW-Workspace/blob/c37ef2e92189adf357dc0e351aff48da9308377f/development/archive/2026-10-09-product-repository/docs/validation.md)。

## 1. 安装、路径与本机工作台

```sh
python -m pip install .
aw --help
aw serve --open
```

或安装 wheel。安装完可以移走源码目录，`aw` 与实例中的工具资源不依赖开发仓绝对路径。用 `python -m agent_workspace` 可代替 `aw`。本机 Workbench 0.4 提供 Agent、协作、共享资料、管家、Workspace 与操作恢复视图；它不是聊天客户端。状态投影标明共享 revision 和本机观测，写操作仍调用同一公共 API。详见 [Workbench 0.4](workbench.md)。

全局参数放在模块名之前：`aw --home PATH --workspace sea agent list`。环境变量 `AW_HOME`、`AW_WORKSPACE` 可代替前两项。通过 GitHub REST 访问时凭据仅从 `GITHUB_TOKEN` / `GH_TOKEN` 读取，不写进配置、仓库或返回结果。

## 2. 建立或接入 Workspace

```sh
aw workspace init sea /path/to/sea.git
aw workspace connect sea /path/to/sea.git
aw workspace list
aw -w sea workspace show
```

`init` 通过首次配置流程创建空目录中的 bare Git 协作仓和三个管家实例，不启动会话或巡检，不在产品仓里初始化。工具另用自己的 bare 对象缓存和临时索引提交，不操作用户产品 checkout 的暂存区。实例目录是工具物化出来的普通目录，快照进入所属仓的 `instance/*`；无需实例自己包含 `.git`。

远端两种路径：

```sh
aw workspace connect sea git@github.com:OWNER/SEA-WORKSPACE.git
aw workspace connect sea github:OWNER/SEA-WORKSPACE
```

前者通过 Git，后者通过 GitHub REST 对 Git 对象读写，不要求本地 clone。远端必须包含平台 workspace.json。已由用户创建的空仓可显式初始化：

```sh
aw workspace bootstrap-remote sea github:OWNER/SEA-WORKSPACE
```

程序不替用户创建 GitHub Repo，不绕过分支保护。新向导采用持久创建 ID 标识 Workspace；上述旧 `bootstrap-remote` 入口仅保留原预览初始化，不补建管家。旧 `local:名称` / 远端地址 locator 不会隐式迁移，接入与补建分开。

```sh
aw -w sea workspace project add --alias product --address /path/to/Sea-Dev
aw -w sea workspace friend add --alias sbp --address /path/to/sbp.git
aw -w sbp workspace friend add --alias sea --address /path/to/sea.git
```

好友需要双方登记。目录映射仅进入本机 registry，不作为跨机器通用路径。关联和移除关联不修改产品或删除仓库。

## 3. 创建、接入、选定资产导入

```sh
aw -w sea agent create helper --description "分析构建日志，修改前向我确认。" --directory /data/aw/sea/helper
aw -w sea agent create ui --definition definitions/ui --directory /data/aw/sea/ui
aw -w sea agent list
aw -w sea agent show helper
aw -w sea agent connect helper --directory /path/to/helper-copy
```

实例名可为中文，未指定 ID 时工具生成安全 ID；自动化可使用 `--id helper`。默认实例目录在 `AW_HOME/instances/WORKSPACE/ID`。工作台和 `--directory` 可选择其他本机绝对路径或另一磁盘；目录只是本机副本位置。`connect` 可增加多个目录，目录存在不授予执行权。

已有外部目录的保守导入形式：

```sh
aw -w sea agent import helper --from-directory /path/to/existing-agent --asset AGENTS.md --asset knowledge/guide.md
```

只导入明确选定的普通文件；不改原目录、不覆盖原 `.git`、不接管旧会话。嵌套 Git、symlink、密钥、数据库整体迁移不自动猜测；原生历史应先通过来源环境明确导出。该操作不是 V2 membership。

## 4. 手动与 Codex 入口

### 4.1 手动 / 云端工具接入

```sh
aw -w sea agent configure helper --config '{"kind":"manual"}'
aw -w sea agent start helper
```

返回本次 binding 和本机 entry-prompt.md 路径。新会话先阅读提示词，并由使用者登记其真实 session ID：

```sh
aw -w sea agent bind helper --binding BINDING --session REAL_NEW_SESSION_ID
```

手动入口不具备自动推送能力，使用 `message receive` 主动收件。连接云端模型需要使用方配置实际可达的工具接入；本包提供 MCP stdio 与本机 HTTP，不包含公网代理、TLS 部署或自动创建 ChatGPT 云会话。

MCP 启动命令是 `aw mcp`。给对应会话的进程配置 `AW_HOME`、`AW_WORKSPACE`、`AW_AGENT`、`AW_BINDING`，使工具以实际运行绑定核对身份。`aw_execute` 接受 `{command, arguments}`，例如：

```json
{"command":"message.receive","arguments":{"message_id":"M123"}}
```

不要把无绑定的管理工具入口当成跨 Agent 的权限隔离。第一版是可信本机协作模型。

### 4.2 Codex Desktop

先在 Codex 手动建立或选择一个已有本地项目，把该 Agent 的实例目录设为主目录；项目和分区沿用用户既有布局。随后在用户授权的真实 Codex 桌面聊天中捕获桌面自己的 MCP 控制连接：

```sh
aw -w sea agent capture-desktop helper --command '["node","ACTUAL_INSTALLED_CODEX_APP_TOOLS/server.mjs"]'
```

这里路径由安装环境确定，不是仓库提供的文件。命令读取该会话真实的 `CODEX_APP_TOOLS_PIPE_PATH` 和 `CODEX_THREAD_ID`，只保存到 `.aw-local/runtime.json`。不能从外部终端编造这两个值。

回到工作台或用户终端，保存模型选择并启动：

```sh
aw -w sea agent configure-desktop helper --model MODEL_ID --effort low
aw -w sea agent start helper
aw -w sea message watch helper start --interval 5
```

模型和强度可省略以沿用桌面默认配置；同一实例主目录匹配多个项目时，用 `--project-id` 明确选择。配置和启动都会读取实际项目列表核对主目录。缺项目或控制接口时先报错，不预留第二个执行入口。

运行器通过 `create_thread` 在该项目创建真实新聊天，读取实际 ID 与 `cwd` 后才绑定。第一轮仅建立连接；正式进入材料随后作为输入交付。桌面 Agent 使用提示中的 `aw call --desktop-agent` 命令前缀，由真实 `CODEX_THREAD_ID` 约束平台身份，不继承管理权限。输入先通过 `runtime.receive-input` 关联当前原生轮次；只有该轮明确完成才记录完成并为初次进入发布检查点，发送回执或 idle 本身不算业务完成。

工作台“换新会话”或 `agent renew` 在旧会话保存检查点、stop 并被观察到 idle 后，自动在同一项目创建新聊天。未知创建结果保留原回执，不自动重试开第二个聊天。自动 transfer 也接受含真实控制连接的 `desktop` 配置；其他入口不会暗中替代 Desktop。

只配置 `kind=desktop` 而未捕获控制连接时，仍保留原手动提示词/深链和真实 ID 绑定路径。深链打开不是自动创建成功。适配器只启动桌面附带 MCP 客户端，不启动第二个 app-server，不通过 exec resume 抢 writer。

Desktop 重启后命名管道可能变化。可从实际会话再次 capture；运行器只在原绑定仍有效且未请求 handoff 时重连。连续失败停下报告，不创造新的会话 ID。当前尚不能承诺无配置的跨版本自动发现。

### 4.3 托管 Codex CLI

先由使用者安装并完成原生 CLI 登录，然后：

```sh
aw -w sea agent configure helper --config '{"kind":"codex","command":["codex","app-server"]}'
aw -w sea agent start helper
aw -w sea message watch helper start --interval 5
```

程序通过 app-server 创建原生线程、提交初始化输入、记录事件；`aw_execute` 动态工具直接调用公共操作，不要求模型切到开发目录。可选配置 `model`、`modelProvider`、`sandbox`，未指定时使用原生配置和 `workspace-write`。原生审批/额外授权请求不会被自动批准。

Windows npm `.cmd` 启动器有单独的 argv 处理；未在真实 Windows/Codex 环境完成验收。CLI 成功不等于 Desktop 成功。

首次新会话若尚未发出创建请求，原 start 可以重试并复用已预留绑定。创建原生线程的结果已经不明时，不重复创建；查看原始记录和本地 launch/status 后处理。当前没有强制接管命令。

## 5. 交出、换会话与 Fork

通常让当前会话按 `handoff` Skill 准备材料。工作台的“交出 / 换新会话”或下列操作发送明确请求：

```sh
aw -w sea agent handoff helper
aw -w sea agent renew helper
```

handoff 请求一开始就关闭旧入口自动投递、暂停桥接重启；模型保存检查点并调用 stop。原生轮次实际结束后，运行器释放执行权。renew 在释放旧运行器锁之后才启动下一端。

底层步骤可明确调用：

```sh
aw -w sea checkpoint create helper --binding BINDING --summary "累计摘要" --content "阶段事实"
aw -w sea agent stop helper --binding BINDING --checkpoint CHECKPOINT_ID
```

Desktop/CLI 的停工确认由原运行器观察，不能用参数伪造。仅 manual 模式允许当前拥有者加 `--confirm-stopped`，表示使用者明确确认停工；不是操作系统隔离保证。

```sh
aw -w sea agent start helper
aw -w sea agent fork helper --checkpoint CHECKPOINT_ID --name explorer
```

start 总是为新入口建立新原生会话；fork 从确定检查点创建新实例，不删除原历史，不复制执行权，不自动创建 Work。检查点读取：`checkpoint list/show`。

`runtime stop helper` 只停止本机监视进程，**不释放实例资格**；不是 handoff。已有归档/解除归档不启动会话。跨目录运行器还要在共享 binding 上条件登记 controller，不能只靠同机 PID。硬崩溃留下未释放 controller 时保持阻塞，不自动接管。

## 6. 消息和可选 Work

```sh
aw -w sea message send helper --binding BINDING --to other --delivery normal --content "请查看资料"
aw -w sea message send helper --binding BINDING --to sbp/helper --delivery insert --content-file request.md --request-id MY_REQUEST
aw -w sea message list --agent helper --unacked
aw -w sea message show --id MESSAGE_ID
aw -w sea message receive helper --binding BINDING --id MESSAGE_ID
aw -w sea message poll helper --binding BINDING
aw -w sea message watch helper status
aw -w sea message watch helper stop
```

`watch start` 只设置循环开关；自动执行需对应运行器已启动。托管 CLI 的 poll 在原拥有者进程内执行；独立命令不会再启动一个 CLI writer。receive 即使正文读取失败也按原协议写最小 ACK，但入口过期时不 ACK。

Git Backend 保存机械 publication receipt。返回 `pending / outcome_unknown` 时保留原 operation ID，使用：

```sh
aw message reconcile OPERATION_ID
```

补齐原内容而非再创建消息。消息原文不含 Backend 参数；双写仅是此版 Git 实现。ACK 不是“已读”或“已完成”。跨进程通知尝试通过共享条件提交登记，超时有限重试原 ID。

```sh
aw -w sea work create --owner helper --content-file work.md
aw -w sea work list --tree
aw -w sea work show WORK_ID
aw -w sea work update WORK_ID --revision OBJECT_REVISION --content-file updated.md
aw -w sea work deliver WORK_ID --revision OBJECT_REVISION --content "完成依据" --ref "repo@COMMIT:path"
```

版本取 show/list 返回的对象 revision，不是随便取当前 main commit。交付后工单与 Delivery 封存，后续变化新建 Work。不自动验收、合并或发布产品。

## 7. 资料、更新与提升

```sh
aw -w sea asset list helper
aw -w sea asset read helper --path AGENTS.md
aw -w sea asset write helper --path notes.md --content "记录" --revision FILE_HASH
aw -w sea agent versions helper
aw -w sea agent update helper --revision SOURCE_COMMIT
aw -w sea agent upgrade-tools helper
aw -w sea agent promote helper --path AGENTS.md --destination definitions/build-helper
```

新文件写入不传 revision；覆盖必须传读取时的哈希。工具资源更新不重置 AGENTS.md。来源更新发现本地修改就保留并报告，不自动三方合并。无关共享消息提交不触发来源过期提示。

实例的 `.aw/` 为受管身份、工具版本、提示词和检查点；`.aw-local/` 为当前环境资料，不进入实例 Git。source.json 只在确有来源时出现。

默认排除 `.git`、`.aw-local`、`.local`、`secrets`、`.env*`、`__pycache__`。排除列表在本机 context.json 的 `exclude` 中明确可见；这是简单名称/路径 glob，不声称实现完整 `.gitignore` 语法。单文件 50 MiB 上限，外部大附件需明确引用。symlink/submodule 不自动穿透。已保存快照的范围和排除项会返回；外部产品、原生隐藏状态、未同步的本机发送事实不自动成为完整备份。

本机待发送 journal 不会被 Fork 自动执行。需要保留其中的业务事实时，按用户选择写进检查点或实例材料；平台不自动重做，也不禁止查阅。

## 8. 可选企业微信与其他渠道

核心不依赖企业微信。附带文本桥接程序：

```sh
python -m pip install '.[wecom]'
```

配置一个渠道（配置文件只在本机）：

```json
{
  "command": ["python", "-m", "agent_workspace.wecom"],
  "enabled": true,
  "max_restarts": 5,
  "bot_id_env": "WECOM_BOT_ID",
  "secret_env": "WECOM_BOT_SECRET",
  "allowed_chat_ids": ["USER_APPROVED_CHAT_ID"]
}
```

```sh
aw -w sea bridge configure helper --name wecom --config @wecom.json
aw -w sea bridge status helper
aw -w sea bridge stop helper --name wecom
aw -w sea bridge start helper --name wecom
aw -w sea bridge send helper --binding BINDING --name wecom --target CHAT_ID --text "明确要求发送的回复"
```

凭据由运行器的环境继承，不能写入共享配置。SDK 只负责通道，监督进程负责有限异常重启，不重跑模型输入或不确定的发送。当前仅实现文本入站与 Markdown 单次主动发送，不假装支持图片、文件、流式卡片或全部企微业务功能。没有实时企业微信验证。

自定义渠道用 stdin/stdout JSONL 契约：向父进程输出 `ready`、`input{id,sender,target,text}`、`sent{id,receipt}`、`send_unknown{id,receipt}` 或 `error{reason,fatal}`；从 stdin 读取 `send{id,target,text}`。原始输入持久保存后才交模型，回复需明确调用 bridge.send。使用退出码 78 表示配置/依赖错误，父进程不反复重启。

## 9. 故障与实际限制

| 现象 | 已实现的处置 |
| --- | --- |
| 目录准备失败 | 共享实例已保存时给出 ID，使用 connect 指定空目录，不重新创建。 |
| 部分消息发布 | 按原 operation ID reconcile；不生成新 Message。 |
| 快照已保存，检查点索引失败 | 用同一 checkpoint ID 重试发布原快照，不混入后来文件。 |
| 桌面断线 | 在原有效入口内有限重连；需新管道时重新 capture，不转为 CLI。 |
| 原生新线程创建结果不明 | 保留记录并阻止重复创建，不虚构失败回滚。 |
| 原入口正在 handoff | 不自动拉起桥接；不允许另一个新入口抢占。 |
| 原运行器硬崩溃且 controller 未释放 | 保留阻塞和全部资料；此版不提供强制接管。 |
| UI 旧状态文件显示 running | 同时检测本机进程锁并标注是否仍活着，不仅信任 PID 文件。 |
| 本地和来源同文件都改动 | 保留现场、显示差异，等待明确处理。 |

这不是完整安全权限系统。分支划分资料归属，不提供仓库成员之间的保密隔离。发布前应确认共享范围。未在真实外部环境验证的功能不要用于生产自动操作。

## 10. 外部接口参考

实现参考的接口文档，不代表这些外部产品已在本环境验收：

- [Codex App Server](https://developers.openai.com/codex/app-server/)：thread/start/read、turn/start/steer、dynamic tools。
- [Codex App commands](https://developers.openai.com/codex/app/commands)：deep link 能力，版本需实测。
- [GitHub Git refs](https://docs.github.com/en/rest/git/refs) 与 [Contents](https://docs.github.com/en/rest/repos/contents)：条件发布及空仓首文件。
- [WecomTeam SDK](https://pypi.org/project/wecom-aibot-python-sdk/)：可选文本渠道，非平台核心依赖。
