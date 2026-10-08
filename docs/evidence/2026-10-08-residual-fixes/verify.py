"""Verify this immutable repair-evidence archive without launching any services."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parent
for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
    expected, name = line.split("  ", 1)
    target = (root / name).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise SystemExit(f"Invalid or missing archive file: {name}")
    if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
        raise SystemExit(f"Archive checksum mismatch: {name}")
for path in root.glob("*.json"):
    json.loads(path.read_text(encoding="utf-8"))
for path in root.glob("*.xml"):
    ET.parse(path)
print("PASS: repair archive checksums, JSON and JUnit formats")
