import datetime
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'reports/evidence'
AW = ROOT / 'app/Scripts/aw.exe'
HOME = ROOT / 'data/home'
WORKSPACE = 'repair-local'

def now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()

def save(name, value):
    with (EVIDENCE / (name + '.json')).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)

def env():
    values = {k:v for k,v in os.environ.items() if not k.startswith(('AW_', 'WECOM_BOT_', 'PIP_')) and k not in ('PYTHONPATH','PYTHONHOME')}
    values.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', PIP_DISABLE_PIP_VERSION_CHECK='1', PIP_NO_CACHE_DIR='1', TEMP=str(ROOT/'temp'), TMP=str(ROOT/'temp'))
    return values

def safe(text):
    text = re.sub(r'(?:sk-|eyJ)[A-Za-z0-9_.-]+', '[REDACTED]', text)
    return re.sub(r'[\w.+-]+@[\w.-]+', '[ACCOUNT]', text)

def run(name, argv, cwd=ROOT, timeout=60, expected=0):
    start = now()
    result = subprocess.run([str(v) for v in argv], cwd=cwd, env=env(), stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    data = {'started_at':start, 'finished_at':now(), 'argv':[str(v) for v in argv], 'cwd':str(cwd), 'exit_code':result.returncode, 'stdout':safe(result.stdout.decode('utf-8',errors='replace')), 'stderr':safe(result.stderr.decode('utf-8',errors='replace'))}
    save(name,data)
    print(name, 'exit', result.returncode, flush=True)
    if expected is not None and result.returncode != expected:
        raise RuntimeError('Unexpected exit: '+name)
    return data

def aw(name, command, arguments=None, expected=0):
    argv=[AW,'--home',HOME,'-w',WORKSPACE,'call',command,'--arguments',json.dumps(arguments or {},ensure_ascii=False)]
    data=run(name,argv,expected=expected)
    return json.loads(data['stdout']) if data['stdout'] else data
