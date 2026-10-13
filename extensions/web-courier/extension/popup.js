const $=id=>document.getElementById(id);
let current=null, running=false;
const phases={planned:'已生成，未填入',prepared:'草稿已填入，未发送',submitting:'发送结果待核实，不会重发',observed:'已看到完整用户消息，待刷新核验',reload_verified:'刷新后仍存在：网页投递已核验'};
const states={wrong_target:'不是指定会话',unknown:'状态不确定，禁止发送',busy:'正在运行，暂不发送',idle_candidate:'未发现忙碌信号（候选空闲）'};
function controls(){
 $('inspect').disabled=running;
 const p=current?.probe,r=current?.record;
 $('prepare').disabled=running||p?.state!=='idle_candidate'||p.hasDraft||!!(r&&r.phase!=='planned');
 $('send').disabled=running||!$('confirm').checked||r?.phase!=='prepared'||p?.state!=='idle_candidate'||!p.draftMatches;
}
async function run(command){
 running=true;controls();$('status').textContent='检查中…';
 try{
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
  const result=await chrome.runtime.sendMessage({command,tabId:tab?.id,confirm:command==='send'&&$('confirm').checked});
  current=result;
  $('details').textContent=JSON.stringify(result,null,2);
  if(result.record)$('body').textContent=result.record.body;
  if(!result.ok)throw new Error(result.error||'未返回结果');
  const r=result.record,p=result.probe;
  $('status').textContent=[states[p?.state]||'未识别',p?.hasDraft?'输入框有草稿':'输入框无草稿',r?phases[r.phase]:'尚无测试记录',r?.note||''].filter(Boolean).join('\n');
 }catch(e){$('status').textContent=e.message;}
 finally{running=false;if(command==='send')$('confirm').checked=false;controls();}
}
for(const id of ['inspect','prepare','send'])$(id).addEventListener('click',()=>run(id));
$('confirm').addEventListener('change',controls);
