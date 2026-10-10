"""Command boundaries and bounded local work, without timing-based assertions."""
from collections import Counter
from functools import partial
import inspect
import queue
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent_workspace import bridges, commands, runtime
from agent_workspace.messages import Messages
from agent_workspace.util import Conflict, Error, read_json, write_json


ACTOR = ("sea", "alice", "b-current")


@pytest.fixture
def local_app(tmp_path):
    app = Mock()
    app.home = tmp_path
    app.root.return_value = tmp_path
    app.agent.return_value = {"current": ACTOR[2]}
    app.require_binding.return_value = ({}, {"kind": "codex"})
    app.checkpoint.return_value = {"revision": "saved"}
    return app


def runner_for(app):
    runner = runtime.Runner(app, *ACTOR[:2])
    runner.binding = ACTOR[2]
    runner.adapter = object.__new__(runtime.Codex)
    runner.adapter.profile = {"model": "fixture-model", "effort": "low", "source": {"path": "runtime.json"}}
    runner.adapter.profile_validation = {"catalog": "fixture_unconfirmed"}
    runner.adapter.completed = queue.Queue()
    runner.adapter.status = Mock(return_value="idle")
    runner.adapter.notify = Mock(return_value={"turn": {"id": "t1"}})
    return runner


def enqueue(app, identifier, **kwargs):
    return runtime.queue_input(app, *ACTOR[:2], identifier, request_id=identifier, **kwargs)


def test_partial_handlers_expose_real_parameters(local_app):
    for handler in commands.command_map(local_app).values():
        if isinstance(handler, partial):
            assert all(p.kind != p.VAR_KEYWORD for p in inspect.signature(handler).parameters.values())


def test_agent_input_defaults_to_caller(local_app):
    result = commands.execute(local_app, "agent.input", {"text": "hello"}, actor=ACTOR)
    assert result["text"] == "hello" and result["binding"] == ACTOR[2]
    local_app.root.assert_called_with("sea", "alice", None)


@pytest.mark.parametrize("arguments", [{}, {"text": "hello", "unknown": True}, []])
def test_bad_arguments_fail_before_any_operation(local_app, arguments):
    with pytest.raises(Error, match="arguments"):
        commands.execute(local_app, "agent.input", arguments, actor=ACTOR)
    local_app.require_binding.assert_not_called()
    local_app.root.assert_not_called()


def test_handler_type_error_is_not_relabelled(local_app):
    failure = TypeError("internal implementation error")

    def show(workspace, agent_id, directory=None):
        raise failure

    local_app.show = show
    with pytest.raises(TypeError) as error:
        commands.execute(local_app, "agent.show", {}, actor=ACTOR)
    assert error.value is failure


@pytest.mark.parametrize("command", sorted(commands.USER_MANAGEMENT))
def test_management_commands_are_explicitly_rejected(local_app, command):
    with pytest.raises(Error, match="user-management"):
        commands.execute(local_app, command, {}, actor=ACTOR)
    local_app.require_binding.assert_not_called()


@pytest.mark.parametrize("field", ["workspace", "agent_id", "binding"])
def test_bound_operations_cannot_change_caller(local_app, field):
    with pytest.raises(Conflict, match="calling"):
        commands.execute(local_app, "message.send", {"to": "bob", "content": "hello", field: "other"}, actor=ACTOR)
    local_app.store.assert_not_called()


def test_new_agent_id_is_not_taken_from_caller(local_app):
    def create(workspace, name, agent_id=None):
        return workspace, name, agent_id

    local_app.create = create
    assert commands.execute(local_app, "agent.create", {"name": "bob"}, actor=ACTOR) == ("sea", "bob", None)


def test_explicit_read_target_is_preserved(local_app):
    def show(workspace, agent_id):
        return workspace, agent_id

    local_app.show = show
    assert commands.execute(local_app, "agent.show", {"workspace": "other", "agent_id": "bob"}, actor=ACTOR) == ("other", "bob")
    local_app.require_binding.assert_not_called()


def test_work_owner_is_not_inferred_from_caller(local_app):
    def create(workspace, owner, content):
        return owner

    local_app.work_create = create
    with pytest.raises(Error, match="owner"):
        commands.execute(local_app, "work.create", {"content": "explicit work"}, actor=ACTOR)


def test_asset_operation_cannot_override_command(local_app):
    path = local_app.root() / "notes.md"
    path.write_text("original", encoding="utf-8")
    with pytest.raises(Error, match="operation"):
        commands.execute(local_app, "asset.read", {"path": "notes.md", "operation": "write", "content": "changed"}, actor=ACTOR)
    assert path.read_text(encoding="utf-8") == "original"
    assert commands.execute(local_app, "asset.read", {"path": "notes.md"}, actor=ACTOR)["content"] == "original"


def test_enqueue_does_not_read_history_when_counter_exists(local_app, monkeypatch):
    for index in range(100):
        enqueue(local_app, f"old-{index}")
    reads = Mock(wraps=runtime.read_json)
    monkeypatch.setattr(runtime, "read_json", reads)
    assert enqueue(local_app, "new")["sequence"] == 101
    assert not [call for call in reads.call_args_list if call.args[0].stem.startswith("old-")]


def test_missing_counter_recovers_from_existing_sequences(local_app):
    first = enqueue(local_app, "first")
    (local_app.root() / ".aw-local/input-sequence.json").unlink()
    assert enqueue(local_app, "next")["sequence"] == first["sequence"] + 1


def test_failed_enqueue_can_leave_gap_but_not_reuse_sequence(local_app, monkeypatch):
    enqueue(local_app, "first")
    path = local_app.root() / ".aw-local/inputs/next.json"
    real_write = runtime.write_json

    def fail_input(target, value):
        if target == path:
            raise OSError("input write failed")
        real_write(target, value)

    monkeypatch.setattr(runtime, "write_json", fail_input)
    with pytest.raises(OSError):
        enqueue(local_app, "next")
    reserved = read_json(local_app.root() / ".aw-local/input-sequence.json")
    monkeypatch.setattr(runtime, "write_json", real_write)
    assert enqueue(local_app, "next")["sequence"] > reserved


def test_one_input_pass_reads_each_record_once(local_app, monkeypatch):
    folder = local_app.root() / ".aw-local/inputs"
    for index in range(100):
        record = enqueue(local_app, f"old-{index}")
        write_json(folder / f"old-{index}.json", {**record, "state": "completed"})
    initial = enqueue(local_app, "boot", purpose="initial")
    write_json(folder / "boot.json", {**initial, "state": "submitted", "result": {"turn": {"id": "t0"}}})
    enqueue(local_app, "new")
    reads = Mock(wraps=runtime.read_json)
    monkeypatch.setattr(runtime, "read_json", reads)
    runner = runner_for(local_app)
    runner.adapter.completed.put({"id": "t0", "status": "completed"})
    records = runner._read_inputs()
    assert len(records) == 2
    runner._complete_inputs(records)
    runner._inputs(records)
    counts = Counter(call.args[0] for call in reads.call_args_list if call.args[0].parent == folder)
    assert len(counts) == 102 and set(counts.values()) == {1}
    assert read_json(folder / "boot.json")["checkpoint_revision"] == "saved"
    runner.adapter.notify.assert_called_once_with("new", "normal")


def test_empty_input_pass_does_not_fall_back_to_another_read(local_app, monkeypatch):
    runner = runner_for(local_app)
    reads = Mock(wraps=runtime.read_json)
    monkeypatch.setattr(runtime, "read_json", reads)
    runner._complete_inputs([])
    runner._inputs([])
    reads.assert_not_called()


def message_snapshot(records=None):
    values = {"workspace.json": {"locator": "local:sea"}, "agents/alice.json": {}, "bindings/b-current.json": {}}
    values.update(records or {})
    return SimpleNamespace(entries={path: path for path in values}, json=lambda path, default=None: values.get(path, default))


def incoming(identifier, target="alice", timestamp="1"):
    return {"id": identifier, "to": {"workspace": "local:sea", "agent": target},
            "from": {"workspace": "local:sea", "agent": "bob"}, "delivery": "normal", "created_at": timestamp}


def test_empty_poll_uses_one_fresh_snapshot(local_app):
    store = local_app.store.return_value
    snap = message_snapshot()
    store.snapshot.return_value = snap
    assert Messages(local_app).poll(*ACTOR) == {"state": "empty"}
    store.snapshot.assert_called_once_with()
    local_app.require_binding.assert_called_once_with(*ACTOR, snapshot=snap)
    store.change.assert_not_called()


def test_list_filtering_and_later_queries_use_fresh_snapshot(local_app):
    store = local_app.store.return_value
    first = message_snapshot({"message-index/z.json": incoming("z", timestamp="1"),
                              "message-index/a.json": incoming("a", timestamp="2"),
                              "message-index/other.json": incoming("other", target="someone"),
                              "acks/z.json": {"message_id": "z"}})
    store.snapshot.side_effect = [first, message_snapshot()]
    messages = Messages(local_app)
    assert [item["id"] for item in messages.list("sea", "alice", unacked=True)] == ["a"]
    assert messages.list("sea", "alice") == []
    assert store.snapshot.call_count == 2


@pytest.mark.parametrize("failure_at", ["binding", "commit", None])
def test_poll_rechecks_ownership_and_conditional_publication(local_app, failure_at):
    store = local_app.store.return_value
    store.snapshot.return_value = message_snapshot({"message-index/m.json": incoming("m")})
    adapter = Mock()
    adapter.status.return_value = "idle"
    if failure_at == "binding":
        local_app.require_binding.side_effect = [({}, {}), Conflict("new binding")]
    if failure_at == "commit":
        store.change.side_effect = Conflict("shared state advanced")
    if failure_at:
        with pytest.raises(Conflict):
            Messages(local_app).poll(*ACTOR, adapter=adapter)
        adapter.notify.assert_not_called()
    else:
        assert Messages(local_app).poll(*ACTOR, adapter=adapter)["state"] == "notified_waiting_ack"
        expected = store.change.call_args.args[2]
        assert expected["acks/m.json"] is None
        assert "agents/alice.json" in expected and "bindings/b-current.json" in expected
        assert local_app.require_binding.call_count == 3
        adapter.notify.assert_called_once()


def test_unused_bridge_manager_does_no_shared_read(local_app):
    manager = bridges.BridgeManager(local_app, *ACTOR, local_app.root())
    manager.tick()
    local_app.require_binding.assert_not_called()


@pytest.mark.parametrize("pending", ["config", "process", "event"])
def test_bridge_work_still_checks_binding(local_app, pending):
    manager = bridges.BridgeManager(local_app, *ACTOR, local_app.root())
    if pending == "config":
        write_json(local_app.root() / ".aw-local/bridges/chat.json", {"enabled": False})
    elif pending == "process":
        manager.processes["chat"] = Mock()
    else:
        manager.events.put(("chat", {"event": "ready"}))
    local_app.require_binding.side_effect = Conflict("released")
    with pytest.raises(Conflict):
        manager.tick()


@pytest.mark.parametrize("transition", ["unchanged", "stopping", "replaced"])
def test_runner_only_continues_for_observed_ownership_transition(local_app, monkeypatch, transition):
    entry = {"id": ACTOR[2], "kind": "codex", "phase": "active", "session": "existing"}
    snap = SimpleNamespace(entries={"agents/alice.json": "agent-sha", "bindings/b-current.json": "binding-sha"},
                           json=lambda path: dict(entry))
    local_app.store.return_value.snapshot.return_value = snap
    write_json(local_app.root() / ".aw-local/entry.json", {"binding": ACTOR[2], "config": {"kind": "codex"},
               "model_profile": {"model": "fixture-model", "effort": "low", "source": {"path": "runtime.json"}}})
    adapter = Mock(session="existing")
    adapter.status.return_value = "idle"
    monkeypatch.setattr(runtime, "Codex", Mock(return_value=adapter))
    monkeypatch.setattr(bridges, "BridgeManager", Mock(return_value=Mock()))
    runner = runtime.Runner(local_app, *ACTOR[:2])
    runner.stop_event = Mock()
    runner.stop_event.wait.side_effect = [False, False, True]
    runner._complete_inputs = Mock()
    local_app.finish_stop.return_value = {"id": "handoff"}
    failure = Conflict("persistent input conflict")

    def fail(records):
        if transition == "stopping":
            entry["phase"] = "stopping"
            entry["checkpoint"] = "explicit-stop"
        elif transition == "replaced":
            local_app.agent.return_value = {"current": "successor"}
        raise failure

    runner._inputs = Mock(side_effect=fail)
    if transition == "unchanged":
        with pytest.raises(Conflict) as error:
            runner.run()
        assert error.value is failure
        assert read_json(local_app.root() / ".aw-local/status.json")["state"] == "failed"
    else:
        runner.run()
    assert runner._inputs.call_count == 1
    assert local_app.finish_stop.call_count == (1 if transition == "stopping" else 0)
    adapter.close.assert_called_once()
