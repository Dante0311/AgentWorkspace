# 共同资料与 Windows：本批开发证据

2026-10-09。基于 main `a8b4535` 和真实远端开发检查点 `8d86b60`。软件仍为 `0.1.0a1`。本页描述已经执行的开发验证，不宣称用户真实模型、最终 Windows 或原生 Desktop 写操作已通过。

## 交付内容

共同职责：Definition 原样复制为 AGENTS.md，独立 @workspace-read 行给出必读仓内路径；平台先检查可读性，进入提示固定同一 Git 提交，模型通过 workspace.read 实际取得全文。不写死机器路径，不复制共同正文，不把预检当作已读。

共享 Skill：自动发现，创建时选择，已有实例安装/更新。与 Definition、内置和自有 Skill 分别记录，保护私人修改和名称冲突。全目录交换有持久意图，中断只恢复原结果；未完成交换不发布半成品，不自动重载模型或代保存检查点。

桌面准备：从真实连接发现项目，核对主目录并保存可靠 ID。分区写操作只在真实 tools/list schema 匹配时启用，并读回成员关系；未知结果保留防重做记录，分区失败仍可采用已核验项目。原生项目创建/文件夹编辑没有可靠合同，仍明确手动，不以夹具假装已接通。

Windows：此前已推送的检查点分四片运行，保持每 job 25 分钟，不删用例，保存选择清单/JUnit/耗时。安装检查改为认证 HTTP 正常停机并等待自有线程；最新远端暴露删除 Git 对象的 WinError5；原日志没有记录该文件属性，本地仅在运行时确认普通只读文件的条件下恢复写位并重试一次，不能把其他权限错误当只读问题。额外限制未完成请求的读取超时，避免停机无限等待。以上不强行释放实例资格。

## 验证矩阵

| 验证 | 已执行结果 | 边界 |
| --- | --- | --- |
| 最终共享资料/Skill/准备/清理/停机/分片/说明组 | [52 passed / 1 skipped](final-features.txt)、[JUnit](final-features.xml)、[exit 0](final-features.exit) | 跳过项为 Windows 真实只读文件语义；Desktop 来自 schema 夹具 |
| 相邻核心/分发/交接安全/Desktop 回归 | [93 passed](final-adjacent.txt)、[JUnit](final-adjacent.xml)、[exit 0](final-adjacent.exit) | 不重跑完整 A–J；与其他组有交叉，不累加 |
| 桌面分区失败不阻塞项目、已有归属不重复移动、预检失败不留未知回执 | [20 passed](desktop-final.txt)、[JUnit](desktop-final.xml)、[exit 0](desktop-final.exit) | 最后增量，覆盖准备与既有 Desktop；不是用户本机实际写入 |
| 真实 Codex 客户端＋回环模型的共享正文工具链 | [1 passed](native-shared.txt)、[JUnit](native-shared.xml) | 随机正文不在初始输入中，工具返回后的后续协议请求含全文；不证明真实付费模型已读取或理解 |
| Skill 管家授权与维修相邻组 | [首跑35 passed / 1 环境导入失败](skill-grants.txt)，修正子进程源码路径后[仅原失败1 passed](skill-grants-environment-fixed.txt) | 新授权/撤权用例首跑通过；原失败是未安装环境中子CLI找不到模块，产品代码未为此改变，原日志保留 |
| 最终 wheel | [构建成功](final-build.txt)、[exit 0](final-build.exit)、[42 个包文件逐字节匹配](final-static.json) | 不发布 Release/PyPI、不改版本 |
| 最终安装/真实 HTTP 重启/巡检退出/临时数据清理 | [Linux PASS](final-smoke-linux.txt)、[exit 0](final-smoke-linux.exit) | 两份独立安装；没有实际模型/普通终端会话 |
| 当前环境真实 Chromium 页面 | [3 setup errors](browser.txt)、[JUnit](browser.xml) | ERR_BLOCKED_BY_ADMINISTRATOR 阻止访问回环页面，未绕过、未计通过；新浏览器测试已加入源码，待最终 CI/实机 |
| 已推送 8d86b60 的 Windows 分片 | 两版 Python 的 8 个 job 全部 success | 只属于初始检查点；不能代表后续新增功能提交。对应 CI 整体 failure |
| 8d86b60 Windows 安装 | [WinError 5 failure](windows-installation-initial.txt) | 独立检查删除 Git 对象时报权限错误；后续条件修正尚未在 Windows 重跑 |

早期 features/adjacent/integrated 运行不与最终数字累加。目录中的 features.txt/native-shared.txt 等保留已执行阶段，final-* 是对应最终检查。一次合并工具调用包含多组检查、构建及早期冒烟，在工具 45 秒限额处中断返回；早期 smoke-linux.txt 后来出现 PASS，但没有取得调用退出码，不以它单独证明该次完整成功。最终构建后的独立冒烟另行执行，明确 exit 0，原过程不删除。

## 不能宣布关闭的边界

Windows 原 `WinError145` 的根因尚未被独立复现为唯一原因。正常停机和只读文件处理消除了已定位的生命周期/清理缺口，但最终 Windows 安装仍需执行。不是“忽略清理错误”，也不以 Linux PASS 或初始 Windows 分片通过关闭最终验收。

当前 GitHub 工具仅提供读取；常规 Git 连接实际在 DNS 解析阶段失败。因此后续提交在真实 `8d86b60` 父历史上本地保存，以 Git bundle 交付，未更新 PR15 或 main。不是等待用户重新开发；取得写通道后可直接 fetch bundle 并 push 相同提交，无需逐文件搬运。实际复测按 [统一验收](../../shared-materials-acceptance.md)完成，不让用户分批重装。

实际业务副作用全部发生在临时隔离数据；未触碰旧 E2E 账本、旧 transfer、alpha HY 资格、生产 SBP 或企微，也没有代用户重启/终止非本批进程。修复后的真实官方账号、WorkBuddy 启动/认证、其他未测能力不在这里冒充通过。

## 归档

[manifest.json](manifest.json)记源日志与归档文件摘要、初始远端检查和最终包摘要；[SHA256SUMS](SHA256SUMS)覆盖本目录其他文件。只替换执行环境路径与测试主机名，保留错误、测试名称、阶段和数值。没有加入密钥、下载 SAS、私人会话、操作系统运行锁或依赖二进制。Git/HTTP/MCP 的测试 token、随机标记和模拟调用明确属于夹具。

执行 `python verify.py` 只核对归档、JUnit/JSON，不启动模型、服务或测试；当前接续见 [CHECKPOINT](CHECKPOINT.md)。
