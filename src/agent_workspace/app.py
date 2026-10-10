from __future__ import annotations

import fnmatch
from importlib.resources import files as package_files
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from . import __version__
from .gitstore import GitStore, GitHubStore, open_store
from .util import Conflict, Error, RetryableRead, Uncertain, digest, encode, inside, locked, now, read_json, relpath, slug, uid, write_bytes, write_json


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

    def workspace_init(self, name, directory):
        slug(name)
        path = Path(directory).expanduser().resolve()
        GitStore.initialize(path)
        store = open_store(str(path), self.home)
        meta = {"schema": 1, "name": name, "locator": "local:" + name, "friends": {}, "projects": {}}
        store.branch("main", {"workspace.json": encode(meta)})
        return self.workspace_connect(name, str(path))

    def workspace_connect(self, name, address):
        slug(name)
        if ":" not in address or Path(address).exists():
            address = str(Path(address).expanduser().resolve())
        store = open_store(address, self.home)
        snap = store.snapshot()
        meta = snap.json("workspace.json")
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

    def workspace_bootstrap_remote(self, name, address):
        """Initialize only an already-created empty remote repo, never create a GitHub account resource."""
        slug(name)
        store = open_store(address, self.home)
        if store.head("main"):
            raise Conflict("Remote main exists; initialization must not overwrite it.")
        meta = {"schema": 1, "name": name, "locator": address, "friends": {}, "projects": {}}
        if isinstance(store, GitHubStore):
            store.bootstrap(meta)
        else:
            store.branch("main", {"workspace.json": encode(meta)})
        return self.workspace_connect(name, address)

    def workspace_list(self):
        return [{"alias": k, **v} for k, v in self.local()["workspaces"].items()]

    def workspace_show(self, workspace):
        snap = self.store(workspace).snapshot()
        return {**snap.json("workspace.json"), "revision": snap.revision,
                "access": self.local()["workspaces"][workspace]}

    def relation(self, workspace, kind, operation, alias=None, address=None, content=""):
        if kind not in ("friends", "projects"):
            raise Error("Unknown relation kind.")
        store = self.store(workspace)
        snap = store.snapshot()
        meta = snap.json("workspace.json")
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
                target_meta = target.snapshot().json("workspace.json")
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
        revision = store.change("main", {"workspace.json": encode(meta)},
                                {"workspace.json": snap.entries["workspace.json"]}, f"{operation} {kind}/{alias}")
        return {"relations": meta[kind], "revision": revision}

    def friend_store(self, workspace, alias):
        meta = self.store(workspace).snapshot().json("workspace.json")
        friend = meta["friends"].get(alias)
        if friend is None:
            raise Error(f"No friend named {alias}.")
        entry = self.local()["workspaces"][workspace]
        address = entry.get("paths", {}).get("friends/" + alias) or friend.get("address")
        if not address:
            raise Error("This friend requires a local path mapping in this environment.")
        store = open_store(address, self.home)
        other = store.snapshot().json("workspace.json")
        if other["locator"] != friend["locator"]:
            raise Conflict("Friend address now resolves to another workspace.")
        if meta["locator"] not in [v["locator"] for v in other["friends"].values()]:
            raise Error("The other workspace has not registered this workspace as a friend.")
        return store, other

    def agent(self, workspace, agent_id, snapshot=None):
        slug(agent_id)
        snap = snapshot or self.store(workspace).snapshot()
        item = snap.json(f"agents/{agent_id}.json")
        if item is None:
            raise Error(f"Unknown agent {agent_id} in {workspace}.")
        return item

    def agents(self, workspace, archived=None):
        snap = self.store(workspace).snapshot()
        items = [snap.json(p) for p in snap.entries if p.startswith("agents/") and p.endswith(".json")]
        return [a for a in items if archived is None or a["archived"] == archived]

    def require_binding(self, workspace, agent_id, binding, *, allow_stopping=False, snapshot=None):
        snap = snapshot or self.store(workspace).snapshot()
        agent = self.agent(workspace, agent_id, snap)
        if not binding or agent["current"] != binding or agent["archived"]:
            raise Conflict("This is not the agent's current execution entry. Do not resume an old session.")
        entry = snap.json(f"bindings/{binding}.json")
        if not isinstance(entry, dict) or entry.get("id") != binding or entry.get("agent") != agent_id:
            raise Error("Binding record does not belong to this execution entry.")
        if entry["phase"] != "active" and not (allow_stopping and entry["phase"] == "stopping"):
            raise Conflict(f"Entry is {entry['phase']}; it cannot perform this operation.")
        return agent, entry

    def _resources(self):
        root = package_files("agent_workspace") / "resources"
        result = {}
        for name in ("workspace", "work", "message", "agent", "handoff", "relay", "fork"):
            result[f".agents/skills/{name}/SKILL.md"] = (root / "skills" / name / "SKILL.md").read_bytes()
        for name in ("initialization.md", "entry.md", "handoff.md", "checkpoints.md", "capabilities.md", "desktop-projects.md"):
            result[f".aw/prompts/{name}"] = (root / "prompts" / name).read_bytes()
        result[".aw/software.json"] = encode({"version": __version__,
            "files": {p: digest(v) for p, v in result.items()}})
        return result

    def _definition(self, workspace, definition, revision=None):
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
            relpath(target)
            if target.startswith(".aw/") or target == "source.json":
                raise Error("Definition cannot replace platform metadata.")
            result[target] = data
            mapping[target] = {"path": origin, "hash": digest(data)}
        if "AGENTS.md" not in result:
            raise Error("Definition must include a responsibility file (definition.md or AGENTS.md).")
        return result, {"definition": prefix, "revision": snap.revision, "files": mapping}

    def create(self, workspace, name, description="", agent_id=None, directory=None,
               definition=None, revision=None, import_directory=None, assets=None, request_id=None):
        if request_id and (not agent_id or import_directory):
            raise Error("Resumable creation needs an explicit agent ID and does not support file import.")
        creation = None
        if request_id:
            creation = {"request_id": slug(request_id), "fingerprint": digest(encode({
                "name": name, "description": description, "definition": definition, "revision": revision}))}
        agent_id = slug(agent_id or (name if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", name) else uid("a")))
        store = self.store(workspace)
        snap = store.snapshot()
        location_target = directory or str(self.home / "instances" / workspace / agent_id)
        existing = snap.json(f"agents/{agent_id}.json")
        if existing:
            if creation is None or existing.get("creation") != creation:
                raise Conflict("Agent ID already exists. Connect to it; do not create a duplicate.")
            return {**existing, **self.connect_agent(workspace, agent_id, location_target)}
        branch = "instance/" + agent_id
        if creation is not None:
            previous = store.snapshot(branch)
            if previous.revision:
                saved = previous.json(".aw/creation.json", {})
                identity = previous.json(".aw/identity.json", {})
                if (saved.get("creation") != creation or saved.get("id") != agent_id
                        or identity != {"workspace": snap.json("workspace.json")["locator"], "agent": agent_id}):
                    raise Conflict("Existing branch does not belong to this creation request.")
                # Resume only registration of this exact saved creation; never replace assets.
                store.change("main", {f"agents/{agent_id}.json": encode(saved)},
                             {f"agents/{agent_id}.json": None}, f"Register {agent_id}")
                return {**saved, **self.connect_agent(workspace, agent_id, location_target)}
        content = self._resources()
        content["AGENTS.md"] = f"# {name}\n\n{description or '职责待使用者逐步完善。'}\n\n工作根为本目录。平台操作参见 `.agents/skills/`；不要将没有收到的任务当作默认任务。\n".encode()
        if definition:
            selected, source = self._definition(workspace, definition, revision)
            for path in selected:
                if path in content and path != "AGENTS.md":
                    raise Conflict(f"Definition overlaps a bundled platform skill: {path}")
            content.update(selected)
            content["source.json"] = encode(source)
        if import_directory:
            if not assets:
                raise Error("Import requires an explicit list of relative asset paths; the source is never modified.")
            root = Path(import_directory).expanduser().resolve()
            for name_in_source in assets:
                source_path = inside(root, name_in_source)
                if source_path.is_symlink() or not source_path.is_file():
                    raise Error("Import selects regular files only; inspect directories before selecting assets.")
                target = relpath(name_in_source)
                if target.startswith(".aw/") or (target in content and target != "AGENTS.md"):
                    raise Conflict(f"Import overlaps managed content: {target}")
                content[target] = source_path.read_bytes()
        content[".aw/identity.json"] = encode({"workspace": snap.json("workspace.json")["locator"], "agent": agent_id})
        item = {"id": agent_id, "name": name, "description": description, "branch": branch,
                "archived": False, "current": None, "has_run": False, "handoff": None,
                "created_at": now()}
        if creation is not None:
            item["creation"] = creation
            content[".aw/creation.json"] = encode(item)
        sha = store.branch(branch, content)
        store.change("main", {f"agents/{agent_id}.json": encode(item)}, {f"agents/{agent_id}.json": None},
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

    def connect_agent(self, workspace, agent_id, directory):
        item = self.agent(workspace, agent_id)
        root = Path(directory).expanduser().resolve()
        marker = root / ".aw-local" / "context.json"
        existing = read_json(marker)
        locator = self.local()["workspaces"][workspace]["locator"]
        if existing:
            if (existing["locator"], existing["agent"]) != (locator, agent_id):
                raise Conflict("Directory belongs to another instance.")
            def register(value):
                locations = value["workspaces"][workspace].setdefault("instances", {}).setdefault(agent_id, [])
                if str(root) not in locations:
                    locations.append(str(root))
            self.change_local(register)
            return {"directory": str(root), "revision": existing["revision"]}
        if root.exists() and any(root.iterdir()):
            raise Conflict("Use an empty directory. To adopt an external agent, select its assets with agent import.")
        snap = self.store(workspace).snapshot(item["branch"])
        content = snap.all()
        context = {"workspace": workspace, "locator": locator, "agent": agent_id, "revision": snap.revision,
                   "saved": {p: digest(data) for p, data in content.items()}, "exclude": DEFAULT_EXCLUDES}
        # Prepare a complete directory before exposing it. A failed copy is safe to retry.
        root.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".aw-connect-", dir=root.parent) as temporary:
            staged = Path(temporary) / "instance"
            staged.mkdir()
            for path, data in content.items():
                write_bytes(inside(staged, path), data)
            write_json(staged / ".aw-local/context.json", context)
            if root.exists():
                root.rmdir()  # Refuse if another writer put anything in the target.
            staged.rename(root)
        def edit(value):
            locations = value["workspaces"][workspace].setdefault("instances", {}).setdefault(agent_id, [])
            if str(root) not in locations:
                locations.append(str(root))
        self.change_local(edit)
        return {"directory": str(root), "revision": snap.revision}

    def collect(self, root):
        context = read_json(root / ".aw-local/context.json")
        excludes = context["exclude"]
        content, skipped = {}, []
        for base, directories, names in os.walk(root, followlinks=False):
            kept = []
            for name in directories:
                candidate = Path(base) / name
                relative = candidate.relative_to(root).as_posix()
                if any(fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(relative, pat) for pat in excludes):
                    skipped.append(relative + "/")
                elif candidate.is_symlink():
                    raise Error(f"Snapshot needs an explicit export for symlink: {relative}")
                else:
                    kept.append(name)
            directories[:] = kept
            for name in names:
                candidate = Path(base) / name
                relative = candidate.relative_to(root).as_posix()
                if name.startswith(".aw-tmp-") or any(fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(relative, pat) for pat in excludes):
                    skipped.append(relative)
                    continue
                if candidate.is_symlink():
                    raise Error(f"Snapshot cannot silently follow symlink: {relative}")
                if candidate.stat().st_size > 50 * 1024 * 1024:
                    raise Error(f"Asset exceeds 50 MiB; store externally and record a reference: {relative}")
                content[relative] = candidate.read_bytes()
        return content, skipped

    def sync_agent(self, workspace, agent_id, directory=None):
        root = self.root(workspace, agent_id, directory)
        with locked(root / ".aw-local/files.lock"):
            context = read_json(root / ".aw-local/context.json")
            local, _ = self.collect(root)
            snap = self.store(workspace).snapshot(self.agent(workspace, agent_id)["branch"])
            remote = snap.all()
            for path in set(context["saved"]) | set(remote):
                previous = context["saved"].get(path)
                actual = digest(local[path]) if path in local else None
                desired = digest(remote[path]) if path in remote else None
                if actual != previous and desired != previous and actual != desired:
                    raise Conflict(f"Local and remote edits overlap: {path}. No file was changed.")
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
            context.update(revision=snap.revision, saved={p: digest(v) for p, v in remote.items()})
            write_json(root / ".aw-local/context.json", context)
            return {"revision": snap.revision, "directory": str(root)}

    def _save_files(self, workspace, agent_id, root, extra=None, message="Save instance assets"):
        context = read_json(root / ".aw-local/context.json")
        content, skipped = self.collect(root)
        content.update(extra or {})
        store = self.store(workspace)
        branch = self.agent(workspace, agent_id)["branch"]
        previous = store.snapshot(branch, revision=context["revision"])
        changes = {p: None for p in previous.entries if p not in content}
        changes.update({p: data for p, data in content.items() if previous.bytes(p) != data})
        sha = store.change(branch, changes, {}, message, base=context["revision"]) if changes else context["revision"]
        for path, data in (extra or {}).items():
            write_bytes(inside(root, path), data)
        context.update(revision=sha, saved={p: digest(v) for p, v in content.items()})
        write_json(root / ".aw-local/context.json", context)
        return sha, skipped

    def checkpoint(self, workspace, agent_id, summary, content="", binding=None, directory=None,
                   checkpoint_id=None, references=None):
        root = self.root(workspace, agent_id, directory)
        item = self.agent(workspace, agent_id)
        if item["current"] or binding:
            self.require_binding(workspace, agent_id, binding, allow_stopping=True)
        cp = slug(checkpoint_id or uid("c"))
        store = self.store(workspace)
        index = f"checkpoints/{agent_id}/{cp}.json"
        found = store.snapshot().json(index)
        if found:
            saved = store.snapshot(revision=found["revision"]).json(found["path"])
            if (saved["summary"], saved["content"]) != (summary, content):
                raise Conflict("Checkpoint ID is immutable and already has different content.")
            return found
        receipt_path = root / ".aw-local/checkpoint-operations" / f"{cp}.json"
        pending = read_json(receipt_path)
        if pending:
            saved = store.snapshot(revision=pending["revision"]).json(pending["path"])
            if (saved["summary"], saved["content"]) != (summary, content):
                raise Conflict("Pending checkpoint has different content.")
            store.change("main", {index: encode(pending)}, {index: None}, f"Register checkpoint {cp}")
            return pending
        with locked(root / ".aw-local/files.lock"):
            if (root / f".aw/checkpoints/{cp}.json").exists():
                raise Conflict("Checkpoint file already exists without a publication receipt; inspect its saved revision before continuing.")
            record = {"id": cp, "created_at": now(), "summary": summary, "content": content,
                      "record_refs": references or [], "scope": "Saved instance files; external/runtime-unavailable state is not implied."}
            sha, skipped = self._save_files(workspace, agent_id, root,
                {f".aw/checkpoints/{cp}.json": encode(record)}, f"Checkpoint {cp}")
            pointer = {"id": cp, "agent": agent_id, "revision": sha, "path": f".aw/checkpoints/{cp}.json",
                       "created_at": record["created_at"], "excluded": skipped}
            write_json(receipt_path, pointer)
            store.change("main", {index: encode(pointer)}, {index: None}, f"Register checkpoint {cp}")
        return pointer

    def checkpoints(self, workspace, agent_id):
        snap = self.store(workspace).snapshot()
        return sorted([snap.json(p) for p in snap.entries if p.startswith(f"checkpoints/{agent_id}/")],
                      key=lambda p: p["created_at"])

    def checkpoint_show(self, workspace, agent_id, checkpoint):
        store = self.store(workspace)
        return self._read_checkpoint(store, store.snapshot(), agent_id, checkpoint)

    def _read_checkpoint(self, store, shared, agent_id, checkpoint):
        checkpoint = slug(checkpoint)
        pointer = shared.json(f"checkpoints/{agent_id}/{checkpoint}.json")
        if pointer is None:
            raise Error("Unknown saved checkpoint.")
        if (not isinstance(pointer, dict) or pointer.get("id") != checkpoint or pointer.get("agent") != agent_id
                or pointer.get("path") != f".aw/checkpoints/{checkpoint}.json" or not pointer.get("revision")):
            raise Error("Saved checkpoint reference does not match this instance and checkpoint.")
        snap = store.snapshot(revision=pointer["revision"])
        identity = snap.json(".aw/identity.json")
        if (not isinstance(identity, dict) or identity.get("agent") != agent_id
                or identity.get("workspace") != shared.json("workspace.json")["locator"]):
            raise Error("Saved checkpoint material belongs to a different instance or workspace.")
        record = snap.json(pointer["path"])
        if not isinstance(record, dict) or record.get("id") != checkpoint:
            raise Error("Saved checkpoint material is missing or does not match its reference.")
        return {**pointer, "record": record, "files": list(snap.entries)}

    def fork(self, workspace, agent_id, checkpoint, name, new_id=None, directory=None):
        point = self.checkpoint_show(workspace, agent_id, checkpoint)
        target = slug(new_id or name)
        store = self.store(workspace)
        snap = store.snapshot()
        if f"agents/{target}.json" in snap.entries:
            raise Conflict("Fork target already exists.")
        source = store.snapshot(revision=point["revision"])
        content = source.all()
        locator = snap.json("workspace.json")["locator"]
        content[".aw/identity.json"] = encode({"workspace": locator, "agent": target,
            "forked_from": {"agent": agent_id, "checkpoint": checkpoint, "revision": source.revision}})
        branch = "instance/" + target
        store.branch(branch, content, parent=source.revision)
        item = {"id": target, "name": name, "description": "", "branch": branch,
                "archived": False, "current": None, "has_run": False, "handoff": None,
                "created_at": now(), "forked_from": {"agent": agent_id, "checkpoint": checkpoint, "revision": source.revision}}
        store.change("main", {f"agents/{target}.json": encode(item)}, {f"agents/{target}.json": None}, f"Fork {target}")
        return {**item, **self.connect_agent(workspace, target, directory or str(self.home / "instances" / workspace / target))}

    def configure(self, workspace, agent_id, value, directory=None):
        root = self.root(workspace, agent_id, directory)
        if value.get("kind", "manual") not in ("manual", "desktop", "codex", "claude", "codebuddy"):
            raise Error("Runtime kind must be manual, desktop, codex, claude or codebuddy.")
        write_json(root / ".aw-local/runtime.json", value)
        return {"configured": True, "entry_changed": False}

    def show(self, workspace, agent_id, directory=None):
        store = self.store(workspace)
        snap = store.snapshot()
        item = self.agent(workspace, agent_id, snap)
        binding = snap.json(f"bindings/{item['current']}.json") if item["current"] else None
        locations = self.local()["workspaces"][workspace].get("instances", {}).get(agent_id, [])
        result = {**item, "revision": snap.entries[f"agents/{agent_id}.json"], "binding": binding, "directories": locations}
        if locations:
            root = self.root(workspace, agent_id, directory)
            result["runtime"] = read_json(root / ".aw-local/status.json", {"state": "not_running"})
            try:
                with locked(root / ".aw-local/runner.lock", wait=0):
                    result["runtime"]["runner_alive"] = False
            except Conflict:
                result["runtime"]["runner_alive"] = True
            result["watch"] = read_json(root / ".aw-local/watch.json", {"enabled": False})
            result["configured_kind"] = read_json(root / ".aw-local/runtime.json", {}).get("kind", "manual")
        return result

    def archive(self, workspace, agent_id, archived=True, directory=None):
        store = self.store(workspace)
        snap = store.snapshot()
        item = self.agent(workspace, agent_id, snap)
        if item["current"]:
            raise Conflict("Handoff before archiving. Archive does not revoke a live entry.")
        item["archived"] = archived
        path = f"agents/{agent_id}.json"
        store.change("main", {path: encode(item)}, {path: snap.entries[path]}, f"Archive={archived} {agent_id}")
        return item

    def reserve(self, workspace, agent_id, directory=None, binding_id=None):
        root = self.root(workspace, agent_id, directory)
        config = read_json(root / ".aw-local/runtime.json", {"kind": "manual"})
        store = self.store(workspace)
        snap = store.snapshot()
        item = self.agent(workspace, agent_id, snap)
        if item["current"] or item["archived"]:
            raise Conflict("Agent already has an entry or is archived; relay cannot take it over.")
        if item["has_run"] and not item["handoff"]:
            raise Conflict("No handoff is available. A crash is not a release of ownership.")
        binding = slug(binding_id) if binding_id else uid("b")
        entry = {"id": binding, "agent": agent_id, "kind": config.get("kind", "manual"),
                 "phase": "starting", "session": None, "created_at": now(), "handoff": item["handoff"]}
        changes = {f"bindings/{binding}.json": encode(entry)}
        path = f"agents/{agent_id}.json"
        expected = {path: snap.entries[path], f"bindings/{binding}.json": None}
        if item["handoff"]:
            handoff_path = f"handoffs/{item['handoff']}.json"
            handoff = snap.json(handoff_path)
            if handoff["consumed_by"]:
                raise Conflict("Handoff already consumed.")
            handoff["consumed_by"] = binding
            expected[handoff_path] = snap.entries[handoff_path]
            changes[handoff_path] = encode(handoff)
        item.update(current=binding, has_run=True, handoff=None)
        changes[path] = encode(item)
        store.change("main", changes, expected, f"Reserve entry {binding}")
        write_json(root / ".aw-local/entry.json", {"binding": binding, "config": config})
        return {"agent": agent_id, "binding": binding, "phase": "starting", "kind": entry["kind"]}

    def bind(self, workspace, agent_id, binding, session, directory=None):
        slug(binding)
        if not session or len(session) > 256 or any(c in session for c in "\r\n\0"):
            raise Error("A real native session ID is required.")
        store = self.store(workspace)
        snap = store.snapshot()
        item = self.agent(workspace, agent_id, snap)
        path = f"bindings/{binding}.json"
        entry = snap.json(path)
        if item["current"] != binding or not entry or entry["phase"] != "starting":
            raise Conflict("Binding is not awaiting a new session.")
        for p in snap.entries:
            if p.startswith("bindings/"):
                previous = snap.json(p)
                if previous["kind"] == entry["kind"] and previous["session"] == session:
                    raise Conflict("A native session cannot be reused as a new execution entry.")
        entry.update(session=session, phase="active")
        session_path = f"sessions/{entry['kind']}/{digest(session.encode())}.json"
        store.change("main", {path: encode(entry), session_path: encode({"agent": agent_id, "binding": binding, "session": session})},
                     {path: snap.entries[path], session_path: None,
                      f"agents/{agent_id}.json": snap.entries[f"agents/{agent_id}.json"]}, f"Bind {binding}")
        return entry

    def stop(self, workspace, agent_id, binding, checkpoint, directory=None):
        root = self.root(workspace, agent_id, directory)
        store = self.store(workspace)
        snap = store.snapshot()
        _, entry = self.require_binding(workspace, agent_id, binding, allow_stopping=True, snapshot=snap)
        point = self._read_checkpoint(store, snap, agent_id, checkpoint)
        result = {"state": "awaiting_native_idle", "binding": binding, "checkpoint": checkpoint}
        if entry["phase"] == "stopping":
            if entry["checkpoint"] != checkpoint:
                raise Conflict("A pending stop cannot be replaced with a different checkpoint.")
            return result
        # Disable local automatic restarts before requesting the native end-of-turn observation.
        write_json(root / ".aw-local/watch.json", {"enabled": False, "reason": "handoff"})
        entry.update(phase="stopping", checkpoint=point["id"], stop_requested_at=now())
        path = f"bindings/{binding}.json"
        store.change("main", {path: encode(entry)}, {path: snap.entries[path],
                     f"checkpoints/{agent_id}/{checkpoint}.json": snap.entries[f"checkpoints/{agent_id}/{checkpoint}.json"],
                     f"agents/{agent_id}.json": snap.entries[f"agents/{agent_id}.json"]}, "Prepare handoff")
        return result

    def _released_handoff(self, snap, agent_id, binding, expected_controller, expected_checkpoint, expected_session):
        entry = snap.json(f"bindings/{binding}.json")
        if entry is None:
            return None
        if not isinstance(entry, dict):
            raise Error("Binding record is damaged; refusing stop confirmation.")
        if entry["phase"] != "released":
            return None
        handoff_id = "h" + binding[1:]
        handoff = snap.json(f"handoffs/{handoff_id}.json")
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
                    expected_session=_UNOBSERVED):
        if not observed_idle:
            raise Conflict("Native stop has not been confirmed. Entry remains owned.")
        store = self.store(workspace)
        snap = store.snapshot()
        released = self._released_handoff(snap, agent_id, binding, expected_controller, expected_checkpoint, expected_session)
        if released is not None:
            return released
        item, entry = self.require_binding(workspace, agent_id, binding, allow_stopping=True, snapshot=snap)
        if entry["phase"] != "stopping":
            raise Conflict("No explicit handoff request is pending.")
        for field, expected in (("controller", expected_controller), ("checkpoint", expected_checkpoint),
                                ("session", expected_session)):
            if expected is not _UNOBSERVED and entry.get(field) != expected:
                raise Conflict(f"The stop observation no longer matches the binding's {field}.")
        self._read_checkpoint(store, snap, agent_id, entry["checkpoint"])
        handoff_id = "h" + binding[1:]
        handoff = {"id": handoff_id, "agent": agent_id, "entry": binding,
                   "checkpoint": entry["checkpoint"], "created_at": now(), "consumed_by": None}
        item.update(current=None, handoff=handoff_id)
        entry.update(phase="released", stopped_at=now())
        ap, bp = f"agents/{agent_id}.json", f"bindings/{binding}.json"
        cp = f"checkpoints/{agent_id}/{entry['checkpoint']}.json"
        try:
            store.change("main", {ap: encode(item), bp: encode(entry), f"handoffs/{handoff_id}.json": encode(handoff)},
                         {ap: snap.entries[ap], bp: snap.entries[bp], cp: snap.entries[cp],
                          f"handoffs/{handoff_id}.json": None}, "Release entry")
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

    def versions(self, workspace, agent_id, directory=None):
        root = self.root(workspace, agent_id, directory)
        source = read_json(root / "source.json")
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
        with locked(root / ".aw-local/files.lock"):
            source = read_json(root / "source.json")
            if source is None:
                raise Error("This agent has no shared source. Its own assets do not need an upstream.")
            selected, new_source = self._definition(workspace, source["definition"], revision)
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
            write_json(root / "source.json", new_source)
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
            "instance_revision": read_json(root / ".aw-local/context.json")["revision"], "created_at": now()})
        sha = store.change("main", changes, {p: None for p in changes}, f"Promote selected assets from {agent_id}")
        return {"revision": sha, "files": list(changes), "source_modified": False}

    def work_create(self, workspace, owner, content, parent_id=None):
        store = self.store(workspace)
        snap = store.snapshot()
        self.agent(workspace, owner, snap)
        if parent_id and f"work/{slug(parent_id)}/work.json" not in snap.entries:
            raise Error("Parent work does not exist.")
        if not isinstance(content, str) or not content.strip():
            raise Error("Work content cannot be empty.")
        wid = uid("w")
        work = {"id": wid, "parent_id": parent_id, "owner": owner, "content": content}
        path = f"work/{wid}/work.json"
        revision = store.change("main", {path: encode(work)}, {path: None}, f"Create work {wid}")
        return {**work, "commit": revision, "revision": store.snapshot(revision=revision).entries[path]}

    def work_show(self, workspace, work_id):
        snap = self.store(workspace).snapshot()
        path = f"work/{slug(work_id)}/work.json"
        work = snap.json(path)
        if work is None:
            raise Error("Work not found.")
        return {**work, "revision": snap.entries[path], "delivery": snap.json(f"work/{work_id}/delivery.json")}

    def work_list(self, workspace, owner=None, parent_id=None, tree=False):
        snap = self.store(workspace).snapshot()
        result = []
        for path in snap.entries:
            if path.startswith("work/") and path.endswith("/work.json"):
                item = snap.json(path)
                if (owner is None or item["owner"] == owner) and (parent_id is None or item["parent_id"] == parent_id):
                    result.append({**item, "revision": snap.entries[path],
                                   "delivery": snap.json(f"work/{item['id']}/delivery.json")})
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
        path, delivery = f"work/{slug(work_id)}/work.json", f"work/{work_id}/delivery.json"
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
                parent = snap.json(f"work/{slug(current)}/work.json")
                if parent is None:
                    raise Error("Parent work not found.")
                parent_path = f"work/{current}/work.json"
                expected[parent_path] = snap.entries[parent_path]
                current = parent["parent_id"]
            item["parent_id"] = parent_id or None
        sha = store.change("main", {path: encode(item)}, expected, f"Update work {work_id}")
        return {**item, "revision": store.snapshot(revision=sha).entries[path]}

    def work_deliver(self, workspace, work_id, revision, content, refs):
        if not isinstance(content, str) or not content.strip() or not refs:
            raise Error("Delivery requires completion evidence and explicit result references.")
        store = self.store(workspace)
        path = f"work/{slug(work_id)}/work.json"
        if not store.snapshot().json(path):
            raise Error("Work not found.")
        target = f"work/{work_id}/delivery.json"
        result = {"work_id": work_id, "content": content, "refs": refs}
        sha = store.change("main", {target: encode(result)}, {path: revision, target: None}, f"Deliver {work_id}")
        return {**result, "revision": sha}
