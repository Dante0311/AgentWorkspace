"""Read portable Workspace material references from a single Git snapshot."""
import re

from .util import Error, digest, relpath


MATERIAL_ROOTS = ('knowledge', 'references', 'skills', 'definitions')
MAX_READ_BYTES = 512 * 1024


def material_path(path):
    if not isinstance(path, str) or any(ord(c) < 32 for c in path):
        raise Error('A shared material path must be a repository-relative string.')
    normalized = relpath(path)
    parts = normalized.split('/')
    if (len(parts) < 2 or parts[0] not in MATERIAL_ROOTS
            or any(':' in part or part.endswith(('.', ' ')) for part in parts)):
        raise Error('Read material under knowledge/, references/, skills/ or definitions/, not protocol or machine state.')
    return normalized


def required_paths(text):
    """Only standalone @workspace-read directives are special; examples are not."""
    paths, fence = [], None
    for line in text.splitlines():
        stripped = line.strip()
        marker = re.match(r'^(`{3,}|~{3,})', stripped)
        if marker:
            token = marker[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence or not stripped.startswith('@workspace-read'):
            continue
        directive, separator, value = stripped.partition(' ')
        if directive != '@workspace-read' or not separator or not value.strip():
            raise Error('Use a standalone @workspace-read followed by one repository-relative file path.')
        path = material_path(value.strip())
        if path not in paths:
            paths.append(path)
    return paths


def read_snapshot(snapshot, paths):
    if not isinstance(paths, list) or not paths or len(paths) > 64:
        raise Error('Select between 1 and 64 shared material files.')
    result, total = [], 0
    for path in dict.fromkeys(material_path(p) for p in paths):
        data = snapshot.bytes(path)
        if data is None:
            raise Error(f'Shared material is missing at {snapshot.revision}: {path}. No complete read was returned.')
        total += len(data)
        if total > MAX_READ_BYTES:
            raise Error('Shared reading exceeds 512 KiB. Split the material explicitly; no truncated read was returned.')
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise Error(f'Shared material must be UTF-8 text: {path}') from exc
        result.append({'path': path, 'content': text, 'sha256': digest(data)})
    return {'revision': snapshot.revision, 'files': result, 'complete': True}


def read(app, workspace, paths, revision=None):
    if revision is not None and (not isinstance(revision, str) or not re.fullmatch(r'[0-9a-fA-F]{40}', revision)):
        raise Error('Use a full Git commit for a pinned read, or omit revision to read current main.')
    snapshot = app.store(workspace).snapshot(revision=revision)
    return {'workspace': workspace, **read_snapshot(snapshot, paths)}


def requirements(app, workspace, root, snapshot=None):
    paths = required_paths((root / 'AGENTS.md').read_text(encoding='utf-8'))
    if not paths:
        return None
    snapshot = snapshot or app.store(workspace).snapshot()
    # Verify availability, not model comprehension. The model must still call read.
    read_snapshot(snapshot, paths)
    return {'command': 'workspace.read', 'arguments': {
        'workspace': workspace, 'paths': paths, 'revision': snapshot.revision}}
