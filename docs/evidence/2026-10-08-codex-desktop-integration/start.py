import json
from pathlib import Path

from agent_workspace.app import App
from agent_workspace import runtime
from agent_workspace.util import read_json

test = Path(__file__).parent
app = App(test / 'home')
root = app.root('desktop-local', 'desktop-probe')
assert app.agent('desktop-local', 'desktop-probe')['current'] is None
config = read_json(root / '.aw-local/runtime.json')
assert config['caller_thread'] == '01a11a5e-7955-7570-b1db-a3290e8c9a3f'
profile = runtime.desktop_profile(app, 'desktop-local', 'desktop-probe', model='gpt-6-luna', effort='low')
result = runtime.start(app, 'desktop-local', 'desktop-probe')
(test / 'reports/02-start.json').write_text(json.dumps({'profile': profile, 'start': result,
    'connection_captured_by_real_probe_chat': True}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
