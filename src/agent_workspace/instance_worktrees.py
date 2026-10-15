"""Git facts and checkout preparation for instance material directories."""
from pathlib import Path

from .gitstore import GitStore, git_env
from .util import Conflict, digest, local_asset_path, run


def git(root, *args, **kwargs):
    return run(['git', '-C', str(root), *args], env=git_env(), **kwargs)


def transport(address):
    return 'https://github.com/' + address[7:] + '.git' if address.startswith('github:') else address


def repository(root, address, home, branch):
    if not (root / '.git').exists():
        return None
    top = Path(git(root, 'rev-parse', '--show-toplevel').stdout.decode().strip()).resolve()
    actual_branch = git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD', check=False).stdout.decode().strip()
    if top != root or actual_branch != branch:
        raise Conflict('The directory is checked out on another Git root or branch; it was preserved.')
    origin = git(root, 'remote', 'get-url', 'origin').stdout.decode().strip()
    expected = transport(address)
    if Path(origin).exists():
        origin = str(Path(origin).resolve())
        expected = str(Path(expected).resolve())
    if origin != expected:
        raise Conflict('The directory Git origin points to another Workspace; it was preserved.')
    common = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir').stdout.decode().strip())
    return GitStore(origin, home, root=common)


def prepare(root, address, home, branch, revision):
    # Each copy has independent Git refs/index, including two copies of the same Agent.
    store = GitStore(transport(address), home, root=home / 'worktree-git' / digest(str(root).encode())[:24])
    store.snapshot(revision=revision)
    with store._cache_lock():
        local = store.git('rev-parse', '--verify', 'refs/heads/' + branch, check=False)
        if local.returncode:
            store.git('branch', branch, revision)
        elif local.stdout.decode().strip() != revision:
            raise Conflict('The previous local branch has different saved Git work; inspect it before preparing this directory.')
        reuse_missing = []
        listing = store.git('worktree', 'list', '--porcelain', '-z').stdout
        for record in listing.split(b'\0\0'):
            facts = {}
            for field in record.split(b'\0'):
                if field:
                    name, _, value = field.partition(b' ')
                    facts[name] = value
            if facts.get(b'branch') != ('refs/heads/' + branch).encode():
                continue
            previous_root = Path(facts[b'worktree'].decode()).resolve()
            if previous_root != root or b'locked' in facts or (root.exists() and any(root.iterdir())):
                raise Conflict('The instance branch already has another or locked worktree; its files and index were preserved.')
            # Git retains the old administrative index; only the absent/empty target is recreated.
            reuse_missing = ['--force']
        store.git('-c', 'core.autocrlf=false', 'worktree', 'add', '--quiet', *reuse_missing, str(root), branch)
    return store


def head(root):
    return git(root, 'rev-parse', 'HEAD').stdout.decode().strip()


def check_index(root):
    entries = git(root, 'ls-files', '--stage', '-z').stdout.split(b'\0')
    for entry in entries:
        if not entry:
            continue
        meta, path = entry.split(b'\t', 1)
        mode, _, stage = meta.split()
        if stage != b'0':
            raise Conflict('Resolve the worktree index merge conflicts before saving or syncing.')
        if mode == b'160000' or local_asset_path(path.decode()):
            raise Conflict('The index contains a nested repository or local runtime data; preserve and remove it from the index first.')
    staged = set(git(root, 'diff', '--cached', '--name-only', '-z', 'HEAD').stdout.split(b'\0')) - {b''}
    unstaged = set(git(root, 'diff', '--name-only', '-z').stdout.split(b'\0')) - {b''}
    if staged & unstaged:
        raise Conflict('A staged file also has different working files; preserve or resolve its staged version before saving.')
    return {path.decode() for path in staged}


def record_saved(root, branch, before, revision):
    if before == revision:
        return
    # Saving includes the selected staged and working bytes. Only the index moves.
    if head(root) != before:
        raise Conflict('The Git branch changed while saving; preserve the published result and local Git state.')
    git(root, 'read-tree', '--reset', revision)
    git(root, 'update-ref', 'refs/heads/' + branch, revision, before)
