"""Public Desktop defaults and explicit Worker overrides, with no native/model calls."""
from unittest.mock import Mock

import pytest

from agent_workspace import desktop_projects, layout, model_profiles, runtime
from agent_workspace.app import App
from agent_workspace.util import Conflict, read_json


def test_public_desktop_defaults_are_inherited_and_adopted_worker_values_stay_fixed(tmp_path, monkeypatch):
    app = App(tmp_path / "home")
    app.workspace_init("team", str(tmp_path / "remote.git"), worker_support=True)
    app.create("team", "owner")
    root = app.root("team", "owner")
    projects = []
    for identifier in ("shared", "override", "later"):
        folder = tmp_path / identifier
        folder.mkdir()
        projects.append({"projectId": identifier, "label": identifier, "path": str(folder),
                         "projectKind": "local", "hostId": "local"})

    class DesktopPeer:
        tools = {"list_projects"}
        tool_schemas = {}

        def __init__(self, root, config, session, *, worker_id=None):
            self.config = config

        def project(self):
            return next(project for project in projects if project["projectId"] == self.config["project_id"])

        def model_choice(self, name, *, selected):
            return selected, {"effective": "unconfirmed"}

        def call(self, name, arguments):
            assert name == "list_projects", "Project preparation must not create chats or model input"
            return {"projects": projects}

        def close(self):
            pass

    monkeypatch.setattr(runtime, "Desktop", DesktopPeer)
    monkeypatch.setattr(runtime, "spawn_runner", Mock(return_value={"state": "protocol_fixture"}))
    monkeypatch.setenv("CODEX_THREAD_ID", "defaults-caller")
    monkeypatch.setenv("CODEX_APP_TOOLS_PIPE_PATH", "defaults-pipe")
    runtime.configure_desktop(app, "team", "owner", command=["protocol-fixture"])
    runtime.desktop_profile(app, "team", "owner", model="base-model", effort="low", project_id="shared")
    shared = desktop_projects.save(app, "team", "owner", "codex", "Shared",
                                   project_directory=projects[0]["path"])
    assert shared["worker_id"] is None
    desktop_projects.prepare(app, "team", "owner", "shared-preparation", revision=shared["revision"])
    app.worker_create("team", "owner", "Topic", "Inherit the shared Desktop defaults", worker_id="topic")

    # Explicitly configuring default Worker must not replace the Agent defaults.
    monkeypatch.setenv("CODEX_THREAD_ID", "override-caller")
    monkeypatch.setenv("CODEX_APP_TOOLS_PIPE_PATH", "override-pipe")
    runtime.configure_desktop(app, "team", "owner", worker_id="default")
    runtime.desktop_profile(app, "team", "owner", model="own-model", effort="high",
                            project_id="override", worker_id="default")
    own = desktop_projects.save(app, "team", "owner", "codex", "Own",
                                project_directory=projects[1]["path"], worker_id="default")
    desktop_projects.prepare(app, "team", "owner", "own-preparation", revision=own["revision"], worker_id="default")
    assert desktop_projects.discover(app, "team", "owner", worker_id="topic")["selected_project"]["projectId"] == "shared"

    adopted = {}
    for worker in ("topic", "default"):
        result = runtime.start(app, "team", "owner", worker_id=worker)
        assert result["kind"] == "desktop"
        app.bind("team", "owner", result["binding"], "session-" + worker, worker_id=worker)
        adopted[worker] = layout.local_path(root, "entry.json", worker).read_bytes()
    topic = read_json(layout.local_path(root, "entry.json", "topic"))
    assert topic["config"]["pipe_path"] == "defaults-pipe"
    assert topic["model_profile"]["model"] == "base-model"
    assert read_json(layout.local_path(root, "entry.json", "default"))["model_profile"]["model"] == "own-model"

    # Root defaults can change while both Workers retain their adopted values.
    monkeypatch.setenv("CODEX_THREAD_ID", "later-caller")
    monkeypatch.setenv("CODEX_APP_TOOLS_PIPE_PATH", "later-pipe")
    runtime.configure_desktop(app, "team", "owner")
    runtime.desktop_profile(app, "team", "owner", model="later-model", effort="medium", project_id="later")
    current = desktop_projects.plan(app, "team", "owner")
    later = desktop_projects.save(app, "team", "owner", "codex", "Later", revision=current["revision"],
                                  project_directory=projects[2]["path"])
    desktop_projects.prepare(app, "team", "owner", "later-preparation", revision=later["revision"])
    for worker, original in adopted.items():
        assert layout.local_path(root, "entry.json", worker).read_bytes() == original
    app.worker_create("team", "owner", "Future", "Check the new defaults", worker_id="future")
    assert model_profiles.runtime_config(root, "future")["pipe_path"] == "later-pipe"
    assert model_profiles.selected(root, "future")["model"] == "later-model"
    assert desktop_projects.project_directory(root, worker_id="future") == tmp_path / "later"
    assert desktop_projects.project_directory(root, worker_id="default") == tmp_path / "override"
    with pytest.raises(Conflict):
        runtime.desktop_profile(app, "team", "owner", model="forbidden", effort="low", worker_id="default")
