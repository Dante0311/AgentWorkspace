"""Continue this existing scenario without replaying its old Binding's inputs."""
import argparse
import json
import sys
import threading
from scenario import confined, read, resume, observe, emit

parser = argparse.ArgumentParser()
parser.add_argument('--run-dir', required=True)
args = parser.parse_args()
from pathlib import Path
folder = confined(Path(args.run_dir))
assert read(folder / 'build_operation.json')['status'] == 'failed'
assert not (folder / 'inputs/tile-B.txt').exists()
closed = threading.Event()


def commands():
    for line in sys.stdin:
        item = json.loads(line)
        if item.get('event') == 'send':
            emit({'event': 'send_unknown', 'id': item['id'], 'receipt': 'receive_only_simulation_observer'})
    closed.set()


threading.Thread(target=commands, daemon=True).start()
emit({'event': 'ready'})
while not closed.wait(0.5):
    if read(folder / 'build_operation.json')['status'] == 'failed' and (folder / 'inputs/tile-B.txt').exists():
        resume(folder)
        event = observe(folder)
        if event:
            emit(event)
