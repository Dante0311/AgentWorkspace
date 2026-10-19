import threading
from unittest.mock import Mock

import pytest

from agent_workspace.rpc import Rpc, RpcTimeout
from agent_workspace.util import Unavailable


@pytest.mark.parametrize("tool", ["read_thread", "send_message_to_thread"])
def test_timeout_identifies_original_tool_and_does_not_poison_connection(tool):
    rpc = object.__new__(Rpc)
    rpc.lock, rpc.pending, rpc.next_id, rpc.failure = threading.Lock(), {}, 1, None
    rpc.send = Mock()
    with pytest.raises(RpcTimeout) as failure:
        rpc.request("tools/call", {"name": tool, "arguments": {"private": "not a diagnostic"}}, timeout=0)
    assert isinstance(failure.value, Unavailable)
    assert failure.value.method == "tools/call" and failure.value.tool == tool
    assert failure.value.timeout == 0 and "private" not in str(failure.value)
    assert not rpc.pending and rpc.failure is None

    def reply(request):
        assert request["id"] == 2
        rpc.pending[request["id"]].put({"result": {"original_reply": True}})

    rpc.send.side_effect = reply
    assert rpc.request("tools/call", {"name": "read_thread"}) == {"original_reply": True}
    assert not rpc.pending
