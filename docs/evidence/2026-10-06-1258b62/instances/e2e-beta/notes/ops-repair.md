# W批 SBP Ops 模拟输入修复

- 授权实际来源：外部渠道 `wecom`，发送者 `T54690021A`，回复目标 `[TEST_CHANNEL_OR_USER]`。
- 收到的明确授权文本：`@E2E_TEST_BOT 同意修复模拟tile-B`。该授权仅用于本次模拟 tile-B 输入修复。
- 操作：新建 `scenario/sbp-ops/inputs/tile-B.txt`，未修改其他文件。
- 规定内容：`fictional navigation tile B\n`（末尾一个实际换行）。写入 revision `ac214a47e234a405ae08f71485abecbcd155b14d9e01470c248a385ca699714b`；随后 `asset.read` 读回一致，revision 相同。
- 当前结果仅证明虚构输入已写入本地；尚未声称观察器重跑或构建恢复。等待模拟观察器的真实恢复事件，不手动重跑，不发送消息，不停止实例。
