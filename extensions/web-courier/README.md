# AW Web Courier

轻量 Chrome Manifest V3 扩展，用于人工确认后向指定 ChatGPT 会话投递一条网页通知。源码由已提供的 0.1.0 MVP 整理；原包和历史测试记录保持原样，私人会话地址已从本目录移除。

当前提交保存网页动作原型和 Node 回归测试，尚未完成 AW 后台连接或正式 Message/ACK 接入。代码中的全 1 会话编号是测试占位值，不是可用的发送目标。后续实现必须由用户明确配置实际 Workspace、Agent、当前 Binding、会话和受限连接；不能把网页观察当作 AW ACK。

保留单次点击、发送前保存原尝试、未知结果不重发、原标签页核对、已有草稿/附件/忙时停止。第一批不加入自动轮询、多会话队列或登录自动化。

从产品仓根目录运行模拟测试，无需安装 Node 依赖：

```sh
node --test extensions/web-courier/tests/core.test.mjs extensions/web-courier/tests/page.test.mjs extensions/web-courier/tests/worker.test.mjs
```

这些测试使用模拟 DOM、chrome API 和存储；通过不表示真实浏览器已加载、网页发送或 AW 接收成功。真实验收应使用同一确定提交的后台与扩展，在独立测试环境中完成。

正式 Message、执行资格与 ACK 的合同见[产品设计](../../docs/design.md)。来源校验、历史结果及详细验收证据保留在开发仓。
