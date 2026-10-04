"""Native errors must not leave a healthy-looking runner or repeat an input."""
import importlib
import json
import queue
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent_workspace import native_sdk, runtime
from agent_workspace.harness_config import sdk_config
from agent_workspace.util import Unavailable, read_json
from test_native_sdk import Peer


class ErrorPeer(Peer):
    async def write(self, data):
        request = json.loads(data)
        if request['type'] != 'user':
            return await super().write(data)
        self.requests.append(request)
        await self.inbox.put({'type': 'system', 'subtype': 'init', 'session_id': self.session})
        # The public CodeBuddy SDK also has standalone terminal errors, not only ResultMessage.
        await self.inbox.put({'type': 'error', 'session_id': self.session, 'error': 'private-native-detail'})


def test_codebuddy_terminal_error_is_saved_and_stops_client(app, monkeypatch):
    sdk = pytest.importorskip('codebuddy_agent_sdk')
    original_import = importlib.import_module
    peer = ErrorPeer()
    proxy = SimpleNamespace(**{name: getattr(sdk, name) for name in dir(sdk)})
    proxy.CodeBuddySDKClient = lambda options: sdk.CodeBuddySDKClient(options=options, transport=peer)
    monkeypatch.setattr(importlib, 'import_module',
                        lambda name, *a, **kw: proxy if name == 'codebuddy_agent_sdk' else original_import(name, *a, **kw))
    app.create('sea', 'alice')
    profile = sdk_config('codebuddy', executable=sys.executable)
    app.configure('sea', 'alice', profile)
    binding = app.reserve('sea', 'alice')['binding']
    adapter = native_sdk.NativeSDK(app, 'sea', 'alice', binding, app.root('sea', 'alice'), profile)
    try:
        adapter.connect()
        try:
            adapter.bootstrap('Explicit terminal-error fixture; do not retry.')
        except Unavailable:
            pass  # The error may arrive before or just after session confirmation.
        adapter.thread.join(10)
        assert not adapter.thread.is_alive(), 'Terminal ErrorMessage left the native client running.'
        assert adapter.status() == 'unknown' and adapter.stopped
        assert 'private-native-detail' not in adapter.failure
        records = [json.loads(line) for line in adapter.record.read_text().splitlines()]
        assert any(record['native_type'] == 'ErrorMessage' for record in records)
        assert not any(record.get('completion') for record in records)
        with pytest.raises(Unavailable):
            adapter.notify('must not repeat', 'normal')
        assert len([r for r in peer.requests if r['type'] == 'user']) == 1
        assert app.agent('sea', 'alice')['current'] == binding
        assert not app.checkpoints('sea', 'alice')
    finally:
        adapter.close()
    assert peer.closed


@pytest.mark.parametrize('phase', ['active', 'stopping'])
def test_runner_reports_disconnected_sdk_even_without_inputs_or_watch(app, monkeypatch, phase):
    app.create('sea', 'alice')
    app.configure('sea', 'alice', {'kind': 'claude', 'executable': sys.executable})
    binding = app.reserve('sea', 'alice')['binding']
    app.bind('sea', 'alice', binding, 'native-session')
    point = app.checkpoint('sea', 'alice', 'Explicit test checkpoint', binding=binding)

    class DisconnectedSDK:
        def __init__(self, *args):
            self.session = 'native-session'
            self.completed = queue.Queue()
            self.close = Mock()

        def connect(self):
            if phase == 'stopping':
                app.stop('sea', 'alice', binding, point['id'])

        def status(self):
            return 'unknown'

    monkeypatch.setattr(runtime, 'NativeSDK', DisconnectedSDK)
    runner = runtime.Runner(app, 'sea', 'alice')
    # One iteration suffices; no wall-clock waiting and no native program needed.
    runner.stop_event = Mock()
    runner.stop_event.wait.side_effect = [False, True]
    with pytest.raises(Unavailable, match='disconnected'):
        runner.run()
    state = read_json(app.root('sea', 'alice') / '.aw-local/status.json')
    assert state['state'] == 'failed' and not state['entry_automatically_released']
    entry = app.show('sea', 'alice')['binding']
    assert entry['id'] == binding and entry['phase'] == phase
    assert not entry.get('controller')  # Controller cleanup is not a handoff.
    runner.adapter.close.assert_called_once()
