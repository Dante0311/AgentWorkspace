"""Read-only evidence integrity check; does not execute tests or start services."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parent
for line in (root / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
    expected, name = line.split('  ', 1)
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
for path in root.glob('*.json'):
    json.loads(path.read_text(encoding='utf-8'))
for path in root.glob('*.xml'):
    ET.parse(path)
print('PASS: archive hashes, JSON and JUnit formats')
