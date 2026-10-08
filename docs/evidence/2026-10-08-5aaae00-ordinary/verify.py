"""Read-only archive integrity, format and relative-link verification."""
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parent
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
failures = []
checksums = {}
for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
    digest, relative = line.split("  ", 1)
    if relative in checksums:
        failures.append("Duplicate checksum: " + relative)
    checksums[relative] = digest
actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
actual.discard("SHA256SUMS")
if actual != set(checksums):
    failures.append("Checksum file list differs from archive")
for relative, digest in checksums.items():
    path = root / relative
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        failures.append("Checksum mismatch: " + relative)
for entry in manifest["files"]:
    path = root / entry["archive_file"]
    data = path.read_bytes()
    if len(data) != entry["archive_bytes"] or hashlib.sha256(data).hexdigest() != entry["archive_sha256"]:
        failures.append("Source manifest mismatch: " + entry["archive_file"])
for relative in sorted(actual):
    path = root / relative
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix == ".json":
        json.loads(text)
    elif path.suffix == ".jsonl":
        for line in text.splitlines():
            if line.strip():
                json.loads(line)
    elif path.suffix == ".xml":
        ET.fromstring(text)
    if path.suffix == ".md":
        for link in re.findall(r"\]\(([^)]+)\)", text):
            target = link.split("#")[0].strip("<>")
            if target and "://" not in target and not (path.parent / target).is_file():
                failures.append("Missing link: " + relative + ": " + target)
print(json.dumps({"source_entries": len(manifest["files"]), "archive_files": len(actual) + 1, "failures": failures}, ensure_ascii=False))
raise SystemExit(bool(failures))
