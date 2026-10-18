"""Worker registration and scoped instance material; Agent identity stays shared."""
import fnmatch
import os
from pathlib import Path
import re

from . import instance_worktrees, layout, model_profiles, software
from .util import (Conflict, Error, Uncertain, digest, encode, inside, local_asset_path, now,
                   locked, read_json, relpath, slug, uid, user_asset_path, write_bytes, write_json)


def agent_record(snapshot, agent_id):
    item = snapshot.json(layout.shared_path(snapshot, f'agents/{slug(agent_id)}.json'))
    if item is None:
        raise Error(f'Unknown agent {agent_id}.')
    return item


def enabled(snapshot, item):
    if item.get('worker_schema') != 1:
        return False
    if not layout.worker_support(snapshot):
        raise Error('Worker registration requires the Worker data version gate.')
    return True


def path(snapshot, agent_id, worker_id):
    return layout.shared_path(snapshot, f'workers/{slug(agent_id)}/{slug(worker_id)}.json')


def get(app, workspace, agent_id, worker_id=None, snapshot=None):
    snap = snapshot or app.store(workspace).snapshot()
    agent = agent_record(snap, agent_id)
    if not enabled(snap, agent):
        raise layout.MigrationRequired('Explicitly map this legacy Agent to a Worker before using Worker operations.')
    worker_id = slug(worker_id if worker_id is not None else agent['default_worker'])
    target = path(snap, agent_id, worker_id)
    item = snap.json(target)
    if not isinstance(item, dict) or item.get('id') != worker_id or item.get('agent') != agent_id:
        raise Error('Worker does not exist or belongs to a different Agent.')
    return {**item, 'revision': snap.entries[target]}


def list_workers(app, workspace, agent_id, archived=None, snapshot=None):
    snap = snapshot or app.store(workspace).snapshot()
    agent = agent_record(snap, agent_id)
    if not enabled(snap, agent):
        return []
    prefix = layout.shared_path(snap, f'workers/{agent_id}/')
    result = [get(app, workspace, agent_id, p[len(prefix):-5], snap) for p in snap.entries
              if p.startswith(prefix) and p.endswith('.json')]
    return [item for item in result if archived is None or item['archived'] == archived]


def record(agent_id, worker_id, name, description='', background='', references=None):
    if not name or not isinstance(name, str):
        raise Error('A Worker needs a display name and a description of its work.')
    return {'id': slug(worker_id), 'agent': slug(agent_id), 'name': name, 'description': description,
            'background': background, 'references': references or [], 'archived': False,
            'current': None, 'has_run': False, 'handoff': None, 'created_at': now()}


def create(app, workspace, agent_id, name, description='', worker_id=None, background='', references=None, binding=None, request_id=None):
    if not description:
        raise Error('Describe the work assigned to this Worker before creating it.')
    if request_id:
        slug(request_id)
        worker_id = worker_id or ('w' + digest(encode([workspace, agent_id, request_id]))[:24])
    if worker_id is None:
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', name):
            raise Error('Provide a stable Worker ID or request_id when creating a Worker.')
        worker_id = name
    worker_id = slug(worker_id)
    store = app.store(workspace)
    creation = {'request_id': request_id or worker_id, 'fingerprint': digest(encode({
        'name': name, 'description': description, 'background': background, 'references': references or []}))}
    locator = app.local()['workspaces'][workspace]['locator']
    operation = app.home / 'worker-creations' / digest(encode([locator, agent_id])) / f'{worker_id}.json'
    with locked(operation.with_suffix('.lock')):
        receipt = read_json(operation)
        if receipt and receipt['record']['creation'] != creation:
            raise Conflict('Worker creation already has a different original request.')
        item = receipt['record'] if receipt else {**record(agent_id, worker_id, name, description, background, references), 'creation': creation}
        for _ in range(4):
            snap = store.snapshot()
            agent = agent_record(snap, agent_id)
            if not enabled(snap, agent):
                raise layout.MigrationRequired('Explicitly enable Worker data before creating parallel Workers.')
            if agent['archived']:
                raise Conflict('Unarchive the Agent before creating a Worker.')
            if binding is not None:
                app.require_binding(workspace, agent_id, binding, snapshot=snap)
            target = path(snap, agent_id, worker_id)
            existing = snap.json(target)
            if existing:
                if existing.get('creation') != creation:
                    raise Conflict('Worker already exists or the original creation request differs.')
                return {**existing, 'starts_session': False}
            if receipt and receipt['phase'] == 'publishing':
                raise Uncertain(f'Original creation of Worker {agent_id}/{worker_id}, commit {receipt["commit"]}, is not confirmed; it was not repeated.')
            if receipt and receipt['phase'] == 'published':
                raise Conflict('The original Worker creation was published but its record is now missing; do not recreate it.')
            commit = store.commit(snap.revision, {target: encode(item)}, f'Create Worker {agent_id}/{worker_id}')
            receipt = {'record': item, 'commit': commit, 'phase': 'publishing'}
            write_json(operation, receipt)
            try:
                store.publish('main', commit, snap.revision)
            except Conflict:
                receipt['phase'] = 'rejected'
                write_json(operation, receipt)
                continue
            receipt['phase'] = 'published'
            write_json(operation, receipt)
            return {**item, 'starts_session': False}
        raise Conflict('Concurrent Worker registration exceeded the retry budget; no native session was created.')


def update(app, workspace, agent_id, worker_id, revision, *, name=None, description=None,
           background=None, references=None):
    store = app.store(workspace)
    snap = store.snapshot()
    item = get(app, workspace, agent_id, worker_id, snap)
    if item.pop('revision') != revision:
        raise Conflict('Worker changed; read its new revision before editing.')
    for key, value in (('name', name), ('description', description), ('background', background), ('references', references)):
        if value is not None:
            if key in ('name', 'description') and not value:
                raise Error('Worker name and description cannot be empty.')
            item[key] = value
    target = path(snap, agent_id, worker_id)
    store.change('main', {target: encode(item)}, layout.expected(snap, {target: revision}), 'Update Worker')
    return item


def set_default(app, workspace, agent_id, worker_id, revision):
    store = app.store(workspace)
    snap = store.snapshot()
    agent = agent_record(snap, agent_id)
    worker = get(app, workspace, agent_id, worker_id, snap)
    if agent['archived'] or worker['archived']:
        raise Conflict('An archived Agent or Worker cannot receive new messages.')
    ap = layout.shared_path(snap, f'agents/{agent_id}.json')
    if snap.entries[ap] != revision:
        raise Conflict('Agent changed; read its new revision before changing the default Worker.')
    agent['default_worker'] = worker_id
    store.change('main', {ap: encode(agent)}, layout.expected(snap, {ap: revision,
                 path(snap, agent_id, worker_id): worker['revision']}), 'Select default receiving Worker')
    return agent


def archive(app, workspace, agent_id, worker_id, archived=True):
    store = app.store(workspace)
    snap = store.snapshot()
    item = get(app, workspace, agent_id, worker_id, snap)
    revision = item.pop('revision')
    if item['current']:
        raise Conflict('Handoff this Worker before archiving; other Workers remain unchanged.')
    item['archived'] = archived
    target = path(snap, agent_id, worker_id)
    store.change('main', {target: encode(item)}, layout.expected(snap, {target: revision}), 'Archive Worker')
    return item


def legacy_worker(app, workspace, agent_id, kind, identifier, snapshot=None):
    if kind not in ('bindings', 'checkpoints', 'messages', 'local_operations'):
        raise Error('Unknown legacy Worker mapping category.')
    snap = snapshot or app.store(workspace).snapshot()
    mapping = snap.json(layout.shared_path(snap, f'worker-mappings/{slug(agent_id)}.json'), {})
    value = mapping.get(kind, {}).get(identifier)
    if value is None:
        raise Conflict('This legacy object has no explicit Worker mapping; do not guess from the current default.')
    return slug(value)


def binding_worker(app, workspace, agent_id, entry, snapshot):
    agent = agent_record(snapshot, agent_id)
    if not enabled(snapshot, agent):
        if entry.get('worker') is not None:
            raise Error('Worker Binding found without Worker version gating.')
        return None
    return entry.get('worker') or legacy_worker(app, workspace, agent_id, 'bindings', entry['id'], snapshot)


def execution_record(app, workspace, agent_id, snapshot, worker_id=None):
    agent = agent_record(snapshot, agent_id)
    if not enabled(snapshot, agent):
        if worker_id is not None:
            raise layout.MigrationRequired('This Agent has no explicitly mapped Worker.')
        return layout.shared_path(snapshot, f'agents/{agent_id}.json'), agent, None
    item = get(app, workspace, agent_id, worker_id, snapshot)
    item.pop('revision')
    return path(snapshot, agent_id, item['id']), item, item['id']


def checkpoint_index(snapshot, agent_id, checkpoint, worker_id=None):
    part = f'{worker_id}/' if worker_id is not None else ''
    return layout.shared_path(snapshot, f'checkpoints/{agent_id}/{part}{slug(checkpoint)}.json')


def prepare_context(app, workspace, agent_id, root, worker_id):
    if layout.version(root, 'instance') != layout.WORKER_VERSION:
        raise layout.MigrationRequired('This copy has not adopted the Worker data version.')
    context_path = layout.local_path(root, 'context.json', worker_id)
    with layout.lock(root, 'worker-context.lock'):
        context = read_json(context_path)
        if context is None:
            original = read_json(layout.local_path(root, 'context.json'))
            context = {**original, 'worker': worker_id}
        if context.get('worker') != worker_id or context.get('agent') != agent_id:
            raise Conflict('The local Worker context belongs to another execution scope.')
        if 'common_versions' not in context:
            base = app.store(workspace).snapshot(revision=context['revision'])
            context['common_versions'] = {p: sha for p, sha in base.entries.items()
                                          if not p.startswith(('workers/', '.agentworkspace/workers/'))}
            context['common_read_revision'] = base.revision
            write_json(context_path, context)
    return context


def selected_profile(root, worker_id):
    portable = layout.instance_path(root, 'config.json', worker_id)
    document = read_json(portable, {})
    if 'codex' not in document:
        return model_profiles.selected(root)
    return {**model_profiles.validate(document['codex']),
            'source': {'path': portable.relative_to(root).as_posix(), 'section': 'codex',
                       'sha256': digest(portable.read_bytes())}}


def owns(path, worker_id):
    return path.startswith((f'workers/{worker_id}/', f'.agentworkspace/workers/{worker_id}/'))


def shared_selection(root, paths):
    result = []
    excludes = read_json(layout.local_path(root, 'context.json'))['exclude']
    for path in paths or []:
        path = relpath(path)
        if path.startswith(('workers/', '.agentworkspace/workers/')) or any(c in path for c in '*?['):
            raise Error('Select exact common files, not Worker directories or patterns.')
        target = user_asset_path(root, path, write=False)
        if path.startswith('.agentworkspace/') and not (path in (
                '.agentworkspace/config.json', '.agentworkspace/source.json', '.agentworkspace/skill-sources.json',
                '.agentworkspace/software.json') or path.startswith('.agentworkspace/prompts/')):
            raise Error('Common selection cannot replace identity, checkpoints or other managed execution history.')
        if path == '.agentworkspace' or path.split('/')[0] in ('.aw',):
            raise Error('Select current common files, not legacy managed execution metadata.')
        resolved = target.resolve().relative_to(root.resolve()).as_posix()
        if resolved.startswith(('workers/', '.agentworkspace/workers/')):
            raise Error('A common path cannot alias another Worker material scope.')
        if any(fnmatch.fnmatch(part, pattern) or fnmatch.fnmatch(path, pattern)
               for part in Path(path).parts for pattern in excludes):
            raise Error('Local and excluded materials cannot be published as common files.')
        if target.is_dir():
            raise Error('Common material must be selected by explicit file paths.')
        if path not in result:
            result.append(path)
    return result


def collect(app, root, worker_id, shared_paths=None):
    """Walk only this Worker's directories; absent peer material is never a deletion."""
    context = read_json(layout.local_path(root, 'context.json', worker_id))
    if context is None:
        # Listing is read-only and must work before a Worker has ever been reserved.
        context = read_json(layout.local_path(root, 'context.json'))
    software.require_ready(root)
    if layout.local_path(root, 'skill-install/operation.json').exists():
        raise Conflict('Finish the shared Skill update before saving Worker materials.')
    excludes = context['exclude']
    content, skipped = {}, []
    for prefix in (f'workers/{worker_id}', f'.agentworkspace/workers/{worker_id}'):
        directory = inside(root, prefix)
        if directory.is_symlink():
            raise Error('Worker materials cannot follow symlinks.')
        if not directory.exists():
            continue
        for base, directories, names in os.walk(directory, followlinks=False):
            kept = []
            for name in directories:
                candidate = Path(base) / name
                relative = candidate.relative_to(root).as_posix()
                if local_asset_path(relative) or any(fnmatch.fnmatch(name, p) or fnmatch.fnmatch(relative, p) for p in excludes) or (candidate / '.git').exists():
                    skipped.append(relative + '/')
                elif candidate.is_symlink():
                    raise Error('Worker materials need an explicit symlink export.')
                else:
                    kept.append(name)
            directories[:] = kept
            for name in names:
                candidate = Path(base) / name
                relative = candidate.relative_to(root).as_posix()
                if name == '.git' or local_asset_path(relative) or name.startswith('.aw-tmp-') or any(fnmatch.fnmatch(name, p) or fnmatch.fnmatch(relative, p) for p in excludes):
                    skipped.append(relative)
                    continue
                if candidate.is_symlink() or candidate.stat().st_size > 50 * 1024 * 1024:
                    raise Error('Worker assets must be regular files at most 50 MiB.')
                content[relative] = candidate.read_bytes()
    for path in shared_selection(root, shared_paths):
        target = inside(root, path)
        if target.exists():
            if target.is_symlink() or target.stat().st_size > 50 * 1024 * 1024:
                raise Error('Common assets must be regular files at most 50 MiB.')
            content[path] = target.read_bytes()
    return content, skipped


def context_hashes(store, previous_context, snapshot):
    """Carry unchanged saved digests without reading every peer blob on each save."""
    previous = store.snapshot(revision=previous_context['revision'])
    return {p: previous_context['saved'][p] if previous.entries.get(p) == sha and p in previous_context['saved']
            else digest(snapshot.bytes(p)) for p, sha in snapshot.entries.items()}


def read_legacy_checkpoint_operation(app, workspace, agent_id, worker_id, point, summary, content, pointer):
    """Old receipts did not record registration outcome; inspect but never replay it."""
    store = app.store(workspace)
    snap = store.snapshot()
    if app.legacy_worker(workspace, agent_id, 'checkpoints', point, snap) != worker_id:
        raise Conflict('The original checkpoint operation belongs to another Worker.')
    if pointer.get('id') != point or pointer.get('agent') != agent_id or not pointer.get('revision'):
        raise Error('Legacy checkpoint receipt does not identify the selected original operation.')
    original = store.snapshot(revision=pointer['revision'])
    if pointer.get('path') != layout.instance_relpath(original, f'checkpoints/{point}.json'):
        raise Error('Legacy checkpoint receipt has a different original material path.')
    record = original.json(pointer['path'])
    identity = original.json(layout.instance_relpath(original, 'identity.json'))
    if (not isinstance(identity, dict) or identity.get('agent') != agent_id or
            identity.get('workspace') != app.local()['workspaces'][workspace]['locator']):
        raise Error('Original checkpoint materials belong to another Agent or Workspace.')
    if not isinstance(record, dict) or record.get('id') != point or (record.get('summary'), record.get('content')) != (summary, content):
        raise Conflict('The original checkpoint content differs; it cannot be rewritten as a Worker checkpoint.')
    index = checkpoint_index(snap, agent_id, point)
    found = snap.bytes(index)
    if found is not None:
        if found != encode(pointer):
            raise Conflict('Original checkpoint registration has different bytes.')
        return pointer
    raise Uncertain('This legacy checkpoint receipt does not prove whether registration was attempted; inspect the original publication before continuing. It was not replayed.')


def save_files(app, workspace, agent_id, root, worker_id, extra=None, message='Save Worker assets',
               shared_paths=None, before_publish=None):
    context = prepare_context(app, workspace, agent_id, root, worker_id)
    content, skipped = collect(app, root, worker_id, shared_paths)
    selected = set(shared_selection(root, shared_paths))
    if any(not owns(p, worker_id) for p in extra or {}):
        raise Error('Generated Worker metadata must stay in this Worker scope.')
    content.update(extra or {})
    branch = app.agent(workspace, agent_id, worker_id=worker_id)['branch']
    repository = instance_worktrees.repository(root, app.local()['workspaces'][workspace]['address'], app.home, branch)
    store = repository or app.store(workspace)
    base = store.snapshot(revision=context['revision'])
    app._check_tracked_local(base)
    scope = {p for p in base.entries if owns(p, worker_id)} | selected | set(content)
    changes = {p: content.get(p) for p in scope if p not in selected and base.bytes(p) != content.get(p)}
    expected = {p: base.entries.get(p) for p in changes}
    for path in selected:
        sha = context['common_versions'].get(path)
        previous_bytes = store.blob(sha) if sha is not None else None
        if previous_bytes != content.get(path):
            changes[path] = content.get(path)
        expected[path] = sha
    before = instance_worktrees.head(root) if repository else None
    if repository:
        instance_worktrees.check_index(root, scope)
    for _ in range(4):
        latest = store.snapshot(branch)
        if layout.version(latest, 'instance') != layout.WORKER_VERSION:
            raise layout.MigrationRequired('Worker material publication needs the Worker version gate.')
        if repository and before != latest.revision and not store.contains_commit(before, latest.revision):
            raise Conflict('Local commits contain unselected material; preserve them and resolve Git history before a Worker save.')
        for path, sha in expected.items():
            if latest.entries.get(path) != sha:
                raise Conflict(f'Worker or selected common file changed: {path}. Read its new revision first.')
        commit = store.commit(latest.revision, changes, message) if changes else latest.revision
        if repository and before != commit:
            if instance_worktrees.head(root) != before:
                raise Conflict('The local Git branch changed before the Worker publication.')
            # Check the index merge before publishing; this does not change index or working bytes.
            instance_worktrees.git(root, 'read-tree', '-i', '-m', '-n', before, commit)
        if before_publish:
            before_publish(commit, skipped, sorted(content))
        try:
            if changes:
                store.publish(branch, commit, latest.revision)
        except Conflict:
            continue
        break
    else:
        raise Conflict('Concurrent Worker saves exceeded the retry budget; no business operation was repeated.')
    try:
        for path, data in (extra or {}).items():
            write_bytes(inside(root, path), data)
        if repository:
            instance_worktrees.record_scoped_saved(root, branch, before, commit)
    except (Error, OSError) as exc:
        raise Uncertain(f'Worker commit {commit} was published, but local finalization failed; inspect the original checkpoint receipt. {exc}') from exc
    saved = store.snapshot(revision=commit)
    common = read_json(layout.local_path(root, 'context.json'))
    context.update(revision=commit, saved=context_hashes(store, common, saved))
    for path in selected:
        if path in saved.entries:
            context['common_versions'][path] = saved.entries[path]
        else:
            context['common_versions'].pop(path, None)
    write_json(layout.local_path(root, 'context.json', worker_id), context)
    # The common context tracks the actual checkout, never another Worker's read versions.
    common.update(revision=commit, saved=context['saved'])
    write_json(layout.local_path(root, 'context.json'), common)
    return commit, skipped


def checkpoint(app, workspace, agent_id, summary, content='', binding=None, directory=None,
               checkpoint_id=None, references=None, worker_id=None, shared_paths=None):
    store = app.store(workspace)
    snap = store.snapshot()
    item = app.agent(workspace, agent_id, snap, worker_id=worker_id)
    entry = None
    if item['current'] or binding:
        item, entry = app.require_binding(workspace, agent_id, binding, allow_stopping=True, snapshot=snap, worker_id=worker_id)
    worker_id = item['worker_id']
    root = Path(app.prepare_agent_directory(workspace, agent_id, directory)['directory'])
    point = slug(checkpoint_id or uid('c'))
    index = checkpoint_index(snap, agent_id, point, worker_id)
    selected_common = sorted(shared_selection(root, shared_paths))
    found = snap.json(index)
    if found is None:
        legacy = snap.json(checkpoint_index(snap, agent_id, point))
        if legacy is not None and app.legacy_worker(workspace, agent_id, 'checkpoints', point, snap) == worker_id:
            found = legacy
    if found:
        previous = app._read_checkpoint(store, snap, agent_id, point, worker_id)
        if ((previous['record']['summary'], previous['record']['content']) != (summary, content)
                or previous['record'].get('shared_paths', []) != selected_common
                or (references is not None and previous['record']['record_refs'] != references)):
            raise Conflict('Checkpoint ID is immutable and already has different content.')
        return found
    with layout.lock(root, 'files.lock'):
        context = prepare_context(app, workspace, agent_id, root, worker_id)
        receipt_path = layout.local_path(root, f'checkpoint-operations/{point}.json', worker_id)
        receipt = read_json(receipt_path)
        if receipt and 'record' not in receipt:
            if selected_common:
                raise Conflict('The old checkpoint selection is immutable; save new common changes under a new checkpoint ID.')
            return read_legacy_checkpoint_operation(app, workspace, agent_id, worker_id, point, summary, content, receipt)
        if receipt:
            record = receipt['record']
            if ((record['summary'], record['content']) != (summary, content)
                    or record.get('shared_paths', []) != selected_common or record['record_refs'] != (references or [])):
                raise Conflict('The original checkpoint has different content.')
            pointer = receipt['pointer']
            repository = instance_worktrees.repository(root, app.local()['workspaces'][workspace]['address'], app.home, item['branch'])
            original_store = repository or store
            try:
                actual = original_store.head(item['branch'])
                confirmed = actual and original_store.contains_commit(pointer['revision'], actual)
            except (Error, OSError) as exc:
                raise Uncertain(f'Could not confirm the original Worker checkpoint commit: {exc}') from exc
            if not confirmed:
                raise Uncertain('The original Worker checkpoint commit is not confirmed; it was not published again.')
            saved = store.snapshot(revision=pointer['revision']).bytes(pointer['path'])
            if saved != encode(record):
                raise Conflict('The original checkpoint bytes do not match its publication receipt.')
            if not receipt.get('local_finalized'):
                target = root / pointer['path']
                if target.exists() and target.read_bytes() != saved:
                    raise Conflict('The local checkpoint differs from the original published record.')
                write_bytes(target, saved)
                repository = instance_worktrees.repository(root, app.local()['workspaces'][workspace]['address'], app.home, item['branch'])
                if repository:
                    repository.snapshot(revision=pointer['revision'])
                    head = instance_worktrees.head(root)
                    if head == receipt['before_head']:
                        instance_worktrees.record_scoped_saved(root, item['branch'], head, pointer['revision'])
                    elif not repository.contains_commit(pointer['revision'], head):
                        raise Conflict('The checkpoint was published but the checkout moved independently; preserve both versions.')
                published = store.snapshot(revision=pointer['revision'])
                context.update(revision=published.revision, saved=context_hashes(store, context, published))
                for path in record['shared_paths']:
                    if path in published.entries:
                        context['common_versions'][path] = published.entries[path]
                    else:
                        context['common_versions'].pop(path, None)
                write_json(layout.local_path(root, 'context.json', worker_id), context)
                receipt['local_finalized'] = True
                write_json(receipt_path, receipt)
            if receipt.get('registration_unknown'):
                raise Uncertain('The original checkpoint registration is not confirmed; inspect its original result.')
        else:
            base = store.snapshot(revision=context['revision'])
            common_versions = dict(context['common_versions'])
            record = {'id': point, 'worker': worker_id, 'created_at': now(), 'summary': summary, 'content': content,
                      'origin': {'workspace': workspace, 'workspace_locator': context['locator'], 'agent': agent_id,
                                 'worker': worker_id, 'instance_branch': item['branch'], 'instance_root': str(root),
                                 'instructions_file': str(root / 'AGENTS.md'), 'binding': entry['id'] if entry else None,
                                 'session': entry['session'] if entry else None, 'runtime_kind': entry['kind'] if entry else None,
                                 'native_cwd': entry.get('execution', {}).get('cwd') if entry else None},
                      'common_revision': context['common_read_revision'], 'common_versions': common_versions,
                      'shared_paths': selected_common,
                      'record_refs': references or [], 'scope': 'Worker files and explicitly selected common paths only.'}
            point_path = layout.instance_relpath(root, f'checkpoints/{point}.json', worker_id)
            if (root / point_path).exists():
                raise Conflict('Checkpoint file exists without its original receipt; inspect it before continuing.')
            def before_publish(revision, skipped, material_paths):
                nonlocal pointer, receipt
                if binding:
                    app.require_binding(workspace, agent_id, binding, allow_stopping=True, worker_id=worker_id)
                pointer = {'id': point, 'agent': agent_id, 'worker': worker_id, 'revision': revision,
                           'path': point_path, 'created_at': record['created_at'], 'excluded': skipped,
                           'material_paths': material_paths, 'common_revision': context['common_read_revision']}
                receipt = {'pointer': pointer, 'record': record, 'registration_unknown': False,
                           'before_head': instance_worktrees.head(root) if (root / '.git').exists() else None,
                           'local_finalized': False}
                write_json(receipt_path, receipt)
            save_files(app, workspace, agent_id, root, worker_id, {point_path: encode(record)},
                       f'Checkpoint Worker {worker_id}/{point}', shared_paths, before_publish)
            receipt['local_finalized'] = True
            write_json(receipt_path, receipt)
        receipt['registration_unknown'] = True
        write_json(receipt_path, receipt)
        # Registration cannot borrow another Worker's execution rights.
        current = store.snapshot()
        if binding:
            app.require_binding(workspace, agent_id, binding, allow_stopping=True, snapshot=current, worker_id=worker_id)
        owner_path, _, _ = execution_record(app, workspace, agent_id, current, worker_id)
        try:
            store.change('main', {index: encode(pointer)}, layout.expected(current, {
                index: None, owner_path: current.entries[owner_path],
                **({layout.shared_path(current, f'bindings/{binding}.json'): current.entries[layout.shared_path(current, f'bindings/{binding}.json')]} if binding else {})}),
                f'Register Worker checkpoint {point}')
        except Conflict:
            receipt['registration_unknown'] = False
            write_json(receipt_path, receipt)
            raise
        receipt['registration_unknown'] = False
        write_json(receipt_path, receipt)
        return pointer


def sync(app, workspace, agent_id, root, worker_id, shared_paths=None):
    with layout.lock(root, 'files.lock'):
        context = prepare_context(app, workspace, agent_id, root, worker_id)
        content, _ = collect(app, root, worker_id, shared_paths)
        branch = app.agent(workspace, agent_id, worker_id=worker_id)['branch']
        repository = instance_worktrees.repository(root, app.local()['workspaces'][workspace]['address'], app.home, branch)
        store = repository or app.store(workspace)
        previous = store.snapshot(revision=context['revision'])
        latest = store.snapshot(branch)
        if layout.version(latest, 'instance') != layout.WORKER_VERSION:
            raise layout.MigrationRequired('The remote instance has not adopted the Worker version gate.')
        scope = {p for p in set(previous.entries) | set(latest.entries) if owns(p, worker_id)}
        scope.update(shared_selection(root, shared_paths))
        updates = {}
        selected = set(shared_selection(root, shared_paths))
        for path in scope:
            sha = context['common_versions'].get(path) if path in selected else previous.entries.get(path)
            before = store.blob(sha) if sha is not None else None
            actual = content.get(path)
            desired = latest.bytes(path)
            if actual != before and desired != before and actual != desired:
                raise Conflict(f'Worker sync overlaps local and remote edits: {path}; no files were changed.')
            if desired != before:
                updates[path] = desired
        if repository:
            before_head = instance_worktrees.head(root)
            if before_head != latest.revision and not store.contains_commit(before_head, latest.revision):
                raise Conflict('Local Git commits must be resolved without publishing other Worker material.')
            instance_worktrees.check_index(root, scope)
            instance_worktrees.record_scoped_saved(root, branch, before_head, latest.revision)
        for path, data in updates.items():
            target = inside(root, path)
            if data is None:
                if target.exists():
                    target.unlink()
            else:
                write_bytes(target, data)
        common = read_json(layout.local_path(root, 'context.json'))
        context.update(revision=latest.revision, saved=context_hashes(store, common, latest))
        for path in selected:
            if path in latest.entries:
                context['common_versions'][path] = latest.entries[path]
            else:
                context['common_versions'].pop(path, None)
        write_json(layout.local_path(root, 'context.json', worker_id), context)
        common.update(revision=latest.revision, saved=context['saved'])
        write_json(layout.local_path(root, 'context.json'), common)
        return {'worker': worker_id, 'revision': latest.revision, 'directory': str(root), 'updated_paths': sorted(updates)}
