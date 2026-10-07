# E2E 修复后定向验收

仅验收 E2E-004 / E2E-001；E2E-002 另列。不是 A–J 重跑，也不重新登记已撤回的 E2E-003。

## 保护现场与使用修复

先读取用户当前开发工作区的 `git status --short` 和验收登记，保留未提交与未跟踪文件。在独立 worktree/修复分支应用补丁，基线为 `c1f747b`，不要覆盖原源码目录。软件安装、测试数据使用新的独立目录；确认实际导入的是修复版，不靠同为 `0.1.0a1` 的版本号判断。

不改旧输入账本，不 advance / 重试旧 `p-beta-normal-transfer-001`，不删除锁、不强制释放 alpha 的旧 HY 资格，不复制旧状态到新数据。原报告、原始验收规程和运行证据均保留。源码应用和模型调用是两件事，应用补丁不启动任何模型。

## 已执行的开发测试

```sh
python -m pytest tests/test_e2e_terminal_state.py tests/test_transfer_safety.py tests/test_local_state.py tests/test_dispatch_efficiency.py tests/test_runtime.py -q
```

该组使用真实临时 Git 和确定性原生边界，121 项通过。新缺陷回归最初为 6 failed / 4 passed；修复后通过。额外边界包含晚到完成事件、失败/未确认 boot、复用显式检查点、并发启动回写、持久记录写入失败、旧 Runner 不覆盖新请求。

选定安装好的原生 Codex，并将其绝对路径通过 `AW_TEST_CODEX` 提供后，仅执行：

```sh
python -m pytest "tests/test_native_transfer.py::test_native_transfer_and_message[codex-codex]" -q
```

这个测试使用真实原生客户端、平台工具、Runner 与 Git，但模型响应由回环协议夹具生成。结果为 1 passed；它不是官方登录或真实模型验收，不因此启动企微。没有重跑六向矩阵或完整 A–J。

## 本机官方登录复测（待执行）

继续使用用户已批准的官方登录 `gpt-6-luna/low` 和已验证 Codex 入口。不复制凭据，不切换服务，不以自报模型名称代替配置/事件证据。先在新隔离数据中建立一个测试 Workspace 和一个测试实例；所有命令都显式指定新 `--home`，使用新的请求 ID。

1. 写入一个只供本轮使用的测试文件，内容包含随机标识；启动实例，等待 boot 成功与初始检查点。记录旧 Binding、session 和文件摘要。
2. 通过公开 `agent transfer-profile` 发起同 Codex、同批准配置的自动交接。只读本机新 `transfer.json` 等待真实后继的完成事实；不要用 `transfer-continue` 或 `advance` 推进它。必须在任何 `transfer-status` 查询前，先取得磁盘记录已是 `completed` 的证据。
3. 给后继一条明确测试指令：通过 `aw_execute` 读取刚才的文件，将读到的内容写到本轮验证文件，保存指定 ID 的检查点，再调用 `agent.stop`。不让模型通过 `asset.read` 访问受保护的 `.aw-local`；该目录由管理端只读核对。
4. 等后继正常释放、运行器退出。由管理端核对输入 ID 对应的原生完成事件、输入终态、显式检查点与释放记录，不能凭 idle 或 released 推定输入成功。旧交接持久记录、重新构造查询后的结果仍必须为 `completed`，session 不消失；验证文件与原资产相符。
5. 用同一旧交接请求 ID 查询/重提，确认仅返回原结果，不多出后继或业务动作。启动一个合法新入口，等待其 boot，再发起新的交接 ID，确认不被已完成的旧记录阻挡；让新的后继也正常保存并停工。旧 ID 应能读回归档的原结果。
6. 保存新报告及新 CHECKPOINT，明确软件提交/文件摘要、数据目录、所有请求/Binding/session/checkpoint、原生事件依据和进程收尾结果。不要改旧报告为“原先已通过”。

发生超时、认证失败或结果未知时保留新现场并停止本组；不重新发送原业务、不新造后继来绕过失败、不通过手改输入或 transfer 制造通过。已启用进程按公开停止入口处理，停止监视不是强制释放资格。未关联和未启用企微、生产 SBP/UE/CI、其他产品目录、远端 Git 或 Desktop。

本修复环境没有用户本机的官方登录，因此以上实际模型链路尚未执行；开发测试不能代替它。

## E2E-002 单独验证

固定 SDK `codebuddy-agent-sdk==0.3.267` 原本直接执行 `codebuddy_code_path`。Windows 选择 `.js/.cjs/.mjs` 入口时，现在通过 SDK 的公开 `transport` 参数注入其 SubprocessTransport 的小型子类，只改变解释器及参数前缀：`node <用户选定脚本> <SDK 原有参数>`。不经过 cmd，不复制一套协议。由于覆盖了 SDK 的 `_get_cli_path` / `_build_args` 两个实现钩子，升级 SDK 时必须重跑契约测试，不能只看版本号安装成功。原生 exe 仍使用原 Client，不自动切换到 SDK 自带程序。

```sh
python -m pytest tests/test_codebuddy_windows_entry.py tests/test_native_sdk.py tests/test_native_failure.py tests/test_sdk_metadata.py -q
```

当前结果：29 passed，实际使用安装的 SDK 和 Node 子进程，验证含空格/中文/符号的路径、原参数和环境保留、正常响应及 `/login` 失败响应、Node 缺失时不预留入口、不发 handoff。当前测试机是 Linux，测试只把本模块的平台选择条件设为 Windows；这不能证明 Windows 内核启动已验收。JS 是明确的协议夹具，不是用户 WorkBuddy 文件，也不是有效 HY 认证。

本机分三项记录，不能合并成一个“通过”：

1. **启动兼容：** 核对实际 JS 入口、Node 的可执行路径和版本、SDK 版本。在新的隔离实例测试 SDK 控制握手；不要只跑 help。缺 Node 时用户自行准备，不安装或选择另一份 Harness 冒充成功。
2. **认证：** 只检查上述同一个入口的实际登录结果。需要 `/login` 时让用户在这个入口登录；不复制 WorkBuddy Desktop 凭据、不改模型服务或环境区域、不释放旧 alpha 的 HY 资格。该入口登录不足不能推断 Desktop 未登录。
3. **真实接手：** 前两项通过并具有相应模型授权后，才在新隔离数据验证实际读旧检查点/资产。未取得相应环境与认证时保持阻塞，不冒称通过。

原生参考（读取于 2026-10-07）：[Python SDK / custom transport](https://www.codebuddy.ai/docs/cli/sdk-python)、[SDK 认证约定](https://www.codebuddy.ai/docs/cli/sdk)。具体启动行为以本仓固定 SDK 0.3.267 的实包源码及契约测试为准，通用网页不替代版本核对。
