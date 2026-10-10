"""Fault classification and one publication against an isolated real Git repo."""
import errno
import functools
import os
import ssl
import subprocess
import urllib.error

import pytest

from agent_workspace import gitstore
from agent_workspace.gitstore import GitHubStore, GitStore
from agent_workspace.util import Error, Conflict, LockBusy, RetryableRead, Uncertain, command_detail, locked


@pytest.fixture
def store(tmp_path):
    remote = tmp_path / "remote.git"
    GitStore.initialize(remote)
    return GitStore(str(remote), tmp_path / "home")


@pytest.mark.parametrize("command", ["ls-remote", "fetch"])
@pytest.mark.parametrize("detail", [b"Could not resolve host: fixture.invalid", b"Connection reset by peer",
                                   b"The requested URL returned error: 503"])
def test_only_known_transport_read_failures_are_retryable(store, monkeypatch, command, detail):
    monkeypatch.setattr(gitstore, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 128, b"", detail))
    with pytest.raises(RetryableRead):
        store.git(command, "origin")


@pytest.mark.parametrize("detail", [
    b"Permission denied; connection timed out", b"SSL certificate problem; connection reset",
    b"schannel: SEC_E_INVALID_TOKEN", b"The requested URL returned error: 403",
    b"bad object; remote end hung up unexpectedly", b"unrecognized Git failure",
    b"Permission denied" + b" progress" * 500 + b" Connection reset",
], ids=["permission", "certificate", "schannel", "http403", "integrity", "unknown", "long-output"])
def test_access_integrity_tls_and_unknown_errors_are_not_retryable(store, monkeypatch, detail):
    monkeypatch.setattr(gitstore, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 128, b"", detail))
    with pytest.raises(Error) as result:
        store.git("ls-remote", "origin")
    assert not isinstance(result.value, RetryableRead)


@pytest.mark.parametrize("command,detail,expected", [
    ("ls-remote", None, RetryableRead), ("fetch", b"partial read", RetryableRead),
    ("ls-remote", "schannel: SEC_E_INVALID_TOKEN", Error),
    ("fetch", b"authentication failed", Error), ("commit-tree", None, Error),
])
def test_timeout_classification_keeps_the_read_boundary(store, monkeypatch, command, detail, expected):
    failure = subprocess.TimeoutExpired(["git", command], 60, stderr=detail)
    def timeout(*args, **kwargs):
        raise failure
    monkeypatch.setattr(gitstore, "run", timeout)
    with pytest.raises(expected) as result:
        store.git(command)
    assert result.value.__cause__ is failure
    if expected is Error:
        assert not isinstance(result.value, RetryableRead)


def test_unchecked_git_failure_remains_a_result(store, monkeypatch):
    failed = subprocess.CompletedProcess(["git"], 1, b"", b"connection reset")
    monkeypatch.setattr(gitstore, "run", lambda *a, **k: failed)
    assert store.git("push", check=False) is failed


def test_diagnostics_redact_before_truncation():
    output = b"https://fixture-secret@fixture.invalid/ " + b"x" * 1800 + b" https://user:password@fixture.invalid/"
    detail = command_detail(output)
    assert "fixture-secret" not in detail and "password" not in detail
    assert "[redacted]" in detail and len(detail) <= 1500


def test_cache_contention_is_retryable_without_deleting_lock(store, monkeypatch):
    path = store.root.with_suffix(".lock")
    monkeypatch.setattr(gitstore, "locked", functools.partial(locked, wait=0))
    before = path.read_bytes()
    with locked(path):
        with pytest.raises(RetryableRead) as result:
            with store._cache_lock():
                pytest.fail("Already held cache lock was acquired.")
        assert isinstance(result.value.__cause__, LockBusy)
        assert path.exists()
    assert path.read_bytes() == before


@pytest.mark.skipif(os.name != "nt", reason="Windows locking boundary")
def test_unrelated_os_lock_failure_is_not_contention(tmp_path, monkeypatch):
    import msvcrt
    failure = OSError(errno.EBADF, "invalid descriptor")
    def reject(*args):
        raise failure
    monkeypatch.setattr(msvcrt, "locking", reject)
    with pytest.raises(OSError) as result:
        with locked(tmp_path / "broken.lock", wait=0):
            pytest.fail("Broken descriptor was accepted.")
    assert result.value is failure


def test_lost_push_reply_confirms_the_original_commit_once(store, monkeypatch):
    store.branch("main", {"asset": b"old"})
    before = store.snapshot()
    git = store.git
    attempts = []
    def lose_reply(*args, **kwargs):
        result = git(*args, **kwargs)
        if args[0] == "push":
            attempts.append(args)
            raise subprocess.TimeoutExpired(["git", "push"], 60)
        return result
    monkeypatch.setattr(store, "git", lose_reply)
    published = store.change("main", {"asset": b"new"}, {"asset": before.entries["asset"]}, "fixture change")
    assert len(attempts) == 1
    assert store.head("main") == published
    assert store.snapshot().bytes("asset") == b"new"


def test_successor_commit_can_confirm_a_lost_original_reply(store, monkeypatch):
    base = store.branch("main", {"asset": b"old"})
    original = store.commit(base, {"asset": b"new"}, "original")
    successor = store.commit(original, {"peer": b"independent"}, "peer append")
    git = store.git
    attempts = []
    def lose_reply(*args, **kwargs):
        result = git(*args, **kwargs)
        if args[0] == "push":
            attempts.append(args)
            git("push", "origin", f"{successor}:refs/heads/main")
            raise subprocess.TimeoutExpired(["git", "push"], 60)
        return result
    monkeypatch.setattr(store, "git", lose_reply)
    store.publish("main", original, base)
    assert len(attempts) == 1 and store.head("main") == successor
    assert store.snapshot().bytes("asset") == b"new"


@pytest.mark.parametrize("detail", [b"schannel: SEC_E_INVALID_TOKEN", b"unrecognized push reply"])
@pytest.mark.parametrize("accepted", [False, True])
def test_ambiguous_push_errors_check_the_original_result(store, monkeypatch, detail, accepted):
    base = store.branch("main", {"asset": b"old"})
    original = store.commit(base, {"asset": b"new"}, "original")
    git = store.git
    attempts = []
    def lose_reply(*args, **kwargs):
        if args[0] != "push":
            return git(*args, **kwargs)
        attempts.append(args)
        if accepted:
            git(*args, **kwargs)
        return subprocess.CompletedProcess(["git", "push"], 128, b"", detail)
    monkeypatch.setattr(store, "git", lose_reply)
    if accepted:
        store.publish("main", original, base)
    else:
        with pytest.raises(Uncertain):
            store.publish("main", original, base)
    assert len(attempts) == 1
    assert store.head("main") == (original if accepted else base)


@pytest.mark.parametrize("read_fails", [False, True])
def test_unconfirmed_push_never_repeats_change(store, monkeypatch, read_fails):
    store.branch("main", {"asset": b"old"})
    before = store.snapshot()
    git = store.git
    attempts = []
    def unavailable(*args, **kwargs):
        if args[0] == "push":
            attempts.append(args)
            raise subprocess.TimeoutExpired(["git", "push"], 60)
        if attempts and read_fails and args[0] == "ls-remote":
            raise RetryableRead("read still unavailable")
        return git(*args, **kwargs)
    with monkeypatch.context() as fault:
        fault.setattr(store, "git", unavailable)
        with pytest.raises(Uncertain):
            store.change("main", {"asset": b"new"}, {"asset": before.entries["asset"]}, "fixture change")
    assert len(attempts) == 1
    assert store.head("main") == before.revision
    assert store.snapshot().bytes("asset") == b"old"


def test_absent_ref_lease_cannot_fast_forward_a_raced_branch(store):
    base = store.branch("main", {"asset": b"old"})
    candidate = store.commit(base, {"asset": b"new"}, "candidate")
    store.publish("instance/raced", base, "")
    with pytest.raises(Conflict):
        store.publish("instance/raced", candidate, "")
    assert store.head("instance/raced") == base


def test_version_conflict_preserves_a_peer_write(store, monkeypatch):
    store.branch("main", {"asset": b"old"})
    before = store.snapshot()
    peer = store.commit(before.revision, {"asset": b"peer"}, "peer")
    git = store.git
    attempts = []
    def race(*args, **kwargs):
        if args[0] == "push":
            attempts.append(args)
            git("push", "origin", f"{peer}:refs/heads/main")
        return git(*args, **kwargs)
    monkeypatch.setattr(store, "git", race)
    with pytest.raises(Conflict):
        store.change("main", {"asset": b"mine"}, {"asset": before.entries["asset"]}, "fixture change")
    assert len(attempts) == 1 and store.snapshot().bytes("asset") == b"peer"


def test_incorrect_old_value_is_a_conflict_not_a_transport_retry(store, monkeypatch):
    base = store.branch("main", {"asset": b"old"})
    candidate = store.commit(base, {"asset": b"mine"}, "candidate")
    rejected = subprocess.CompletedProcess(["git", "push"], 1,
        b"!\tfixture:refs/heads/main\t[remote rejected] (incorrect old value provided)\n", b"")
    git = store.git
    def reject(*args, **kwargs):
        return rejected if args[0] == "push" else git(*args, **kwargs)
    monkeypatch.setattr(store, "git", reject)
    with pytest.raises(Conflict):
        store.publish("main", candidate, base)
    assert store.head("main") == base


@pytest.mark.parametrize("method,status,expected", [
    ("GET", 503, RetryableRead), ("GET", 429, RetryableRead), ("GET", 403, Error),
    ("POST", 503, Uncertain), ("POST", 429, Uncertain), ("PATCH", 403, Error),
])
def test_github_http_failures_distinguish_reads_and_writes(tmp_path, monkeypatch, method, status, expected):
    store = GitHubStore("github:fixture/repo", tmp_path)
    def reject(*args, **kwargs):
        raise urllib.error.HTTPError("https://fixture.invalid", status, "fixture", {}, None)
    monkeypatch.setattr(gitstore.urllib.request, "urlopen", reject)
    with pytest.raises(expected) as result:
        store.request(method, "/git/refs")
    if expected is Error:
        assert not isinstance(result.value, (RetryableRead, Uncertain))


@pytest.mark.parametrize("reason,expected", [
    (TimeoutError("timed out"), RetryableRead), (OSError(errno.ECONNRESET, "reset"), RetryableRead),
    (ssl.SSLCertVerificationError("certificate verify failed"), Error),
    (OSError(errno.EACCES, "permission denied"), Error), ("unrecognized transport failure", Error),
])
def test_github_transport_errors_are_not_all_retryable(tmp_path, monkeypatch, reason, expected):
    store = GitHubStore("github:fixture/repo", tmp_path)
    def reject(*args, **kwargs):
        raise urllib.error.URLError(reason)
    monkeypatch.setattr(gitstore.urllib.request, "urlopen", reject)
    with pytest.raises(expected) as result:
        store.request("GET", "/git/ref/heads/main")
    if expected is Error:
        assert not isinstance(result.value, RetryableRead)


def test_github_write_reconciliation_cannot_become_retryable(tmp_path, monkeypatch):
    store = GitHubStore("github:fixture/repo", tmp_path)
    writes = []
    def unavailable(method, path, value=None):
        if method == "PATCH":
            writes.append(value)
            raise Uncertain("write reply lost")
        raise RetryableRead("read unavailable")
    monkeypatch.setattr(store, "request", unavailable)
    with pytest.raises(Uncertain):
        store.publish("main", "original-commit", "parent")
    assert writes == [{"sha": "original-commit", "force": False}]
