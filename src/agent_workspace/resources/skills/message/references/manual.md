# 仅有仓库工具或 Git 时的操作

先读 [精确协议](protocol.md)。手动操作仍使用用户/进入材料明确授予**本会话**的实例地址与 Binding，不从仓库抄 current 冒充接手。本 Skill 不创建 Agent、预留 Binding、绑定会话、抢占或释放入口，也不默认开启 Watch。

## GitHub 等仓库工具

无完整 AW、无 Python、未 clone 时，可以使用仓库工具。需要对明确目标仓库的读权限；发布另需允许写 `main`、创建 Git 对象和条件移动 ref 的权限。好友配置、公开仓库或能创建 blob 不等于有发布权限。

1. 读 `refs/heads/main` 的 HEAD `H`，再读 **H 对应 commit 和 tree**。固定在 H 读取 `workspace.json`、自身 `agents/<id>.json`、明确获授的 `bindings/<binding>.json`；核对 locator、实例、current、archived=false、Binding 归属和 phase=active。不能用不同时间的默认分支文件拼资格，也不能接受截断 tree。
2. 在同一 H 读 `message-index/<id>.json` 和 `acks/<id>.json`；核对 index.id/to。已有 ACK 不再开展业务，回看历史即可；原部分发布另核对原操作。没有 ACK 时尝试读 `messages/<id>.json` 的原 blob，记录成功或失败。正文失败也可 ACK 可定位的通知，但不猜正文。
3. 在第一次可能发布前保存原 Message/索引或 ACK 的完整字节（可用 Base64）、稳定 ID、真实地址、首次真实时间、获授 Binding、双方 locator/仓库映射及已有提交/发布结果。材料是手动操作依据，不冒充 `.aw-local` 或 AW `operations` receipt；敏感内容留在获准位置。
4. 每次写入前再读 HEAD 和同版本资格、索引、目标登记、已有原记录。前提或原字节变了就停止；不能覆盖他人修改。创建所缺 blob，以当前 commit 的 `tree.sha` 为 **base_tree** 创建新 tree，保留其余路径；创建新 commit，**parents=[当前 HEAD]**。只添加本次消息/索引或 ACK，不写 agent/binding/Work。
5. 条件移动 `refs/heads/main`：使用确实比较预期 HEAD 的 `expected_sha=H`、Git 显式 lease 或等效 CAS。新 commit 必须是 H 的直接子提交，不能删历史。GitHub 仓库工具若声明 `update_ref(expected_sha=...)` 的原子比较合同，可以按其实际参数使用；参数名本身不证明执行语义。普通 GitHub REST PATCH 只有 sha/force，`force=false` 的快进检查不是“当前 SHA 等于 H”的比较；不要自造 REST expected_sha。工具不能安全 CAS 时保留已准备对象，明确未发布，交给能安全发布的获准端。
6. 按返回的新 ref/commit/tree 读回原路径字节。响应丢失时先核对原 commit 是否在当前分支祖先中、原 ID 的 Message/索引或 ACK 是否具有原字节。确认原结果才报发布；不能确认则保持未知，不能盲目重放写入。明确 lease 冲突可以重读前提，基于新 HEAD 补相同原字节；未知结果不能当成已拒绝。部分双写按原目标逐一核对，只补缺失记录；不重发模型或业务动作。

跨两仓无法在一个事务中冻结双方资格；先在自己 Workspace 的条件提交里保护本入口，再补另一仓，补前重新核对当前资格、朋友路由与目标版本。入口被撤销后本会话停止写入，原部分发布保留给有权端核对。不要让维护身份凭名称绕过授权。

相关接口依据：[GitHub Git refs](https://docs.github.com/en/rest/git/refs#update-a-reference)、[Git 显式 lease](https://git-scm.com/docs/git-push)。这些说明操作机制，不授予目标仓库写权限。

## 主动发送第一条新 Message

没有原通知时也可以用仓库工具发起消息，不需要先制造 receive 或 ACK。沿用以上条件提交与读回步骤，区别如下：

1. 使用本会话明确获授的发送实例和 Binding，在自己 Workspace 的同一 HEAD 核对资格。由用户明确指定的实例地址和当前朋友配置确定目标；同 Workspace 读该 HEAD 的目标 `agents/<id>.json`，跨 Workspace 另固定对方 HEAD 核对 locator 和目标未归档。目标暂时没有入口仍可保存消息，不能为此创建或接管 Binding。
2. 选择新稳定 ID，核对双方 `messages/<id>.json`、`message-index/<id>.json` 和 `acks/<id>.json`。新 ID 应未使用；如已有原记录，只能按已保存的原操作核对，不能给已有 ID 新造时间或内容。异字节或无原操作材料的占用停止发布，不覆盖。准备一次完整 Message：真实 `from/to`、实际带时区时间、显式 normal/insert、非空 content 和可选 message_refs；没有原消息时不编造引用。
3. 保存完整 Message、其五字段索引的原字节和目标映射。在自己的当前 HEAD 再核对发送资格与 ID 空缺，使用该 HEAD 的 base_tree 和直接 parent，把 Message 与索引放在**同一个条件提交**中。同 Workspace 到此只发布一份；跨 Workspace 在重新核对当前资格/朋友路由和对方目标后，把相同两份字节条件提交到对方，不创建 ACK。
4. 各目标读回原字节才确认发布。冲突、部分成功或未知结果保留同一原操作，按上文核对；不重发模型动作，不修改原消息。回复复用这条发送协议，但使用新 ID 并把原消息 ID 加入 message_refs。

## 独立辅助脚本

`scripts/message_git.py` 只使用 Python 3.11+ 标准库和 Git 可执行程序，不 import agent_workspace、不需要 pip 安装 AW。它提供 show、receive 和接收后的 reply；主动发起第一条消息使用上节仓库协议。它针对 Message/ACK 固定路径，不替代完整 Backend 或执行业务。需要实际网络/认证及仓库权限；本地隔离仓库也可作为 origin。先为每个明确 Workspace 准备独立 bare clone，例如 `git clone --bare REPOSITORY_URL message-repo`；脚本 fetch origin 的 main 并使用单独索引，不改用户工作区/index。

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

脚本保存 `format=message-git-operation-v1` 的私有原操作文件，含原字节/Base64、actor、目标、每次提交和读回状态；它不是 AW receipt，不能拿给 `aw message reconcile`。同一 receive/reply 操作文件已存在时拒绝重新准备，必须核对并 continue；真实回复的 from/to 和 message_refs 由原可信索引确定，不转发到额外对象。继续命令须再次显式提供同一获授实例和 Binding，不能从文件改成新入口。

发布使用新 commit 的固定直接 parent 和 `--force-with-lease=refs/heads/main:EXPECTED_HEAD`；没有 `--force`、不重写历史、不自动循环。消息/索引/ACK已有不同字节则拒绝覆盖。`published` 需全部目标按原字节读回；`conflict` 表示明确 lease 拒绝，重读前提后可显式 continue；`outcome_unknown` 仅查询原记录，不再次 push。部分发布时已确认目标不重复提交，只补尚未开始写入的目标。

Git 读取错误暂停，不能当作路径不存在；文件确实缺失或 JSON 损坏时 receive 可以准备 ACK 并记录 read_error。脚本不自动分类或重试网络故障，详细临时错误核对由操作者按实际工具结果判断。进程退出可能留下此脚本的操作锁；先证明原进程已经退出并核对原记录，才可人工移除自己的失效锁，不能删除 AW 运行锁或不明文件。保留原失败和未知事实，不能用删除操作文件来重新生成请求。

脚本和协议不证明真实云端工具、Harness 收件或模型按 Skill 行动；这些需在具体环境另取证。消息已发布、通知已投递、ACK 已保存和业务已完成分别记录。
