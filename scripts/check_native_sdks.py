"""Check public SDK types without starting native programs or invoking models."""
import importlib
from importlib import metadata
import inspect
import json
from pathlib import Path

result={}
for name, client_name, option_name, executable in (
    ('claude_agent_sdk','ClaudeSDKClient','ClaudeAgentOptions','cli_path'),
    ('codebuddy_agent_sdk','CodeBuddySDKClient','CodeBuddyAgentOptions','codebuddy_code_path'),
):
    module=importlib.import_module(name)
    client=getattr(module,client_name)
    options=getattr(module,option_name)
    fields=list(inspect.signature(options).parameters)
    methods={n:str(inspect.signature(getattr(client,n))) for n in
             ('connect','query','receive_messages','disconnect','interrupt')}
    assert {'cwd','env','mcp_servers','hooks','can_use_tool','setting_sources',executable}<=set(fields)
    assert {'prompt','session_id'}<=set(inspect.signature(client.query).parameters)
    assert module.PermissionResultDeny(message='denied').behavior=='deny'
    result[name]={'version':metadata.version(name.replace('_','-')),'options':fields,'methods':methods,
                  'models_invoked':False,'native_processes_started':False}
print(json.dumps(result,indent=2))
Path('native-sdk-contract.json').write_text(json.dumps(result,indent=2)+'\n')
