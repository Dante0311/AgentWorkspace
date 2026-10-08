# 修复版定向验收只读预审

2026-10-07（Asia/Shanghai）。基线 5aaae00520374b022e0c38fa21f312f8e08629ba（PR #11）。本次读当前 AGENTS.md、docs/e2e-repair-acceptance.md、相对第一父提交的三个生产文件改动、相关新测试、必要调用链和新批次已保存安装证据。未运行测试、模型、Runner、浏览器或服务，未读取/修改旧批次现场。

## 结论

未发现阻止本轮已授权定向验收的实质遗漏或新增确定缺陷。修复静态上保持唯一执行入口、显式 stop、真实完成事件关联和未知结果不重放规则；新回归覆盖原问题与必要相邻边界。可以按既定范围取得实机证据；本结论不是官方账号模型、Windows 启动、WorkBuddy 认证或真实接手已经通过。

## 修复与合同核对

- **E2E-001：停工时收口输入。** runtime.py:439-449 保留显式 stopping 和原生 idle 前提，先关闭真实 Adapter，再处理已收到的完成事件，保存 transfer 终态，最后 finish_stop 释放资格。_complete_inputs（550-577）只按同 Binding 的 submitted 输入和匹配 turn ID 更新状态；completed 事件才判成功，其他终态判失败，无对应完成事实则保留 submitted，不从 idle/released 推断业务完成。boot 自己 stop 时复用该 stop 的显式检查点，不在关闭后自动生成另一份初始化检查点。关闭未确认仍阻止资格释放，runtime.stop 仍只是停止监视，不强制释放。没有新增业务重放路径。
- **E2E-004：后继自动持久完成。** 正常循环与停止分支都调用 persist_completion。transfer.py:117-152 同时要求真实 session、匹配目标 Binding 的 boot.state=completed、checkpoint_revision；不会凭 session 或检查点单项判通过。它与 advance 共用 transfer.lock 并在锁内重新核对目标，避免快速后继完成被启动回写 starting 覆盖，也不让旧 Runner 修改后来新请求。写入 completed 后 status/advance 直接返回原终态；request 保留相同 ID/config 的读回，以及新请求开始时归档旧结果。固定 successor、不同 owner 的冲突拒绝和 uncertain launch 不创建替代 session 的约束保留。
- **E2E-002：Windows JS 入口。** native_sdk.py:49-73 只对 Windows 的 .js/.cjs/.mjs 选择 Node；exe 仍使用原 SDK Client。通过公开 transport 注入小型 SubprocessTransport 子类，命令是参数数组 node + 选定 script + 原 SDK 参数，没有 cmd、Shell 拼接或偷偷切换自带 Harness。直接读取新 sdk-app 内固定 SDK 0.3.267 实包：_get_cli_path/_build_args 确为启动钩子，connect 使用 [cli_path, *args]，原 cwd/env/stdio/权限与生命周期仍由 SDK 处理。缺 Node 在 start 预留 Binding、transfer 交出旧端之前失败。两个实现钩子依赖固定 SDK 契约；SDK 升级后的兼容性不能外推。

## 已检查的测试与实机证据要求

test_e2e_terminal_state.py 覆盖匹配/未匹配完成、失败/中断/未确认事件、关闭后晚到事件、关闭失败、boot 自停复用检查点、初始化检查点失败、启动锁回写竞态、终态记录写失败和旧 Runner 不改新目标。test_native_transfer.py 的同 Codex 用例先直接读磁盘 completed，再验证两次交接、同 ID 原结果/归档、后继显式停工和对应原生完成事件；回环模型夹具的通过不等于真实账号通过。test_codebuddy_windows_entry.py 使用固定 SDK 和真实 Node 协议夹具，验证参数/环境、含空格中文符号路径、成功及 /login 结果分离、缺 Node 和 exe 路径；夹具不是实际 WorkBuddy 或有效 HY 认证。本复核未重跑这些测试，也未将文档登记的测试数量当作本次复核结果。

本轮最终复核须分别核对：

1. 两次 transfer 的磁盘 completed 必须先于任何 status/advance 查询；后继停工后终态和 session 保留，新 ID 不被旧记录阻挡，旧 ID 读回不增加原生 session/turn 或业务动作。
2. 停工输入与 boot 自停分支都要有匹配的原生完成事件、输入终态、模型显式检查点、实际关闭/释放与进程退出证据。仅自然语言、自报成功、idle 或 released 不足。未知或失败事实保留，不补发输入制造通过。
3. Windows 实际 WorkBuddy JS 的控制握手/启动、同一入口认证、真实资产接手分项记录。help、SDK import、进程出现或夹具结果均不足。若需要人工 /login，本轮保留认证阻塞，不复制 Desktop 凭据、不换服务、不动旧 HY 资格；不能由 CLI 阻塞推断 Desktop 未登录或上游永久不支持。

这些要求已在验收文件和此次授权范围中体现，无需扩展故障矩阵。文档“在 c1f747b 修复分支应用补丁”的段落属于此前开发接入步骤；当前用户已授权拉取合入的 PR #11，应以本轮 5aaae00 固定源码/wheel为准，不再重复应用补丁或改旧现场。

## 新批次准备材料与边界

已保存 00-source-origin、05-wheel-origin、08-installed-origin、09-native-route 支持：源码来自该提交的 tracked-files archive，未复制旧数据，wheel 与安装位于本轮隔离根，已选官方登录 Codex gpt-6-luna/low、无 base_url override。独立读文件校验，新 app、sdk-app 两套安装的三个生产文件均与主仓基线一致：

| 文件 | SHA256 |
| --- | --- |
| runtime.py | 700e2c7733a4e18d202b8050f54a6956b00fe49a81cd4bd5c949735b6f92b592 |
| transfer.py | 1776fa2d4de763f44486dab9012eab3dfe21af62176d3f97a0cb382da0d281a4 |
| native_sdk.py | c9bb50a64ca1c73debb6e166e028d195686839471e4c82ce75cddbe4284237d1 |

这里只确认准备材料与安装来源，不确认后续实机回归效果；未轮询执行中的测试/报告。主仓未跟踪用户规程保留。本次仅新增 review/PREFLIGHT-REVIEW.md，不修改产品、canonical reports、配置、凭据、旧输入/transfer/locks/资格。后续由 Lead 整合脱敏材料到仓库协作归档；本机预审文件本身不代表仓库归档完成。预审收口，等待明确授权最终证据复核，不自动继续。
