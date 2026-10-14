'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const root=path.resolve(__dirname,'../..');
const ui=fs.readFileSync(path.join(root,'cyber_lion/app_coordination/local_intelligence_gateway.py'),'utf8');
const main=fs.readFileSync(path.join(root,'browser_broker/src/main.cjs'),'utf8');

function widget(){
 const start=ui.indexOf('function cmcRenderBridge(c){');
 const end=ui.indexOf('\nfunction cmcRenderConversation(c){',start);
 assert.ok(start>=0&&end>start,'canonical bridge renderer must be present');
 const nodes={};
 for(const id of ['cmcBridgeState','cmcExternalThreadRef','cmcOpenSaasThread',
  'cmcRotateBridge','cmcBindExistingSaas','cmcOpenSaasProject']){
  nodes[id]={textContent:'',value:'',disabled:true};
 }
 const context={$:id=>nodes[id]};
 vm.runInNewContext(ui.slice(start,end),context,{timeout:1000});
 return {render:context.cmcRenderBridge,nodes};
}
test('switching from existing bridge to no bridge disables stale open/rotate actions',()=>{
 const {render,nodes}=widget();
 render({state:'UNBOUND',external_bridges:[{
  external_system:'CHATGPT_SAAS',bridge_id:'bridge-old',external_thread_ref:'thread-old',
 }]});
 assert.equal(nodes.cmcOpenSaasThread.disabled,false);
 assert.equal(nodes.cmcRotateBridge.disabled,false);
 assert.equal(nodes.cmcBindExistingSaas.disabled,true);
 render({state:'BOUND',external_bridges:[]});
 assert.equal(nodes.cmcOpenSaasThread.disabled,true);
 assert.equal(nodes.cmcRotateBridge.disabled,true);
 assert.equal(nodes.cmcBindExistingSaas.disabled,false);
 assert.equal(nodes.cmcExternalThreadRef.value,'');
 assert.match(nodes.cmcBridgeState.textContent,/NO BRIDGE/);
});
test('recorded bridge is never labelled a proven current SaaS binding',()=>{
 const {render,nodes}=widget();
 render({state:'BOUND',external_bridges:[{
  external_system:'CHATGPT_SAAS',bridge_id:'bridge-record',external_thread_ref:'record-only',
 }]});
 assert.match(nodes.cmcBridgeState.textContent,/SaaS E2E NOT PROVEN/);
 assert.equal(nodes.cmcExternalThreadRef.value,'record-only');
 assert.equal(nodes.cmcBindExistingSaas.disabled,true);
});
test('frozen canonical successor cannot establish a new manual bridge',()=>{
 const {render,nodes}=widget();
 render({state:'FROZEN',external_bridges:[]});
 assert.equal(nodes.cmcBindExistingSaas.disabled,true);
 assert.equal(nodes.cmcOpenSaasProject.disabled,true);
});
test('UI sends explicit local project/bind intents to original Electron main only',()=>{
 assert.match(ui,/id="cmcOpenSaasProject"/);
 assert.match(ui,/id="cmcBindExistingSaas"/);
 assert.match(ui,/lion-saas:\/\/project\//);
 assert.match(ui,/lion-saas:\/\/bind\//);
 assert.match(main,/if\(v===panel&&u\.protocol==='lion-saas:'/);
 assert.match(main,/canonicalConsumer\?\.bindExistingProjectThread/);
 assert.match(main,/selected\.response===0/);
 const consumer=fs.readFileSync(path.join(root,'browser_broker/src/canonical-conversation-consumer.cjs'),'utf8');
 assert.match(consumer,/creation_mode:'EXPLICIT_NATIVE_OPERATOR_EXISTING_THREAD'/);
 assert.match(main,/u.hostname==='bind'/);
});
