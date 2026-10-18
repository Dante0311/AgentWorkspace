# 仅有仓库工具或 Git 时的操作

先按主 Skill 判断发送/回复通路，以下仅为正式 Message 的仓库操作；没有同机 Codex 真实观察能力时使用本路径。先读 [精确协议](protocol.md)。手动操作仍使用用户/进入材料明确授予**本会话**的 Agent 地址与 Binding，不从仓库抄 current 冒充接手。本 Skill 不创建 Agent、预留 Binding、绑定会话、抢占或释放入口，也不默认开启 Watch。

## GitHub 等仓库工具

无完整 AW、无 Python、未 clone 时，可以使用仓库工具。需要明确目标仓库的读权限，以及创建 Git 对象、条件移动所选消息 ref 的写权限。版本 3 的普通通信写 `aw-messages`，旧布局写 `main`；它们都不授予修改身份、Binding 或权限标记的权利。好友登记和能创建 blob 不等于能发表消息。

1. 先取 `refs/heads/aw-messages` 的消息提交 `M`（旧空间可尚无此 ref），再取 main 提交 `H`；固定读取各自 commit/tree，不接受截断 tree。按 [协议](protocol.md#地址与固定路径)判断 `H` 的布局。旧版 0/1/2 使用 `M=H`、消息 ref=main；版本 3 必须有明确的 aw-messages、消息角色标记与权限标记，不能因缺分支或缺文件退回 main。分别从各快照的布局解析 `P_main` 与 `P_msg`。
2. 版本 3 核对 `M` 中 `.agentworkspace/message-permissions.json` 的 main_revision 属于 `H` 的祖先或等于 `H`。在 `H` 读取 workspace.json、Agent、实际获授 Binding 和所属 Worker/历史映射，核对 locator、未归档、current 和 phase=active。旧单入口仍核对 Agent.current。消息索引和 ACK 从 `M` 读取，按 `H` 的 Worker 记录核对 index.to；不能把两份快照合成一个 revision，或从 current 抄值赋权。
3. 已有合法 ACK 不再开展业务；原部分发表另核对原操作。否则尝试读 `M` 中原 Message 的完整 blob，正文失败也可确认可信索引定位的通知，但不猜正文。首次可能发表前保存完整原字节/Base64、稳定 ID、实际时间、地址、获授 Binding、双方 locator/仓库映射和各次提交/分支/结果。材料不是 AW receipt。
4. 写入前重新完成以上消息先、资格后的读取。以本次采样的消息提交 `M` 为 base_tree 和唯一直接 parent，只添加原消息/索引或单字段 ACK，保留其他记录及权限标记。不能在核验 `H` 后单独取新消息 HEAD 来规避旧标记；消息条件或资格不再满足时停止。本 Skill 不修改 main 的身份、Worker、Binding、Work 或消息权限标记。
5. 对所选消息 ref 做真正的预期版本比较。Git 使用 `--force-with-lease=refs/heads/所选分支:M`，新 commit 必须是 `M` 的直接子提交，不能重写历史；GitHub GraphQL 使用 `updateRefs`，单项 refUpdates 指定 name、beforeOid=`M`、afterOid=新提交，并保持非强制更新。普通 REST PATCH 没有 beforeOid，不能自造 expected_sha；不能可靠比较的工具只准备对象并报告未发表。比较整个原消息 HEAD 同时保护原权限标记、原消息/索引、ACK 和 dispatch 条件。
6. 从实际消息 ref 按原字节读回同一 ID。超时或未知结果只核对原提交/原记录，当前缺记录也不能重新 push；明确版本冲突才可重新取得两份快照，在资格仍有效时用原字节创建缺失提交。已确认目标不重写，尚未开始的缺失端可继续原操作。期间显式迁移时按当前布局核对同一记录，保留原分支与原提交事实，不回旧位置找缺失文件，也不重发业务。

跨两仓无法在一个事务中冻结双方资格；先在自己 Workspace 的条件提交里保护本入口，再补另一仓，补前重新核对当前资格、朋友路由与目标版本。入口被撤销后本会话停止写入，原部分发布保留给有权端核对。不要让维护身份凭名称绕过授权。

权限变更由平台使用同一仓库的真正双 ref 原子更新：Git 的 `--atomic` 或 GitHub `updateRefs` 的多项 beforeOid。两次普通写入不满足这一约束，服务器缺能力时失败；本 Skill 不代行这些资格管理动作。接口依据：[GitHub updateRefs / RefUpdate](https://docs.github.com/en/graphql/reference/git#updaterefs)、[Git atomic 与显式 lease](https://git-scm.com/docs/git-push)。这些机制不授予仓库写权限。

## 主动发送第一条新 Message

没有原通知时也可以用仓库工具发起消息，不需要先制造 receive 或 ACK。沿用以上条件提交与读回步骤，区别如下：

1. 使用本会话获授的发送实例和 Binding，按上述顺序取得自己 Workspace 的消息/资格快照。由用户指定地址和当前朋友登记选择目标；同 Workspace 用 `H` 的目标 Agent/Worker，跨 Workspace 独立取得对方消息/资格快照。未指定 Worker 的新消息首次保存前解析默认收件 Worker，随后固定；回复选择原来源 Worker。目标离线可排队，归档则拒绝新消息，不能创建或接管入口。
2. 选择新稳定 ID，从双方各自消息快照查 Message、索引和 ACK。已有原记录只能按已保存原操作核对，异字节或无原材料的占用停止，不给相同 ID 新造时间或内容。准备一次真实 from/to、实际带时区时间、normal/insert、非空正文及可选关联引用；没有原消息不编造引用。
3. 保存完整 Message 和五字段索引原字节，在自己 Workspace 的原消息 HEAD 上条件发表这两份记录，保护采样权限标记和资格。同 Workspace 只存一份；跨 Workspace 在重新核对本入口、朋友路由与对方消息/资格快照后，把相同字节补到对方，不创建 ACK。
4. 各目标读回原字节才确认发布。冲突、部分成功或未知结果保留同一原操作，按上文核对；不重发模型动作，不修改原消息。回复复用这条发送协议，但使用新 ID 并把原消息 ID 加入 message_refs。

## 独立辅助脚本

`scripts/message_git.py` 只使用 Python 3.11+ 标准库和 Git，不 import agent_workspace、不需要 pip 安装 AW。它提供 show、receive 和接收后的 reply；第一条主动消息使用上节协议。需要实际网络、认证和仓库权限，本地隔离仓库也可作为 origin。每个明确 Workspace 使用独立 bare clone，例如 `git clone --bare REPOSITORY_URL message-repo`；脚本先采样消息 ref，再取 main，按明确版本选择消息分支和前缀，使用单独索引，不改用户工作区/index。

以下 `AGENT`、`GRANTED_BINDING`、消息 ID 和路径须替换为本会话实际材料。不要先运行一个查询来“获得” Binding。从 message Skill 目录执行，先读取或准备：

```sh
python scripts/message_git.py show --repo message-repo --agent AGENT --binding GRANTED_BINDING --id ORIGINAL_ID
python scripts/message_git.py receive --repo message-repo --agent AGENT --binding GRANTED_BINDING --id ORIGINAL_ID --record private-ack.json
python scripts/message_git.py reply --repo message-repo --agent AGENT --binding GRANTED_BINDING --id ORIGINAL_ID --content-file reply.md --request-id STABLE_REPLY_ID --record private-reply.json
```

跨 Workspace 在 receive/reply 上增加 `--peer peer-repo`，必须符合当前朋友 locator 和原消息方向。同 Workspace 不需要 peer。没有写权限时保留 `state=prepared`，不能说已经 ACK/回复。

在已有授权内明确发布可给首次 receive/reply 加 `--publish`，或核对保存的原操作后继续：

```sh
python scripts/message_git.py continue --record private-ack.json --agent AGENT --binding GRANTED_BINDING
python scripts/message_git.py continue --record private-reply.json --agent AGENT --binding GRANTED_BINDING
```

脚本保存 `message-git-operation-v1`（旧单入口）或 `message-git-operation-v2`（Worker）的私有原操作文件，含原字节/Base64、actor、目标、各次提交、分支和读回状态；这与仓库消息布局版本 3 是不同编号。文件不是 AW receipt，不能给 `aw message reconcile`。已存在的原文件必须核对后 continue，不重新准备；回复保留原索引确定的来源 Worker 和真实 from/to。继续须显式提供同一获授 Agent/Binding，不改成新入口。

两种私有操作文件的 records 都以 messages/...、message-index/... 或 acks/... 为逻辑键，按每个目标当前明确布局解析实际消息分支和路径。显式迁移后仍核对同一原记录，不改 payload、ID、来源索引或旧尝试的分支/提交事实。部分成功只补尚未尝试的缺失端；未知结果只观察，不重推原提交或新建操作。

版本 3 的发表使用采样的 aw-messages 直接 parent 和 `--force-with-lease=refs/heads/aw-messages:EXPECTED_HEAD`；旧布局使用 main 的对应 parent/lease。没有 `--force`、历史重写或自动循环。原权限标记随父提交保留，不读完 main 后换用新的消息 HEAD。异字节记录拒绝覆盖；published 要求全部目标按原字节读回，conflict 仅在明确 lease 拒绝时允许重新核对后显式 continue，outcome_unknown 只读回。首次目标校验失败不发表任何一端；部分发表后只补未开始的目标。

Git 读取错误暂停，不能当作路径不存在；文件确实缺失或 JSON 损坏时 receive 可以准备 ACK 并记录 read_error。脚本不自动分类或重试网络故障，详细临时错误核对由操作者按实际工具结果判断。进程退出可能留下此脚本的操作锁；先证明原进程已经退出并核对原记录，才可人工移除自己的失效锁，不能删除 AW 运行锁或不明文件。保留原失败和未知事实，不能用删除操作文件来重新生成请求。

脚本和协议不证明真实云端工具、Harness 收件或模型按 Skill 行动；这些需在具体环境另取证。消息已发布、通知已投递、ACK 已保存和业务已完成分别记录。
