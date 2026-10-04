"""The actual authenticated HTTP server and maintenance clock, without a Harness."""
import json
import threading
import time
import urllib.request

from agent_workspace import maintenance
from agent_workspace.server import make_server


def test_http_schedule_runs_and_stops_without_a_model(app):
    # make_server is deliberately pure; serve/standalone run own the worker lifecycle.
    server = make_server(app, 0, 'isolated-control-token')
    listener = threading.Thread(target=server.serve_forever, daemon=True)
    stop = threading.Event()
    worker = threading.Thread(target=maintenance.run, args=(app, stop), daemon=True)
    listener.start()
    base = f'http://127.0.0.1:{server.server_port}'

    def call(command, **arguments):
        data = json.dumps({'command': command, 'arguments': {'workspace': 'sea', **arguments}}).encode()
        request = urllib.request.Request(base + '/api/execute', data=data, headers={
            'Authorization': 'Bearer isolated-control-token', 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.load(response)
        assert value['ok'], value
        return value['result']

    try:
        assert call('maintenance.status')['worker_running'] is False
        call('maintenance.schedule', enabled=True, interval=30)
        worker.start()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            state = call('maintenance.status')
            if state['local_run'] and state['local_run'].get('state') == 'checked':
                break
            time.sleep(.05)
        assert state['worker_running'] and state['local_run']['report']['state'] == 'healthy', state
        # Disabling preserves the report and does not trigger catch-up or another model input.
        call('maintenance.schedule', enabled=False)
        assert maintenance.tick(app, 'sea') == {'state': 'disabled'}
        assert call('maintenance.status')['local_run'] == state['local_run']
        assert not app.agents('sea')
    finally:
        stop.set()
        if worker.ident is not None:
            worker.join(30)
        server.shutdown()
        server.server_close()
        listener.join(5)
    assert not worker.is_alive() and not listener.is_alive()
    assert maintenance.status(app, 'sea')['worker_running'] is False
