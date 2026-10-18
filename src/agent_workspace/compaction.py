"""Save the current Codex transcript before context compaction."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat

from . import layout, runtime, workers
from .commands import execute
from .util import Conflict, Error, digest, read_json, write_bytes, write_json


MAX_TRANSCRIPT_BYTES = 50 * 1024 * 1024
TRANSCRIPT_RELATIVE_PATH = "records/{binding}/codex-transcript.jsonl"


def _reply(message):
    return {"systemMessage": message, "continue": True}


def _actor(app, actor, session_id):
    if actor is not None:
        return actor

    names = ("AW_WORKSPACE", "AW_AGENT", "AW_BINDING")
    values = tuple(os.environ.get(name) for name in names)
    if any(name in os.environ for name in names):
        if not all(values):
            raise Error("AW caller identity is incomplete; no checkpoint was saved.")
        return values

    if "CODEX_THREAD_ID" in os.environ:
        return runtime.desktop_directory_actor(app, "checkpoint.create")

    # Native command hooks have no CODEX_THREAD_ID. Without a model identity this
    # is AW's existing local user context; the trusted hook supplies only a session
    # lookup key. An inherited model identity must never fall back to this path.
    matches = []
    for workspace in app.local()["workspaces"]:
        snapshot = app.store(workspace).snapshot()
        for kind in ("codex", "desktop"):
            linked = snapshot.json(layout.shared_path(snapshot, f"sessions/{kind}/{digest(session_id.encode())}.json"))
            if linked is None:
                continue
            _, entry = app.require_binding(workspace, linked["agent"], linked["binding"], snapshot=snapshot)
            if linked["session"] != session_id or entry["session"] != session_id or entry["kind"] != kind:
                raise Conflict("Codex hook session index does not match its execution entry.")
            matches.append((workspace, linked["agent"], linked["binding"]))
    if len(matches) > 1:
        raise Conflict("Codex hook session is registered to more than one AW execution entry.")
    return matches[0] if matches else None


def _transcript_bytes(payload, session_id):
    transcript_path = payload.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        raise Error("Codex did not provide a transcript path; no checkpoint was saved.")

    path = Path(transcript_path).expanduser()
    if not path.is_absolute():
        raise Error("Codex transcript path is not absolute; no checkpoint was saved.")

    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise Error("Codex transcript path contains a symbolic link; no checkpoint was saved.")

    with path.open("rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise Error("Codex transcript is not a regular file; no checkpoint was saved.")
        if metadata.st_size > MAX_TRANSCRIPT_BYTES:
            raise Error("Codex transcript exceeds the 50 MiB snapshot limit; no checkpoint was saved.")
        cutoff_bytes = metadata.st_size
        content = stream.read(cutoff_bytes)
    if len(content) != cutoff_bytes:
        raise Error("Codex transcript changed while its initial byte range was read; no checkpoint was saved.")
    first_line = content.splitlines()[0] if content else b""
    try:
        first_record = json.loads(first_line)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Error("Codex transcript has no valid first session record; no checkpoint was saved.") from exc
    if (not isinstance(first_record, dict) or first_record.get("type") != "session_meta"
            or not isinstance(first_record.get("payload"), dict)
            or first_record["payload"].get("id") != session_id):
        raise Conflict("Codex transcript session does not match the current AW Binding; no checkpoint was saved.")
    return content


def _latest_business_checkpoint(app, workspace, agent_id, worker_id=None):
    for point in reversed(app.checkpoints(workspace, agent_id, worker_id=worker_id)):
        saved = app.checkpoint_show(workspace, agent_id, point["id"], worker_id=worker_id)["record"]
        references = saved.get("record_refs", [])
        automatic = saved["id"].startswith("initial-") or any(
            isinstance(reference, dict) and reference.get("source") == "codex-precompact"
            for reference in references
        )
        if not automatic:
            return saved["id"], saved["created_at"], saved.get("summary", ""), saved.get("content", "")
    return None


def _destination(root, binding, worker_id=None):
    logical_path = TRANSCRIPT_RELATIVE_PATH.format(binding=binding)
    relative_path = layout.instance_relpath(root, logical_path, worker_id)
    destination = layout.instance_path(root, logical_path, worker_id)
    resolved_root = root.resolve()
    current = root
    for part in relative_path.split("/"):
        current = current / part
        if current.is_symlink():
            raise Error("The AW transcript destination contains a symbolic link; no checkpoint was saved.")
    if not destination.resolve(strict=False).is_relative_to(resolved_root):
        raise Error("The AW transcript destination escapes the instance root; no checkpoint was saved.")
    if destination.exists() and not destination.is_file():
        raise Error("The AW transcript destination is not a regular file; no checkpoint was saved.")
    return relative_path, destination


def _verify_checkpoint(app, workspace, agent_id, checkpoint_id, revision, reference, transcript, worker_id=None):
    point = app.checkpoint_show(workspace, agent_id, checkpoint_id, worker_id=worker_id)
    if point["revision"] != revision:
        raise Conflict("Saved checkpoint revision differs from the PreCompact receipt.")
    if reference not in point["record"].get("record_refs", []):
        raise Conflict("Saved checkpoint does not contain the expected PreCompact reference.")
    snapshot = app.store(workspace).snapshot(revision=revision)
    if snapshot.bytes(reference["transcript_path"]) != transcript:
        raise Conflict("Saved checkpoint revision does not contain the exact Codex transcript bytes.")
    return point


def run(app, payload, actor=None):
    """Handle one Codex PreCompact event and always let compaction continue."""
    if not isinstance(payload, dict) or payload.get("hook_event_name") != "PreCompact":
        return _reply("已忽略非 Codex PreCompact 事件；工作继续。")

    session_id = payload.get("session_id")
    turn_id = payload.get("turn_id")
    trigger = payload.get("trigger")
    if not isinstance(session_id, str) or not session_id:
        return _reply("Codex PreCompact 缺少 session_id，未保存检查点；压缩继续。")
    if not isinstance(turn_id, str) or not turn_id:
        return _reply("Codex PreCompact 缺少 turn_id，未保存检查点；压缩继续。")
    if trigger not in ("manual", "auto"):
        return _reply("Codex PreCompact 的 trigger 无效，未保存检查点；压缩继续。")

    try:
        current_actor = _actor(app, actor, session_id)
        if current_actor is None:
            return _reply("当前会话没有 AW 执行身份，未保存自动检查点；压缩继续。")
        if not isinstance(current_actor, tuple) or len(current_actor) != 3:
            raise Error("AW caller identity is invalid; no checkpoint was saved.")

        workspace, agent_id, binding = current_actor
        owner, entry = app.require_binding(workspace, agent_id, binding)
        worker_id = owner.get("worker_id")
        if entry.get("kind") not in ("codex", "desktop"):
            raise Conflict("PreCompact is only supported for a current Codex or Desktop Binding.")
        if entry.get("session") != session_id:
            raise Conflict("Codex hook session does not match the current AW Binding; no checkpoint was saved.")

        transcript = _transcript_bytes(payload, session_id)
        transcript_hash = digest(transcript)
        root = Path(app.prepare_agent_directory(workspace, agent_id)["directory"])
        if worker_id is not None:
            workers.prepare_context(app, workspace, agent_id, root, worker_id)
        relative_path, destination = _destination(root, binding, worker_id)
        request_key = digest(
            json.dumps([session_id, turn_id, trigger, transcript_hash], ensure_ascii=False,
                       separators=(",", ":")).encode("utf-8")
        )
        checkpoint_id = "pc-" + request_key[:61]
        receipt_path = layout.local_path(root, f"precompact/{checkpoint_id}.json", worker_id)

        checkpoint_ref = {
            "source": "codex-precompact",
            "session_id": session_id,
            "turn_id": turn_id,
            "trigger": trigger,
            "transcript_sha256": transcript_hash,
            "transcript_cutoff_bytes": len(transcript),
            "transcript_path": relative_path,
        }
        with layout.lock(root, "precompact.lock", worker_id=worker_id):
            receipt = read_json(receipt_path)
            if receipt:
                if (receipt.get("request_key") != request_key
                        or receipt.get("checkpoint_id") != checkpoint_id
                        or receipt.get("trigger") != trigger
                        or receipt.get("transcript_sha256") != transcript_hash
                        or receipt.get("transcript_path") != relative_path
                        or receipt.get("record_refs") != [checkpoint_ref]):
                    raise Conflict("PreCompact request ID is already in use by a different event.")
                if receipt.get("state") == "saved":
                    if not isinstance(receipt.get("checkpoint_revision"), str):
                        raise Conflict("Saved PreCompact receipt has no checkpoint revision.")
                    _verify_checkpoint(app, workspace, agent_id, checkpoint_id,
                                       receipt["checkpoint_revision"], checkpoint_ref, transcript, worker_id)
                    return _reply(f"压缩前检查点已保存：{checkpoint_id}。")
                if receipt.get("state") != "pending":
                    raise Conflict("PreCompact retry receipt has an unknown state; no checkpoint was saved.")
                summary, content = receipt["summary"], receipt["content"]
                references = receipt["record_refs"]
            else:
                previous = _latest_business_checkpoint(app, workspace, agent_id, worker_id)
                if previous is None:
                    summary = "无此前保存的业务总结。"
                    content = "没有可沿用的非自动 checkpoint。此点只保存 Codex 压缩前的转录快照，不包含新生成的业务总结。"
                else:
                    previous_id, previous_created_at, previous_summary, previous_content = previous
                    summary = (f"沿用 checkpoint {previous_id}（{previous_created_at}）的摘要；"
                               f"本次没有生成新摘要。\n{previous_summary}")
                    content = (f"沿用 checkpoint {previous_id}（{previous_created_at}）的阶段事实；"
                               f"本次没有生成新内容。\n{previous_content}")
                references = [checkpoint_ref]
                receipt = {
                    "request_key": request_key,
                    "checkpoint_id": checkpoint_id,
                    "trigger": trigger,
                    "transcript_sha256": transcript_hash,
                    "transcript_path": relative_path,
                    "state": "pending",
                    "summary": summary,
                    "content": content,
                    "record_refs": references,
                }
                write_json(receipt_path, receipt)

            operation_receipt = layout.local_path(root, "checkpoint-operations", worker_id) / f"{checkpoint_id}.json"
            registered = any(point["id"] == checkpoint_id for point in app.checkpoints(workspace, agent_id, worker_id=worker_id))
            revision_saved = operation_receipt.exists() or registered or layout.instance_path(
                root, f"checkpoints/{checkpoint_id}.json", worker_id).exists()
            if not revision_saved:
                if destination.exists() and destination.read_bytes() != transcript:
                    write_bytes(destination, transcript)
                elif not destination.exists():
                    write_bytes(destination, transcript)
                captured, _ = app.collect(root, worker_id=worker_id)
                if captured.get(relative_path) != transcript:
                    raise Conflict("AW snapshot rules exclude or alter the Codex transcript; no checkpoint was saved.")

            pointer = execute(app, "checkpoint.create", {
                "workspace": workspace,
                "agent_id": agent_id,
                "binding": binding,
                "summary": summary,
                "content": content,
                "checkpoint_id": checkpoint_id,
                "references": references,
                "worker_id": worker_id,
            }, actor=current_actor)

            _verify_checkpoint(app, workspace, agent_id, checkpoint_id,
                               pointer["revision"], checkpoint_ref, transcript, worker_id)
            receipt.update(state="saved", checkpoint_revision=pointer["revision"])
            write_json(receipt_path, receipt)
            return _reply(f"压缩前检查点已保存：{checkpoint_id}。")
    except Exception as exc:
        return _reply(f"压缩前检查点未能确认保存（{type(exc).__name__}: {exc}）；压缩继续。")
