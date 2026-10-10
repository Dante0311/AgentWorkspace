"""Workbench shared revisions use real local Git; local status is a fixture."""
import pytest

from agent_workspace.app import App
from agent_workspace.commands import execute
from agent_workspace.server import build_state
from agent_workspace.util import Error, write_json


@pytest.fixture
def state_app(app):
    app.create("sea", "alice")
    app.create("sea", "bob")
    return app


@pytest.mark.parametrize("local_unreadable", [False, True])
def test_workspace_response_uses_one_shared_snapshot(state_app, tmp_path, monkeypatch, local_unreadable):
    app = state_app
    original = app.store("sea").snapshot()
    peer = App(tmp_path / "peer-home")
    peer.workspace_connect("copy", str(tmp_path / "sea.git"))
    workspace_show = app.workspace_show
    status_path = app.root("sea", "alice") / ".aw-local/status.json"
    local_status = {"state": "fixture-after-shared-snapshot", "observed_at": "fixture-later-local-observation"}

    def concurrent_commit(*args, **kwargs):
        shared = workspace_show(*args, **kwargs)
        peer.archive("copy", "alice")
        peer.relation("copy", "projects", "add", "later-project", "https://example.invalid/project")
        if local_unreadable:
            status_path.write_text("{", encoding="utf-8")
        else:
            write_json(status_path, local_status)
        return shared

    with monkeypatch.context() as race:
        race.setattr(app, "workspace_show", concurrent_commit)
        value = build_state(app)

    workspace = value["workspaces"][0]
    agents = {item["id"]: item for item in value["agents"]}
    assert workspace["snapshot_revision"] == original.revision
    assert workspace["projects"] == original.json("workspace.json")["projects"]
    assert set(agents) == {"alice", "bob"}
    assert agents["alice"]["archived"] is False
    assert all(item["snapshot_revision"] == original.revision for item in agents.values())
    assert agents["bob"]["revision"] == original.entries["agents/bob.json"]
    if local_unreadable:
        assert agents["alice"]["unknown_reason"] == "instance_observation_failed"
        assert "runtime" not in agents["alice"]
        assert any(error.get("agent") == "alice" for error in value["errors"])
        write_json(status_path, local_status)
    else:
        assert agents["alice"]["revision"] == original.entries["agents/alice.json"]
        assert agents["alice"]["runtime"]["state"] == local_status["state"]
        assert agents["alice"]["runtime"]["observed_at"] == local_status["observed_at"]
        assert agents["alice"]["observation_source"]["kind"] == "local_registry_and_runtime"
        assert value["errors"] == []

    latest = app.store("sea").snapshot()
    assert latest.revision != original.revision
    assert latest.json("agents/alice.json")["archived"] is True
    assert "later-project" in latest.json("workspace.json")["projects"]
    assert app.workspace_show("sea", snapshot=original)["revision"] == original.revision
    assert {item["id"] for item in app.agents("sea", archived=False, snapshot=original)} == {"alice", "bob"}
    assert app.agents("sea", archived=True, snapshot=original) == []
    assert app.show("sea", "alice", snapshot=original)["archived"] is False
    assert {item["id"] for item in app.agents("sea", archived=True)} == {"alice"}
    assert app.show("sea", "alice")["archived"] is True
    refreshed = build_state(app)
    assert refreshed["workspaces"][0]["snapshot_revision"] == latest.revision
    assert all(item["snapshot_revision"] == latest.revision for item in refreshed["agents"])
    assert next(item for item in refreshed["agents"] if item["id"] == "alice")["archived"] is True
    assert app.store("sea").snapshot().revision == latest.revision


def test_binding_details_use_the_same_shared_snapshot(state_app, monkeypatch):
    app = state_app
    binding = app.reserve("sea", "alice")["binding"]
    original = app.store("sea").snapshot()
    workspace_show = app.workspace_show

    def bind_after_workspace_read(*args, **kwargs):
        shared = workspace_show(*args, **kwargs)
        app.bind("sea", "alice", binding, "fixture-bound-after-shared-read")
        return shared

    with monkeypatch.context() as race:
        race.setattr(app, "workspace_show", bind_after_workspace_read)
        value = build_state(app)

    alice = next(item for item in value["agents"] if item["id"] == "alice")
    assert alice["snapshot_revision"] == original.revision
    assert alice["binding"] == original.json(f"bindings/{binding}.json")
    assert alice["revision"] == original.entries["agents/alice.json"]
    assert app.show("sea", "alice")["binding"]["session"] == "fixture-bound-after-shared-read"
    assert app.store("sea").snapshot().revision != original.revision


def test_unavailable_workspace_has_no_agent_projection(state_app, monkeypatch):
    store = state_app.store("sea")

    def unavailable(*args, **kwargs):
        raise Error("fixture shared read unavailable")

    monkeypatch.setattr(store, "snapshot", unavailable)
    value = build_state(state_app)
    assert value["workspaces"][0]["unknown_reason"] == "workspace_read_failed"
    assert "snapshot_revision" not in value["workspaces"][0]
    assert value["agents"] == []
    assert value["errors"]


@pytest.mark.parametrize("command,arguments", [
    ("workspace.show", {"workspace": "sea"}),
    ("agent.list", {"workspace": "sea"}),
    ("agent.show", {"workspace": "sea", "agent_id": "alice"}),
    ("runtime.status", {"workspace": "sea", "agent_id": "alice"}),
])
@pytest.mark.parametrize("snapshot", [None, {"revision": "untrusted"}])
def test_commands_cannot_supply_internal_snapshots(tmp_path, monkeypatch, command, arguments, snapshot):
    app = App(tmp_path / "home")

    def unexpected_store(*args):
        raise AssertionError("Snapshot command input reached shared storage")

    monkeypatch.setattr(app, "store", unexpected_store)
    with pytest.raises(Error):
        execute(app, command, {**arguments, "snapshot": snapshot})
