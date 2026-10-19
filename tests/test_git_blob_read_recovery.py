"""Local object failure recovery uses real objects; native peers are protocol fixtures."""
import json
import subprocess

import pytest

from agent_workspace import gitstore, layout, runtime
from agent_workspace.gitstore import GitStore, Snapshot
from agent_workspace.util import Error, RetryableRead, read_json, write_bytes, write_json
from test_runtime_recovery import desktop_owner, fast_wait


@pytest.fixture
def store(tmp_path):
    remote = tmp_path / 'remote.git'
    GitStore.initialize(remote)
    return GitStore(str(remote), tmp_path / 'home')


def put_blob(store, data):
    return store.git('hash-object', '-w', '--stdin', data=data).stdout.decode().strip()


def fail_once(monkeypatch, sha, *, code=1, stdout=b'', stderr=b''):
    run = gitstore.run
    observed = []
    def fault(args, **kwargs):
        if args[-3:] == ['cat-file', 'blob', sha]:
            observed.append(sha)
            if len(observed) == 1:
                return subprocess.CompletedProcess(args, code, stdout, stderr)
        return run(args, **kwargs)
    monkeypatch.setattr(gitstore, 'run', fault)
    return observed


def test_empty_failed_process_retries_only_after_same_object_is_verified(store, monkeypatch):
    data = b'{"id":"original-index"}\n'
    sha = put_blob(store, data)
    observed = fail_once(monkeypatch, sha)
    snap = Snapshot(store, 'fixed-object-fixture', {'index.json': sha})
    with pytest.raises(RetryableRead) as error:
        snap.json('index.json')
    assert sha in str(error.value) and len(observed) == 2
    assert snap.json('index.json') == {'id': 'original-index'}
    assert len(observed) == 3


@pytest.mark.parametrize('damage', ['missing', 'corrupt'])
def test_real_bad_objects_remain_errors_including_after_blank_first_failure(store, monkeypatch, tmp_path, damage):
    sha = put_blob(store, b'isolated object')
    path = store.root / 'objects' / sha[:2] / sha[2:]
    assert path.resolve().is_relative_to(tmp_path.resolve())
    path.chmod(0o600)
    if damage == 'missing':
        path.unlink()
    else:
        write_bytes(path, b'Not a compressed Git object')
    # A real failure and an empty first process failure must both preserve the bad object error.
    with pytest.raises(Error) as error:
        store.blob(sha)
    assert not isinstance(error.value, RetryableRead)
    with monkeypatch.context() as fault:
        fail_once(fault, sha)
        with pytest.raises(Error) as error:
            store.blob(sha)
        assert not isinstance(error.value, RetryableRead) and sha in str(error.value)


def test_recheck_must_validate_content_hash(store, monkeypatch):
    sha = put_blob(store, b'original bytes')
    run = gitstore.run; observed = []
    def fault(args, **kwargs):
        if args[-3:] == ['cat-file', 'blob', sha]:
            observed.append(sha)
            return subprocess.CompletedProcess(args, 1, b'', b'') if len(observed) == 1 else subprocess.CompletedProcess(args, 0, b'wrong bytes', b'')
        return run(args, **kwargs)
    monkeypatch.setattr(gitstore, 'run', fault)
    with pytest.raises(Error) as error:
        store.blob(sha)
    assert not isinstance(error.value, RetryableRead) and sha in str(error.value)


def test_two_empty_failures_do_not_claim_object_is_healthy(store, monkeypatch):
    sha = put_blob(store, b'original bytes')
    run = gitstore.run; observed = []
    def fault(args, **kwargs):
        if args[-3:] == ['cat-file', 'blob', sha]:
            observed.append(sha)
            return subprocess.CompletedProcess(args, 1, b'', b'')
        return run(args, **kwargs)
    monkeypatch.setattr(gitstore, 'run', fault)
    with pytest.raises(Error) as error:
        store.blob(sha)
    assert not isinstance(error.value, RetryableRead) and len(observed) == 2


@pytest.mark.parametrize('code,stdout,stderr', [(1, b'', b'fatal: unknown local object error'),
                                              (1, b'partial object', b''), (128, b'', b'')])
def test_other_blob_failures_do_not_gain_retries(store, monkeypatch, code, stdout, stderr):
    sha = put_blob(store, b'original bytes')
    observed = fail_once(monkeypatch, sha, code=code, stdout=stdout, stderr=stderr)
    with pytest.raises(Error) as error:
        store.blob(sha)
    assert not isinstance(error.value, RetryableRead) and len(observed) == 1


def test_malformed_json_remains_a_format_error_after_verified_read(store, monkeypatch):
    sha = put_blob(store, b'Not JSON')
    fail_once(monkeypatch, sha)
    snap = Snapshot(store, 'fixed-object-fixture', {'index.json': sha})
    with pytest.raises(RetryableRead):
        snap.json('index.json')
    with pytest.raises(json.JSONDecodeError):
        snap.json('index.json')


def test_watch_blob_failure_keeps_session_binding_and_single_input(desktop_owner, monkeypatch):
    app, root, binding, native = desktop_owner
    app.create('sea', 'bob')
    sender = app.reserve('sea', 'bob')['binding']
    app.bind('sea', 'bob', sender, 'sender-chat')
    runtime.Messages(app).send('sea', 'bob', sender, 'alice', 'explicit message fixture', request_id='original-message')
    state = app.store('sea').message_snapshot()
    sha = state.messages.entries[layout.shared_path(state.messages, 'message-index/original-message.json')]
    runtime.queue_input(app, 'sea', 'alice', 'one model input', request_id='one-input')
    write_json(layout.local_path(root, 'watch.json'), {'enabled': True, 'binding': binding, 'interval': .5})
    runner = runtime.Runner(app, 'sea', 'alice')
    delays = fast_wait(runner, monkeypatch)
    observed = fail_once(monkeypatch, sha)
    def notified():
        if len(native['sent']) == 2:
            runner.stop_event.set()
    native['on_notify'] = notified
    runner.run()
    assert len(observed) >= 3 and 2 in delays
    assert native['attached'] == ['original-chat'] and len(native['sent']) == 2
    assert 'one-input' in native['sent'][0][1] and 'original-message' in native['sent'][1][1]
    assert app.agent('sea', 'alice')['current'] == binding
    assert read_json(layout.local_path(root, 'inputs/one-input.json'))['state'] == 'submitted'
    snap = app.store('sea').snapshot()
    assert snap.json(layout.shared_path(snap, 'dispatch/alice.json'))['attempts'] == 1
