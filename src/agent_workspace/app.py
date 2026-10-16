from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from . import instance_worktrees, migration, skills as shared_skills, software, workers
from .gitstore import GitStore, GitHubStore, open_store
from . import model_profiles
from . import layout
from .util import Conflict, Error, RetryableRead, Uncertain, digest, encode, inside, local_asset_path, locked, now, read_json, relpath, slug, uid, write_bytes, write_json


DEFAULT_EXCLUDES = [".git", ".aw-local", ".local", "__pycache__", ".env", ".env.*", "secrets"]
_UNOBSERVED = object()


class App:
    def __init__(self, home: str | Path | None = None):
        self.home = Path(home or os.environ.get("AW_HOME", Path.home() / ".agent-workspace")).expanduser().resolve()
        self.home.mkdir(parents=True, exist_ok=True)
        self.registry = self.home / "registry.json"
        self._stores = {}

    def local(self):
        return read_json(self.registry, {"workspaces": {}})

    def change_local(self, edit):
        with locked(self.home / "registry.lock"):
            value = self.local()
            edit(value)
            write_json(self.registry, value)

    def store(self, workspace):
        entry = self.local()["workspaces"].get(workspace)
        if entry is None:
            raise Error(f"Unknown workspace: {workspace}; use workspace connect.")
        address = entry["address"]
        if address not in self._stores:
            self._stores[address] = open_store(address, self.home)
        return self._stores[address]

    def workspace_init(self, name, directory, *, worker_support=True):
        slug(name)
        path = Path(directory).expanduser().resolve()
        GitStore.initialize(path)
        store = open_store(str(path), self.home)
        meta = {"schema": 1, "name": name, "locator": "local:" + name, "friends": {}, "projects": {}}
        store.branch("main", {layout.MARKER: layout.marker('workspace', version=layout.WORKER_VERSION if worker_support else layout.VERSION),
                              '.agentworkspace/workspace.json': encode(meta)})
        return self.workspace_connect(name, str(path))

    def workspace_connect(self, name, address):
        slug(name)
        if ":" not in address or Path(address).exists():
            address = str(Path(address).expanduser().resolve())
        store = open_store(address, self.home)
        snap = store.snapshot()
        meta = snap.json(layout.shared_path(snap, "workspace.json"))
        if meta is None:
            raise Error("This repository has no workspace.json. Initialize it explicitly, not over existing files.")
        if meta.get("schema") != 1:
            raise Error("Unsupported workspace format.")
        def edit(value):
            previous = value["workspaces"].get(name)
            if previous and previous["locator"] != meta["locator"]:
                raise Conflict("Alias already points to a different workspace.")
            value["workspaces"][name] = dict(previous or {}, address=address, locator=meta["locator"])
        self.change_local(edit)
        return {"name": name, "locator": meta["locator"], "address": address, "revision": snap.revision}

    def workspace_bootstrap_remote(self, name, address, *, worker_support=True):
        """Initialize only an already-created empty remote repo, never create a GitHub account resource."""
        slug(name)
        store = open_store(address, self.home)
        if store.head("main"):
            raise Conflict("Remote main exists; initialization must not overwrite it.")
        meta = {"schema": 1, "name": name, "locator": address, "friends": {}, "projects": {}}
        if isinstance(store, GitHubStore):
            store.bootstrap(meta, layout_version=layout.WORKER_VERSION if worker_support else layout.VERSION)
        else:
            store.branch("main", {layout.MARKER: layout.marker('workspace', version=layout.WORKER_VERSION if worker_support else layout.VERSION),
                                  '.agentworkspace/workspace.json': encode(meta)})
        return self.workspace_connect(name, address)

    def workspace_list(self):
        return [{"alias": k, **v} for k, v in self.local()["workspaces"].items()]

    def workspace_show(self, workspace, *, snapshot=None):
        snap = snapshot or self.store(workspace).snapshot()
        return {**snap.json(layout.shared_path(snap, "workspace.json")), "revision": snap.revision,
                "access": self.local()["workspaces"][workspace]}

    def layout_plan(self, workspace, agent_ids=None):
        return migration.plan(self, workspace, agent_ids)

    def layout_migrate(self, workspace, request_id, *, agent_ids=None, migrate_shared=False, compatible_writers=None):
        return migration.migrate(self, workspace, request_id, agent_ids=agent_ids,
                                 migrate_shared=migrate_shared, compatible_writers=compatible_writers)

    def relation(self, workspace, kind, operation, alias=None, address=None, content=""):
        if kind not in ("friends", "projects"):
            raise Error("Unknown relation kind.")
        store = self.store(workspace)
        snap = store.snapshot()
        meta = snap.json(layout.shared_path(snap, "workspace.json"))
        if operation == "list":
            return meta[kind]
        slug(alias)
        if operation == "remove":
            meta[kind].pop(alias, None)
        elif operation == "add":
            if not address:
                raise Error("An address is required.")
            local = Path(address).expanduser().exists()
            if kind == "friends":
                target = open_store(str(Path(address).expanduser().resolve()) if local else address, self.home)
                target_snapshot = target.snapshot()
                target_meta = target_snapshot.json(layout.shared_path(target_snapshot, "workspace.json"))
                if not target_meta:
                    raise Error("Friend must be an initialized workspace.")
                locator = target_meta["locator"]
                if locator == meta["locator"]:
                    raise Error("Distinct local Workspaces need distinct names; do not register an ambiguous self-friend.")
                meta[kind][alias] = {"locator": locator, "content": content}
                if not local:
                    meta[kind][alias]["address"] = address
            else:
                meta[kind][alias] = {"content": content}
                if not local:
                    meta[kind][alias]["address"] = address
            if local:
                def edit(value):
                    entry = value["workspaces"][workspace]
                    entry.setdefault("paths", {})[kind + "/" + alias] = str(Path(address).expanduser().resolve())
                self.change_local(edit)
        else:
            raise Error("Expected add, list or remove.")
        revision = store.change("main", {layout.shared_path(snap, "workspace.json"): encode(meta)},
                                layout.expected(snap, {layout.shared_path(snap, "workspace.json"): snap.entries[layout.shared_path(snap, "workspace.json")]}), f"{operation} {kind}/{alias}")
        return {"relations": meta[kind], "revision": revision}

    def friend_store(self, workspace, alias):
        snap = self.store(workspace).snapshot()
        meta = snap.json(layout.shared_path(snap, "workspace.json"))
        friend = meta["friends"].get(alias)
        if friend is None:
            raise Error(f"No friend named {alias}.")
        entry = self.local()["workspaces"][workspace]
        address = entry.get("paths", {}).get("friends/" + alias) or friend.get("address")
        if not address:
            raise Error("This friend requires a local path mapping in this environment.")
        store = open_store(address, self.home)
        other_snapshot = store.snapshot()
        other = other_snapshot.json(layout.shared_path(other_snapshot, "workspace.json"))
        if other["locator"] != friend["locator"]:
            raise Conflict("Friend address now resolves to another workspace.")
        if meta["locator"] not in [v["locator"] for v in other["friends"].values()]:
            raise Error("The other workspace has not registered this workspace as a friend.")
        return store, other

    def agent(self, workspace, agent_id, snapshot=None, worker_id=None):
        slug(agent_id)
        snap = snapshot or self.store(workspace).snapshot()
        item = snap.json(layout.shared_path(snap, f"agents/{agent_id}.json"))
        if item is None:
            raise Error(f"Unknown agent {agent_id} in {workspace}.")
        if workers.enabled(snap, item):
            worker = self.worker(workspace, agent_id, worker_id, snapshot=snap)
            return {**item, 'worker_id': worker['id'], 'worker': worker,
                    'current': worker['current'], 'has_run': worker['has_run'], 'handoff': worker['handoff']}
        if worker_id is not None:
            raise layout.MigrationRequired('Explicitly migrate this Agent before selecting a Worker.')
        return item

    def worker(self, workspace, agent_id, worker_id=None, snapshot=None):
        return workers.get(self, workspace, agent_id, worker_id, snapshot)

    def workers(self, workspace, agent_id, archived=None, snapshot=None):
        return workers.list_workers(self, workspace, agent_id, archived, snapshot)

    def worker_create(self, workspace, agent_id, name, description='', worker_id=None, background='', references=None, binding=None, request_id=None):
        return workers.create(self, workspace, agent_id, name, description, worker_id, background, references, binding, request_id)

    def worker_update(self, workspace, agent_id, worker_id, revision, **changes):
        return workers.update(self, workspace, agent_id, worker_id, revision, **changes)

    def worker_default(self, workspace, agent_id, worker_id, revision):
        return workers.set_default(self, workspace, agent_id, worker_id, revision)

    def worker_archive(self, workspace, agent_id, worker_id, archived=True):
        return workers.archive(self, workspace, agent_id, worker_id, archived)

    def legacy_worker(self, workspace, agent_id, kind, identifier, snapshot=None):
        return workers.legacy_worker(self, workspace, agent_id, kind, identifier, snapshot)

    def binding_worker(self, workspace, agent_id, entry, snapshot=None):
        return workers.binding_worker(self, workspace, agent_id, entry, snapshot or self.store(workspace).snapshot())

    def workers_migrate(self, workspace, agent_id, worker_id, request_id, **options):
        return migration.workers_migrate(self, workspace, agent_id, worker_id, request_id, **options)

    def agents(self, workspace, archived=None, *, snapshot=None):
        snap = snapshot or self.store(workspace).snapshot()
        items = [self.agent(workspace, snap.json(p)['id'], snap) for p in snap.entries
                 if p.startswith(layout.shared_path(snap, "agents/")) and p.endswith(".json")]
        return [a for a in items if archived is None or a["archived"] == archived]

    def require_binding(self, workspace, agent_id, binding, *, allow_stopping=False, snapshot=None, worker_id=None):
        snap = snapshot or self.store(workspace).snapshot()
        if not binding:
            raise Conflict("This is not the agent's current execution entry. Do not resume an old session.")
        entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
        if not isinstance(entry, dict) or entry.get("id") != binding or entry.get("agent") != agent_id:
            raise Error("Binding record does not belong to this execution entry.")
        actual_worker = self.binding_worker(workspace, agent_id, entry, snap)
        if worker_id is not None and actual_worker != worker_id:
            raise Conflict('Binding belongs to another Worker; the Agent ID does not grant its execution rights.')
        agent = self.agent(workspace, agent_id, snap, worker_id=actual_worker)
        if not binding or agent['current'] != binding or agent['archived'] or agent.get('worker', {}).get('archived'):
            raise Conflict("This is not the agent's current execution entry. Do not resume an old session.")
        if entry["phase"] != "active" and not (allow_stopping and entry["phase"] == "stopping"):
            raise Conflict(f"Entry is {entry['phase']}; it cannot perform this operation.")
        return agent, entry

    def _resources(self, root=None):
        return layout.resource_files(root)

    def _registration(self, snap, item):
        path = layout.shared_path(snap, f"agents/{item['id']}.json")
        changes = {path: encode(item)}
        if item.get('worker_schema') == 1:
            worker = workers.record(item['id'], item['default_worker'], '日常工作', item['description'] or '本 Agent 的日常工作')
            worker['created_at'] = item['created_at']
            changes[workers.path(snap, item['id'], item['default_worker'])] = encode(worker)
        return changes

    def _definition(self, workspace, definition, revision=None, *, root=None):
        prefix = relpath(definition).rstrip("/")
        snap = self.store(workspace).snapshot(revision=revision)
        selected = snap.all(prefix + "/")
        if not selected and prefix in snap.entries:
            selected = {prefix: snap.bytes(prefix)}
        result, mapping = {}, {}
        for origin, data in selected.items():
            relative = origin[len(prefix) + 1:] if origin != prefix else "definition.md"
            target = "AGENTS.md" if relative in ("definition.md", "AGENTS.md") else relative
            if target.startswith("skills/"):
                target = ".agents/" + target
            if target in ('runtime.json', '.agentworkspace/config.json'):
                destination = root if root is not None else {layout.MARKER: layout.marker('instance')}
                target = layout.instance_relpath(destination, 'config.json')
            relpath(target)
            if (target.startswith('.aw/') or target == 'source.json'
                    or target.startswith('.agentworkspace/') and target != '.agentworkspace/config.json'):
                raise Error("Definition cannot replace platform metadata.")
            result[target] = data
            mapping[target] = {"path": origin, "hash": digest(data)}
        if "AGENTS.md" not in result:
            raise Error("Definition must include a responsibility file (definition.md or AGENTS.md).")
        return result, {"definition": prefix, "revision": snap.revision, "files": mapping}

    def create(self, workspace, name, description="", agent_id=None, directory=None,
               definition=None, revision=None, import_directory=None, assets=None, request_id=None, skills=None):
        skills = shared_skills.names(skills)
        if request_id and (not agent_id or import_directory):
            raise Error("Resumable creation needs an explicit agent ID and does not support file import.")
        creation = None
        if request_id:
            creation = {"request_id": slug(request_id), "fingerprint": digest(encode({
                "name": name, "description": description, "definition": definition, "revision": revision, **({"skills": skills} if skills else {})}))}
        agent_id = slug(agent_id or (name if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", name) else uid("a")))
        store = self.store(workspace)
        snap = store.snapshot()
        location_target = directory
        existing = snap.json(layout.shared_path(snap, f"agents/{agent_id}.json"))
        if existing:
            if creation is None or existing.get("creation") != creation:
                raise Conflict("Agent ID already exists. Connect to it; do not create a duplicate.")
            return {**existing, **self.connect_agent(workspace, agent_id, location_target)}
        branch = "instance/" + agent_id
        if creation is not None:
            previous = store.snapshot(branch)
            if previous.revision:
                saved = previous.json(layout.instance_relpath(previous, "creation.json"), {})
                identity = previous.json(layout.instance_relpath(previous, "identity.json"), {})
                if (saved.get("creation") != creation or saved.get("id") != agent_id
                        or identity != {"workspace": snap.json(layout.shared_path(snap, "workspace.json"))["locator"], "agent": agent_id}):
                    raise Conflict("Existing branch does not belong to this creation request.")
                # Resume only registration of this exact saved creation; never replace assets.
                changes = self._registration(snap, saved)
                store.change("main", changes, layout.expected(snap, {p: None for p in changes}), f"Register {agent_id}")
                return {**saved, **self.connect_agent(workspace, agent_id, location_target)}
        content = self._resources()
        content[layout.MARKER] = layout.marker('instance')
        content["AGENTS.md"] = f"# {name}\n\n{description or '职责待使用者逐步完善。'}\n\n工作根为本目录。平台操作参见 `.agents/skills/`；不要将没有收到的任务当作默认任务。\n".encode()
        if definition:
            selected, source = self._definition(workspace, definition, (revision or snap.revision) if skills else revision)
            for path in selected:
                if path in content and path != "AGENTS.md":
                    raise Conflict(f"Definition overlaps a bundled platform skill: {path}")
            content.update(selected)
            content[layout.instance_relpath(content, "source.json")] = encode(source)
        if import_directory:
            if not assets:
                raise Error("Import requires an explicit list of relative asset paths; the source is never modified.")
            root = Path(import_directory).expanduser().resolve()
            for name_in_source in assets:
                source_path = inside(root, name_in_source)
                if source_path.is_symlink() or not source_path.is_file():
                    raise Error("Import selects regular files only; inspect directories before selecting assets.")
                target = relpath(name_in_source)
                if target.startswith((".aw/", '.agentworkspace/')) or (target in content and target != "AGENTS.md"):
                    raise Conflict(f"Import overlaps managed content: {target}")
                content[target] = source_path.read_bytes()
        if skills:
            shared_skills.seed(shared_skills.snapshot(self, workspace, revision or snap.revision), skills, content)
        content[layout.instance_relpath(content, "identity.json")] = encode({"workspace": snap.json(layout.shared_path(snap, "workspace.json"))["locator"], "agent": agent_id})
        item = {"id": agent_id, "name": name, "description": description, "branch": branch,
                "archived": False, "current": None, "has_run": False, "handoff": None,
                "created_at": now()}
        if layout.version(snap, 'workspace') == layout.WORKER_VERSION:
            item.update(worker_schema=1, default_worker='default')
            for key in ('current', 'has_run', 'handoff'):
                item.pop(key)
            content[layout.MARKER] = layout.marker('instance', version=layout.WORKER_VERSION)
        if creation is not None:
            item["creation"] = creation
            content[layout.instance_relpath(content, "creation.json")] = encode(item)
        layout.add_git_excludes(content)
        sha = store.branch(branch, content)
        registration = self._registration(snap, item)
        store.change("main", registration, layout.expected(snap, {p: None for p in registration}),
                     f"Register {agent_id}")
        try:
            location = self.connect_agent(workspace, agent_id, location_target)
        except Exception as exc:
            raise Error(f"Agent {agent_id} and branch {sha} are saved; directory preparation failed. Use agent connect. {exc}") from exc
        return {**item, **location}

    def root(self, workspace, agent_id, directory=None):
        locations = self.local()["workspaces"][workspace].get("instances", {}).get(agent_id, [])
        if directory is not None:
            selected = str(Path(directory).expanduser().resolve())
            if selected not in locations:
                raise Error("Directory has not been connected to this instance.")
        elif locations:
            selected = locations[0]
        else:
            raise Error("No instance directory here; run agent connect first.")
        return Path(selected)

    def _default_instance_directory(self, workspace, agent_id):
        address = self.local()["workspaces"][workspace]["address"]
        workspace_root = Path(address) if Path(address).is_dir() else self.home / 'workspaces' / workspace
        return workspace_root / '.agentworkspace/local/worktrees' / agent_id

    def prepare_agent_directory(self, workspace, agent_id, directory=None):
        item = self.agent(workspace, agent_id)
        locations = self.local()["workspaces"][workspace].get("instances", {}).get(agent_id, [])
        selected = directory if directory is not None else (locations[0] if locations else self._default_instance_directory(workspace, agent_id))
        root = Path(selected).expanduser().resolve()
        locator = self.local()["workspaces"][workspace]["locator"]
        address = self.local()["workspaces"][workspace]["address"]
        with locked(self.home / 'directory-preparations' / (digest(str(root).encode()) + '.lock')):
            existing = read_json(layout.local_path(root, "context.json"))
            repository = instance_worktrees.repository(root, address, self.home, item['branch'])
            if existing:
                identity = read_json(layout.instance_path(root, 'identity.json'))
                if (not isinstance(identity, dict) or (existing["locator"], existing["agent"]) != (locator, agent_id)
                        or identity['workspace'] != locator or identity['agent'] != agent_id):
                    raise Conflict("Directory belongs to another instance.")
                if item.get('worker_schema') == 1 and layout.version(root, 'instance') != layout.WORKER_VERSION:
                    raise layout.MigrationRequired('This registered copy has not adopted the Worker format; preserve it and finish its explicit migration.')
                revision = existing['revision']
            else:
                if root.exists() and any(root.iterdir()) and repository is None:
                    raise Conflict("Use an empty directory. To adopt an external agent, select its assets with agent import.")
                if repository:
                    identity = read_json(layout.instance_path(root, 'identity.json'))
                    if not isinstance(identity, dict) or identity.get('workspace') != locator or identity.get('agent') != agent_id:
                        raise Conflict('The actual directory identity differs from its Git branch; it was preserved.')
                snap = (repository.snapshot(revision=instance_worktrees.head(root)) if repository
                        else self.store(workspace).snapshot(item["branch"]))
                identity = snap.json(layout.instance_relpath(snap, 'identity.json'))
                if not isinstance(identity, dict) or identity.get('workspace') != locator or identity.get('agent') != agent_id:
                    raise Conflict('The saved branch belongs to another instance; no directory was prepared.')
                if item.get('worker_schema') == 1 and layout.version(snap, 'instance') != layout.WORKER_VERSION:
                    raise layout.MigrationRequired('A Worker copy must come from its saved Worker-version material.')
                content = snap.all()
                context = {"workspace": workspace, "locator": locator, "agent": agent_id, "revision": snap.revision,
                           "saved": {p: digest(data) for p, data in content.items()}, "exclude": DEFAULT_EXCLUDES}
                root.parent.mkdir(parents=True, exist_ok=True)
                if layout.version(snap, 'instance'):
                    self._check_tracked_local(snap)
                    if repository is None:
                        repository = instance_worktrees.prepare(root, address, self.home, item['branch'], snap.revision)
                    write_json(layout.local_path(root, "context.json"), context)
                else:
                    # Preserve the legacy ordinary-copy path; preparation does not migrate layouts.
                    with tempfile.TemporaryDirectory(prefix=".aw-connect-", dir=root.parent) as temporary:
                        staged = Path(temporary) / "instance"
                        staged.mkdir()
                        for path, data in content.items():
                            write_bytes(inside(staged, path), data)
                        write_json(layout.local_path(staged, "context.json"), context)
                        if root.exists():
                            root.rmdir()
                        staged.rename(root)
                revision = snap.revision
            def register(value):
                locations = value["workspaces"][workspace].setdefault("instances", {}).setdefault(agent_id, [])
                if str(root) not in locations:
                    locations.append(str(root))
            self.change_local(register)
        return {"workspace": workspace, "agent_id": agent_id, "branch": item['branch'],
                "directory": str(root), "revision": revision, "worktree": bool(repository and (root / '.git').is_file()),
                "prepared": existing is None, "instructions": str(root / 'AGENTS.md')}

    def connect_agent(self, workspace, agent_id, directory=None):
        result = self.prepare_agent_directory(workspace, agent_id, directory)
        root = Path(result['directory'])
        if layout.version(root, 'instance'):
            software.update_instance(self, workspace, agent_id, str(root))
        return result

    def collect(self, root, worker_id=None, shared_paths=None):
        software.require_ready(root)
        if (layout.local_path(root, "skill-install/operation.json")).exists():
            raise Conflict("Finish or recover the pending Skill update before taking a snapshot.")
        if worker_id is not None:
            return workers.collect(self, root, worker_id, shared_paths)
        context = read_json(layout.local_path(root, "context.json"))
        excludes = context["exclude"]
        content, skipped = {}, []
        for base, directories, names in os.walk(root, followlinks=False):
            kept = []
            for name in directories:
                candidate = Path(base) / name
                relative = candidate.relative_to(root).as_posix()
                if name == '.git' or local_asset_path(relative) or any(fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(relative, pat) for pat in excludes):
                    skipped.append(relative + "/")
                elif candidate.is_symlink():
                    raise Error(f"Snapshot needs an explicit export for symlink: {relative}")
                elif (candidate / '.git').exists():
                    skipped.append(relative + '/')
                else:
                    kept.append(name)
            directories[:] = kept
            for name in names:
                candidate = Path(base) / name
                relative = candidate.relative_to(root).as_posix()
                if name == '.git' or local_asset_path(relative) or name.startswith(".aw-tmp-") or any(fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(relative, pat) for pat in excludes):
                    skipped.append(relative)
                    continue
                if candidate.is_symlink():
                    raise Error(f"Snapshot cannot silently follow symlink: {relative}")
                if candidate.stat().st_size > 50 * 1024 * 1024:
                    raise Error(f"Asset exceeds 50 MiB; store externally and record a reference: {relative}")
                content[relative] = candidate.read_bytes()
        return content, skipped

    def _check_tracked_local(self, snapshot):
        if any(local_asset_path(path) for path in snapshot.entries):
            raise Error('Local runtime data is already tracked; migrate it explicitly before saving or syncing.')

    def sync_agent(self, workspace, agent_id, directory=None, worker_id=None, shared_paths=None):
        root = Path(self.prepare_agent_directory(workspace, agent_id, directory)['directory'])
        item = self.agent(workspace, agent_id, worker_id=worker_id)
        if item.get('worker_id') is not None:
            return workers.sync(self, workspace, agent_id, root, item['worker_id'], shared_paths)
        with layout.lock(root, "files.lock"):
            context = read_json(layout.local_path(root, "context.json"))
            local, _ = self.collect(root)
            branch = self.agent(workspace, agent_id)['branch']
            repository = instance_worktrees.repository(root, self.local()['workspaces'][workspace]['address'], self.home, branch)
            store = repository or self.store(workspace)
            snap = store.snapshot(branch)
            if repository:
                before = instance_worktrees.head(root)
                instance_worktrees.check_index(root)
                if not store.contains_commit(context['revision'], before):
                    raise Conflict('The local Git history no longer continues this copy; no files were changed.')
                saved = store.snapshot(revision=before)
                self._check_tracked_local(saved)
                context.update(revision=before, saved={p: digest(data) for p, data in saved.all().items()})
                if store.contains_commit(snap.revision, before):
                    snap = saved
                elif not store.contains_commit(before, snap.revision):
                    raise Conflict('Local and remote Git histories diverged; preserve both and resolve them before syncing.')
            self._check_tracked_local(snap)
            if layout.version(root, 'instance') != layout.version(snap, 'instance'):
                raise layout.MigrationRequired('Continue the explicit layout migration before synchronizing this copy.')
            remote = snap.all()
            for path in set(context["saved"]) | set(remote):
                previous = context["saved"].get(path)
                actual = digest(local[path]) if path in local else None
                desired = digest(remote[path]) if path in remote else None
                if actual != previous and desired != previous and actual != desired:
                    raise Conflict(f"Local and remote edits overlap: {path}. No file was changed.")
            if repository and before != snap.revision:
                instance_worktrees.git(root, 'read-tree', '-m', before, snap.revision)
            for path in set(context["saved"]) | set(remote):
                previous = context["saved"].get(path)
                desired = digest(remote[path]) if path in remote else None
                if desired == previous:
                    continue
                target = inside(root, path)
                if path in remote:
                    write_bytes(target, remote[path])
                elif target.exists():
                    target.unlink()
            if repository:
                instance_worktrees.git(root, 'update-ref', 'refs/heads/' + branch, snap.revision, before)
            context.update(revision=snap.revision, saved={p: digest(v) for p, v in remote.items()})
            write_json(layout.local_path(root, "context.json"), context)
            return {"revision": snap.revision, "directory": str(root)}

    def _save_files(self, workspace, agent_id, root, extra=None, message="Save instance assets", worker_id=None, shared_paths=None):
        if layout.version(root, 'instance') == layout.WORKER_VERSION:
            if worker_id is None:
                raise Error('Worker saves require an explicit execution scope and common file selection.')
            return workers.save_files(self, workspace, agent_id, root, worker_id, extra, message, shared_paths)
        context = read_json(layout.local_path(root, "context.json"))
        content, skipped = self.collect(root)
        content.update(extra or {})
        store = self.store(workspace)
        branch = self.agent(workspace, agent_id)["branch"]
        repository = instance_worktrees.repository(root, self.local()['workspaces'][workspace]['address'], self.home, branch)
        if repository:
            store = repository
            before = instance_worktrees.head(root)
            staged = instance_worktrees.check_index(root)
            if any(path not in content and (root / path).exists() for path in staged):
                raise Conflict('A staged asset is excluded from this save; its index and working files were preserved.')
            if not store.contains_commit(context['revision'], before):
                raise Conflict('The local Git history no longer continues this copy; no assets were published.')
            remote = store.head(branch)
            if not store.contains_commit(remote, before):
                raise Conflict('The remote branch changed; sync or resolve the worktree before saving.')
            previous = store.snapshot(revision=before)
        else:
            previous = store.snapshot(branch, revision=context["revision"])
        self._check_tracked_local(previous)
        changes = {p: None for p in previous.entries if p not in content}
        changes.update({p: data for p, data in content.items() if previous.bytes(p) != data})
        if repository:
            sha = store.commit(before, changes, message) if changes else before
            if sha != remote:
                store.publish(branch, sha, remote)
        else:
            sha = store.change(branch, changes, {}, message, base=context["revision"]) if changes else context["revision"]
        for path, data in (extra or {}).items():
            write_bytes(inside(root, path), data)
        if repository:
            instance_worktrees.record_saved(root, branch, before, sha)
        context.update(revision=sha, saved={p: digest(v) for p, v in content.items()})
        write_json(layout.local_path(root, "context.json"), context)
        return sha, skipped

    def checkpoint(self, workspace, agent_id, summary, content="", binding=None, directory=None,
                   checkpoint_id=None, references=None, worker_id=None, shared_paths=None):
        item = self.agent(workspace, agent_id, worker_id=worker_id)
        if item.get('worker_id') is not None:
            return workers.checkpoint(self, workspace, agent_id, summary, content, binding, directory,
                                      checkpoint_id, references, worker_id, shared_paths)
        entry = None
        if item["current"] or binding:
            item, entry = self.require_binding(workspace, agent_id, binding, allow_stopping=True)
        root = Path(self.prepare_agent_directory(workspace, agent_id, directory)['directory'])
        cp = slug(checkpoint_id or uid("c"))
        store = self.store(workspace)
        snap = store.snapshot()
        index = layout.shared_path(snap, f"checkpoints/{agent_id}/{cp}.json")
        found = snap.json(index)
        if found:
            saved = store.snapshot(revision=found["revision"]).json(found["path"])
            if (saved["summary"], saved["content"]) != (summary, content):
                raise Conflict("Checkpoint ID is immutable and already has different content.")
            return found
        with layout.lock(root, "files.lock"):
            receipt_path = layout.local_path(root, "checkpoint-operations") / f"{cp}.json"
            pending = read_json(receipt_path)
            if pending:
                saved = store.snapshot(revision=pending["revision"]).json(pending["path"])
                if (saved["summary"], saved["content"]) != (summary, content):
                    raise Conflict("Pending checkpoint has different content.")
                store.change("main", {index: encode(pending)}, layout.expected(snap, {index: None}), f"Register checkpoint {cp}")
                return pending
            if (layout.instance_path(root, f"checkpoints/{cp}.json")).exists():
                raise Conflict("Checkpoint file already exists without a publication receipt; inspect its saved revision before continuing.")
            record = {"id": cp, "created_at": now(), "summary": summary, "content": content,
                      "origin": {"workspace": workspace,
                                 "workspace_locator": self.local()["workspaces"][workspace]["locator"],
                                 "agent": agent_id, "instance_branch": item["branch"],
                                 "instance_root": str(root), "instructions_file": str(root / "AGENTS.md"),
                                 "binding": entry["id"] if entry else None,
                                 "session": entry["session"] if entry else None,
                                 "runtime_kind": entry["kind"] if entry else None,
                                 "native_cwd": entry.get("execution", {}).get("cwd") if entry else None},
                      "record_refs": references or [], "scope": "Saved instance files; external/runtime-unavailable state is not implied."}
            point_path = layout.instance_relpath(root, f'checkpoints/{cp}.json')
            sha, skipped = self._save_files(workspace, agent_id, root,
                {point_path: encode(record)}, f"Checkpoint {cp}")
            pointer = {"id": cp, "agent": agent_id, "revision": sha, "path": point_path,
                       "created_at": record["created_at"], "excluded": skipped}
            write_json(receipt_path, pointer)
            store.change("main", {index: encode(pointer)}, layout.expected(snap, {index: None}), f"Register checkpoint {cp}")
        return pointer

    def checkpoints(self, workspace, agent_id, worker_id=None):
        snap = self.store(workspace).snapshot()
        agent = self.agent(workspace, agent_id, snap, worker_id=worker_id)
        worker_id = agent.get('worker_id')
        prefix = layout.shared_path(snap, f"checkpoints/{agent_id}/")
        selected = []
        for path in snap.entries:
            if not path.startswith(prefix):
                continue
            point = snap.json(path)
            if worker_id is not None:
                owner = point.get('worker') or self.legacy_worker(workspace, agent_id, 'checkpoints', point['id'], snap)
                if owner != worker_id:
                    continue
            selected.append(point)
        return sorted(selected,
                      key=lambda p: p["created_at"])

    def checkpoint_show(self, workspace, agent_id, checkpoint, worker_id=None):
        store = self.store(workspace)
        snap = store.snapshot()
        item = self.agent(workspace, agent_id, snap, worker_id=worker_id)
        return self._read_checkpoint(store, snap, agent_id, checkpoint, item.get('worker_id'))

    def _read_checkpoint(self, store, shared, agent_id, checkpoint, worker_id=None):
        checkpoint = slug(checkpoint)
        pointer = shared.json(workers.checkpoint_index(shared, agent_id, checkpoint, worker_id))
        if pointer is None and worker_id is not None:
            legacy = shared.json(workers.checkpoint_index(shared, agent_id, checkpoint))
            if legacy is not None:
                mapping = shared.json(layout.shared_path(shared, f'worker-mappings/{agent_id}.json'), {})
                if mapping.get('checkpoints', {}).get(checkpoint) != worker_id:
                    raise Conflict('This legacy checkpoint belongs to another or unmapped Worker.')
                pointer = legacy
        if pointer is None:
            raise Error("Unknown saved checkpoint.")
        if (not isinstance(pointer, dict) or pointer.get("id") != checkpoint or pointer.get("agent") != agent_id
                or not pointer.get("revision")):
            raise Error("Saved checkpoint reference does not match this instance and checkpoint.")
        snap = store.snapshot(revision=pointer["revision"])
        if pointer.get('worker') is not None and pointer['worker'] != worker_id:
            raise Conflict('Checkpoint belongs to another Worker.')
        if pointer.get('path') != layout.instance_relpath(snap, f'checkpoints/{checkpoint}.json', pointer.get('worker')):
            raise Error('Saved checkpoint path does not match its original layout.')
        identity = snap.json(layout.instance_relpath(snap, "identity.json"))
        if (not isinstance(identity, dict) or identity.get("agent") != agent_id
                or identity.get("workspace") != shared.json(layout.shared_path(shared, "workspace.json"))["locator"]):
            raise Error("Saved checkpoint material belongs to a different instance or workspace.")
        record = snap.json(pointer["path"])
        if not isinstance(record, dict) or record.get("id") != checkpoint:
            raise Error("Saved checkpoint material is missing or does not match its reference.")
        if pointer.get('worker') is not None and (record.get('worker') != worker_id or record.get('origin', {}).get('worker') != worker_id):
            raise Error('Worker checkpoint content and its immutable reference disagree about ownership.')
        return {**pointer, "record": record, "files": pointer.get('material_paths', list(snap.entries))}

    def _fork_files(self, store, source, point, shared, agent_id):
        if point.get('worker') is None:
            source_files = source.all()
            owned = migration.owned_instance_files(source_files, shared, agent_id)
            return migration.instance_files(source_files, owned=owned)[0]
        result = {}
        for path, sha in point['record']['common_versions'].items():
            relpath(path)
            if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', sha) or path.startswith(('workers/', '.agentworkspace/workers/')):
                raise Error('Fork common-material references do not match the saved checkpoint.')
            result[path] = store.blob(sha)
        for path in point['material_paths']:
            if not workers.owns(path, point['worker']):
                # These common files were explicitly selected in this checkpoint.
                if path.startswith(('workers/', '.agentworkspace/workers/')):
                    raise Error('Fork checkpoint includes another Worker material scope.')
            result[path] = source.bytes(path)
        return result

    def fork(self, workspace, agent_id, checkpoint, name, new_id=None, directory=None, *, resume=False, worker_id=None):
        point = self.checkpoint_show(workspace, agent_id, checkpoint, worker_id=worker_id)
        target = slug(new_id or name)
        store = self.store(workspace)
        snap = store.snapshot()
        source_worker = self.agent(workspace, agent_id, snap, worker_id=worker_id).get('worker_id')
        source = store.snapshot(revision=point["revision"])
        locator = snap.json(layout.shared_path(snap, "workspace.json"))["locator"]
        branch = "instance/" + target
        agent_path = layout.shared_path(snap, f"agents/{target}.json")
        origin = {"agent": agent_id, "checkpoint": point["id"], "revision": source.revision}
        if source_worker is not None:
            origin['worker'] = source_worker
        identity = {"workspace": locator, "agent": target, "forked_from": origin}
        receipt_path = self.home / "fork-operations" / digest(encode([locator, target])) / "operation.json"
        location = directory
        with locked(receipt_path.with_suffix(".lock")):
            receipt = read_json(receipt_path)
            existing = store.snapshot().json(agent_path)
            if not resume:
                if existing or receipt:
                    raise Conflict("Fork target already exists or has a pending operation; explicitly resume the original Fork.")
                item = {"id": target, "name": name, "description": "", "branch": branch,
                        "archived": False, "current": None, "has_run": False, "handoff": None,
                        "created_at": now(), "forked_from": origin}
                if layout.version(snap, 'workspace') == layout.WORKER_VERSION:
                    item.update(worker_schema=1, default_worker=source_worker or 'default')
                    for key in ('current', 'has_run', 'handoff'):
                        item.pop(key)
                content = self._fork_files(store, source, point, snap, agent_id)
                content[layout.MARKER] = layout.marker('instance', version=layout.WORKER_VERSION if item.get('worker_schema') else layout.VERSION)
                content[layout.instance_relpath(content, "identity.json")] = encode(identity)
                content[layout.instance_relpath(content, "fork.json")] = encode(item)
                receipt = {"fingerprint": digest(encode(item)), "registration_unknown": False}
                # Retain the original target even if branch publication loses its reply.
                write_json(receipt_path, receipt)
                try:
                    store.branch(branch, content, parent=source.revision)
                except Uncertain:
                    raise
                except Error:
                    receipt_path.unlink()
                    raise
            else:
                saved = store.snapshot(branch)
                if not saved.revision:
                    raise Uncertain("The original Fork branch is not confirmed; do not create it again.")
                item = saved.json(layout.instance_relpath(saved, "fork.json"), {})
                if (not isinstance(item, dict) or item.get("id") != target or item.get("branch") != branch
                        or item.get("name") != name or item.get("forked_from") != origin
                        or saved.json(layout.instance_relpath(saved, "identity.json")) != identity
                        or (receipt and receipt["fingerprint"] != digest(encode(item)))):
                    raise Conflict("Saved target does not belong to this Fork and checkpoint revision.")
                if existing:
                    if (existing.get("id") != target or existing.get("branch") != branch
                            or existing.get("forked_from") != origin
                            or existing.get("created_at") != item.get("created_at")):
                        raise Conflict("Registered target belongs to another Fork identity.")
                    return {**existing, **self.connect_agent(workspace, target, location)}
                # Until registration, the target must still contain exactly the saved starting files.
                content = self._fork_files(store, source, point, snap, agent_id)
                content[layout.MARKER] = layout.marker('instance', version=layout.WORKER_VERSION if item.get('worker_schema') else layout.VERSION)
                content[layout.instance_relpath(content, "identity.json")] = encode(identity)
                content[layout.instance_relpath(content, "fork.json")] = encode(item)
                if saved.all() != content:
                    raise Conflict("Unregistered Fork files changed; inspect the original target before continuing.")
                if receipt and receipt["registration_unknown"]:
                    raise Uncertain("Original Fork registration is still unconfirmed; do not publish it again.")
                receipt = {"fingerprint": digest(encode(item)), "registration_unknown": False}
            # A crash or an unknown write result leaves this marker until the original record is read back.
            receipt["registration_unknown"] = True
            write_json(receipt_path, receipt)
            try:
                registration = self._registration(snap, item)
                store.change("main", registration, layout.expected(snap, {p: None for p in registration}), f"Fork {target}")
            except Uncertain:
                raise
            except Error:
                receipt["registration_unknown"] = False
                write_json(receipt_path, receipt)
                raise
            receipt["registration_unknown"] = False
            write_json(receipt_path, receipt)
            return {**item, **self.connect_agent(workspace, target, location)}

    def configure(self, workspace, agent_id, value, directory=None, worker_id=None):
        root = self.root(workspace, agent_id, directory)
        if value.get("kind", "manual") not in ("manual", "desktop", "codex", "claude", "codebuddy"):
            raise Error("Runtime kind must be manual, desktop, codex, claude or codebuddy.")
        if worker_id is not None:
            self.worker(workspace, agent_id, worker_id)
            workers.prepare_context(self, workspace, agent_id, root, worker_id)
            if value.get('kind') in model_profiles.CODEX_KINDS:
                local, choice, _ = model_profiles.split_config(value)
                if choice:
                    choice = model_profiles.validate(choice)
            else:
                local, choice = dict(value), None
            with layout.lock(root, 'files.lock'):
                portable_path = layout.instance_path(root, 'config.json', worker_id)
                portable = read_json(portable_path, {})
                portable['kind'] = local.get('kind', 'manual')
                if choice:
                    portable['codex'] = choice
                write_json(portable_path, portable)
                write_json(layout.local_path(root, 'runtime.json', worker_id), local)
            return {'configured': True, 'worker': worker_id, 'entry_changed': False}
        if value.get("kind") in model_profiles.CODEX_KINDS:
            model_profiles.configure(root, value)
        else:
            with layout.lock(root, "files.lock"):
                write_json(layout.local_path(root, "runtime.json"), value)
        return {"configured": True, "entry_changed": False}

    def _binding_history(self, snap, agent_id, worker_id=None, workspace=None):
        entries = []
        for path in snap.entries:
            if path.startswith(layout.shared_path(snap, "bindings/")) and path.endswith(".json"):
                entry = snap.json(path)
                if entry["agent"] == agent_id and (worker_id is None or self.binding_worker(workspace, agent_id, entry, snap) == worker_id):
                    entries.append(entry)
        return sorted(entries, key=lambda entry: (entry["created_at"], entry["id"]))

    def history(self, workspace, agent_id, *, snapshot=None, worker_id=None):
        snap = snapshot or self.store(workspace).snapshot()
        self.agent(workspace, agent_id, snap, worker_id=worker_id)
        return {"agent": agent_id, "bindings": self._binding_history(snap, agent_id, worker_id, workspace),
                "snapshot_revision": snap.revision}

    def _observe_copy(self, root, binding, installation, worker_id=None):
        source = {"installation_id": installation, "directory": str(root), "kind": "local_copy"}
        if not root.is_dir():
            return {"directory": str(root), "observation_source": source,
                    "unknown_reason": "directory_missing",
                    "observation_error": "The registered material directory is missing; prepare its saved copy before observing local state."}
        try:
            if not layout.local_path(root, 'context.json').is_file():
                return {"directory": str(root), "observation_source": source,
                        "unknown_reason": "copy_not_prepared",
                        "observation_error": "The registered copy has no local context; prepare its saved material before observing local state."}
            if worker_id is not None and not layout.local_path(root, 'context.json', worker_id).is_file():
                return {'directory': str(root), 'observation_source': source, 'unknown_reason': 'worker_copy_not_prepared',
                        'observation_error': 'This Worker has no prepared local context; no runtime state was created.'}
            local_entry = read_json(layout.local_path(root, "entry.json", worker_id), {})
            status = read_json(layout.local_path(root, "status.json", worker_id), {"state": "not_running"})
            try:
                with layout.lock(root, "runner.lock", wait=0, worker_id=worker_id):
                    status["runner_alive"] = False
            except Conflict:
                status["runner_alive"] = True
            execution = binding.get("execution") if binding else None
            worker_config = read_json(layout.instance_path(root, 'config.json', worker_id), {}) if worker_id else {}
            desired_profile = worker_config['codex'] if 'codex' in worker_config else model_profiles.desired(root)
            return {
                "directory": str(root), "entry_binding": local_entry.get("binding"),
                "entry_matches_current": bool(binding and local_entry.get("binding") == binding["id"]),
                # Runner lifecycle status identifies its Binding; session is optional, but must match when present.
                "runtime_matches_current": bool(binding and status.get("binding") == binding["id"]
                                                 and ("session" not in status or status["session"] == binding.get("session"))),
                "execution_matches_local": bool(execution and execution["installation_id"] == installation
                                                 and execution["directory"] == str(root)),
                "runtime": status,
                "watch": read_json(layout.local_path(root, "watch.json", worker_id), {"enabled": False}),
                "configured_kind": read_json(layout.local_path(root, "runtime.json", worker_id), {}).get("kind", "manual"),
                "model_selection": desired_profile,
                "observation_source": source,
            }
        except (Error, ValueError, OSError, KeyError) as exc:
            return {"directory": str(root), "observation_source": source,
                    "unknown_reason": "local_copy_observation_failed",
                    "observation_error": f"Local copy observation failed ({type(exc).__name__}); inspect its local files."}

    def show(self, workspace, agent_id, directory=None, *, snapshot=None, worker_id=None):
        store = self.store(workspace)
        snap = snapshot or store.snapshot()
        item = self.agent(workspace, agent_id, snap, worker_id=worker_id)
        worker_id = item.get('worker_id')
        binding = snap.json(layout.shared_path(snap, f"bindings/{item['current']}.json")) if item["current"] else None
        locations = self.local()["workspaces"][workspace].get("instances", {}).get(agent_id, [])
        installation = read_json(self.home / "installation.json", {}).get("id")
        copies = [self._observe_copy(Path(location), binding, installation, worker_id) for location in locations]
        result = {**item, "revision": snap.entries[layout.shared_path(snap, f"agents/{agent_id}.json")], "binding": binding,
                  "directories": locations, "copies": copies, "history": self._binding_history(snap, agent_id, worker_id, workspace),
                  "directory": None}
        if worker_id is not None:
            result.update(workers=self.workers(workspace, agent_id, snapshot=snap),
                          worker_revision=snap.entries[workers.path(snap, agent_id, worker_id)])
        errors = [f"{copy['directory']}: {copy['observation_error']}" for copy in copies if "observation_error" in copy]
        if errors:
            result["observation_error"] = "\n".join(errors)
        selected = None
        if directory is not None:
            requested = str(self.root(workspace, agent_id, directory))
            selected = next(copy for copy in copies if copy["directory"] == requested)
        elif binding:
            for copy in copies:
                if copy.get("entry_matches_current") and (not binding.get("execution") or copy["execution_matches_local"]):
                    selected = copy
                    break
        elif copies:
            selected = copies[0]
        if selected:
            result["directory"] = selected["directory"]
            if "observation_error" in selected:
                result["runtime"] = {"state": "unknown", "reason": "local_copy_observation_failed"}
            else:
                result.update(watch=selected["watch"], configured_kind=selected["configured_kind"],
                              model_selection=selected["model_selection"])
                if not binding or (selected["entry_matches_current"] and selected["runtime_matches_current"]
                                   and (not binding.get("execution") or selected["execution_matches_local"])):
                    result["runtime"] = selected["runtime"]
        if binding and "runtime" not in result:
            result["runtime"] = {"state": "unknown", "reason": "current_entry_not_observed_locally"}
        return result

    def archive(self, workspace, agent_id, archived=True, directory=None):
        store = self.store(workspace)
        snap = store.snapshot()
        item = workers.agent_record(snap, agent_id)
        if (any(w['current'] for w in self.workers(workspace, agent_id, snapshot=snap))
                if workers.enabled(snap, item) else item['current']):
            raise Conflict("Handoff before archiving. Archive does not revoke a live entry.")
        item["archived"] = archived
        path = layout.shared_path(snap, f"agents/{agent_id}.json")
        store.change("main", {path: encode(item)}, layout.expected(snap, {path: snap.entries[path]}), f"Archive={archived} {agent_id}")
        return item

    def reserve(self, workspace, agent_id, directory=None, binding_id=None, *, expected_handoff=None, worker_id=None):
        root = self.root(workspace, agent_id, directory)
        initial = self.agent(workspace, agent_id, worker_id=worker_id)
        worker_id = initial.get('worker_id')
        if worker_id is None:
            model_profiles.migrate(root)
        else:
            workers.prepare_context(self, workspace, agent_id, root, worker_id)
        with layout.lock(root, "files.lock"):
            config = model_profiles.runtime_config(root, worker_id)
            if worker_id is not None:
                portable = read_json(layout.instance_path(root, 'config.json', worker_id), {})
                if 'kind' in portable and config['kind'] != portable['kind']:
                    raise Error('Prepare this Worker local connection for its selected Harness before reserving an entry.')
            profile = (workers.selected_profile(root, worker_id) if worker_id and config.get('kind') in model_profiles.CODEX_KINDS else
                       model_profiles.selected(root) if config.get("kind") in model_profiles.CODEX_KINDS
                       and model_profiles.desired(root) is not None else None)
            store = self.store(workspace)
            snap = store.snapshot()
            item = self.agent(workspace, agent_id, snap, worker_id=worker_id)
            path, owner, _ = workers.execution_record(self, workspace, agent_id, snap, worker_id)
            if item["current"] or item["archived"] or owner['archived']:
                raise Conflict("Agent already has an entry or is archived; relay cannot take it over.")
            # An automatic continuation must consume its verified handoff, never a later one.
            if expected_handoff is not None and item["handoff"] != expected_handoff:
                raise Conflict("The handoff selected for continuation changed; the old request cannot use its successor.")
            if item["has_run"] and not item["handoff"]:
                raise Conflict("No handoff is available. A crash is not a release of ownership.")
            binding = slug(binding_id) if binding_id else uid("b")
            entry = {"id": binding, "agent": agent_id, "kind": config.get("kind", "manual"),
                     "phase": "starting", "session": None, "created_at": now(), "handoff": item["handoff"]}
            if worker_id is not None:
                entry['worker'] = worker_id
            from .maintenance import installation_id
            entry["execution"] = {"installation_id": installation_id(self), "directory": str(root)}
            changes = {layout.shared_path(snap, f"bindings/{binding}.json"): encode(entry)}
            ap = layout.shared_path(snap, f"agents/{agent_id}.json")
            expected = {path: snap.entries[path], ap: snap.entries[ap], layout.shared_path(snap, f"bindings/{binding}.json"): None}
            if item["handoff"]:
                handoff_path = layout.shared_path(snap, f"handoffs/{item['handoff']}.json")
                handoff = snap.json(handoff_path)
                if worker_id is not None and (handoff.get('worker') or self.legacy_worker(workspace, agent_id, 'bindings', handoff['entry'], snap)) != worker_id:
                    raise Conflict('The handoff belongs to another Worker.')
                if handoff["consumed_by"]:
                    raise Conflict("Handoff already consumed.")
                handoff["consumed_by"] = binding
                expected[handoff_path] = snap.entries[handoff_path]
                changes[handoff_path] = encode(handoff)
            owner.update(current=binding, has_run=True, handoff=None)
            changes[path] = encode(owner)
            store.change("main", changes, layout.expected(snap, expected), f"Reserve entry {binding}")
            record = {"binding": binding, "config": config, **({'worker': worker_id} if worker_id else {})}
            if profile is not None:
                record.update(model_profile=profile, model_adopted_at=now())
            write_json(layout.local_path(root, "entry.json", worker_id), record)
            return {"agent": agent_id, "binding": binding, "phase": "starting", "kind": entry["kind"], **({'worker': worker_id} if worker_id else {})}

    def bind(self, workspace, agent_id, binding, session, directory=None, *, cwd=None, worker_id=None):
        slug(binding)
        if not session or len(session) > 256 or any(c in session for c in "\r\n\0"):
            raise Error("A real native session ID is required.")
        if cwd is not None and (not isinstance(cwd, str) or not cwd or any(c in cwd for c in "\r\n\0")):
            raise Error('Native cwd must be an explicit nonempty path observation.')
        store = self.store(workspace)
        snap = store.snapshot()
        path = layout.shared_path(snap, f"bindings/{binding}.json")
        entry = snap.json(path)
        if not entry or entry.get('agent') != agent_id:
            raise Conflict('Binding does not belong to this Agent.')
        actual_worker = self.binding_worker(workspace, agent_id, entry, snap)
        if worker_id is not None and actual_worker != worker_id:
            raise Conflict('Binding belongs to another Worker.')
        item = self.agent(workspace, agent_id, snap, worker_id=actual_worker)
        owner_path, _, _ = workers.execution_record(self, workspace, agent_id, snap, actual_worker)
        if item["current"] != binding or not entry or entry["phase"] != "starting":
            raise Conflict("Binding is not awaiting a new session.")
        for p in snap.entries:
            if p.startswith(layout.shared_path(snap, "bindings/")):
                previous = snap.json(p)
                if previous["kind"] == entry["kind"] and previous["session"] == session:
                    raise Conflict("A native session cannot be reused as a new execution entry.")
        entry.update(session=session, phase="active")
        if cwd is not None:
            entry['execution']['cwd'] = cwd
        session_path = layout.shared_path(snap, f"sessions/{entry['kind']}/{digest(session.encode())}.json")
        store.change("main", {path: encode(entry), session_path: encode({"agent": agent_id, "binding": binding, "session": session,
                     **({'worker': actual_worker} if actual_worker else {})})},
                     layout.expected(snap, {path: snap.entries[path], session_path: None,
                      owner_path: snap.entries[owner_path],
                      layout.shared_path(snap, f"agents/{agent_id}.json"): snap.entries[layout.shared_path(snap, f"agents/{agent_id}.json")]}), f"Bind {binding}")
        return entry

    def stop(self, workspace, agent_id, binding, checkpoint, directory=None, worker_id=None):
        root = self.root(workspace, agent_id, directory)
        with layout.lock(root, "files.lock"):
            store = self.store(workspace)
            snap = store.snapshot()
            item, entry = self.require_binding(workspace, agent_id, binding, allow_stopping=True, snapshot=snap, worker_id=worker_id)
            worker_id = item.get('worker_id')
            owner_path, _, _ = workers.execution_record(self, workspace, agent_id, snap, worker_id)
            point = self._read_checkpoint(store, snap, agent_id, checkpoint, worker_id)
            cp = workers.checkpoint_index(snap, agent_id, checkpoint, worker_id if point.get('worker') else None)
            result = {"state": "awaiting_native_idle", "binding": binding, "checkpoint": checkpoint}
            if entry["phase"] == "stopping":
                if entry["checkpoint"] != checkpoint:
                    raise Conflict("A pending stop cannot be replaced with a different checkpoint.")
                return result
            # Disable local automatic restarts before requesting the native end-of-turn observation.
            write_json(layout.local_path(root, "watch.json", worker_id), {"enabled": False, "reason": "handoff"})
            entry.update(phase="stopping", checkpoint=point["id"], stop_requested_at=now())
            path = layout.shared_path(snap, f"bindings/{binding}.json")
            store.change("main", {path: encode(entry)}, layout.expected(snap, {path: snap.entries[path],
                         cp: snap.entries[cp], owner_path: snap.entries[owner_path],
                         layout.shared_path(snap, f"agents/{agent_id}.json"): snap.entries[layout.shared_path(snap, f"agents/{agent_id}.json")]}), "Prepare handoff")
            return result

    def _released_handoff(self, snap, agent_id, binding, expected_controller, expected_checkpoint, expected_session):
        entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
        if entry is None:
            return None
        if not isinstance(entry, dict):
            raise Error("Binding record is damaged; refusing stop confirmation.")
        if entry["phase"] != "released":
            return None
        handoff_id = "h" + binding[1:]
        handoff = snap.json(layout.shared_path(snap, f"handoffs/{handoff_id}.json"))
        if (entry.get("id") != binding or entry.get("agent") != agent_id or not handoff
                or handoff.get("id") != handoff_id or handoff.get("agent") != agent_id
                or handoff.get("entry") != binding or handoff.get("checkpoint") != entry.get("checkpoint")):
            raise Error("Released entry has no matching saved handoff.")
        if expected_checkpoint is not _UNOBSERVED and entry.get("checkpoint") != expected_checkpoint:
            raise Conflict("Saved handoff belongs to a different stop checkpoint.")
        if expected_session is not _UNOBSERVED and entry.get("session") != expected_session:
            raise Conflict("Saved handoff belongs to a different native session.")
        if expected_controller is not _UNOBSERVED and entry.get("controller") != expected_controller:
            raise Conflict("Saved handoff belongs to a different controller.")
        return handoff

    def finish_stop(self, workspace, agent_id, binding, *, observed_idle,
                    expected_controller=_UNOBSERVED, expected_checkpoint=_UNOBSERVED,
                    expected_session=_UNOBSERVED, worker_id=None):
        if not observed_idle:
            raise Conflict("Native stop has not been confirmed. Entry remains owned.")
        store = self.store(workspace)
        snap = store.snapshot()
        original_entry = snap.json(layout.shared_path(snap, f'bindings/{binding}.json'))
        if original_entry and worker_id is not None and self.binding_worker(workspace, agent_id, original_entry, snap) != worker_id:
            raise Conflict('Stop observation belongs to another Worker.')
        released = self._released_handoff(snap, agent_id, binding, expected_controller, expected_checkpoint, expected_session)
        if released is not None:
            return released
        item, entry = self.require_binding(workspace, agent_id, binding, allow_stopping=True, snapshot=snap, worker_id=worker_id)
        worker_id = item.get('worker_id')
        ap, owner, _ = workers.execution_record(self, workspace, agent_id, snap, worker_id)
        if entry["phase"] != "stopping":
            raise Conflict("No explicit handoff request is pending.")
        for field, expected in (("controller", expected_controller), ("checkpoint", expected_checkpoint),
                                ("session", expected_session)):
            if expected is not _UNOBSERVED and entry.get(field) != expected:
                raise Conflict(f"The stop observation no longer matches the binding's {field}.")
        point = self._read_checkpoint(store, snap, agent_id, entry["checkpoint"], worker_id)
        handoff_id = "h" + binding[1:]
        handoff = {"id": handoff_id, "agent": agent_id, "entry": binding,
                   "checkpoint": entry["checkpoint"], "created_at": now(), "consumed_by": None}
        if worker_id is not None:
            handoff['worker'] = worker_id
        owner.update(current=None, handoff=handoff_id)
        entry.update(phase="released", stopped_at=now())
        bp = layout.shared_path(snap, f"bindings/{binding}.json")
        agent_path = layout.shared_path(snap, f'agents/{agent_id}.json')
        cp = workers.checkpoint_index(snap, agent_id, entry['checkpoint'], worker_id if point.get('worker') else None)
        try:
            store.change("main", {ap: encode(owner), bp: encode(entry), layout.shared_path(snap, f"handoffs/{handoff_id}.json"): encode(handoff)},
                         layout.expected(snap, {ap: snap.entries[ap], agent_path: snap.entries[agent_path], bp: snap.entries[bp], cp: snap.entries[cp],
                          layout.shared_path(snap, f"handoffs/{handoff_id}.json"): None}), "Release entry")
        except (Conflict, Uncertain) as failure:
            # A competing observer or a lost push reply may have completed this exact request.
            # Only read its result; never repeat the release mutation here.
            try:
                latest = store.snapshot()
            except (Error, OSError, ValueError) as exc:
                raise Uncertain(f"{failure}\nCould not confirm the original stop publication: {exc}") from exc
            # A snapshot lists versions; reading its result content can still fail remotely.
            try:
                released = self._released_handoff(latest, agent_id, binding,
                                                  entry.get("controller"), entry["checkpoint"], entry.get("session"))
            except RetryableRead as exc:
                raise Uncertain(f"{failure}\nCould not confirm the original stop result content: {exc}") from exc
            if released is not None:
                return released
            raise
        return handoff

    def _forced_handoff(self, snap, agent_id, binding, checkpoint):
        entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
        if not entry or entry["phase"] != "revoked":
            return None
        handoff = snap.json(layout.shared_path(snap, f"handoffs/h{binding[1:]}.json"))
        if (entry["id"] != binding or entry["agent"] != agent_id or not handoff
                or not handoff.get("forced") or handoff["agent"] != agent_id or handoff["entry"] != binding):
            raise Error("Revoked entry has no matching forced handoff.")
        if entry.get("checkpoint") != checkpoint or handoff["checkpoint"] != checkpoint:
            raise Conflict("This entry was taken over from another saved checkpoint.")
        return handoff

    def takeover(self, workspace, agent_id, binding, checkpoint, *, confirm=False, worker_id=None):
        if confirm is not True:
            raise Error("Explicit user confirmation is required to revoke the old execution entry.")
        slug(binding)
        slug(checkpoint)
        store = self.store(workspace)
        locator = self.local()["workspaces"][workspace]["locator"]
        operation = self.home / "takeovers" / digest(locator.encode()) / f"{binding}.json"
        with locked(operation.with_suffix(".lock")):
            snap = store.snapshot()
            original_entry = snap.json(layout.shared_path(snap, f'bindings/{binding}.json'))
            if not original_entry or original_entry.get('agent') != agent_id:
                raise Conflict('The selected Binding belongs to another Agent or is missing.')
            actual_worker = self.binding_worker(workspace, agent_id, original_entry, snap)
            if worker_id is not None and actual_worker != worker_id:
                raise Conflict('The selected Binding belongs to another Worker.')
            worker_id = actual_worker
            item = self.agent(workspace, agent_id, snap, worker_id=worker_id)
            ap, owner, _ = workers.execution_record(self, workspace, agent_id, snap, worker_id)
            handoff = self._forced_handoff(snap, agent_id, binding, checkpoint)
            if handoff is None:
                if item["current"] != binding or item["archived"]:
                    raise Conflict("The selected entry is no longer current; read the Agent before taking it over.")
                entry = snap.json(layout.shared_path(snap, f"bindings/{binding}.json"))
                if entry["agent"] != agent_id or entry["phase"] not in ("starting", "active", "stopping"):
                    raise Conflict("The current execution entry cannot be taken over.")
                point = self._read_checkpoint(store, snap, agent_id, checkpoint, worker_id)
                receipt = read_json(operation, {})
                if receipt.get("publication_unknown"):
                    if receipt["agent"] != agent_id or receipt["checkpoint"] != checkpoint:
                        raise Conflict("An unresolved takeover already uses this entry and another checkpoint.")
                    raise Uncertain("The original takeover publication remains unknown; it was not repeated.")
                handoff_id = "h" + binding[1:]
                handoff = {"id": handoff_id, "agent": agent_id, "entry": binding, "checkpoint": point["id"],
                           "created_at": now(), "consumed_by": None, "forced": True,
                           "native_stop_confirmed": False}
                if worker_id is not None:
                    handoff['worker'] = worker_id
                owner.update(current=None, handoff=handoff_id)
                entry.update(phase="revoked", checkpoint=point["id"], revoked_at=now(), revocation="user_takeover")
                bp = layout.shared_path(snap, f"bindings/{binding}.json")
                agent_path = layout.shared_path(snap, f'agents/{agent_id}.json')
                cp, hp = workers.checkpoint_index(snap, agent_id, checkpoint, worker_id if point.get('worker') else None), layout.shared_path(snap, f"handoffs/{handoff_id}.json")
                pending = {"agent": agent_id, "checkpoint": checkpoint, "publication_unknown": True}
                write_json(operation, pending)
                try:
                    store.change("main", {ap: encode(owner), bp: encode(entry), hp: encode(handoff)},
                                 layout.expected(snap, {ap: snap.entries[ap], agent_path: snap.entries[agent_path], bp: snap.entries[bp], cp: snap.entries[cp], hp: None}),
                                 "User takeover")
                except (Conflict, Uncertain) as failure:
                    if isinstance(failure, Conflict):
                        write_json(operation, {**pending, "publication_unknown": False})
                    try:
                        latest = store.snapshot()
                    except (Error, OSError, ValueError) as exc:
                        raise Uncertain(f"{failure}\nCould not confirm the original takeover publication: {exc}") from exc
                    try:
                        handoff = self._forced_handoff(latest, agent_id, binding, checkpoint)
                    except RetryableRead as exc:
                        raise Uncertain(f"{failure}\nCould not read the original takeover result: {exc}") from exc
                    if handoff is None:
                        raise
                except Error:
                    write_json(operation, {**pending, "publication_unknown": False})
                    raise
                write_json(operation, {**pending, "publication_unknown": False})
            return {"state": "execution_revoked", "previous_binding": binding, "checkpoint": checkpoint,
                    "handoff": handoff, "execution_right_revoked": True, "native_state": "not_observed",
                    "native_stop_confirmed": False, "starts_new_session": False}

    def versions(self, workspace, agent_id, directory=None):
        root = self.root(workspace, agent_id, directory)
        source = read_json(layout.instance_path(root, 'source.json'))
        if source is None:
            return {"source": None, "files": [], "status": "instance_owned"}
        snap = self.store(workspace).snapshot()
        result = []
        for target, info in source["files"].items():
            local = inside(root, target)
            upstream = snap.bytes(info["path"])
            local_hash = digest(local.read_bytes()) if local.is_file() else None
            upstream_hash = digest(upstream) if upstream is not None else None
            result.append({"path": target, "local_changed": local_hash != info["hash"],
                           "upstream_changed": upstream_hash != info["hash"], "missing_upstream": upstream is None})
        return {"source": source, "files": result}

    def update(self, workspace, agent_id, revision=None, directory=None):
        root = self.root(workspace, agent_id, directory)
        with layout.lock(root, "files.lock"):
            if (layout.local_path(root, "skill-install/operation.json")).exists():
                raise Conflict("Finish the pending Skill update before changing Definition materials.")
            source = read_json(layout.instance_path(root, 'source.json'))
            if source is None:
                raise Error("This agent has no shared source. Its own assets do not need an upstream.")
            selected, new_source = self._definition(workspace, source["definition"], revision, root=root)
            for name in read_json(layout.instance_path(root, 'skill-sources.json'), {}):
                prefix = f".agents/skills/{name}/".casefold()
                if any(p.casefold().startswith(prefix) for p in selected):
                    raise Conflict(f"Definition overlaps independently installed shared Skill: {name}")
            for target, info in source["files"].items():
                path = inside(root, target)
                actual = digest(path.read_bytes()) if path.is_file() else None
                if actual != info["hash"]:
                    raise Conflict(f"Locally modified: {target}. Inspect differences before adopting a revision.")
            for target in selected.keys() - source["files"].keys():
                if inside(root, target).exists():
                    raise Conflict(f"New source file would overwrite an instance asset: {target}")
            for target in source["files"].keys() - selected.keys():
                inside(root, target).unlink()
            for target, data in selected.items():
                write_bytes(inside(root, target), data)
            write_json(layout.instance_path(root, 'source.json'), new_source)
        return {"revision": new_source["revision"], "model_reloaded": False, "shared_snapshot_saved": False}

    def promote(self, workspace, agent_id, paths, destination, directory=None):
        root = self.root(workspace, agent_id, directory)
        prefix = relpath(destination).rstrip("/")
        if prefix.split("/")[0] not in ("definitions", "skills", "knowledge"):
            raise Error("Promote targets definitions/, skills/ or knowledge/, not protocol state.")
        if not paths:
            raise Error("Select exact files to promote.")
        store = self.store(workspace)
        snap = store.snapshot()
        changes, source_files = {}, []
        for path in paths:
            source = inside(root, path)
            if source.is_symlink() or not source.is_file():
                raise Error("Promote selects regular files only.")
            relative = "definition.md" if path == "AGENTS.md" and prefix.startswith("definitions/") else path
            if relative.startswith(".agents/skills/"):
                relative = relative[len(".agents/"):]
            target = prefix + "/" + relpath(relative)
            if target in snap.entries:
                raise Conflict(f"Shared target exists: {target}. Choose a new asset path; no silent replacement.")
            changes[target] = source.read_bytes()
            source_files.append({"path": path, "hash": digest(changes[target])})
        changes[prefix + "/provenance.json"] = encode({"agent": agent_id, "files": source_files,
            "instance_revision": read_json(layout.local_path(root, "context.json"))["revision"], "created_at": now()})
        sha = store.change("main", changes, layout.expected(snap, {p: None for p in changes}), f"Promote selected assets from {agent_id}")
        return {"revision": sha, "files": list(changes), "source_modified": False}

    def work_create(self, workspace, owner, content, parent_id=None):
        store = self.store(workspace)
        snap = store.snapshot()
        self.agent(workspace, owner, snap)
        if parent_id and layout.shared_path(snap, f"work/{slug(parent_id)}/work.json") not in snap.entries:
            raise Error("Parent work does not exist.")
        if not isinstance(content, str) or not content.strip():
            raise Error("Work content cannot be empty.")
        wid = uid("w")
        work = {"id": wid, "parent_id": parent_id, "owner": owner, "content": content}
        path = layout.shared_path(snap, f"work/{wid}/work.json")
        revision = store.change("main", {path: encode(work)}, layout.expected(snap, {path: None}), f"Create work {wid}")
        return {**work, "commit": revision, "revision": store.snapshot(revision=revision).entries[path]}

    def work_show(self, workspace, work_id):
        snap = self.store(workspace).snapshot()
        path = layout.shared_path(snap, f"work/{slug(work_id)}/work.json")
        work = snap.json(path)
        if work is None:
            raise Error("Work not found.")
        return {**work, "revision": snap.entries[path], "delivery": snap.json(layout.shared_path(snap, f"work/{work_id}/delivery.json"))}

    def work_list(self, workspace, owner=None, parent_id=None, tree=False):
        snap = self.store(workspace).snapshot()
        result = []
        for path in snap.entries:
            if path.startswith(layout.shared_path(snap, "work/")) and path.endswith("/work.json"):
                item = snap.json(path)
                if (owner is None or item["owner"] == owner) and (parent_id is None or item["parent_id"] == parent_id):
                    result.append({**item, "revision": snap.entries[path],
                                   "delivery": snap.json(layout.shared_path(snap, f"work/{item['id']}/delivery.json"))})
        if tree:
            nodes = {item["id"]: {**item, "children": []} for item in result}
            roots = []
            for node in nodes.values():
                parent = nodes.get(node["parent_id"])
                (parent["children"] if parent else roots).append(node)
            return roots
        return result

    def work_update(self, workspace, work_id, revision, content=None, owner=None, parent_id=None):
        store = self.store(workspace)
        snap = store.snapshot()
        path, delivery = layout.shared_path(snap, f"work/{slug(work_id)}/work.json"), layout.shared_path(snap, f"work/{work_id}/delivery.json")
        item = snap.json(path)
        if not item:
            raise Error("Work not found.")
        if delivery in snap.entries:
            raise Conflict("Delivered work is immutable; create a follow-up work.")
        if content is not None:
            if not isinstance(content, str) or not content.strip():
                raise Error("Work content cannot be empty.")
            item["content"] = content
        if owner is not None:
            self.agent(workspace, owner, snap)
            item["owner"] = owner
        expected = {path: revision, delivery: None}
        if parent_id is not None:
            current = parent_id or None
            visited = {work_id}
            while current:
                if current in visited:
                    raise Conflict("A work cannot be its own ancestor.")
                visited.add(current)
                parent = snap.json(layout.shared_path(snap, f"work/{slug(current)}/work.json"))
                if parent is None:
                    raise Error("Parent work not found.")
                parent_path = layout.shared_path(snap, f"work/{current}/work.json")
                expected[parent_path] = snap.entries[parent_path]
                current = parent["parent_id"]
            item["parent_id"] = parent_id or None
        sha = store.change("main", {path: encode(item)}, layout.expected(snap, expected), f"Update work {work_id}")
        return {**item, "revision": store.snapshot(revision=sha).entries[path]}

    def work_deliver(self, workspace, work_id, revision, content, refs):
        if not isinstance(content, str) or not content.strip() or not refs:
            raise Error("Delivery requires completion evidence and explicit result references.")
        store = self.store(workspace)
        snap = store.snapshot()
        path = layout.shared_path(snap, f"work/{slug(work_id)}/work.json")
        if not snap.json(path):
            raise Error("Work not found.")
        target = layout.shared_path(snap, f"work/{work_id}/delivery.json")
        result = {"work_id": work_id, "content": content, "refs": refs}
        sha = store.change("main", {target: encode(result)}, layout.expected(snap, {path: revision, target: None}), f"Deliver {work_id}")
        return {**result, "revision": sha}
