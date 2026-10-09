"""Isolated protocol compatibility check; never opens the daily workspace."""
from __future__ import annotations

import json
import tempfile
from contextlib import nullcontext
from pathlib import Path

from agent_workspace.app import App
from agent_workspace.messages import Messages
from agent_workspace.util import Conflict, Error, encode, now, uid


def require_manual(app, binding):
    actor, entry = app.require_binding("protocol-check", "workbench", binding)
    assert actor["current"] == binding
    assert entry["kind"] == "manual" and entry["session"] is None
    return actor, entry


def run_check():
    # Retain this isolated fixture; Windows may briefly lock Git files after use.
    with nullcontext(tempfile.mkdtemp(prefix="aw-github-protocol-")) as directory:
        sandbox = Path(directory)
        app = App(sandbox / "home")
        app.workspace_init("protocol-check", str(sandbox / "workspace.git"))
        store = app.store("protocol-check")
        store.change("main", {
            "definitions/workbench/definition.md": b"# Workbench\n\nIsolated protocol fixture.\n"
        }, {"definitions/workbench/definition.md": None}, "Fixture definition")
        app.create("protocol-check", "workbench", agent_id="workbench",
                   definition="definitions/workbench", request_id="fixture-workbench")
        app.create("protocol-check", "lead")
        lead_binding = app.reserve("protocol-check", "lead")["binding"]
        app.bind("protocol-check", "lead", lead_binding, "fixture-native-lead")

        binding, checkpoint, message_id = uid("b"), uid("c"), uid("m")
        shared = store.snapshot()
        original_actor_blob = shared.entries["agents/workbench.json"]
        actor = shared.json("agents/workbench.json")
        assert actor["current"] is None and not actor["has_run"]
        entry = {"id": binding, "agent": "workbench", "kind": "manual",
                 "phase": "starting", "session": None, "created_at": now(),
                 "handoff": None}
        actor.update(current=binding, has_run=True, handoff=None)
        store.change("main", {
            "agents/workbench.json": encode(actor),
            f"bindings/{binding}.json": encode(entry)
        }, {
            "agents/workbench.json": original_actor_blob,
            f"bindings/{binding}.json": None
        }, "Reserve manual fixture entry")

        stale_claim_rejected = False
        try:
            store.change("main", {"agents/workbench.json": encode(actor)}, {
                "agents/workbench.json": original_actor_blob
            }, "Stale competing claim")
        except Conflict:
            stale_claim_rejected = True
        assert stale_claim_rejected

        cli_without_session_supported = True
        try:
            app.bind("protocol-check", "workbench", binding, None)
        except Error:
            cli_without_session_supported = False
        assert not cli_without_session_supported

        shared = store.snapshot()
        entry = shared.json(f"bindings/{binding}.json")
        assert entry["phase"] == "starting"
        entry["phase"] = "active"
        store.change("main", {f"bindings/{binding}.json": encode(entry)}, {
            "agents/workbench.json": shared.entries["agents/workbench.json"],
            f"bindings/{binding}.json": shared.entries[f"bindings/{binding}.json"]
        }, "Activate manual fixture with no native session ID")
        require_manual(app, binding)

        timestamp = now()
        point = {"id": checkpoint, "created_at": timestamp,
                 "summary": "Manual protocol fixture entered.",
                 "content": "Only instance Git assets are saved.",
                 "record_refs": [],
                 "scope": "Instance Git assets only; native conversation export unavailable."}
        note = {"binding": binding, "checkpoint": checkpoint,
                "message": message_id, "session": None,
                "verification_value": "isolated-protocol-readback"}
        require_manual(app, binding)
        revision = store.change("instance/workbench", {
            "notes/startup.json": encode(note),
            f".aw/checkpoints/{checkpoint}.json": encode(point)
        }, {
            "notes/startup.json": None,
            f".aw/checkpoints/{checkpoint}.json": None
        }, "Save exact instance checkpoint")
        shared = store.snapshot()
        require_manual(app, binding)
        pointer = {"id": checkpoint, "agent": "workbench", "revision": revision,
                   "path": f".aw/checkpoints/{checkpoint}.json",
                   "created_at": timestamp, "excluded": []}
        store.change("main", {f"checkpoints/workbench/{checkpoint}.json": encode(pointer)}, {
            f"checkpoints/workbench/{checkpoint}.json": None,
            "agents/workbench.json": shared.entries["agents/workbench.json"],
            f"bindings/{binding}.json": shared.entries[f"bindings/{binding}.json"]
        }, "Register exact checkpoint")
        restored = app.checkpoint_show("protocol-check", "workbench", checkpoint)
        assert restored["record"] == point
        assert restored["revision"] == revision
        assert store.snapshot(revision=revision).json("notes/startup.json") == note

        shared = store.snapshot()
        require_manual(app, binding)
        locator = shared.json("workspace.json")["locator"]
        payload = {"id": message_id,
                   "from": {"workspace": locator, "agent": "workbench"},
                   "to": {"workspace": locator, "agent": "lead"},
                   "created_at": now(), "message_refs": [],
                   "delivery": "normal", "content": "Isolated protocol ping"}
        index = {key: payload[key] for key in ("id", "from", "to", "created_at", "delivery")}
        store.change("main", {
            f"messages/{message_id}.json": encode(payload),
            f"message-index/{message_id}.json": encode(index)
        }, {
            f"messages/{message_id}.json": None,
            f"message-index/{message_id}.json": None,
            "agents/workbench.json": shared.entries["agents/workbench.json"],
            f"bindings/{binding}.json": shared.entries[f"bindings/{binding}.json"],
            "agents/lead.json": shared.entries["agents/lead.json"]
        }, "Publish protocol ping")

        messages = Messages(app)
        received = messages.receive("protocol-check", "lead", lead_binding, message_id)
        assert received["message"] == payload
        assert received["publication"]["state"] == "published"
        assert messages.show("protocol-check", message_id)["ack"] == {"message_id": message_id}
        reply_id = uid("m")
        reply = messages.send("protocol-check", "lead", lead_binding, "workbench",
                              "Isolated protocol reply", message_refs=[message_id],
                              request_id=reply_id)
        assert reply["state"] == "published"
        shared = store.snapshot()
        require_manual(app, binding)
        reply_index = shared.json(f"message-index/{reply_id}.json")
        reply_body = shared.json(f"messages/{reply_id}.json")
        assert reply_index["to"] == {"workspace": locator, "agent": "workbench"}
        assert reply_body["message_refs"] == [message_id]
        store.change("main", {f"acks/{reply_id}.json": encode({"message_id": reply_id})}, {
            f"acks/{reply_id}.json": None,
            "agents/workbench.json": shared.entries["agents/workbench.json"],
            f"bindings/{binding}.json": shared.entries[f"bindings/{binding}.json"]
        }, "Acknowledge reply through protocol")
        assert messages.show("protocol-check", reply_id)["ack"] == {"message_id": reply_id}

        shared = store.snapshot()
        actor, entry = require_manual(app, binding)
        entry.update(phase="stopping", checkpoint=checkpoint, stop_requested_at=now())
        store.change("main", {f"bindings/{binding}.json": encode(entry)}, {
            "agents/workbench.json": shared.entries["agents/workbench.json"],
            f"bindings/{binding}.json": shared.entries[f"bindings/{binding}.json"]
        }, "Fixture requests handoff")

        # Test data models an explicit confirmation; it is not native idle evidence.
        shared = store.snapshot()
        actor = shared.json("agents/workbench.json")
        entry = shared.json(f"bindings/{binding}.json")
        handoff_id = "h" + binding[1:]
        handoff = {"id": handoff_id, "agent": "workbench", "entry": binding,
                   "checkpoint": checkpoint, "created_at": now(), "consumed_by": None}
        actor.update(current=None, handoff=handoff_id)
        entry.update(phase="released", stopped_at=now())
        store.change("main", {
            "agents/workbench.json": encode(actor),
            f"bindings/{binding}.json": encode(entry),
            f"handoffs/{handoff_id}.json": encode(handoff)
        }, {
            "agents/workbench.json": shared.entries["agents/workbench.json"],
            f"bindings/{binding}.json": shared.entries[f"bindings/{binding}.json"],
            f"handoffs/{handoff_id}.json": None
        }, "Release fixture after simulated explicit confirmation")

        successor = uid("b")
        shared = store.snapshot()
        actor = shared.json("agents/workbench.json")
        handoff = shared.json(f"handoffs/{handoff_id}.json")
        assert actor["current"] is None and actor["handoff"] == handoff_id
        assert handoff["consumed_by"] is None
        actor.update(current=successor, handoff=None)
        handoff["consumed_by"] = successor
        new_entry = {"id": successor, "agent": "workbench", "kind": "manual",
                     "phase": "starting", "session": None, "created_at": now(),
                     "handoff": handoff_id}
        store.change("main", {
            "agents/workbench.json": encode(actor),
            f"handoffs/{handoff_id}.json": encode(handoff),
            f"bindings/{successor}.json": encode(new_entry)
        }, {
            "agents/workbench.json": shared.entries["agents/workbench.json"],
            f"handoffs/{handoff_id}.json": shared.entries[f"handoffs/{handoff_id}.json"],
            f"bindings/{successor}.json": None
        }, "Claim fixture successor")
        shared = store.snapshot()
        new_entry["phase"] = "active"
        store.change("main", {f"bindings/{successor}.json": encode(new_entry)}, {
            "agents/workbench.json": shared.entries["agents/workbench.json"],
            f"bindings/{successor}.json": shared.entries[f"bindings/{successor}.json"]
        }, "Activate fixture successor")

        require_manual(app, successor)
        assert app.checkpoint_show("protocol-check", "workbench", checkpoint)["revision"] == revision
        old_entry_rejected = False
        try:
            app.require_binding("protocol-check", "workbench", binding)
        except Conflict:
            old_entry_rejected = True
        assert old_entry_rejected

        result = {
            "result": "passed",
            "scope": "Isolated local Git protocol compatibility with installed AW 0.1.0a1; no daily workspace or GitHub writes.",
            "checks": {
                "manual_active_record_without_native_session_readable": True,
                "stale_competing_claim_rejected": stale_claim_rejected,
                "checkpoint_pointer_and_exact_assets_readable": True,
                "AW_receives_protocol_message_and_publishes_ACK": True,
                "AW_reply_read_and_ACKed_through_protocol": True,
                "handoff_consumed_by_new_manual_binding": True,
                "old_binding_rejected": old_entry_rejected
            },
            "unchanged_limitations": {
                "agent_bind_without_native_session_id_supported": cli_without_session_supported,
                "real_GitHub_tool_execution_verified": False,
                "real_model_protocol_following_verified": False,
                "native_session_identity_or_idle_observed": False,
                "real_chat_handoff_verified": False
            }
        }
        return result


if __name__ == "__main__":
    print(json.dumps(run_check(), ensure_ascii=False, indent=2))
