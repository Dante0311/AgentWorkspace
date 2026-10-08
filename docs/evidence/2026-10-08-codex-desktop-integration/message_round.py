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
watch = runtime.watch(app, 'desktop-local', 'desktop-probe', 'start', interval=2)
prompt = '''这是用户授权的桌面 Message/ACK 隔离测试。请用平台 message.send 给本实例 desktop-probe 发送一条 normal 消息，request_id 固定为 desktop-watch-9f84a3c1，消息正文为：
“收到本条测试通知后，先按平台正常流程 message.receive 取得正文并生成 ACK，再用 asset.write 保存 notes/desktop-message.txt，内容为 DESKTOP_MESSAGE_9f84a3c1 加本轮实际 CODEX_THREAD_ID；保存 checkpoint，立即结束本轮。”
只发布这一条消息，发布成功后立即结束当前轮，不等待、不 sleep、不轮询、不主动读取自己刚发出的消息，不运行任何产品工作。后续投递由工作台完成。'''
queued = runtime.queue_input(app, 'desktop-local', 'desktop-probe', prompt, request_id='desktop-send-self-9f84a3c1')
(test / 'reports/05-boot-complete-and-message-queued.json').write_text(json.dumps({'agent': before, 'boot': boot,
    'watch': watch, 'queued': queued}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'queued': queued['id'], 'binding': queued['binding'], 'watch': watch}, ensure_ascii=False))
