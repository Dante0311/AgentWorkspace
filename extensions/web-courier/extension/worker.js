import {isTarget, testText, canPrepare, canSend, reconcile} from './core.mjs';
const KEY = 'awSingleTestV1';
let locked = false;
const read = async () => (await chrome.storage.local.get(KEY))[KEY] || null;
const save = async r => { await chrome.storage.local.set({[KEY]:r}); return r; };
async function page(tabId, command, body) {
  const tab = await chrome.tabs.get(tabId);
  if (!isTarget(tab.url)) throw new Error('请在指定的通信测试网页中点击扩展');
  await chrome.scripting.executeScript({target:{tabId}, files:['page.js']});
  const results = await chrome.scripting.executeScript({target:{tabId}, func:async args => globalThis.__awCourierProbeV1.run(args), args:[{command,body}]});
  if (results.length !== 1 || !results[0].result) throw new Error('页面没有返回唯一结果');
  return results[0].result;
}
async function handle(message) {
  const {command,tabId} = message;
  if (!['inspect','prepare','send'].includes(command) || !Number.isInteger(tabId)) throw new Error('非法请求');
  let r = await read();
  if (command === 'inspect') {
    const probe = await page(tabId,'inspect',r?.body);
    if (r) r = await save(reconcile(r,probe));
    return {record:r,probe};
  }
  if (command === 'prepare') {
    if (!canPrepare(r)) throw new Error('已有测试记录，请检查状态；不会创建重复投递');
    if (!r) { const id='AW-EXT-'+crypto.randomUUID(); r=await save({id,body:testText(id),phase:'planned',createdAt:new Date().toISOString()}); }
    const probe = await page(tabId,'prepare',r.body);
    r=await save({...r,phase:probe.receipt?'observed':'prepared',tabId,note:probe.receipt?'同正文已存在，禁止重发':'草稿已填入，尚未发送'});
    return {record:r,probe};
  }
  if (!canSend(r) || r.tabId !== tabId || message.confirm !== true) throw new Error('需要在原标签页明确确认；或该测试已经尝试发送');
  const before = await page(tabId,'inspect',r.body);
  if (before.receipt) return {record:await save(reconcile(r,before)),probe:before};
  if (before.state !== 'idle_candidate' || !before.draftMatches) throw new Error('会话忙碌、状态不明或草稿已变，不会发送');
  // Commit first. A crash or lost response must never cause an automatic resend.
  r=await save({...r,phase:'submitting',submitEpoch:before.pageEpoch,note:'发送结果待核实；严禁直接重试',attemptedAt:new Date().toISOString()});
  try {
    const probe=await page(tabId,'send',r.body);
    r=await save(reconcile(r,probe));
    return {record:r,probe};
  } catch (e) {
    await save({...r,note:'结果未确认（也可能未点击）：'+e.message+'。请检查会话，勿重发。'});
    throw e;
  }
}
chrome.runtime.onMessage.addListener((message,sender,respond) => {
  // Accept only our popup, never web-page messages or external extensions.
  if (sender.id !== chrome.runtime.id || sender.url !== chrome.runtime.getURL('popup.html')) return false;
  if (locked) {respond({ok:false,error:'正在处理，请稍后检查'});return false;}
  locked=true;
  (async () => {
    let response;
    try { response={ok:true,...await handle(message)}; }
    catch (e) { response={ok:false,error:e.message,record:await read().catch(()=>null)}; }
    finally { locked=false; }
    respond(response);
  })();
  return true;
});
