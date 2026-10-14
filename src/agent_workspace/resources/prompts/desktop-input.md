这是平台向本次已绑定的 Codex Desktop 会话发送的输入领取通知。
开头 JSON 来自当前 Agent 和 Binding 登记，session 与 native_cwd 来自已经核验的本次原生会话；未知目录仍为 null。先核对真实 CODEX_THREAD_ID 与 session 一致，不设置或替换该变量。当前身份由 workspace、agent、binding 和真实 session 确定，不由项目名、项目根中的其他 Agent 名称或旧检查点署名确定。
项目共同规则继续适用。自己的职责文件是 instructions_file，个人 Skills 在 skills_directory；需要核对职责或接手方法时读取这些路径，不使用另一实例的个人入口。平台已经激活本次 Binding，不再次 start、reserve 或 bind，也不采用旧角色材料里的 Binding。
下面是本次原请求的领取命令参数数组。先执行该命令，读取返回 text 后按其内容工作；完整首次进入、交接或业务正文仍从这次领取返回。already_received 时不要重复执行，领取失败时报告实际结果，不改输入记录或绕过权限。
