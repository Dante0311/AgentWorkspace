# Workspace 共同职责与共享 Skill

这是两条不同路径：共同职责在每个新会话进入后必读；Skill 按需安装一个明确版本。都使用所属 Workspace 的 Git 文件，不依赖 main 的普通检出目录，不修改产品规则。

## 共同职责：定义保留指引，正文只有一个共享来源

共享仓可以这样组织：

```text
knowledge/team-rules.md
knowledge/stage-owner-rules.md
definitions/stage-a/definition.md
definitions/stage-a/skills/special-review/SKILL.md
skills/code-review/SKILL.md
skills/code-review/references/checklist.md
```

在 `definition.md` 的正文中写独立行，例如：

```markdown
# Stage A

@workspace-read knowledge/team-rules.md
@workspace-read knowledge/stage-owner-rules.md

本角色负责 Stage A；特殊边界在这里说明。
```

复制这个示例的内容时，不保留外围代码围栏。平台只识别独立的 `@workspace-read` 指令行，忽略 Markdown 围栏中的示例；不替换 `<…>`，不支持通用模板、嵌套 include 或职责继承。每行一个仓内相对文件路径。

创建时 `definition.md` 仍逐字节成为实例根目录 `AGENTS.md`。不写入机器盘符、不拼接共同正文、不新增隐藏的个人 Workspace。新会话的进入材料会给出精确的 `workspace.read` 参数：这些文件从同一个共享提交读取，而不是逐文件追逐变化中的 main。平台预检缺文件时，在预留入口或交出前报错；预检成功只表示资料可读，不能代替模型读取。

实例进入后，先读自己的 `AGENTS.md`，再实际调用提供的读取操作，完整阅读正文。首次进入、relay 和 fork 都遵循此约定。手动进入可用 CLI；Desktop 使用进入材料给出的真实身份 CLI 前缀，不能自行改身份。

```sh
aw -w sea workspace read --path knowledge/team-rules.md --path knowledge/stage-owner-rules.md
aw -w sea workspace read --path knowledge/team-rules.md --revision FULL_COMMIT_SHA
```

`FULL_COMMIT_SHA` 要替换为实际 40 位提交。模型工具调用为 `workspace.read`，参数 `paths` 是路径数组，所属 Workspace 默认由调用身份补入；模型不能借此读取另一个 Workspace。返回完整 UTF-8 正文、每文件 SHA-256、同一 `revision` 和 `complete=true`。允许读取 `knowledge/`、`references/`、`skills/`、`definitions/` 下的普通材料，不是任意协议状态或本机文件读取接口。一次 1–64 份文件、总计最多 512 KiB；缺失、二进制、非法路径、权限/网络失败或超限都报错，不返回截断内容冒充完整读取。

进入提示固定当次共享版本；新会话重新读取当时 main。修改共同文件不必改写所有 Definition，`agent.versions` 也不会把共同文件变化误判成个人 `AGENTS.md` 被改。已有会话只有明确再次读取才获得新正文。换机器后先正常 connect 同一 Workspace/实例，调用其 Git 读取入口即可，不沿用旧机器路径。离线且无法取得指定版本时如实失败，不静默读旧缓存当最新。

这是一项可验证的读取约定，不是模型理解或遵守的数学保证。文件生成、平台读回、原生工具正文传输和真实模型遵循分层验收。读取失败时暂停依赖共同职责的工作，不把自动初始检查点标成已阅读证明。业务规则仍留在产品仓。

## Skill：自动发现，明确安装与更新

共享候选来自 `skills/<目录名>/SKILL.md`；说明从简单 frontmatter 的单行 `description:` 读取。候选目录使用可移植 ID。目录不会因为被发现而自动安装。Definition 的专用 `skills/` 仍随该定义带入；七个软件内置 Skill 仍由安装资源维护。

```sh
aw -w sea workspace skills
aw -w sea agent create reviewer --definition definitions/reviewer --skill code-review
aw -w sea agent skills reviewer
aw -w sea agent skill-install reviewer --name build-check
aw -w sea agent skill-update reviewer --name code-review --revision FULL_COMMIT_SHA
```

创建时可重复 `--skill`，也可不使用 Definition。工作台创建表单提供勾选，实例卡片的“Skill”提供安装和选定更新；批量操作逐项执行并显示结果，不声称跨 Skill 原子提交。直接修改文件的 Agent 使用同一组 `agent.skills`、`agent.skill-install`、`agent.skill-update` 工具，其原有身份与跨实例授权边界不变。管家跨实例需要用户明确授予 agent.skill-install/agent.skill-update 及目标；撤权立即拒绝，不凭角色名称取得权限。

安装把完整目录复制到 `.agents/skills/<目录名>/`，包含脚本和参考文件，但不执行脚本。共享 Git 是发布来源，不把未提交检出修改当成已发布版本。Definition 来源继续由 `source.json` 管理；独立 Skill 来源记录在 `.aw/skill-sources.json`，按每个 Skill 保存源路径、实际提交和所有文件摘要。`agent.versions/update` 继续处理 Definition，`agent.skills/skill-update` 单独处理共享 Skill。

更新比较实际文件变化，不因 Workspace 无关提交而提示过期。实例添加、删除、修改过该 Skill 的任何文件都先报冲突；软件内置、Definition 专用、自有 Skill 和大小写冲突名称不得覆盖。共享来源删除后保留实例副本，不自动删除。更新 Definition 也不能侵占独立安装的 Skill。仅文件替换，不自动重载当前模型，不自动发布实例检查点；需持久保存时按既有 checkpoint 流程完成。

文件交换前写入本机意图，复用现有文件锁。中断时 `agent.skills` 返回 `pending_update` 与原操作的名称/版本，工作台提供“恢复原更新”；CLI 重用原名称与固定版本即可。已完成的文件交换只补来源记录，未交换的旧目录可恢复；出现额外私人修改时保留双方供检查。未完成交换时拒绝新会话、交出和实例快照，不能把半个 Skill 发布为成功。不要删除 `.aw-local/skill-install` 来绕过恢复。

## Codex 项目和分区准备

实例的“桌面项目”先保存建议名称、实例主目录和显式产品目录。然后选择“发现并复用 Codex 项目”，或：

```sh
aw -w sea agent desktop-discover reviewer
aw -w sea agent desktop-prepare reviewer --request-id prepare-reviewer-001 --project-id ACTUAL_ID
```

已有偏好时还须传入最新 `--revision`。这些操作不创建模型会话或 Binding。必须先捕获实际 Desktop 控制连接；从原生项目列表按本机实例主目录和可靠项目 ID 选择，不凭重名匹配，不把路径缺失视作成功。保存原生 ID 后，后续启动复用；用户改名仍能按 ID 找回。

原生项目创建、编辑文件夹的调用合同尚未核实，本版返回一次集中手动准备说明和预填值，用户准备后重新发现，不臆造 API 或改应用私有数据库。附加产品目录仍须手动核对，`product_folders_verified=false` 明确保留。

分区可以跳过。只有当前连接 `tools/list` 的名称及参数 schema 与本版窄适配吻合时，才允许显式 `--section-id` 或 `--create-section`；本版识别 `list_sidebar_sections`、`create_sidebar_section(name)`、`move_project_to_sidebar_section(projectId, sectionId)`。写后读回成员关系才报告 verified。schema 不符、接口缺失或分区读取失败时手动补齐，项目复用仍可继续。这个运行时检查不等于当前用户桌面已完成实测。

同一请求读回原结果，不重复创建或搬回用户后来的布局。分区创建结果未知时保留原请求及按名称的创建记录，新请求也不能另造重复分区。无法确定结果时先通过只读发现核对；不要删回执、换请求 ID 盲目重发。项目准备与原生会话的创建/交接分别验收。

统一复测见 [本批验收说明](https://github.com/Dante0311/AW-Workspace/blob/5ec6e5e99dcc68b8ec58e701a7ff9d7b119974e8/development/archive/2026-10-10-unified-57446de/docs/shared-materials-acceptance.md)。
