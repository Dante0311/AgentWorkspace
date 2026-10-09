"""Explicit shared Skill copies, per-Skill provenance, and protected local updates."""
import re
import shutil
import stat

from .util import Conflict, Error, digest, encode, inside, locked, read_json, relpath, slug, write_bytes, write_json


MANIFEST = '.aw/skill-sources.json'


def names(values):
    if values is None:
        return []
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise Error('skills must be a list of shared Skill directory names.')
    result = sorted(set(slug(v) for v in values))
    if len({v.casefold() for v in result}) != len(result):
        raise Conflict('Skill names must also be unique on case-insensitive filesystems.')
    return result


def snapshot(app, workspace, revision):
    if revision is not None and (not isinstance(revision, str) or not re.fullmatch(r'[a-fA-F0-9]{40}', revision)):
        raise Error('Use a full Git source commit, or omit revision for current main.')
    return app.store(workspace).snapshot(revision=revision)


def bundle(snap, name):
    slug(name)
    prefix = f'skills/{name}/'
    data = {p[len(prefix):]: v for p, v in snap.all(prefix).items()}
    if 'SKILL.md' not in data:
        raise Error(f'Shared Skill {name} has no SKILL.md at {snap.revision}.')
    try:
        data['SKILL.md'].decode('utf-8')
    except UnicodeDecodeError as exc:
        raise Error(f'SKILL.md must be UTF-8: {name}') from exc
    for path in data:
        relpath(path)
        if any(':' in p or p.endswith(('.', ' ')) or any(ord(c) < 32 for c in p) for p in path.split('/')):
            raise Error(f'Non-portable Skill asset path: {path}')
    if len({p.casefold() for p in data}) != len(data):
        raise Conflict(f'Skill {name} contains case-conflicting files.')
    return data, {'path': prefix.rstrip('/'), 'revision': snap.revision,
                  'files': {p: digest(v) for p, v in data.items()}}


def catalog(app, workspace, revision=None):
    snap = snapshot(app, workspace, revision)
    result = []
    for path in sorted(snap.entries):
        parts = path.split('/')
        if len(parts) != 3 or parts[0] != 'skills' or parts[-1] != 'SKILL.md':
            continue
        name = parts[1]
        try:
            slug(name)
        except Error:
            result.append({'name': name, 'available': False, 'error': 'Use a portable Skill directory name.'})
            continue
        text = snap.bytes(path).decode('utf-8', errors='replace')
        description = ''
        if text.startswith('---\n') or text.startswith('---\r\n'):
            for line in text.splitlines()[1:]:
                if line.strip() == '---':
                    break
                if line.startswith('description:'):
                    description = line.partition(':')[2].strip().strip('"\'')
                    break
        result.append({'name': name, 'path': f'skills/{name}', 'description': description, 'available': True})
    return {'workspace': workspace, 'revision': snap.revision, 'skills': result}


def seed(snap, selected, content):
    manifest = {}
    for name in names(selected):
        prefix = f'.agents/skills/{name}/'
        if any(p.casefold().startswith(prefix.casefold()) for p in content):
            raise Conflict(f'Skill {name} overlaps an existing platform, definition or imported Skill.')
        data, info = bundle(snap, name)
        content.update({prefix + p: v for p, v in data.items()})
        manifest[name] = info
    if manifest:
        content[MANIFEST] = encode(manifest)


def local_files(root):
    if not root.exists() and not root.is_symlink():
        return None
    result = {}
    pending = [root]
    while pending:
        path = pending.pop()
        info = path.lstat()
        if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
            raise Conflict('Skill updates do not follow symlinks or reparse points.')
        if stat.S_ISREG(info.st_mode):
            result[path.relative_to(root).as_posix()] = digest(path.read_bytes())
        elif stat.S_ISDIR(info.st_mode):
            pending.extend(path.iterdir())
        else:
            raise Conflict('Skill assets must be regular files.')
    return result


def inspect(app, workspace, agent_id, directory=None):
    root = app.root(workspace, agent_id, directory)
    available = catalog(app, workspace)
    snap = snapshot(app, workspace, available['revision'])
    sources = read_json(root / MANIFEST, {})
    definition = read_json(root / 'source.json', {}).get('files', {})
    candidates = {v['name']: v for v in available['skills']}
    folders = root / '.agents/skills'
    for path in folders.iterdir() if folders.exists() else []:
        if path.is_dir():
            candidates.setdefault(path.name, {'name': path.name, 'available': False})
    for name in sources:
        candidates.setdefault(name, {'name': name, 'available': False})
    platform = {p.split('/')[2] for p in app._resources() if p.startswith('.agents/skills/')}
    result = []
    for name, candidate in sorted(candidates.items()):
        prefix = f'.agents/skills/{name}/'
        origin = ('workspace' if name in sources else 'platform' if name in platform else
                  'definition' if any(p.startswith(prefix) for p in definition) else 'instance')
        local = local_files(folders / name)
        value = {**candidate, 'origin': origin, 'installed': local is not None}
        if name in sources:
            previous = sources[name]
            value.update(source_revision=previous['revision'], local_changed=local != previous['files'])
            if f'skills/{name}/SKILL.md' not in snap.entries:
                value['state'] = 'source_missing'
            else:
                _, latest = bundle(snap, name)
                value['upstream_changed'] = latest['files'] != previous['files']
                value['state'] = ('local_changes' if value['local_changed'] else
                                  'update_available' if value['upstream_changed'] else 'current')
        elif local is None:
            value['state'] = 'not_installed'
        else:
            value['state'] = 'owned_elsewhere'
        result.append(value)
    pending = read_json(root / '.aw-local/skill-install/operation.json')
    pending_skill = ({'name': pending['name'], 'revision': pending['after'][pending['name']]['revision'],
                      'operation': 'update' if pending['old_files'] is not None else 'install'} if pending else None)
    return {**available, 'agent_id': agent_id, 'skills': result,
            'pending_update': pending is not None, 'pending_skill': pending_skill}


def recover(root):
    """Finish only a known file swap; divergent user data is never overwritten."""
    stage = root / '.aw-local/skill-install'
    operation = read_json(stage / 'operation.json')
    if operation is None:
        # No swap can precede the durable intent. Discard only abandoned staging.
        if stage.exists():
            shutil.rmtree(stage)
        return
    name = slug(operation['name'])
    target = inside(root, f'.agents/skills/{name}')
    current = read_json(root / MANIFEST, {})
    actual = local_files(target)
    if current not in (operation['before'], operation['after']):
        raise Conflict('Skill source records changed during an unfinished update; preserve the staging directory.')
    if actual == operation['after'][name]['files']:
        if current != operation['after']:
            write_json(root / MANIFEST, operation['after'])
    elif current == operation['before'] and actual == operation['old_files']:
        pass  # Swap never happened.
    elif current == operation['before'] and actual is None and (stage / 'old').exists():
        if local_files(stage / 'old') != operation['old_files']:
            raise Conflict('Skill backup changed; recovery needs inspection.')
        (stage / 'old').rename(target)
    else:
        raise Conflict('Skill changed during an unfinished update; preserve local and staged files for inspection.')
    shutil.rmtree(stage)


def apply(app, operation, /, workspace, agent_id, name, revision=None, directory=None):
    slug(name)
    root = app.root(workspace, agent_id, directory)
    with locked(root / '.aw-local/files.lock'):
        recover(root)
        snap = snapshot(app, workspace, revision)
        data, info = bundle(snap, name)
        sources = read_json(root / MANIFEST, {})
        target = inside(root, f'.agents/skills/{name}')
        for parent in (root / '.agents', target.parent):
            if parent.exists() and (parent.is_symlink() or getattr(parent.lstat(), 'st_file_attributes', 0) & 0x400):
                raise Conflict('Skill parent directories must not be symlinks or reparse points.')
        siblings = target.parent.iterdir() if target.parent.exists() else []
        if any(p.name != name and p.name.casefold() == name.casefold() for p in siblings):
            raise Conflict('A case-conflicting Skill already exists.')
        local = local_files(target)
        previous = sources.get(name)
        reserved = set(app._resources()) | set(read_json(root / 'source.json', {}).get('files', {}))
        prefix = f'.agents/skills/{name}/'.casefold()
        if any(p.casefold().startswith(prefix) for p in reserved):
            raise Conflict('This Skill name belongs to platform or definition resources.')
        if previous is None and (local is not None or operation == 'update'):
            raise Conflict('This Skill is not installed from Workspace skills/; do not replace another source.')
        if previous is not None:
            if local != previous['files']:
                raise Conflict('Locally modified Skill; preserve or reconcile changes before updating.')
            if info['files'] == previous['files']:
                return {'name': name, 'state': 'unchanged', 'source_revision': previous['revision'],
                        'model_reloaded': False, 'shared_snapshot_saved': False}
            if operation != 'update':
                raise Conflict('Skill already installed; use the explicit update operation.')
        stage = root / '.aw-local/skill-install'
        for path, content in data.items():
            write_bytes(inside(stage / 'new', path), content)
        after = {**sources, name: info}
        write_json(stage / 'operation.json', {'name': name, 'before': sources, 'after': after, 'old_files': local})
        target.parent.mkdir(parents=True, exist_ok=True)
        if local is not None:
            target.rename(stage / 'old')
        (stage / 'new').rename(target)
        write_json(root / MANIFEST, after)
        shutil.rmtree(stage)
    return {'name': name, 'state': 'updated' if previous else 'installed', 'source_revision': info['revision'],
            'model_reloaded': False, 'shared_snapshot_saved': False}
