# Codex → tclaude / DeepSeek真实交接增量

限定闭环通过。固定产品wheel仍来自5aaae00520374b022e0c38fa21f312f8e08629ba，SHA256 e9bcff1a015358643bafbc800d1beb7453dd36cbb8bd1c34a10e68d68ca309f7；复用隔离安装，新建transfer-local/transfer-agent/transfer-peer，没有重启旧Watch或管家实例。此前r3“tclaude query=0、待选型”的报告是当时事实，保持不变；本增量在用户选择DeepSeek后执行，不覆盖旧失败或结论。

用户选型由Lead转达精确目录ID claude-deepseek-v4.1-flash[1m]，effort=low；使用已核验同包装器native tclaude0.1.8/b7d3493、upstreamClaude Code2.1.251、claude-agent-sdk0.2.163及既有内部登录。没有换官方Claude、endpoint、密钥、全局配置或产品源码。[请求与exe/wheel校验](evidence/T00-authorized-profile.json)。

便捷入口兼容问题仍成立：[真实公开agent.configure-sdk拒绝](evidence/T01-public-typed-model-rejected.json)在任何实例/配置/模型副作用前发生，模型ID正则不接受方括号。[无query SDK握手](evidence/T02-no-query-sdk-handshake.json)connected。确认原操作未执行后，经公开agent.configure(value)保存原样native profile并读回configured_kind=claude，再切回原Codex配置开始；正式agent.transfer(target_config)同样原样携带目录ID、low、空provider和原有空allowed_tools，沿正常preflight/sdk_options接入。[边界](evidence/T03-profile-recovery-boundary.json)、[完整配置保存](evidence/T17-native-profile-save.json)、[配置读回](evidence/T17-native-profile-show.json)、[一次正式请求](evidence/T22-public-exact-profile-transfer.json)。这条成功路径不关闭便捷入口的兼容问题，不是改变模型/服务的fallback或修产品。

| 核对项 | 实际事实 |
| --- | --- |
| 同一身份/工作根 | transfer-agent，新旧公开show的directories完全相同 |
| 旧Codex入口 | Binding b03737ac951374b90824d9f583824e2f5；session 01a11a34-91a4-7991-a42e-5a2396ce06e9 |
| 后继tclaude入口 | Binding bfdecfd797423449ba36c659de7e3d63e；session c08cf6ec-8245-4b10-a3d2-aaca6377effe，原生实际回报后绑定 |
| 旧模型本人交接检查点 | c7caaca4521c94bdf9b1f0186bdae127d，原模型checkpoint/stop后平台自动启动后继；无控制器手动start后继 |
| 随机资产 | 6ef47b430cc648b2920451ba6fe7416d在source、旧Codex资产、relay资产、真实消息和后继记录一致 |
| 原生模型回报 | 两次System init均claude-deepseek-v4.1-flash[1m]；Assistant model为deepseek/deepseek-flash；两次Result model_usage均含请求ID |
| 实际后续消息 | peer本人发送aw-transfer-message-001；后继本人receive/ACK，ack-aw-transfer-message-001 published |
| 后继本人停工点 | cd0940423d2f74518b059295fd0da29b4；handoff hfdecfd797423449ba36c659de7e3d63e；最终current=null/released |
| transfer持久终态 | deepseek-transfer-001 completed，最终公开读取仍completed；不是口头自报 |

[旧身份与Binding](evidence/T21-old-identity-binding.json)、[完成relay的原始观察](evidence/T24-target-relay-completed.json)、[真实relay资产](evidence/T25-tclaude-relay-asset.json)、[新Binding](evidence/T26-new-identity-binding.json)、[最终transfer](evidence/T33-transfer-final.json)、[消息和ACK](evidence/T34-message-show.json)、[ACK操作](evidence/T35-ack-operation.json)、[准确记录](evidence/T36-message-asset.json)、[原生模型/工具/结果事实](evidence/T39-deepseek-native-facts.json)、[独立共享协议核对](evidence/T40-independent-protocol-verification.json)。旧Binding写入实际被拒绝，[错误](evidence/T27-old-binding-write-rejected.json)和[原操作not_recorded](evidence/T28-old-binding-operation-absent.json)保留，未产生副作用。

模型与强度边界：以上只证明包装器回报的模型路由和成功平台副作用，不是独立验证底层权重。low只证明已在配置/SDK选项传递；没有原生effective-effort回报，不声称强度实际生效。没有独立模型问答探针；实际增量Codex平台轮次3（原实例boot+handoff2、peer1），tclaude query2/Result成功2（后继boot、Watch通知各1）。Result.num_turns是SDK内部回合字段，不当作平台query数。先前9个Codex轮次保持历史，本增量不重算或重跑它们。

限制偏差保留：后继boot有4次成功原生Read，读取本实例AGENTS、公开检查点、codex-origin及source资产，违反“仅aw_execute、禁Read”的本轮任务要求；strict-aw_execute-only不通过。空allowed_tools及原default权限保持原样，未为验收扩权；默认只读工具获执行不是本轮硬限制已实现的证明。asset.read/asset.write两次误传binding，真实MCP error -32603/Invalid arguments记录；同一query内模型自行改正，控制器没有纠偏输入、重放或制造新轮。实际写入、receive/ACK、checkpoint/stop经平台工具完成。部分中文工具输出出现乱码，原输出保留，不据此编造原因或改源码。原生thinking内容仅本机保留、分享不含thinking_tokens或reasoning正文。

独立核对20项事实全部通过，44个T*证据JSON及其中JSON stdout/stderr已解析验证。[最终两端观察](evidence/T31-final-native-observation.json)、[agent最终show](evidence/T32-transfer-agent-show.json)、[peer最终show](evidence/T32-transfer-peer-show.json)、[最终doctor](evidence/T37-final-doctor.json)healthy。后继及peer均本人cp/stop、released/runner_alive=false、Watch关闭，旧Binding也released；未管理端代cp/stop、强制清资格或删锁。[清理边界](evidence/T41-process-cleanup-boundary.json)：已知本组Runner/启动PID均退出、ROOT关联原生客户端不再观察到；全局tclaude/claude仍有归属未证独占的服务，未停止、不宣称全局服务退出。本组没有开启maintenance schedule或新增grant，旧组清理状态保持不变。

没有全测试、矩阵/反向交接、WorkBuddy、Desktop、外部聊天渠道或生产操作。主仓修改/提交由Lead负责，本执行方未改主仓/源码或push。增量分享包独立deepseek-transfer目录，原文件保留在本轮根；任务文件为AGENTS.snapshot.md，只供审查。manifest.json逐项源SHA/归档SHA及处理规则、SHA256SUMS和EXCLUSIONS说明排除凭据/账号/私密路径、完整聊天/catalog、reasoning、缓存/锁/完整可运行状态。
