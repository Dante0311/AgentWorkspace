import json
from pathlib import Path
from agent_workspace.app import App
from agent_workspace import runtime
from agent_workspace.util import read_json

test = Path(__file__).parent
app = App(test / 'home')
root = app.root('desktop-local', 'desktop-probe')
before = app.show('desktop-local', 'desktop-probe')
boot = read_json(root / '.aw-local/inputs' / ('boot-' + before['binding']['id'] + '.json'))
assert boot['state'] == 'completed' and boot.get('checkpoint_revision')
assert before['binding']['session'] == '01a11a8d-4410-7472-9db4-bc5d7f05b30f'
watch = runtime.watch(app, 'desktop-local', 'desktop-probe', 'start', interval=2)
prompt = '''继续用户授权的桌面隔离验收。你上一轮 notes/desktop-relay.txt 与检查点把真实聊天 ID 抄错了。命令输出的 CODEX_THREAD_ID 是平台核验的实际值；请重新读取旧启动资产，再读取 relay 资产的 revision，用 PowerShell 变量 $env:CODEX_THREAD_ID 和 ConvertTo-Json 直接生成 asset.write 参数，纠正 relay 资产。不要手抄 UUID；旧检查点保留，新建更正检查点。
随后只发送一条 normal 消息给本实例 desktop-probe，request_id 固定 desktop-watch-post-relay-9f84a3c1，正文是：
收到通知后按平台 message.receive 读取消息并生成 ACK；读取 notes/desktop-bootstrap.txt，再通过 asset.write 保存 notes/desktop-message-post-relay.txt，内容为 DESKTOP_POST_RELAY_9f84a3c1 加本轮实际 CODEX_THREAD_ID。必须用环境变量直接构造 JSON，不要手抄 UUID。保存 checkpoint 后结束本轮。
发送成功立即结束当前轮；不要提前接收、不等待、不 sleep、不轮询、不操作产品目录。后续投递由工作台负责。'''
queued = runtime.queue_input(app, 'desktop-local', 'desktop-probe', prompt, request_id='desktop-send-post-relay-9f84a3c1')
(test / 'reports/16-post-relay-message-queued.json').write_text(json.dumps({'agent': before, 'boot': boot, 'watch': watch, 'queued': queued, 'relay_before_correction': (root / 'notes/desktop-relay.txt').read_text(encoding='utf-8')}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'queued': queued['id'], 'binding': queued['binding']}, ensure_ascii=False))
