import asyncio
import dataclasses
import hashlib
import importlib.metadata
from pathlib import Path
import shutil
from agent_workspace.native_sdk import _codebuddy_client
import codebuddy_agent_sdk as sdk
from record import ROOT, save, now, safe, run

entry=Path.home()/'AppData/Local/Programs/WorkBuddy/resources/app.asar.unpacked/cli/bin/codebuddy'
assert entry.is_file(), 'Use the original selected actual JS entry only'

async def main():
    result={'time':now(),'entry':str(entry),'entry_suffix':entry.suffix,'entry_sha256':hashlib.sha256(entry.read_bytes()).hexdigest(),
            'node':shutil.which('node'),'sdk':importlib.metadata.version('codebuddy-agent-sdk'),
            'model_selected':'hunyuan-2.0-instruct-ioa','query_sent':False,'authentication_files_read':False}
    options=sdk.CodeBuddyAgentOptions(codebuddy_code_path=str(entry),cwd=str(ROOT/'temp'),
        model='hunyuan-2.0-instruct-ioa',setting_sources=[],tools=[],mcp_servers={},allowed_tools=[])
    client=_codebuddy_client(sdk,str(entry))(options)
    messages=[]
    async def receive():
        async for message in client.receive_messages():
            data=dataclasses.asdict(message);messages.append({'native_type':type(message).__name__,'event':data})
    receiver=None
    try:
        async with asyncio.timeout(25):
            await client.connect()
            result['process_connect']='success'
            receiver=asyncio.create_task(receive())
            status=await client.mcp_server_status()
            result.update(control_handshake='success',mcp_status=[dataclasses.asdict(v) for v in status])
    except Exception as exc:
        result.update(control_handshake='failed_or_unconfirmed',error_type=type(exc).__name__,error=safe(str(exc)))
    finally:
        if receiver:
            receiver.cancel();await asyncio.gather(receiver,return_exceptions=True)
        try: await client.disconnect();result['disconnect']='completed'
        except Exception as exc:result['disconnect_error_type']=type(exc).__name__
    result['native_events']=messages
    save('24-workbuddy-real-js-control',result)
    print('Actual WorkBuddy JS SDK control:',result.get('control_handshake'),flush=True)

run('24-node-version',[shutil.which('node'),'--version'])
asyncio.run(main())
