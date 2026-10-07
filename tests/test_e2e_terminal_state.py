"""E2E-004/001 regressions: real Git/lifecycle, deterministic native-event boundary."""
import queue
import sys
from unittest.mock import Mock

import pytest

from agent_workspace import runtime, transfer
from agent_workspace.util import Conflict, Error, Unavailable, read_json, write_json


def profile():
    return {"kind": "codex", "command": [sys.executable]}


def prepare_agent(app):
    app.create("sea", "alice")
    app.configure("sea", "alice", profile())
    binding = app.reserve("sea", "alice")["binding"]
    return binding, app.root("sea", "alice")


def prepare_successor(app, monkeypatch):
    old, root = prepare_agent(app)
    app.bind("sea", "alice", old, "old-session")
    record = transfer.request(app, "sea", "alice", profile(), request_id="transfer-001")
    cp = app.checkpoint("sea", "alice", "old handoff", binding=old)
    app.stop("sea", "alice", old, cp["id"])
    app.finish_stop("sea", "alice", old, observed_idle=True)
    spawn = Mock(return_value={"state": "starting_runner"})
    monkeypatch.setattr(runtime, "spawn_runner", spawn)
    transfer.advance(app, "sea", "alice")
    assert spawn.call_count == 1
    return record, root, spawn


def install_native(app, monkeypatch, *, terminal="completed", stop_on_boot=False, late=False, close_error=False):
    """Use the real Runner; emit explicit events, including events drained on close."""
    class Native(runtime.Codex):
        def __init__(self, app, workspace, aid, binding, root, config, session=None):
            self.session = session or "session-" + binding
            self.binding, self.root = binding, root
            self.completed = queue.Queue()
            self.turns = 0
            self.pending = None
            self.closed = False

        def status(self):
            return "idle"

        def notify(self, prompt, delivery):
            self.turns += 1
            turn = {"id": "turn-" + str(self.turns), "status": "completed"}
            if stop_on_boot or prompt == "stop explicitly":
                cp = app.checkpoint("sea", "alice", "explicit stop", binding=self.binding,
                                    checkpoint_id="stop-" + self.binding)
                app.stop("sea", "alice", self.binding, cp["id"])
                turn["status"] = terminal
                if late:
                    self.pending = turn
                elif terminal:
                    self.completed.put(turn)
            else:
                self.completed.put(turn)
            return {"turn": {"id": turn["id"]}}

        def close(self):
            if close_error:
                raise Unavailable("close not confirmed")
            self.closed = True
            if self.pending and self.pending["status"]:
                self.completed.put(self.pending)
                self.pending = None

    monkeypatch.setattr(runtime, "Codex", Native)
    return Native


class Steps:
    def __init__(self, action=lambda step: None):
        self.step, self.action = 0, action

    def wait(self, interval):
        self.step += 1
        assert self.step <= 8, "Runner did not finish the targeted stop path"
        self.action(self.step)
        return False


@pytest.mark.parametrize("terminal,expected", [("completed", "completed"), ("failed", "failed"),
                                               ("interrupted", "failed"), (None, "submitted")])
def test_stop_drains_only_matched_terminal_events_before_release(app, monkeypatch, terminal, expected):
    binding, root = prepare_agent(app)
    install_native(app, monkeypatch, terminal=terminal, late=True)
    runner = runtime.Runner(app, "sea", "alice")
    folder = root / ".aw-local/inputs"

    def action(step):
        if step == 3:
            runtime.queue_input(app, "sea", "alice", "stop explicitly", request_id="stop-input")
            # These inputs have no matching terminal evidence, or a different owner.
            for name, state, owner in [("pending", "queued", binding), ("unknown", "outcome_unknown", binding),
                                       ("unfinished", "submitted", binding), ("historical", "submitted", "old")]:
                write_json(folder / (name + ".json"), {"id": name, "binding": owner, "state": state,
                    "purpose": "user", "created_at": "later", "sequence": 999, "delivery": "normal",
                    "text": name, "result": {"turn": {"id": "no-event"}}})
    runner.stop_event = Steps(action)
    finish = app.finish_stop

    def release(*args, **kwargs):
        assert runner.adapter.closed
        assert read_json(folder / "stop-input.json")["state"] == expected
        return finish(*args, **kwargs)
    monkeypatch.setattr(app, "finish_stop", release)
    runner.run()
    assert app.show("sea", "alice")["binding"] is None
    assert read_json(root / ".aw-local/status.json")["state"] == "released"
    for name, state in [("pending", "queued"), ("unknown", "outcome_unknown"),
                        ("unfinished", "submitted"), ("historical", "submitted")]:
        assert read_json(folder / (name + ".json"))["state"] == state
    assert runner.adapter.turns == 2
    assert {cp["id"] for cp in app.checkpoints("sea", "alice")} == {"initial-" + binding, "stop-" + binding}


def test_transfer_is_persisted_by_runner_without_status_or_continue(app, monkeypatch):
    record, root, spawn = prepare_successor(app, monkeypatch)
    install_native(app, monkeypatch)
    runner = runtime.Runner(app, "sea", "alice")
    completed = []

    def action(step):
        if step == 3:
            # Read bytes directly. A status query must not be necessary for persistence.
            value = read_json(root / ".aw-local/transfer.json")
            assert value["state"] == "completed"
            assert value["target_binding"] == record["target_binding"]
            assert value["session"] == "session-" + record["target_binding"]
            completed.append(value)
            runtime.queue_input(app, "sea", "alice", "stop explicitly", request_id="target-stop")
    runner.stop_event = Steps(action)
    runner.run()
    assert completed and app.agent("sea", "alice")["current"] is None
    assert transfer.status(app, "sea", "alice") == completed[0]
    assert transfer.advance(app, "sea", "alice") == completed[0]
    assert spawn.call_count == 1
    assert read_json(root / ".aw-local/inputs/target-stop.json")["state"] == "completed"

    # A new legitimate entry can request a different transfer; the old ID is archived.
    next_binding = app.reserve("sea", "alice")["binding"]
    app.bind("sea", "alice", next_binding, "later-session")
    following = transfer.request(app, "sea", "alice", profile(), request_id="transfer-002")
    assert following["old_binding"] == next_binding
    assert transfer.request(app, "sea", "alice", profile(), request_id="transfer-001") == completed[0]
    assert transfer.request(app, "sea", "alice", profile(), request_id="transfer-002") == following
    assert spawn.call_count == 1


def test_stop_during_boot_reuses_explicit_checkpoint_and_persists_completed_transfer(app, monkeypatch):
    record, root, _ = prepare_successor(app, monkeypatch)
    binding = record["target_binding"]
    install_native(app, monkeypatch, stop_on_boot=True, late=True)
    runner = runtime.Runner(app, "sea", "alice")
    runner.stop_event = Steps()
    runner.run()
    boot = read_json(root / f".aw-local/inputs/boot-{binding}.json")
    assert boot["state"] == "completed"
    point = app.checkpoint_show("sea", "alice", "stop-" + binding)
    assert boot["checkpoint_revision"] == point["revision"]
    assert not any(p["id"] == "initial-" + binding for p in app.checkpoints("sea", "alice"))
    assert read_json(root / ".aw-local/transfer.json")["state"] == "completed"
    handoff = app.store("sea").snapshot().json(f"handoffs/{app.agent('sea', 'alice')['handoff']}.json")
    assert handoff["checkpoint"] == point["id"]


@pytest.mark.parametrize("terminal", ["failed", None])
def test_stopped_unsuccessful_boot_does_not_complete_transfer(app, monkeypatch, terminal):
    record, root, _ = prepare_successor(app, monkeypatch)
    install_native(app, monkeypatch, stop_on_boot=True, terminal=terminal)
    runner = runtime.Runner(app, "sea", "alice")
    runner.stop_event = Steps()
    runner.run()
    assert read_json(root / ".aw-local/transfer.json")["state"] != "completed"
    boot = read_json(root / f".aw-local/inputs/boot-{record['target_binding']}.json")
    assert boot["state"] == ("failed" if terminal else "submitted")
    assert not boot.get("checkpoint_revision")


def test_checkpoint_failure_retains_completed_input_but_not_transfer_success(app, monkeypatch):
    record, root, _ = prepare_successor(app, monkeypatch)
    install_native(app, monkeypatch)
    monkeypatch.setattr(app, "checkpoint", Mock(side_effect=Error("cannot publish initial checkpoint")))
    runner = runtime.Runner(app, "sea", "alice")
    runner.stop_event = Steps()
    with pytest.raises(Error, match="cannot publish"):
        runner.run()
    boot = read_json(root / f".aw-local/inputs/boot-{record['target_binding']}.json")
    assert boot["state"] == "completed" and not boot.get("checkpoint_revision")
    assert read_json(root / ".aw-local/transfer.json")["state"] != "completed"


def test_unconfirmed_close_still_blocks_release(app, monkeypatch):
    binding, root = prepare_agent(app)
    install_native(app, monkeypatch, stop_on_boot=True, close_error=True)
    runner = runtime.Runner(app, "sea", "alice")
    runner.stop_event = Steps()
    with pytest.raises(Unavailable, match="close not confirmed"):
        runner.run()
    entry = app.show("sea", "alice")["binding"]
    assert entry["phase"] == "stopping" and entry["controller"]


@pytest.mark.parametrize("state,revision,session", [("submitted", "saved", "native"),
    ("failed", "saved", "native"), ("completed", None, "native"), ("completed", "saved", None)])
def test_completion_requires_successful_boot_and_session(tmp_path, state, revision, session):
    root = tmp_path
    record = {"id": "original", "target_binding": "b-target", "state": "starting"}
    write_json(root / ".aw-local/transfer.json", record)
    write_json(root / ".aw-local/inputs/boot-b-target.json", {"binding": "b-target", "state": state,
                                                              "checkpoint_revision": revision})
    transfer.persist_completion(root, {"id": "b-target", "phase": "active", "session": session})
    assert read_json(root / ".aw-local/transfer.json") == record


def test_fast_successor_completion_waits_for_launch_write(tmp_path):
    import threading
    from agent_workspace.util import locked
    root = tmp_path
    path = root / ".aw-local/transfer.json"
    record = {"id": "original", "target_binding": "b-target", "state": "launching"}
    write_json(path, record)
    write_json(root / ".aw-local/inputs/boot-b-target.json", {"binding": "b-target", "state": "completed",
                                                              "checkpoint_revision": "saved"})
    started, errors = threading.Event(), []
    def observe():
        started.set()
        try:
            transfer.persist_completion(root, {"id": "b-target", "phase": "active", "session": "native"})
        except Exception as exc:
            errors.append(exc)
    with locked(root / ".aw-local/transfer.lock"):
        thread = threading.Thread(target=observe)
        thread.start()
        assert started.wait(2)
        # advance holds this lock until its post-spawn write is complete.
        write_json(path, {**record, "state": "starting"})
    thread.join(5)
    assert not thread.is_alive() and not errors
    assert read_json(path)["state"] == "completed"


def test_completion_write_failure_retries_only_the_receipt(app, monkeypatch):
    record, root, spawn = prepare_successor(app, monkeypatch)
    real_write, failed = transfer.write_json, []
    path = root / ".aw-local/transfer.json"
    def write(target, value):
        if target == path and value.get("state") == "completed" and not failed:
            failed.append(True)
            raise OSError("receipt temporarily unavailable")
        real_write(target, value)
    monkeypatch.setattr(transfer, "write_json", write)
    # The existing Codex loop stops on an OSError; exercise the next safe bookkeeping
    # pass directly rather than pretending a disconnected model may be restarted.
    entry = {"id": record["target_binding"], "phase": "active", "session": "native"}
    write_json(root / f".aw-local/inputs/boot-{record['target_binding']}.json",
               {"binding": record["target_binding"], "state": "completed", "checkpoint_revision": "saved"})
    with pytest.raises(OSError, match="temporarily"):
        transfer.persist_completion(root, entry)
    assert read_json(path)["state"] == "starting"
    transfer.persist_completion(root, entry)
    assert read_json(path)["state"] == "completed"
    assert spawn.call_count == 1


def test_old_runner_cannot_complete_replacement_transfer(tmp_path):
    path = tmp_path / ".aw-local/transfer.json"
    next_record = {"id": "next", "target_binding": "b-next", "state": "starting"}
    write_json(path, next_record)
    transfer.persist_completion(tmp_path, {"id": "b-previous", "phase": "active", "session": "previous"})
    assert read_json(path) == next_record
