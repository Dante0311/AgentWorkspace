# 保存检查点

使用 checkpoint.create，summary 是截至此刻的累计摘要，content 是阶段事实、决定与不确定性。
CLI：aw -w WORKSPACE checkpoint create AGENT --binding BINDING --summary "累计摘要" --content "阶段记录"
动态工具：{"command":"checkpoint.create","arguments":{"summary":"累计摘要","content":"阶段记录"}}
工具保存实例分支的实际文件版本，返回 ID、revision 与排除范围。`.git`、`.aw-local`、`.local`、secrets、环境文件等按公开排除规则不上传；外部产品仓没有自动备份。
不要把未取得的原生记录说成已保存；如需纳入其他资料，先按使用者选择保存或提供固定引用。snapshot 后无权修改旧检查点，纠正应新增。
检查点不释放控制权。停工交出由 handoff/stop 完成，Fork 只选已经保存并登记的检查点。
