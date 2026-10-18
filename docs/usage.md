# 0.1.0a1 使用说明

首次安装见 [新机器配置](first-use.md)；后台启停、既有高级运行接口与管家维护见 [运行与维护说明](runtime-and-maintenance.md)。近期优先 Codex Desktop 与手动接入的 ChatGPT Web。本页保留基础命令，实际能力与未验证事项见 [当前实现](implementation.md)。

本文件描述实际代码，不替代 [产品合同](design.md)。这是开发预览版本，先使用隔离 Workspace；真实外部 Runtime 和渠道的验收范围见 [验证记录](https://github.com/Dante0311/AW-Workspace/blob/c37ef2e92189adf357dc0e351aff48da9308377f/development/archive/2026-10-09-product-repository/docs/validation.md)。

## 1. 安装、路径与本机工作台

```powershell
npm install --global .\git-native-agent-workspace-0.1.0-alpha.1.tgz
aw --help
aw backend start --open
```

Windows x64 的 npm 预览包需要 Node.js 22+，已包含 Python 运行时、网页与八个 Skills，无需保留源码。获取和升级方法见[安装和依赖](runtime-and-maintenance.md#1-安装和依赖)。工作台提供 Agent 与环境、消息历史、本机后台三项；创建、配置和交接继续使用下列 CLI 与 Skills。共享事实和本机观察分别标明，详见[工作台说明](workbench.md)。

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

前者通过 Git，后者通过 GitHub REST 对 Git 对象读写，不要求本地 clone。新版远端保存 `.agentworkspace/workspace.json`，旧仓仍按自身布局读取，不自动迁移。已由用户创建的空仓可显式初始化：

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

### 2.1 正式消息的独立分支

新空间默认把正式 Message、ACK、消息索引和 dispatch 放在 `aw-messages`。身份、Worker、Binding、Work、共同资料和原生直发留档仍在 main；普通发送和确认不再给 main 增加消息提交。实例资料分支保持原状，正常使用 CLI、HTTP 或 MCP 不需要手工切分支。

旧空间的软件升级不会自动迁移消息。先查看原格式、待移动路径和当前版本，再从用户管理入口明确切换：

```sh
aw -w sea message branch-plan
aw -w sea message migrate --request-id messages-20261018 --compatible-writer message-v3
aw -w sea message branch-plan
```

`--compatible-writer message-v3` 表示已经确认相关写入端支持新格式；旧版工具读到新共享格式后会拒绝写入。迁移保留消息原字节、ID、ACK、通知记录和旧历史引用，也保留原路径前缀，不顺带转换旧单入口 Agent 或移动实例资料。返回的 main 与消息分支版本必须实际可读；仓库不支持原子多 ref 更新时明确失败。

结果未知时用同一个 `request-id` 核对原提交，不换 ID 重发。若返回明确的版本冲突，原请求会保留拒绝事实；查看新的计划并处理并发修改后，再明确发起新迁移请求。Agent 或管家不能把普通业务调用当作用户迁移授权。手动 Git 写入必须使用新版 [Message 协议](../src/agent_workspace/resources/skills/message/references/protocol.md) 和配套脚本，不能只把原脚本中的 `main` 替换成新分支名。

## 3. 创建、接入、选定资产导入

```sh
aw -w sea agent create helper --description "分析构建日志，修改前向我确认。" --directory /data/aw/sea/helper
aw -w sea agent create ui --definition definitions/ui --directory /data/aw/sea/ui
aw -w sea agent list
aw -w sea agent show helper
aw -w sea agent connect helper
aw -w sea agent connect helper --directory /path/to/helper-copy
```

实例名可为中文，未指定 ID 时工具生成安全 ID；自动化可使用 `--id helper`。新布局的默认资料目录在本机 Workspace 的 `.agentworkspace/local/worktrees/ID` 中，是 `instance/ID` 分支的真实 Git worktree。仅有远端地址时，本机 Workspace 区域位于 `AW_HOME/workspaces/WORKSPACE`。`--directory` 仍可选择其他本机路径；已有普通副本不搬迁。`connect` 省略目录时复用原登记副本，缺失时从已保存的实例分支准备；目录存在不授予执行权，也不恢复尚未保存的资料。

新 worktree 需要 Git 及该 Workspace 的 Git 访问权限；`github:owner/repo` 的 REST 读取凭据不等于 Git transport 已可访问。准备只恢复资料，不启动会话或消费 handoff。身份、分支、已有目录或 Git 历史冲突会保留现场并报错。保存包括本次选定的实际文件与对应暂存内容，并更新 worktree 分支和索引；同一文件的暂存版本与工作文件不同、或本地和远端历史已经分叉时，先解决差异。同步保留不重叠的本机修改，`.git`、本机运行数据和嵌套仓库不进入实例快照。

已有外部目录的保守导入形式：

```sh
aw -w sea agent import helper --from-directory /path/to/existing-agent --asset AGENTS.md --asset knowledge/guide.md
```

只导入明确选定的普通文件；不改原目录、不覆盖原 `.git`、不接管旧会话。嵌套 Git、symlink、密钥、数据库整体迁移不自动猜测；原生历史应先通过来源环境明确导出。该操作不是 V2 membership。

<a id="workers"></a>

### 3.1 同一 Agent 的 Worker

新 Workspace 的 Agent 默认包含名为“日常工作”的 `default` Worker。只用这一个即可；需要独立保留另一项工作的上下文时，先查看已有 Worker，再按用户已批准的分工创建。Agent 身份与共同资料不变，每个 Worker 分别维护执行入口、消息和检查点。

```sh
aw -w sea worker list helper
aw -w sea worker create helper "日志调查" --id logs --description "调查已指定的构建日志" --request-id create-logs
aw -w sea worker show helper logs
aw -w sea worker start helper logs
aw -w sea agent show helper --worker logs
```

创建登记不会自动启动会话；`start` 是独立动作。Worker 继承 Agent 的 Harness 和模型默认值，明确的专用设置使用 `worker configure`、`worker configure-codex`、`worker configure-sdk` 或 `worker configure-desktop`。修改默认值不改变已运行入口采用的配置。原生标题使用 `Workspace 简称 · Agent 名称 · Worker 名称`；宿主实际采用情况仍须读回。

`worker update` 修改名称、说明、背景和材料引用，`--revision` 使用 `worker show` 返回的 Worker revision。`worker default` 改默认收件位置，`--revision` 使用 `agent show` 的 Agent revision。默认 Worker 没有管理其他 Worker 的权限，只负责接收未指定 Worker 的新消息。

```sh
aw -w sea worker update helper logs --revision WORKER_REVISION --name "构建日志调查"
aw -w sea worker default helper logs --revision AGENT_REVISION
aw -w sea message send helper --binding GRANTED_BINDING --to core --to-worker rules --delivery normal --content-file task.md --request-id task-one
aw -w sea message send helper --binding GRANTED_BINDING --reply-to ORIGINAL_MESSAGE_ID --delivery normal --content-file reply.md --request-id reply-one
```

发送方由真实 Binding 决定。明确回复回到原来源 Worker；普通 `message_refs` 不决定路由。改变默认收件位置不改投已保存消息，离线目标保留队列，归档目标拒绝新的发送。同一 Agent 的其他 Worker 不能代为 ACK。

过程文件放在 `workers/<worker-id>/`。检查点保存本 Worker 的材料；共同文件必须逐个明确选择，不收集同伴的未提交修改。更新产品代码时仍使用产品仓的任务 worktree。

```sh
aw -w sea checkpoint create helper --worker logs --binding GRANTED_BINDING --summary "调查结果" --shared-path knowledge/build-notes.md
aw -w sea worker stop helper logs --binding GRANTED_BINDING --checkpoint CHECKPOINT_ID
aw -w sea worker start helper logs --here
```

上述交出与接续按实际 Harness 执行；`--here` 只用于当前真实的新 Codex Desktop 聊天。完成任务不会自动停工或归档。`worker archive helper logs` 要求该 Worker 已交出入口，保留其他 Worker；归档整个 Agent 则要求全部 Worker 已交出。

既有布局 v0/v1 继续使用旧单入口，不因安装新版自动迁移。启用 Worker 时使用明确的用户管理操作 `worker migrate`，指定旧 Agent 对应的 Worker ID、原请求 ID 和全部写入端已兼容的确认；v0 先完成原目录迁移。例如 `aw -w sea worker migrate helper default --request-id migrate-helper --compatible-writers '["worker-v2"]'`。这是对实际写入端的确认，不能为通过检查随意填写。迁移保持旧 Message、ACK、检查点和 Binding 原字节，用单独映射确定其 Worker，不重新创建原生聊天。

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

可选的 [Web Courier 扩展](../extensions/web-courier/README.md)用于人工确认投递一条正式 Message。先准备实际 ChatGPT 会话、对应的 active manual Binding 和可用的收件工具，再在 Chrome 加载构建包内的扩展。它不替代接收方执行 `message receive` 或通过 Git 发布真实 ACK。

在用户管理终端中，为实际会话与扩展 ID 创建受限连接；端口必须与该 `AW_HOME` 的后台实际监听端口一致：

```sh
aw -w sea web-courier connect web-agent --binding CURRENT_BINDING --target-url "https://chatgpt.com/c/CONVERSATION_ID" --extension-id EXTENSION_ID --request-id courier-one --port 8765
aw web-courier status courier-one
aw web-courier revoke courier-one --request-id revoke-courier-one
```

这三个命令都只供用户管理终端调用，普通 Agent 不能凭连接 ID 查询会话地址或尝试记录。只将 connect 返回的连接 JSON 粘贴到扩展设置，不把后台管理 Token 交给扩展。status 不返回连接密钥，并分别显示网页观察和真实 ACK。原发送返回丢失或页面结果未知时只查询原记录，不再次点击；撤销保留连接与尝试记录。首批只支持单条 normal Message，真实 Chrome 加载、登录和页面效果由具体候选的 E2E 结果说明。

MCP 启动命令是 `aw mcp`。给对应会话的进程配置 `AW_HOME`、`AW_WORKSPACE`、`AW_AGENT`、`AW_BINDING`，使工具以实际运行绑定核对身份。`aw_execute` 接受 `{command, arguments}`，例如：

```json
{"command":"message.receive","arguments":{"message_id":"M123"}}
```

不要把无绑定的管理工具入口当成跨 Agent 的权限隔离。第一版是可信本机协作模型。

云端完成报告使用单独的受限 stdio 入口，不把通用 `aw_execute` 交给云会话：

```sh
aw --home /path/to/isolated-acceptance-home mcp --completion-config /path/to/completion.json
```

本机用户保存的配置示例（替换为实际隔离验收身份，不编造 Binding）：

```json
{
  "enabled": true,
  "workspace": "acceptance",
  "agent_id": "cloud-report",
  "binding": "ACTUAL_GRANTED_BINDING",
  "recipient": "local-receiver",
  "material_paths": ["knowledge/completion-brief.md"]
}
```

这个入口只公开 `aw_read_materials`（读取配置中的共享材料）、`aw_report_completion`（用稳定的 `request_id` 和 `content` 向固定收件人发正式 Message）及 `aw_report_status`（只查本配置身份和收件人对应的原请求）。调用方不能改 Workspace、Agent、Binding、收件人或材料路径，也不能用配置替换进程已继承的执行身份。共享材料仍受 `workspace.read` 的路径与大小约束。

每次调用都核对配置；将 `enabled` 改为 `false` 会拒绝后续调用。修改身份或其他范围后必须重新启动入口，不能让原进程静默改用新资格。Binding 停止或换会话后，旧配置不能再次发报告或读取材料，但仍可在配置未停用时只读核对自己原报告的发布回执。撤销不表示已经开始的发布已回滚。

发送回复丢失或结果未知时，只用原 `request_id` 查 `aw_report_status`；`not_recorded` 不表示可以盲目重发。返回的 `notification_acknowledged` 只说明正式 ACK 存在，不表示本机接收者已完成业务处理。MCP 握手、正式 Message 发布、接收者实际阅读与保存结果、真实云端模型调用分别验收。


### 4.2 Codex Desktop

先在 Codex 手动建立或选择一个已有本地项目。默认使用该 Agent 的个人资料目录作为主目录，也可让多个 Agent 共用 Workspace 或产品项目；项目和分区沿用用户既有布局。选择共用项目时，先读 `agent desktop-project helper` 的 revision，再保存本机引用：

```sh
aw -w sea agent desktop-project-save helper --harness codex --project-name "Shared project" --project-directory ACTUAL_PROJECT_DIRECTORY --revision READ_REVISION
```

省略 `--project-directory` 保留原选择；明确传入个人资料根可恢复独立项目。保存引用不修改原生项目、Binding 或附加目录权限。切换目录后用 `desktop-prepare --project-id` 明确采用实际匹配项目，旧项目 ID 不会静默指向另一个目录。随后在用户授权的真实 Codex 桌面聊天中捕获桌面自己的 MCP 控制连接：

```sh
aw -w sea agent capture-desktop helper --command '["node","ACTUAL_INSTALLED_CODEX_APP_TOOLS/server.mjs"]'
```

这里路径由安装环境确定，不是仓库提供的文件。命令读取该会话真实的 `CODEX_APP_TOOLS_PIPE_PATH` 和 `CODEX_THREAD_ID`，只保存到 `.agentworkspace/local/runtime/runtime.json`。不能从外部终端编造这两个值。

回到用户终端，保存模型选择并启动：

```sh
aw -w sea agent configure-desktop helper --model MODEL_ID --effort low
aw -w sea agent start helper
aw -w sea message watch helper start --interval 5
```

模型和强度必须明确选择，保存在 `.agentworkspace/config.json` 的 `codex` 段；本机文件只保存连接和项目信息。可选 Definition 提供创建模板，实例此后独立维护；详见[实例模型配置](instance-model-profiles.md)。所选项目目录匹配多个项目时，用 `--project-id` 明确选择。配置和自动启动都会读取实际项目列表核对所选目录。缺配置、项目或控制接口时先报错，不预留第二个执行入口。

运行器通过 `create_thread` 在该项目创建真实新聊天，读取实际 ID 与 `cwd` 后才绑定。第一轮仅建立连接；正式进入材料随后作为输入交付。桌面 Agent 使用提示中的 `aw call --desktop-agent` 命令前缀，由真实 `CODEX_THREAD_ID` 约束平台身份，不继承管理权限。输入先通过 `runtime.receive-input` 关联当前原生轮次；只有该轮明确完成才记录完成并为初次进入发布检查点，发送回执或 idle 本身不算业务完成。

建聊的连接提示先给本次已登记目标及个人 AGENTS.md/Skills 入口；此时 Binding 仍 starting、真实 session/cwd 尚未观测，不执行业务。绑定后的每次输入通知在领取命令前给当前 Agent、Binding、真实 session 与个人资料路径，避免共用项目里另一实例的角色被当成本人。项目共同规则继续适用，个人身份以当前登记为准。业务正文仍通过原 request_id 的 receive-input 领取，不复制到通知中；已经 submitted 或结果未知的原输入不会因此重发或改回 queued。

用户已经在新 Codex 聊天里发起接手时，在该真实聊天内运行下面的命令：

```sh
aw -w sea agent start helper --here
```

`--here` 使用真实环境变量和 `read_thread` 核验当前聊天，不调用 `create_thread`，不重新发送进入提示词。它返回 `bound_current_chat`、Binding、实际 `native_cwd`、个人资料目录和完整 `prompt`，并将同一份进入材料保存为 `prompt_file`。当前 Agent 实际阅读自己的 AGENTS.md、Skills、共同职责以及交接检查点后接续业务；工具返回不证明模型已经读过这些材料。个人资料根与 native cwd 分别登记，提示词中的路径不表示已经切换目录。已绑定或已交出的旧聊天不能用此选项取得新资格。

此模式需要该实例已配置真实 Desktop MCP 命令与模型选择；连接从当前新聊天捕获，不沿用旧聊天的 pipe/thread。首次接入本机时 `agent connect` 可省略目录，由平台准备已保存分支；然后在当前聊天 `capture-desktop --command`。准备、启动、绑定和交接均复用 Core 的目录准备能力；缺失目录仅恢复已保存资料，普通副本仍保留。原建聊已经尝试而结果未知时，`--here` 也拒绝替换，必须核对原 `runtime launch-show` 和 `reconcile-create`。绑定或后台请求结果未知时先读取 `agent show`、进入材料文件及原状态，不再次预留或重绑。`runner` 仅说明后台连接请求状态，不能代替模型完成、真实 E2E 或跨机器验收。

`agent renew` 在旧会话保存检查点、stop 并被观察到 idle 后，自动在同一项目创建新聊天。未知创建结果保留原回执，不自动重试开第二个聊天。自动 transfer 也接受含真实控制连接的 `desktop` 配置；其他入口不会暗中替代 Desktop。

只配置 `kind=desktop` 而未捕获控制连接时，仍保留原手动提示词/深链和真实 ID 绑定路径。深链打开不是自动创建成功。适配器只启动桌面附带 MCP 客户端，不启动第二个 app-server，不通过 exec resume 抢 writer。

Desktop 重启后命名管道可能变化。可从实际会话再次 capture；运行器只在原绑定仍有效且未请求 handoff 时重连。连续失败停下报告，不创造新的会话 ID。当前尚不能承诺无配置的跨版本自动发现。

### 4.3 托管 Codex CLI

先由使用者安装并完成原生 CLI 登录，然后：

```sh
aw -w sea agent configure helper --config '{"kind":"codex","command":["codex","app-server"],"model":"MODEL_ID","effort":"NATIVE_EFFORT"}'
aw -w sea agent start helper
aw -w sea message watch helper start --interval 5
```

程序通过 app-server 创建原生线程、提交初始化输入、记录事件；`aw_execute` 动态工具直接调用公共操作，不要求模型切到开发目录。实例须明确选择 `model` 与 `effort`，保存到 `.agentworkspace/config.json`；`modelProvider` 与 `sandbox` 留在本机连接配置，sandbox 默认 `workspace-write`。旧模型覆盖首次使用时迁移并保留来源，缺项不继承原生默认。原生审批/额外授权请求不会被自动批准。

Windows npm `.cmd` 启动器有单独的 argv 处理；未在真实 Windows/Codex 环境完成验收。CLI 成功不等于 Desktop 成功。

首次新会话若尚未发出创建请求，原 start 可以重试并复用已预留绑定。创建原生线程的结果已经不明时，不重复创建；先读取原回执：

```sh
aw -w sea runtime launch-show helper
```

仅当原回执包含真实 `threadId`，用户才可用同一个 ID 核对并认领。将下例中的 Binding 和 threadId 换成原回执的值：

```sh
aw -w sea runtime reconcile-create helper --binding ORIGINAL_BINDING --session ORIGINAL_THREAD_ID
```

核对会读取原聊天的 ID、本机目录、状态和已采用模型。确认返回 `state=session_bound` 后，再运行 `aw -w sea runtime start helper` 继续观察。认领命令本身不发原生输入，也不开始观察。只有 `clientThreadId` 或完全没有真实 ID 时仍返回 `outcome_unknown`，不能用同目录候选代替原创建证据。已有未知或已提交的 boot 输入不会重置。原 controller 未释放、来源不明、不同副本或不同安装位置时拒绝认领；用户显式强制接手见下节，它不用于自动重试未知创建。

## 5. 交出、换会话与 Fork

通常让当前会话按 `handoff` Skill 准备材料，也可用下列操作发送明确请求：

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

新检查点的 `origin` 由程序记录 Workspace 及 locator、Agent、实例分支、实际资料根和职责文件，以及保存时的 Binding、会话类型、session 和已知原生 cwd。未知 cwd 保存为 `null`。这些字段是历史来源；后继仍解析自己的本机路径并取得本次入口，不使用旧 Binding 或路径恢复执行资格。原检查点及同一 ID 的原请求内容保持不变，旧记录不补写这些字段。

Desktop/CLI 的停工确认由原运行器观察，不能用参数伪造。仅 manual 模式允许当前拥有者加 `--confirm-stopped`，表示使用者明确确认停工；不是操作系统隔离保证。

```sh
aw -w sea agent start helper
aw -w sea agent fork helper --checkpoint CHECKPOINT_ID --name explorer
```

start 为新入口建立新原生会话；fork 从确定检查点创建新 Agent，不删除原历史，不复制执行权，不自动创建 Work。检查点读取：`checkpoint list/show`。需要保留可继续的明确目标时，在首次 Fork 指定 `--new-id`。

Fork 已保存目标分支但登记或目录准备未完成时，用原来源 Agent、检查点、名称和目标 ID 加 `--resume` 继续：

```sh
aw -w sea agent fork helper --checkpoint CHECKPOINT_ID --name explorer --new-id explorer --resume
```

程序核对原目标的 `.agentworkspace/fork.json` 和资料版本，只补缺失步骤；旧分支按原布局读取。已登记目标只准备或复用本地副本，已有用户修改保留。原发表结果未知时先读回原分支和登记，不重发。换机器或 `AW_HOME` 前，先在原环境核实尚未确认的发表；新环境没有本机凭据不能证明原操作未发生。旧 Fork 没有该来源记录时不支持这条继续路径；已经登记的旧目标仍可使用 `agent connect`。

`runtime stop helper` 只停止本机监视任务，**不释放实例资格**；不是 handoff。已有归档/解除归档不启动会话。跨目录运行器还要在共享 binding 上条件登记 controller，不能只靠同机 PID。硬崩溃留下未释放 controller 时保持阻塞，不自动接管。

### 5.1 用户显式强制接手

先用 `agent show` / `agent history` 核对当前入口，用 `checkpoint list/show` 选择已保存资料。用户决定撤销旧资格时，在没有 Agent 调用身份的管理终端执行：

```sh
aw -w sea agent takeover helper --binding CURRENT_BINDING --checkpoint SAVED_CHECKPOINT --confirm
aw -w sea agent start helper
```

第一条只撤销旧入口的 AW 资格并保存同一 Agent 的交接点；第二条才按正常启动流程取得新入口。旧原生聊天可能仍在运行，旧副本中的未保存资料不会迁移。返回值分别说明 AW 资格已撤销、原生停工未观察和没有自动启动新会话。Agent 与管家不能调用此管理操作，额度耗尽或断线也不会自动触发。

重复指定同一旧入口和检查点只读取原交接结果，不撤销已经启动的后继。写入结果未知时保留原记录并核对，不重新创建身份、不重放旧业务。

## 6. 消息和可选 Work

每次发送和回复先按 [message Skill](../src/agent_workspace/resources/skills/message/SKILL.md) 核对自己和对方的当前入口。只有当次 `runtime.desktop-observe` 确认双方都是可寻址的本机 Codex 会话时，才使用原生直发；首次发送前无法确认同机，或跨 Harness、跨机器、云端时，使用正式 AW Message。原生发送已经尝试而结果未知，只核对原目标与原发送，不换路重发。

原生直发可以通过 `direct-message.record` 保存独立记录，`direct-message.list/show` 只读回这些记录。记录或可选回执失败不改变交流结果，不会生成正式 ACK，也不进入自动投递。记录只保存在调用方 Workspace，不自动双写收件方空间，详见[独立直发记录](../src/agent_workspace/resources/skills/message/references/direct.md)。下面是正式 Message 的操作：

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

自动通知包含短指引和完整原始 Message JSON，`content` 是正文；按 message Skill 核对本会话已获授的入口、尝试读取并保存 ACK，再在已有授权内判断工作和是否回复。正文缺失或损坏时通知附可信索引，记录正文未知，仍可按原 ID 尝试接收；已有 ACK 的重复通知不重新开展业务。其他 Agent 的消息不新增用户授权。

没有安装 AW 时，可以使用仓库工具或 Git 按同一协议收件、ACK 和回复。随包 message Skill 的 [精确协议](../src/agent_workspace/resources/skills/message/references/protocol.md)列出路径、字段与权限前提，[手动操作](../src/agent_workspace/resources/skills/message/references/manual.md)说明 GitHub 的 HEAD/tree/base_tree/parent、预期版本比较和读回步骤。仅有仓库工具也可执行，不要求 Python；工具无法安全比较预期 HEAD 或没有写权限时只读取/准备，明确未发布。

可选 `message/scripts/message_git.py` 只需 Python 3.11+ 和 Git，不导入 AW。它使用明确获授的实例/Binding 和独立 bare clone；receive/reply 默认只准备私有原操作文件，发布与继续须明确执行。跨仓库补齐复用原 ID/字节，不重复业务；结果未知只核对，不再次 push。该文件不是 AW receipt，不能交给 `aw message reconcile`。用法和状态含义见上述手动说明。

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
aw software status
aw software update
aw -w sea agent promote helper --path AGENTS.md --destination definitions/build-helper
```

新文件写入不传 revision；覆盖必须传读取时的哈希。工具资源更新不重置 AGENTS.md。来源更新发现本地修改就保留并报告，不自动三方合并。无关共享消息提交不触发来源过期提示。

实例的 `.agentworkspace/` 保存受管身份、配置、材料来源、提示词、检查点和平台记录；`.agentworkspace/local/` 保存当前环境资料，不进入实例 Git。`.agentworkspace/source.json` 只在确有来源时出现。`AGENTS.md`、原生 `.agents/skills/` 与用户自己的文档留在原位置。旧实例在明确迁移前继续使用旧布局，旧检查点仍从原提交读取。

旧数据先用 `aw -w sea layout plan` 查看范围，再由用户显式迁移；实例迁移和共享 main 迁移分别选择，后者还需核实完整写入端集合。[迁移操作与原请求继续](runtime-and-maintenance.md#1-安装和依赖)说明参数、冲突和中断处理，不通过手工搬动目录混合两种布局。

默认排除 `.git`、`.agentworkspace/local`、旧 `.aw-local`、`.local`、`secrets`、`.env*`、`__pycache__`。排除列表在本机 context.json 的 `exclude` 中明确可见；本机运行目录也由收集器强制排除，不只依赖 `.gitignore`。自定义排除是简单名称/路径 glob，不声称实现完整 `.gitignore` 语法。单文件 50 MiB 上限，外部大附件需明确引用。symlink/submodule 不自动穿透。已保存快照的范围和排除项会返回；外部产品、原生隐藏状态、未同步的本机发送事实不自动成为完整备份。

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
| 原运行器硬崩溃且 controller 未释放 | 保留原资料与阻塞；用户核对当前入口及保存检查点后，可明确执行 `agent takeover --confirm`，原生聊天是否停止另行确认。 |
| UI 旧状态文件显示 running | 同时检测本机进程锁并标注是否仍活着，不仅信任 PID 文件。 |
| 本地和来源同文件都改动 | 保留现场、显示差异，等待明确处理。 |

这不是完整安全权限系统。分支划分资料归属，不提供仓库成员之间的保密隔离。发布前应确认共享范围。未在真实外部环境验证的功能不要用于生产自动操作。

## 10. 外部接口参考

实现参考的接口文档，不代表这些外部产品已在本环境验收：

- [Codex App Server](https://developers.openai.com/codex/app-server/)：thread/start/read、turn/start/steer、dynamic tools。
- [Codex App commands](https://developers.openai.com/codex/app/commands)：deep link 能力，版本需实测。
- [GitHub Git refs](https://docs.github.com/en/rest/git/refs) 与 [Contents](https://docs.github.com/en/rest/repos/contents)：条件发布及空仓首文件。
- [WecomTeam SDK](https://pypi.org/project/wecom-aibot-python-sdk/)：可选文本渠道，非平台核心依赖。
