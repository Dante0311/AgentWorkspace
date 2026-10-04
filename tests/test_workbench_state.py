"""A damaged observation must not take the whole management UI offline."""
import json
import threading
import urllib.error
import urllib.request

import pytest

from agent_workspace.server import make_server


@pytest.mark.parametrize("filename", ["status.json", "watch.json", "runtime.json"])
def test_state_keeps_other_instances_and_diagnostics_available(pair, filename):
    app, bindings = pair
    damaged = app.root("sea", "alice") / ".aw-local" / filename
    damaged.write_bytes(b"{broken")
    server = make_server(app, 0, "state-test-token")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    headers = {"Authorization": "Bearer state-test-token", "Content-Type": "application/json"}
    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(base + "/api/state", timeout=10)
        assert error.value.code == 401
        with urllib.request.urlopen(urllib.request.Request(base + "/api/state", headers=headers), timeout=10) as response:
            result = json.load(response)["result"]
        entries = {item["id"]: item for item in result["agents"]}
        assert set(entries) == {"alice", "bob"}
        assert entries["alice"]["current"] == bindings["alice"]
        assert "observation_error" in entries["alice"]
        assert "binding" not in entries["alice"]  # Unknown, not an invented inactive state.
        assert entries["bob"]["binding"]["id"] == bindings["bob"]
        assert result["errors"][0]["agent"] == "alice"
        body = json.dumps({"command": "workspace.doctor", "arguments": {"workspace": "sea"}}).encode()
        with urllib.request.urlopen(urllib.request.Request(base + "/api/execute", data=body, headers=headers), timeout=10) as response:
            report = json.load(response)["result"]
        # watch/runtime config may not be part of doctor's evidence; it must still respond.
        assert report["state"] in ("healthy", "degraded")
        assert damaged.read_bytes() == b"{broken"
        assert app.agent("sea", "alice")["current"] == bindings["alice"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
        assert not thread.is_alive()
