"""Update this installation's managed Agent materials without Agent business writes."""
import base64
import json
from pathlib import Path

from . import __version__, layout
from .util import Conflict, Error, Unavailable, digest, encode, inside, now, read_json, write_bytes, write_json


MANIFEST = '.agentworkspace/software.json'
OPERATION = 'software-update.json'
BUILTIN_SKILLS = frozenset(('workspace', 'work', 'message', 'agent', 'handoff', 'relay', 'fork'))


def _hash(root, path):
    target = inside(root, path)
    return digest(target.read_bytes()) if target.exists() else None


def _copy(root, locator, agent_id):
    if not root.is_dir():
        raise Unavailable('The registered instance directory is not accessible.')
    layout.require_current(root)
    identity = read_json(layout.instance_path(root, 'identity.json'))
    context = read_json(layout.local_path(root, 'context.json'))
    if (not isinstance(identity, dict) or identity.get('workspace') != locator
            or identity.get('agent') != agent_id or not isinstance(context, dict)
            or context.get('locator') != locator or context.get('agent') != agent_id):
        raise Conflict('The registered directory does not match this Workspace and Agent.')


def _preflight(root, fresh):
    manifest = read_json(root / MANIFEST)
    if not isinstance(manifest, dict) or not isinstance(manifest.get('files'), dict):
        raise Error('The managed resource manifest is missing or invalid.')
    before = {}
    for path, content in fresh.items():
        actual = _hash(root, path)
        before[path] = actual
        if path == MANIFEST or actual is None:
            continue
        previous = manifest['files'].get(path)
        if previous is None or actual not in (previous, digest(content)):
            raise Conflict(f'Modified or unowned platform resource: {path}. Preserve or reconcile it before updating.')
    return before


def _finish(root, operation):
    """Continue the original recorded bytes, including after a different release was installed."""
    changes = operation.get('files')
    if (not isinstance(changes, dict) or MANIFEST not in changes
            or not isinstance(operation.get('resource_revision'), str)
            or not isinstance(operation.get('version'), str)):
        raise Error('The original software update record is invalid.')
    content = {}
    for path, change in changes.items():
        parts = path.split('/')
        managed = (path == MANIFEST or path.startswith('.agentworkspace/prompts/')
                   or (len(parts) > 3 and parts[:2] == ['.agents', 'skills'] and parts[2] in BUILTIN_SKILLS))
        if (not managed or not isinstance(change, dict)
                or not {'before', 'after', 'content'} <= change.keys()
                or not isinstance(change['after'], str) or not isinstance(change['content'], str)
                or (change['before'] is not None and not isinstance(change['before'], str))):
            raise Error('The original software update contains an invalid material path.')
        data = base64.b64decode(change['content'], validate=True)
        if digest(data) != change['after']:
            raise Error('The original software update bytes do not match their recorded digest.')
        if _hash(root, path) not in (change['before'], change['after']):
            raise Conflict(f'Material changed during the original software update: {path}.')
        content[path] = data
    # The manifest is last so it never reports a complete release before its material files.
    for path in [name for name in content if name != MANIFEST] + [MANIFEST]:
        current = _hash(root, path)
        if current == changes[path]['after']:
            continue
        if current != changes[path]['before']:
            raise Conflict(f'Material changed during the original software update: {path}.')
        write_bytes(inside(root, path), content[path])
    for path, change in changes.items():
        if _hash(root, path) != change['after']:
            raise Conflict(f'Material readback differs after updating: {path}.')
    write_json(layout.local_path(root, OPERATION), {
        'state': 'complete', 'resource_revision': operation['resource_revision'],
        'version': operation['version'], 'completed_at': now(),
        'files': {path: change['after'] for path, change in changes.items()},
    })


def _update(root, fresh, revision):
    recovered = False
    with layout.lock(root, 'files.lock'):
        operation = read_json(layout.local_path(root, OPERATION), {})
        if not isinstance(operation, dict):
            raise Error('The software update record is invalid.')
        if operation.get('state') == 'pending':
            _finish(root, operation)
            recovered = True
        before = _preflight(root, fresh)
        changed = [path for path, data in fresh.items() if before[path] != digest(data)]
        if changed:
            operation = {'state': 'pending', 'version': __version__, 'resource_revision': revision,
                         'started_at': now(), 'files': {
                             path: {'before': before[path], 'after': digest(data),
                                    'content': base64.b64encode(data).decode('ascii')}
                             for path, data in fresh.items()}}
            write_json(layout.local_path(root, OPERATION), operation)
            _finish(root, operation)
        return {'state': 'updated' if changed or recovered else 'current', 'updated_files': changed,
                'original_update_completed': recovered}


def _status(root, fresh, revision):
    operation = read_json(layout.local_path(root, OPERATION), {})
    if not isinstance(operation, dict):
        raise Error('The software update record is invalid.')
    if operation.get('state') == 'pending':
        return {'state': 'pending', 'resource_revision': operation.get('resource_revision')}
    before = _preflight(root, fresh)
    changed = [path for path, data in fresh.items() if before[path] != digest(data)]
    return {'state': 'update_available' if changed else 'current', 'changed_files': changed,
            'resource_revision': revision}


def _registered(app, action):
    fresh = layout.resource_files()
    manifest = json.loads(fresh[MANIFEST])
    revision = digest(encode(manifest))
    results, seen = [], set()
    for workspace, access in app.local()['workspaces'].items():
        for agent_id, directories in access.get('instances', {}).items():
            for directory in directories:
                result = {'workspace': workspace, 'agent_id': agent_id, 'directory': directory}
                try:
                    root = Path(directory).expanduser().resolve()
                    key = (access['locator'], agent_id, root)
                    if key in seen:
                        continue
                    seen.add(key)
                    result['directory'] = str(root)
                    _copy(root, access['locator'], agent_id)
                    result.update(action(root, fresh, revision))
                except (Error, OSError, ValueError) as exc:
                    result.update(state=getattr(exc, 'code', 'unavailable'), reason=str(exc))
                results.append(result)
    return {'version': __version__, 'resource_revision': revision, 'instances': results,
            'complete': all(item['state'] in ('updated', 'current') for item in results),
            'user_assets_changed': False, 'snapshot_saved': False, 'shared_data_changed': False}


def update(app):
    return _registered(app, _update)


def status(app):
    return _registered(app, _status)


def require_ready(root):
    operation = read_json(layout.local_path(root, OPERATION), {})
    if not isinstance(operation, dict):
        raise Error('The software update record is invalid.')
    if operation.get('state') == 'pending':
        raise Conflict('Complete the original software update before using these Agent materials.')


def update_instance(app, workspace, agent_id, directory=None):
    root = app.root(workspace, agent_id, directory)
    _copy(root, app.local()['workspaces'][workspace]['locator'], agent_id)
    fresh = layout.resource_files(root)
    result = _update(root, fresh, digest(encode(json.loads(fresh[MANIFEST]))))
    return {**result, 'resources_updated': list(fresh), 'user_assets_changed': False, 'snapshot_saved': False}
