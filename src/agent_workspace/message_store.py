"""Separate permission and message snapshots; never combine their revisions."""
from dataclasses import dataclass

from . import layout
from .util import Conflict, Error


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
            messages.json(layout.MARKER).get('role') != 'messages'):
        raise Error('The dedicated message branch is missing or has a different layout.')
    guard = messages.json(layout.MESSAGE_GUARD)
    if not isinstance(guard, dict) or not guard.get('main_revision'):
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
        return store.change('main', changes, {**permission_expected, **expected}, message)
    allowed = tuple(layout.shared_path(state.messages, root + '/') for root in layout.MESSAGE_ROOTS)
    if any(not path.startswith(allowed) for path in changes):
        raise Error('Message writes may change only Message, ACK, index and dispatch records.')
    return store.change(layout.MESSAGE_BRANCH, changes,
                        {**expected, layout.MARKER: state.messages.entries[layout.MARKER],
                         layout.MESSAGE_GUARD: state.messages.entries[layout.MESSAGE_GUARD]}, message)
