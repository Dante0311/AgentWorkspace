"""Read-only integrity and link check for this fixed evidence archive."""
from pathlib import Path
import hashlib
import json
import re

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
failures = []
for item in manifest['files']:
    path = root / item['path']
    data = path.read_bytes()
    if len(data) != item['archived_bytes'] or hashlib.sha256(data).hexdigest() != item['archived_sha256']:
        failures.append('Hash/size mismatch: ' + item['path'])
    text = data.decode('utf-8')
    if path.suffix == '.json' and text.strip():
        json.loads(text)
    if path.suffix == '.jsonl':
        for line in text.splitlines():
            if line.strip():
                json.loads(line)
for path in root.rglob('*.md'):
    for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
        if re.match(r'(https?://|mailto:|#)', link):
            continue
        if not (path.parent / link.split('#')[0]).exists():
            failures.append('Missing link in ' + str(path.relative_to(root)) + ': ' + link)
print(json.dumps({'files_verified': len(manifest['files']), 'failures': failures}, ensure_ascii=False))
raise SystemExit(bool(failures))
