import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';

const source = fs.readFileSync(new URL('../extension/popup.js', import.meta.url), 'utf8');
const CONNECTION = 'awWebCourierConnectionV1', ATTEMPT = 'awWebCourierAttemptV1';
const config = {
  backend_url:'http://127.0.0.1:18765', connection_id:'courier-test', workspace:'test',
  agent_id:'receiver', binding:'binding-test', target_url:'https://chatgpt.com/c/test',
  extension_id:'a'.repeat(32), token:'private-bearer-token',
};
const publicConfig = Object.fromEntries(Object.entries(config).filter(([key]) => key !== 'token'));
const body = '完整原通知\n确认码 WC-20261013-7B61\n第二行';

async function openPopup(store, respond = () => { throw new Error('unexpected worker call'); }) {
  const elements = {};
  for (const id of ['extension-id','configuration','configure','get','inspect','prepare','send',
                    'confirm','details','target','body','ack','status']) {
    elements[id] = {
      textContent:'', value:'', disabled:false, hidden:false, checked:false, scrolls:0, handlers:{},
      addEventListener(event, handler) { this.handlers[event] = handler; },
      scrollIntoView() { this.scrolls++; },
    };
  }
  const calls = [];
  const chrome = {
    runtime:{id:'a'.repeat(32),sendMessage:async args => { calls.push(args); return respond(args,store); }},
    storage:{local:{get:async keys => Object.fromEntries(keys.map(key => [key,structuredClone(store[key])]))}},
    tabs:{query:async () => [{id:1}]},
  };
  vm.runInNewContext(source, vm.createContext({chrome,document:{getElementById:id=>elements[id]}}));
  await new Promise(resolve => setImmediate(resolve));
  return {
    elements, calls,
    click:async id => { await elements[id].handlers.click(); },
    change:id => elements[id].handlers.change(),
  };
}

function inspect(args, store, probe = {state:'idle_candidate',hasDraft:false,draftMatches:false}) {
  assert.equal(args.command, 'inspect');
  return {ok:true,connection:publicConfig,record:store[ATTEMPT],
          aw:{eligible:true,ack:null},probe};
}

test('saved original is visible immediately after reopening and only inspected', async () => {
  const store = {[CONNECTION]:structuredClone(config),
                 [ATTEMPT]:{message_id:'original',phase:'fetched',body}};
  for (let reopening = 0; reopening < 2; reopening++) {
    const popup = await openPopup(store, inspect);
    assert.deepEqual(popup.calls.map(call=>call.command), ['inspect']);
    assert.match(popup.elements.target.textContent,/test \/ receiver/);
    assert.match(popup.elements.target.textContent,/binding-test/);
    assert.equal(popup.elements.body.textContent, body);
    assert.match(popup.elements.status.textContent,/原消息：original/);
    assert.match(popup.elements.status.textContent,/原通知已保存/);
    assert.equal(popup.elements.body.scrolls, 1);
    assert.equal(popup.elements.get.disabled, true);
    assert.equal(popup.elements.prepare.disabled, false);
    assert.equal(popup.elements.send.disabled, true);
    assert.equal(popup.elements.configuration.hidden, true);
    assert.equal(popup.elements.details.textContent.includes(config.token), false);
  }
  assert.equal(store[ATTEMPT].phase, 'fetched');
});

test('first fetch shows the full body and keeps the same record for reopening', async () => {
  const store = {[CONNECTION]:structuredClone(config)};
  const respond = (args, saved) => {
    if (args.command === 'get') {
      saved[ATTEMPT] = {message_id:'original',phase:'fetched',body};
      return {ok:true,connection:publicConfig,record:saved[ATTEMPT],
              aw:{state:'ready'},probe:{state:'idle_candidate',hasDraft:false}};
    }
    return inspect(args,saved);
  };
  const first = await openPopup(store, respond);
  assert.deepEqual(first.calls, []);
  assert.equal(first.elements.get.disabled, false);
  await first.click('get');
  assert.deepEqual(first.calls.map(call=>call.command), ['get']);
  assert.equal(first.elements.body.textContent, body);
  assert.equal(first.elements.body.scrolls, 1);
  assert.equal(first.elements.get.disabled, true);
  assert.equal(first.elements.prepare.disabled, false);
  const reopened = await openPopup(store, respond);
  assert.deepEqual(reopened.calls.map(call=>call.command), ['inspect']);
  assert.equal(reopened.elements.body.textContent, body);
  assert.equal(store[ATTEMPT].body, body);
});

test('prepared draft needs fresh inspection and explicit confirmation after reopening', async () => {
  const store = {[CONNECTION]:structuredClone(config),
                 [ATTEMPT]:{message_id:'original',phase:'prepared',tabId:1,body}};
  const respond = (args,saved) => inspect(args,saved,{state:'idle_candidate',hasDraft:true,draftMatches:true});
  const first = await openPopup(store,respond);
  assert.deepEqual(first.calls.map(call=>call.command), ['inspect']);
  assert.equal(first.elements.send.disabled, true);
  first.elements.confirm.checked = true;
  first.change('confirm');
  assert.equal(first.elements.send.disabled, false);
  const reopened = await openPopup(store,respond);
  assert.equal(reopened.elements.confirm.checked, false);
  assert.equal(reopened.elements.send.disabled, true);
  assert.deepEqual(reopened.calls.map(call=>call.command), ['inspect']);
});

test('unknown send outcome stays visible and cannot trigger another get or send', async () => {
  const store = {[CONNECTION]:structuredClone(config),
                 [ATTEMPT]:{message_id:'original',phase:'submitting',body,note:'发送结果待核对；不会重试'}};
  const popup = await openPopup(store,(args,saved)=>inspect(args,saved));
  assert.deepEqual(popup.calls.map(call=>call.command), ['inspect']);
  assert.match(popup.elements.status.textContent,/不会重试/);
  assert.equal(popup.elements.get.disabled, true);
  assert.equal(popup.elements.prepare.disabled, true);
  popup.elements.confirm.checked = true;
  popup.change('confirm');
  assert.equal(popup.elements.send.disabled, true);
  assert.equal(store[ATTEMPT].phase, 'submitting');
});

test('page inspection failure keeps local target and original body visible', async () => {
  const store = {[CONNECTION]:structuredClone(config),
                 [ATTEMPT]:{message_id:'original',phase:'fetched',body}};
  let wrongTab = true;
  const popup = await openPopup(store,args=>{
    assert.equal(args.command,'inspect');
    return wrongTab ? {ok:false,error:'不是登记的会话',record:store[ATTEMPT]} : inspect(args,store);
  });
  assert.match(popup.elements.target.textContent,/binding-test/);
  assert.equal(popup.elements.body.textContent,body);
  assert.match(popup.elements.status.textContent,/不是登记的会话/);
  assert.equal(popup.elements.prepare.disabled,true);
  assert.equal(popup.elements.send.disabled,true);
  assert.deepEqual(popup.calls.map(call=>call.command),['inspect']);
  wrongTab = false;
  await popup.click('inspect');
  assert.equal(popup.elements.prepare.disabled,false);
  assert.equal(popup.elements.details.textContent.includes('不是登记的会话'),false);
  assert.deepEqual(popup.calls.map(call=>call.command),['inspect','inspect']);
});
