# 本批开发检查点

基线 main：a8b45354743bf865534396e66c9885f16feb2199。
已推送开发分支：feat/shared-materials-and-windows，PR15 draft，已核对 head 8d86b60c7e515e634096cd97a27e9e7f4eed8f35。

本地真实历史提交：
- 2517e1e：确认的 Windows 普通只读 Git 文件清理，未知错误保留。
- ca89371：未完整 HTTP 请求的有界读取超时及停机回归。
- ee2fc60：共同职责 Git 读取、独立共享 Skill、工作台与窄接口 Desktop 准备及测试。
- dd2decc：复用已有管家授权表开放共享 Skill 的明确目标管理及撤权回归。
- 本文件所在的后续文档提交：设计合同、用法、统一验收和完整证据，不再修改产品代码。

8d86b60 对象的树和原生 Git 提交 SHA 已核对；它的真实父提交是 a8b4535。当前浅库以8d为边界，不伪造 root 或上传合成历史。Git bundle 使用8d作为已有前提，接手时先正常 fetch origin 再 fetch bundle 中的相同分支。不得从源码压缩包覆盖 main。

当前 GitHub 只读，常规 Git网络解析不可用；后续本地提交尚未推送。没有合入 main、发 Release、改生产实例或扩大权限。下一次合并只核对远端变化及必要检查，保留其他会话的新提交，不逐文件重建，CI 未结束不反复 sleep。

## 已完成与剩余检查

产品功能和针对性回归已保存，详情以 README 的矩阵和确切日志为准。最终包的42个代码/资源文件逐字节匹配。Linux 独立安装 exit0；真实 Codex客户端/回环正文传输1passed。浏览器受到管理员策略阻止，最后Windows清理代码未在Windows执行，两者保持未通过/待验证而非冒充绿灯。

8d初始CI：37898110675，总体 failure；Windows8片、Linux2组、浏览器与Linux构建通过，Windows安装只读对象失败。原生SDK37898110691 success。这不是最终功能提交CI。

## 接续约束

不重跑 A–J，不改旧 ledger/transfer/锁或alpha资格。先把现成的Git提交通过可用写通道推到同一开发分支，必要CI结束后再按用户授权合并。最终Windows安装、真实模型共同正文、真实Desktop schema和分区按 docs/shared-materials-acceptance.md 集中验收。

新增源文件：shared.py 和 skills.py。Definition原内容保持，独立Skill来源在.aw/skill-sources.json，临时交换在.aw-local/skill-install。不要手工改来源清单或删除中断意图。桌面项目创建/文件夹编辑没有核实接口，明确手动；现有项目复用与按广告schema支持的分区是本版窄适配，不据夹具宣称任意桌面版本兼容。
