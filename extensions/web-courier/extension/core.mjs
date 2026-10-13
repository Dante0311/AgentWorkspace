export function canonicalTarget(raw) {
  if (typeof raw !== 'string') throw new Error('需要明确的 ChatGPT 会话地址');
  const url = new URL(raw);
  const path = url.pathname.replace(/\/$/, '');
  if (url.origin !== 'https://chatgpt.com' || url.username || url.password || !/^\/c\/[a-zA-Z0-9_-]{1,256}$/.test(path)) {
    throw new Error('需要 https://chatgpt.com/c/… 会话地址');
  }
  return url.origin + path;
}

export function isTarget(raw, target) {
  try { return canonicalTarget(raw) === canonicalTarget(target); }
  catch { return false; }
}

export function connectionConfig(value, extensionId) {
  if (!value || typeof value !== 'object') throw new Error('请粘贴 AW 创建的受限连接');
  const backend = new URL(value.backend_url);
  if (backend.protocol !== 'http:' || backend.hostname !== '127.0.0.1' || !backend.port || backend.username || backend.password || backend.pathname !== '/' || backend.search || backend.hash) {
    throw new Error('后台必须是明确端口的本机 127.0.0.1 地址');
  }
  if (value.extension_id !== extensionId || !/^[a-p]{32}$/.test(extensionId)) throw new Error('连接登记的扩展 ID 与当前扩展不符');
  for (const key of ['connection_id', 'workspace', 'agent_id', 'binding']) {
    if (typeof value[key] !== 'string' || !/^[a-zA-Z0-9_-]{1,128}$/.test(value[key])) throw new Error('连接缺少有效的 ' + key);
  }
  if (typeof value.token !== 'string' || value.token.length < 32 || !/^[a-zA-Z0-9_-]+$/.test(value.token)) throw new Error('连接缺少受限凭据');
  return {
    backend_url: backend.origin, connection_id: value.connection_id, workspace: value.workspace,
    agent_id: value.agent_id, binding: value.binding, target_url: canonicalTarget(value.target_url),
    extension_id: extensionId, token: value.token,
  };
}

export function canPrepare(record) { return record?.phase === 'fetched'; }
export function canSend(record) { return record?.phase === 'prepared'; }

export function reconcile(record, probe) {
  if (!record || !probe.target || !probe.receipt) return record;
  const refreshed = record.submitEpoch !== undefined && probe.pageEpoch !== record.submitEpoch;
  return {...record, phase: refreshed ? 'reload_verified' : 'observed',
    web_fact: refreshed ? 'reload_verified' : 'observed',
    note: refreshed ? '刷新后仍看到完整用户消息；AW ACK 单独核对' : '看到完整用户消息；AW ACK 单独核对'};
}
