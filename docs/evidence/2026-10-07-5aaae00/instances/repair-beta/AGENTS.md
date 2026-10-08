这是明确授权的隔离normal Watch回归，只用aw_execute，不运行Shell、外部渠道、子代理或后继。
首次boot：读取AGENTS.md，简短确认并等待，不自行stop。后续由Watch送入的两条真实normal通知：严格先处理repair-watch-001，再处理repair-watch-002；逐条message.receive形成真实ACK。
第一条：将消息ID和随机标识记入notes/watch-order.md，读取现有revision再追加，保留顺序，随后等待第二条。
第二条：先读取notes/watch-order.md与第一条记录，再追加第二消息ID/引用和随机标识；按真实revision写回。保存checkpoint.create，arguments明确checkpoint_id=repair-watch-receiver-stop，使用返回的实际id agent.stop，结束响应。两条通知是测试任务，不重放任何旧消息。
