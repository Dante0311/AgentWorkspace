# DeepSeek交接增量检查点

2026-10-08：用户明确选择DeepSeek，Lead转达精确目录ID claude-deepseek-v4.1-flash[1m]、effort=low；继续既有同包装器tclaude内部登录路线，不改全局配置/endpoint/凭据，不重启已完成Watch/Maintenance实例。既有r3历史与结论保留。

公共 typed agent.configure-sdk 在任何实例/配置/会话副作用前拒绝模型ID中的[1m]。T01记录真实拒绝；T02无模型SDK握手仍connected。公开完整 native profile 的agent.configure(value)/agent.transfer(target_config)可原样表达同一ID，按原生SDK正常选项接入，不是改模型或服务的fallback。T03记录先前操作未执行及恢复编排边界；没有改产品源码。

正在创建新的transfer-local、transfer-agent/transfer-peer，当前仅准备合法公共配置与原Codex入口。后续原Codexboot写随机资产→正式transfer→原模型本人cp/stop→平台自动后继→DeepSeek原生model/session及资产/检查点读回→旧Binding写入拒绝→真实normal Message/ACK→新入口本人cp/stop。各阶段以实际新证据更新，不以此计划当已通过。

阶段实际更新：公开完整配置已保存且读回configured_kind=claude，然后原Codex配置启动并写真实随机资产。正式transfer请求deepseek-transfer-001仅提交一次，旧Binding b03737ac951374b90824d9f583824e2f5本人checkpoint/stop，后继bfdecfd797423449ba36c659de7e3d63e由平台自动启动，真实session c08cf6ec-8245-4b10-a3d2-aaca6377effe，System init model=claude-deepseek-v4.1-flash[1m]。后继第一Result成功、boot已completed带checkpoint_revision，transfer终态completed。实际接续资产notes/tclaude-relay.md包含相同随机标识6ef47b430cc648b2920451ba6fe7416d、旧检查点c7caaca4521c94bdf9b1f0186bdae127d及新旧Binding。T27旧Binding写入拒绝，T28操作not_recorded。真实消息发送方已启动，后继Message/ACK/最终自停仍待实际完成。

偏差保留：后继首轮使用原生Read读取AGENTS/公开检查点/资产，违反本轮仅aw_execute限制；asset.read/asset.write误传binding后工具拒绝，在同一模型轮内自行纠正，未加控制器提示。任务中文在部分原生工具输出出现乱码，原字节与结果保留，不凭乱码推断原因或修产品。实际资产写入经平台工具完成。模型标识仅证明包装器回报路由，不宣称验证底层权重。

最终实际更新：真实peer消息aw-transfer-message-001 published，后继本人receive发布ACK，再准确保存notes/tclaude-message.md（源sender=transfer-peer、时间/内容/marker/ACK与平台记录一致）。后继本人cp cd0940423d2f74518b059295fd0da29b4并stop，peer同样本人cp/stop；最终两端current=null/released/runner_alive=false，Watch关闭，transfer completed持久保留。T40独立20项核对均通过；增量Codex3轮started/completed各3，SDK query/成功Result2个，总增量5轮。

原生路由核对：init请求ID、Assistant deepseek/deepseek-flash、两个Result model_usage包含请求ID。low仅证明传递，不证明effective-effort。4次原生Read和2次非法binding参数错误均保留，strict-aw_execute-only不通过。T41已知本组Runner退出、ROOT关联原生客户端0；未停止归属不明的共享tclaude/Claude服务。

本轮实际已收口，新总报告TRANSFER-DEEPSEEK.md；独立增量包及最后hash/核对结果另见根DEEPSEEK-HANDOFF.md。历史E2E-REPORT.md/CHECKPOINT.md/r3包保持不变。不要再起模型轮、重复消息、交接或扩测；便捷profile方括号兼容问题仍开放，产品修复另行授权。
