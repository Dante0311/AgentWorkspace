"""Physical paths selected by an explicit layout, never by per-file fallback."""
from collections.abc import Mapping
from contextlib import contextmanager
from importlib.resources import files as package_files
import json
from pathlib import Path, PurePosixPath

from . import __version__
from .util import Conflict, Error, digest, encode, locked, read_json


VERSION = 1
WORKER_VERSION = 2
MESSAGE_VERSION = 3
MESSAGE_BRANCH = 'aw-messages'
MESSAGE_ROOTS = frozenset(('messages', 'acks', 'message-index', 'dispatch'))
MESSAGE_GUARD = '.agentworkspace/message-permissions.json'
MARKER = '.agentworkspace/layout.json'
SHARED_ROOTS = frozenset(('agents', 'bindings', 'sessions', 'handoffs', 'checkpoints',
                         'messages', 'acks', 'message-index', 'dispatch', 'direct-messages',
                         'work', 'maintenance', 'migrations', 'workers', 'worker-mappings'))
INSTANCE_ROOT_FILES = {'source.json': 'source.json', 'config.json': 'runtime.json'}
LOCAL_OPERATIONS = frozenset(('context.json', 'launch.json', 'input-sequence.json',
                             'inputs', 'checkpoint-operations', 'fork-operations',
                             'skill-install', 'transfer.json', 'transfers',
                             'renew.json', 'renew-result.json', 'model-migration.json', 'software-update.json',
                             'bridge-sends', 'desktop-preparations'))


class MigrationRequired(Conflict):
    code = 'migration_required'


def _relative(name):
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name
            or any(ord(c) < 32 for c in name)):
        raise Error('Layout paths must be safe repository-relative paths.')
    path = PurePosixPath(name)
    if not path.parts or path.is_absolute() or '..' in path.parts or '.git' in (p.lower() for p in path.parts):
        raise Error('Layout path escapes its data root.')
    return path.as_posix() + ('/' if name.endswith('/') else '')


def marker(kind, *, version=VERSION, **facts):
    if kind not in ('workspace', 'instance'):
        raise Error('Unknown layout kind.')
    if version not in (VERSION, WORKER_VERSION, MESSAGE_VERSION) or (kind == 'instance' and version == MESSAGE_VERSION):
        raise Error('Unsupported data layout version.')
    return encode({**facts, 'version': version, 'kind': kind})


def version(source, kind):
    """Accept an instance root, pinned Snapshot, or prepared byte mapping."""
    if kind not in ('workspace', 'instance'):
        raise Error('Unknown layout kind.')
    if isinstance(source, (str, Path)):
        value = read_json(Path(source) / MARKER)
    elif isinstance(source, Mapping):
        raw = source.get(MARKER)
        value = None if raw is None else json.loads(raw)
    else:
        value = source.json(MARKER)
    if value is None:
        return 0
    if not isinstance(value, dict) or value.get('kind') != kind or type(value.get('version')) is not int:
        raise Error('Invalid data layout marker.')
    if value['version'] not in (VERSION, WORKER_VERSION, MESSAGE_VERSION) or (kind == 'instance' and value['version'] == MESSAGE_VERSION):
        raise Error(f"Unsupported {kind} layout version: {value['version']}")
    if value.get('state', 'ready') != 'ready':
        raise MigrationRequired('Finish the original layout migration before accessing this copy.')
    if value['version'] == MESSAGE_VERSION:
        if value.get('platform_prefix') not in ('', '.agentworkspace'):
            raise Error('Invalid message-layout platform prefix.')
        if value.get('role') != 'messages' and (value.get('messages_branch') != MESSAGE_BRANCH or
                                               type(value.get('worker_support')) is not bool):
            raise Error('Invalid message-layout branch or Worker support declaration.')
    return value['version']


def shared_path(snapshot, name):
    name = _relative(name)
    if name != 'workspace.json' and name.split('/')[0] not in SHARED_ROOTS:
        raise Error('Use the shared path resolver only for AW platform records.')
    current = version(snapshot, 'workspace')
    if current == MESSAGE_VERSION:
        document = snapshot.get(MARKER) if isinstance(snapshot, Mapping) else snapshot.bytes(MARKER)
        document = json.loads(document)
        prefix = document['platform_prefix']
        if prefix not in ('', '.agentworkspace'):
            raise Error('Unsupported platform data prefix.')
        if name.split('/')[0] in MESSAGE_ROOTS and document.get('role') != 'messages':
            raise Error('Read Message/ACK/index/dispatch through the explicit message snapshot.')
        return f'{prefix}/{name}' if prefix else name
    return f'.agentworkspace/{name}' if current else name


def worker_support(snapshot):
    current = version(snapshot, 'workspace')
    if current == MESSAGE_VERSION:
        return snapshot.json(MARKER).get('worker_support') is True
    return current == WORKER_VERSION


def expected(snapshot, objects):
    """Bind conditional writes to the same layout as their original read."""
    return {**objects, MARKER: snapshot.entries.get(MARKER)}


def instance_relpath(source, name, worker_id=None):
    name = _relative(name)
    if worker_id is not None:
        from .util import slug
        if version(source, 'instance') != WORKER_VERSION:
            raise MigrationRequired('Explicitly migrate this instance before using Worker paths.')
        return f'.agentworkspace/workers/{slug(worker_id)}/{name}'
    if name.split('/')[0] in ('local', 'layout.json'):
        raise Error('Use local_path for local state; layout metadata belongs to the migration.')
    if version(source, 'instance'):
        return f'.agentworkspace/{name}'
    if name in INSTANCE_ROOT_FILES:
        return INSTANCE_ROOT_FILES[name]
    if name == 'records/channels' or name.startswith('records/channels/'):
        return 'channels' + name[len('records/channels'):]
    if name.split('/')[0] in ('records', 'messages'):
        return name
    return f'.aw/{name}'


def instance_path(root, name, worker_id=None):
    return Path(root) / instance_relpath(root, name, worker_id)


def local_relpath(name):
    """Stable classification also used when moving legacy local receipts."""
    name = _relative(name)
    first = name.split('/')[0]
    if first in LOCAL_OPERATIONS:
        return f'operations/{name}'
    if first == 'cache':
        return name
    if first == 'logs' or name.endswith('.log'):
        return name if first == 'logs' else f'logs/{name}'
    return f'runtime/{name}'


def local_path(root, name, worker_id=None):
    name = _relative(name)
    if worker_id is not None:
        from .util import slug
        if version(root, 'instance') != WORKER_VERSION:
            raise MigrationRequired('Explicitly migrate this copy before using Worker runtime paths.')
        return Path(root) / '.agentworkspace/local/workers' / slug(worker_id) / local_relpath(name)
    if version(root, 'instance'):
        return Path(root) / '.agentworkspace/local' / local_relpath(name)
    return Path(root) / '.aw-local' / name


@contextmanager
def lock(root, name, *, wait=30, worker_id=None):
    """Recheck the layout after waiting so an old waiter joins the current mutex."""
    while True:
        path = local_path(root, name, worker_id)
        with locked(path, wait=wait):
            if local_path(root, name, worker_id) != path:
                continue
            yield
            return


def require_current(root):
    if version(root, 'instance') == 0:
        raise MigrationRequired('Migrate this legacy copy before updating current AW resources.')


def add_git_excludes(content):
    original = content.get('.gitignore', b'')
    lines = original.decode('utf-8').splitlines()
    missing = [value for value in ('/.agentworkspace/local/', '/.aw-local/') if value not in lines]
    if missing:
        content['.gitignore'] = original + (b'\n' if original and not original.endswith(b'\n') else b'') + ('\n'.join(missing) + '\n').encode()


def resource_files(root=None):
    """Current software resources; a legacy copy must be explicitly migrated first."""
    if root is not None:
        require_current(root)
    source = package_files('agent_workspace') / 'resources'
    result = {}
    for name in ('workspace', 'work', 'message', 'agent', 'handoff', 'relay', 'fork', 'worker'):
        pending = [(source / 'skills' / name, f'.agents/skills/{name}')]
        while pending:
            directory, prefix = pending.pop()
            for item in directory.iterdir():
                if item.name == '__pycache__':
                    continue
                path = prefix + '/' + item.name
                if item.is_dir():
                    pending.append((item, path))
                else:
                    result[path] = item.read_bytes()
    for name in ('initialization.md', 'entry.md', 'handoff.md', 'checkpoints.md',
                 'capabilities.md', 'desktop-projects.md', 'message-notification.json'):
        result[f'.agentworkspace/prompts/{name}'] = (source / 'prompts' / name).read_bytes()
    result['.agentworkspace/software.json'] = encode({'version': __version__,
        'files': {path: digest(data) for path, data in result.items()}})
    return result
