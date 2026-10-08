import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

from agent_workspace.app import App
from agent_workspace.util import read_json

test = Path(__file__).parent
app = App(test / 'home')
root = app.root('desktop-local', 'desktop-probe')
state = app.show('desktop-local', 'desktop-probe')
assert state['current'] is None, state['current']
snapshot = app.store('desktop-local').snapshot()
bindings = [snapshot.json(p) for p in snapshot.entries if p.startswith('bindings/')]
assert all(b['phase'] == 'released' for b in bindings)
assert not read_json(root / '.aw-local/watch.json')['enabled']
assert not (root / 'notes/must-not-write.txt').exists()
product = root.parent.parent / 'product'
before = read_json(test / 'reports/01-prepared.json')['product_sha256']
after = {p:hashlib.sha256((product / p).read_bytes()).hexdigest() for p in before}
assert before == after
assert read_json(root / '.aw-local/transfer.json')['state'] == 'completed'
saved = test / 'snapshot'
for prefix in ('agents/', 'bindings/', 'handoffs/', 'checkpoints/', 'messages/', 'message-index/', 'acks/', 'dispatch/'):
    for name, data in snapshot.all(prefix).items():
        path = saved / 'shared' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
for prefix in ('notes', 'records', '.aw/checkpoints', '.aw-local/inputs', '.aw-local/transfers'):
    for path in (root / prefix).rglob('*'):
        if path.is_file() and path.suffix in ('.json', '.jsonl', '.txt'):
            dest = saved / 'instance' / path.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
for name in ('status.json', 'entry.json', 'launch.json', 'transfer.json', 'watch.json', 'renew.json', 'renew-result.json', 'runner.log'):
    path = root / '.aw-local' / name
    if path.exists():
        dest = saved / 'instance/.aw-local' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
wheels = {p.relative_to(test / 'dist').as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (test / 'dist').rglob('*.whl')}
with zipfile.ZipFile(test / 'dist/round5/git_native_agent_workspace-0.1.0a1-py3-none-any.whl') as tested, zipfile.ZipFile(test / 'dist/final/git_native_agent_workspace-0.1.0a1-py3-none-any.whl') as final:
    old = {n:tested.read(n).replace(b'\r\n',b'\n') for n in tested.namelist() if n.startswith('agent_workspace/')}
    new = {n:final.read(n).replace(b'\r\n',b'\n') for n in final.namelist() if n.startswith('agent_workspace/')}
    changed = sorted(n for n in old.keys() | new.keys() if old.get(n) != new.get(n))
assert changed == ['agent_workspace/resources/prompts/capabilities.md'], changed
report = {'shared_revision':snapshot.revision,'agent':state,'bindings':bindings,'product_before':before,'product_after':after,'watch_disabled':True,'old_session_sentinel_absent':True,'wheels_sha256':wheels,'final_vs_live_tested_payload_changes':changed}
(test / 'reports/22-final-state.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'current':state['current'],'bindings_released':len(bindings),'product_unchanged':before==after,'final_payload_changes':changed}))
