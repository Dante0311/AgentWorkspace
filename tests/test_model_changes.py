"""One-time model-choice requests: real filesystem boundaries, mocked native consent."""
import json
from types import SimpleNamespace

import pytest

from agent_workspace import layout, model_changes
from agent_workspace.app import App
from agent_workspace.commands import execute
from agent_workspace.util import Conflict, Error, read_json, write_json


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    """One isolated real Git workspace shared by these tests to avoid repeated fixture commits."""
    root = tmp_path_factory.mktemp("model-changes")
    app = App(root / "home")
    app.workspace_init("sea", str(root / "sea.git"))
    bindings = {}
    for agent_id in ("alice", "bob"):
        app.create("sea", agent_id)
        bindings[agent_id] = app.reserve("sea", agent_id)["binding"]
        app.bind("sea", agent_id, bindings[agent_id], "native-" + agent_id)
    app.configure("sea", "bob", {"kind": "codex", "model": "before-bob", "effort": "low",
                                  "command": ["codex", "app-server"]})
    app.create("sea", "carol")
    app.configure("sea", "carol", {"kind": "desktop", "model": "before-carol", "effort": "medium",
                                    "command": ["codex", "app-server"], "pipe_path": "fixture-pipe"})
    return app, bindings


def codex_targets(pair):
    # Alice remains a manual caller. Bob and Carol are saved Codex targets.
    app, bindings = pair
    return app, bindings


@pytest.fixture(autouse=True)
def restore_target_files(pair):
    app, _ = pair
    paths = {}
    for agent_id in ("bob", "carol"):
        root = app.root("sea", agent_id)
        for path in (layout.instance_path(root, "config.json"),
                     layout.local_path(root, "runtime.json"),
                     layout.local_path(root, "entry.json"),
                     layout.local_path(root, "watch.json")):
            paths[path] = path.read_bytes() if path.exists() else None
    yield
    for path, original in paths.items():
        if original is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(original)


def config_path(app, agent_id):
    return layout.instance_path(app.root("sea", agent_id), "config.json")


def seed_config(app, agent_id, model, effort):
    value = {"codex": {"model": model, "effort": effort, "provider": "fixture-provider"},
             "connection": {"session": f"native-{agent_id}"},
             "entry": {"binding": f"binding-{agent_id}"},
             "watch": {"enabled": False}, "other": {"keep": True}}
    write_json(config_path(app, agent_id), value)
    return value


def seed_local_state(app, agent_id):
    root = app.root("sea", agent_id)
    write_json(layout.local_path(root, "entry.json"), {"binding": f"binding-{agent_id}",
                                                        "session": f"native-{agent_id}"})
    write_json(layout.local_path(root, "watch.json"), {"enabled": False, "reason": "fixture"})
    paths = (layout.local_path(root, "runtime.json"), layout.local_path(root, "entry.json"),
             layout.local_path(root, "watch.json"))
    return {agent_id: {path: path.read_bytes() for path in paths}}


def request(app, bindings, request_id="review-one"):
    return execute(app, "agent.model-change-request", {
        "workspace": "sea", "request_id": request_id,
        "changes": [
            {"agent_id": "bob", "model": "gpt-6-astra", "effort": "high"},
            {"agent_id": "carol", "model": "gpt-6-luna", "effort": "medium"},
        ],
    }, actor=("sea", "alice", bindings["alice"]))


def replace_binding(app, agent_id, binding, label):
    point = app.checkpoint("sea", agent_id, f"model-change test {label}", binding=binding,
                           checkpoint_id=f"cp-{label}")
    handoff = app.takeover("sea", agent_id, binding, point["id"], confirm=True)
    successor = app.reserve("sea", agent_id, expected_handoff=handoff["handoff"]["id"])["binding"]
    app.bind("sea", agent_id, successor, f"native-{agent_id}-{label}")
    return successor


def test_prepare_then_explicit_review_updates_batch_and_preserves_unrelated_configuration(pair, monkeypatch):
    app, bindings = codex_targets(pair)
    request_id = "batch"
    before = {agent_id: seed_config(app, agent_id, f"before-{agent_id}", "low")
              for agent_id in ("bob", "carol")}
    local_before = {agent_id: seed_local_state(app, agent_id)[agent_id]
                    for agent_id in before}
    before_bytes = {agent_id: config_path(app, agent_id).read_bytes() for agent_id in before}

    prepared = request(app, bindings, request_id)
    assert prepared["state"] == "pending"
    assert prepared["approval_required"] is True
    assert prepared["entry_changed"] is False
    assert {agent_id: config_path(app, agent_id).read_bytes() for agent_id in before} == before_bytes

    confirmations = []
    monkeypatch.setattr(model_changes, "native_confirm",
                        lambda record: confirmations.append(record["request_id"]) or True)
    result = execute(app, "agent.model-change-review",
                     {"workspace": "sea", "request_id": request_id},
                     actor=("sea", "alice", bindings["alice"]))
    assert confirmations == [request_id]
    assert result["state"] == "applied"
    assert result["entry_changed"] is False
    for agent_id, model, effort in (("bob", "gpt-6-astra", "high"),
                                    ("carol", "gpt-6-luna", "medium")):
        saved = read_json(config_path(app, agent_id))
        assert saved == {**before[agent_id], "codex": {
            **before[agent_id]["codex"], "model": model, "effort": effort}}
        assert {path: path.read_bytes() for path in local_before[agent_id]} == local_before[agent_id]

    # A second apply is a read of the completed request and does not rewrite either target.
    def reject_rewrite(path, value):
        if str(path).endswith("config.json"):
            raise AssertionError(f"Applied request rewrote {path}")
        return original_write_json(path, value)

    original_write_json = model_changes.write_json
    monkeypatch.setattr(model_changes, "write_json", reject_rewrite)
    repeated = execute(app, "agent.model-change-review",
                       {"workspace": "sea", "request_id": request_id},
                       actor=("sea", "alice", bindings["alice"]))
    assert repeated["state"] == "applied"


def test_declining_review_keeps_request_pending_and_changes_nothing(pair, monkeypatch):
    app, bindings = codex_targets(pair)
    request_id = "decline"
    seed_config(app, "bob", "before-bob", "low")
    seed_config(app, "carol", "before-carol", "low")
    request(app, bindings, request_id)
    original = {agent_id: config_path(app, agent_id).read_bytes() for agent_id in ("bob", "carol")}

    monkeypatch.setattr(model_changes, "native_confirm", lambda record: False)
    result = execute(app, "agent.model-change-review",
                     {"workspace": "sea", "request_id": request_id},
                     actor=("sea", "alice", bindings["alice"]))
    assert result["confirmation"] == "cancelled"
    assert {agent_id: config_path(app, agent_id).read_bytes() for agent_id in original} == original
    assert execute(app, "agent.model-change-show",
                   {"workspace": "sea", "request_id": request_id})["state"] == "pending"
    for actor in (None, ("sea", "alice", bindings["alice"])):
        with pytest.raises(Error, match="Unknown operation: agent.model-change-apply"):
            execute(app, "agent.model-change-apply",
                    {"workspace": "sea", "request_id": request_id}, actor=actor)


def test_review_is_bound_to_requester_and_does_not_prompt_another_agent(pair, monkeypatch):
    app, bindings = codex_targets(pair)
    request_id = "wrong-caller"
    seed_config(app, "bob", "before-bob", "low")
    seed_config(app, "carol", "before-carol", "low")
    request(app, bindings, request_id)
    monkeypatch.setattr(model_changes, "native_confirm",
                        lambda record: pytest.fail("Wrong caller opened native confirmation"))
    with pytest.raises(Error, match="Only the Agent that prepared"):
        execute(app, "agent.model-change-review",
                {"workspace": "sea", "request_id": request_id},
                actor=("sea", "bob", bindings["bob"]))
    assert execute(app, "agent.model-change-show",
                   {"workspace": "sea", "request_id": request_id})["state"] == "pending"


def test_native_confirmation_is_unavailable_off_windows(pair, monkeypatch):
    app, bindings = codex_targets(pair)
    request_id = "non-windows"
    seed_config(app, "bob", "before-bob", "low")
    seed_config(app, "carol", "before-carol", "low")
    request(app, bindings, request_id)
    original = {agent_id: config_path(app, agent_id).read_bytes() for agent_id in ("bob", "carol")}
    monkeypatch.setattr(model_changes, "os", SimpleNamespace(name="posix"))
    with pytest.raises(Error, match="unsupported on this platform"):
        model_changes.native_confirm({"changes": []})
    assert {agent_id: config_path(app, agent_id).read_bytes() for agent_id in original} == original
    assert execute(app, "agent.model-change-show",
                   {"workspace": "sea", "request_id": request_id})["state"] == "pending"


def test_native_confirmation_messagebox_failure_raises_and_leaves_batch_pending(pair, monkeypatch):
    app, bindings = codex_targets(pair)
    request_id = "messagebox"
    for agent_id in ("bob", "carol"):
        seed_config(app, agent_id, f"before-{agent_id}", "low")
    request(app, bindings, request_id)
    before = {agent_id: config_path(app, agent_id).read_bytes() for agent_id in ("bob", "carol")}
    calls = []

    def message_box(hwnd, text, title, flags):
        calls.append((hwnd, text, title, flags))
        return 0  # MessageBoxW failure is not IDYES.

    monkeypatch.setattr(model_changes.ctypes, "WinDLL",
                        lambda name, use_last_error: SimpleNamespace(MessageBoxW=message_box))
    with pytest.raises(OSError):
        execute(app, "agent.model-change-review",
                {"workspace": "sea", "request_id": request_id},
                actor=("sea", "alice", bindings["alice"]))
    assert calls and calls[0][2] == "确认模型默认值"
    assert calls[0][3] & 0x00000100  # MB_DEFBUTTON2: decline is the default.
    assert "before-bob" in calls[0][1] and "gpt-6-astra" in calls[0][1]
    assert "sea" in calls[0][1] and "alice" in calls[0][1]
    assert {agent_id: config_path(app, agent_id).read_bytes() for agent_id in before} == before
    assert execute(app, "agent.model-change-show",
                   {"workspace": "sea", "request_id": request_id})["state"] == "pending"


def test_interrupted_applying_request_is_never_replayed(pair, monkeypatch):
    app, bindings = codex_targets(pair)
    request_id = "interrupted"
    seed_config(app, "bob", "before-bob", "low")
    seed_config(app, "carol", "before-carol", "low")
    request(app, bindings, request_id)
    record_path = app.home / f"model-change-requests/sea/{request_id}.json"
    record = read_json(record_path)
    record["state"] = "applying"
    write_json(record_path, record)
    before = {agent_id: config_path(app, agent_id).read_bytes() for agent_id in ("bob", "carol")}
    monkeypatch.setattr(model_changes, "native_confirm",
                        lambda record: pytest.fail("Interrupted request must not be replayed"))

    result = execute(app, "agent.model-change-review",
                     {"workspace": "sea", "request_id": request_id},
                     actor=("sea", "alice", bindings["alice"]))
    assert result["state"] == "applying"
    assert {agent_id: config_path(app, agent_id).read_bytes() for agent_id in before} == before


@pytest.mark.parametrize("change", [
    {"agent_id": "bob", "model": "target", "effort": "high", "directory": "../../outside"},
    {"agent_id": "../outside", "model": "target", "effort": "high"},
])
def test_request_rejects_extra_fields_and_path_injection_without_creating_request(pair, change):
    app, bindings = codex_targets(pair)
    with pytest.raises(Error):
        execute(app, "agent.model-change-request", {
            "workspace": "sea", "request_id": "invalid-request", "changes": [change]},
            actor=("sea", "alice", bindings["alice"]))
    with pytest.raises(Error, match="not found"):
        execute(app, "agent.model-change-show",
                {"workspace": "sea", "request_id": "invalid-request"})
    assert not (app.home / "model-change-requests/sea/invalid-request.json").exists()


def test_stale_value_in_any_target_blocks_entire_batch_before_writing(pair, monkeypatch):
    app, bindings = codex_targets(pair)
    request_id = "stale"
    seed_config(app, "bob", "before-bob", "low")
    seed_config(app, "carol", "before-carol", "low")
    request(app, bindings, request_id)
    bob_before = config_path(app, "bob").read_bytes()
    write_json(config_path(app, "carol"), {"codex": {"model": "changed-after-review", "effort": "low"}})

    # Confirmation succeeds, then the complete batch preflight detects the changed second target.
    monkeypatch.setattr(model_changes, "native_confirm", lambda record: True)
    with pytest.raises(Conflict, match="changed after the request was prepared"):
        execute(app, "agent.model-change-review",
                {"workspace": "sea", "request_id": request_id},
                actor=("sea", "alice", bindings["alice"]))
    assert config_path(app, "bob").read_bytes() == bob_before
    assert read_json(app.home / f"model-change-requests/sea/{request_id}.json")["state"] == "pending"


def test_request_id_cannot_be_reused_for_a_different_scope(pair):
    app, bindings = codex_targets(pair)
    request_id = "scope"
    seed_config(app, "bob", "before-bob", "low")
    seed_config(app, "carol", "before-carol", "low")
    request(app, bindings, request_id)
    with pytest.raises(Conflict, match="different model-change scope"):
        execute(app, "agent.model-change-request", {
            "workspace": "sea", "request_id": request_id,
            "changes": [{"agent_id": "bob", "model": "different-model", "effort": "high"}]},
            actor=("sea", "alice", bindings["alice"]))


def test_z_pending_request_rejects_changed_target_and_requester_bindings(pair, monkeypatch):
    app, bindings = codex_targets(pair)
    request_id = "binding-changed"
    for agent_id in ("bob", "carol"):
        seed_config(app, agent_id, f"before-{agent_id}", "low")
    request(app, bindings, request_id)
    bob_before = config_path(app, "bob").read_bytes()
    replace_binding(app, "bob", bindings["bob"], "bob-successor")
    monkeypatch.setattr(model_changes, "native_confirm", lambda record: True)
    with pytest.raises(Conflict, match="changed after the request was prepared"):
        execute(app, "agent.model-change-review",
                {"workspace": "sea", "request_id": request_id},
                actor=("sea", "alice", bindings["alice"]))
    assert config_path(app, "bob").read_bytes() == bob_before

    replace_binding(app, "alice", bindings["alice"], "alice-successor")
    monkeypatch.setattr(model_changes, "native_confirm",
                        lambda record: pytest.fail("Stale requester must not open confirmation"))
    with pytest.raises(Error):
        execute(app, "agent.model-change-review",
                {"workspace": "sea", "request_id": request_id},
                actor=("sea", "alice", bindings["alice"]))
    assert read_json(app.home / f"model-change-requests/sea/{request_id}.json")["state"] == "pending"
