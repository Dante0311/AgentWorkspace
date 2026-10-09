# GitHub 操作细节：相同动作的手动访问方式

本文件供 startup、handoff、relay 提示词在没有正式 AW 工具且具备相应授权时引用。先按 [工具选择说明](access.md) 核对能力、身份和当前操作；本文件本身不授权执行任何生命周期动作。

仅在用户已选择的 aw-team manual 方案内使用。这里列出与当前记录格式兼容的条件写入步骤，复用正式 Skill 的执行权、检查点、交出和接手规则；不是一套新的平台合同。现有 `0.1.0a1` 的 `agent.bind` 不接受 null Session，本文件未修改正式命令。不得用这些步骤绕过正式工具的权限拒绝或强制处理 Desktop/CLI 停止。

协作仓为 `Dante0311/AW-Workspace`。令 A 为目标实例 ID，B 为本会话实际拥有的 Binding；先读当前 `workspace.json` 验证 locator。startup 本批三角色使用 [创建清单](bootstrap-manifests.json)；handoff/relay 不使用创建清单、不重建身份。

## 1. 所有既有分支写入的方法

以下是工具功能后缀，使用当前会话实际可调用的 GitHub 工具。不要靠网页上的文字或自然语言答复判断写入成功。

1. `github_fetch` 读取 `https://api.github.com/repos/OWNER/REPO/git/ref/heads/BRANCH`，记 `object.sha` 为 G；再读 `git/commits/G` 取得 `tree.sha`。
2. 用 `github_fetch_file(ref=G)` 检查本步依赖的记录。必须在同一快照检查，不能拼接不同版本的前提。
3. `github_create_tree(base_tree_sha=原 tree SHA)`，只列本步变动，保留其他文件。文本条目形如 `{"path":"相对路径","mode":"100644","type":"blob","content":"完整 UTF-8 文本"}`。
4. `github_create_commit(parent_sha=G, tree_sha=新树 SHA)` 得到 NEW。
5. `github_update_ref(branch_name=BRANCH, sha=NEW, expected_sha=G, force=false)` 发布。
6. 读回记录和分支，确认内容及实际提交。远端已经前进时核对 NEW 是否在历史中，不把别人后续提交误判为本次失败。

冲突后读新版本、重查业务前提，再制作条件提交；不 force push。结果未知时核对原 ID、原提交及实际远端状态，不能换一套 ID 重试可能已经完成的操作。无法确认则保留证据并报告。

每次先选择并记下本会话操作所需的唯一 ID：Binding 用 `b`、检查点用 `c`、消息用 `m` 开头，总长 1–64 个字母、数字、下划线或短横线。用工具可提供的随机 UUID 等可靠方法产生后缀；不冒充原生会话 ID。时间使用实际操作时的 UTC ISO 8601 时间。

需要共同成立的记录放在同一次 tree/commit 中。不可变记录首次写入必须确认不存在；相同原操作已完成则复用，内容不同则不覆盖。JSON 为 UTF-8、两个空格缩进和末尾一个换行；补写保留原始内容。

## 2. 创建自己的实例，仅首次需要

读取本目录 [bootstrap-manifests.json](bootstrap-manifests.json)，只使用 `roles` 中自己 ID 对应的条目。它是创建模板，文件存在不代表实例已经创建。每份模板包含 14 个已核对的平台资源 blob 和 4 个本实例文件，共 18 个文件；不得复制其他实例的身份、Binding、历史或检查点。

同时核对当前共享 `main`、`agents/<自己>.json` 和 `instance/<自己>` 分支。旧版材料准备时三个新角色均不存在，这不是执行时的实时状态；每次必须重读。已有登记时不得覆盖；已有 active/stopping 入口而本会话没有拥有它的真实操作记录时，停止实例写入并报告，不借用现成 Binding。

若登记和实例分支都不存在：

1. 核对 `workspace.json` locator、固定职责来源和清单内容。将本角色条目中的 `<ACTUAL_UTC_CREATED_AT>` 替换成同一个实际创建时间；不得重新生成职责、来源 hash、creation fingerprint 或平台资源内容。
2. 在协作仓调用 `github_create_tree(base_tree_sha=null, tree_elements=本角色的 instance_tree_elements)`。这是新实例的独立 18 文件树，不能以共享 main 的整棵树为 base。
3. 创建提交时 `parent_sha` 使用本步读取的协作仓 main 提交 G，`tree_sha` 使用上一步结果。然后仅创建 `instance/<自己>` 分支指向此提交；不更新 main，也不覆盖已有分支。
4. 读回 `.aw/identity.json`、`.aw/creation.json`、`AGENTS.md`、`source.json` 及资源列表。然后按第 1 节在共享 main 新增 `agents/<自己>.json`，内容必须等于实例分支保存的 `.aw/creation.json`。登记前重新检查目标路径不存在、Workspace 未变。
5. 读回共享登记与实例分支，确认身份、分支、来源和创建记录一致。

如果分支创建成功、登记未完成，核对该分支 `.aw/creation.json` 的 ID、creation 请求与 fingerprint，以及 `.aw/identity.json`。全部属于这份确定的创建请求时，仅将已经保存的创建记录补登记到 main；保留原创建时间及全部资产，不再建分支。未知结果先核对，不能重新创建。

## 3. startup：首次手动入口

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

本会话操作中断后，只能凭自身已有工具记录续做原 B；不能从远端读出一个 active B 就自称拥有者。`has_run=true` 且不是本会话本轮已预留的首次入口时，不走本节。报告 startup 前提不符，不在这个入口自动改做 relay。

## 4. 当前入口的资料与检查点

仅当前 active 入口可以新增业务资料和检查点。按本次操作保存实际需要延续的资产，保留累计资料和原始来源；不要把不同操作都写成一次新 startup。已经 stopping 时只继续既有停止请求，不再新建检查点或执行业务。

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


## 5. 已授权任务需要的消息与 ACK

只有当前 active 入口、实际任务需要且收件人属于用户授权范围时使用。本节不要求 handoff 或 relay 必须发一条测试消息。

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

正式技术讨论、进度和交付通过这些消息留痕；本会话同时向用户直接报告实际结果。不得处理或确认原来发给 Lead 的 Workbench 测试消息 `m4914c0f7229040be8bb1419fbc0c1994`。

## 6. handoff：请求停止与完成交出

本节只能处理本会话实际拥有的 `kind=manual` 入口。Desktop/CLI 即使已经结束回复，也必须由正式适配器和恢复流程确认；不能按本节直接写 released。没有本会话拥有当前 B 的真实记录时，不凭读到的 B 取得资格。

1. 在 active 时完成第 4 节，取得实际 C/R。读取共享指针并按 R 核对检查点正文，确认属于 A。
2. 在同一个 main 快照核对 A 未归档、`current=B`、B 属于 A 且 kind=manual、phase=active，以及检查点记录仍为原内容。
3. 保留 Binding 的其他字段，只更新 `phase=stopping, checkpoint=C, stop_requested_at=实际 UTC 时间`，按第 1 节提交并读回。已经由本会话发出的同一停止请求则读取原 C/R，不重新发起或替换检查点。
4. 结束业务执行。仅收到**当前使用者明确确认该旧会话业务已经停止**后继续释放；原消息只说“请 handoff”、一次回复结束或长期无响应，都不代替确认。未取得确认时报告 waiting for explicit manual stop confirmation。此时旧入口仍拥有资格，不能给新会话预留入口。
5. 取得上述确认后，重新读取 main，核对 current 仍为 B、B 为同一 manual/stopping 请求、原 C/R 可读。令 X 为 `"h" + B 去掉首字符后的内容`。X 不存在时，用同一条件提交完成下列三个文件：
   - 在完整 `agents/A.json` 中只改 `current=null, handoff=X`，保留 `has_run=true` 和其他字段；
   - 在完整 `bindings/B.json` 中只改 `phase=released, stopped_at=实际 UTC 时间`，保留原 session、checkpoint 与停止请求；
   - 新增 `handoffs/X.json`：

```json
{
  "id": "<X>",
  "agent": "<A>",
  "entry": "<B>",
  "checkpoint": "<C>",
  "created_at": "<本次释放的实际 UTC 时间>",
  "consumed_by": null
}
```

6. 读回旧 Binding、handoff 与 Agent；三者一致才报告交出完成。明确结果依据是使用者对 manual 停止的确认，不是原生进程隔离或平台观察到了物理停机。
7. 结果未知先查原 B/X/C。若该原操作已经完整发布，则只报告已有结果；若 X 已被合法后继消费，也不能退回 null 或清空新 current。只出现部分结果、内容冲突或无法判断时报告，不能补造完成状态。

仅在 X 已发布、未消费且可读时输出给新会话的 relay 材料。不要在 handoff 中消费 X、预留 B2 或创建新聊天。停止后需要补足的确认只是控制操作，不恢复业务。

## 7. relay：消费已完成的交接

只在另一个真实新会话中执行。实例必须已经运行并合法 handoff；没有 X 时不自动改做 startup。原 B 是来源，不是后继可以复用的资格。

1. 从用户交接材料确定 A、X、C、R。读取同一个 main 快照，核对 A 未归档、`has_run=true, current=null, handoff=X`；X 属于 A、`consumed_by=null`，指向原 B 和 C；原 B 已 released，且与 A/C 一致。按共享检查点指针的固定 R 读回正文和必要资产；任何一项未满足都不取得新资格。
2. 为这个真实新会话选择一次性的 B2。确认 `bindings/B2.json` 不存在，在一次 main 条件提交中同时：
   - 将完整 `handoffs/X.json` 的 `consumed_by` 改成 B2；
   - 将完整 `agents/A.json` 改成 `current=B2, handoff=null`，保留其他字段；
   - 新增以下 Binding：

```json
{
  "id": "<B2>",
  "agent": "<A>",
  "kind": "manual",
  "phase": "starting",
  "session": null,
  "created_at": "<实际 UTC 时间>",
  "handoff": "<X>"
}
```

3. 读回后重新取 main，确认 X 已由本会话的 B2 消费、A.current=B2、B2 仍 starting 且指向 X，才把同一 Binding 的 phase 改为 active；其他字段保持不变，再读回。session=null 仍只在本次 manual 扩展范围内使用，不声称验证了原生身份。
4. 若返回不确定，先核对原 X/B2。仅有本新会话自己的实际操作记录、且远端恰为这个预留结果时，才续做激活。X 已被其他 Binding 消费则不得覆盖。不能从“知道 B2 的值”推定自己是拥有者。
5. 取得 active 资格后，加载固定检查点及实例原有 AGENTS.md、Skill、累计资产与任务关联。当前实例 HEAD 与 R 不同时核对差异、保留后来资产，不把分支直接 reset 回 R；本地文件有差异也不覆盖。读取必要原始资料，不自行筛掉历史。
6. 保存真实接手事实，报告 X/B2/C/R、当前能力和未解决项；后续仅继续用户授权的工作。需要新检查点时使用第 4 节，旧检查点不变。所有后续写入继续核对 current=B2 和 active，旧 B 不得恢复。

正式 AW 工具已经为这个新会话预留或绑定后继时，使用正式流程核对该结果，不另外走本节再造一个手动入口。
