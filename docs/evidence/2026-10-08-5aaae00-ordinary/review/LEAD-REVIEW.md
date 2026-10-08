# 控制者复核

本记录由本批控制者结合用户截图、原始测试文件、本机启动回执和 OS 进程核对，不冒充第二执行者独立复核。

- [第一轮](../reports/evidence/03-first-native-response.json)的两个字段与实际文件逐项相等；截图显示实际只读工具和返回结果，配置命令与原生 UI 同时支持所选 Luna/low。Codex 的 effort 位于命令中的 `model_reasoning_effort`，早期记录读取 `profile.effort` 得到 null 不是配置丢失证据。
- [第二轮](../reports/evidence/04-second-native-response.json)在包含连续对话的原终端截图中正确复述两字段，未见新增工具；原请求/PID没有变化。原生 session UUID 未另查，不填造 ID。
- [防重核对](../reports/evidence/06-duplicate-request-check.json)确认真实 UI 的只读刷新、继续原请求与整页刷新之后，请求内容字节一致，启动次数没有新增记录，OS匹配原生进程只有原PID；不外推双击竞态或所有故障恢复。
- [最终退出](../reports/evidence/08-native-exit.json)与[进程查询](../reports/evidence/08-native-exit-processes.json)一致：native_exited/0，原生与包装进程无残留。三个测试文件的内容与列表保持；没有 Workspace registry、实例目录或持久 Binding。
- [工作台关闭](../reports/evidence/09-service-exit-audit.json)确认终端 Ctrl+C 后进程、监听端口停止，终端退出码1保留，不能写成0或证明所有清理内部步骤。未强制终止进程。
- TERM兼容提示已留档；另2条瞬时warnings详情未知。二者不混同，不把提示消失当作修复；本轮未登记新的确定产品缺陷。

结论：认可普通会话 C 组所测主要路径的 PASS_REAL，保留上述提示和未测边界。本批产品源文件未修改，旧批次数据未写入。归档校验另由 manifest/SHA256SUMS/verify.py 支持。
