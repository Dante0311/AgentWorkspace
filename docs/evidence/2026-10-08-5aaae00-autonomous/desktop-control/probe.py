"""Read-only check of the installed Desktop adapter using this caller's real context."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
from datetime import datetime, timezone

from agent_workspace import runtime, rpc

root = Path(__file__).resolve().parent
server = Path(r'<USER_HOME>\.codex\plugins\cache\openai-bundled\codex-app-tools\0.1.5\server.mjs')
node = Path(r'<NODE_HOME>\node.exe')
record = {
    'observed_at': datetime.now(timezone.utc).isoformat(),
    'scope': 'installed Desktop adapter handshake and read-only status of the actual calling chat',
    'agent_workspace_version': importlib.metadata.version('git-native-agent-workspace'),
    'server_version': '0.1.5',
    'server_sha256': hashlib.sha256(server.read_bytes()).hexdigest(),
    'runtime_sha256': hashlib.sha256(Path(runtime.__file__).read_bytes()).hexdigest(),
    'rpc_sha256': hashlib.sha256(Path(rpc.__file__).read_bytes()).hexdigest(),
    'real_pipe_available': bool(os.environ.get('CODEX_APP_TOOLS_PIPE_PATH')),
    'real_caller_available': bool(os.environ.get('CODEX_THREAD_ID')),
    'target_is_actual_caller': True,
    'model_inputs_sent': 0,
    'binding_created': False,
    'workspace_created': False,
    'messages_sent': 0,
    'private_database_accessed': False,
}
adapter = None
try:
    config = {'command': [str(node), str(server)],
              'pipe_path': os.environ['CODEX_APP_TOOLS_PIPE_PATH'],
              'caller_thread': os.environ['CODEX_THREAD_ID']}
    adapter = runtime.Desktop(root, config, os.environ['CODEX_THREAD_ID'])
    record['handshake'] = 'passed'
    catalog = adapter.rpc.request('tools/list')['tools']
    inspected = {'create_thread', 'read_thread', 'send_message_to_thread', 'list_threads',
                 'list_projects', 'create_sidebar_section', 'move_project_to_sidebar_section'}
    record['relevant_tools_exposed'] = sorted(t['name'] for t in catalog if t['name'] in inspected)
    record['platform_status_result'] = adapter.status()
    record['status_read'] = 'passed'
except Exception as exc:
    record['result'] = 'failed'
    record['error_type'] = type(exc).__name__
    # Preserve the private diagnostic locally; do not copy it into shareable evidence.
    (root / 'private-error.txt').write_text(str(exc), encoding='utf-8')
else:
    record['result'] = 'PASS_REAL_READ_ONLY'
finally:
    if adapter is not None:
        adapter.close()
        record['owned_rpc_process_exited'] = adapter.rpc.process.poll() is not None
    record['not_tested'] = ['native chat creation', 'platform Binding', 'notification',
                          'handoff', 'relay', 'idle status', 'native stop']
    (root / 'desktop-control-result.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(record, ensure_ascii=False))
