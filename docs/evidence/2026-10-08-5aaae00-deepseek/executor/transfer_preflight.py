import hashlib,json
from pathlib import Path
from transfer_record import ROOT,HOME,aw,run,save,now
exe=Path.home()/'AppData/Roaming/npm/node_modules/@tencent/tclaude/node_modules/@tencent/tclaude-win32-x64/tclaude.exe'
config={'kind':'claude','executable':str(exe),'model':'claude-deepseek-v4.1-flash[1m]','effort':'low','provider':{'base_url':'','env_key':''},'allowed_tools':[]}
save('T00-authorized-profile',{'time':now(),'direct_user_selection':'tclaude模型用deepseek吧，你应该可以改？','Lead_exact_profile':config,'same_wheel_sha256':hashlib.sha256((ROOT/'dist/git_native_agent_workspace-0.1.0a1-py3-none-any.whl').read_bytes()).hexdigest(),'native_executable_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'query_count':0,'global_configuration_changed':False,'previous_test_instances_restarted':False})
aw('T01-public-typed-model-rejected','agent.configure-sdk',{'agent_id':'transfer-agent','kind':'claude','model':config['model'],'effort':'low','executable':str(exe)},expected=2)
aw('T02-no-query-sdk-handshake','setup.inspect-sdk',{'kind':'claude','executable':str(exe)})
save('T03-profile-recovery-boundary',{'original_side_effect_executed':False,'old_failure':'Typed SDK profile regex rejects bracketed native catalog model before root/config/write/session','next_public_route':'agent.configure value / agent.transfer target_config','model_changed':False,'service_changed':False,'source_modified':False,'allowlist_widened':False,'config':config})
print('public typed rejection and no-query handshake recorded; no session created',flush=True)
