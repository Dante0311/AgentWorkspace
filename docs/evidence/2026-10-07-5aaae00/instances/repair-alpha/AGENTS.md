这是新的隔离normal Watch发送任务，旧boot-stop/交接职责仅为历史。只用aw_execute，不运行Shell、外部渠道、子代理或新后继。
本次boot读取notes/source.md，取得真实随机标识。随后亲自message.send两条normal消息给repair-beta：第一条request_id=repair-watch-001，content包含顺序A与该随机标识；第二条request_id=repair-watch-002，content包含顺序B与同标识，message_refs=[repair-watch-001]。只发送各一次，不查询未知记录后重发。
写notes/watch-sender.md记录两个实际返回消息结果，保存checkpoint.create，arguments明确checkpoint_id=repair-watch-sender-stop，然后使用返回的实际id agent.stop并结束响应。
