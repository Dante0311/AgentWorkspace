# AW Web Courier

首批只通过本机 AW 后台，在用户确认后向登记的 ChatGPT 会话发送一条正式 Message 通知。扩展不创建 Message，不保存 ACK，也不自动轮询。原 0.1.0 测试包保留在来源目录，产品中的 0.2.0 扩展使用独立的连接和尝试记录。

## 隔离验收顺序

1. 在隔离的 AW Home 和 Workspace 中准备接收 Agent。它的当前 Binding 必须是 `active` 的 `manual` 类型，已登记 `session` 必须精确对应目标 `https://chatgpt.com/c/<id>` 或同一个会话 ID。启动同一 AW Home 的本机后台，记下监听端口。
2. 由用户在 Chrome 中手动加载 `extensions/web-courier/extension/`，在扩展弹窗中读取实际扩展 ID。浏览器需已登录目标 ChatGPT 会话；不要用会话标题推断目标。
3. 在 AW 的用户管理终端调用 `web-courier.connect`，明确提供 Workspace、Agent、当前 Binding、目标会话 URL、实际扩展 ID、稳定 request ID 和后台端口。把返回的受限连接 JSON 粘贴到扩展弹窗并保存。JSON 含一次连接所用 token，只交扩展，不写入网页、仓库或验收日志。普通 AW 后台管理 token 不用于扩展。
4. 切到该会话，确保已完成上一轮回复，输入框没有草稿或附件。人工点击“获取一条原通知”，检查完整正文，再点击“填入原通知”。核对页面和目标后勾选确认，只点击一次发送。
5. 发送结果不明、worker 重启或返回丢失时，只点“检查页面 / 查询原 ACK”，或用用户管理的 `web-courier.status` 查原连接。不要清除存储、覆盖配置、更换 ID 或重复点击。网页看到消息或刷新后仍看到消息，只是网页观察事实。
6. 真正接收方按 AW Message 协议在当前入口读取原消息并 `message.receive`，由 AW 保存原 ACK。再次检查扩展或 `web-courier.status`，只有读到原 ACK 才报告通知已确认。ACK 仍不代表业务任务完成。

每个连接只取一条消息；`insert` 明确拒绝。扩展不提供多会话调度、自动登录或无人值守发送。旧版 `awSingleTestV1` 存储如果存在，扩展会保留并拒绝覆盖，请使用独立浏览器资料验收新版本。撤销连接用用户管理的 `web-courier.revoke`，不会清除原尝试。

本目录的 Node 测试覆盖配置、worker 和模拟页面；产品 Python 测试覆盖消息领取和隔离 HTTP。真实 Chrome 加载、ChatGPT 页面 DOM 与人工发送、真正接收方的 ACK 需要 E2E 独立记录，测试通过不能替代这些事实。

开发测试：`node --test extensions/web-courier/tests/*.test.mjs`。可加载扩展目录为 `extensions/web-courier/extension/`。
