# T/G 正常旅程最终复核

2026-10-07（Asia/Shanghai），gpt-6.1-sol / high。正式根 ${E2E_ROOT}；产品 HEAD 核对仍为 1258b622c474beb73f13234c0f00672d8d5b5bbb。

## 结论

认可 T 的真实内部 Watch 有序通知与 Fork 实际会话，以及 G 的管家受限 grant/deny/revoke、正常 sync-idle 和本人停工链路。没有发现需要新增登记的产品缺陷。既有 E2E-001 输入账本问题、E2E-004 transfer 终态问题仍保留，不能把本次正常旅程通过解释为这些问题已修复。

T 严格“只用 aw_execute”的测试指令没有完全遵守：beta boot 有一次原生只读 Shell 读取材料，已单列；其消息、ACK、检查点及停工副作用仍来自真实 aw_execute。G 是没有新远端变化的正常空闲同步，不证明故障恢复或 Workspace healthy。目标新增笔记仅保存本机，不能称 Fork 已为它保存检查点。

## T：Watch、顺序和 Fork 的真实证据

核对 T15-final-facts-with-native-trigger.json、T14-native-watch-trigger-and-busy-proof.json、T11-final-snapshot.json、T11-process-exit-audit.json，并直接扫描两个 Binding 的 records/<binding>/runtime.jsonl、读取共享 Git 消息/ACK 和最终资产。

- **真实新 Fork 会话与发送。** e2e-q-fork Binding bf000d594021742cea71d260e2399277f、native session 01a1121b-af94-7e13-9035-fbdaf72ded67，原生 turn 01a1121b-cb0b-7442-b170-2e2b85301d76。模型实际读回自己的 .aw/identity.json 和来源说明 notes/q-fork-verification.md，身份为 e2e-q-fork；来源为 beta 的 c3788071b0e70473aa054a218b12688eb。它在自身 aw_execute 顺序发送 r-watch-normal-001、r-watch-normal-002，均返回 published；第二条 message_refs 引用第一条。共享 Git main 中两条消息和对应 ACK 与原生返回一致。Fork 的先前创建/管理核对仍归管理端，不倒写成模型创建；本次验证的是新身份真实执行会话及通信。
- **Watch 自动触发。** beta Binding bfe56718746f34061bcf4334d686d159a、session 01a1121a-7b6d-7f70-aa94-d40cd3afbe8e。T14 保存两个原生 userMessage 通知，分别带真实消息 ID，进入 turn 01a1121d-2d4b-74d3-adba-e65e721a87ca 和 01a1121d-8e97-7322-ba91-1a8be0038f27。原始输入账本只有 boot；通知不是控制者 agent.input 伪装。源码 messages.py:199-245 的 Messages.poll 在 normal/busy 时返回 waiting_idle，空闲时直接 adapter.notify，与观测相符。
- **自然 busy 与同 session 顺序。** 第二条 r-watch-normal-002 在 00:47:58.099、00:48:01.103、00:48:04.106（+08）已被观察为 waiting_idle；第一条通知轮直到 00:48:04.268 才完成，第二轮在 00:48:09.384 开始。三次等待早于第一轮结束，随后第二轮开始，均为同 session；不是事后只凭一条最终状态推断自然 busy。
- **本人 receive/ACK 和资产承接。** 两个通知轮分别真实 aw_execute message.receive；两 ACK 的 publication.state=published，receiver 为 beta，Binding 匹配。第二轮实际 asset.read 第一轮记录，再以真实 revision 更新 notes/t-watch-order.md，包含 A/B 两段、两消息 ID 和引用顺序。本复核直接读取该资产，SHA256=4e4d21bfa748a956a58246686785aec351e711ddb5c6df26875d22cdf4291f35，与原生返回相符。没有管理端代 receive/ACK 的证据。
- **本人检查点和最终释放。** Fork 模型保存 cc2e9fab3e2a1422cb3c6c9c084e8c93e（revision 0f8c6a54a861563a41ef982bc78d62d26d17ca63）并 agent.stop；beta 模型保存 c7c9aa716dfb045c9beabb5f40c5e0db0（revision ede83b0d747379d97863c41df5af3ab7fc878d80）并 agent.stop。两次 stop 返回 awaiting_native_idle，此时仅为待观测；后续最终 show 的 current/binding=null、runtime=released、runner_alive=false，加上 T11 39 条进程审计 alive_count=0，才支持正常释放退出。
- **测试指令偏差。** beta boot turn 01a1121a-9d00-7043-a3bb-e46fc5ac00ad 有一次原生 commandExecution，读取 capabilities、AGENTS、旧检查点和 p-final，exitCode=0；不是 aw_execute。严格指令遵守结果为 false。该只读偏差不应隐藏，也不能把真实模型平台工具副作用误记为控制者伪造。

直接扫描原始 runtime：beta 三轮 started/completed=3/3，Fork 一轮=1/1，合计 T 4/4。T 没有增加企微发送或生产调用；旧 beta transfer 与 alpha 保持原有记录。

## G：真实受限授权、撤权和正常同步

核对 G06-phase1-denial-proof.json、G06-scoped-grant.json/grant-readback、G11-phase2-authorized-proof.json/revocation-readback、G13-revoked-denial-and-note-proof.json、G15-final-snapshot.json、G16-process-exit-confirmed.json、G17 最终 show/角色/笔记读回及已保存的 G18-final-facts.json；直接扫描 maintainer 原始 runtime，并比较 G01/G11 目标资产清单与本机文件。

- **主体和权限拒绝真实。** maintainer Binding b03a2ce413aa24da7bb85ab6247d8930e，session 01a11225-0f4b-7423-93b7-ae3107f47105。第一轮 01a11225-3009-75f0-b370-661f3cfb75e2，模型本人通过 dynamicToolCall/aw_execute 对 e2e-q-fork 的 notes/g-maintenance-scope.md 尝试 asset.write，success=false，返回明确 caretaker grant 要求，目标笔记不存在。是受限执行入口权限拒绝，不是管理 CLI 制造的拒绝，也不是错误参数签名导致失败。
- **grant 范围准确。** 中间管理端正式授权仅 commands=[asset.write, maintenance.repair]、targets=[e2e-q-fork]；G06 读回一致。管理端负责授权/撤权，模型负责受限业务动作；不混称模型自行 grant，也不由名称“maintainer”推断任意权限。
- **同步与同 ID 读回。** 第二轮 01a11229-048d-7203-af29-eeb8a0e8f5a0，两次真实 aw_execute maintenance.repair 使用相同 g-sync-idle-fork-001、目标和 action=sync-idle。首次 state=applied，result.revision 为 Fork 的 0f8c6a54a861563a41ef982bc78d62d26d17ca63；两次 created_at/result/verification 一致，只有一份保存请求。maintenance.py:164-173 在相同请求已有回执时直接读回，209-223 不在已取得 degraded verification 时重做效果，因此支持同 ID 不重复同步动作。这里没有新远端变化，不能用回执 applied 声称修复了某个异常。
- **保留 degraded。** verification.state=degraded，具体 issue 是 beta 的 p-beta-normal-transfer-001 仍 starting；这是既有 E2E-004，目标闲置同步成功不意味着全 Workspace healthy。未修旧 transfer、alpha 或未知状态。
- **仅新增本机笔记，撤权后无覆盖。** 模型授权期间创建目标笔记并 asset.read 核对；G01/G11 清单比较：74 个既有资产无修改/删除，只增加 notes/g-maintenance-scope.md，变为 75 个。随后正式撤权读回 commands=[]、targets=[]。第三轮 01a1122c-c753-7ed3-9d13-e085bce9d34f 用真实回读 revision 再尝试一次替换，aw_execute 仍以 caretaker grant 原因拒绝。直接读取最终文件，SHA256=0dd0390cf8293c2a337b718217b1690aac44453d5bbb2d882068adafe6d36a5f，与授权时 hash 相同。请求有效、revision 正确，拒绝不能解释成版本冲突。目标 Git 检查点 0f8c6a54… 不含该新增路径；笔记 saved=local，不能称目标已 checkpoint/published。
- **模型本人停工和角色保留。** maintainer 模型在第三轮保存 c6267872ca59048a2ae88d100f9c8faa6（revision 357d69abde5000badb426a05e6bfb4f2b1f6296d），agent.stop 引用它返回 awaiting_native_idle。G17 最终 show 才确认 current/binding=null、runtime=released、runner_alive=false；G16 审计 19 条、alive_count=0。没有管理端代 checkpoint/stop。Workspace caretaker 三角色读回保留 steward/sentinel/maintainer；身份、定义和目标元数据未被维护操作替换。原始 G runtime 无 commandExecution，业务调用均为 aw_execute。

直接扫描 G 原始 runtime，三轮 started/completed=3/3。最后输入 g-maintainer-phase3-revoked-stop-001 仍 submitted，虽原生完成及停工副作用已成立；这是 E2E-001 的既有表现，不自动重放、不伪造账本 completed。

## 边界与收口

本次独立确认新增 T4+G3 共七个原生完成轮次；G18 的累计 Codex 24 与既有累计17+本次7相符，未为复核重扫所有历史批次。T/G 新增企微均为0，已记录累计仍3/20；原生 turn 不等于精确模型API次数或账单。

只读取 T/G 证据及必要关联事实，只写本报告；未写 review/CHECKPOINT.md、canonical reports、主仓或平台数据，未调用模型/渠道、启动或检查执行者浏览器/服务、修产品、改变旧 transfer/alpha 或未知状态。H 桌面项目引用 UI 与 A 服务重启不属于本次复核，未观察，不能纳入通过结论。T 不证明所有投递模式、故障矩阵或长期 Watch；G 不证明远端变化同步、故障恢复、OS 隔离、周期巡检、生产业务或所有管家能力。没有新增实际缺陷需要登记；本轮完成后停止，不自动继续。
