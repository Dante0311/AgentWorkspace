# 开发接续 Checkpoint

软件开发恢复记录，不是产品实例 checkpoint，也不是第二份设计。先核对远端提交和实际测试，不从聊天中的“继续”推断完成。

## 接续位置

- 日期：2026-10-04。唯一实现分支 `feat/native-runtime-maintenance`，草稿 [PR #4](https://github.com/Dante0311/AgentWorkspace/pull/4)，基于 PR #3。不要新建平行实现、合并 main、改写历史或发布版本。
- 本批基线：`9c24ff807fb72cdde97147ee47644b677ab40bfd`。它已保存跨实例写入授权修复，以及真实 Claude/CodeBuddy 通过 MCP 创建检查点、接收 Message 和写入 ACK 的测试。
- 产品决定以文档 PR #2 的 `7cc281aa3b6f0f03250cdd8f43364dfb53357558` 为准。该分支的旧设计与使用说明尚须对齐，不据旧合同削减 V1 自动化。

## 本批完成

- 维修动作的结果先持久保存，再执行独立健康复查。复查失败、进程退出、复查结果写入失败后，同一请求仅补复查，不重复修复动作；未知副作用仍不自动重放。
- 单个实例的损坏 JSON 不再中断其他实例巡检；无法识别归属的本机发布记录单列异常，不删除、不修改原记录。
- 新增真实 Codex → Claude 自动交接验证：模型协议夹具要求原生 Codex 调用 checkpoint.create 和 agent.stop，Runner 确认停妥后创建原生 Claude 后继会话。检查原绑定 released、后继绑定固定、用户资产保留、接手材料加载，以及 Message 自动投递到后继并生成真实 ACK。不用手工 stop 调用代替原生工具执行。
- Native SDK CI 已包含该交接测试。模型响应来自回环 API，不使用付费模型、真实账号或生产数据；真实客户端、SDK、平台 MCP 和 Git 副作用均参与测试。

## 验证

- 新维修恢复用例在修复前为 3 failed / 1 passed，损坏记录用例在修复前为 2 failed。
- 本批维护/恢复/HTTP/交接安全组：`33 passed in 26.03s`。
- Codex、Claude、CodeBuddy 原生工具测试与真实跨 Harness 交接组：`4 passed in 28.84s`。
- `9c24ff8` 的 Native SDK contracts run `37198787506` 已成功；CI run `37198787505` 的 Linux 两组和构建已成功，最后读取时 Windows 仍运行。本批新提交须查看自己的 CI，不能沿用旧结果。
- 本机完整套件之前超时，未取得全套结论；不将分组结果冒充全套。上传前核对文件 Git blob SHA，并保存所有完成单元。

## 待接续

1. 对齐 PR #2 的设计/开发约定，更新当前使用说明、能力矩阵和实机验收步骤。
2. 查看本批 CI 和原生 SDK CI；如有失败先修复，不放宽断言掩盖问题。
3. Claude/WorkBuddy 原生 Desktop 控制接口仍未确认；Codex Desktop 为显式桌面控制接入，不能宣称已自动创建和跨端接手。SDK insert/steer 不支持时明确拒绝。以上不是仅待用户验收。
4. 当前已有持续会话、持久交接、管家授权、程序定时巡检、限定维修和隔离安装入口；真实账号、自己的 API、生产 Git 凭据/权限、企业微信及新机器体验需分别实测。

管家和用户 Agent 共用普通实例能力；首次启动只发现和引导，不代装 Git/Harness 或登录。不改全局模型配置，不重写 Harness，不强制 ACP/网关。保留唯一入口、用户资产、凭据引用和未知结果保护；权限检查不等于操作系统沙箱。
