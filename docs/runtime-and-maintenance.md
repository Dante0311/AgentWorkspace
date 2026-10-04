# 会话、自动交接与管家维护

这是当前实现的使用说明，不替代 [产品设计](design.md)。使用对应功能分支的构建制品；`0.1.0a1` 仍是开发预览。以下操作默认由用户在终端或本机工作台发起，不把管理权限注入普通模型会话。

## 1. 安装和依赖

从所选提交的 GitHub Actions `CI` 中获取 `agent-workspace-build` 制品，解压后包含 wheel、sdist、`install.py`、`SHA256SUMS` 和准确源码快照。普通使用只需安装包，不必 clone 源码。制品有保留期限，尚不是正式 Release/PyPI 发布。

本机先准备 Python 3.11+；Git 和需要的 Harness 由用户自行安装、登录。基础安装不访问包索引；选择 `--extra` 才通过 pip 安装对应 SDK 依赖。上游 SDK 包可能携带其二进制资源，平台仍要求明确发现或指定实际使用的 Harness，不自动配置、登录或执行它。

```sh
python install.py git_native_agent_workspace-0.1.0a1-py3-none-any.whl --destination ./aw-app --extra claude --extra codebuddy
```

脚本先校验同目录 `SHA256SUMS`，再建立隔离环境；不改 PATH、不改 Workspace 数据、不覆盖已有非空安装目录。校验和不能替代可信下载来源。终端会输出实际启动命令：POSIX 为 `./aw-app/bin/aw setup --open`，Windows 为 `aw-app\Scripts\aw.exe setup --open`。下文把这个可执行文件简称为 `aw`。

默认应用数据在 `~/.agent-workspace`，可用 `--home` 或 `AW_HOME` 指定。软件安装目录、Workspace 数据仓与产品代码仓应分开。检测和 Git 认证规则见 [首次配置](first-use.md)。

## 2. 配置和进入真实会话

管家与普通实例共用相同配置入口。首次向导支持创建本地/空远端空间和准备已有实例的本机目录；主工作台的“配置”支持三种受管入口。安装对应 extra 和用户指定的原生程序后，可以使用：

```sh
aw -w demo agent configure-codex helper --model MODEL_ID --effort low --base-url https://gateway.example/v1 --env-key MY_MODEL_API_KEY
aw -w demo agent configure-sdk helper --kind claude --model MODEL_ID --base-url https://gateway.example --env-key MY_MODEL_API_KEY
aw -w demo agent configure-sdk helper --kind codebuddy --model MODEL_ID --base-url https://gateway.example/v1 --env-key MY_MODEL_API_KEY
```

三行是三种替代配置示例，不是要求依次执行。地址、模型 ID 和强度必须换成实际服务支持的值；省略地址时沿用该 Harness 的认证/服务环境。`--executable` 可指定已安装原生程序的绝对路径。密钥由用户在启动工作台/运行器的环境中提供，这里只保存环境变量名，不将密钥放进命令、Git 或角色定义。

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

## 3. 自动交接到指定 Harness

在当前实例工作中，用户选择目标运行配置并请求交接。例如 Codex → Claude：

```sh
aw -w demo agent transfer-profile helper --kind claude --model MODEL_ID --base-url https://gateway.example --env-key MY_MODEL_API_KEY --request-id switch-001
aw -w demo agent transfer-status helper
aw -w demo agent transfer-continue helper
```

请求先预检目标，再固定原 Binding、目标配置和唯一后继 Binding。原会话收到 handoff，使用工具保存检查点并请求 stop；运行器确认旧端停妥、发布交接点后，为同一实例目录创建目标新会话并提供接手材料。身份、资料和 Work 归属不变，不转换两家私有会话数据库。

`transfer-continue` 只推进原记录，不另造后继。结果不明先检查原会话/记录；不能删除 `.aw-local/transfer.json`、锁或 Binding 强行重试。状态含义：`handoff_requested` 等原端交出，`starting` 等原生入口，`session_bound` 等接手轮次完成，`completed` 已观察到后继和检查点；`relay_failed`/`outcome_unknown` 不等于可从头重做。

目标缺程序/凭据/SDK 时，不开始交出。旧会话真正丢失且没有交接点时仍阻塞；正常自动化不是强制接管后门。当前自动 transfer 接受 `codex`、`claude`、`codebuddy` 受管入口，不把 Desktop 替换成后台 CLI。

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

计时由 `aw serve` / `aw setup` 的本机服务或独立 `aw maintenance run` 执行。只关浏览器不停止服务；退出进程、系统休眠/关机时不会继续巡检。没有自动安装 OS 服务或开机启动项。一个安装只运行一个 worker，同一共享计划只由明确登记的安装位置执行，不因接入第二台机器自动启动第二份。

健康报告基于共享登记和当前机器可观察的状态；其他机器的进程列为未观察范围。异常通知经稳定请求 ID 进入已运行的 Sentinel 会话，同一异常不每次巡检重复通知。没有可用 Sentinel 会话时保留待通知，不自动新增模型会话。Sentinel 可将诊断交给 Maintainer；业务判断和修复只能使用已授权工具。

```sh
aw -w demo maintenance schedule --no-enabled
aw -w demo maintenance grant maintainer
```

禁用后不再安排新巡检；无法撤回已经执行的模型/外部动作。下次启用不会补发休眠期间每一个错过的轮次。

维修工具只提供三类动作：

| 动作 | 前提与行为 |
| --- | --- |
| `publication-reconcile` | 指定原 operation ID，核对本 Workspace 和实例归属，仅追认/补齐原 Git 协议记录。 |
| `bridge-retry` | 提供当前 Binding 和刚读取的 generation，桥接必须仍启用，且未主动停止或交接；不重发未知外部消息。 |
| `sync-idle` | 实例没有有效入口，取得本机运行器锁后同步；保留文件版本冲突检查。 |

```sh
aw -w demo maintenance repair helper --repair-action sync-idle --request-id repair-001
```

维修先保存动作结果，再独立复查。同一请求重试只补缺失/失败的复查，不能因为复查失败重做动作。`applied` 仅表示动作返回，必须查看 `result` 和 `verification`，不能据此宣称 Workspace 全部健康。`attempting`/`outcome_unknown` 保留原记录，不自动再执行。损坏记录会报告异常，不当缓存删除；一个实例的 JSON 读取失败不隐去其他实例的巡检结果。

## 5. 当前能力与验收边界

| 对象 | 已实现和开发者验证 | 仍需验证或尚缺能力 |
| --- | --- | --- |
| Codex 受管 CLI/App Server | 独立模型配置、真实会话、工具调用、持续通信；原生客户端对回环 API 测试；六向交接矩阵 | 用户账号/自有真实 API、实际模型能力和机器权限 |
| Claude Code 受管 CLI/SDK | 持续会话、平台 MCP 检查点/ACK、原生模型元数据、作为三种 CLI 交接的前端或后继 | 真实模型/账号；未实现已验证的 insert/steer |
| CodeBuddy 受管 CLI/SDK | 持续会话、平台 MCP 检查点/ACK；三种 CLI 六向交接矩阵 | 真实模型/账号；不是 WorkBuddy Desktop；未实现已验证的 insert/steer |
| Codex Desktop | 指定桌面 MCP 控制连接、真实会话绑定、状态与通知代码；深链准备新会话 | 实机接口版本、完整自动创建/跨入口接手；深链打开不能当作会话已建立 |
| Claude Code / WorkBuddy Desktop | 安装位置发现与未接入状态提示 | 尚缺明确的原生会话创建、持续通信、停工观测接入；不是仅待用户验收 |
| 管家维护 | 实例授权、持久计划、去重通知、健康观察和三类有限维修 | 真实模型是否正确诊断/选择动作、持续运行机器和用户明确授权 |
| 企业微信 | 可选文本 Bridge、发送记录、受管进程看护 | 真实 Bot、网络、映射及收发验收；不宣称多模态全部支持 |
| 安装/存储 | 隔离 wheel 安装、资源检查、本地与普通 Git 远端逻辑 | 用户新机器安装/凭据/远端分支策略；正式发布另行授权 |

SDK 不支持 insert 时，队头保持等待并返回 `delivery_unsupported`，不改成 normal、不新开会话，也不让后面的消息越过它。检查目标能力后由用户决定处理方式。

开发测试中的“真实客户端”指已安装的原生可执行程序、SDK、平台工具和 Git；模型响应是回环 API 夹具。它验证通信和副作用，不证明真实模型质量、费用、账号权限、长期运行或任何 Desktop 已验收。参见 [开发检查点](development-checkpoint.md) 与当前提交的 CI。

截至 2026-10-04 核对的外部入口说明：[Codex App Server](https://developers.openai.com/codex/app-server)、[Claude Desktop](https://code.claude.com/docs/en/desktop)、[CodeBuddy SDK](https://www.codebuddy.ai/docs/cli/sdk)。这些不是我们已经实现对应全部能力的证明，使用特定版本前须重新核对。

### 5.1 Desktop 接入仍缺什么

2026-10-04 的接口核对区分“原生产品能做”与“第三方能可靠控制”：

- Codex Desktop：已有指定拥有者 MCP 的连接代码，需取得用户版本实际暴露的创建、投递和状态接口及参数。深链或后台 App Server 均不能证明原 Desktop 新会话已建立；不通过冒充调用方或绕过工具授权补接口。
- Claude Desktop：[官方对照](https://code.claude.com/docs/en/desktop#feature-comparison)仍将脚本自动化与 Agent SDK 列为 CLI 能力。文档有 `/desktop`、桌面会话间消息等功能，但这不等于已提供可由 AgentWorkspace 调用的完整会话控制接口；当前不能据此承诺自动配置和接管原生窗口。
- WorkBuddy：[开放平台](https://open.workbuddy.cn/docs/third-party-app)及[本地助理 API](https://open.workbuddy.cn/docs/openapi)确实提供消息、在线状态和历史查询。该路线要求应用注册、相应 Scope 与用户授权；还需核实其是否能指定实例工作根、创建独立会话、观察停工并选择模型。不会为暂未确认的适配引入一整套 OAuth 服务，也不能宣称 WorkBuddy 没有任何通信 API。

下一步接入需要的是合法的实际控制接口与能力证据，不是用户提供账号密码或整份私有会话。此处记录开发阻塞，不缩减 V1 的 Desktop 目标；在它们得到解决前，不能把剩余工作统称为实机验收。

## 6. 实机验收顺序

在隔离 Workspace 上，按以下顺序记录实际版本、命令结果和副作用；不要提交凭据或原始私密会话。

1. 新机器缺 Git/Harness 时只提示，安装并登录后重新检测；本地与私有远端分别创建/接入，不覆盖原目录。
2. 使用自己的端点、模型和凭据引用启动一个受管实例；确认真实 Session、初始检查点和模型服务日志，不只看“配置已保存”。
3. 同一会话发送两轮输入，并接收另一实例的 Message；检查同一 Session、原消息 ID、ACK 和本机副本。
4. 在 Codex 请求交接到 Claude/CodeBuddy；核对旧入口 released、新入口唯一、材料保留，且后续 Message 到达后继。不手工替模型完成 checkpoint/stop 来冒充自动交接。
5. 启用明确授权的巡检，制造一个可恢复测试异常；确认发现、通知、允许的维修和复查。关闭计划后不复活旧入口，撤销授权后操作被拒绝。
6. 单独验收企业微信和具备真实控制接口的 Desktop。接口未确认的入口不能列入“已通过”。
