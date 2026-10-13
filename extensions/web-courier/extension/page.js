/* Isolated-world DOM adapter. No cookies, network, app internals or page-world eval. */
(() => {
  if (globalThis.__awCourierProbeV1) return;
  const TARGET = 'https://chatgpt.com/c/11111111-1111-4111-8111-111111111111';
  const visible = e => !!e && e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden' && getComputedStyle(e).display !== 'none';
  const norm = s => (s || '').replace(/\r\n/g, '\n').trim();
  const enabled = e => !!e && !e.disabled && e.getAttribute('aria-disabled') !== 'true';
  const name = e => e.getAttribute('aria-label') || e.textContent.trim();
  const all = s => Array.from(document.querySelectorAll(s));
  function target() { return location.origin + location.pathname.replace(/\/$/, '') === TARGET; }
  function editorList() {
    return all('[data-composer-markdown][contenteditable="true"][role="textbox"], textarea[placeholder], [contenteditable="true"][role="textbox"][aria-label]')
      .filter(e => visible(e) && /^(询问 ChatGPT|Ask ChatGPT|Message ChatGPT)$/i.test(e.getAttribute('aria-label') || e.getAttribute('placeholder') || ''));
  }
  function text(e) { return norm(e?.tagName === 'TEXTAREA' ? e.value : e?.innerText); }
  function buttons(re) { return all('button').filter(e => visible(e) && re.test(name(e))); }
  function receipt(body) {
    return !!body && all('[data-user-message-bubble="true"]').some(e => text(e) === norm(body));
  }
  function inspect(body) {
    if (!target()) return {target:false, state:'wrong_target', pageEpoch:performance.timeOrigin};
    const es = editorList(), e = es.length === 1 ? es[0] : null;
    const composer = e?.closest('[data-composer-body]');
    const attachments = !!composer && Array.from(composer.querySelectorAll('[data-composer-attachments]')).some(x => visible(x) && x.children.length > 0);
    const modal = all('[role="dialog"], [aria-modal="true"]').some(visible);
    const stop = buttons(/^(停止|停止生成|Stop|Stop generating|Stop streaming)$/i).length > 0;
    const signals = all('[role="status"], [aria-live]').filter(visible).map(x => x.textContent || '').join('\n');
    const busy = stop || /ChatGPT 正在回应|ChatGPT is responding|正在生成|正在思考|Thinking|Generating/i.test(signals);
    const users = all('[data-user-message-bubble="true"]');
    const answers = all('[data-markdown-text-style="assistant-message"]');
    const lastU = users.at(-1), lastA = answers.at(-1);
    const assistantAfter = !!lastU && !!lastA && !!(lastU.compareDocumentPosition(lastA) & Node.DOCUMENT_POSITION_FOLLOWING);
    const composerAction = buttons(/^(开始语音|Start voice|Start voice mode|发送|Send|Send message|Send prompt)$/i).some(enabled);
    let state = 'unknown';
    if (busy) state = 'busy';
    else if (e && composer && !attachments && !modal && enabled(e) && assistantAfter && composerAction) state = 'idle_candidate';
    return {target:true, state, attachments, modal, composerRecognized:!!composer, editorCount:es.length, editorEnabled:enabled(e), hasDraft:!!text(e), draftMatches:!!body && text(e) === norm(body), receipt:receipt(body), pageEpoch:performance.timeOrigin, userMessageCount:users.length, assistantAfter, busySignal:busy};
  }
  async function run({command, body}) {
    if (!['inspect','prepare','send'].includes(command)) throw new Error('未知操作');
    if (command === 'inspect') return inspect(body);
    if (typeof body !== 'string' || !/^网页扩展投递测试，编号 (AW-EXT-[a-f0-9-]{36})。请只回复：已收到 \1。不要继续研究或调用工具。$/.test(body)) throw new Error('仅支持固定测试正文');
    let p = inspect(body);
    if (!p.target) throw new Error('不是指定通信测试会话');
    if (p.receipt) return {...p, action:'already_present'};
    if (p.state !== 'idle_candidate') throw new Error('页面忙碌或状态不确定，未操作');
    if (command === 'prepare') {
      if (p.hasDraft) throw new Error('输入框有草稿，未覆盖');
      const e = editorList()[0];
      e.focus();
      // Native editor command, so React/ProseMirror receives normal input events.
      if (e.tagName === 'TEXTAREA') {
        Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(e, body);
        e.dispatchEvent(new Event('input', {bubbles:true}));
      } else if (!document.execCommand('insertText', false, body)) {
        throw new Error('浏览器不支持编辑命令，停止；请检查输入框');
      }
      await new Promise(r => setTimeout(r, 120));
      p = inspect(body);
      if (!p.target || !p.draftMatches) throw new Error('草稿填入未通过核验，请手动检查，不会发送');
      return {...p, action:'prepared'};
    }
    if (!p.draftMatches) throw new Error('草稿与本次测试正文不一致，未发送');
    const send = buttons(/^(发送|Send|Send message|Send prompt)$/i).filter(enabled);
    if (send.length !== 1) throw new Error('无法唯一识别发送按钮，未发送');
    // Final synchronous guard before the single click; no queue/stop/Enter fallback.
    p = inspect(body);
    if (p.state !== 'idle_candidate' || !p.draftMatches || p.receipt) throw new Error('发送前状态改变，未发送');
    const pageEpoch = performance.timeOrigin;
    send[0].click();
    const until = Date.now() + 8000;
    while (Date.now() < until) {
      await new Promise(r => setTimeout(r, 250));
      p = inspect(body);
      if (!p.target) return {target:false, action:'uncertain', pageEpoch};
      if (p.receipt) return {...p, action:'observed'};
    }
    return {...p, action:'uncertain'};
  }
  globalThis.__awCourierProbeV1 = {run};
})();
