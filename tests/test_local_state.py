"""Local-state regressions; no model, remote repository or timing budget is needed."""
from concurrent.futures import ThreadPoolExecutor
import queue
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent_workspace import commands, runtime
from agent_workspace.util import Conflict, Error, Unavailable, digest, read_json, write_bytes, write_json


@pytest.fixture
def local_app(tmp_path):
    return SimpleNamespace(
        root=Mock(return_value=tmp_path),
        agent=Mock(return_value={"current": "b-current"}),
        require_binding=Mock(return_value=({}, {})),
        checkpoint=Mock(return_value={"id": "initial-b-current", "revision": "saved-revision"}),
    )


def local_runner(app):
    runner = runtime.Runner(app, "sea", "alice")
    runner.binding = "b-current"
    # Exercise the real Runner methods without starting an external Runtime.
    runner.adapter = object.__new__(runtime.Codex)
    runner.adapter.completed = queue.Queue()
    runner.adapter.status = Mock(return_value="idle")
    runner.adapter.notify = Mock(return_value={"turn": {"id": "t1"}})
    return runner


def input_path(app, identifier):
    return app.root() / ".aw-local/inputs" / f"{identifier}.json"


def enqueue(app, text="first", **kwargs):
    return runtime.queue_input(app, "sea", "alice", text, **kwargs)


def test_inputs_follow_enqueue_order_not_ids_or_clock(local_app, monkeypatch):
    monkeypatch.setattr(runtime, "uid", Mock(side_effect=["iz", "ia"]))
    monkeypatch.setattr(runtime, "now", Mock(return_value="2026-10-01T02:00:00+00:00"))
    first = enqueue(local_app, "first")
    monkeypatch.setattr(runtime, "now", Mock(return_value="2026-10-01T01:00:00+00:00"))
    second = enqueue(local_app, "second", delivery="insert")
    runner = local_runner(local_app)
    runner._inputs()
    runner._inputs()
    assert [call.args[0] for call in runner.adapter.notify.call_args_list] == ["first", "second"]
    assert first["sequence"] < second["sequence"]


def test_repeated_input_preserves_record_and_sequence(local_app):
    first = enqueue(local_app, request_id="same")
    saved = input_path(local_app, "same").read_bytes()
    assert enqueue(local_app, request_id="same") == first
    assert input_path(local_app, "same").read_bytes() == saved
    second = enqueue(local_app, "second", request_id="next")
    assert second["sequence"] == first["sequence"] + 1


@pytest.mark.parametrize("changed", [{"text": "different"}, {"delivery": "insert"}, {"purpose": "handoff"}])
def test_request_id_cannot_change_input_meaning(local_app, changed):
    enqueue(local_app, request_id="same")
    with pytest.raises(Conflict):
        enqueue(local_app, request_id="same", **changed)


def test_concurrent_producers_get_distinct_ordered_sequences(local_app):
    barrier = threading.Barrier(6)

    def submit(index):
        barrier.wait(timeout=10)
        return enqueue(local_app, str(index), request_id=f"input-{index}")

    with ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(submit, range(6)))
    ordered = sorted(records, key=lambda item: item["sequence"])
    assert [item["sequence"] for item in ordered] == list(range(1, 7))
    runner = local_runner(local_app)
    for _ in records:
        runner._inputs()
    assert [call.args[0] for call in runner.adapter.notify.call_args_list] == [item["text"] for item in ordered]


def test_legacy_inputs_keep_timestamp_order_before_new_inputs(local_app, monkeypatch):
    for identifier, text, timestamp in (("z-old", "old first", "2026-10-01T01:00:00+00:00"),
                                        ("a-old", "old second", "2026-10-01T02:00:00+00:00")):
        write_json(input_path(local_app, identifier), {
            "id": identifier, "binding": "b-current", "text": text, "delivery": "normal",
            "purpose": "user", "state": "queued", "created_at": timestamp,
        })
    monkeypatch.setattr(runtime, "now", Mock(return_value="2026-09-30T01:00:00+00:00"))
    enqueue(local_app, "new", request_id="new")
    runner = local_runner(local_app)
    for _ in range(3):
        runner._inputs()
    assert [call.args[0] for call in runner.adapter.notify.call_args_list] == ["old first", "old second", "new"]
    assert "sequence" not in read_json(input_path(local_app, "z-old"))


def test_busy_normal_blocks_later_insert(local_app):
    enqueue(local_app, "normal", request_id="z-first")
    enqueue(local_app, "insert", request_id="a-second", delivery="insert")
    runner = local_runner(local_app)
    runner.adapter.status.return_value = "busy"
    runner._inputs()
    runner.adapter.notify.assert_not_called()
    runner.adapter.status.return_value = "idle"
    runner._inputs()
    runner.adapter.status.return_value = "busy"
    runner._inputs()
    assert [call.args for call in runner.adapter.notify.call_args_list] == [("normal", "normal"), ("insert", "insert")]


def test_uncertain_input_is_not_replayed(local_app):
    enqueue(local_app, request_id="uncertain")
    runner = local_runner(local_app)
    runner.adapter.notify.side_effect = Unavailable("reply lost after submission")
    with pytest.raises(Unavailable):
        runner._inputs()
    assert read_json(input_path(local_app, "uncertain"))["state"] == "outcome_unknown"
    runner._inputs()
    assert runner.adapter.notify.call_count == 1


def test_input_rechecks_binding_before_submission(local_app):
    enqueue(local_app, request_id="pending")
    runner = local_runner(local_app)
    local_app.require_binding.side_effect = Conflict("entry was released")
    with pytest.raises(Conflict):
        runner._inputs()
    runner.adapter.notify.assert_not_called()
    assert read_json(input_path(local_app, "pending"))["state"] == "queued"


def initial_completion(app, status="completed"):
    enqueue(app, purpose="initial", request_id="boot-b-current")
    runner = local_runner(app)
    runner._inputs()
    runner.adapter.completed.put({"id": "t1", "status": status})
    return runner


def test_failed_initial_checkpoint_is_reconciled_after_runner_restart(local_app):
    runner = initial_completion(local_app)
    local_app.checkpoint.side_effect = [Error("Git publication failed"), {"revision": "saved-revision"}]
    with pytest.raises(Error, match="publication failed"):
        runner._complete_inputs()
    assert read_json(input_path(local_app, "boot-b-current"))["state"] == "completed"
    assert runner.adapter.completed.empty()
    restarted = local_runner(local_app)
    restarted._complete_inputs()
    restarted._inputs()
    saved = read_json(input_path(local_app, "boot-b-current"))
    assert saved["checkpoint_revision"] == "saved-revision"
    assert local_app.checkpoint.call_count == 2
    assert {call.kwargs["checkpoint_id"] for call in local_app.checkpoint.call_args_list} == {"initial-b-current"}
    assert runner.adapter.notify.call_count == 1
    restarted.adapter.notify.assert_not_called()


def test_checkpoint_marker_failure_reuses_original_checkpoint_id(local_app, monkeypatch):
    runner = initial_completion(local_app)
    real_write = runtime.write_json

    def fail_marker(path, value):
        if value.get("checkpoint_revision"):
            raise OSError("marker unavailable")
        real_write(path, value)

    monkeypatch.setattr(runtime, "write_json", fail_marker)
    with pytest.raises(OSError, match="marker unavailable"):
        runner._complete_inputs()
    assert read_json(input_path(local_app, "boot-b-current"))["state"] == "completed"
    monkeypatch.setattr(runtime, "write_json", real_write)
    restarted = local_runner(local_app)
    restarted._complete_inputs()
    restarted._complete_inputs()
    assert local_app.checkpoint.call_count == 2
    assert {call.kwargs["checkpoint_id"] for call in local_app.checkpoint.call_args_list} == {"initial-b-current"}
    restarted.adapter.notify.assert_not_called()


@pytest.mark.parametrize("status", ["failed", "interrupted"])
def test_failed_initial_turn_never_gets_success_checkpoint(local_app, status):
    runner = initial_completion(local_app, status)
    runner._complete_inputs()
    local_runner(local_app)._complete_inputs()
    assert read_json(input_path(local_app, "boot-b-current"))["state"] == "failed"
    local_app.checkpoint.assert_not_called()


def test_duplicate_completion_does_not_resave_checkpoint(local_app):
    runner = initial_completion(local_app)
    runner._complete_inputs()
    runner.adapter.completed.put({"id": "t1", "status": "completed"})
    runner._complete_inputs()
    assert local_app.checkpoint.call_count == 1


def test_checkpoint_failure_does_not_discard_other_completion_events(local_app):
    runner = initial_completion(local_app)
    other = enqueue(local_app, "other", request_id="other")
    other.update(state="submitted", result={"turn": {"id": "t2"}})
    write_json(input_path(local_app, "other"), other)
    runner.adapter.completed.put({"id": "t2", "status": "completed"})
    local_app.checkpoint.side_effect = Error("cannot publish")
    with pytest.raises(Error):
        runner._complete_inputs()
    assert read_json(input_path(local_app, "other"))["state"] == "completed"


def test_pending_checkpoint_from_old_binding_is_not_reconciled(local_app):
    record = enqueue(local_app, purpose="initial", request_id="old")
    record.update(state="completed", binding="b-old")
    write_json(input_path(local_app, "old"), record)
    local_runner(local_app)._complete_inputs()
    local_app.checkpoint.assert_not_called()


@pytest.mark.parametrize("path", [
    ".aw/identity.json", "./.aw/identity.json", ".aw//identity.json", ".AW/identity.json",
    "source.json", "./source.json", "Source.JSON",
    ".aw./identity.json", ".aw /identity.json", "source.json:alternate", "source.json.",
])
def test_asset_write_rejects_managed_path_aliases(local_app, path):
    root = local_app.root()
    write_bytes(root / ".aw/identity.json", b"original")
    write_bytes(root / "source.json", b"original")
    with pytest.raises(Error, match="managed metadata|portable asset"):
        commands.assets(local_app, "write", "sea", "alice", path=path,
                        content="replacement", revision=digest(b"original"))
    assert (root / ".aw/identity.json").read_bytes() == b"original"
    assert (root / "source.json").read_bytes() == b"original"


@pytest.mark.parametrize("protected", [".aw", ".aw-local"])
def test_asset_write_rejects_symlink_into_managed_directory(local_app, protected):
    root = local_app.root()
    target = root / protected / "identity.json"
    write_bytes(target, b"original")
    try:
        (root / "alias").symlink_to(root / protected, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("This environment cannot create directory symlinks.")
    with pytest.raises(Error):
        commands.assets(local_app, "write", "sea", "alice", path="alias/identity.json",
                        content="replacement", revision=digest(b"original"))
    assert target.read_bytes() == b"original"


def test_asset_path_normalization_preserves_user_write_and_conflict_check(local_app):
    result = commands.assets(local_app, "write", "sea", "alice", path="./notes//entry.md", content="first")
    assert result["path"] == "notes/entry.md"
    with pytest.raises(Conflict):
        commands.assets(local_app, "write", "sea", "alice", path="notes/entry.md", content="second")
    assert commands.assets(local_app, "read", "sea", "alice", path="notes/entry.md")["content"] == "first"
    commands.assets(local_app, "write", "sea", "alice", path="notes/entry.md",
                    content="second", revision=result["revision"])
    assert (local_app.root() / "notes/entry.md").read_text() == "second"


def test_managed_assets_remain_readable(local_app):
    write_bytes(local_app.root() / ".aw/identity.json", b"identity")
    result = commands.assets(local_app, "read", "sea", "alice", path="./.aw/identity.json")
    assert result["content"] == "identity"
    assert result["path"] == ".aw/identity.json"


@pytest.mark.parametrize('status,expected', [('completed', 'completed'), ('failed', 'failed'), ('interrupted', 'failed')])
def test_one_native_turn_finishes_normal_input_and_all_busy_steers(local_app, status, expected):
    runner = local_runner(local_app)
    runner.adapter.session = 'actual-session'
    runner.adapter.turn_id = 't1'
    runner.adapter.rpc = Mock()
    runner.adapter.rpc.request.side_effect = lambda method, params: (
        {'turnId': 't1'} if method == 'turn/steer' else {'turn': {'id': 't1'}})
    # Use Codex.notify itself: turn/start and turn/steer really return different shapes.
    runner.adapter.notify = runtime.Codex.notify.__get__(runner.adapter)
    enqueue(local_app, 'first task', request_id='normal')
    runner._inputs()
    runner.adapter.status.return_value = 'busy'
    for identifier in ('insert-one', 'insert-two'):
        enqueue(local_app, identifier, request_id=identifier, delivery='insert')
        runner._inputs()
        assert read_json(input_path(local_app, identifier))['result'] == {'turnId': 't1'}
    assert [call.args[0] for call in runner.adapter.rpc.request.call_args_list] == ['turn/start', 'turn/steer', 'turn/steer']
    runner._complete_inputs()  # A receipt alone is not a completed native turn.
    assert all(read_json(input_path(local_app, i))['state'] == 'submitted'
               for i in ('normal', 'insert-one', 'insert-two'))
    runner.adapter.completed.put({'id': 't1', 'status': status})
    runner._complete_inputs()
    assert all(read_json(input_path(local_app, i))['state'] == expected
               for i in ('normal', 'insert-one', 'insert-two'))
    for identifier in ('insert-one', 'insert-two'):
        enqueue(local_app, identifier, request_id=identifier, delivery='insert')
    runner._inputs()
    assert runner.adapter.rpc.request.call_count == 3
    local_app.checkpoint.assert_not_called()


def test_steer_without_matching_completion_is_not_promoted_or_replayed(local_app):
    runner = local_runner(local_app)
    for identifier, state, binding in [('submitted', 'submitted', 'b-current'),
                                     ('unknown', 'outcome_unknown', 'b-current'),
                                     ('old', 'submitted', 'b-old')]:
        item = enqueue(local_app, identifier, request_id=identifier, delivery='insert')
        write_json(input_path(local_app, identifier), {**item, 'state': state, 'binding': binding,
                                                      'result': {'turnId': 'our-turn'}})
    runner.adapter.completed.put({'id': 'another-turn', 'status': 'completed'})
    runner._complete_inputs()
    assert read_json(input_path(local_app, 'submitted'))['state'] == 'submitted'
    runner.adapter.completed.put({'id': 'our-turn', 'status': 'completed'})
    runner._complete_inputs()
    assert read_json(input_path(local_app, 'submitted'))['state'] == 'completed'
    assert read_json(input_path(local_app, 'unknown'))['state'] == 'outcome_unknown'
    assert read_json(input_path(local_app, 'old'))['state'] == 'submitted'
    runner._inputs()
    runner.adapter.notify.assert_not_called()
