import {isTarget, connectionConfig, canPrepare, canSend, reconcile} from './core.mjs';
const CONNECTION = 'awWebCourierConnectionV1';
const ATTEMPT = 'awWebCourierAttemptV1';
const LEGACY = 'awSingleTestV1';
let locked = false;
const storageReady = chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'});
const read = async key => (await chrome.storage.local.get(key))[key] || null;
const save = async (key, value) => { await chrome.storage.local.set({[key]:value}); return value; };
const publicConnection = config => config && Object.fromEntries(Object.entries(config).filter(([key]) => key !== 'token'));

async function request(config, action, args = {}) {
  const response = await fetch(`${config.backend_url}/api/web-courier/${config.connection_id}`, {
    method:'POST', headers:{'Content-Type':'application/json', Authorization:'Bearer '+config.token},
    body:JSON.stringify({action,...args}), credentials:'omit', redirect:'error', cache:'no-store',
  });
  const value = await response.json();
  if (!response.ok || value.ok !== true) throw new Error(value.error || 'AW 后台未返回成功结果');
  return value.result;
}
async function page(config, tabId, command, body) {
  const tab = await chrome.tabs.get(tabId);
  if (!isTarget(tab.url, config.target_url)) throw new Error('当前标签页不是连接登记的会话');
  await chrome.scripting.executeScript({target:{tabId}, files:['page.js']});
  const results = await chrome.scripting.executeScript({target:{tabId},
    func:async args => globalThis.__awCourierProbeV2.run(args),
    args:[{command,body,targetUrl:config.target_url}]});
  if (results.length !== 1 || !results[0].result) throw new Error('页面没有返回唯一结果');
  if (results[0].result.target !== true) throw new Error('页面已经离开登记的会话');
  return results[0].result;
}
const attemptArgs = record => ({message_id:record.message_id, attempt_id:record.attempt_id});
async function report(config, record, probe) {
  return request(config, 'report', {...attemptArgs(record), web_fact:record.web_fact || 'unknown',
    page_epoch:probe?.pageEpoch ?? record.submitEpoch, target_url:config.target_url});
}
async function handle(message) {
  await storageReady;
  const {command,tabId} = message;
  if (!['configure','get','inspect','prepare','send'].includes(command)) throw new Error('非法请求');
  let config = await read(CONNECTION), record = await read(ATTEMPT);
  if (command === 'configure') {
    if (await read(LEGACY)) throw new Error('保留了旧版测试记录；请在独立浏览器资料中验收，不能清除旧记录重发');
    const proposed = connectionConfig(message.connection, chrome.runtime.id);
    if ((config && JSON.stringify(config) !== JSON.stringify(proposed)) || record) throw new Error('已有连接或原尝试；只允许查询，不能覆盖');
    const status = await request(proposed, 'status');
    if (status.eligible !== true) throw new Error('连接已失效或原入口不再可用');
    config = await save(CONNECTION, proposed);
    return {connection:publicConnection(config), aw:status, record};
  }
  if (!config) throw new Error('先在 AW 中创建受限连接并保存配置');
  if (!Number.isInteger(tabId)) throw new Error('没有有效的目标标签页');
  if (command === 'get') {
    if (record) throw new Error('已保存一条原消息；请查询原记录');
    await page(config, tabId, 'inspect');
    const value = await request(config, 'get');
    if (value.state !== 'ready') return {connection:publicConnection(config), aw:value, record:null};
    const n = value.notification;
    if (!n || n.binding !== config.binding || n.agent !== config.agent_id || n.workspace !== config.workspace || n.delivery !== 'normal' || typeof value.prompt !== 'string' || !value.prompt.trim() || value.prompt.length > 2*1024*1024 || value.message_id !== n.message_id) {
      throw new Error('后台返回的原通知与限定连接不符');
    }
    record = await save(ATTEMPT, {message_id:value.message_id, notification:n, body:value.prompt,
      attempt_id:crypto.randomUUID(), phase:'fetched', createdAt:new Date().toISOString()});
    const probe = await page(config, tabId, 'inspect', record.body);
    return {connection:publicConnection(config), aw:value, record, probe};
  }
  const status = await request(config, 'status');
  if (command === 'inspect') {
    const probe = await page(config, tabId, 'inspect', record?.body);
    if (record) {
      record = await save(ATTEMPT, reconcile(record, probe));
      if (status.attempt?.attempt_id === record.attempt_id) await report(config, record, probe);
    }
    return {connection:publicConnection(config), aw:status, record, probe};
  }
  if (status.eligible !== true || status.ack) throw new Error('原入口已失效或已取得真实 ACK；不会发送');
  if (command === 'prepare') {
    if (!canPrepare(record)) throw new Error('没有可准备的原消息；已有尝试不会重新填入');
    const probe = await page(config, tabId, 'prepare', record.body);
    record = await save(ATTEMPT, {...record, phase:probe.receipt?'observed':'prepared',tabId,
      note:probe.receipt?'相同正文已经存在，禁止重发':'完整原通知已填入，尚未发送'});
    return {connection:publicConnection(config), aw:status, record, probe};
  }
  if (!canSend(record) || record.tabId !== tabId || message.confirm !== true) throw new Error('需要在原标签页明确确认；或原消息已经尝试发送');
  const before = await page(config, tabId, 'inspect', record.body);
  if (before.receipt) return {record:await save(ATTEMPT,reconcile(record,before)),probe:before,aw:status};
  if (before.state !== 'idle_candidate' || !before.draftMatches) throw new Error('会话忙碌、状态不明或草稿已变，不会发送');
  // Persist before claiming and clicking. Lost replies and worker restarts only allow inspection.
  record = await save(ATTEMPT, {...record,phase:'submitting',submitEpoch:before.pageEpoch,
    web_fact:'unknown',note:'发送结果待核对；不会重试',attemptedAt:new Date().toISOString()});
  try {
    const claim = await request(config, 'begin', {...attemptArgs(record),binding:config.binding,target_url:config.target_url});
    if (claim.state !== 'claimed' || claim.attempt_id !== record.attempt_id) throw new Error('没有取得本次原尝试的发送许可');
    const probe = await page(config, tabId, 'send', record.body);
    record = await save(ATTEMPT, reconcile(record, probe));
    const aw = await report(config, record, probe);
    return {connection:publicConnection(config), aw, record, probe};
  } catch (error) {
    await save(ATTEMPT, {...record,note:'结果未确认（也可能未点击）：'+error.message+'。只能核对原记录。'});
    throw error;
  }
}
chrome.runtime.onMessage.addListener((message,sender,respond) => {
  if (sender.id !== chrome.runtime.id || sender.url !== chrome.runtime.getURL('popup.html')) return false;
  if (locked) {respond({ok:false,error:'正在处理，请稍后检查'});return false;}
  locked=true;
  (async () => {
    let response;
    try { response={ok:true,...await handle(message)}; }
    catch (error) { response={ok:false,error:error.message,record:await read(ATTEMPT).catch(()=>null)}; }
    finally { locked=false; }
    respond(response);
  })();
  return true;
});
