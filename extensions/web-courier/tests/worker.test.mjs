import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
import crypto from 'node:crypto';
import * as core from '../extension/core.mjs';
const source=fs.readFileSync(new URL('../extension/worker.js',import.meta.url),'utf8').replace(/^import .*\n/,'');
function harness(options={},store={}){
 let listener, pageCalls=[], failSend=false;
 const chrome={storage:{local:{get:async()=>structuredClone(store),set:async v=>Object.assign(store,structuredClone(v))}},tabs:{get:async()=>({url:options.url||core.TARGET})},scripting:{executeScript:async spec=>{
  if(spec.files)return [];
  const {command,body}=spec.args[0];pageCalls.push(command);
  if(command==='send'&&(options.failSend||failSend))throw new Error('connection lost');
  const p={target:true,state:'idle_candidate',hasDraft:true,draftMatches:true,receipt:false,pageEpoch:100};
  if(command==='send')p.receipt=true;
  return [{result:{...p,...options.probe}}];
 }},runtime:{id:'local-test',getURL:p=>'chrome-extension://local-test/'+p,onMessage:{addListener:f=>{listener=f}}}};
 const ctx=vm.createContext({...core,chrome,crypto});vm.runInContext(source,ctx);
 return {store,pageCalls,call:(command,extra={})=>new Promise(resolve=>listener({command,tabId:1,...extra},{id:'local-test',url:chrome.runtime.getURL('popup.html')},resolve)),external:()=>listener({command:'send',tabId:1,confirm:true},{id:'other',url:'https://evil.test'},()=>{throw new Error('should not respond')} )};
}
test('full worker flow stores before send, no second send',async()=>{const h=harness();assert.ok((await h.call('prepare')).ok);assert.equal(h.store.awSingleTestV1.phase,'prepared');assert.ok((await h.call('send',{confirm:true})).ok);assert.equal(h.store.awSingleTestV1.phase,'observed');assert.equal((await h.call('send',{confirm:true})).ok,false);assert.equal(h.pageCalls.filter(x=>x==='send').length,1);});
test('explicit confirmation required',async()=>{const h=harness();await h.call('prepare');assert.equal((await h.call('send')).ok,false);assert.equal(h.pageCalls.includes('send'),false);});
test('different tab cannot send prepared draft',async()=>{const h=harness();await h.call('prepare');assert.equal((await h.call('send',{confirm:true,tabId:2})).ok,false);assert.equal(h.pageCalls.includes('send'),false);});
test('lost result survives worker restart and blocks resend',async()=>{const h=harness({failSend:true});await h.call('prepare');assert.equal((await h.call('send',{confirm:true})).ok,false);assert.equal(h.store.awSingleTestV1.phase,'submitting');const h2=harness({},h.store);assert.equal((await h2.call('send',{confirm:true})).ok,false);assert.equal(h2.pageCalls.includes('send'),false);assert.equal((await h2.call('prepare')).ok,false);});
test('wrong URL rejected before injection',async()=>{const h=harness({url:'https://chatgpt.com/c/other'});assert.equal((await h.call('inspect')).ok,false);assert.deepEqual(h.pageCalls,[]);});
test('external sender ignored',()=>assert.equal(harness().external(),false));
test('probe sees receipt after reload and reconciles without sending',async()=>{const store={awSingleTestV1:{phase:'submitting',submitEpoch:99,body:'fixed'}};const h=harness({probe:{receipt:true,pageEpoch:100}},store);const r=await h.call('inspect');assert.equal(r.record.phase,'reload_verified');assert.equal(h.pageCalls.includes('send'),false);});
test('busy before send blocks without commit or click',async()=>{const store={awSingleTestV1:{phase:'prepared',tabId:1,body:'fixed'}};const h=harness({probe:{state:'busy'}},store);assert.equal((await h.call('send',{confirm:true})).ok,false);assert.equal(store.awSingleTestV1.phase,'prepared');assert.equal(h.pageCalls.includes('send'),false);});
