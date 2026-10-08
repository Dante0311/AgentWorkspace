这是明确授权的同一实例 Codex→tclaude 真实交接验收。仅用 aw_execute 平台工具；禁止 Shell、原生Read/Write、sleep、轮询、.aw-local、外部渠道、子代理、后继。
读取 AGENTS.md 与 notes/source.md。根据当前入口提示中的 runtime_kind 区分阶段，不能根据名字猜身份：
1. 首次 runtime_kind=codex boot：读取随机标识，写 notes/codex-origin.md 记录实际标识与本入口 Binding，然后立即简短 final 结束轮，不自行stop。仅等待平台明确handoff请求。
2. 明确handoff输入：checkpoint.create 保存本次真实资产，agent.stop 使用实际返回 checkpoint id，简短 final。不要创建后继，平台自动接续。
3. 后继 runtime_kind=claude boot：读取入口提供的真实交接检查点、notes/codex-origin.md 与 notes/source.md；确认相同标识，写 notes/tclaude-relay.md，记录读取的实际检查点ID、旧Codex资产标识与当前新Binding。立即简短 final 结束轮，不stop、不sleep、不提前receive。平台稍后开启Watch并送入消息。
4. 仅收到真实 normal Watch 通知 aw-transfer-message-001：本人 message.receive 形成ACK；读取 notes/tclaude-relay.md 与实际消息，核对同一标识，写 notes/tclaude-message.md，checkpoint.create，agent.stop 用真实返回 checkpoint id，立即简短 final。失败保留实际结果，不重试发送、不自助新增轮或后继。
