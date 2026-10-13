const $ = id => document.getElementById(id);
let current = null, running = false;
const phases = {fetched:'原通知已保存，尚未填入',prepared:'原通知已填入，尚未发送',submitting:'发送结果待核对；不会重试',observed:'已在网页看到完整用户消息',reload_verified:'刷新后仍看到完整用户消息'};
const states = {wrong_target:'不是登记的会话',unknown:'网页状态不明，禁止发送',busy:'会话正在运行，暂不发送',idle_candidate:'未发现忙碌信号'};
$('extension-id').textContent = chrome.runtime.id;
function controls() {
  for (const id of ['configure','get','inspect']) $(id).disabled = running;
  const probe = current?.probe, record = current?.record;
  $('prepare').disabled = running || record?.phase !== 'fetched' || probe?.state !== 'idle_candidate' || probe.hasDraft;
  $('send').disabled = running || !$('confirm').checked || record?.phase !== 'prepared' || probe?.state !== 'idle_candidate' || !probe.draftMatches || current?.aw?.eligible === false || !!current?.aw?.ack;
}
async function run(command) {
  running = true; controls(); $('status').textContent = '正在核对…';
  try {
    const [tab] = await chrome.tabs.query({active:true,currentWindow:true});
    const args = {command,tabId:tab?.id,confirm:command === 'send' && $('confirm').checked};
    if (command === 'configure') args.connection = JSON.parse($('configuration').value);
    const result = await chrome.runtime.sendMessage(args);
    current = result;
    $('details').textContent = JSON.stringify(result,null,2);
    if (result.record) $('body').textContent = result.record.body;
    if (!result.ok) throw new Error(result.error || '未返回结果');
    if (command === 'configure') $('configuration').value = '';
    if (result.connection) $('target').textContent = `${result.connection.workspace} / ${result.connection.agent_id}\n${result.connection.target_url}\nBinding: ${result.connection.binding}`;
    $('ack').textContent = result.aw?.ack ? `AW 实际 ACK：${result.aw.ack.message_id}` : '尚未取得 AW ACK。网页发送事实不代表确认收件。';
    $('status').textContent = [states[result.probe?.state],phases[result.record?.phase],result.record?.note,result.aw?.state].filter(Boolean).join('\n') || '受限连接已保存';
  } catch (error) { $('status').textContent = error.message; }
  finally { running = false; if (command === 'send') $('confirm').checked = false; controls(); }
}
for (const id of ['configure','get','inspect','prepare','send']) $(id).addEventListener('click',()=>run(id));
$('confirm').addEventListener('change',controls);
controls();
