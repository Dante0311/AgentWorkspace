import hashlib
import json
from pathlib import Path

from agent_workspace.app import App
from agent_workspace.commands import execute
from agent_workspace.util import encode

test = Path(__file__).parent
previous = Path(r'<FIXTURE_ROOT>')
old = App(previous / 'data/desktop-home')
app = App(test / 'home')
app.workspace_connect('desktop-local', old.workspace_list()[0]['address'])
root = previous / 'instances/desktop-probe'
app.connect_agent('desktop-local', 'desktop-probe', str(root))
state = app.show('desktop-local', 'desktop-probe')
assert state['current'] is None and not state['has_run'], 'Existing fixture was already started; inspect it.'
(test / 'reports').mkdir(exist_ok=True)
(test / 'reports/00-before.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
description = '''本实例现用于用户授权的 Codex Desktop 自动启动、消息和同实例交接隔离验收。
首次正式进入：用平台 asset.write 保存 notes/desktop-bootstrap.txt，内容为 DESKTOP_BOOTSTRAP_9f84a3c1，然后保存一次 checkpoint 并结束本轮。
接手时：读取该已保存资产，使用真实 CODEX_THREAD_ID 写 notes/desktop-relay.txt，内容包含旧标记和本次真实聊天 ID；保存 checkpoint 后结束本轮。
只处理本轮明确测试通知。不得查询或修改产品目录、创建其他实例或聊天、安排业务、发送外部消息、轮询或 sleep 等待后续消息。
handoff 请求到来时保存实际资料和 checkpoint，调用 agent.stop，随后立即结束本轮，不自行启动后继。
所有平台操作使用正式进入材料提供的 aw call --desktop-agent 命令前缀，身份由实际桌面聊天校验。
'''
store = app.store('desktop-local')
snapshot = store.snapshot()
path = 'agents/desktop-probe.json'
item = snapshot.json(path)
item['description'] = description
store.change('main', {path: encode(item)}, {path: snapshot.entries[path]}, 'Authorize isolated Codex Desktop integration acceptance')
asset = execute(app, 'asset.read', {'workspace': 'desktop-local', 'agent_id': 'desktop-probe', 'path': 'AGENTS.md'})
execute(app, 'asset.write', {'workspace': 'desktop-local', 'agent_id': 'desktop-probe', 'path': 'AGENTS.md',
                           'revision': asset['revision'], 'content': '# desktop-probe\n\n' + description})
execute(app, 'agent.upgrade-tools', {'workspace': 'desktop-local', 'agent_id': 'desktop-probe'})
product_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (previous / 'product').iterdir() if p.is_file()}
(test / 'reports/01-prepared.json').write_text(json.dumps({'fixture_root': str(root), 'new_home': str(app.home),
    'product_sha256': product_hashes, 'description': description, 'baseline': '5aaae00520374b022e0c38fa21f312f8e08629ba',
    'wheel_sha256': hashlib.sha256(next((test / 'dist').glob('*.whl')).read_bytes()).hexdigest()}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'prepared': True, 'current': app.agent('desktop-local', 'desktop-probe')['current']}))
