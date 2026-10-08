# 无纠偏 normal Watch 实测

基线 5aaae00520374b022e0c38fa21f312f8e08629ba；隔离新安装、新 AW_HOME、新 Workspace watch-local。官方 Codex 当前本机可执行文件已重新发现并校验，gpt-6-luna/low，既有登录有效；没有修改全局配置。

限定闭环通过：发送者自身发送 aw-watch-001/002（normal，第二条引用第一条）；接收者在同一原生会话分别 receive、ACK、按实际 revision 保存 A/B 及同一随机标识；两端自身 checkpoint/stop，最终 released、runner_alive=false、Watch disabled。实际发送者 started/completed 1/1，接收者 3/3，共4轮；控制器没有通信开始后的纠偏输入、代 receive/ACK 或代结果记录。

初始化遵循有偏差：接收者首次 boot 提前尝试 receive 尚未存在的 aw-watch-001，平台拒绝，不产生 ACK 或资产副作用；模型结束该轮，后续真实通知正常完成。不能声称首次 boot 完全遵循“只读并结束”的任务要求。原错误保留，未重跑求绿。

发送者笔记另有抄录偏差：notes/watch-sender.md把第二条payload.from.agent写成watch-beta；原生真实发送回执、operation和共享消息均为watch-alpha，实际发送/路由未受影响。[原笔记回读](evidence/96-watch-sender-note-readback.json)与[真实消息2](evidence/16-aw-watch-002-show.json)分别保留，以平台原始记录为准；未修改模型资产或重跑。本轮不能声称模型笔记完整准确复制返回值。

证据：[首轮](evidence/11-receiver-boot-complete.json)、[最终原生观察](evidence/14-watch-final-observation.json)、[发送者](evidence/15-watch-alpha-show.json)、[接收者](evidence/15-watch-beta-show.json)、[消息1](evidence/16-aw-watch-001-show.json)、[消息2](evidence/16-aw-watch-002-show.json)、[实际顺序资产](evidence/17-order-asset.json)、[健康观察](evidence/18-watch-health.json)。最终原生记录及工具结果随脱敏包归档。

不代表 Desktop、多事务插入、企微或跨 Harness 结果。未修改产品源码或主仓。
