# 残余 E2E 问题修复与验证

日期：2026-10-08。产品基线 `71bd0581a0c509c2ddc9daa2b8e545891cedc4b0`，版本仍为 `0.1.0a1`。这是开发侧定向修复，不是用户 Windows／官方账号的复测报告。四项改动分别保存为本地提交，未推送、合并或发布。

## 当前问题登记

| 问题 | 本批实际结果 | 尚未验证的部分 |
| --- | --- | --- |
| `message.reconcile` 跨实例补齐权限 | 隔离真实 Git 中已复现，不再只是静态疑点。直接模型调用必须匹配原回执的 Workspace、实例和 Binding；管家跨实例仍须走获授权的 `maintenance.repair`。 | 未在用户生产实例上进行越权探测；本版仍不是 OS 安全沙箱。 |
| E2E-001 busy insert/steer | 原生回执的 `turn.id` 与 `turnId` 均能匹配真实完成事件；同轮多条输入分别保存终态。失败、未知、未匹配、其他入口不被改判成功。 | 修复后官方 `gpt-6-luna/low` 忙时输入链未运行。 |
| E2E-002 Windows 无扩展名入口 | 无扩展名文件具有明确 Node 首行时，走现有 Node＋SDK transport；原生可执行程序、不符合的文件仍用原路径。缺 Node 仍在新入口／交出之前报错。 | 原始证据没有保存 WorkBuddy 文件首行，尚不能证明它命中识别条件。Windows 内核、同入口认证及真实接手分别待验收，不关闭 E2E-002。 |
| 原生模型 ID 的方括号 | `claude-deepseek-v4.1-flash[1m]` 可原样通过便捷模型配置、普通会话参数及交接配置；仅模型字段允许 `[]`。 | 没有重新调用 DeepSeek；配置传递不等于服务端模型／强度生效。 |
| Windows wheel 清理 WinError 145 | 查阅原始清理堆栈与当前脚本；本批 Linux 同脚本实际隔离安装、重启、Git 和清理通过。 | Windows 失败原因尚未确定，未修清理代码，不能据 Linux 通过关闭。 |

原始问题来自 [Windows 修复后复测](../2026-10-07-5aaae00/README.md)、[自主验收独立复核](../2026-10-08-5aaae00-autonomous/review/FINAL-REVIEW.md)、[DeepSeek 交接](../2026-10-08-5aaae00-deepseek/README.md)及 [Desktop 集成报告](../2026-10-08-codex-desktop-integration/README.md)。以上历史证据不修改。已撤回的 E2E-003 不重新登记；E2E-004 和普通停工已通过的限定结论不回退。

## 具体实现与行为变化

**授权：** 公共 `message.reconcile` 加入已有调用者绑定的命令集合，分发器注入并校验真实调用身份，后端在原回执锁内核对归属。直接调用者不能代另一实例或旧入口补齐；获授权维修继续经 `maintenance.repair` 保留授权、结果和复查记录。用户管理入口及 send/receive 内部补齐保持原流程，没有增加权限框架。

**忙时输入：** 只在已有完成事件匹配处补上顶层 `turnId` 的取值，不修改回执格式，不靠 idle 或 released 推定成功，不改变 stop、检查点、关闭与释放顺序。测试包含同轮 normal＋两条 steer、失败／中断、未匹配和停工收尾；旧运行账本未触碰。

**Node 入口：** 只在 Windows 检查选定文件，既有 `.js/.cjs/.mjs` 支持保留。无扩展名只读取有界首行，接受 `#!/usr/bin/env node`、`#!/usr/bin/node` 或 `#!/usr/local/bin/node`（兼容 CRLF）；不将任意文本、PE 文件、其他解释器或带参数的任意 hashbang 猜成 Node。依然使用固定 CodeBuddy SDK `0.3.267` 的小型 transport 子类，不复制协议、凭据和清理逻辑。未新增依赖、自动安装 Node 或更换服务。

**模型配置：** 沿原校验仅为 model 增加方括号，强度与凭据变量名的校验不放宽。传给原生 CLI／SDK 的模型 ID 不改名、不去掉后缀。非法控制字符、换行和原先禁止的命令语法仍被拒绝。

## 已执行的定向验证

各组独立列出，不与历史通过数、修复前失败或误运行相加。没有执行完整 A–J 或额外付费模型、企微和生产 SBP／UE／CI。

| 组 | 修复前有效回归 | 修复后结果 | 证据 |
| --- | --- | --- | --- |
| 权限与消息／管家相邻回归 | 8 failed / 6 passed | 101 passed | [before](authority-before.txt)、[after](authority-after.txt)、[JUnit](authority-after.xml) |
| steer／停工／Desktop 相邻回归 | 7 failed / 5 passed / 45 deselected | 84 passed | [before](steer-before.txt)、[after](steer-after.txt)、[JUnit](steer-after.xml) |
| SDK／Node 入口与认证响应 | 6 failed / 8 passed | 39 passed | [before](node-before.txt)、[after](node-after.txt)、[JUnit](node-after.xml) |
| 模型配置与 HTTP 边界 | 6 failed / 40 deselected | 117 passed | [before](model-before.txt)、[after](model-after.txt)、[JUnit](model-after.xml) |
| 真实 Codex 原生链 | 未重跑已保存的旧基线链 | 1 passed | [结果](native-chain.txt)、[JUnit](native-chain.xml) |
| 新授权说明随包回归 | 未将文案更新当作原缺陷 | 8 passed | [结果](guidance.txt)、[JUnit](guidance.xml) |
| 隔离 wheel 安装 | 未复现 Windows 清理失败 | Linux PASS | [结果](smoke-linux.txt) |

四项修复均先取得有效的失败回归，再修代码。测试环境为 Python 3.13.5、Node 22.16.0、固定 CodeBuddy 0.3.267／Claude SDK 0.2.163；使用真实临时 bare Git，不访问用户旧数据。

真实 Codex 链只运行 `tests/test_native_transfer.py::test_native_transfer_and_message[codex-codex]`，客户端真实，模型响应来自本地回环协议夹具。覆盖两次自动交接、原资产保留、正常自停、旧请求读回和后继 ACK，不冒充官方登录或忙时真实模型验收。SDK／Node 测试在 Linux 用真实 SDK 与 Node 子进程，只模拟本模块 Windows 入口选择条件；JS 是协议夹具，不是用户 WorkBuddy 安装文件，`/login` 失败仍保存失败，不擅自放行。

wheel 检查实际完成独立安装、失败安装恢复、零 Workspace 普通启动请求、三管家创建、真实 HTTP、巡检落盘、退出、第二安装读取同一数据和临时目录清理。普通启动请求只 prepare，没有启动真实普通模型会话。软件安装的版本、资源与是否执行模型分别核对。

### 测试构造及运行失误（保留，不计为产品新缺陷）

- 首版 steer 替身错误地把 boot 也改成 steer 回执，导致测试提前中断；随后只对 insert 返回顶层 ID，才取得上表有效修复前结果。[草稿失败](steer-fixture-draft.txt)保留。
- Node 新断言在 connect 前读取 `_transport`，固定 SDK 此时把注入项保存在 `_custom_transport`；只修正测试观察位置，未为测试更改生产行为。[原失败](node-test-observation-error.txt)保留。
- 模型测试首次选错不存在的文件名，收集零测试；改用实际 `test_http_model_profiles.py`。[选择错误](model-selector-error.txt)保留，零测试不算通过。

最终文档补充了随包 message Skill 的新授权边界；重新打包后只有该 Skill 与 wheel RECORD 不同，Python 和其他资源与成功冒烟的构建一致。[最终包差异](wheel-payload.json)逐项核对，没有把上一个构建的冒烟说成新包重新执行过。

## Windows 清理失败：仍需定点证据

[原失败堆栈](../2026-10-08-codex-desktop-integration/reports/smoke-final.log)仅表明 `TemporaryDirectory` 删除 `home/git/<cache>` 时 `os.rmdir` 得到 WinError 145（目录非空）。源码的冒烟收尾使用 `process.terminate()` 等待父进程；它不能单独证明所有 Git 子进程均已停止，也不能单独证明残留就是子进程造成。旧报告中的最终进程清理发生在失败后，不能代替失败瞬间的证据。

本批没有修改生产关闭逻辑、忽略清理异常、添加盲目删除重试或递归穿透 reparse point。下一次 Windows 定向运行若再失败，先保留错误目录，记录该目录一级和必要子层实际条目、属性／链接类型、失败前后本次服务及子进程状态；不列举无关私人文件，不扫描整机凭据，不在采证前强删目录。仅这一条安装检查需要复查，不重跑 A–J。

## 交付、复测与后续

- 应用补丁前保留用户未提交／未跟踪文件，在基于真实 `71bd058` 或之后兼容提交的独立 worktree 操作；不把此开发副本整体覆盖到 main。
- 不修改旧 input/transfer，不运行旧 transfer-continue，不删除旧锁，不强制释放 alpha 的 HY 资格；新模型测试仍用全新数据和请求 ID。
- 官方账号复测只做本轮变化：一次忙时 steer 的实际回执／轮次／终态；WorkBuddy 先只读检查选定入口首行，再分开验证启动、认证、接手；括号模型通过便捷入口保存并核对传入原值。模型授权与费用按用户已有授权，不为验证启动兼容切换服务。
- 共同职责共享引用、共享 Skill 安装更新、项目分区自动准备仍为后续独立批次，本批没有实现。V2 独立 Agent 不混入修复。

[CHECKPOINT.md](CHECKPOINT.md)给出恢复位置与命令；[manifest.json](manifest.json)记录源码基线、修改文件与源／归档日志摘要。归档仅替换测试机器绝对路径和主机名，测试名称、错误类型、结果及数量保留。
