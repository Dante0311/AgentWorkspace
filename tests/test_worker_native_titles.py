"""Native title requests and readbacks, without live sessions or model input."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent_workspace import model_profiles, native_sdk, runtime, session_titles
from agent_workspace.util import Unavailable, read_json, write_json


@pytest.fixture
def native_root(tmp_path):
    root = tmp_path / "agent"
    root.mkdir()
    write_json(root / "runtime.json", {"codex": {"model": "fixture-model", "effort": "high"}})
    write_json(root / ".aw-local/entry.json", {"binding": "one", "config": {"kind": "desktop"},
               "model_profile": model_profiles.selected(root)})
    return root


@pytest.mark.parametrize("title_supported", [True, False])
def test_desktop_uses_advertised_title_field_and_records_native_readback(native_root, monkeypatch, title_supported):
    root = native_root
    title = session_titles.format_title("AW", "Runtime", "运行器")
    fields = {"model": {"type": "string"}, "thinking": {"type": "string"}}
    if title_supported:
        fields["title"] = {"type": "string"}
    rpc = Mock()
    rpc.request.return_value = {"tools": [{"name": name, "inputSchema": {"properties": fields}}
        for name in ("read_thread", "send_message_to_thread", "create_thread", "list_projects")]}
    monkeypatch.setattr(runtime, "Rpc", Mock(return_value=rpc))
    adapter = runtime.Desktop(root, {"command": ["fixture"], "pipe_path": "fixture", "caller_thread": "fixture"}, None, title=title)
    requests = []
    def call(name, arguments):
        requests.append((name, arguments))
        if name == "list_projects":
            return {"projects": [{"projectId": "project", "projectKind": "local", "hostId": "local", "path": str(root)}]}
        if name == "create_thread":
            return {"threadId": "new-thread", "hostId": "local"}
        if name == "read_thread":
            return {"thread": {"id": "new-thread", "hostId": "local", "cwd": str(root),
                               "title": title if title_supported else "Host title", "status": {"type": "idle"}}}
        pytest.fail("Title creation must not send an extra model input")
    adapter.call = call
    adapter.create("one", "Connection-only fixture")
    creates = [args for name, args in requests if name == "create_thread"]
    assert len(creates) == 1 and ("title" in creates[0]) == title_supported
    saved = read_json(root / ".aw-local/launch.json")["native_title"]
    assert saved["requested"] == title
    assert saved["reported"] == (title if title_supported else "Host title")
    assert saved["native_accepted"] is (True if title_supported else None)


def test_codex_unknown_name_write_is_read_back_without_repeating_creation(native_root, monkeypatch):
    title, methods = "AW · Runtime · 压缩记录", []
    class NativeRpc:
        name = None
        def __init__(self, *args, **kwargs):
            pass
        def send(self, value):
            pass
        def request(self, method, params=None, **kwargs):
            methods.append(method)
            if method == "thread/start":
                return {"thread": {"id": "new-thread"}}
            if method == "thread/name/set":
                self.name = params["name"]
                raise Unavailable("Title write reply lost")
            if method == "thread/read":
                return {"thread": {"id": "new-thread", "name": self.name, "status": {"type": "idle"}}}
            return {}
        def close(self):
            pass
    monkeypatch.setattr(runtime, "Rpc", NativeRpc)
    adapter = runtime.Codex(SimpleNamespace(home=native_root), "aw", "runtime", "one", native_root,
                            {"kind": "codex", "modelProvider": "protocol-fixture"}, title=title)
    assert methods.count("thread/start") == methods.count("thread/name/set") == 1
    assert "turn/start" not in methods
    assert adapter.title_receipt["native_accepted"] is None
    assert adapter.title_receipt["reported"] == title
    assert read_json(native_root / ".aw-local/launch.json")["native_title"]["effective"] == "native_reported"


def test_desktop_name_write_with_unknown_reply_is_not_repeated(native_root, monkeypatch):
    rpc = Mock()
    rpc.request.return_value = {"tools": [{"name": name, "inputSchema": {"properties": {"title": {}, "threadId": {}}}}
        for name in ("read_thread", "send_message_to_thread", "set_thread_title")]}
    monkeypatch.setattr(runtime, "Rpc", Mock(return_value=rpc))
    adapter = runtime.Desktop(native_root, {"command": ["fixture"], "pipe_path": "fixture", "caller_thread": "fixture"}, "original")
    calls = []
    title = "AW · Runtime · 接续"
    def call(name, arguments):
        calls.append(name)
        if name == "set_thread_title":
            raise Unavailable("Reply lost after the name was applied")
        return {"thread": {"id": "original", "title": title}}
    adapter.call = call
    assert adapter.set_title(title)["reported"] == title
    assert adapter.set_title(title)["native_accepted"] is None
    assert calls.count("set_thread_title") == 1


@pytest.mark.parametrize("supported", [True, False])
def test_sdk_title_uses_only_an_explicit_installed_option(native_root, monkeypatch, supported):
    class NamedOptions:
        def __init__(self, session_name=None, **kwargs):
            pass
    class OtherOptions:
        def __init__(self, **kwargs):
            pass
    monkeypatch.setattr(native_sdk, "sdk_options", lambda *args: (None, None, NamedOptions if supported else OtherOptions, {}))
    adapter = native_sdk.NativeSDK(SimpleNamespace(), "aw", "runtime", "one", native_root, {}, title="AW · Runtime · SDK")
    assert ("session_name" in adapter.options) == supported
    assert adapter.title_receipt["native_accepted"] is None
    assert adapter.title_receipt["reported"] is None
