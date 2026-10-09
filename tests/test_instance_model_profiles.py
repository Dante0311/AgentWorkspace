"""Instance selection and native request contracts; these are not live model tests."""
from pathlib import Path
from unittest.mock import Mock

import pytest

from agent_workspace import model_profiles as profiles, runtime, transfer
from agent_workspace.util import Conflict, Error, Unavailable, read_json, write_json


@pytest.fixture
def root(tmp_path):
    root = tmp_path / "instance"
    root.mkdir()
    return root


@pytest.fixture
def desktop(root, monkeypatch):
    write_json(root / "runtime.json", {"codex": {"model": "target-model", "effort": "none"}})
    profile = profiles.selected(root)
    write_json(root / ".aw-local/entry.json", {"binding": "one", "config": {"kind": "desktop"}, "model_profile": profile})
    config = {"kind": "desktop", "command": ["fixture"], "pipe_path": "fixture", "caller_thread": "caller",
              "model": "caller-astra", "effort": "max"}
    schema = {"type": "object", "properties": {"model": {"type": "string"},
              "thinking": {"type": "string", "enum": ["none", "low", "max"]}}}
    rpc = Mock()
    rpc.request.return_value = {"tools": [{"name": name, "inputSchema": schema}
                               for name in ("create_thread", "send_message_to_thread", "read_thread", "list_projects")]}
    monkeypatch.setattr(runtime, "Rpc", Mock(return_value=rpc))
    adapter = runtime.Desktop(root, config, None)
    writes = []

    def call(name, arguments):
        if name == "list_projects":
            return {"projects": [{"projectId": "p", "projectKind": "local", "hostId": "local", "path": str(root)}]}
        if name == "read_thread":
            return {"thread": {"id": adapter.session, "cwd": str(root), "status": {"type": "idle"}}}
        writes.append((name, arguments))
        return {"threadId": "native", "hostId": "local"}

    adapter.call = call
    return adapter, writes, rpc


@pytest.mark.parametrize("choice", [None, {}, {"model": "target"}, {"effort": "low"},
                                    {"model": None, "effort": "low"}, {"model": "target", "effort": ""},
                                    {"model": "target", "effort": []}])
def test_missing_or_malformed_choice_never_creates_or_sends(root, desktop, choice):
    adapter, writes, _ = desktop
    write_json(root / "runtime.json", {"codex": choice})
    write_json(root / ".aw-local/entry.json", {"binding": "one", "config": {"kind": "desktop"}})
    with pytest.raises(Error):
        adapter.create("one")
    adapter.session = "existing"
    with pytest.raises(Error):
        adapter.notify("explicit test", "normal")
    assert not writes
    assert not (root / ".aw-local/launch.json").exists()


def test_target_choice_reaches_creation_later_input_and_reconnect(root, desktop):
    adapter, writes, rpc = desktop
    adapter.create("one")
    write_json(root / "runtime.json", {"codex": {"model": "next-model", "effort": "low"}})
    adapter.notify("later input", "normal")
    reconnected = runtime.Desktop(root, adapter.config, adapter.session)
    reconnected.call = adapter.call
    reconnected.notify("same-session recovery", "normal")
    assert len(writes) == 3
    assert all(params["model"] == "target-model" and params["thinking"] == "none" for _, params in writes)
    receipt = read_json(root / ".aw-local/launch.json")["model_profile"]
    assert receipt["native_accepted"] is True and receipt["effective"] == "unconfirmed"
    assert receipt["requested"]["source"]["path"] == "runtime.json"


def test_known_unsupported_desktop_parameter_rejects_without_fallback(root, desktop):
    adapter, writes, _ = desktop
    adapter.tool_schemas["create_thread"]["properties"]["thinking"]["enum"] = ["low"]
    with pytest.raises(Error):
        adapter.create("one")
    assert writes == []
    adapter.tool_schemas["send_message_to_thread"] = {"properties": {"model": {"type": "string"}}}
    with pytest.raises(Unavailable):
        adapter.notify("test", "normal")
    assert writes == []


def test_native_mismatch_preserves_creation_receipt_and_prevents_repeat(root, desktop):
    adapter, writes, _ = desktop
    original = adapter.call

    def call(name, arguments):
        result = original(name, arguments)
        if name == "create_thread":
            result.update(model="different-model", thinking="none")
        return result

    adapter.call = call
    with pytest.raises(Error):
        adapter.create("one")
    launch = read_json(root / ".aw-local/launch.json")
    assert launch["result"]["threadId"] == "native"
    assert launch["model_profile"]["effective"] == "mismatch"
    with pytest.raises(Conflict):
        adapter.create("one")
    assert len(writes) == 1


def test_legacy_migration_is_repeatable_and_preserves_connections_and_choice(root):
    config = {"kind": "codex", "model": "legacy", "command": ["codex", "-c", 'model="legacy"',
              "-c", 'model_reasoning_effort="none"', "-c", 'model_provider="mine"', "app-server"],
              "credential_env": "MY_KEY", "modelProvider": "mine", "caller_thread": "old-connection"}
    write_json(root / ".aw-local/runtime.json", config)
    local = profiles.migrate(root)
    assert local["command"] == ["codex", "-c", 'model_provider="mine"', "app-server"]
    assert local["credential_env"] == "MY_KEY" and local["caller_thread"] == "old-connection"
    choice = read_json(root / "runtime.json")["codex"]
    assert choice["model"] == "legacy" and choice["effort"] == "none"
    assert choice["migrated_from"]["path"] == ".aw-local/runtime.json"
    assert choice["migrated_from"]["fields"]["effort"] == "command:model_reasoning_effort"
    write_json(root / "runtime.json", {"codex": {"model": "user-edit", "effort": "low"}})
    # An old capture writer cannot reintroduce a second editable model source.
    write_json(root / ".aw-local/runtime.json", {**config, "caller_thread": "new-connection"})
    for _ in range(2):
        profiles.migrate(root)
    assert profiles.selected(root)["model"] == "user-edit"
    assert read_json(root / ".aw-local/runtime.json")["caller_thread"] == "new-connection"
    assert read_json(root / ".aw-local/model-migration.json")[0]["choice"]["model"] == "legacy"


def test_partial_or_conflicting_migration_does_not_guess(root):
    path = root / ".aw-local/runtime.json"
    write_json(path, {"kind": "desktop", "model": "legacy", "pipe_path": "connection"})
    profiles.migrate(root)
    assert "effort" not in read_json(root / "runtime.json")["codex"]
    with pytest.raises(Error):
        profiles.selected(root)
    conflicting = {"kind": "codex", "model": "one", "command": ["codex", "-c", 'model="two"', "app-server"]}
    write_json(path, conflicting)
    with pytest.raises(Conflict):
        profiles.migrate(root)
    assert read_json(path) == conflicting


def test_environment_configuration_does_not_replace_the_instance_choice(root):
    profiles.configure(root, {"kind": "desktop", "model": "selected", "effort": "low", "pipe_path": "old"})
    profiles.configure(root, {"kind": "desktop", "pipe_path": "new", "caller_thread": "actual"})
    assert profiles.selected(root)["model"] == "selected"
    assert "model" not in read_json(root / ".aw-local/runtime.json")
    assert read_json(root / ".aw-local/runtime.json")["pipe_path"] == "new"


def test_migration_provenance_survives_an_immediate_explicit_profile_update(root):
    write_json(root / ".aw-local/runtime.json", {"kind": "desktop", "model": "old", "effort": "none", "pipe_path": "p"})
    profiles.configure(root, {"kind": "desktop", "model": "new", "effort": "low", "pipe_path": "p"})
    assert profiles.selected(root)["model"] == "new"
    history = read_json(root / ".aw-local/model-migration.json")
    assert history[0]["choice"] == {"model": "old", "effort": "none"}
    assert history[0]["fields"] == {"model": "model", "effort": "effort"}


def test_unprofiled_existing_native_session_requires_handoff(root, desktop):
    adapter, writes, _ = desktop
    write_json(root / ".aw-local/entry.json", {"binding": "one", "config": {"kind": "desktop"}})
    adapter.session = "legacy-native"
    with pytest.raises(Error):
        adapter.notify("cannot silently apply a new choice", "normal")
    assert not writes


def codex_peer(root, monkeypatch, *, catalog=None, custom=False, session=None):
    profile = profiles.selected(root)
    write_json(root / ".aw-local/entry.json", {"binding": "one", "config": {"kind": "codex"}, "model_profile": profile})
    rpc = Mock()

    def request(method, params, **kwargs):
        if method == "model/list":
            if catalog is None:
                raise Unavailable("catalog unavailable")
            return {"data": catalog, "nextCursor": None}
        if method == "thread/read":
            return {"thread": {"id": "native", "status": {"type": "idle"}}}
        if method == "turn/start":
            return {"turn": {"id": "t"}}
        return {"thread": {"id": "native"}}

    rpc.request.side_effect = request
    monkeypatch.setattr(runtime, "Rpc", Mock(return_value=rpc))
    config = {"kind": "codex", "command": ["fixture"], "model": "caller-astra", "effort": "max"}
    if custom:
        config["modelProvider"] = "custom"
    adapter = runtime.Codex(Mock(), "sea", "alice", "one", root, config, session)
    return adapter, rpc


@pytest.mark.parametrize("session", [None, "native"])
def test_codex_create_resume_and_normal_input_are_explicit(root, monkeypatch, session):
    write_json(root / "runtime.json", {"codex": {"model": "target", "effort": "none"}})
    adapter, rpc = codex_peer(root, monkeypatch, session=session)
    write_json(root / "runtime.json", {"codex": {"model": "later", "effort": "low"}})
    adapter.notify("test input", "normal")
    method = "thread/resume" if session else "thread/start"
    creation = next(call.args[1] for call in rpc.request.call_args_list if call.args[0] == method)
    assert creation["model"] == "target" and creation["config"]["model_reasoning_effort"] == "none"
    params = next(call.args[1] for call in rpc.request.call_args_list if call.args[0] == "turn/start")
    assert params["model"] == "target" and params["effort"] == "none"
    assert adapter.model_receipt["effective"] == "unconfirmed"


def test_catalog_rejects_known_unsupported_pair_before_creation(root, monkeypatch):
    write_json(root / "runtime.json", {"codex": {"model": "target", "effort": "none"}})
    with pytest.raises(Error):
        codex_peer(root, monkeypatch, catalog=[{"model": "target", "supportedReasoningEfforts": [{"reasoningEffort": "low"}]}])
    rpc = runtime.Rpc.return_value
    assert not any(call.args[0] in ("thread/start", "thread/resume", "turn/start") for call in rpc.request.call_args_list)
    assert not (root / ".aw-local/launch.json").exists()


def test_custom_provider_does_not_use_builtin_account_catalog(root, monkeypatch):
    write_json(root / "runtime.json", {"codex": {"model": "gateway-model", "effort": "low"}})
    adapter, rpc = codex_peer(root, monkeypatch, catalog=[], custom=True)
    assert not any(call.args[0] == "model/list" for call in rpc.request.call_args_list)
    assert adapter.model_receipt["validation"]["catalog"] == "custom_provider_unconfirmed"


def test_automatic_start_and_transfer_reject_missing_profile_before_side_effects(root, monkeypatch):
    app = Mock()
    app.root.return_value = root
    app.agent.return_value = {"current": None}
    write_json(root / ".aw-local/runtime.json", {"kind": "desktop"})
    rpc = Mock()
    monkeypatch.setattr(runtime, "Rpc", rpc)
    with pytest.raises(Error):
        runtime.start(app, "sea", "alice")
    with pytest.raises(Error):
        transfer.preflight(app, "sea", "alice", {"kind": "desktop"}, root)
    app.reserve.assert_not_called()
    rpc.assert_not_called()


@pytest.mark.parametrize("choice", [{}, {"model": "target", "effort": None}])
def test_codex_missing_choice_does_not_open_or_resume_native_client(root, monkeypatch, choice):
    write_json(root / "runtime.json", {"codex": choice})
    write_json(root / ".aw-local/entry.json", {"binding": "one", "config": {"kind": "codex"}})
    rpc = Mock()
    monkeypatch.setattr(runtime, "Rpc", rpc)
    with pytest.raises(Error):
        runtime.Codex(Mock(), "sea", "alice", "one", root, {"kind": "codex"}, session="existing")
    rpc.assert_not_called()


def test_template_copy_checkpoint_and_next_binding_are_independent(app):
    from agent_workspace.util import encode
    store = app.store("sea")
    paths = {"definitions/reviewer/definition.md": b"Review only.",
             "definitions/reviewer/runtime.json": encode({"codex": {"model": "template", "effort": "none"}})}
    store.change("main", paths, {path: None for path in paths}, "Create optional role profile")
    app.create("sea", "alice", definition="definitions/reviewer")
    root = app.root("sea", "alice")
    app.configure("sea", "alice", {"kind": "desktop", "command": ["fixture"]})
    binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", binding, "native")
    path = "definitions/reviewer/runtime.json"
    store.change("main", {path: encode({"codex": {"model": "new-template", "effort": "low"}})},
                 {path: store.snapshot().entries[path]}, "Update role template")
    assert profiles.adopted(root, binding)["model"] == "template"
    assert profiles.selected(root)["model"] == "template"
    write_json(root / "runtime.json", {"codex": {"model": "instance-edit", "effort": "low"}})
    point = app.checkpoint("sea", "alice", "profile edit for successor", binding=binding)
    snapshot = store.snapshot("instance/alice", revision=point["revision"])
    assert snapshot.json("runtime.json")["codex"]["model"] == "instance-edit"
    assert not any(path.startswith(".aw-local/") for path in snapshot.entries)
    assert profiles.adopted(root, binding)["model"] == "template"
    app.stop("sea", "alice", binding, point["id"])
    app.finish_stop("sea", "alice", binding, observed_idle=True)
    successor = app.reserve("sea", "alice")["binding"]
    assert successor != binding
    assert profiles.adopted(root, successor)["model"] == "instance-edit"
