# T批 Watch 消息顺序记录

- 第一条原消息 ID：`r-watch-normal-001`
- 第一条 from：`workspace:setupc43bab4966e34765851333d07122cdfd` / `e2e-q-fork`
- 第一条 to：`workspace:setupc43bab4966e34765851333d07122cdfd` / `e2e-beta`
- 第一条 delivery：`normal`
- 第一条当前 Binding：`bfe56718746f34061bcf4334d686d159a`
- 第一条 ACK：`ack-r-watch-normal-001`，publication.state=`published`，receiver=`e2e-beta`，binding 匹配。
- 第一段：虚构交接记录A

- 第二条原消息 ID：`r-watch-normal-002`
- 第二条 from：`workspace:setupc43bab4966e34765851333d07122cdfd` / `e2e-q-fork`
- 第二条 to：`workspace:setupc43bab4966e34765851333d07122cdfd` / `e2e-beta`
- 第二条 delivery：`normal`
- 第二条当前 Binding：`bfe56718746f34061bcf4334d686d159a`
- 第二条 message_refs：[`r-watch-normal-001`]，引用第一条。
- 第二条 ACK：`ack-r-watch-normal-002`，publication.state=`published`，receiver=`e2e-beta`，binding 匹配。
- 第二段：虚构交接记录B
- 实际顺序：先接收 `r-watch-normal-001`，后接收引用第一条的 `r-watch-normal-002`。
