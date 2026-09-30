"""Protocol fixture: stdout is the documented channel bridge contract."""
import json
import sys
if len(sys.argv)>1 and sys.argv[1]=='crash':
    raise SystemExit(1)
print(json.dumps({'event':'ready'}),flush=True)
for line in sys.stdin:
    item=json.loads(line)
    if item['event']=='send':
        print(json.dumps({'event':'sent','id':item['id'],'receipt':'fixture-only'}),flush=True)
