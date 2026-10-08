import json
from pathlib import Path
from agent_workspace.app import App
from agent_workspace.runtime import Desktop
from agent_workspace.util import read_json

test = Path(__file__).parent
app = App(test / 'home')
root = app.root('desktop-local', 'desktop-probe')
snapshot = app.store('desktop-local').snapshot()
assert 'messages/desktop-watch-post-relay-9f84a3c1.json' not in snapshot.entries
assert not (root / 'notes/desktop-message-post-relay.txt').exists()
previous = read_json(root / '.aw-local/inputs/desktop-send-post-relay-9f84a3c1.json')
assert previous['state'] == 'completed'
adapter = Desktop(root, read_json(root / '.aw-local/runtime.json'), app.show('desktop-local', 'desktop-probe')['binding']['session'])
try:
    result = adapter.notify('用户授权验收的控制者纠偏：上一轮命令实际上 exit=0 并返回完整 text，已核实你尚未执行以下任务、尚无对应消息或资产。请按下面已核验正文继续完成；不要再调用 receive-input。命令若超过等待时限返回 session_id，应继续取回完成输出再判断，不要把仍在执行当作空结果。\n' + previous['text'], 'normal')
finally:
    adapter.close()
(test / 'reports/20-controller-correction.json').write_text(json.dumps({'confirmed_no_message_or_asset':True,'request_id':previous['id'],'result':result},indent=2),encoding='utf-8')
print(json.dumps(result))
