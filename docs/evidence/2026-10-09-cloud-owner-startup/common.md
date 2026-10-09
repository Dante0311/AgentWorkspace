# 云端功能 Owner：本批启动与开发操作说明

本文件与对应角色的启动提示词一起使用。它落实用户本轮要求：让尚未建立的三个功能 Owner 通过普通 ChatGPT 云会话和现有 GitHub 工具开始研发，包括修复 AW-RUNTIME-001、AW-RUNTIME-002。无需安装 AW，也不以能够运行本地命令为前提。

这是已由用户选择、此前由 Workbench 实际试用的 GitHub 手动操作方式。`kind=manual, session=null` 是本轮采用的协议扩展；现有 `0.1.0a1` 的 `agent.bind` 仍要求原生 Session ID。不要因此伪造 ID，也不要宣称正式 CLI、自动唤醒或原生停止观测已经支持该扩展。

## 1. 对象、授权与资料

- 协作仓：`Dante0311/AW-Workspace`，Workspace 别名 `aw-team`。预期 locator 为 `workspace:setupda5f4c6eab2c4b938ff1c7ebb72a6977`，执行前必须从当前 `main:workspace.json` 核对。
- 产品仓：`Dante0311/AgentWorkspace`。研发基线固定为 `62760fae3df05b84766a35b24d3f4d31b1aeb63b`；它包含两个缺陷的记录及真实失败证据。日常安装仍来自 `00fb6bdb61f4accf47067b7acff48b9e5fc6284b`，两者不能混称同一版本。
- 本批集成目标：产品仓 `codex/cloud-owner-recovery-20261009`。每位 Owner 在自己提示词指定的代码分支工作，提交 Draft PR 到该集成分支，由 Lead 集成；不直接修改产品 `main`。
- 实例长期资料保存在协作仓 `instance/<自己的 agent ID>`。代码保存在产品仓任务分支；不要把产品源码放入实例分支，也不要把整个实例分支合入共享 `main`。
- 三个新角色的职责来源固定为协作仓 `32fb3d000bb265452e04c3918862d0025b67d1ef` 下的 `definitions/<agent ID>/definition.md`。创建后以自己的 `AGENTS.md`、产品仓 `AGENTS.md`、`docs/design.md`、`docs/implementation.md` 为依据，不在本材料中另建产品合同。

本轮允许建立自己的这一个身份和手动入口、保存自己的资产与检查点、在指定产品分支研发并提交 Draft PR，以及向本 Workspace 已登记的 `lead`、`e2e`、`core`、`runtime-adapter`、`communication-maintenance`、`workbench` 发送本任务必要的正式协作消息。发信前核对实际登记；不存在的收件人不代建、不猜 ID，不因此停下自己能做的工作。

本轮没有授权接管其他实例、修改管家授权、启用日常 Watch/巡检、升级日常安装、运行付费模型或外部渠道测试、向真人发送外部消息、合并 PR 或发布软件。三个管家的现有停止请求、检查点和旧会话由 Lead 后续安排恢复；云端研发不得手改这些状态来验证修复。

读取自己的平台 Skill，理解相应动作的保存、执行权和交接规则。遇到需要本地 AW 命令的操作，不声称已执行；本批仅对下面明确列出的 GitHub 手动操作使用协议等价步骤。无 GitHub 写工具时如实报告缺失的能力，先做当前工具允许的源码调查，不虚构登记或提交。

## 2. 所有既有分支写入的方法

以下是工具功能后缀，使用当前会话实际可调用的 GitHub 工具。不要靠网页上的文字或自然语言答复判断写入成功。

1. `github_fetch` 读取 `https://api.github.com/repos/OWNER/REPO/git/ref/heads/BRANCH`，记 `object.sha` 为 H；再读 `git/commits/H` 取得 `tree.sha`。
2. 用 `github_fetch_file(ref=H)` 检查本步依赖的记录。必须在同一快照检查，不能拼接不同版本的前提。
3. `github_create_tree(base_tree_sha=原 tree SHA)`，只列本步变动，保留其他文件。文本条目形如 `{"path":"相对路径","mode":"100644","type":"blob","content":"完整 UTF-8 文本"}`。
4. `github_create_commit(parent_sha=H, tree_sha=新树 SHA)` 得到 NEW。
5. `github_update_ref(branch_name=BRANCH, sha=NEW, expected_sha=H, force=false)` 发布。
6. 读回记录和分支，确认内容及实际提交。远端已经前进时核对 NEW 是否在历史中，不把别人后续提交误判为本次失败。

冲突后读新版本、重查业务前提，再制作条件提交；不 force push。结果未知时核对原 ID、原提交及实际远端状态，不能换一套 ID 重试可能已经完成的操作。无法确认则保留证据并报告。

每次先选择并记下本会话操作所需的唯一 ID：Binding 用 `b`、检查点用 `c`、消息用 `m` 开头，总长 1–64 个字母、数字、下划线或短横线。用工具可提供的随机 UUID 等可靠方法产生后缀；不冒充原生会话 ID。时间使用实际操作时的 UTC ISO 8601 时间。

需要共同成立的记录放在同一次 tree/commit 中。不可变记录首次写入必须确认不存在；相同原操作已完成则复用，内容不同则不覆盖。JSON 为 UTF-8、两个空格缩进和末尾一个换行；补写保留原始内容。

## 3. 创建自己的实例，仅首次需要

读取本目录 [bootstrap-manifests.json](bootstrap-manifests.json)，只使用 `roles` 中自己 ID 对应的条目。它是创建模板，文件存在不代表实例已经创建。每份模板包含 14 个已核对的平台资源 blob 和 4 个本实例文件，共 18 个文件；不得复制其他实例的身份、Binding、历史或检查点。

同时核对当前共享 `main`、`agents/<自己>.json` 和 `instance/<自己>` 分支。准备材料时三个新角色均不存在，但执行时必须重读。已有登记时不得覆盖；已有 active/stopping 入口而本会话没有拥有它的真实操作记录时，停止实例写入并报告，不借用现成 Binding。

若登记和实例分支都不存在：

1. 核对 `workspace.json` locator、固定职责来源和清单内容。将本角色条目中的 `<ACTUAL_UTC_CREATED_AT>` 替换成同一个实际创建时间；不得重新生成职责、来源 hash、creation fingerprint 或平台资源内容。
2. 在协作仓调用 `github_create_tree(base_tree_sha=null, tree_elements=本角色的 instance_tree_elements)`。这是新实例的独立 18 文件树，不能以共享 main 的整棵树为 base。
3. 创建提交时 `parent_sha` 使用本步读取的协作仓 main 提交 H，`tree_sha` 使用上一步结果。然后仅创建 `instance/<自己>` 分支指向此提交；不更新 main，也不覆盖已有分支。
4. 读回 `.aw/identity.json`、`.aw/creation.json`、`AGENTS.md`、`source.json` 及资源列表。然后按第 2 节在共享 main 新增 `agents/<自己>.json`，内容必须等于实例分支保存的 `.aw/creation.json`。登记前重新检查目标路径不存在、Workspace 未变。
5. 读回共享登记与实例分支，确认身份、分支、来源和创建记录一致。

如果分支创建成功、登记未完成，核对该分支 `.aw/creation.json` 的 ID、creation 请求与 fingerprint，以及 `.aw/identity.json`。全部属于这份确定的创建请求时，仅将已经保存的创建记录补登记到 main；保留原创建时间及全部资产，不再建分支。未知结果先核对，不能重新创建。

## 4. 登记本会话的手动入口

令 A 为自己的 agent ID，B 为本会话一次性选择的 Binding ID。首次启动预期 `archived=false, current=null, has_run=false, handoff=null`。同一 main 快照检查这些条件与 `bindings/B.json` 不存在。

一次提交同时新增下列 Binding，并在完整 `agents/A.json` 中只改 `current=B, has_run=true, handoff=null`：

```json
{
  "id": "<B>",
  "agent": "<A>",
  "kind": "manual",
  "phase": "starting",
  "session": null,
  "created_at": "<实际 UTC 时间>",
  "handoff": null
}
```

读回后重新取 main，确认 current 仍为 B、B 属于自己且处于 starting、本会话确实执行过预留，再只把同一 Binding 的 `phase` 改成 `active` 并读回。session 保持 null，不建立虚构的 `sessions/manual/*` 索引。

这一步只证明当前会话按手动协议登记，不证明原生会话核验、Watch 或自动投递。此后每次实例写入、发信、ACK、发布检查点前，都检查 current 仍为 B、实例未归档、Binding 属于自己且为 active。资格变化后停止写入。不得把旧会话的 B 复制给新会话使用。

本会话操作中断后，只能凭自身已有工具记录续做原 B；不能从远端读出一个 active B 就自称拥有者。`has_run=true` 且无可用当前入口时需要正常 handoff/relay，不走这里的首次启动步骤。

## 5. 建立代码分支并开始本次研发

读取产品固定基线上的 `AGENTS.md`、`README.md`、`docs/design.md`、`docs/implementation.md` 与 [真实失败记录](../2026-10-09-caretaker-relay/README.md)。核对当前源码是否仍有对应缺陷；已被其他提交修复的部分先核对实际结果，不重复造另一套实现。

用 `github_create_branch` 在产品仓从 `sha=62760fae3df05b84766a35b24d3f4d31b1aeb63b` 创建自己提示词指定的代码分支。若分支已存在，先核对其来源与实际工作，不重置或覆盖。按第 2 节提交最小变更；有真实代码环境时也可以用正常 Git 完成相同工作。

Runtime / Adapter 是两个 Bug 的主负责人；Core 负责公共存储与执行权规则上的配合；Communication / Maintenance 负责诊断和授权恢复入口。先读真实调用链，避免三方各写一份重试或停止确认循环。跨域接口由负责业务的一方实现，相关 Owner 直接协商；共享文件需要修改时明确由谁提交。没有新接口结论时，先完成本领域独立的调查和验证，不为等待消息或 ACK 停掉全部研发。

本次明确交付了修复任务，不能只问候、保存启动记录后待命。完成当前工具允许的调查、实现和验证；遇到确实阻止后续工作的权限或接口问题时说明缺什么、影响什么，保留已经完成的成果。测试能力缺失时明确列出未运行项，提供可执行命令及预期结果；不能把阅读代码或 GitHub 接受提交称为测试通过。

## 6. 协作消息与收件

普通云会话本轮没有自动唤醒能力。进入本次任务、收到用户新一轮指令或完成一个需要协作的阶段时，顺便读取自己的未确认消息；不要无限轮询，不把这种主动读取计作 AW 自动收件验收。Lead 当前运行器异常，因此消息发布后继续自己可执行的工作，不等待自动回复才开工。

发信前核对当前入口与真实收件人。为一次必要消息选择 M；同一 main 提交新增两份记录：

`messages/M.json`：

```json
{
  "id": "<M>",
  "from": {"workspace": "<实际 locator>", "agent": "<A>"},
  "to": {"workspace": "<同一 locator>", "agent": "<实际收件人>"},
  "created_at": "<实际 UTC 时间>",
  "message_refs": [],
  "delivery": "normal",
  "content": "本次实际进展、需要协作的具体接口或提交与验证链接"
}
```

`message-index/M.json` 只保留同一消息的 `id, from, to, created_at, delivery` 五个字段，值完全一致。回复在 `message_refs` 中保留真实被回复 ID。读回后只报告已发布，不替收件人写 ACK，不据此声称对方已处理。

收件时在同一 main 快照筛选 `message-index` 中 to 为自己的条目，排除已有 `acks/M.json` 的通知，按 `created_at, id` 排序。先核对收件人并实际尝试读取正文，再确认自己的资格，新增 `acks/M.json`，内容为 `{"message_id":"<M>"}`。正文无法读取则如实保留该事实；ACK 仅确认通知，不表示读取成功或业务完成。已有确认不重复产生业务副作用，需要回看可只读。

正式技术讨论、进度和交付通过这些消息留痕；本会话同时向用户直接报告可点击的代码与证据链接，不要求用户手工转发每条消息。不得处理或确认原来发给 Lead 的 Workbench 测试消息 `m4914c0f7229040be8bb1419fbc0c1994`。

## 7. 资料、检查点与交付

进入后在自己的实例分支保存 `notes/startup.json`，记录职责来源、真实 B、产品代码分支、当前任务、工具能力和未验证项；不写凭据、机器路径或原生私有会话全文。已有文件通过条件更新保留重要历史。实例资产是持续资料；问题、设计、代码与验收证据仍以产品仓正式落点为准，不复制另一套产品状态系统。

初始化完成、重要任务阶段或需要交接时创建新 C。确认 B active，在实例分支提交实际资料及 `.aw/checkpoints/C.json`：

```json
{
  "id": "<C>",
  "created_at": "<实际 UTC 时间>",
  "summary": "实际已完成工作与下一步",
  "content": "实际修改、提交、验证、未完成事项及必要资料路径；仅保存实例 Git 资产。",
  "record_refs": [],
  "scope": "Instance Git assets only; native conversation export unavailable."
}
```

取得该实例提交的确定 SHA R，重新检查 B active，然后在共享 main 新增 `checkpoints/A/C.json`：

```json
{
  "id": "<C>",
  "agent": "<A>",
  "revision": "<R>",
  "path": ".aw/checkpoints/<C>.json",
  "created_at": "<与检查点正文完全相同的时间>",
  "excluded": []
}
```

按指针中的 R 读回正文和实际资料，才算检查点已发布。main 登记失败时只补原 C/R 指针，不修改旧检查点或用后来 HEAD 替代 R。`excluded=[]` 仅表示本次保存的 Git 资产没有排除项，不表示备份了产品工作区或原生聊天。

交付包含产品提交或 Draft PR、实际变化、已运行的验证、明确未测项，以及 E2E 可执行的验证步骤。协议/单测、真实 GitHub、真实 Harness、Desktop 和长期运行分别报告。若创建 PR，使用当前环境提供的附件工具关联当前会话。

本轮不自动 handoff 或创建后继。用户后续要求换会话时再按相应 Skill 保存和交出，手动入口确认与 Desktop 观测分别处理，不能借本协议释放三个仍在 stopping 的 Desktop 管家。
