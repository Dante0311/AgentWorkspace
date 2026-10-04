"""Real Codex binary with a loopback Responses fixture, never a paid model.

Set AW_TEST_CODEX to an installed executable. This test does not install a Harness.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading

import pytest

from agent_workspace.harness_config import codex_config
from agent_workspace.runtime import Codex


def test_native_codex_custom_provider_tools_and_two_turns(app, tmp_path, monkeypatch):
    executable = os.environ.get("AW_TEST_CODEX")
    if not executable or not Path(executable).is_file():
        pytest.skip("An explicit Codex test executable is required.")
    home = tmp_path / "isolated-codex-home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("AW_TEST_MODEL_KEY", "isolated-test-key")
    for key in ("OPENAI_API_KEY", "CODEX_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    requests = []

    class ModelFixture(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, self.headers.get("Authorization"), body))
            number = len(requests)
            if number == 1:
                item = {"id": "fc-test", "type": "function_call", "call_id": "call-test", "name": "aw_execute",
                        "arguments": json.dumps({"command": "checkpoint.create", "arguments": {"summary": "Explicit native protocol checkpoint"}}),
                        "status": "completed"}
            else:
                item = {"id": f"msg-{number}", "type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": "Isolated protocol fixture completed.", "annotations": []}]}
            events = [
                {"type": "response.created", "response": {"id": f"resp-{number}", "status": "in_progress", "output": []}},
                {"type": "response.output_item.done", "output_index": 0, "item": item},
                {"type": "response.completed", "response": {"id": f"resp-{number}", "status": "completed", "output": [item],
                 "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}},
            ]
            payload = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), ModelFixture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    adapter = None
    try:
        app.create("sea", "native-test")
        root = app.root("sea", "native-test")
        config = codex_config(model="offline-test-model", effort="low", base_url=f"http://127.0.0.1:{server.server_port}/v1",
                              env_key="AW_TEST_MODEL_KEY", executable=executable)
        app.configure("sea", "native-test", config)
        binding = app.reserve("sea", "native-test")["binding"]
        adapter = Codex(app, "sea", "native-test", binding, root, config)
        app.bind("sea", "native-test", binding, adapter.session)
        session = adapter.session
        for text in ("Explicit protocol fixture, not a user task.", "Explicit second protocol fixture."):
            result = adapter.notify(text, "normal")
            completed = adapter.completed.get(timeout=30)
            assert completed["status"] == "completed", completed
            assert completed["id"] == result["turn"]["id"]
        assert adapter.session == session and adapter.status() == "idle"
        assert app.checkpoints("sea", "native-test")
        assert len(requests) == 3  # Tool call, tool result continuation, second user turn.
        assert all(path == "/v1/responses" and auth == "Bearer isolated-test-key" for path, auth, _ in requests)
        assert all(body["model"] == "offline-test-model" for _, _, body in requests)
        assert all(body.get("reasoning", {}).get("effort") == "low" for _, _, body in requests)
        assert not (home / "config.toml").exists()
    finally:
        if adapter:
            adapter.close()
        server.shutdown()
        server.server_close()
        thread.join(5)
