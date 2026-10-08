这是明确授权的隔离 normal Watch 发送测试。只用 aw_execute；禁止 Shell、sleep、轮询、读取 .aw-local、其他渠道、子代理、后继。
本次 boot 读取 AGENTS.md、notes/source.md；亲自发送两条 normal Message 给 watch-beta，各发送一次：第一条 request_id=aw-watch-001，内容包含 A 和 source 中随机标识；第二条 request_id=aw-watch-002，内容包含 B 和相同标识，message_refs=[aw-watch-001]。不要读取接收方或代它 ACK。
asset.write notes/watch-sender.md 保存实际发送返回结果。checkpoint.create 保存本次结果，然后 agent.stop（checkpoint 使用返回真实 id，身份自动注入），简短 final 结束当前轮。不等待 ACK、不重试发送。
