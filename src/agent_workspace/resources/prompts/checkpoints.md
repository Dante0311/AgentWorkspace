# 保存检查点

使用 checkpoint.create，summary 是截至此刻的累计摘要，content 是阶段事实、决定与不确定性。
为 handoff 保存时，同时说明自己承担什么职责、正在处理什么任务、实际工作位置、已完成事项、下一步与未决结果。平台从当前登记补充 Workspace、Agent、实例分支、个人资料根、职责入口及实际会话位置；已知字段不要求模型凭记忆手填，未知位置不编造。接手时重新解析本机路径与新 Binding，不把检查点里的旧资格直接恢复。
CLI：aw -w WORKSPACE checkpoint create AGENT --binding BINDING --summary "累计摘要" --content "阶段记录"
动态工具：{"command":"checkpoint.create","arguments":{"summary":"累计摘要","content":"阶段记录"}}
工具保存实例分支的实际文件版本，返回 ID、revision 与排除范围。`.git`、`.agentworkspace/local`、旧 `.aw-local`、`.local`、secrets、环境文件等按公开排除规则不上传；外部产品仓没有自动备份。
资产来自登记的个人资料根，不随共用项目或当前 cwd 改变。支持 worktree 的版本复用公共准备能力；若目录缺失只能取回已保存版本，须说明本轮尚未保存资料的范围，不能据此声称已经完整交接。
不要把未取得的原生记录说成已保存；如需纳入其他资料，先按使用者选择保存或提供固定引用。snapshot 后无权修改旧检查点，纠正应新增。
检查点不释放控制权。停工交出由 handoff/stop 完成，Fork 只选已经保存并登记的检查点。
