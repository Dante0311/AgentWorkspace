"""Orderly server shutdown drains its own worker, without releasing Agent authority."""
import json
import threading
import urllib.error
import urllib.request

import pytest

from agent_workspace import server, maintenance


def test_shutdown_requires_local_control_token(app):
    http = server.make_server(app, 0, 'test-control')
    thread = threading.Thread(target=http.serve_forever)
    thread.start()
    url = f'http://127.0.0.1:{http.server_port}/api/shutdown'
    try:
        for headers in ({}, {'Authorization': 'Bearer wrong'},
                        {'Authorization': 'Bearer test-control', 'Origin': 'https://invalid.example'}):
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(urllib.request.Request(url, data=b'', headers=headers), timeout=5)
            assert exc.value.code in (401, 403)
            assert thread.is_alive()
        with urllib.request.urlopen(urllib.request.Request(url, data=b'', headers={'Authorization': 'Bearer test-control'}), timeout=5) as response:
            result = json.load(response)
        assert result['result']['agent_bindings_released'] is False
        thread.join(5)
        assert not thread.is_alive()
    finally:
        http.shutdown()
        http.server_close()
        thread.join(5)


def test_serve_waits_for_worker_after_stop(app, monkeypatch):
    entered, finished = threading.Event(), threading.Event()
    calls = []

    def worker(application, event):
        entered.set()
        assert event.wait(3)
        finished.set()

    class HTTP:
        server_port = 12345
        control_token = 'isolated-token'
        def serve_forever(self):
            assert entered.wait(3)
        def server_close(self):
            calls.append('closed')

    monkeypatch.setattr(server, 'make_server', lambda *_: HTTP())
    monkeypatch.setattr(maintenance, 'run', worker)
    server.serve(app, 0)
    assert finished.is_set()
    assert calls == ['closed']


def test_incomplete_http_request_cannot_hold_shutdown_forever(app):
    import socket
    http = server.make_server(app, 0, 'test-control')
    assert http.RequestHandlerClass.timeout == 30
    http.RequestHandlerClass.timeout = 0.2  # Same socket timeout path without a 30-second test delay.
    thread = threading.Thread(target=http.serve_forever)
    thread.start()
    client = socket.create_connection(http.server_address, timeout=3)
    try:
        client.sendall(b'POST /api/execute HTTP/1.1\r\nHost: localhost\r\n')
        http.shutdown()
        http.server_close()  # Waits for accepted handlers, including the incomplete request.
        thread.join(3)
        assert not thread.is_alive()
    finally:
        client.close()
        http.shutdown()
        http.server_close()
        thread.join(3)
