# W批 SBP Ops 恢复初始化

- 当前会话：binding `b0ab72f3040a545a8a82320d01000f82c`，Codex，`agent.show` 返回 active/running。
- 能力说明：已读 `.aw/prompts/capabilities.md`。企业微信文本 Bridge 与有限维修已有实现，但真实 Bot/长期运行仍待实机验收；这不是外发授权或生产验收。
- 历史检查点：`c04877e9d873f4943a96b75ecf1975a61`（revision `862210bae2f9e9b45e83ccb87376864ce15d1ba0`）。其中记录的旧 binding 为 `bf06398581b804f2c9da2134133b8d006`，属于历史，不是当前身份。
- 补齐首轮漏读日志证据：`scenario/sbp-ops/archive/sim-build-1/job.log` 实际可读，内容 `Missing fictional input: tile-B.txt`（revision `f45bb63c97a3bddd7b6c496ee6be2ef8957ef2700b2f0a47ab22d343f23e2bd2`）；同目录 `job_summary.json` 指示模拟构建 `sim-build-1` 的 `navigation_export` / `fictional-tile-export` 失败，错误码 `sim_required_input_missing`，状态 `failed`（revision `e6e64bd820b4a3dfda7a77273e08184db507feb14fb3e2130dd80feebc3fc3c7`）。
- `scenario/sbp-ops/build_operation.json` 与上述摘要一致：operation `sim-operation-1`、状态 `failed`、完成输入 1/2，效果确定（revision `54a574cbae223b03c2bbf726ae6d9c0df51ad6f59a446c5892dfcd16aa48c800`）。`scenario.json` 显示 `simulation=true`，需要 `tile-A.txt` 与 `tile-B.txt`，预设修复内容为 `fictional navigation tile B\n`，范围仅此目录（revision `0d4b7fecafa2d9fc12a6a2f930da1472473ed9401e10f9d0392c4f7f6619a157`）。
- 本轮仅读取并记录；未修改模拟输入/配置或生产文件，未发消息，未停止实例。等待真实 wecom 用户明确同意“修复模拟tile-B”后再按说明只写指定虚构输入；无该入站授权前不执行修复。
