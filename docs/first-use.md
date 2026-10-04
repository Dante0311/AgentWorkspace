# 新机器配置

本页说明首次配置。后续会话、交接和维护操作见 [运行与维护说明](runtime-and-maintenance.md)；不将管家身份、配置保存或协议测试等同于真实自动化已验收。

## 打开

安装本项目 wheel 后，不需要保留开发仓。已有安装可运行：

```sh
aw setup --open
```

`aw serve --open` 在尚未登记 Workspace 时也显示首次配置页；已有空间可通过 `/setup` 打开。两者复用本机服务、控制 Token 和操作分发，不启动另一套 Web 服务。地址中的控制 Token 不要分享。

本仓仍是开发预览，已有 CI wheel 制品与隔离安装脚本，尚未发布正式 Release 或 PyPI 包。[安装步骤](runtime-and-maintenance.md#1-安装和依赖)不要求 clone 源码；构建方式见 [开发说明](../CONTRIBUTING.md)。操作数据应放在开发仓和产品仓之外。

## 依赖和认证

检测只检查 Git、PATH 中的 Codex/Claude/CodeBuddy CLI，以及 macOS 的部分标准 Desktop 安装位置。非标准位置和其他系统的 Desktop 可能显示未确认，不是未安装的证明。Codex CLI 和 Claude/CodeBuddy SDK 已接通受管运行器；Claude/WorkBuddy Desktop 的发现不等于桌面自动控制已实现。没有 Harness 时可先建立身份，之后自行安装、登录并重新检测。

Git 是新配置流程的前置条件，需用户自行安装。选择本机目录或自己准备的专用私有空远端仓。首次配置接受本机路径、普通 HTTPS/SSH 地址，不接受携带凭据的 URL、远端 helper 或 `github:` 简写。已有 GitHub REST 后端仍留在原低层接口，未扩展成另一套首次向导。

认证复用 Git 的凭据助手、标准 OpenSSH 配置和 SSH agent。工作台不发起交互登录，不接受密码或 Token，不自动确认 SSH 主机密钥；请先在同一系统用户环境中完成 Git 登录和主机信任。当前受管 Git 命令使用带 BatchMode 和严格主机检查的 OpenSSH，不支持依赖交互输入的自定义 SSH 包装命令。已有终端认证也需在实际运行工作台的环境中可用。

“检查访问”仅执行有超时的 `git ls-remote`，不写测试文件或分支，成功只确认读取；写权限保持未验证。点击初始化后才实际提交 Workspace 数据，分支权限仍由 Git 服务执行。后台错误不转述可能含凭据的原始认证输出。

## 创建与接入

创建本机 Workspace 可以使用页面，或：

```sh
aw workspace init demo /path/to/demo.git
```

远端初始化和接入可用首次配置页面，或同一操作接口：

```sh
aw call setup.check-git --arguments '{"address":"https://host/owner/workspace.git"}'
aw call setup.create --arguments '{"name":"demo","address":"https://host/owner/workspace.git","mode":"remote"}'
aw call setup.create --arguments '{"name":"demo","address":"https://host/owner/workspace.git","mode":"connect"}'
```

命令示例采用 POSIX shell 引号；其他 shell 可以将 JSON 写入文件并使用 `--arguments @file.json`。

新建通过普通实例创建流程建立 Steward、Sentinel、Maintainer 及各自的来源记录、目录、七个 Skill。没有创建默认 Work，没有启动模型或巡检。首次配置过程中部分成功会返回 `state=pending`，保留原位置和创建记录，修复访问问题后用完全相同的参数继续。创建记录保存在本机 `AW_HOME/setup`，不是跨机恢复协议；不要删除该目录后期待按名称猜测原操作。

重复请求只复用对应请求已经创建的实例，不覆盖用户资料或配置。普通 `agent create` 仍拒绝同名实例；需要明确重试时可使用固定 `--id` 与 `--request-id`。可恢复创建暂不用于外部文件导入。实例目录先完整写入临时同级位置，再发布到目标目录，避免失败后留下半份目录。

“接入已有”仅登记空间，不重建三名管家，也不自动接管已有执行权。在配置区选择已有实例并点击“在本机准备选中实例目录”，才取得本机副本。后续仍需本机 Harness 和认证，原机有有效入口时须先交接。低层 `App.workspace_init` 和旧 `workspace bootstrap-remote` 仍保留预览格式，旧 Workspace 不自动补建小组；新用户使用本页入口。

## Codex CLI 配置

配置区用于管家和普通实例，模型服务保持为原生 Harness 配置，不增加网关或 SDK 依赖。每个实例可以单独选择模型、推理强度、自有 URL 和凭据环境变量名。对新建空间可选择将相同配置分别保存到登记的三名管家，失败会报告已完成项。

自有服务需要满足 Codex Responses 协议；URL 不是协议转换器。HTTP 仅允许回环地址，其余使用 HTTPS。API 密钥由用户在启动工作台的环境中准备，页面只保存环境变量名。选择值以进程 `-c` 参数和现有实例 Runtime 配置传入，不修改全局 Codex 配置，不影响其他实例；依赖原生默认值的字段留空即可。

“查询元数据”是用户明确发起的探测，短暂启动 Codex app-server 并调用 `account/read`、`model/list`，不调用会话/轮次创建或登录接口。只展示过滤后的元数据；认证配置存在不等于实际模型调用成功。自有端点不采用 Codex 内置模型目录来冒充服务发现，需要按服务说明填写原生模型 ID 和强度。改变端点后清除旧候选。

保存配置不会启动会话，当前实例已有入口时拒绝改写，需先交接。进入原工作台后可以明确调用现有“进入新会话”。程序实际返回的 starting、awaiting_new_session_bind、active 等状态仍须区别，不能仅因子进程启动便认定初始化完成。

## 当前边界与验收

当前已有环境检测、只读 Git 探测、可补齐的三实例创建、首次配置 UI；首次向导的配置区以 Codex 为入口，其他 SDK 配置可进入主工作台或使用 CLI。运行、自动交接、管家授权、程序定时巡检与受限维修的实际操作和缺口统一见 [运行与维护说明](runtime-and-maintenance.md)。

没有增加 ACP、模型网关、账号管理器、插件市场或通用任务调度器。安装、登录、模型调用和巡检启用仍是明确分开的步骤。已有资料和当前入口不因重新打开向导而重建或接管。

真实临时 Git、配置协议、CLI/HTTP、原生客户端与回环 API 测试不能代替真实模型、Desktop、生产远端和企微验收。采用原生参数的依据为对应 Harness 官方配置和 SDK 文档；升级支持版本时需重新验证。
