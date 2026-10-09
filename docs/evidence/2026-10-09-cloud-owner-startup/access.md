# 同一套提示词怎样在本机和云端执行

这些 Markdown 是可复制的操作入口：startup 对应首次初始化，handoff 对应交出，relay 对应交出后的接手。它们复用实例 Skill、平台当前能力与产品合同，不另设一套生命周期，也不根据环境把 startup 自动改成 relay。

复制并发送某个入口，只授权其中明确的操作。先确认用户要执行的是哪一个，读取本实例相应 Skill 和能力说明，再选择下面实际可用的工具。不要把只读到材料、接受请求或完成一部分操作报告为整个操作成功。

## 有正式 AW 工具时

优先使用本会话实际可调用的 AW MCP、HTTP 或已配置 CLI。本机和云端都可以走这条路径，不按“云端”三个字强制改用 GitHub。

- 通过实际进入材料、实例身份文件及 `agent.show` 核对 Workspace、Agent、Binding、入口种类和当前资格。显示名称或一个已有 Binding ID 不能证明本会话拥有它。
- 桌面入口使用进入材料规定的调用前缀；不改真实会话 ID、去掉调用身份或改变目录来绕过授权。工具参数使用当前真实 schema，不凭示例猜写。
- 身份创建、接入、首次进入使用 `agent.create / agent.connect / agent.start / agent.bind` 中实际需要的操作；这些是工具名，不意味着每次都顺序调用全部。已经由平台准备并绑定到本会话的入口直接核验，不再创建或 start。
- `agent.start` 可能创建另一个真实原生会话，也可能返回待绑定材料。尊重实际返回；不能把另一个新会话的 Binding 冒充本会话的资格。管理权限不足时说明具体缺项，由有权限的入口完成，不用 GitHub 改记录绕过拒绝。
- 资料读写使用 `asset.read / asset.write` 等正式操作，写入带上实际读到的 revision；检查点使用 `checkpoint.create / checkpoint.show`；交出使用 `agent.stop`；接手使用正式进入流程并加载固定检查点。不要直接编辑 `.aw`、Binding 或交接记录替代工具。
- 缺少真实 Session ID、Harness 配置或新会话绑定权限时如实说明。不得将 Desktop/CLI 静默降为 manual，也不得虚构 session 来通过校验。

本批角色首次创建时，`workspace=aw-team`、自己的 `agent_id/name`、`definition=definitions/<自己>`、`revision=32fb3d000bb265452e04c3918862d0025b67d1ef` 与对应清单的 `request_id` 可以交给正式 `agent.create`。平台资源由实际安装版本生成，不手工把旧资源清单覆盖回正式工具创建的实例。本机工作目录由已给定位置或正常创建规则确定，不把产品 checkout 当作实例根。

## 没有正式 AW 工具时

在用户已经选择的 `aw-team` GitHub 手动方案内，使用 [GitHub 操作细节](github-operations.md)。它把相同的身份、条件写入、检查点和交接规则落实到当前可用的 GitHub 工具；不能借此扩大调用身份或绕过正式工具的权限拒绝。

- 必须有实际可用的 GitHub 读取和所需写入工具；无相应工具则报告不能完成的步骤，不伪造登记。
- 这条路径只建立或使用明确选择的 manual 入口。`session=null` 是用户已选择的当前试验范围；现有 `0.1.0a1` 正式 `agent.bind` 仍要求真实 Session ID，本材料未修改它。
- 当前已有 Desktop/CLI Binding 时，handoff 仍需它自己的真实停止观测。GitHub 能读写仓库不等于有权把该 Binding 改成 manual 或直接释放它。继任 manual 会话只能消费已经合法发布的 handoff。
- 只用条件提交保存相应操作，并读回实际结果。请求结果未知先核对原 ID 和记录；不 force push、不换 ID 重做可能已完成的操作。
- 手动 GitHub 路径没有因此获得自动唤醒或原生观察能力；消息已发布、主动读取、ACK 和完成工作分别报告。

所有路径都沿用同一个 Workspace、实例身份和资产来源。访问方式不同不创建第二套身份、不增加另一份职责文件，也不改变四个入口状态的含义。

## 读取规则的来源

优先读取实际实例的 `.agents/skills/` 与 `.aw/prompts/`；没有本机文件时，从该实例分支或固定版本中读取同一材料。

- 初始化：[agent Skill](../../../src/agent_workspace/resources/skills/agent/SKILL.md) 与 [initialization.md](../../../src/agent_workspace/resources/prompts/initialization.md)。
- 交出：[handoff Skill](../../../src/agent_workspace/resources/skills/handoff/SKILL.md) 与 [检查点说明](../../../src/agent_workspace/resources/prompts/checkpoints.md)。
- 接手：[relay Skill](../../../src/agent_workspace/resources/skills/relay/SKILL.md) 与当前能力说明。
- 正式规则：[产品设计](../../design.md)。底层进入工具可复用，但本批用户入口明确分开：startup 只初始化，relay 只接手。

固定链接的来源用于追溯；实际安装能力不足或记录状态不满足时，保留失败事实并报告，提示词本身不能补出缺失功能。
