import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
import crypto from 'node:crypto';
import * as core from '../extension/core.mjs';
const source=fs.readFileSync(new URL('../extension/worker.js',import.meta.url),'utf8').replace(/^import .*\n/,'');
const ID='a'.repeat(32), TARGET='https://chatgpt.com/c/11111111-1111-4111-8111-111111111111';
const C='awWebCourierConnectionV1', R='awWebCourierAttemptV1';
const config={backend_url:'http://127.0.0.1:8765',connection_id:'courier-test',workspace:'test',agent_id:'receiver',binding:'binding-test',target_url:TARGET,extension_id:ID,token:'t'.repeat(43)};
const prompt='原始通知\n{\n "id": "original",\n "content": "line1\\nline2",\n "future": {"x": true}\n}\n';
function harness(options={},store={[C]:structuredClone(config)}) {
  let listener, pageCalls=[], requests=[], trusted=false;
  const backend=options.backend||{attempt:null};
  const chrome={storage:{local:{setAccessLevel:async spec=>{assert.equal(spec.accessLevel,'TRUSTED_CONTEXTS');trusted=true;},get:async()=>structuredClone(store),set:async value=>{
    if(options.failStorage && value[R]?.phase==='submitting')throw new Error('storage failed');
    Object.assign(store,structuredClone(value));
  }}},tabs:{get:async()=>({url:options.url||TARGET})},scripting:{executeScript:async spec=>{
    if(spec.files)return [];
    const args=spec.args[0];pageCalls.push(structuredClone(args));
    assert.equal(args.targetUrl,TARGET);assert.equal(args.token,undefined);
    if(args.command==='send' && options.failSend)throw new Error('page response lost');
    return [{result:{target:true,state:'idle_candidate',hasDraft:false,draftMatches:true,receipt:args.command==='send',pageEpoch:100,...options.probe}}];
  }},runtime:{id:ID,getURL:p=>'chrome-extension://'+ID+'/'+p,onMessage:{addListener:f=>{listener=f}}}};
  async function fetch(url,request) {
    assert.equal(url,config.backend_url+'/api/web-courier/'+config.connection_id);
    assert.equal(request.headers.Authorization,'Bearer '+config.token);
    assert.equal(request.redirect,'error');
    const args=JSON.parse(request.body);requests.push(args);
    let result;
    if(args.action==='get')result={state:options.delivery==='insert'?'delivery_unsupported':'ready',message_id:'original',prompt,notification:{message_id:'original',workspace:'test',agent:'receiver',binding:'binding-test',delivery:'normal'}};
    if(args.action==='status')result={eligible:options.stale!==true,ack:options.ack||null,attempt:backend.attempt};
    if(args.action==='begin') {
      assert.equal(store[R].phase,'submitting');assert.ok(trusted);
      backend.attempt={attempt_id:args.attempt_id,message_id:args.message_id};
      if(options.failBegin)throw new Error('begin response lost');
      result={state:'claimed',attempt_id:args.attempt_id};
    }
    if(args.action==='report')result={eligible:true,ack:options.ack||null,attempt:backend.attempt,web_fact:args.web_fact};
    return {ok:true,json:async()=>({ok:true,result})};
  }
  vm.runInContext(source,vm.createContext({...core,chrome,crypto,fetch}));
  return {store,pageCalls,requests,backend,call:(command,extra={})=>new Promise(resolve=>listener({command,tabId:1,...extra},{id:ID,url:chrome.runtime.getURL('popup.html')},resolve)),external:()=>listener({command:'send',tabId:1,confirm:true},{id:'other',url:'https://evil.test'},()=>{throw new Error('should not respond')})};
}
async function prepare(h){assert.ok((await h.call('get')).ok);assert.ok((await h.call('prepare')).ok);}
test('original multiline prompt preserved, one claim and one click, no invented ACK',async()=>{const h=harness();await prepare(h);assert.equal(h.store[R].body,prompt);const result=await h.call('send',{confirm:true});assert.ok(result.ok);assert.equal(result.record.phase,'observed');assert.equal(result.aw.ack,null);assert.equal(h.pageCalls.find(p=>p.command==='prepare').body,prompt);assert.equal((await h.call('send',{confirm:true})).ok,false);assert.equal(h.requests.filter(r=>r.action==='begin').length,1);assert.equal(h.pageCalls.filter(p=>p.command==='send').length,1);});
test('explicit confirmation required',async()=>{const h=harness();await prepare(h);assert.equal((await h.call('send')).ok,false);assert.equal(h.requests.some(r=>r.action==='begin'),false);});
test('different tab cannot send prepared draft',async()=>{const h=harness();await prepare(h);assert.equal((await h.call('send',{confirm:true,tabId:2})).ok,false);assert.equal(h.pageCalls.some(p=>p.command==='send'),false);});
for(const key of ['failBegin','failSend'])test('lost '+key+' survives worker restart without second claim or click',async()=>{const h=harness({[key]:true});await prepare(h);assert.equal((await h.call('send',{confirm:true})).ok,false);assert.equal(h.store[R].phase,'submitting');const next=harness({backend:h.backend},h.store);assert.equal((await next.call('send',{confirm:true})).ok,false);assert.equal(next.requests.some(r=>r.action==='begin'),false);assert.equal(next.pageCalls.some(p=>p.command==='send'),false);assert.equal((await next.call('prepare')).ok,false);assert.equal((await next.call('get')).ok,false);});
test('storage failure stops before backend claim',async()=>{const h=harness({failStorage:true});await prepare(h);assert.equal((await h.call('send',{confirm:true})).ok,false);assert.equal(h.requests.some(r=>r.action==='begin'),false);assert.equal(h.pageCalls.some(p=>p.command==='send'),false);});
test('wrong URL rejected before injection or backend get',async()=>{const h=harness({url:'https://chatgpt.com/c/other'});assert.equal((await h.call('get')).ok,false);assert.deepEqual(h.pageCalls,[]);assert.deepEqual(h.requests,[]);});
test('navigation during injection rejects before backend get',async()=>{const h=harness({probe:{target:false}});assert.equal((await h.call('get')).ok,false);assert.deepEqual(h.requests,[]);});
test('external sender ignored',()=>assert.equal(harness().external(),false));
test('busy final guard preserves prepared record',async()=>{const store={[C]:config,[R]:{phase:'prepared',tabId:1,body:prompt}};const h=harness({probe:{state:'busy'}},store);assert.equal((await h.call('send',{confirm:true})).ok,false);assert.equal(store[R].phase,'prepared');assert.equal(h.requests.some(r=>r.action==='begin'),false);});
test('stale binding blocks prepare and send',async()=>{const h=harness({stale:true});assert.ok((await h.call('get')).ok);assert.equal((await h.call('prepare')).ok,false);assert.equal(h.pageCalls.some(p=>p.command==='prepare'),false);});
test('insert unsupported stays unchanged and creates no extension record',async()=>{const h=harness({delivery:'insert'});const r=await h.call('get');assert.equal(r.aw.state,'delivery_unsupported');assert.equal(h.store[R],undefined);});
test('existing legacy record preserved and cannot be replaced through pairing',async()=>{const store={awSingleTestV1:{phase:'submitting',body:'old'}};const h=harness({},store);assert.equal((await h.call('configure',{connection:config})).ok,false);assert.equal(store.awSingleTestV1.phase,'submitting');assert.equal(store[C],undefined);});
test('restricted connection only, no token in response or page',async()=>{const h=harness({},{});const r=await h.call('configure',{connection:config});assert.ok(r.ok);assert.equal(r.connection.token,undefined);assert.equal(h.store[C].token,config.token);});
test('real backend ACK is returned separately from page fact',async()=>{const store={[C]:config,[R]:{phase:'submitting',submitEpoch:99,body:prompt,attempt_id:'attempt-test',message_id:'original'}};const h=harness({ack:{message_id:'original'},backend:{attempt:{attempt_id:'attempt-test'}},probe:{receipt:true,pageEpoch:100}},store);const r=await h.call('inspect');assert.equal(r.record.phase,'reload_verified');assert.equal(r.aw.ack.message_id,'original');assert.equal(h.pageCalls.some(p=>p.command==='send'),false);assert.equal(h.requests.some(r=>r.action==='begin'),false);});
