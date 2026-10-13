export const TARGET = 'https://chatgpt.com/c/11111111-1111-4111-8111-111111111111';
export function isTarget(raw) {
  try { const u = new URL(raw); return u.origin + u.pathname.replace(/\/$/, '') === TARGET && !u.username && !u.password; }
  catch { return false; }
}
export function testText(id) {
  if (!/^AW-EXT-[a-f0-9-]{36}$/.test(id)) throw new Error('无效测试编号');
  return `网页扩展投递测试，编号 ${id}。请只回复：已收到 ${id}。不要继续研究或调用工具。`;
}
export function canPrepare(record) { return !record || record.phase === 'planned'; }
export function canSend(record) { return record?.phase === 'prepared'; }
export function reconcile(record, probe) {
  if (!record || !probe.target) return record;
  if (!probe.receipt) return record;
  if (!record.submitEpoch) return {...record, phase: 'observed', note: '页面已存在相同正文，不再发送'};
  const refreshed = probe.pageEpoch !== record.submitEpoch;
  return {...record, phase: refreshed ? 'reload_verified' : 'observed', note: refreshed ? '重新载入的页面仍含完整用户消息；不是 AW ACK' : '已观察到完整用户消息；请等回复结束后手动刷新核验'};
}
