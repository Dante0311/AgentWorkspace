"""Local desktop project preferences and honest manual setup guidance.

These are references, not another project database or proof of native operations.
No private application state, product files, runtime profile or Binding is changed.
"""
from importlib.resources import files
from pathlib import Path
import json

from .util import Conflict, Error, digest, locked, now, write_json


HARNESSES = ("codex", "claude", "workbuddy")


def _path(app, workspace, agent_id, harness):
    if harness not in HARNESSES:
        raise Error("Choose codex, claude or workbuddy for a desktop project reference.")
    root = app.root(workspace, agent_id)
    return root, root / ".aw-local/desktop-projects" / (harness + ".json")


def plan(app, workspace, agent_id, harness="codex"):
    root, path = _path(app, workspace, agent_id, harness)
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        data = None
    value = json.loads(data) if data is not None else {}
    if not isinstance(value, dict):
        raise Error("Invalid desktop reference; preserve the file and inspect it before changing it.")
    project = {"project_name": f"AW · {workspace} · {agent_id}",
               "section_name": f"AW · {workspace}" if harness == "codex" else "",
               "product_paths": [], **value}
    if (not isinstance(project["product_paths"], list)
            or not all(isinstance(p, str) for p in project["product_paths"])):
        raise Error("Invalid product folder references; the original file was not changed.")
    return {"workspace": workspace, "agent_id": agent_id, "harness": harness,
            "primary_folder": str(root), "project": project,
            "revision": digest(data) if data is not None else None,
            "state": "manual_setup_required", "native_project_verified": False,
            "path_status": [{"path": p, "exists": Path(p).is_dir()} for p in project["product_paths"]],
            "instructions": (files("agent_workspace") / "resources/prompts/desktop-projects.md").read_text(encoding="utf-8")}


def save(app, workspace, agent_id, harness, project_name, section_name="", product_paths=None, revision=None):
    root, path = _path(app, workspace, agent_id, harness)
    for key, value in (("project_name", project_name), ("section_name", section_name)):
        if not isinstance(value, str) or len(value) > 160 or any(ord(c) < 32 for c in value):
            raise Error(f"Invalid {key}; use a short display name without control characters.")
    if not project_name.strip():
        raise Error("A project display name is required.")
    if section_name and harness != "codex":
        raise Error("Automatic/native sections are not verified for this desktop. Leave section_name empty.")
    if product_paths is None:
        product_paths = []
    if not isinstance(product_paths, list) or len(product_paths) > 20:
        raise Error("Select up to 20 explicit existing product folders.")
    paths = []
    for value in product_paths:
        if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
            raise Error("Use explicit folder paths, one per entry.")
        directory = Path(value).expanduser().resolve(strict=True)
        if not directory.is_dir() or directory == root:
            raise Error("A product folder must be an existing directory distinct from the Agent's primary folder.")
        if str(directory) not in paths:
            paths.append(str(directory))
    with locked(path.with_suffix(".lock")):
        actual = digest(path.read_bytes()) if path.exists() else None
        if revision != actual:
            raise Conflict("Desktop project preferences changed; read them again before saving.")
        write_json(path, {"project_name": project_name, "section_name": section_name,
                          "product_paths": paths, "updated_at": now()})
    return {**plan(app, workspace, agent_id, harness), "saved": "local_reference_only",
            "native_project_changed": False, "binding_changed": False}
