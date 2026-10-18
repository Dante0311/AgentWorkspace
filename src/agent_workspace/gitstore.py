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
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from . import layout
from .util import (Conflict, Error, LockBusy, RetryableRead, Uncertain, command_detail,
                   digest, encode, locked, read_json, relpath, run, write_json)


def _validate_commit(store, parent, changes):
    previous = store.snapshot(revision=parent) if parent else None
    original_marker = previous.bytes(layout.MARKER) if previous else None
    shared = bool(previous and 'workspace.json' in previous.entries and '.aw/identity.json' not in previous.entries)
    if original_marker is not None:
        document = json.loads(original_marker)
        layout.version({layout.MARKER: original_marker}, document.get('kind') if isinstance(document, dict) else None)
        shared = document['kind'] == 'workspace'
    current_marker = changes.get(layout.MARKER, original_marker)
    if original_marker and json.loads(original_marker).get('version') == layout.MESSAGE_VERSION and current_marker is None:
        raise Error('The message layout marker cannot be removed.')
    if current_marker is not None:
        document = json.loads(current_marker)
        layout.version({layout.MARKER: current_marker}, document.get('kind') if isinstance(document, dict) else None)
        shared = shared and document['kind'] == 'workspace'
        if shared and document['version'] == layout.MESSAGE_VERSION:
            prefix = document['platform_prefix']
            message_prefixes = tuple((prefix + '/' if prefix else '') + root + '/' for root in layout.MESSAGE_ROOTS)
            if document.get('role') == 'messages':
                if any(p not in (layout.MARKER, layout.MESSAGE_GUARD) and not p.startswith(message_prefixes) for p in changes):
                    raise Error('The message branch cannot contain permission or instance records.')
            elif any(p.startswith(message_prefixes) and data is not None for p, data in changes.items()):
                raise Error('Publish message records through the dedicated message branch.')
        if original_marker and json.loads(original_marker).get('version') == layout.MESSAGE_VERSION and document['version'] != layout.MESSAGE_VERSION:
            raise Error('The message layout cannot be downgraded by a normal write.')
    platform_roots = layout.SHARED_ROOTS | {'.aw', '.aw-local', '.agentworkspace'}
    paths = set(previous.entries if previous else ()) | set(changes)
    for path in paths:
        if path not in changes or changes[path] is not None:
            # Shared repositories may retain historical user archives outside AW's data roots.
            inherited_archive = shared and path not in changes and path.split('/', 1)[0].casefold() not in platform_roots
            relpath(path, allow_local=inherited_archive)


def git_env(env=None):
    # Reuse the user's Git credential helpers and SSH agent, but never initiate login.
    return dict(os.environ if env is None else env, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never",
                GIT_ASKPASS="", SSH_ASKPASS="", GIT_SSH_VARIANT="ssh",
                GIT_SSH_COMMAND="ssh -o BatchMode=yes -o StrictHostKeyChecking=yes")



TLS_FAILURES = ("schannel", "sec_e_", "ssl", "tls")
SCHANNEL_INVALID_TOKEN = "schannel: next initializesecuritycontext failed: sec_e_invalid_token (0x80090308)"


def permanent_git_failure(detail: str) -> bool:
    # A partial transfer can mention both a network symptom and invalid data.
    # Do not let the network wording hide an explicit access or integrity failure.
    detail = detail.lower()
    if any(word in detail for word in ("permission denied", "access denied", "authentication failed",
            "repository not found", "not a git repository", "certificate", "host key verification failed",
            "could not read username", "could not read password", "unable to get password from user",
            "terminal prompts disabled", "corrupt", "bad object",
            "invalid object", "protocol error",
            "the requested url returned error: 401",
            "the requested url returned error: 403")):
        return True
    # Retry only the observed handshake failure, with full TLS validation on the new read.
    # Other TLS diagnostics and explicit access/integrity failures still take precedence.
    remaining = detail.replace(SCHANNEL_INVALID_TOKEN, "")
    return any(word in remaining for word in TLS_FAILURES)


def temporary_transport_failure(detail: str) -> bool:
    if permanent_git_failure(detail):
        return False
    detail = detail.lower()
    return any(word in detail for word in (
        SCHANNEL_INVALID_TOKEN,
        "could not resolve host", "could not resolve proxy", "could not resolve hostname",
        "temporary failure in name resolution", "failed to connect to", "connection timed out",
        "operation timed out", "connection reset", "connection refused", "network is unreachable",
        "no route to host", "empty reply from server", "remote end hung up unexpectedly",
        "unexpected disconnect while reading sideband packet",
        *(f"the requested url returned error: {code}" for code in (408, 429, 500, 502, 503, 504))))


def rejected_ref_update(result, branch, expected):
    stdout = result.stdout.decode("utf-8", errors="replace")
    ref = re.escape(f"refs/heads/{branch}")
    return any(reason in stdout for reason in (
        "[rejected] (non-fast-forward)", "[rejected] (fetch first)", "[rejected] (stale info)",
        "[remote rejected] (incorrect old value provided)")) or bool(expected and re.search(
            rf"^!\t[^\t\r\n]+:{ref}\t\[remote rejected\] \(cannot lock ref '{ref}': "
            rf"is at (?:[0-9a-f]{{40}}|[0-9a-f]{{64}}) but expected {re.escape(expected)}\)\r?$",
            stdout, re.MULTILINE))


class Snapshot:
    def __init__(self, store, revision: str, entries: dict[str, str]):
        self.store, self.revision, self.entries = store, revision, entries
        self._blobs = {}

    def bytes(self, path: str) -> bytes | None:
        sha = self.entries.get(path)
        if sha is None:
            return None
        # A blob ID fixes immutable bytes; keep reuse within this pinned snapshot.
        if sha not in self._blobs:
            self._blobs[sha] = self.store.blob(sha)
        return self._blobs[sha]

    def json(self, path: str, default=None):
        value = self.bytes(path)
        return default if value is None else json.loads(value)

    def all(self, prefix: str = "") -> dict[str, bytes]:
        return {p: self.bytes(p) for p in self.entries if p.startswith(prefix)}


class GitStore:
    def message_snapshot(self):
        from . import message_store
        return message_store.read(self)

    def message_change(self, state, changes, expected, message, *, permission_expected=None):
        from . import message_store
        return message_store.change(self, state, changes, expected, message,
                                    permission_expected=permission_expected)

    def __init__(self, address: str, home: Path, *, root: Path | None = None):
        self.address = address
        self.operations = Path(home) / 'storage-operations' / digest(address.encode())
        self.root = root if root is not None else home / "git" / digest(address.encode())[:24]
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

    def contains_commit(self, commit, head):
        result = self.git('merge-base', '--is-ancestor', commit, head, check=False)
        if result.returncode not in (0, 1):
            raise Error(command_detail(result.stderr) or 'Could not inspect migration commit ancestry.')
        return result.returncode == 0

    def commit(self, parent: str, changes: dict[str, bytes | None], message: str) -> str:
        _validate_commit(self, parent, changes)
        with tempfile.TemporaryDirectory(prefix="aw-index-") as directory:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / "index"),
                       GIT_AUTHOR_NAME="Agent Workspace", GIT_AUTHOR_EMAIL="aw@localhost",
                       GIT_COMMITTER_NAME="Agent Workspace", GIT_COMMITTER_EMAIL="aw@localhost")
            self.git("read-tree", parent if parent else "--empty", env=env)
            lines = []
            for path, content in changes.items():
                relpath(path, allow_local=content is None)
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
        if branch == 'main':
            from . import message_store
            if expected and message_store.publish_permissions(self, commit, expected):
                return
            if not expected and layout.version(self.snapshot(revision=commit), 'workspace') == layout.MESSAGE_VERSION:
                raise Error('Initialize the message layout through its atomic two-ref publication.')
        self._publish_ref(branch, commit, expected)

    def publication_status(self, updates):
        accepted = []
        for branch, update in updates.items():
            head = self.head(branch)
            accepted.append(bool(head and (head == update['after'] or self.contains_commit(update['after'], head))))
        if any(accepted) and not all(accepted):
            raise Uncertain('Only part of the original atomic publication is observable; preserve it and inspect both original refs.')
        return all(accepted)

    def publish_atomic(self, updates):
        if len(updates) < 2:
            raise Error('An atomic permission publication needs two actual ref updates.')
        for branch, update in updates.items():
            if update['before'] == update['after'] or not update['after']:
                raise Error('Every protected ref must receive a new commit.')
            if update['before'] and not self.contains_commit(update['before'], update['after']):
                raise Error('Atomic publication must fast-forward every existing ref.')
        path = self.operations / 'atomic' / (digest(encode(updates)) + '.json')
        with locked(path.with_suffix('.lock')):
            receipt = read_json(path)
            if receipt:
                if self.publication_status(updates):
                    return
                if receipt['phase'] == 'rejected':
                    raise Conflict('The original atomic publication was rejected; reread its preconditions.')
                raise Uncertain('The original atomic publication is not confirmed; it was not repeated.')
            write_json(path, {'updates': updates, 'phase': 'publishing'})
            try:
                self._publish_atomic(updates)
            except (Conflict, Uncertain) as exc:
                try:
                    accepted = self.publication_status(updates)
                except (Error, OSError) as read_error:
                    raise Uncertain(f'Cannot confirm the original atomic publication: {read_error}') from exc
                if not accepted:
                    if isinstance(exc, Conflict):
                        write_json(path, {'updates': updates, 'phase': 'rejected'})
                    raise
            except Error:
                write_json(path, {'updates': updates, 'phase': 'rejected'})
                raise
            write_json(path, {'updates': updates, 'phase': 'published'})

    def _publish_atomic(self, updates):
        args = ['push', '--atomic', '--porcelain']
        for branch, update in updates.items():
            args.append(f"--force-with-lease=refs/heads/{branch}:{update['before']}")
        args += ['origin', *(f"{u['after']}:refs/heads/{b}" for b, u in updates.items())]
        try:
            result = self.git(*args, check=False)
        except subprocess.TimeoutExpired as exc:
            raise Uncertain('Atomic Git push timed out; inspect both original commits.') from exc
        if result.returncode == 0:
            return
        output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
        if 'does not support --atomic push' in output or 'does not support atomic push' in output:
            raise Error('This remote does not support atomic ref updates; the message layout cannot be enabled or changed.')
        if any(rejected_ref_update(result, branch, update['before']) for branch, update in updates.items()) or any(reason in output for reason in ('[rejected] (stale info)', '[rejected] (fetch first)',
                '[rejected] (non-fast-forward)', '[rejected] (atomic push failed)', '[remote rejected] (atomic push failure)')):
            raise Conflict(command_detail(result.stdout + result.stderr))
        if permanent_git_failure(output) and not any(word in output.lower() for word in TLS_FAILURES):
            raise Error(command_detail(result.stdout + result.stderr))
        raise Uncertain(command_detail(result.stdout + result.stderr))

    def _publish_ref(self, branch: str, commit: str, expected: str) -> None:
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
            rejected = rejected_ref_update(result, branch, expected)
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
        self.operations = Path(home) / 'storage-operations' / digest(address.encode())
        owner, repo = address.removeprefix("github:").split("/")
        self.api = f"https://api.github.com/repos/{owner}/{repo}"
        self._blobs = {}

    def request(self, method: str, path: str, value=None):
        read_request = method == 'GET' or (path == '/graphql' and value['query'].lstrip().startswith('query'))
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "agent-workspace"}
        if token:
            headers["Authorization"] = "Bearer " + token
        data = None if value is None else json.dumps(value).encode()
        if data is not None:
            headers["Content-Type"] = "application/json"
        url = 'https://api.github.com/graphql' if path == '/graphql' else self.api + path
        req = urllib.request.Request(url, data, headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=40) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and method == "GET":
                return None
            if exc.code in (409, 422):
                raise Conflict("GitHub rejected a stale or invalid Git update.") from None
            if exc.code in (408, 429, 500, 502, 503, 504):
                if read_request:
                    raise RetryableRead(f"GitHub HTTP {exc.code}; no shared state was confirmed.") from exc
                raise Uncertain(f"GitHub HTTP {exc.code}; inspect the original write result.") from exc
            raise Error(f"GitHub HTTP {exc.code}; check token permissions and branch rules.") from None
        except (urllib.error.URLError, TimeoutError) as exc:
            if not read_request:
                raise Uncertain("GitHub write result is unknown; inspect the original operation.") from exc
            reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
            if not permanent_git_failure(str(reason)) and (isinstance(reason, TimeoutError) or (isinstance(reason, OSError) and reason.errno in
                    (errno.ETIMEDOUT, errno.ECONNRESET, errno.ECONNREFUSED, errno.ENETUNREACH, errno.EHOSTUNREACH))
                    or temporary_transport_failure(str(reason))):
                raise RetryableRead("GitHub read temporarily unavailable; no shared state was confirmed.") from exc
            raise Error("GitHub read failed; no shared state was confirmed.") from exc

    def bootstrap(self, metadata, *, layout_version=layout.VERSION):
        # GitHub cannot create a ref in a repository with no branches. The Contents
        # endpoint creates the initial commit; omitting sha forbids replacing a file.
        self.atomic_capability()
        self.request("PUT", "/contents/workspace.json", {"message": "Initialize Agent Workspace",
            "content": base64.b64encode(encode(metadata)).decode(), "branch": "main"})
        snap = self.snapshot()
        from . import message_store
        message_store.initialize(self, metadata, layout_version == layout.WORKER_VERSION, parent=snap.revision)

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

    def contains_commit(self, commit, head):
        comparison = self.request('GET', f'/compare/{commit}...{head}')
        if not isinstance(comparison, dict) or comparison.get('status') not in ('ahead', 'behind', 'identical', 'diverged'):
            raise Error('Could not inspect migration commit ancestry.')
        return comparison['status'] in ('ahead', 'identical')

    def commit(self, parent, changes, message):
        _validate_commit(self, parent, changes)
        items = []
        for path, data in changes.items():
            relpath(path, allow_local=data is None)
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

    def atomic_capability(self):
        owner, repo = self.address.removeprefix('github:').split('/')
        info = self.request('POST', '/graphql', {'query':
            'query($owner:String!,$name:String!){repository(owner:$owner,name:$name){id} __type(name:"Mutation"){fields{name}}}',
            'variables': {'owner': owner, 'name': repo}})
        data = info.get('data') or {}
        if info.get('errors') or not data.get('repository') or not any(
                field['name'] == 'updateRefs' for field in (data.get('__type') or {}).get('fields', [])):
            raise Error('GitHub atomic updateRefs is unavailable; refusing the message layout operation.')
        return data['repository']['id']

    def _publish_atomic(self, updates):
        repository = self.atomic_capability()
        identifier = digest(encode(updates))
        value = {'repositoryId': repository, 'clientMutationId': identifier,
                 'refUpdates': [{'name': 'refs/heads/' + branch, 'beforeOid': item['before'] or '0' * 40,
                                 'afterOid': item['after'], 'force': False} for branch, item in updates.items()]}
        result = self.request('POST', '/graphql', {'query':
            'mutation($input:UpdateRefsInput!){updateRefs(input:$input){clientMutationId}}', 'variables': {'input': value}})
        if result.get('errors'):
            if all(error.get('type') in ('UNPROCESSABLE', 'CONFLICT') for error in result['errors']):
                raise Conflict('GitHub rejected the original atomic ref preconditions.')
            raise Uncertain('GitHub did not confirm the original updateRefs mutation; inspect both original refs.')
        if ((result.get('data') or {}).get('updateRefs') or {}).get('clientMutationId') != identifier:
            raise Uncertain('GitHub did not return the original atomic mutation receipt.')

    def _publish_ref(self, branch, commit, expected):
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
