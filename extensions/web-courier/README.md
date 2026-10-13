# AW Web Courier

0.2.0 开发候选：人工确认向明确登记的 ChatGPT 会话投递一条原 AW Message 通知。来源 MVP 已脱敏复制，原目录不参与产品运行。

扩展只请求用户配置的 `127.0.0.1` AW 后台。受限连接登记 Workspace、Agent、当前 Binding、目标会话和扩展 ID；后台管理 token 不进入扩展，受限 token 不进入页面脚本。完整通知原样填入，网页动作与真实 AW ACK 分开显示。

在 AW 创建受限连接后，粘贴返回的连接 JSON。切到登记的会话，人工点击获取、准备、确认发送；随后手动查询原记录。只处理一条 Message，不轮询、不调度；insert 明确拒绝。发送前保存原尝试，worker 重启、返回丢失或页面状态不明时不再次点击。旧 MVP 的存储记录保留，存在旧记录时需要独立浏览器资料验收。

当前后台受限接口还在接入，尚不能把本目录当作已完成的用户安装包。Node 测试覆盖配置、受限请求和模拟 DOM；这些结果不证明真实 Chrome 加载、后台跨域连接或 ChatGPT 页面投递已通过。正式候选和步骤随后台同一确定提交交付。

运行模拟测试：`node --test extensions/web-courier/tests/*.test.mjs`。可加载扩展目录为 `extensions/web-courier/extension/`。
