这是明确授权的隔离 normal Watch 测试。只用 aw_execute；禁止 Shell、sleep、轮询、读取 .aw-local、其他渠道、子代理、后继。
首次 boot 读取 AGENTS.md，简短 final 结束当前轮，不 stop，不等待工具或 sleep；让 Runner 后续交付通知。
仅处理两条真实 normal Watch 通知，按消息 aw-watch-001、aw-watch-002 顺序，逐条 message.receive 形成真实 ACK。不要提前接收第二条。
第一条通知：message.receive aw-watch-001；asset.read notes/watch-order.md（不存在时按新文件）；记录 A、真实 message_id、内容中的随机标识。asset.write 使用真实返回 revision，新文件 revision=null。随后立即用简短 final 结束当前轮。禁止等待第二条、sleep、agent.show 轮询。
第二条通知：message.receive aw-watch-002；asset.read notes/watch-order.md，保留 A 并追加 B、真实 message_id、message_refs 与随机标识；使用真实 revision 写回。checkpoint.create 保存真实结果，然后 agent.stop（checkpoint 参数使用返回的真实 id，身份自动注入）；简短 final 结束当前轮。
异常时如实记录并 final，不重试发送、不请求自助新轮。
