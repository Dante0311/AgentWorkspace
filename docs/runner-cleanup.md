# 已退出运行器的 controller 清理

controller 是 Binding 中对运行器的占用记录。运行器退出时删除自己的记录，不代表释放 Agent 的 Binding，也不会关闭原生聊天。清理发布失败后，普通恢复保留 `original_controller_remains`，不自动替换旧占用者。

`runtime.cleanup_controller(app, workspace, agent_id, *, expected_binding, expected_controller, expected_session, expected_revision, cleanup_commit=None, directory=None, worker_id=None)` 只接续这一项清理，由 `maintenance.repair` 按既有用户管理/管家授权调用。它不是新的无权限 CLI，也不启动后台或运行器。

Worker 版本从原 Binding 确定实际 Worker；显式 `worker_id` 不一致会拒绝。清理只读取该 Worker 的 entry、状态、暂停标记与锁，同时比较该 Worker 和 Agent 的版本。共用资料根中另一 Worker 的运行器不会被当成本 Worker 的运行器，维修回执也固定原 Worker，不随默认收件 Worker 改变。

- `expected_binding/controller/session` 使用原入口的真实登记。
- `expected_revision` 使用公开 `workspace.doctor.revision`，或成功 `runtime.desktop-observe` 的 `snapshot_revision`；二者都是共享快照版本。`agent.show.revision` 是 Agent 文件 blob，不能用于此参数。函数在所给快照中解析 Binding 文件版本，不要求使用者读取内部 blob。无关共享文件的更新不使这个前提失效。
- `cleanup_commit` 是原 controller 清理提交的 SHA，用于核对原结果；不是要重新推送的提交。只有后台意外中断、未生成清理提交，且没有已保存的终止失败时，才可省略，条件见下文。
- `directory` 省略时采用 Binding 登记的原资料根；提供时必须匹配。

函数取得原资料根的运行器 OS 锁，并核对后台线程已经退出、本机 entry/status、安装来源、原生 Desktop session 与 cwd。暂停或交出标记保留。省略清理提交时还要求后台确认为已停止；本机状态必须匹配原 Binding，且不能有 `cleanup_errors` 或已记录的 `failed` / `native_stop_unconfirmed`。这些终止失败可能只在 `reason` 中保存唯一的清理失败，列表为空不代表没有原发布需要核对。当前接续仅支持可只读确认的本机 Desktop 入口。

随后读取当前共享快照；已提供清理提交时，必须核对它准确表示该 Binding 的 controller 删除。controller 已不在时返回 `controller_already_cleared`。需要写入且已有原提交时，它必须与当前 main 已分叉，确认旧快进推送不能再生效。若当前 main 仍是原提交的祖先，原推送仍可能完成，抛出 `Uncertain`，不新推送。合法接续从当前版本生成只删除匹配 controller 的新提交，以 Binding 和 Agent 文件版本为条件；不重推旧整笔提交。无原提交的合法中断路径返回 `original_outcome=no_cleanup_commit`，不推断一个不存在的原发布结果。

成功清理返回 `controller_cleared`；安全阻止返回 `cleanup_blocked` 或 `cleanup_paused` 及 `reason_code`。正常结果都包含原 `binding/session/controller/cleanup_commit` 与 `runner_started=false`、`binding_released=false`；成功结果另外包含共享 `revision`，`original_published` 只描述原清理提交是否在观测到的 main 历史中。绑定、controller 或文件版本改变抛 `Conflict`。未知发布交给原维修回执核对，不换 request ID 重发。

清理后另行请求既有 `runtime-recover`。恢复保留原 Binding/session 和已尝试输入，不清除 stop/handoff，不创建聊天。Desktop 恢复先只读确认登记的原生 cwd；聊天位置与 Binding 不符时返回阻止原因，不自动移动聊天或改写执行来源。本产品没有原地修改已有聊天 cwd 的操作，保存项目引用或改变分组也不证明实际 cwd 已改变；保留原聊天的位置修复须先取得原生客户端的实际支持和读回证据，不能承诺可行。若用户选择换入口，应由原入口正常保存、交出，再在明确选择的项目接续；该过程会产生新 Binding，不属于保留原 Binding 的恢复。无法正常交出时，只有用户管理入口可按既有显式 takeover 流程决定下一步。

安装新 CLI 与后台换版是两步。清理动作由发起公开维修的 CLI 执行，可只读查询现有后台而不重启健康运行器；`runtime-recover` 则让正在运行的后台创建观察线程，该线程仍采用该后台已加载的代码。新的读取错误分类、运行循环和后台恢复检查必须在后台换版后才生效，不能以 launcher 已更新代替后台版本证据。后台换版会停止它管理的观察线程；应另行安排并核对健康入口、未决输入和暂停标记，不因本次清理擅自切换全局后台。

这些行为不判断 TLS 底层原因，也不保证自动投递或模型设置已恢复。运行器恢复接受、原生观察、正式消息执行和模型实际报告应分别验证。
