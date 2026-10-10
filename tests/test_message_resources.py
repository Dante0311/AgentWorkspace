"""The installed Message skill is complete and preserves private instance assets."""
import json

import pytest

from agent_workspace.commands import upgrade_tools
from agent_workspace.util import Conflict, digest, encode


MESSAGE_PATHS = (
    ".agents/skills/message/SKILL.md",
    ".agents/skills/message/references/protocol.md",
    ".agents/skills/message/references/manual.md",
    ".agents/skills/message/scripts/message_git.py",
    ".aw/prompts/message-notification.json",
)


def legacy_resources(fresh):
    legacy = {path: content for path, content in fresh.items()
              if path not in MESSAGE_PATHS[1:] and path != ".aw/software.json"}
    legacy[".aw/software.json"] = encode({"version": "isolated-old-version",
        "files": {path: digest(content) for path, content in legacy.items()}})
    return legacy


def test_new_instance_receives_complete_message_skill_and_template(app):
    fresh = app._resources()
    app.create("sea", "helper")
    root = app.root("sea", "helper")
    assert len(list(root.glob(".agents/skills/*/SKILL.md"))) == 7
    manifest = json.loads((root / ".aw/software.json").read_bytes())
    for path in MESSAGE_PATHS:
        assert (root / path).read_bytes() == fresh[path]
        assert manifest["files"][path] == digest(fresh[path])
    assert not any("__pycache__" in path for path in fresh)


def test_upgrade_adds_nested_resources_and_preserves_private_skills(app, monkeypatch):
    fresh = app._resources()
    with monkeypatch.context() as scoped:
        scoped.setattr(app, "_resources", lambda: legacy_resources(fresh))
        app.create("sea", "helper")
    root = app.root("sea", "helper")
    private = root / ".agents/skills/my-private/SKILL.md"
    private.parent.mkdir(parents=True)
    private.write_bytes(b"private instructions")
    extra = root / ".agents/skills/message/private.md"
    extra.write_bytes(b"private message notes")
    assert upgrade_tools(app, "sea", "helper")["user_assets_changed"] is False
    for path in MESSAGE_PATHS:
        assert (root / path).read_bytes() == fresh[path]
    assert private.read_bytes() == b"private instructions"
    assert extra.read_bytes() == b"private message notes"


@pytest.mark.parametrize("changed", [MESSAGE_PATHS[0], MESSAGE_PATHS[1], MESSAGE_PATHS[3]])
def test_upgrade_refuses_modified_skill_reference_or_script_before_any_write(app, changed):
    app.create("sea", "helper")
    root = app.root("sea", "helper")
    (root / changed).write_bytes(b"private change")
    before = {path: (root / path).read_bytes() for path in (*MESSAGE_PATHS, ".aw/software.json")}
    with pytest.raises(Conflict):
        upgrade_tools(app, "sea", "helper")
    assert {path: (root / path).read_bytes() for path in before} == before


def test_upgrade_does_not_overwrite_new_resource_path_owned_by_user(app, monkeypatch):
    fresh = app._resources()
    with monkeypatch.context() as scoped:
        scoped.setattr(app, "_resources", lambda: legacy_resources(fresh))
        app.create("sea", "helper")
    root = app.root("sea", "helper")
    manual = root / MESSAGE_PATHS[2]
    manual.parent.mkdir(parents=True)
    manual.write_bytes(b"user's earlier manual")
    before = (root / ".aw/software.json").read_bytes()
    with pytest.raises(Conflict):
        upgrade_tools(app, "sea", "helper")
    assert manual.read_bytes() == b"user's earlier manual"
    assert (root / ".aw/software.json").read_bytes() == before
    assert not (root / MESSAGE_PATHS[3]).exists()
