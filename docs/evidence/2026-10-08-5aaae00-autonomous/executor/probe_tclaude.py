import hashlib,importlib.metadata,json
from pathlib import Path
from record import ROOT, run, aw, save, now
exe=Path.home()/'AppData/Roaming/npm/node_modules/@tencent/tclaude/node_modules/@tencent/tclaude-win32-x64/tclaude.exe'
save('20-tclaude-prerequisites',{'time':now(),'native_executable':str(exe),'sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'sdk_version':importlib.metadata.version('claude-agent-sdk'),'dependencies':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},'model_queries':0})
run('21-tclaude-version',[exe,'--version'])
run('22-tclaude-wrapper-help',[exe,'--help'])
run('23-tclaude-upstream-help',[exe,'--','-h'])
aw('24-tclaude-sdk-handshake','setup.inspect-sdk',{'kind':'claude','executable':str(exe)})
print('no-model tclaude preflight complete',flush=True)
