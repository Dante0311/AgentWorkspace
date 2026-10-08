# Codex → tclaude / DeepSeek 增量独立复核

复核日期：2026-10-08。结论：**完整配置路径的真实交接、后续消息和本人停工闭环限定通过；便捷配置入口的方括号兼容缺陷仍成立；strict-aw_execute-only 不通过。** 本次没有修复产品。

## 范围与方法

只读核对 transfer-local / transfer-agent / transfer-peer 的执行证据、真实原生记录、共享 Git 协议和已安装源码。未启动模型、Runner、服务、测试或探针，未调用产品管理命令；本复核只新增此文件。旧 Watch、维护组及历史结论没有改动。

固定产品基线为 `5aaae00520374b022e0c38fa21f312f8e08629ba`；主仓历史归档 HEAD 为 `842cc66df6386188b9470d489df3935a89ea701b`，不能把后者称为产品修复。旧 [FINAL-REVIEW](../../2026-10-08-5aaae00-autonomous/review/FINAL-REVIEW.md) 的 SHA256 仍为 `6165ecfb610774e07e26f4b2ee151e7211962654c0a804b24b7fe17f998e6a3b`，此前 tclaude query=0 是历史事实，不由这次增量覆盖。

已核对 [执行报告](../reports/TRANSFER-DEEPSEEK.md) 与 T00–T43 证据。T40 的二十项检查是执行方的核对结果；本复核没有运行该检查脚本，而是另读原生记录、共享 Binding/交接记录和公开结果确认关键事实。分享包、脱敏归档及其 manifest 由 Lead 另行校验，本文件不对尚未复核的包作完整性或脱敏通过声明。

## 配置入口：失败与通过分别保留

用户选型后的原始请求是 `claude-deepseek-v4.1-flash[1m]`、`effort=low`，继续使用原内部 tclaude、既有登录、空 provider 覆盖及 `allowed_tools=[]`。[T00 授权与软件校验](../reports/evidence/T00-authorized-profile.json) 和 [T10 正式配置](../reports/evidence/T10-transfer-authorized-profile.json) 相符。

[T01](../reports/evidence/T01-public-typed-model-rejected.json) 记录真实公开 `agent.configure-sdk` 调用退出 2，报 `Invalid native model identifier`。已安装 `harness_config.sdk_config` 对 model 使用 `[A-Za-z0-9_./:@+-]+`，确实拒绝方括号；校验发生于创建配置/会话之前，不能归因于当时尚未创建实例。它是已复现的便捷入口兼容缺陷，**未修复**。[T02](../reports/evidence/T02-no-query-sdk-handshake.json) 的 connected 只是无 query 握手，不是模型交接通过。

确认拒绝没有副作用后，经授权使用已有公开完整配置接口保存原样 native profile，读回 `configured_kind=claude`，再切回 Codex 准备旧入口；正式 `agent.transfer(target_config)` 原样携带上述模型 ID、low、空 provider 和空工具列表。[恢复边界](../reports/evidence/T03-profile-recovery-boundary.json)、[完整配置保存](../reports/evidence/T17-native-profile-save.json)、[读回](../reports/evidence/T17-native-profile-show.json)、[唯一正式 transfer 请求](../reports/evidence/T22-public-exact-profile-transfer.json) 可互相核对。该路径沿正常 SDK preflight 接入，没有换短模型名、服务或密钥，不是便捷入口修复。

## 原生回报与模型边界

后继真实记录有两次 System init，均回报精确请求 ID；AssistantMessage.model 为 `deepseek/deepseek-flash`，两个 Result 的 model_usage 含请求 ID/canonicalModel。实际 session 均为 `c08cf6ec-8245-4b10-a3d2-aaca6377effe`，两个 Result 均 `is_error=false`、完成。两次 init 不代表两个会话。[T39 原生事实提取](../reports/evidence/T39-deepseek-native-facts.json) 与原始记录的工具块/结果逐项相符；本复核未读取或转录 thinking 正文。

这证明原生包装器回报了请求模型路由，并成功完成平台操作；不独立证明底层权重、`v4.1` 物理版本、`[1m]` 上下文容量或真实收费。low 在请求和配置中保持原值；源码把它传给 SDK options，SDK transport 有 `--effort` 传递路径，但本批没有有效强度的原生回报，也没有实际子进程 argv 的独立记录。因此只确认请求及配置传递，**不确认服务端实际采用 low**。usage 中的 thinking_tokens=0 也不能代替这种确认。

本增量共五次外层执行：旧 Codex boot+handoff 两次，peer Codex boot 一次，tclaude SDK boot+Watch 两次。SDK Result.num_turns 的 10/9 是内部回合计数；SDK 的本地 submission ID 也不能称为原生 Codex turn ID。没有额外模型问答、控制器纠偏输入或未知结果重放。

## 身份、资产与自动交接

| 核对项 | 直接证据及结果 |
| --- | --- |
| 身份与工作根 | 新旧均 transfer-agent，instance branch 均 instance/transfer-agent，公开 directories 相同；保留同一工作根 |
| 旧入口 | Binding `b03737ac951374b90824d9f583824e2f5`；Codex session `01a11a34-91a4-7991-a42e-5a2396ce06e9` |
| 新入口 | Binding `bfdecfd797423449ba36c659de7e3d63e`；claude SDK session `c08cf6ec-8245-4b10-a3d2-aaca6377effe`；Binding/session 均改变 |
| 原本人交接点 | checkpoint `c7caaca4521c94bdf9b1f0186bdae127d`，revision `d5539c7be887d72fd1e960fad5514e196590e6c1` |
| 生命周期顺序 | 旧 Binding 于 14:31:09.251833 +08:00 released；新 Binding 于 14:31:15.435638 +08:00 创建，旧 handoff.consumed_by 指向新 Binding |
| 真实资产连续性 | marker `6ef47b430cc648b2920451ba6fe7416d` 在源资产、Codex 本人记录、后继 relay 与后续消息记录一致；relay 同时包含旧 checkpoint 与新旧 Binding |

[旧身份](../reports/evidence/T21-old-identity-binding.json)、[Codex 资产](../reports/evidence/T20-codex-origin-read.json)、[后继完成观察](../reports/evidence/T24-target-relay-completed.json)、[relay 实际读回](../reports/evidence/T25-tclaude-relay-asset.json)、[新身份](../reports/evidence/T26-new-identity-binding.json) 与共享 Git 的 Binding/handoff/checkpoint 一致。relay revision 为 `2e36bfd009e0f0265bcee118cba344d5a1b70a66dcf06a7cd2176ff7ec174bce`。

读取执行控制脚本和原生输入记录，只有一次 `deepseek-transfer-001` 请求。旧 Codex 本人创建 checkpoint、stop；后继由平台推进启动。没有管理端手动 start 后继或 transfer-continue，也没有管理端代写 relay/消息记录。[控制器边界](../reports/evidence/T23-request-boundary.json) 与 [执行脚本](../executor/run_transfer_deepseek.py) 相符。

`completed` 在首次公开 transfer-status 前已经出现在真实本地 transfer 状态中：T24 对完成状态及实际 session 有观察，boot 的 completed 与初始 checkpoint 同时成立。读取已安装 runtime/transfer 代码也确认它由原生 Result 完成与持久化推进，不依赖首次 status 调用制造成功。后继本人最终停工以后，[T33](../reports/evidence/T33-transfer-final.json) 仍回报同一 transfer 为 `completed`，没有退回 pending。

旧 Binding 写入负向验证确实执行一次，被拒绝为非当前入口；[T27 拒绝](../reports/evidence/T27-old-binding-write-rejected.json) 与 [T28 原操作 not_recorded](../reports/evidence/T28-old-binding-operation-absent.json) 一致，未产生消息副作用。此结果只覆盖本次旧入口写入，没有扩展为全部并发/权限矩阵通过。

## 后续消息、ACK 与本人停工

peer 本人通过平台工具一次发布 `aw-transfer-message-001`，内容含同一随机 marker。后继在相同 SDK session 的第二次 query 收到 normal 消息通知，调用 message.receive；返回发布 ACK，操作 `ack-aw-transfer-message-001` 为 `published`，接收者/Binding 为 transfer-agent/新 Binding。[共享消息](../reports/evidence/T34-message-show.json)、[ACK operation](../reports/evidence/T35-ack-operation.json) 和原生真实工具结果相符。ACK 是收取证明；本次业务完成另由资产、checkpoint 和停工记录支持。

后继本人写入 `notes/tclaude-message.md`，准确保存消息 ID、marker、ACK、新 Binding 和原交接点核对，读回 revision `0b41be7fcfdebeffd719b770472e28ecfbb720dfc5047c405e03c30f7fac547d`。[消息记录](../reports/evidence/T36-message-asset.json)、[relay 末次读回](../reports/evidence/T36-relay-asset.json)、[sender 记录](../reports/evidence/T36-sender-asset.json) 一致；sender 的记录没有冒称收件人已经 ACK。

后继本人 checkpoint `cd0940423d2f74518b059295fd0da29b4`、stop 返回 `awaiting_native_idle`，随后真实第二个 Result 完成，平台才形成 released/最终 handoff。后继 stopped_at 为 14:34:36.877454 +08:00；peer 也由本人 checkpoint/stop 后 released。最后两端均 current=null、runner_alive=false、Watch disabled，[T31 最终观察](../reports/evidence/T31-final-native-observation.json)、[后继 show](../reports/evidence/T32-transfer-agent-show.json)、[peer show](../reports/evidence/T32-transfer-peer-show.json)、[checkpoint 列表](../reports/evidence/T38-checkpoint-list.json)、[T40 共享协议核对](../reports/evidence/T40-independent-protocol-verification.json) 相符。不能把先前 awaiting_native_idle 当成已停止。

[T37 doctor](../reports/evidence/T37-final-doctor.json) 为 healthy、无待 ACK；仅覆盖新 transfer-local。本次未管理端代 checkpoint/stop、清理协议资格或删除锁。执行方 [T41 清理记录](../reports/evidence/T41-process-cleanup-boundary.json) 显示已知本组 Runner PID 均退出、未再观察到关联本组的原生客户端；仍有未证明本组独占的 tclaude/claude 服务，保持不动。复核没有再查询进程，不把此快照扩大成所有共享服务退出或当前全机状态。

## 偏差与未验证边界

- **strict-aw_execute-only 失败。** 后继 boot 实际有四次成功原生 Read，读取本实例 AGENTS、公开旧 checkpoint、codex-origin 和 source。原生 boot 违反本轮禁 Read 要求；即使全部为只读、后续业务效果通过，也不能抹去该偏差。两次 query 合计 13 个平台 aw_execute 和 4 个 Read，没有观察到原生 Shell/Write。空 allowed_tools/default 权限及 permission_denials=[] 不证明严格工具隔离生效。
- 参数错误共六次：旧 Codex 的 agent.show/asset.list 两次，peer 的 agent.show/sender asset.write 两次，SDK boot 的 asset.read/relay asset.write 两次，均误传 binding。真实错误保留，模型在各自原轮自行纠正；无新增控制器纠偏输入。这些错误没有被虚构成成功工具结果。
- 部分原生中文工具输出有乱码，原输出保留；实际 UTF-8 消息/资产及 marker 可核对。没有足够证据判断具体编码故障原因，不据此编造根因或声称修复。
- [T42 软件核对](../reports/evidence/T42-software-audit.json) 记录安装产品 Python 与固定 wheel 相符；本复核另对关键安装源码取 hash。未读取凭据、账号或全局配置。原生 thinking 完整内容不复制到复核文件，也不以此替代分享包的单独脱敏审查。
- [T43 维护状态](../reports/evidence/T43-no-extra-maintenance-authority.json) 为 worker_running=false、schedule=null、grants={}，只证明本次新空间记录的状态；不扩展为全空间授权检查。

本次未验证反向/矩阵交接、busy insert/steer、WorkBuddy、Desktop 控制、外部消息渠道、生产空间或长期运行。该闭环也不构成 E2E-001/E2E-002 已修复或 V1 全量完成的结论。

## 复核快照校验

下列 SHA256 由复核方只读取文件计算，固定这次引用的证据/源码快照；不是重跑验收。运行原始记录仅保留 hash 来追溯，本文件不复制其正文。执行报告中“44 个 JSON”对应 T40 记录的当时解析集合；本次复核快照 T00–T43 共 48 个 JSON，不将后续新增文件混作当时已解析项。

| 相对批次根的文件 | SHA256 |
| --- | --- |
| `reports/evidence/T00-authorized-profile.json` | `0d35ce1f9cd3a187cb68850d2175f63b8568db7897e7010b3d9234b7ff80ffef` |
| `reports/evidence/T01-public-typed-model-rejected.json` | `19ac0f1ad0b541731600c0a8082fe8c485f1404faf81c5af484f054b04d1c528` |
| `reports/evidence/T02-no-query-sdk-handshake.json` | `d754a37efa3d168d22a4f1583d800c86d6141dd990d3d98599285807c1cf3e08` |
| `reports/evidence/T03-profile-recovery-boundary.json` | `ec06c7c67aa6928ee771a42098d123aba1d5063db9cade5e149b5553548e4e6e` |
| `reports/evidence/T10-transfer-authorized-profile.json` | `db43f83ed80c918027cb3f43276a665da48dfcfee1b710eba6fd7324ecbc2316` |
| `reports/evidence/T11-transfer-workspace.json` | `8cc6b6c193275605522583d8d7a60801035696a4ddceb0539e1e349672f3865b` |
| `reports/evidence/T12-transfer-marker.json` | `2040c928bec249eb2dadd41de6763c17f538401ce485ed655c3681ff8c98258f` |
| `reports/evidence/T13-0-create.json` | `b0ee1f2a60a7b245e73138d22c6ffb1cb5cecb346bc8ec6470ee8c6f1f3e3613` |
| `reports/evidence/T13-1-create.json` | `8ba1020f0a4c6bf7a55ff90cc40cb86e30ec253fbb431d3a7bece521272a65e7` |
| `reports/evidence/T14-0-read.json` | `54f382d1dbfc4870c13528cb953fa7151a0cfbceb21c3777fe90fe5130c4306f` |
| `reports/evidence/T14-1-read.json` | `6b44b9827efd5edc1db6ed9baef88e22c8b7afd5118da03d98048a9491f837ab` |
| `reports/evidence/T15-0-task.json` | `3cdccabef583ff60998515247e3f4b0e40c4f841aaa53cff4462790f5c81944d` |
| `reports/evidence/T15-1-task.json` | `d4092dd6ef9d5bca95c55a65542cfeba57dba8a8d919ce8fcf89d0fff91c2927` |
| `reports/evidence/T16-0-source.json` | `c4258c78a03e86024a15098020a6270d8f9fbda429e29fdb009332a123876fa9` |
| `reports/evidence/T16-1-source.json` | `7131282c81c19d160191b4e05454444297963c116bc2405c22098096b05e244d` |
| `reports/evidence/T17-0-codex.json` | `cab66ecbad543bdba17e5363569ad9f683074e9ce361d6ec073883042aa03b42` |
| `reports/evidence/T17-1-codex.json` | `4251d912081d9a0bccff1622b4792207bf2b2b974bf70888d7bd0842a300fa4c` |
| `reports/evidence/T17-native-profile-save.json` | `a030bca40c7a8de56d943faaff6f4ef543e4dcf167466439b38b6ac746fd1114` |
| `reports/evidence/T17-native-profile-show.json` | `3c00270edb60ea6825259a321484388cf95cac1e5f34ab2653745e91fa132715` |
| `reports/evidence/T18-transfer-codex-start.json` | `06e193438c3283360d648ff5e228dfee68c925c1f42a6759e5ee3352654fb029` |
| `reports/evidence/T19-codex-boot-complete.json` | `3c9fd256bf5dfe33efbc79fbe4c81379244457c57604db54ffbd36fd5ec69a87` |
| `reports/evidence/T20-codex-origin-read.json` | `2612ba3f63d40621d63f63ade73249ae550fb7277945cb2732dda41169d41abf` |
| `reports/evidence/T21-old-identity-binding.json` | `f18e342296312685d4875d322b0571691fed78e3fac8b47b41868f086ca4c23a` |
| `reports/evidence/T22-public-exact-profile-transfer.json` | `0277b12bd2a3800fd0eda26b8b63349fca46396c5ba5a627316912e17070eb5d` |
| `reports/evidence/T23-request-boundary.json` | `7b833c74c5b3efa37956d2e22f07bc0073bec64ee5b93b21bfb474fd7ca609af` |
| `reports/evidence/T24-target-relay-completed.json` | `709d03831c27bcc447c0dca45609ab32482dae50fd1c4348cc75336e2a9c82fd` |
| `reports/evidence/T25-tclaude-relay-asset.json` | `4b0d838acb43383e0f2befb120732a2182236f2d0dc700fa9654d03c37dce2f8` |
| `reports/evidence/T26-new-identity-binding.json` | `8bf411da965b390cbcf406dba2c5097e7c75307ecba9d22481a42b3c9a4e5efe` |
| `reports/evidence/T27-old-binding-write-rejected.json` | `ac8ba6393de2a349a44845803e70bb170bd18639d5871a99a60d5cc83be2e914` |
| `reports/evidence/T28-old-binding-operation-absent.json` | `5435380a0874beac36dda5bf45a7e42e86b1611d9b0f41796f237d504e9837c5` |
| `reports/evidence/T29-target-watch-on.json` | `e5a42dc8fdf5851946b1ada8e0fa0f9f626ea47ae09624d331218d6f960cc72d` |
| `reports/evidence/T30-peer-start.json` | `d79daf8472bd1aca2ae943314bf4b9a72c545711821d489a18d0aa240048c42b` |
| `reports/evidence/T31-final-native-observation.json` | `5b3329c1cfa386ff0df902ed01a4bf5f788263897c15020fcaee0948465c568d` |
| `reports/evidence/T32-transfer-agent-show.json` | `ad81baa11f84ea40a0bd542b1ac2a2a7a092d173a31cf329e93bdf7c8cc371e0` |
| `reports/evidence/T32-transfer-peer-show.json` | `a6befd2f7f62f86bdcde49dca5fbc98490c795eb1a6dc5910dba3e29dc9529e5` |
| `reports/evidence/T33-transfer-final.json` | `f0277c2690a48359052d0a4b17aff17f07b72badc3cfd534bc2662a2bcdf0659` |
| `reports/evidence/T34-message-show.json` | `c861a106fc2b3c7b2999d489c526e9a7c2b6b678356f9e890000638b02476151` |
| `reports/evidence/T35-ack-operation.json` | `422c4086921e838a14e69c5f5bd339aa8d5ac772115ed84be379b0071d6e945b` |
| `reports/evidence/T36-message-asset.json` | `39dcd2b22f69b98dfc42f0e121d6ea62f56e1f6ff7ca59ad8bfde60828081a76` |
| `reports/evidence/T36-relay-asset.json` | `d6c9d50d3056fb9875d159838504ff89fedb62ab6797fec9511892e126cc57a1` |
| `reports/evidence/T36-sender-asset.json` | `b2e01e16350fe2c13a77718f8fe640f2a149521474e4a2c334d9b56ff6f97fcf` |
| `reports/evidence/T37-final-doctor.json` | `f55fe383d34c745055058bad32a86371321b00e48b6a6fbc7884d0e2d72c86a9` |
| `reports/evidence/T38-checkpoint-list.json` | `37ef4151e960bbe89089cd972444982869e446a35008084a793bdd55aa270f6e` |
| `reports/evidence/T39-deepseek-native-facts.json` | `7a34a6d82d84ad3a4e43a3c7d88d3bb2330f63a334448f6b14ca8ef8bd15d911` |
| `reports/evidence/T40-independent-protocol-verification.json` | `a6383d0340a972ecb045feff032681d65b2dbfa761d49f7dee87f12479c9e3b7` |
| `reports/evidence/T41-process-cleanup-boundary.json` | `9420d9498adba398291c9ff1d1db3789125ac08cca36c2bbc18a2e95094b9662` |
| `reports/evidence/T42-software-audit.json` | `677382c1ac0ad75832de1b625583ff26f2eee59721bed5f65631973e68160d13` |
| `reports/evidence/T43-no-extra-maintenance-authority.json` | `7e826628237a7dafe53583503d91d25745239d9be8d8cfc47c7d72d8245aeb67` |
| `reports/TRANSFER-DEEPSEEK.md` | `9d3cc7647762f25d84b9461fcaa9d3475ad2a79bfdf30f31b091d5e1b7dd8ad8` |
| `tools/transfer_preflight.py` | `c3d8db4f47f514c6b7cb134c0c47e54436a52abd8c774791ef3d1285c49ba8af` |
| `tools/prepare_transfer_deepseek.py` | `fcd8f8f546b2a8b26b87bebb372388335fec00e79eb498f828b9b75991c83260` |
| `tools/run_transfer_deepseek.py` | `4f3f8733b991e7339b86bc8a59d80d81b8b1d1ae562661bbce8766953d414a2c` |
| `tools/finish_transfer_deepseek.py` | `7ee8d61d93e294cb5d27820954e5acd9b5fb9db9b67e9a3a95f1de0b5b7d6917` |
| `tools/transfer_record.py` | `d10eae034425b0a48afd41b6d735300f2375d578baae2b08425783f0f26b346d` |
| `tools/collect_transfer_native.py` | `2f783e69eaf6b764eb1373cd0d9830d2a39a0d5820e10e44fcf61359a01313b3` |
| `tools/verify_transfer_deepseek.py` | `10473d5c3b0beaa794a0aa487936e07caf01c9b0f70d797257ba6e77c9b3e850` |
| `app/Lib/site-packages/agent_workspace/native_sdk.py` | `c9bb50a64ca1c73debb6e166e028d195686839471e4c82ce75cddbe4284237d1` |
| `app/Lib/site-packages/agent_workspace/runtime.py` | `700e2c7733a4e18d202b8050f54a6956b00fe49a81cd4bd5c949735b6f92b592` |
| `app/Lib/site-packages/agent_workspace/transfer.py` | `1776fa2d4de763f44486dab9012eab3dfe21af62176d3f97a0cb382da0d281a4` |
| `app/Lib/site-packages/agent_workspace/harness_config.py` | `4a4676093572a121540ab06982f8912094e18ee2e31698749ceeb4d309a257cc` |
| `app/Lib/site-packages/agent_workspace/commands.py` | `5461ccf3564338661107f36881fdbcd54a4dd2216d9416faa09662a89b1317ff` |
| `data/home/instances/transfer-local/transfer-agent/records/b03737ac951374b90824d9f583824e2f5/runtime.jsonl` | `59ee5fd5273b79640462200fb4297095c94bc408dacc94aba5f17e2032791b12` |
| `data/home/instances/transfer-local/transfer-agent/records/bfdecfd797423449ba36c659de7e3d63e/runtime.jsonl` | `19370fd9dad359eee40aea24393a6f92b7b62253a4e0645b1ad2da3459e3740a` |
| `data/home/instances/transfer-local/transfer-peer/records/b7d19e1bd46414a4e89dbe69e40c9724c/runtime.jsonl` | `aff2d9de3e8f7ffbf7415eb6cad658bfbb2a79b59f68da23f2b02d3e8228eb25` |
