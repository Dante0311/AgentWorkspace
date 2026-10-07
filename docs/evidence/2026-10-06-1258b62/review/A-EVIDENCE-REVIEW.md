# A 组证据独立复核

日期：2026-10-06（Asia/Shanghai）；复核配置 gpt-6.1-sol / high。
正式根：${E2E_ROOT}。
本次仅有界读取已生成证据、查看截图和重算文件哈希；未安装、启动服务/客户端/模型、运行测试或修改执行方文件。

## 结论

现有证据支持 A 组已经完成的本机安装、页面打开、HTTP 控制边界、同安装请求重跑、受控安装中断及原目录续装、最终服务/端口清理观测。可分别保留 PASS_REAL，安装恢复明确标“真实组件 + 受控故障注入”。本轮抽查未发现安装/UI/HTTP 的新产品缺陷。

不能据此认定 A 整组或全 E2E 通过。第二独立安装复用已创建 Workspace/身份/资料并重启尚未执行，须保留 NOT_RUN。普通会话真实 TTY/第二轮、真实模型、管家初始化、通信/ACK、交接均未由这些证据证明。

首次读取 reports/E2E-REPORT.md 和 reports/CHECKPOINT.md 时仍在收尾，主报告仅“进行中”，检查点仍含运行服务和恢复进行中的历史状态。因此本次没有核对最终主报告是否准确整合以下结论，不把暂未写完判为缺陷；Lead 整合时应以完成后的记录为准。本复核不持续轮询。

## 认可范围及抽查依据

| 范围 | 独立抽查结果 |
| --- | --- |
| 固定来源/构建 | 00-provenance 追到旧根 01-baseline-head、12-source-archive、15-build-wheel：分别退出 0，archive 显式固定 1258b622c474beb73f13234c0f00672d8d5b5bbb，wheel 从归档副本构建。三个原始证据哈希与 provenance 一致。正式根 wheel、source-checkout.zip、install.py 的实算 SHA256 与 SHA256SUMS/provenance 一致。没有搬 venv。 |
| 真实隔离安装 | A01 退出 0，A02/03/06 退出 0。绝对安装器/包/aw 路径，cwd 在源码外；A06 显示模块来自正式 app/Lib/site-packages，direct_url 指向同一 wheel 且哈希相符，支持非 editable 安装。 |
| 随包资源/同请求重复 | A13 退出 0，无重新 pip 安装输出；A14 保存安装标记未变，并核对七个 Skill、三个内置定义和资源与源码副本一致。读取检查脚本确认实际逐文件比较；独立重算安装后 message Skill/capabilities 哈希与 A14 一致。 |
| 真实页面可见 | 已直接查看 A09-setup.jpg 和 A10-sessions.jpg：首次配置与普通会话页面实际可见，发现/待确认/当前限制、HTTP 明文确认等说明显示；截图无浏览器地址栏、未见 Token 或实际密钥，MY_MODEL_API_KEY 是变量名占位符。四页 DOM A09–A12 分别记录 setup、sessions、capabilities、root；空 Workspace 的 root 展示首次配置，不将其称为已配置后的 Agent 工作台。支持页面打开，不能扩展为所有表单/按钮交互已验收。 |
| HTTP 控制边界 | A08 实际无 Token 的 state/commands/execute 为 401，错误 Token 为 401，有效授权跨来源为 403，本机有授权 state 为 200。静态页面无授权 200，与控制接口区分。A07 服务使用绝对 aw、独立 --home、源码外 cwd、回环 127.0.0.1:59076；URL 脱敏未持久化真实 Token。 |
| 真实中断/续装 | A15a 是实际安装进程 PID 220788，在 installing 标记与 pyvenv.cfg 已生成后终止其已拥有进程树，退出 1 为故障注入预期，非 Mock。A15b 同解释器/wheel/选装项/原目录续装退出 0，A15c 版本检查退出 0；现存恢复标记为 installed，保留 sentinel 的实算哈希与 A15d 相同，支持原目录续装且未清空现场。故障发生在 venv 创建早期，不泛化为所有安装阶段中断恢复。 |
| 停止/最后观测 | A16 state=stopped，实际 stop_method=owned_process_tree_termination，退出 1。A17 在 00:29:48 的记录中 Processes/Listeners 均为空，源码仍为基线，仅用户规程未跟踪；支持本次清理检查范围的“已停止/无监听”。未在本轮重新执行进程/端口检查，不声称无限期保持停止。 |
| 未建测试身份/未调模型的范围 | A08 state 显示 workspaces/agents 为空；A18 绝对 aw/测试 --home 的 workspace list 退出 0 且空；A22 仅 installation/worker 锁、无 registry/ordinary requests。command-index 没有原生模型启动命令，测试记录称 model_gate CLOSED 和请求数 0；这支持本组仅安装/扫描/页面/HTTP 检查、未安排测试模型请求，不是全机网络审计。A19 pip check 退出 0。 |

wheel SHA256：0ec257b1ffc14ede077f023415fa52f013f2a83ed04042d31be1baa9eeafb048。
源码归档 SHA256：890ebe8030622dfa15f640c1b0f69682c7759bf337476ae9694051a70d3c52bc。

## 需要保留的纠正与边界

1. 服务停止不可写成“正常关闭流程已验证”：检查脚本先尝试 CTRL_BREAK_EVENT，实际记录采用已拥有进程树终止。可以认可清理结果，正常退出路径尚未取得证据；这不是本轮已确认产品失败。
2. 第二安装复用已创建数据/身份的重启验收仍 NOT_RUN，当前 empty home 页面/最终空 Workspace 不构成该项。A 整组不得一括标通过。
3. 第一轮静态发现 docs/first-use.md:55 的 HTTP 仅回环旧文字仍是文档矛盾，单独保留；A09 截图已显示正确的逐配置 HTTP 确认，不能把文档问题混记为本轮 HTTP 控制接口失败。实际模型服务/HTTP 模型配置属于后续授权范围。

无需因上述口径问题重跑已完成安装或 UI。主报告完成后由 Lead 采用正确范围和状态；如需复核最终文字，再明确派发。结束本轮，不陪跑或轮询。
