import json
from pathlib import Path
from agent_workspace.app import App
from agent_workspace.runtime import Desktop
from agent_workspace.util import read_json

test = Path(__file__).parent
app = App(test / 'home')
root = app.root('desktop-local', 'desktop-probe')
assert not (root / 'notes/must-not-write.txt').exists()
adapter = Desktop(root, read_json(root / '.aw-local/runtime.json'), '01a11a6e-2e37-7860-a43a-5fa7fe6230df')
prefix = [str(test / 'app5/Scripts/python.exe'), '-m', 'agent_workspace', '--home', str(test / 'home'), '--workspace', 'desktop-local', 'call', 'asset.write', '--arguments', json.dumps({'path':'notes/must-not-write.txt','content':'DENIAL_TEST'})]
try:
    result = adapter.notify('这是用户授权的隔离验收：验证已交出的旧桌面聊天无法继续写平台资产。只执行下面参数数组对应的命令一次，预期平台拒绝；报告原始错误后结束本轮。不要读取新 Binding、不要加 --desktop-agent、不要替换环境、不要直接写文件、不要恢复或重试，不要做其他工作。\n' + json.dumps(prefix), 'normal')
finally:
    adapter.close()
(test / 'reports/17-old-session-denial-request.json').write_text(json.dumps({'session':'01a11a6e-2e37-7860-a43a-5fa7fe6230df','result':result,'sentinel_absent_before':True}, indent=2), encoding='utf-8')
print(json.dumps(result))
