"""Isolated fictional build; never imports or executes SBP, UE or a model."""
import argparse
import hashlib
import json
from pathlib import Path
import queue
import sys
import threading
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
REPAIR_CONTENT = "fictional navigation tile B\n"


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def append(path, value):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def confined(path):
    path = path.resolve()
    if not path.is_relative_to(ROOT) or path == ROOT:
        raise ValueError("Scenario data must remain below the isolated E2E root")
    return path


def transition(folder, status, event_type, attempt, error=None):
    journal = folder / "operation-events.jsonl"
    cursor = len(journal.read_text(encoding="utf-8").splitlines()) + 1 if journal.exists() else 1
    operation = {
        "schema_version": 1, "simulation": True,
        "operation_id": f"sim-operation-{attempt}", "build_id": f"sim-build-{attempt}",
        "status": status, "stage_order": ["navigation_export"],
        "updated_at": now(), "error": error, "last_cursor": cursor,
        "progress": {"stage_name": "navigation_export", "job_id": "fictional-tile-export",
                     "completed_inputs": 2 if status == "succeeded" else 1, "total_inputs": 2},
        "effects_certainty": "certain",
    }
    write(folder / "build_operation.json", operation)
    append(journal, {"cursor": cursor, "operation_id": operation["operation_id"],
                     "event_type": event_type, "created_at": now(), "data": operation})
    return operation


def execute(folder, attempt):
    transition(folder, "running", "build.started", attempt)
    transition(folder, "running", "job.progress", attempt)
    missing = [name for name in ("tile-A.txt", "tile-B.txt") if not (folder / "inputs" / name).is_file()]
    error = {"code": "sim_required_input_missing", "message": "Missing fictional input: " + ", ".join(missing)} if missing else None
    status = "failed" if missing else "succeeded"
    archive = folder / "archive" / f"sim-build-{attempt}"
    archive.mkdir(parents=True, exist_ok=False)
    log = archive / "job.log"
    log.write_text((error["message"] if error else "Exported two fictional tiles") + "\n", encoding="utf-8")
    if not missing:
        output = "".join((folder / "inputs" / name).read_text(encoding="utf-8") for name in ("tile-A.txt", "tile-B.txt"))
        (archive / "navigation-export.txt").write_text(output, encoding="utf-8")
    facts = {"simulation": True, "build_id": f"sim-build-{attempt}", "stage_name": "navigation_export",
             "job_id": "fictional-tile-export", "error": error, "log_path": str(log.relative_to(folder))}
    write(archive / "job_summary.json", {**facts, "job_status": "failed" if missing else "success"})
    write(archive / "stage_summary.json", {**facts, "stage_status": "failed" if missing else "success"})
    write(archive / "build_summary.json", {**facts, "build_status": "failed" if missing else "success"})
    operation = transition(folder, status, "build." + status, attempt, error)
    write(archive / "build_operation.json", operation)
    return operation


def prepare(folder):
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs").mkdir()
    (folder / "inputs" / "tile-A.txt").write_text("fictional navigation tile A\n", encoding="utf-8")
    write(folder / "scenario.json", {"simulation": True, "required_inputs": ["tile-A.txt", "tile-B.txt"],
                                   "repair_content": REPAIR_CONTENT, "scope": "this directory only"})
    execute(folder, 1)


def observe(folder):
    operation = read(folder / "build_operation.json")
    status = operation["status"]
    if status not in ("failed", "succeeded"):
        return None
    event_id = operation["build_id"] + "-" + status
    seen_path = folder / "observed.json"
    seen = read(seen_path) if seen_path.exists() else []
    append(folder / "observations.jsonl", {"at": now(), "event_id": event_id, "duplicate": event_id in seen})
    if event_id in seen:
        return None
    text = json.dumps({"simulation": True, "operation": operation,
                       "evidence_directory": f"archive/{operation['build_id']}",
                       "scenario_directory": str(folder),
                       "notice": "Fictional build facts. Repair requires explicit authorization; scope is this scenario only."}, ensure_ascii=False)
    event = {"event": "input", "id": event_id, "sender": "sim-build-watcher",
             "target": "simulation-outbox", "text": text}
    append(folder / "agent-events.jsonl", event)
    write(seen_path, seen + [event_id])
    return event


def repair(folder):
    path = folder / "inputs" / "tile-B.txt"
    with path.open("x", encoding="utf-8", newline="") as stream:
        stream.write(REPAIR_CONTENT)
    write(folder / "repair.json", {"action": "create_missing_fictional_input", "path": "inputs/tile-B.txt",
                                 "previously_absent": True, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})


def resume(folder):
    if read(folder / "build_operation.json")["status"] != "failed":
        raise ValueError("Only the failed first attempt may resume")
    if (folder / "inputs" / "tile-B.txt").read_text(encoding="utf-8") != REPAIR_CONTENT:
        raise ValueError("Repair input does not match the fictional fixture")
    if not (folder / "repair.json").exists():
        path = folder / "inputs" / "tile-B.txt"
        write(folder / "repair.json", {"action": "create_missing_fictional_input", "path": "inputs/tile-B.txt",
                                     "previously_absent": True, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return execute(folder, 2)


def undo(folder):
    record = read(folder / "repair.json")
    path = folder / record["path"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError("Input changed after repair; refusing to remove it")
    path.unlink()
    write(folder / "repair-undone.json", {"at": now(), "removed": record["path"], "history_preserved": True})


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def bridge(folder):
    # Future opt-in AW custom Bridge. No model invocation or external delivery here.
    if not folder.exists():
        prepare(folder)
    observe(folder)
    emit({"event": "ready"})
    for line in (folder / "agent-events.jsonl").read_text(encoding="utf-8").splitlines():
        emit(json.loads(line))  # Stable IDs allow AW to deduplicate restart replays.
    inbox = queue.Queue()
    def reader():
        for line in sys.stdin:
            inbox.put(json.loads(line))
        inbox.put(None)
    threading.Thread(target=reader, daemon=True).start()
    while True:
        try:
            item = inbox.get(timeout=0.5)
        except queue.Empty:
            if read(folder / "build_operation.json")["status"] == "failed" and (folder / "inputs" / "tile-B.txt").exists():
                resume(folder)
                event = observe(folder)
                if event:
                    emit(event)
            continue
        if item is None:
            return
        if item.get("event") != "send" or item.get("target") != "simulation-outbox":
            raise ValueError("Only local simulation-outbox sends are allowed")
        append(folder / "simulation-outbox.jsonl", item)
        emit({"event": "sent", "id": item["id"], "receipt": {"simulation": True, "external_delivery": False}})


def check(folder):
    prepare(folder)
    first = observe(folder)
    duplicate = observe(folder)
    assert first and duplicate is None
    assert "tile-B.txt" in (folder / "archive/sim-build-1/job.log").read_text(encoding="utf-8")
    repair(folder)
    assert resume(folder)["status"] == "succeeded"
    recovered = observe(folder)
    assert recovered and observe(folder) is None
    output = folder / "archive/sim-build-2/navigation-export.txt"
    assert output.read_text(encoding="utf-8") == "fictional navigation tile A\n" + REPAIR_CONTENT
    undo(folder)
    assert not (folder / "inputs/tile-B.txt").exists()
    assert read(folder / "archive/sim-build-1/build_operation.json")["status"] == "failed"
    result = {"passed": True, "simulation": True, "model_calls": 0, "external_messages": 0,
              "failure_events": 1, "recovery_events": 1, "duplicate_observations_suppressed": 2,
              "repair_reversed": True, "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
              "run_directory": str(folder), "proof_boundary": "driver only; no AW runtime, Agent or WeCom verification"}
    write(folder / "check-result.json", result)
    emit(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "observe", "repair", "resume", "undo", "bridge", "check"])
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    globals()[args.action](confined(args.run_dir))
