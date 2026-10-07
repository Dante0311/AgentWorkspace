# G批三阶段总结

## 第一阶段
- 目标 e2e-q-fork 初始笔记 notes/g-maintenance-scope.md 不存在；目标处于无当前Binding、已交出状态（handoff=hf000d594021742cea71d260e2399277f，runtime=released）。
- 对目标笔记仅尝试一次未授权 asset.write（revision=null），真实结果为“Managing another instance requires an explicit caretaker grant.”，权限拒绝。

## 第二阶段
- 在正式normal授权后，以 agent_id=e2e-q-fork、action=sync-idle、request_id=g-sync-idle-fork-001 调用 maintenance.repair，结果 state=applied，result.revision=0f8c6a54a861563a41ef982bc78d62d26d17ca63。
- verification.state=degraded，issue为 transfer_pending：e2e-beta / p-beta-normal-transfer-001 / starting。该操作是正常空闲同步，不是历史异常恢复，也不代表Workspace全部健康。
- 以相同参数和ID第二次调用，读回相同的applied结果及verification。
- 仅新增目标 notes/g-maintenance-scope.md，正式asset.read核对内容为“G批已授权的隔离维护笔记。sync-idle由maintainer真实受限工具完成；仅记录正常空闲同步，不代表故障恢复或Workspace全部健康。”，revision=0dd0390cf8293c2a337b718217b1690aac44453d5bbb2d882068adafe6d36a5f。

## 第三阶段
- 正式撤销临时grant后，使用上述真实回读revision，对同一目标笔记仅尝试一次替换。真实结果为“Managing another instance requires an explicit caretaker grant.”，权限拒绝；未重试、未换路径或绕过。
- 撤权信息：commands=[]、targets=[]。

## 当前入口
- workspace=e2e-local，agent_id=maintainer，Binding=b03a2ce413aa24da7bb85ab6247d8930e；本记录形成时agent.show显示Binding active、runtime running。
