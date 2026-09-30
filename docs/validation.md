# 0.1.0a1 验证记录

日期：2026-09-30。代码以本记录所在提交为准，来源设计为 Playbook `c9d4d4424e8116f86e7e585c2b126ab032da9cb4`。本轮新增可安装实现，不代表生产 V1 或真实外部 Runtime 已验收。

## 本次实际执行

环境：Linux、Python 3.13、Git 2.47.3。全部业务数据使用隔离临时目录；未调用真实用户模型、企业微信 Bot 或生产仓库中的平台数据。

```text
pytest -q                 47 passed，88.08 秒。
compileall                通过。
Python wheel 构建         通过，无运行时第三方依赖。
全新虚拟环境安装 wheel    通过。
脱离源码目录运行 aw       通过，创建 Workspace、创建及列出实例。
安装后资源检查            七个 SKILL.md 及配套资源均可读取。
```

上述安装检查在另一个工作目录运行，清空 PYTHONPATH，不靠源码或 Playbook 父目录导入。

## 测试证明的范围

| 范围 | 实际证据 |
| --- | --- |
| Git 持久化 | 使用真正的临时 bare 远端和 Git 命令，验证条件提交、分支、快照及多处访问。 |
| 实例与控制权 | 无 Definition/Work 创建、两个接手者竞争、旧入口拒绝、不可复用旧原生会话标识、本机进程锁及跨副本 controller。 |
| 资产 | 检查点不可变、Fork 保留确定版本、symlink/越界拒绝、同步冲突保护、来源更新不覆盖本地修改、选定文件导入与显式提升。 |
| Message | show 不 ACK、正文失败仍确认通知、FIFO、normal/insert、有限通知次数、过期入口拒绝、双仓同 ID 与部分发布补齐。 |
| Work | 创建、查询、工作树、条件修订、父子环拒绝、唯一交付及封存。 |
| Runtime | 真正启动隔离 JSON-RPC 协议替身进程，验证 Codex app-server 与 Desktop MCP 请求、事件落盘、绑定、停止确认和新入口。 |
| 桥接 | 真正启动隔离 JSONL 子进程，验证显式发送回执、异常退出和主动关闭；不自动回复用户或重放不明发送。 |
| 接口 | CLI 子进程、MCP stdio、本机 HTTP 请求、控制 Token、Host/Origin 校验及共同操作分发。 |
| GitHub Backend | 内存 REST 协议替身验证 Git 对象、条件变更及空仓首次 Contents 提交；不是真实 GitHub 平台业务调用。 |

另运行一条实际本地 Git 手动路径：创建两实例 → Message → receive/ACK → checkpoint → stop/交出 → Fork。没有使用 Work 也能完成。

## 工作台检查

Chromium 在离线页面中加载实际 HTML/CSS/JS，用明确的内存接口数据检查界面。1440×960 与 390×844 两种视口没有横向溢出；检查了页面切换、创建表单和 JavaScript 错误。此项属于静态资源与界面交互验证，不是实际模型操作。

真实 HTTP 服务另由 urllib 测试请求完成。当前浏览器环境对 localhost 导航返回管理员策略阻止，因此没有把浏览器到真实 HTTP 服务的端到端链路标为通过，也未绕过该限制。

## 尚未验证

真实 Codex Desktop 版本、真实 app-server 模型调用、Windows 的命令启动和进程行为、账号鉴权、企业微信 Bot/群聊、生产 GitHub Token/权限/限流、长期断线运行，均未在本次环境中验收。协议替身通过不等于这些外部系统可用。

企微插件按 WecomTeam 发布的 `wecom-aibot-python-sdk` 接口编写。当前环境下载可选依赖时发生 DNS 解析失败，未安装该 SDK，更未完成真实连接。基础 wheel 不依赖它；使用企微前须安装可选依赖并实际配置测试。

Desktop 首次配置与新会话 ID 取得可能仍需用户操作。打开 composer 不等于已提交提示词或取得执行资格；工具返回 awaiting_new_session_bind 时必须完成真实绑定，不能宣称端到端自动启动成功。

## 结论

这是有实际代码、测试、安装包和工作台的开发预览版。可以开始安装及隔离试用；不把它标为已完成全部生产 V1 验收。外部接入、性能与恢复边界按真实使用继续验证，不以扩大架构替代发现和修复问题。
