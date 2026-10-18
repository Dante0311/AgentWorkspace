"""Separate permission and message snapshots; never combine their revisions."""
from dataclasses import dataclass
import re

from . import layout
from .util import Conflict, Error, Uncertain, digest, encode, locked, read_json, slug, uid, write_json


@dataclass(frozen=True)
class MessageState:
    main: object
    messages: object
    branch: str


def read(store):
    # This order is required: a later permission change invalidates the old guard.
    messages = store.snapshot(layout.MESSAGE_BRANCH)
    main = store.snapshot('main')
    if layout.version(main, 'workspace') != layout.MESSAGE_VERSION:
        return MessageState(main, main, 'main')
    document = main.json(layout.MARKER)
    if document.get('messages_branch') != layout.MESSAGE_BRANCH or document.get('role') == 'messages':
        raise Error('The main message layout does not identify its message branch.')
    if (layout.version(messages, 'workspace') != layout.MESSAGE_VERSION or
            messages.json(layout.MARKER).get('role') != 'messages' or
            messages.json(layout.MARKER)['platform_prefix'] != document['platform_prefix']):
        raise Error('The dedicated message branch is missing or has a different layout.')
    guard = messages.json(layout.MESSAGE_GUARD)
    if (not isinstance(guard, dict) or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', guard.get('main_revision', ''))
            or not guard.get('nonce')):
        raise Error('The message permission marker is missing.')
    if not store.contains_commit(guard['main_revision'], main.revision):
        raise Conflict('The main read does not include the sampled message permission version; reread both snapshots.')
    return MessageState(main, messages, layout.MESSAGE_BRANCH)


def change(store, state, changes, expected, message, *, permission_expected=None):
    permission_expected = permission_expected or {}
    for path, revision in permission_expected.items():
        if state.main.entries.get(path) != revision:
            raise Conflict(f'Permission snapshot differs at {path}.')
    if state.branch == 'main':
        return store.change('main', changes, {**permission_expected, **expected,
                                            layout.MARKER: state.main.entries.get(layout.MARKER)}, message)
    if any(not permission_path(state.main, path) for path in permission_expected):
        raise Error('Message permission conditions must name guarded main qualification or routing records.')
    allowed = tuple(layout.shared_path(state.messages, root + '/') for root in layout.MESSAGE_ROOTS)
    if any(not path.startswith(allowed) for path in changes):
        raise Error('Message writes may change only Message, ACK, index and dispatch records.')
    return store.change(layout.MESSAGE_BRANCH, changes,
                        {**expected, layout.MARKER: state.messages.entries[layout.MARKER],
                         layout.MESSAGE_GUARD: state.messages.entries[layout.MESSAGE_GUARD]}, message)


def permission_path(snapshot, path):
    if path == layout.MARKER:
        return True
    prefix = snapshot.json(layout.MARKER)['platform_prefix']
    if prefix:
        if not path.startswith(prefix + '/'):
            return False
        path = path[len(prefix) + 1:]
    return path == 'workspace.json' or path.split('/')[0] in (
        'agents', 'workers', 'bindings', 'sessions', 'handoffs', 'worker-mappings', 'maintenance')


def publish_permissions(store, commit, expected):
    before = store.snapshot(revision=expected)
    after = store.snapshot(revision=commit)
    old_version = layout.version(before, 'workspace')
    new_version = layout.version(after, 'workspace')
    if old_version != layout.MESSAGE_VERSION:
        if new_version == layout.MESSAGE_VERSION:
            raise Error('Enable the message branch through the explicit atomic migration.')
        return False
    changed = {p for p in before.entries.keys() | after.entries.keys() if before.entries.get(p) != after.entries.get(p)}
    if not any(permission_path(before, path) for path in changed):
        return False
    path = store.operations / 'permissions' / (commit + '.json')
    with locked(path.with_suffix('.lock')):
        receipt = read_json(path, {'attempts': [], 'phase': 'rejected'})
        if receipt['phase'] != 'rejected':
            if store.publication_status(receipt['attempts'][-1]):
                return True
            raise Uncertain('The original permission publication is not confirmed; it was not repeated.')
        state = read(store)
        if state.main.revision != expected:
            raise Conflict('Main changed before its permission publication; reread the original preconditions.')
        guard = store.commit(state.messages.revision,
                             {layout.MESSAGE_GUARD: encode({'main_revision': commit, 'nonce': uid('p')})},
                             'Advance message permission version')
        updates = {'main': {'before': expected, 'after': commit},
                   layout.MESSAGE_BRANCH: {'before': state.messages.revision, 'after': guard}}
        receipt['attempts'].append(updates)
        receipt['phase'] = 'publishing'
        write_json(path, receipt)
        try:
            store.publish_atomic(updates)
        except Conflict:
            receipt['phase'] = 'rejected'
            write_json(path, receipt)
            raise
        except Uncertain:
            raise
        except Error:
            receipt['phase'] = 'rejected'
            write_json(path, receipt)
            raise
        receipt['phase'] = 'published'
        write_json(path, receipt)
        return True


def initial_files(worker_support=True):
    return layout.marker('workspace', version=layout.MESSAGE_VERSION, platform_prefix='.agentworkspace',
                         worker_support=worker_support, messages_branch=layout.MESSAGE_BRANCH)


def initialize(store, metadata, worker_support=True, *, parent='', shared_files=None):
    changes = {**(shared_files or {}), layout.MARKER: initial_files(worker_support),
               'workspace.json': None, '.agentworkspace/workspace.json': encode(metadata)}
    request = digest(encode({'parent': parent, 'files': {p: digest(raw) if raw is not None else None
                                                       for p, raw in changes.items()}}))
    path = store.operations / 'initialization.json'
    with locked(path.with_suffix('.lock')):
        receipt = read_json(path)
        if receipt and receipt['request'] != request:
            raise Conflict('Another Workspace initialization already owns this address; preserve its original publication.')
        if receipt is None:
            main = store.commit(parent, changes, 'Initialize independent message layout')
            marker = layout.marker('workspace', version=layout.MESSAGE_VERSION, role='messages', platform_prefix='.agentworkspace')
            messages = store.commit('', {layout.MARKER: marker,
                layout.MESSAGE_GUARD: encode({'main_revision': main, 'nonce': uid('p')})}, 'Initialize message branch')
            receipt = {'request': request, 'phase': 'prepared', 'updates': {
                'main': {'before': parent, 'after': main}, layout.MESSAGE_BRANCH: {'before': '', 'after': messages}}}
            write_json(path, receipt)
        if receipt['phase'] != 'prepared':
            if store.publication_status(receipt['updates']):
                return receipt['updates']
            if receipt['phase'] == 'rejected':
                raise Conflict('The original initialization was rejected; inspect its original ref preconditions.')
            raise Uncertain('The original initialization is not confirmed; it was not repeated.')
        receipt['phase'] = 'publishing'
        write_json(path, receipt)
        try:
            store.publish_atomic(receipt['updates'])
        except Uncertain:
            raise
        except Error:
            receipt['phase'] = 'rejected'
            write_json(path, receipt)
            raise
        receipt['phase'] = 'published'
        write_json(path, receipt)
        return receipt['updates']


def plan(store):
    snap = store.snapshot()
    current = layout.version(snap, 'workspace')
    if current == layout.MESSAGE_VERSION:
        state = read(store)
        return {'enabled': True, 'main_revision': state.main.revision, 'message_revision': state.messages.revision,
                'branch': state.branch, 'worker_support': layout.worker_support(state.main)}
    paths = message_paths(snap)
    return {'enabled': False, 'main_revision': snap.revision, 'source_layout': current,
            'branch': layout.MESSAGE_BRANCH, 'message_paths': sorted(paths),
            'compatible_writers': ['message-v3'], 'starts_session': False}


def message_paths(snapshot):
    prefixes = tuple(layout.shared_path(snapshot, root + '/') for root in layout.MESSAGE_ROOTS)
    return [path for path in snapshot.entries if path.startswith(prefixes)]


def migrate(app, workspace, request_id, *, compatible_writers=None):
    if compatible_writers != ['message-v3']:
        raise Error('Confirm all writers use the message version gate with compatible_writers=["message-v3"].')
    request_id = slug(request_id)
    store = app.store(workspace)
    path = store.operations / 'migrations' / (request_id + '.json')
    with locked(store.operations / 'message-migration.lock'):
        for other_path in (store.operations / 'migrations').glob('*.json'):
            if other_path == path:
                continue
            previous = read_json(other_path)
            if previous['phase'] == 'prepared':
                raise Conflict(f"Resume the original prepared migration {previous['request_id']}; a new ID cannot replace it.")
            if previous['phase'] == 'publishing':
                if not store.publication_status(previous['updates']):
                    raise Uncertain(f"Inspect the original migration {previous['request_id']}; a new ID cannot repeat its unknown publication.")
                previous['phase'] = 'published'
                write_json(other_path, previous)
        receipt = read_json(path)
        if receipt is None:
            snap = store.snapshot()
            current = layout.version(snap, 'workspace')
            if current == layout.MESSAGE_VERSION:
                raise Conflict('This Workspace already has a message branch; no migration was repeated.')
            if store.head(layout.MESSAGE_BRANCH):
                raise Conflict('The reserved message branch already exists; inspect it without overwriting it.')
            prefix = '.agentworkspace' if current else ''
            paths = message_paths(snap)
            # Preserve every original blob and every non-message record in place.
            changes = {p: None for p in paths}
            changes[layout.MARKER] = layout.marker('workspace', version=layout.MESSAGE_VERSION,
                platform_prefix=prefix, worker_support=current == layout.WORKER_VERSION,
                messages_branch=layout.MESSAGE_BRANCH, message_migration=request_id)
            main = store.commit(snap.revision, changes, 'Move message records to their independent branch')
            content = {p: snap.bytes(p) for p in paths}
            content[layout.MARKER] = layout.marker('workspace', version=layout.MESSAGE_VERSION,
                                                 role='messages', platform_prefix=prefix)
            content[layout.MESSAGE_GUARD] = encode({'main_revision': main, 'nonce': uid('p')})
            messages = store.commit('', content, 'Preserve original message records')
            receipt = {'request_id': request_id, 'phase': 'prepared', 'source_layout': current,
                       'updates': {'main': {'before': snap.revision, 'after': main},
                                   layout.MESSAGE_BRANCH: {'before': '', 'after': messages}}}
            write_json(path, receipt)
        if receipt['phase'] == 'rejected':
            raise Conflict('The original atomic migration was rejected; inspect its preconditions and use a new explicit request.')
        if receipt['phase'] != 'prepared':
            if store.publication_status(receipt['updates']):
                receipt['phase'] = 'published'
                write_json(path, receipt)
            else:
                raise Uncertain('The original message migration is not confirmed; it was not repeated.')
        else:
            receipt['phase'] = 'publishing'
            write_json(path, receipt)
            try:
                store.publish_atomic(receipt['updates'])
            except Conflict:
                receipt['phase'] = 'rejected'
                write_json(path, receipt)
                raise
            except Uncertain:
                raise
            except Error:
                receipt['phase'] = 'rejected'
                write_json(path, receipt)
                raise
            receipt['phase'] = 'published'
            write_json(path, receipt)
        return {'state': receipt['phase'], 'request_id': request_id, 'source_layout': receipt['source_layout'],
                'main_revision': receipt['updates']['main']['after'],
                'message_revision': receipt['updates'][layout.MESSAGE_BRANCH]['after'],
                'branch': layout.MESSAGE_BRANCH, 'starts_session': False, 'protocol_bytes_preserved': True}
