import json
from pathlib import Path
from agent_workspace.app import App
from agent_workspace.runtime import handoff_request
from agent_workspace.messages import Messages
from agent_workspace.util import read_json

test = Path(__file__).parent
app = App(test / 'home')
root = app.root('desktop-local', 'desktop-probe')
state = app.show('desktop-local', 'desktop-probe')
session = state['binding']['session']
message = Messages(app).show('desktop-local', 'desktop-watch-post-relay-9f84a3c1')
assert message['ack']
relay = (root / 'notes/desktop-relay.txt').read_text(encoding='utf-8')
post = (root / 'notes/desktop-message-post-relay.txt').read_text(encoding='utf-8')
assert session in relay and session in post
assert not (root / 'notes/must-not-write.txt').exists()
transfer = read_json(root / '.aw-local/transfer.json')
assert transfer['state'] == 'completed'
stop = handoff_request(app, 'desktop-local', 'desktop-probe')
report = {'agent':state,'message':message,'relay':relay,'post_relay_message_asset':post,'transfer':transfer,'old_session_write_denied_no_asset':True,'handoff_request':stop}
(test / 'reports/21-final-message-ack-and-stop-request.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'message':message['message']['id'],'ack':message['ack'],'handoff_request':stop['id']},ensure_ascii=False))
