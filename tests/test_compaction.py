import io
import json
import os
import sys

import pytest

from agent_workspace import compaction, layout
from agent_workspace.util import Error, read_json, write_json


@pytest.fixture(autouse=True)
def clear_inherited_identity(monkeypatch):
    for name in tuple(os.environ):
        if name.startswith("AW_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)


def desktop_binding(app, monkeypatch, tmp_path, *, session="native-session"):
    app.create("sea", "e2e", directory=str(tmp_path / "instance"))
    app.configure("sea", "e2e", {"kind": "desktop"})
    root = app.root("sea", "e2e")
    binding = app.reserve("sea", "e2e")["binding"]
    app.bind("sea", "e2e", binding, session)
    monkeypatch.setenv("AW_HOME", str(app.home))
    monkeypatch.setenv("AW_WORKSPACE", "sea")
    monkeypatch.setenv("AW_AGENT", "e2e")
    monkeypatch.setenv("AW_BINDING", binding)
    return root, binding


def transcript_file(tmp_path, session, body=b'{"type":"turn_context"}\n'):
    path = tmp_path / "native-rollout.jsonl"
    header = json.dumps({"type": "session_meta", "payload": {"id": session}},
                        separators=(",", ":")).encode("utf-8")
    path.write_bytes(header + b"\n" + body)
    return path


def event(session, path, *, turn="turn-1", trigger="auto"):
    return {"hook_event_name": "PreCompact", "session_id": session,
            "turn_id": turn, "trigger": trigger, "transcript_path": str(path.resolve())}


def response(app, payload):
    result = compaction.run(app, payload)
    assert result["continue"] is True
    assert isinstance(result["systemMessage"], str)
    return result


def precompact_points(app, agent_id="e2e"):
    result = []
    for pointer in app.checkpoints("sea", agent_id):
        record = app.checkpoint_show("sea", agent_id, pointer["id"])["record"]
        if any(ref.get("source") == "codex-precompact" for ref in record.get("record_refs", [])):
            result.append((pointer, record))
    return result


def test_precompact_uses_desktop_identity_saves_exact_bytes_and_reuses_business_summary(app, tmp_path, monkeypatch):
    root, binding = desktop_binding(app, monkeypatch, tmp_path)
    business = app.checkpoint("sea", "e2e", "业务目标", "已确认事实与待办。", binding=binding)
    app.checkpoint("sea", "e2e", "自动初始化摘要", "不能覆盖业务总结。",
                   binding=binding, checkpoint_id="initial-first")
    raw = transcript_file(tmp_path, "native-session", '{"type":"assistant"}\n未改写的原始字节\n'.encode("utf-8"))
    expected = raw.read_bytes()

    # Exercise the real Desktop lookup through CODEX_THREAD_ID, not the AW_* caller path.
    for name in ("AW_HOME", "AW_WORKSPACE", "AW_AGENT", "AW_BINDING"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "native-session")
    payload = event("native-session", raw)
    first = response(app, payload)
    repeated = response(app, payload)

    points = precompact_points(app)
    assert len(points) == 1
    pointer, record = points[0]
    assert record["summary"].startswith(f"沿用 checkpoint {business['id']}（{business['created_at']}）")
    assert record["summary"].endswith("\n业务目标")
    assert record["content"].startswith(f"沿用 checkpoint {business['id']}（{business['created_at']}）")
    assert record["content"].endswith("\n已确认事实与待办。")
    reference = record["record_refs"][0]
    assert reference["session_id"] == "native-session"
    assert reference["turn_id"] == "turn-1"
    assert reference["trigger"] == "auto"
    assert reference["transcript_cutoff_bytes"] == len(expected)
    archived = layout.instance_path(root, f"records/{binding}/codex-transcript.jsonl")
    archived_path = layout.instance_relpath(root, f"records/{binding}/codex-transcript.jsonl")
    assert reference["transcript_path"] == archived_path
    assert archived.read_bytes() == expected
    snapshot = app.store("sea").snapshot(revision=pointer["revision"])
    assert snapshot.bytes(archived_path) == expected
    assert pointer["id"] in first["systemMessage"]
    assert pointer["id"] in repeated["systemMessage"]
    assert app.agent("sea", "e2e")["current"] == binding
    assert app.require_binding("sea", "e2e", binding)[1]["phase"] == "active"


def test_unbound_payload_cannot_claim_identity_and_cli_emits_codex_json(app, tmp_path, monkeypatch, capsys):
    raw = transcript_file(tmp_path, "claimed-session")
    payload = event("claimed-session", raw)
    payload.update(workspace="sea", agent_id="e2e", binding="forged", actor=("sea", "e2e", "forged"))

    result = response(app, payload)
    assert "没有 AW 执行身份" in result["systemMessage"]
    assert not any(item["id"] == "e2e" for item in app.agents("sea"))

    from agent_workspace import cli
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert cli.main(["--home", str(tmp_path / "cli-home"), "codex-hook"]) == 0
    valid = json.loads(capsys.readouterr().out)
    assert valid["continue"] is True and isinstance(valid["systemMessage"], str)

    monkeypatch.setattr(sys, "stdin", io.StringIO("{invalid json"))
    assert cli.main(["--home", str(tmp_path / "cli-home"), "codex-hook"]) == 0
    invalid = json.loads(capsys.readouterr().out)
    assert invalid["continue"] is True and isinstance(invalid["systemMessage"], str)


def test_stale_binding_is_refused_after_takeover(app, tmp_path, monkeypatch):
    root, old_binding = desktop_binding(app, monkeypatch, tmp_path)
    old_point = app.checkpoint("sea", "e2e", "takeover point", "saved before takeover", binding=old_binding)
    app.takeover("sea", "e2e", old_binding, old_point["id"], confirm=True)
    successor = app.reserve("sea", "e2e")["binding"]
    app.bind("sea", "e2e", successor, "successor-session")
    raw = transcript_file(tmp_path, "old-session")
    monkeypatch.setenv("AW_BINDING", old_binding)

    result = response(app, event("old-session", raw))

    assert "未能确认保存" in result["systemMessage"]
    assert precompact_points(app) == []
    assert not layout.instance_path(root, f"records/{old_binding}/codex-transcript.jsonl").exists()
    assert app.agent("sea", "e2e")["current"] == successor


def test_invalid_sessions_missing_and_excluded_transcript_are_refused(app, tmp_path, monkeypatch):
    root, binding = desktop_binding(app, monkeypatch, tmp_path)
    wrong_session = transcript_file(tmp_path, "claimed-other-session")
    wrong_header = transcript_file(tmp_path, "different-header")
    missing = tmp_path / "missing-rollout.jsonl"
    cases = [event("claimed-other-session", wrong_session),
             event("native-session", wrong_header),
             event("native-session", missing)]
    for payload in cases:
        assert "未能确认保存" in response(app, payload)["systemMessage"]

    context_path = layout.local_path(root, "context.json")
    context = read_json(context_path)
    context["exclude"].append(layout.instance_relpath(root, f"records/{binding}/codex-transcript.jsonl"))
    write_json(context_path, context)
    excluded = transcript_file(tmp_path, "native-session")
    result = response(app, event("native-session", excluded, turn="turn-excluded"))
    assert "未能确认保存" in result["systemMessage"]
    assert precompact_points(app) == []


def test_index_publication_retry_reuses_pending_checkpoint(app, tmp_path, monkeypatch):
    root, binding = desktop_binding(app, monkeypatch, tmp_path)
    app.checkpoint("sea", "e2e", "业务总结", "固定的旧总结。", binding=binding)
    raw = transcript_file(tmp_path, "native-session", '{"type":"assistant"}\n原始内容\n'.encode("utf-8"))
    payload = event("native-session", raw)
    store = app.store("sea")
    original_change = store.change
    failed = False

    def fail_checkpoint_index(branch, changes, expected, message, **kwargs):
        nonlocal failed
        if message.startswith("Register checkpoint ") and not failed:
            failed = True
            raise Error("injected checkpoint index publication failure")
        return original_change(branch, changes, expected, message, **kwargs)

    monkeypatch.setattr(store, "change", fail_checkpoint_index)
    failure = response(app, payload)
    assert failed and "未能确认保存" in failure["systemMessage"]
    assert precompact_points(app) == []
    receipts = list((root / ".agentworkspace" / "local" / "runtime" / "precompact").glob("*.json"))
    assert len(receipts) == 1
    receipt = read_json(receipts[0])
    assert receipt["state"] == "pending"
    checkpoint_id = receipt["checkpoint_id"]

    monkeypatch.setattr(store, "change", original_change)
    retry = response(app, payload)
    points = precompact_points(app)
    assert len(points) == 1 and points[0][0]["id"] == checkpoint_id
    assert checkpoint_id in retry["systemMessage"]
    assert points[0][1]["summary"].endswith("\n业务总结")
    assert points[0][1]["content"].endswith("\n固定的旧总结。")
    assert len(list((root / ".agentworkspace" / "local" / "operations" / "checkpoint-operations").glob(f"{checkpoint_id}.json"))) == 1


def test_native_hook_routes_by_session_and_rejects_other_or_stale_binding(app, tmp_path, monkeypatch):
    bindings = {}
    for agent_id, session in (("target", "target-native-session"), ("other", "other-native-session")):
        app.create("sea", agent_id, directory=str(tmp_path / agent_id))
        app.configure("sea", agent_id, {"kind": "desktop"})
        binding = app.reserve("sea", agent_id)["binding"]
        app.bind("sea", agent_id, binding, session)
        bindings[agent_id] = binding

    raw = transcript_file(tmp_path, "target-native-session")
    saved = response(app, event("target-native-session", raw))
    target_points = precompact_points(app, "target")
    assert len(target_points) == 1
    checkpoint_id = target_points[0][0]["id"]
    assert checkpoint_id in saved["systemMessage"]
    assert app.checkpoints("sea", "other") == []

    # A real but unbound Desktop chat ID must not fall back to payload.session_id.
    monkeypatch.setenv("CODEX_THREAD_ID", "unbound-real-desktop-chat")
    wrong_chat = response(app, event("target-native-session", raw, turn="turn-other-chat"))
    assert "已保存" not in wrong_chat["systemMessage"]
    assert len(precompact_points(app, "target")) == 1
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)

    app.takeover("sea", "target", bindings["target"], checkpoint_id, confirm=True)
    successor = app.reserve("sea", "target")["binding"]
    app.bind("sea", "target", successor, "target-successor-session")
    stale = response(app, event("target-native-session", raw, turn="turn-old-binding"))
    assert "已保存" not in stale["systemMessage"]
    assert len(precompact_points(app, "target")) == 1
    assert app.agent("sea", "target")["current"] == successor
