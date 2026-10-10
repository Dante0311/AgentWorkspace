# 会话、自动交接与管家维护

这是当前实现的使用说明，不替代 [产品设计](design.md)。使用对应功能分支的构建制品；`0.1.0a1` 仍是开发预览。以下操作默认由用户在终端或本机工作台发起，不把管理权限注入普通模型会话。

## 1. 安装和依赖

从所选提交的 GitHub Actions `CI` 中获取 `agent-workspace-build` 制品，解压后包含 wheel、sdist、`install.py`、`SHA256SUMS` 和准确源码快照。普通使用只需安装包，不必 clone 源码。制品有保留期限，尚不是正式 Release/PyPI 发布。

本机先准备 Python 3.11+；Git 和需要的 Harness 由用户自行安装、登录。基础安装不访问包索引；选择 `--extra` 才通过 pip 安装对应 SDK 依赖。上游 SDK 包可能携带其二进制资源，平台仍要求明确发现或指定实际使用的 Harness，不自动配置、登录或执行它。

```sh
python install.py git_native_agent_workspace-0.1.0a1-py3-none-any.whl --destination ./aw-app --extra claude --extra codebuddy
```

脚本先校验同目录 `SHA256SUMS`，再建立隔离环境；不改 PATH、不改 Workspace 数据、不覆盖无法确认归属的已有目录。校验和不能替代可信下载来源。终端会输出实际启动命令：POSIX 为 `./aw-app/bin/aw setup --open`，Windows 为 `aw-app\Scripts\aw.exe setup --open`。下文把这个可执行文件简称为 `aw`。

安装中断后，可用**相同 wheel、选装项、Python 主/次版本和目标目录**重跑原命令。安装器校验 `.aw-install.json` 后继续，不清空目录、不移动虚拟环境；已完成的同一安装仅检查启动程序，不再次运行 pip。不同包、不同选装项、损坏记录或复制到另一处的安装目录会被拒绝，不要删除标记绕过检查。没有安装记录的旧版残留也不会自动清理，应保留后换一个空目录。

升级使用新的独立安装目录。先保存并交接需要停止的会话、停用巡检和旧后台，再让新安装使用原 `--home`；不复制旧锁、不重建 Workspace。保留旧安装作为退路，但软件回退还要求数据格式兼容，不能把旧程序启动成功等同于数据迁移已经可逆。当前没有自动更新或自动迁移服务。

默认应用数据在 `~/.agent-workspace`，可用 `--home` 或 `AW_HOME` 指定。软件安装目录、Workspace 数据仓与产品代码仓应分开。检测和 Git 认证规则见 [首次配置](first-use.md)。

## 2. 配置和进入真实会话

管家与普通实例共用相同配置入口。首次向导支持为三名管家分别选择本机绝对目录，也支持为已有身份准备明确目录；主工作台创建普通实例时同样先确定目录。“配置”支持三种受管入口。工作台状态与恢复语义见 [Workbench 0.4](workbench.md)。安装对应 extra 和用户指定的原生程序后，可以使用：

```sh
aw -w demo agent configure-codex helper --model MODEL_ID --effort low --base-url https://gateway.example/v1 --env-key MY_MODEL_API_KEY
aw -w demo agent configure-sdk helper --kind claude --model MODEL_ID --base-url https://gateway.example --env-key MY_MODEL_API_KEY
aw -w demo agent configure-sdk helper --kind codebuddy --model MODEL_ID --base-url https://gateway.example/v1 --env-key MY_MODEL_API_KEY
```

三行是三种替代配置示例，不是要求依次执行。地址、模型 ID 和强度必须换成实际服务支持的值；省略地址时沿用该 Harness 的认证/服务环境。`--executable` 可指定已安装原生程序的绝对路径。密钥由用户在启动工作台/运行器的环境中提供，这里只保存环境变量名，不将密钥放进命令、Git 或角色定义。

可信网络上的非本机 HTTP 模型地址默认需要明确确认：在首次配置或实例配置中勾选“允许此地址使用 HTTP 明文传输”，CLI 使用 `--allow-http`；JSON 操作（含元数据查询）传 `"allow_http": true`。该选择仅随本次实例配置保存，不是全局放开；地址或 Harness 变更后界面清除确认。管家不能代替用户作出新的明文传输确认，但已由用户配置好的实例可以继续正常启动。

HTTP 会明文传输凭据及请求内容。是否属于可信内网由用户确认，不按固定私有 IP 范围猜测，也不自动访问截图地址或额外探测端口。配置、查询和交接复用同一校验，仍拒绝 URL 中的凭据、查询参数和非 HTTP(S) 协议。Base URL 原样传给对应 Harness，不擅自添加 `/v1`、`/messages` 或更换 HTTPS。OpenAI 与 Anthropic 两种入口应分别填写网关提供的地址；地址可保存不等于认证、Responses/工具调用或实际模型能力已经验收。

Codex 自有服务使用 Responses，Claude SDK 使用对应原生 Messages，CodeBuddy SDK 使用其原生服务或兼容接入配置；不是通用协议转换器。不同实例的配置只作用于本实例启动参数/子进程，不改全局设置。Codex 和 Claude 可以显式查询原生返回的模型/强度选项；CodeBuddy 尚无已验证的目录接口时保留手工填写。保存仍返回 `unchecked`，目录不是模型调用权限的证明；自有网关不冒用内置目录。

元数据查询可在首次配置页明确点击，或调用 `setup.inspect-codex` / `setup.inspect-sdk`。Claude 查询只做 SDK 握手，使用与真实会话相同的凭据路由，不发送模型输入、不创建平台 Binding、不返回账号明细。CodeBuddy 返回 `catalog=unsupported` 时，不尝试猜测或建立会话。

```sh
aw call setup.inspect-sdk --arguments '{"kind":"claude"}'
```

当前入口有效时拒绝直接换配置，使用下节自动交接。保存配置本身不启动模型：

```sh
aw -w demo agent start helper
aw -w demo agent show helper
aw -w demo agent input helper --text "请报告当前实例身份，暂不开展业务。" --request-id first-input
aw -w demo message watch helper start --interval 5
```

`starting_runner` 只是进程启动请求，真实 Session 和 active Binding 必须由原生事件确认；初始化完成还需初始检查点。收到 Message 通知不等于业务完成，ACK 必须由当前实例的 `message.receive` 实际保存。

SDK 事件流断开或收到独立的终止错误时，运行器保存失败状态并停止，不继续显示为正常运行。错误事实保留在原会话记录中，不伪造成功检查点、不自动重发输入。关闭受管客户端后的 controller 清理不等于释放 Binding；交接中断也必须按原记录检查。

Claude/CodeBuddy 托管入口默认只放行指定的平台 MCP；其他原生工具按用户明确提供的 `--allowed-tool` 开启。默认不加载用户/产品目录中的任意 SDK 配置、MCP 或钩子。实例材料通过进入提示和平台资料工具加载，不宣称原生 SDK 自动识别全部 Skill 目录。平台授权检查不是 OS 沙箱；不要给不受信任实例宽泛的文件/进程权限。

Windows 使用 CodeBuddy SDK 时，用户明确选择的 `.js/.cjs/.mjs` CLI 入口通过已安装的 Node 启动，沿用 SDK 原有参数、权限和通信。Node 需在实际运行器的 PATH 中；缺失或只有 `.cmd/.bat` 包装会在预留新入口或 handoff 前报错。选定的原生 `.exe` 继续直接启动，不自动切换为 SDK 自带程序。此改动只补启动方式，不复制桌面凭据、不切换模型服务或自动登录；返回 `/login` 只说明当前入口需要认证，真实 Windows/WorkBuddy 接手需单独验证。见 [定向复测说明](https://github.com/Dante0311/AW-Workspace/blob/c37ef2e92189adf357dc0e351aff48da9308377f/development/archive/2026-10-09-product-repository/docs/e2e-repair-acceptance.md#e2e-002-单独验证)。

### 2.1 工作台发送与响应丢失

发送方从当前有效实例中选择，表单固定当时的 Binding，后端在提交时重新检查。一次发送在网络请求前固定 request ID，并把正文及原参数暂存于本浏览器标签页；重复点击、响应丢失或页面刷新不生成新消息 ID。

存在未确认请求时，“查看原请求”调用只读 `message.operation`，“继续原请求”只发送尚未落盘的原请求，或补齐已有 publication receipt；不会自动重发，也不会改用新的 Binding。结果为 published 后移除浏览器恢复记录，不代表消息已 ACK 或业务完成。本标签页一次只保留一个未确认发送，按安装位置和 Workspace 标识区分；关闭标签页可能丢失浏览器记录，服务端原回执仍保留，可按原 ID 查询。存储被禁用或记录损坏时停止发送并说明，不能静默创建新请求。

```sh
aw -w demo call message.operation --arguments '{"operation_id":"ORIGINAL_REQUEST_ID"}'
```

“移除本页提示”仅删除浏览器记录，不撤回消息或删除服务端回执；未知结果须先核对，不能用清除提示代替处理。高级操作仍按各自的请求 ID 与结果规则执行，不宣称所有任意命令都能从网页刷新恢复。

### 2.2 渠道事件与共享读取失败

Bridge 在当前 Runner 内保留正在处理的原事件，只有该事件处理成功后才取下一条。资格读取或本地输入排队失败时，异常交给 Runtime 判断，原事件不会丢失或被放到队尾，后面的输入和发送回执也不会提前处理。可重试读取的分类与退避由 Runtime/Core 提供；这段保留逻辑不提供跨进程退出的事件恢复。

入站事件沿用渠道名称和原事件 ID 派生的输入 ID，并固定原 Binding。恢复只补缺失的本地排队，已有 `submitted` 或 `outcome_unknown` 输入保持原记录；旧入口不能把事件排到后继入口。此过程不重发外部 `send`，也不生成 Message ACK；渠道的 `sent` 回执仅表示渠道报告的发送结果。

## 3. 自动交接到指定 Harness

在当前实例工作中，用户选择目标运行配置并请求交接。例如 Codex → Claude：

```sh
aw -w demo agent transfer-profile helper --kind claude --model MODEL_ID --base-url https://gateway.example --env-key MY_MODEL_API_KEY --request-id switch-001
aw -w demo agent transfer-status helper
aw -w demo agent transfer-continue helper
```

请求先预检目标，再固定原 Binding、目标配置和唯一后继 Binding。原会话收到 handoff，使用工具保存检查点并请求 stop；运行器确认旧端停妥、发布交接点后，为同一实例目录创建目标新会话并提供接手材料。身份、资料和 Work 归属不变，不转换两家私有会话数据库。

`transfer-continue` 只推进原记录，不另造后继。结果不明先检查原会话/记录；不能删除 `.aw-local/transfer.json`、锁或 Binding 强行重试。状态含义：`handoff_requested` 等原端交出，`starting` 等原生入口，`session_bound` 等接手轮次完成，`completed` 已观察到后继和检查点；`relay_failed`/`outcome_unknown` 不等于可从头重做。

目标缺程序/凭据/SDK 时，不开始交出。旧会话真正丢失且没有交接点时仍阻塞；正常自动化不是强制接管后门。自动 transfer 接受 `codex`、`claude`、`codebuddy`，以及已捕获实际控制连接并核验已有本地项目的 `desktop`。不把 Desktop 替换成后台 CLI。桌面首次准备和操作见 [Codex Desktop](usage.md#42-codex-desktop)。

手动保底仍有效：旧端 handoff；用户在同一实例目录打开新 Harness 后，按 relay 提示取得并绑定真实新会话。手动模式的停工确认来自当前所有者明确确认，不是平台证明外部进程已经终止。

## 4. 管家授权、巡检和维修

新 Workspace 的角色映射可用 `workspace show` 查询，默认实例 ID 为 `steward`、`sentinel`、`maintainer`。职位名称不授予额外管理权。下面以 `helper` 为明确目标，逐项授权：

```sh
aw -w demo maintenance grant steward --command agent.start --command agent.transfer-profile --target helper
aw -w demo maintenance grant sentinel --command maintenance.schedule
aw -w demo maintenance grant maintainer --command maintenance.repair --target helper
aw -w demo workspace doctor
aw -w demo maintenance schedule --enabled --interval 300 --notify
aw -w demo maintenance status
```

`grant` 替换该管家的整份本机授权，不是追加。省略 `--command` 即撤销全部委托；`--target '*'` 表示本 Workspace 全部实例，只有用户明确选择才使用。授权不跨机器自动复制，不跨 Workspace 生效，不允许管家继续转授。跨实例资产写入也必须显式授权；配置程序路径、扩大原生工具权限等仍由用户操作。

工作台“管家授权”读取当前角色映射和程序实际允许委托的操作，逐项勾选操作与目标，重新打开会显示已有授权。“整个 Workspace”必须显式选择；保存仍是替换而不是追加。健康报告中的可处理发布/桥接问题可带入原 operation ID、Binding 与 generation 到维修表单，由用户确认执行；后端仍重新核对版本和授权，报告不是绕过检查的凭证。

计时由 `aw serve` / `aw setup` 的本机服务或独立 `aw maintenance run` 执行。只关浏览器不停止服务；退出进程、系统休眠/关机时不会继续巡检。没有自动安装 OS 服务或开机启动项。一个安装只运行一个 worker，同一共享计划只由明确登记的安装位置执行，不因接入第二台机器自动启动第二份。

健康报告基于共享登记和当前机器可观察的状态；其他机器的进程列为未观察范围。异常通知经稳定请求 ID 进入已运行的 Sentinel 会话，同一异常不每次巡检重复通知。没有可用 Sentinel 会话时保留待通知，不自动新增模型会话。Sentinel 可将诊断交给 Maintainer；业务判断和修复只能使用已授权工具。

`workspace doctor` 的 `local_observations` 分别列出当前 Binding、入口阶段、是否观察到本机 Runner、该入口最近的运行状态以及 Watch 配置。Watch 的 `not_configured`、`disabled`、`enabled` 和 `binding_mismatch` 分别表示没有配置、已关闭、为当前入口开启和配置仍指向其他入口；`enabled` 不证明通知已经送达。`runtime=null` 表示没有当前入口的运行记录。主动停止监视器不会抹去已经记录的故障；已进入 `stopping` 却没有本机观察进程时报告 `stop_confirmation_not_observed`，保留原 Binding 和 checkpoint 供核对，正常等待繁忙会话结束不会仅因等待被判为失效。

运行器报告 `shared_read_backoff` 时，诊断列出 `runtime_shared_read_backoff`；停止观察返回未知时列出 `stop_observation_unknown`。最近记录中的退避次数、等待秒数和原因保留在 `local_observations`，不会因程序仍在运行而显示健康。状态记录的时间也要一并查看，较早的网络失败记录不证明当前网络仍然故障。

报告中的 `maintenance` 和 `maintenance.status` 区分计划未配置、已停用、由其他安装执行、本机 worker 未观察到和 worker 已观察到。只有本机拥有的启用计划缺少 worker 时才报告 `maintenance_worker_not_observed`；其他安装的计划列为 `not_owned`，本机报告不据此声称整个 Workspace 健康。`worker_observed` 只证明本机程序存在，实际检查结果仍查看 `local_run`。

`maintenance.status.local_run.notice.state=queued` 是通知排队记录。另一个字段 `input_state` 只读回同一通知 ID、Binding 和用途对应的原输入状态；`completed` 只表示记录中的原生轮次结束，不证明维修或业务完成，`outcome_unknown` 仍须核对原输入。原记录缺失或不属于该入口时显示 `not_observed`，无法读取时显示 `unavailable`。查看状态不重新排队、不生成 ACK、不覆盖已保存的通知事实。

```sh
aw -w demo maintenance schedule --no-enabled
aw -w demo maintenance grant maintainer
```

禁用后不再安排新巡检；无法撤回已经执行的模型/外部动作。下次启用不会补发休眠期间每一个错过的轮次。

维修工具提供以下限定动作：

| 动作 | 前提与行为 |
| --- | --- |
| `publication-reconcile` | 指定原 operation ID，核对本 Workspace 和实例归属，仅追认/补齐原 Git 协议记录。 |
| `bridge-retry` | 提供当前 Binding 和刚读取的 generation，桥接必须仍启用，且未主动停止或交接；不重发未知外部消息。 |
| `sync-idle` | 实例没有有效入口，取得本机运行器锁后同步；保留文件版本冲突检查。 |
| `continue-stop` | 指定原 `expected_binding` 和 `expected_checkpoint`，在当前目标授权内复用 Runtime 的停止确认入口。只继续原请求，不创建会话或后继；Runtime 重新核对原会话、checkpoint、controller 及本机归属。 |

```sh
aw -w demo maintenance repair helper --repair-action sync-idle --request-id repair-001
aw -w demo maintenance repair helper --repair-action continue-stop --expected-binding ORIGINAL_BINDING --expected-checkpoint ORIGINAL_CHECKPOINT --request-id stop-repair-001
```

维修先保存动作结果，再独立复查。同一请求重试只补缺失/失败的复查，不能因为复查失败重做动作。`applied` 仅表示动作返回，必须查看 `result` 和 `verification`，不能据此宣称 Workspace 全部健康。`attempting`/`outcome_unknown` 保留原记录，不自动再执行。损坏记录会报告异常，不当缓存删除；一个实例的 JSON 读取失败不隐去其他实例的巡检结果。

`continue-stop` 的 `result` 保存首次继续请求的返回值，`starting_stop_observer` 或 `runner_present` 表示确认过程已请求或已存在；原入口是否释放要看 `verification.stop.state`。重复同一维修请求只读回固定旧 Binding 的状态、checkpoint 和 session，不重新启动观察进程，也不会跟随新的 Binding；checkpoint 与原请求不符时报告 `request_changed`。即使首次动作结果未知，复查也保留该动作的未知状态；看到旧 Binding 已 `released` 不会擅自启动后继。真实 Desktop 的忙碌、空闲和未知判断仍由 Runtime 的原生观察负责，维护工具不直接调用 `finish_stop`。

## 5. 当前能力与验收边界

用户与 Agent 共用一份随包维护的[当前版本支持范围](../src/agent_workspace/resources/prompts/capabilities.md)，不在这里另存一张可能漂移的矩阵。工作台与首次配置页可打开 `/capabilities` 查看本机安装版本，不需要 Git、账号或额外服务。

明确不支持的操作是本版公开限制，不靠反复重试或自行更换入口“修好”；未确认能力不冒充上游不支持。SDK 的 insert 队头仍保留并返回 `delivery_unsupported`，结果同时给出处理说明，不改消息和 ACK。模型目录不支持时明确说明可手工填写，填写成功仍不等于服务已经验收。

新建实例带有 `.aw/prompts/capabilities.md`，message/relay Skill 引导读取。自动或手动 `agent start` 生成的首次进入与接手提示总是附带当前安装包的说明和实际 Binding 类型，不信任旧 checkpoint 中的能力副本。已有实例可显式使用 `agent upgrade-tools` 更新受管说明，保留本地修改冲突检查，不覆盖 AGENTS.md 或用户资料。已经运行的模型不会因软件更新自动读到新规则，需用户明确让它读取更新材料，或在下次接手时加载。

开发测试中的原生客户端回环用例使用协议夹具，不能证明真实模型、账号或 Desktop。本批另做了 Windows Codex Desktop / App Tools 0.1.5 / gpt-6-luna 的限定实测，保留修复前失败和模型偏差，见 [桌面接入报告](https://github.com/Dante0311/AW-Workspace/blob/c37ef2e92189adf357dc0e351aff48da9308377f/development/archive/2026-10-09-product-repository/docs/evidence/2026-10-08-codex-desktop-integration/README.md)。未测的跨 Harness、busy insert、桌面重启恢复和长期运行不由该结果代验收。源码测试与当前提交的 CI 仍分别记录。

截至 2026-10-04 核对的外部入口说明：[Codex App Server](https://developers.openai.com/codex/app-server)、[Claude Desktop](https://code.claude.com/docs/en/desktop)、[CodeBuddy SDK](https://www.codebuddy.ai/docs/cli/sdk)。这些不是我们已经实现对应全部能力的证明，使用特定版本前须重新核对。

### 5.1 当前不支持项与上游待确认事项

2026-10-04 的接口核对区分“原生产品能做”与“第三方能可靠控制”：

- Codex Desktop（2026-10-08 更新）：已核实实际桌面 MCP 的 `list_projects`、`create_thread`、`read_thread` 和 `send_message_to_thread`，接入已有项目的自动创建、目录核验、绑定、输入轮次跟踪及交接。首次项目准备和真实连接捕获仍需用户完成，跨版本自动发现未提供。不能编造调用方、把深链打开或后台 App Server 当成桌面创建成功。
- Claude Desktop：[官方对照](https://code.claude.com/docs/en/desktop#feature-comparison)仍将脚本自动化与 Agent SDK 列为 CLI 能力。文档有 `/desktop`、桌面会话间消息等功能，但这不等于已提供可由 AgentWorkspace 调用的完整会话控制接口；当前不能据此承诺自动配置和接管原生窗口。
- WorkBuddy：[开放平台](https://open.workbuddy.cn/docs/third-party-app)及[本地助理 API](https://open.workbuddy.cn/docs/openapi)确实提供消息、在线状态和历史查询。该路线要求应用注册、相应 Scope 与用户授权；还需核实其是否能指定实例工作根、创建独立会话、观察停工并选择模型。不会为暂未确认的适配引入一整套 OAuth 服务，也不能宣称 WorkBuddy 没有任何通信 API。

Claude/WorkBuddy Desktop 完整自动化仍未接入；Codex Desktop 需要上述项目和实际控制连接条件，不承诺输入账号即可启用。后续扩展须取得合法控制接口与能力证据，不要求用户提交账号密码或整份私有会话。上游接口未知与本版未接入是两件事；已支持路径的实机验收与剩余限制分别列明。

## 6. 实机验收顺序

在隔离 Workspace 上，按以下顺序记录实际版本、命令结果和副作用；不要提交凭据或原始私密会话。

1. 新机器缺 Git/Harness 时只提示，安装并登录后重新检测；本地与私有远端分别创建/接入，不覆盖原目录。
2. 使用自己的端点、模型和凭据引用启动一个受管实例；确认真实 Session、初始检查点和模型服务日志，不只看“配置已保存”。
3. 同一会话发送两轮输入，并接收另一实例的 Message；检查同一 Session、原消息 ID、ACK 和本机副本。
4. 在 Codex 请求交接到 Claude/CodeBuddy；核对旧入口 released、新入口唯一、材料保留，且后续 Message 到达后继。不手工替模型完成 checkpoint/stop 来冒充自动交接。
5. 启用明确授权的巡检，制造一个可恢复测试异常；确认发现、通知、允许的维修和复查。关闭计划后不复活旧入口，撤销授权后操作被拒绝。
6. 单独验收企业微信和具备真实控制接口的 Desktop。接口未确认的入口不能列入“已通过”。

## 普通会话与桌面项目

无 Workspace 的交互 CLI 启动、内网 HTTP 明确确认，以及持久 Agent 项目/分区的本机引用和手动准备，见 [session-projects.md](session-projects.md)。这批功能不把 Desktop 项目管理标为已自动接入。
