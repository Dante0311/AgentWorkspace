"""Git storage without changing the user's checkout or index.

Every shared mutation compares file versions, creates a child of the observed head,
and uses a fast-forward push. Independent appends can retry; business conflicts cannot.
"""
from __future__ import annotations

import base64
import contextlib
import errno
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from .util import (Conflict, Error, LockBusy, RetryableRead, Uncertain, command_detail,
                   digest, encode, locked, relpath, run)


def git_env(env=None):
    # Reuse the user's Git credential helpers and SSH agent, but never initiate login.
    return dict(os.environ if env is None else env, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never",
                GIT_ASKPASS="", SSH_ASKPASS="", GIT_SSH_VARIANT="ssh",
                GIT_SSH_COMMAND="ssh -o BatchMode=yes -o StrictHostKeyChecking=yes")



TLS_FAILURES = ("schannel", "sec_e_", "ssl", "tls")


def permanent_git_failure(detail: str) -> bool:
    # A partial transfer can mention both a network symptom and invalid data.
    # Do not let the network wording hide an explicit access or integrity failure.
    return any(word in detail.lower() for word in ("permission denied", "access denied", "authentication failed",
            "repository not found", "not a git repository", "certificate", "host key verification failed",
            "could not read username", "terminal prompts disabled", "corrupt", "bad object",
            "invalid object", "protocol error", *TLS_FAILURES,
            "the requested url returned error: 401",
            "the requested url returned error: 403"))


def temporary_transport_failure(detail: str) -> bool:
    if permanent_git_failure(detail):
        return False
    detail = detail.lower()
    return any(word in detail for word in (
        "could not resolve host", "could not resolve proxy", "could not resolve hostname",
        "temporary failure in name resolution", "failed to connect to", "connection timed out",
        "operation timed out", "connection reset", "connection refused", "network is unreachable",
        "no route to host", "empty reply from server", "remote end hung up unexpectedly",
        "unexpected disconnect while reading sideband packet",
        *(f"the requested url returned error: {code}" for code in (408, 429, 500, 502, 503, 504))))


class Snapshot:
    def __init__(self, store, revision: str, entries: dict[str, str]):
        self.store, self.revision, self.entries = store, revision, entries

    def bytes(self, path: str) -> bytes | None:
        sha = self.entries.get(path)
        return None if sha is None else self.store.blob(sha)

    def json(self, path: str, default=None):
        value = self.bytes(path)
        return default if value is None else json.loads(value)

    def all(self, prefix: str = "") -> dict[str, bytes]:
        return {p: self.store.blob(sha) for p, sha in self.entries.items() if p.startswith(prefix)}


class GitStore:
    def __init__(self, address: str, home: Path):
        self.address = address
        self.root = home / "git" / digest(address.encode())[:24]
        with self._cache_lock():
            if not self.root.exists():
                self.root.parent.mkdir(parents=True, exist_ok=True)
                # Assets are regular files; avoid Git for Windows' symlink probe.
                run(["git", "-c", "core.symlinks=false", "init", "--bare", str(self.root)])
                self.git("remote", "add", "origin", address)

    def git(self, *args, **kwargs):
        kwargs["env"] = git_env(kwargs.get("env"))
        check = kwargs.pop("check", True)
        try:
            result = run(["git", "-c", "credential.interactive=false", "--git-dir", str(self.root), *args],
                         check=False, **kwargs)
        except subprocess.TimeoutExpired as exc:
            if args[0] == "push":
                # The publication boundary knows the original commit and can check its result.
                raise
            output = exc.stderr or exc.output or ""
            full_detail = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else output
            detail = command_detail(output)
            message = f"Git {args[0]} timed out after {exc.timeout} seconds. {detail}".strip()
            if args[0] in ("ls-remote", "fetch") and not permanent_git_failure(full_detail):
                raise RetryableRead(message) from exc
            raise Error(message) from exc
        if check and result.returncode:
            output = result.stdout + result.stderr
            detail = command_detail(output) or f"Git {args[0]} exited {result.returncode}"
            if args[0] in ("ls-remote", "fetch") and temporary_transport_failure(output.decode("utf-8", errors="replace")):
                raise RetryableRead(detail)
            raise Error(detail)
        return result

    @contextlib.contextmanager
    def _cache_lock(self):
        try:
            with locked(self.root.with_suffix(".lock")):
                yield
        except LockBusy as exc:
            raise RetryableRead(str(exc)) from exc

    @staticmethod
    def initialize(path: Path):
        if path.exists() and any(path.iterdir()):
            raise Conflict("Workspace target must be empty; use workspace connect for an existing repo.")
        path.mkdir(parents=True, exist_ok=True)
        run(["git", "-c", "core.symlinks=false", "init", "--bare", "--initial-branch=main", str(path)])

    def head(self, branch: str) -> str | None:
        result = self.git("ls-remote", "--heads", "origin", f"refs/heads/{branch}")
        lines = result.stdout.decode().splitlines()
        if not lines:
            return None
        sha = lines[0].split()[0]
        with self._cache_lock():
            self.git("fetch", "--quiet", "--no-tags", "origin", sha)
        return sha

    def snapshot(self, branch: str = "main", *, revision: str | None = None) -> Snapshot:
        sha = revision if revision is not None else self.head(branch)
        if sha is None:
            return Snapshot(self, "", {})
        if self.git("cat-file", "-e", sha, check=False).returncode:
            with self._cache_lock():
                self.git("fetch", "--quiet", "origin", sha)
        raw = self.git("ls-tree", "-rz", sha).stdout
        entries = {}
        for item in raw.split(b"\0"):
            if not item:
                continue
            meta, path = item.split(b"\t", 1)
            mode, kind, blob = meta.decode().split()
            if kind != "blob" or mode == "120000":
                raise Error("Workspace assets must be regular files; symlinks/submodules need explicit export.")
            entries[path.decode("utf-8")] = blob
        return Snapshot(self, sha, entries)

    def blob(self, sha: str) -> bytes:
        return self.git("cat-file", "blob", sha).stdout

    def commit(self, parent: str, changes: dict[str, bytes | None], message: str) -> str:
        with tempfile.TemporaryDirectory(prefix="aw-index-") as directory:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / "index"),
                       GIT_AUTHOR_NAME="Agent Workspace", GIT_AUTHOR_EMAIL="aw@localhost",
                       GIT_COMMITTER_NAME="Agent Workspace", GIT_COMMITTER_EMAIL="aw@localhost")
            self.git("read-tree", parent if parent else "--empty", env=env)
            lines = []
            for path, content in changes.items():
                relpath(path)
                if content is None:
                    lines.append(b"0 " + b"0" * 40 + b"\t" + path.encode() + b"\0")
                else:
                    sha = self.git("hash-object", "-w", "--stdin", data=content).stdout.strip()
                    lines.append(b"100644 " + sha + b"\t" + path.encode() + b"\0")
            self.git("update-index", "-z", "--index-info", data=b"".join(lines), env=env)
            tree = self.git("write-tree", env=env).stdout.decode().strip()
            args = ["commit-tree", tree]
            if parent:
                args += ["-p", parent]
            return self.git(*args, data=message.encode(), env=env).stdout.decode().strip()

    def publish(self, branch: str, commit: str, expected: str) -> None:
        args = ["push", "--porcelain"]
        if not expected:
            # This lease only creates an absent ref; it cannot replace an existing branch.
            args.append(f"--force-with-lease=refs/heads/{branch}:")
        args += ["origin", f"{commit}:refs/heads/{branch}"]
        try:
            result = self.git(*args, check=False)
        except subprocess.TimeoutExpired as exc:
            detail = f"Git push timed out after {exc.timeout} seconds. {command_detail(exc.stderr or exc.output)}".strip()
            failure = Uncertain(detail)
            failure.__cause__ = exc
            rejected = False
        else:
            if result.returncode == 0:
                return
            output = result.stdout + result.stderr
            detail = command_detail(output) or f"Git push exited {result.returncode}"
            full_detail = output.decode("utf-8", errors="replace")
            # TLS or an unrecognized push failure may occur after the ref was updated.
            # This is a write with an unknown outcome, never a retryable read.
            known_failure = permanent_git_failure(full_detail) and not any(word in full_detail.lower() for word in TLS_FAILURES)
            failure = Error(detail) if known_failure else Uncertain(detail)
            rejected = any(reason in result.stdout.decode("utf-8", errors="replace") for reason in (
                "[rejected] (non-fast-forward)", "[rejected] (fetch first)", "[rejected] (stale info)",
                "[remote rejected] (incorrect old value provided)"))
            if not isinstance(failure, Uncertain) and not rejected:
                raise failure
        try:
            actual = self.head(branch)
            if actual == commit:
                return
            if actual:
                ancestry = self.git("merge-base", "--is-ancestor", commit, actual, check=False)
                if ancestry.returncode == 0:
                    return
                if ancestry.returncode != 1:
                    raise Error(command_detail(ancestry.stderr) or "Could not inspect publication ancestry.")
        except (Error, OSError) as exc:
            raise Uncertain(f"{detail}\nCould not confirm commit {commit}: {exc}") from exc
        if rejected:
            raise Conflict(f"{detail}\nShared branch rejected the expected version; reread the operation preconditions.")
        # Even an unchanged ref does not prove a timed-out server operation cannot finish later.
        raise Uncertain(f"{detail}\nCommit {commit} is not confirmed; inspect the original operation before retrying.") from failure

    def change(self, branch: str, changes: dict[str, bytes | None], expected: dict[str, str | None],
               message: str, *, base: str | None = None) -> str:
        for _ in range(4):
            snap = self.snapshot(branch)
            if base is not None and snap.revision != base:
                raise Conflict("Instance branch changed since this directory was synchronized.")
            for path, sha in expected.items():
                if snap.entries.get(path) != sha:
                    raise Conflict(f"Changed object: {path}. Read its new revision first.")
            commit = self.commit(snap.revision, changes, message)
            try:
                self.publish(branch, commit, snap.revision)
                return commit
            except Conflict:
                continue
        raise Conflict("Concurrent writes exceeded the retry budget; no business action was repeated.")

    def branch(self, name: str, files: dict[str, bytes], *, parent: str = "") -> str:
        if self.head(name) is not None:
            raise Conflict(f"Branch already exists: {name}")
        if parent:
            snap = self.snapshot(revision=parent)
            changes = {p: None for p in snap.entries if p not in files}
            changes.update(files)
        else:
            changes = files
        commit = self.commit(parent, changes, f"Create {name}")
        self.publish(name, commit, "")
        return commit


class GitHubStore(GitStore):
    """The same Git contract through GitHub REST; no git executable or clone required.

    Address form: github:owner/repo. Credentials are read from GITHUB_TOKEN/GH_TOKEN only.
    """
    def __init__(self, address: str, home: Path):
        self.address = address
        owner, repo = address.removeprefix("github:").split("/")
        self.api = f"https://api.github.com/repos/{owner}/{repo}"
        self._blobs = {}

    def request(self, method: str, path: str, value=None):
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "agent-workspace"}
        if token:
            headers["Authorization"] = "Bearer " + token
        data = None if value is None else json.dumps(value).encode()
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.api + path, data, headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=40) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and method == "GET":
                return None
            if exc.code in (409, 422):
                raise Conflict("GitHub rejected a stale or invalid Git update.") from None
            if exc.code in (408, 429, 500, 502, 503, 504):
                if method == "GET":
                    raise RetryableRead(f"GitHub HTTP {exc.code}; no shared state was confirmed.") from exc
                raise Uncertain(f"GitHub HTTP {exc.code}; inspect the original write result.") from exc
            raise Error(f"GitHub HTTP {exc.code}; check token permissions and branch rules.") from None
        except (urllib.error.URLError, TimeoutError) as exc:
            if method != "GET":
                raise Uncertain("GitHub write result is unknown; inspect the original operation.") from exc
            reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
            if not permanent_git_failure(str(reason)) and (isinstance(reason, TimeoutError) or (isinstance(reason, OSError) and reason.errno in
                    (errno.ETIMEDOUT, errno.ECONNRESET, errno.ECONNREFUSED, errno.ENETUNREACH, errno.EHOSTUNREACH))
                    or temporary_transport_failure(str(reason))):
                raise RetryableRead("GitHub read temporarily unavailable; no shared state was confirmed.") from exc
            raise Error("GitHub read failed; no shared state was confirmed.") from exc

    def bootstrap(self, metadata):
        # GitHub cannot create a ref in a repository with no branches. The Contents
        # endpoint creates the initial commit; omitting sha forbids replacing a file.
        self.request("PUT", "/contents/workspace.json", {"message": "Initialize Agent Workspace",
            "content": base64.b64encode(encode(metadata)).decode(), "branch": "main"})

    def head(self, branch):
        ref = self.request("GET", "/git/ref/heads/" + urllib.parse.quote(branch, safe="/"))
        return ref["object"]["sha"] if ref else None

    def snapshot(self, branch="main", *, revision=None):
        sha = revision if revision is not None else self.head(branch)
        if not sha:
            return Snapshot(self, "", {})
        tree = self.request("GET", f"/git/trees/{sha}?recursive=1")
        if tree is None or tree.get("truncated"):
            raise Error("GitHub tree is unavailable or truncated; refusing an incomplete snapshot.")
        entries = {}
        for item in tree["tree"]:
            if item["type"] == "tree":
                continue
            if item["type"] != "blob" or item["mode"] == "120000":
                raise Error("Export symlinks/submodules explicitly before adding them as assets.")
            entries[item["path"]] = item["sha"]
        return Snapshot(self, sha, entries)

    def blob(self, sha):
        if sha not in self._blobs:
            item = self.request("GET", f"/git/blobs/{sha}")
            if item is None:
                raise Error(f"Git blob unavailable: {sha}")
            self._blobs[sha] = base64.b64decode(item["content"])
        return self._blobs[sha]

    def commit(self, parent, changes, message):
        items = []
        for path, data in changes.items():
            relpath(path)
            blob = None
            if data is not None:
                blob = self.request("POST", "/git/blobs", {
                    "content": base64.b64encode(data).decode(), "encoding": "base64"})["sha"]
            items.append({"path": path, "mode": "100644", "type": "blob", "sha": blob})
        value = {"tree": items}
        if parent:
            value["base_tree"] = self.request("GET", f"/git/commits/{parent}")["tree"]["sha"]
        tree = self.request("POST", "/git/trees", value)["sha"]
        return self.request("POST", "/git/commits", {
            "message": message, "tree": tree, "parents": [parent] if parent else []})["sha"]

    def publish(self, branch, commit, expected):
        path = "/git/refs/heads/" + urllib.parse.quote(branch, safe="/")
        try:
            if not expected:
                self.request("POST", "/git/refs", {"ref": "refs/heads/" + branch, "sha": commit})
            else:
                self.request("PATCH", path, {"sha": commit, "force": False})
        except (Conflict, Uncertain) as failure:
            try:
                actual = self.head(branch)
            except (Error, OSError) as exc:
                raise Uncertain(f"{failure}\nCould not confirm commit {commit}: {exc}") from exc
            if actual == commit:
                return
            raise

    def branch(self, name, files, *, parent=""):
        if self.head(name):
            raise Conflict("Instance branch already exists.")
        previous = self.snapshot(revision=parent).entries if parent else {}
        changes = {p: None for p in previous if p not in files}
        changes.update(files)
        commit = self.commit(parent, changes, f"Create {name}")
        self.publish(name, commit, "")
        return commit


def open_store(address: str, home: Path):
    return GitHubStore(address, home) if address.startswith("github:") else GitStore(address, home)
