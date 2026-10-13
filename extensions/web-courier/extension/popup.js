const $ = id => document.getElementById(id);
const CONNECTION = 'awWebCourierConnectionV1', ATTEMPT = 'awWebCourierAttemptV1';
let current = null, running = false;
const phases = {fetched:'原通知已保存，尚未填入',prepared:'原通知已填入，尚未发送',submitting:'发送结果待核对；不会重试',observed:'已在网页看到完整用户消息',reload_verified:'刷新后仍看到完整用户消息'};
const states = {wrong_target:'不是登记的会话',unknown:'网页状态不明，禁止发送',busy:'会话正在运行，暂不发送',idle_candidate:'未发现忙碌信号'};
const publicConnection = config => config && Object.fromEntries(Object.entries(config).filter(([key]) => key !== 'token'));
$('extension-id').textContent = chrome.runtime.id;

function controls() {
  const probe = current?.probe, record = current?.record, connected = !!current?.connection;
  $('configuration').hidden = connected;
  $('configure').hidden = connected;
  $('configure').disabled = running || connected;
  $('get').disabled = running || !connected || !!record;
  $('get').textContent = record ? '原通知已保存（请继续）' : '获取一条原通知';
  $('inspect').disabled = running || !connected;
  $('prepare').disabled = running || record?.phase !== 'fetched' || probe?.state !== 'idle_candidate' || probe.hasDraft;
  $('send').disabled = running || !$('confirm').checked || record?.phase !== 'prepared' || current?.aw?.eligible !== true || probe?.state !== 'idle_candidate' || !probe.draftMatches || !!current?.aw?.ack;
}

function show(result) {
  current = {
    ...current, ...result,
    error: result.ok === false ? result.error : null,
    connection: publicConnection(result.connection === undefined ? current?.connection : result.connection),
    record: result.record === undefined ? current?.record : result.record,
    aw: result.aw ?? null, probe: result.probe ?? null,
  };
  const connection = current.connection, record = current.record;
  $('details').textContent = JSON.stringify(current,null,2);
  $('target').textContent = connection
    ? connection.workspace + ' / ' + connection.agent_id + '\n' + connection.target_url + '\nBinding: ' + connection.binding
    : '尚未配置目标';
  $('body').textContent = record?.body || '尚未获取';
  $('ack').textContent = current.aw?.ack ? 'AW 实际 ACK：' + current.aw.ack.message_id : '尚未取得 AW ACK。网页发送事实不代表确认收件。';
  $('status').textContent = [current.ok === false && current.error, record?.message_id && '原消息：' + record.message_id,
    states[current.probe?.state], phases[record?.phase], record?.note, current.aw?.state,
    record && !current.probe && '原通知仍在本机；检查页面后继续原记录。'].filter(Boolean).join('\n')
    || (connection ? '受限连接已保存；可以获取原通知。' : '切到登记的 ChatGPT 会话后，手动获取原通知。');
  controls();
}

async function run(command) {
  if (running) return;
  running = true; controls(); $('status').textContent = '正在核对…';
  try {
    const [tab] = await chrome.tabs.query({active:true,currentWindow:true});
    const args = {command,tabId:tab?.id,confirm:command === 'send' && $('confirm').checked};
    if (command === 'configure') args.connection = JSON.parse($('configuration').value);
    const result = await chrome.runtime.sendMessage(args);
    if (!result || typeof result !== 'object') throw new Error('扩展未返回结果');
    show(result);
    if (result.ok && command === 'configure') $('configuration').value = '';
    if (result.ok && command === 'get' && result.record?.body) $('body').scrollIntoView({block:'nearest'});
  } catch (error) { show({ok:false,error:error.message}); }
  finally { running = false; if (command === 'send') $('confirm').checked = false; controls(); }
}

async function restore() {
  try {
    const saved = await chrome.storage.local.get([CONNECTION, ATTEMPT]);
    const connection = publicConnection(saved[CONNECTION]), record = saved[ATTEMPT] || null;
    if (connection || record) {
      show({ok:true,connection,record});
      if (record?.body) $('body').scrollIntoView({block:'nearest'});
      if (connection && record) await run('inspect');
    }
  } catch (error) { show({ok:false,error:'无法读取已保存的原记录：'+error.message}); }
}

for (const id of ['configure','get','inspect','prepare','send']) $(id).addEventListener('click',()=>run(id));
$('confirm').addEventListener('change',controls);
controls();
restore();
