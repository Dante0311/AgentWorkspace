"""Exercise installed native SDK clients through an isolated transport, never a model."""
import asyncio
from collections import deque
import importlib
import json
import sys
import time
from types import SimpleNamespace

import pytest

from agent_workspace import native_sdk, runtime
from agent_workspace.harness_config import sdk_config
from agent_workspace.util import Conflict, Error, Unavailable, read_json


class Peer:
    def __init__(self):
        self.inbox = asyncio.Queue()
        self.requests = []
        self.closed = False
        self.session = "native-session-from-protocol-peer"
        self.fail_send = False

    async def connect(self):
        self.closed = False

    async def write(self, data):
        request = json.loads(data)
        self.requests.append(request)
        if request["type"] == "control_request":
            await self.inbox.put({"type": "control_response", "response": {
                "subtype": "success", "request_id": request["request_id"], "response": {}}})
        elif request["type"] == "user":
            if self.fail_send:
                raise OSError("lost native pipe")
            await self.inbox.put({"type": "system", "subtype": "init", "session_id": self.session})
            await self.inbox.put({"type": "result", "subtype": "success", "is_error": False,
                "session_id": self.session, "duration_ms": 1, "duration_api_ms": 1, "num_turns": 1,
                "result": "explicit protocol fixture", "usage": {}})

    async def read_messages(self):
        while not self.closed:
            value = await self.inbox.get()
            if value is None:
                return
            yield value

    async def close(self):
        self.closed = True
        await self.inbox.put(None)

    def is_ready(self):
        return not self.closed

    @property
    def is_closed(self):
        return self.closed

    @property
    def sdk_mcp_server_names(self):
        return []

    async def end_input(self):
        pass


@pytest.fixture(params=["claude", "codebuddy"])
def connected(app, monkeypatch, request):
    kind = request.param
    module_name, client_name, option_name, _ = native_sdk.SDK_TYPES[kind]
    sdk = pytest.importorskip(module_name)
    original_import = importlib.import_module
    peer = Peer()
    client = getattr(sdk, client_name)
    proxy = SimpleNamespace(**{name: getattr(sdk, name) for name in dir(sdk)})
    setattr(proxy, client_name, lambda options: client(options=options, transport=peer))
    monkeypatch.setattr(importlib, "import_module", lambda name, *a, **kw: proxy if name == module_name else original_import(name, *a, **kw))
    app.create("sea", "alice")
    profile = sdk_config(kind, model="model-under-test", executable=sys.executable)
    app.configure("sea", "alice", profile)
    binding = app.reserve("sea", "alice")["binding"]
    adapter = native_sdk.NativeSDK(app, "sea", "alice", binding, app.root("sea", "alice"), profile)
    adapter.connect()
    yield app, adapter, peer, profile
    adapter.close()
    assert peer.closed and not adapter.thread.is_alive()


def test_native_session_and_two_turns_use_one_client(connected):
    app, adapter, peer, config = connected
    assert app.show("sea", "alice")["binding"]["phase"] == "starting"
    adapter.bootstrap("Explicit test: initialize this isolated instance.")
    assert adapter.session == peer.session
    assert app.show("sea", "alice")["binding"]["session"] == peer.session
    first = adapter.completed.get(timeout=5)
    assert first["status"] == "completed"
    result = adapter.notify("Explicit second test input.", "normal")
    second = adapter.completed.get(timeout=5)
    assert second["id"] == result["turn"]["id"] and first["id"] != second["id"]
    assert len([r for r in peer.requests if r["type"] == "user"]) == 2
    runner = runtime.Runner(app, "sea", "alice")
    runner.binding, runner.adapter = adapter.binding, adapter
    adapter.completed.put(first)
    runner._complete_inputs()
    boot = read_json(adapter.root / ".aw-local/inputs" / f"boot-{adapter.binding}.json")
    assert boot["checkpoint_revision"]
    assert not app.work_list("sea")


def test_sdk_does_not_pretend_insert_is_supported(connected):
    _, adapter, peer, _ = connected
    before = len(peer.requests)
    with pytest.raises(Error, match="insert"):
        adapter.notify("must not be sent", "insert")
    assert not any(r["type"] == "user" for r in peer.requests[before:])


def test_sdk_submit_failure_stays_unknown(connected):
    _, adapter, peer, _ = connected
    peer.fail_send = True
    with pytest.raises(Unavailable, match="unknown"):
        adapter.notify("explicit send failure fixture", "normal")
    assert adapter.status() == "unknown"
    before = len(peer.requests)
    with pytest.raises(Unavailable):
        adapter.notify("must not retry", "normal")
    assert len(peer.requests) == before


def test_native_tool_guard_rejects_released_entry(connected):
    app, adapter, _, _ = connected
    adapter.bootstrap("explicit init")
    adapter.completed.get(timeout=5)
    point = app.checkpoint("sea", "alice", "done", binding=adapter.binding)
    app.stop("sea", "alice", adapter.binding, point["id"])
    result = asyncio.run_coroutine_threadsafe(adapter._tool_guard({}, None, None), adapter.loop).result(5)
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_profiles_keep_credentials_as_references(monkeypatch):
    monkeypatch.setenv("AW_TEST_API_KEY", "secret-not-for-files")
    for kind in ("claude", "codebuddy"):
        config = sdk_config(kind, base_url="https://gateway.example", env_key="AW_TEST_API_KEY", executable=sys.executable)
        assert "secret-not-for-files" not in json.dumps(config)
    with pytest.raises(Error):
        sdk_config("claude", base_url="https://user:password@gateway.example", executable=sys.executable)


@pytest.mark.parametrize('kind', ['claude', 'codebuddy'])
def test_codex_runner_automatically_transfers_to_native_sdk(app, monkeypatch, kind):
    """Real Runner, Git, native SDK and isolated Codex subprocess; no model call."""
    from pathlib import Path
    import threading
    from agent_workspace import transfer
    module_name, client_name, _, _ = native_sdk.SDK_TYPES[kind]
    sdk = pytest.importorskip(module_name)
    original_import = importlib.import_module
    peer = Peer()
    client = getattr(sdk, client_name)
    proxy = SimpleNamespace(**{name: getattr(sdk, name) for name in dir(sdk)})
    setattr(proxy, client_name, lambda options: client(options=options, transport=peer))
    monkeypatch.setattr(importlib, 'import_module', lambda name, *a, **kw: proxy if name == module_name else original_import(name, *a, **kw))
    app.create('sea', 'alice')
    root = app.root('sea', 'alice')
    (root / 'user-note.md').write_text('Keep this asset through the transfer.', encoding='utf-8')
    app.configure('sea', 'alice', {'kind': 'codex', 'command': [sys.executable, str(Path(__file__).with_name('fake_native.py')), 'codex']})
    runners, threads, failures = [], [], []

    def spawn(app, workspace, agent_id, directory):
        runner = runtime.Runner(app, workspace, agent_id, directory)
        runners.append(runner)
        def target():
            try:
                runner.run()
            except Exception as exc:
                failures.append(exc)
        thread = threading.Thread(target=target)
        threads.append(thread)
        thread.start()
        return {'state': 'starting_runner', 'pid': 0}

    def wait_until(predicate):
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline and not failures:
            if predicate():
                return
            time.sleep(.05)
        pytest.fail(f'Native runner did not reach expected state: {failures}; {read_json(root / ".aw-local/status.json")}')

    monkeypatch.setattr(runtime, 'spawn_runner', spawn)
    try:
        runtime.start(app, 'sea', 'alice')
        wait_until(lambda: bool(app.checkpoints('sea', 'alice')))
        old = app.agent('sea', 'alice')['current']
        target = sdk_config(kind, executable=sys.executable, model='explicit-test-model')
        op = transfer.request(app, 'sea', 'alice', target, request_id='cross-harness')
        # Simulate the explicitly requested old model's checkpoint/stop tool calls.
        cp = app.checkpoint('sea', 'alice', 'Explicit handoff fixture', binding=old)
        app.stop('sea', 'alice', old, cp['id'])
        wait_until(lambda: transfer.status(app, 'sea', 'alice')['state'] == 'completed')
        assert len(runners) == 2
        entry = app.show('sea', 'alice')['binding']
        assert entry['kind'] == kind and entry['session'] == peer.session
        assert entry['id'] == op['target_binding'] and entry['id'] != old
        assert (root / 'user-note.md').read_text(encoding='utf-8') == 'Keep this asset through the transfer.'
        prompts = [r['message']['content'] for r in peer.requests if r['type'] == 'user']
        assert 'Explicit handoff fixture' in prompts[0]
        with pytest.raises(Conflict):
            app.require_binding('sea', 'alice', old)
    finally:
        for runner in runners:
            runner.stop_event.set()
        for thread in threads:
            thread.join(timeout=15)
    assert not failures and not any(thread.is_alive() for thread in threads)
