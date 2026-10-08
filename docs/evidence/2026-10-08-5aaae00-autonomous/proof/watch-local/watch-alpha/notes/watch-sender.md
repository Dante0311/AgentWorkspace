# Watch normal 发送结果

- 本次 binding：`b1a328acff2754abcae00512d2036f112`（入口注入，`agent.show` 当前 binding 一致）。
- source 随机标识：`f8e45861ceb449bc9b10f00cef198b90`。

## 第 1 条

请求：`message.send`，`request_id=aw-watch-001`，目标 `watch-beta`，normal，内容：`A — f8e45861ceb449bc9b10f00cef198b90`。

实际返回：

```json
{"id":"aw-watch-001","type":"message","workspace":"watch-local","payload":{"id":"aw-watch-001","from":{"workspace":"workspace:setup3518d9d3a00040f0bfc35a352ab28fa5","agent":"watch-alpha"},"to":{"workspace":"workspace:setup3518d9d3a00040f0bfc35a352ab28fa5","agent":"watch-beta"},"created_at":"2026-10-08T04:55:26.199543+00:00","message_refs":[],"delivery":"normal","content":"A — f8e45861ceb449bc9b10f00cef198b90"},"destinations":["<E2E_ROOT>\\data\\watch.git"],"completed":["<E2E_ROOT>\\data\\watch.git"],"sender":"watch-alpha","binding":"b1a328acff2754abcae00512d2036f112","state":"published"}
```

## 第 2 条

请求：`message.send`，`request_id=aw-watch-002`，目标 `watch-beta`，normal，内容：`B — f8e45861ceb449bc9b10f00cef198b90`，`message_refs=[aw-watch-001]`。

实际返回：

```json
{"id":"aw-watch-002","type":"message","workspace":"watch-local","payload":{"id":"aw-watch-002","from":{"workspace":"workspace:setup3518d9d3a00040f0bfc35a352ab28fa5","agent":"watch-beta"},"to":{"workspace":"workspace:setup3518d9d3a00040f0bfc35a352ab28fa5","agent":"watch-beta"},"created_at":"2026-10-08T04:55:32.260037+00:00","message_refs":["aw-watch-001"],"delivery":"normal","content":"B — f8e45861ceb449bc9b10f00cef198b90"},"destinations":["<E2E_ROOT>\\data\\watch.git"],"completed":["<E2E_ROOT>\\data\\watch.git"],"sender":"watch-alpha","binding":"b1a328acff2754abcae00512d2036f112","state":"published"}
```

未读取接收方消息或代 ACK；未等待 ACK，未重试发送。
