import hashlib,importlib.metadata,json,zipfile
from pathlib import Path
import agent_workspace,claude_agent_sdk
from transfer_record import ROOT,save,now
def sha(data):return hashlib.sha256(data).hexdigest()
wheel=ROOT/'dist/git_native_agent_workspace-0.1.0a1-py3-none-any.whl'
package=Path(agent_workspace.__file__).parent
with zipfile.ZipFile(wheel) as source:
    matches={name:sha(source.read(name))==sha((package.parent/name).read_bytes()) for name in source.namelist() if name.startswith('agent_workspace/') and name.endswith('.py')}
sdk_root=Path(claude_agent_sdk.__file__).parent
sdk_files={p.relative_to(sdk_root).as_posix():sha(p.read_bytes()) for p in sorted(sdk_root.rglob('*.py'))}
codex=Path.home()/'AppData/Local/OpenAI/Codex/bin/9691020b546a15b2/codex.exe'
tclaude=Path.home()/'AppData/Roaming/npm/node_modules/@tencent/tclaude/node_modules/@tencent/tclaude-win32-x64/tclaude.exe'
save('T42-software-audit',{'time':now(),'wheel_sha256':sha(wheel.read_bytes()),'installed_product_python_matches_wheel':matches,'all_product_python_matches':all(matches.values()),'sdk_version':importlib.metadata.version('claude-agent-sdk'),'sdk_python_hashes':sdk_files,'sdk_aggregate_sha256':sha(json.dumps(sdk_files,sort_keys=True,separators=(',',':')).encode()),'codex_sha256':sha(codex.read_bytes()),'tclaude_sha256':sha(tclaude.read_bytes()),'dependency_versions':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},'auth_or_global_config_read':False})
assert all(matches.values())
print('Installed product Python files match fixed wheel: '+str(len(matches)))
