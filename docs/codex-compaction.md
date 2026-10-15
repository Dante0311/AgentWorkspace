# Codex 压缩前保存

这是主动 checkpoint 指引之外的自动保存入口。Codex 的同步 `PreCompact` hook 在自动或手动压缩开始前调用 AW；AW 保存可取得的会话原文、已有业务总结与实例资料快照，然后让 Codex 继续。配置不依赖 `context_management.experimental_mode`。

## 启用

使用包含 `codex-hook` 命令的 AW 安装，并在 Codex 的 `hooks.json` 中加入以下 handler。将命令替换为本机实际 AW 可执行文件及 `AW_HOME`，优先使用绝对路径；不要替换已有的其他 hooks。

```json
{
  "hooks": {
    "PreCompact": [{
      "matcher": "^(auto|manual)$",
      "hooks": [{
        "type": "command",
        "command": "aw --home /path/to/aw-home codex-hook",
        "timeout": 180
      }]
    }]
  }
}
```

保留同步执行，不设置 `async`。非托管 hooks 需要在 Codex 中审查并信任；项目层配置还需要项目受信任。不要由 AW 写入 Codex 的信任记录或绕过用户审查。具体加载范围和审查入口以 [Codex Hooks 文档](https://learn.chatgpt.com/docs/hooks)为准。

启用意味着允许将对应 AW 会话的原文保存到其 Workspace 的 Git 存储。它可能是远端仓库，不只是本机备份。普通未绑定聊天不保存；旧入口、错误会话或不支持的事件不产生检查点。已有 `AW_WORKSPACE/AW_AGENT/AW_BINDING` 或 `CODEX_THREAD_ID` 身份环境时，只使用该身份，失败或未绑定都不降级。原生命令 hook 没有这些模型身份环境时，沿用 AW 的本机用户管理上下文，用 hook 提供的 `session_id` 查已有会话索引，并核对唯一的当前 active Binding；不接受输入中的 Agent/Workspace/Binding 作为目标，不设置或清除身份变量。

## 保存结果

- `record_refs` 记录原始会话、轮次、触发方式、原文文件、截至哪个字节及校验值。原文按字节保存，不根据对话内容生成总结。
- 自动点沿用最近非自动检查点的业务说明，标注其 ID 和时间；没有已保存说明就明确指出。后续应继续按主动 checkpoint 指引整理重要进展。
- 同一会话、轮次、触发方式及原文字节使用固定检查点 ID。未知结果核对原 ID，继续原请求，不创建新的随机检查点。
- 保存不改变 Binding，不进行 handoff/stop，也不调用模型。同步保存包含 Git 操作，耗时受仓库访问影响。
- 失败通过 hook 的 `systemMessage` 显示，默认继续压缩。原文缺失、归属无法核对或超过现有 50 MiB 单文件限制时，不报告原文已保存。

原文只覆盖 Codex 提供的本机会话文件以及实际读取的范围。外部产品仓、未落盘内容、Codex 未公开的内部状态不在保存承诺中。`PostCompact` 摘要导出尚未接入；这个保存点也不是新的人工总结。

## 验证

产品测试使用隔离 Git 和构造的 hook 输入核对身份、原文、资料快照与重复保存。真实原生触发须另用隔离 Codex 会话验证；人工执行保存命令或看到配置文件都不能证明真实压缩 hook 已运行。现有业务聊天不能仅为验证而强制压缩。
