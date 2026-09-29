'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {conversation,conversationInfo,boundConversation,conversationReport}=require('../src/conversation.cjs');
const {EmbeddedBrowser}=require('../src/browser.cjs');
const PROJECT='https://chatgpt.com/g/g-p-6a91cabd3f208191a37f295819e9f75b-lion-evolusion/project';
const DIRECT='https://chatgpt.com/c/6a123456-1234-1234-1234-123456789abc';
const SCOPED='https://chatgpt.com/g/g-p-6a91cabd3f208191a37f295819e9f75b/c/6a123456-1234-1234-1234-123456789abc';
const confirmation={method:'NATIVE_OPERATOR',project_url:PROJECT,conversation_url:DIRECT};
test('same project stable identity permits a different or absent display slug',()=>{
 for(const url of [SCOPED,SCOPED.replace('/c/','-renamed-project/c/'),SCOPED+'/'])assert.equal(conversation(url,PROJECT),url);
 assert.equal(conversationInfo(SCOPED,PROJECT).project_membership,'URL_PROJECT_ID_MATCH');
 assert.throws(()=>conversation(SCOPED.replace('6a91','6a92'),PROJECT),/PROJECT_ID_MISMATCH/);
});
test('direct conversation is recognized without inventing project membership',()=>{
 assert.equal(conversation(DIRECT,PROJECT),DIRECT);
 assert.equal(conversationInfo(DIRECT,PROJECT).project_membership,'OPERATOR_CONFIRMATION_REQUIRED');
 assert.throws(()=>boundConversation({conversation_url:DIRECT},PROJECT),/PROJECT_CONFIRMATION_REQUIRED/);
 assert.equal(boundConversation({conversation_url:DIRECT,project_confirmation:confirmation},PROJECT),DIRECT);
 for(const patch of [{method:'WEB_PAGE'},{project_url:PROJECT.replace('6a91','6a92')},{conversation_url:DIRECT+'-other'}])assert.throws(()=>boundConversation({conversation_url:DIRECT,project_confirmation:{...confirmation,...patch}},PROJECT),/PROJECT_CONFIRMATION_REQUIRED/);
});
test('landing page, auth page, other origin and decorated addresses have explicit rejections',()=>{
 assert.throws(()=>conversation(PROJECT,PROJECT),/PROJECT_LANDING_PAGE/);
 assert.throws(()=>conversation(DIRECT+'?token=secret',PROJECT),/CONVERSATION_PARAMETERS_UNSUPPORTED/);
 assert.throws(()=>conversation(DIRECT+'#secret',PROJECT),/CONVERSATION_PARAMETERS_UNSUPPORTED/);
 for(const url of [DIRECT.replace('https:','http:'),DIRECT.replace('chatgpt.com','chatgpt.com.evil.test'),'https://user:secret@chatgpt.com/c/test','https://auth.openai.com/?code=secret','https://chatgpt.com/c/test/extra'])assert.throws(()=>conversation(url,PROJECT));
});
test('diagnostic retains the routing error but never query, fragment or auth credentials',()=>{
 const report=conversationReport(DIRECT+'?token=secret-value#secret-fragment',PROJECT);
 assert.equal(report.address,DIRECT);assert.equal(report.has_query,true);assert.equal(report.has_fragment,true);assert.equal(report.error,'CONVERSATION_PARAMETERS_UNSUPPORTED');
 assert.ok(!JSON.stringify(report).includes('secret'));
 for(const url of ['https://auth.openai.com/?code=secret','https://user:secret@chatgpt.com/c/test'])assert.ok(!JSON.stringify(conversationReport(url,PROJECT)).includes('secret'));
});
test('legacy thread and mission consumers are retired from Electron startup in favor of canonical conversations',()=>{
 const main=fs.readFileSync(path.join(__dirname,'../src/main.cjs'),'utf8');
 assert.match(main,/CanonicalConversationSaaSConsumer/);
 assert.match(main,/LEGACY_DELIVERY_RETIRED/);
 assert.match(main,/external_saas_semantics:'EXPLICIT_BRIDGE_ONLY'/);
 assert.doesNotMatch(main,/new ThreadConsumer\(/);
 assert.doesNotMatch(main,/new Relay\(/);
});
test('browser send binds exact direct conversation and refuses a navigation before click',async()=>{
 const PriorInputEvent=global.InputEvent,PriorEvent=global.Event;
 global.InputEvent=class InputEvent{constructor(type,init={}){this.type=type;Object.assign(this,init)}};
 global.Event=class Event{constructor(type,init={}){this.type=type;Object.assign(this,init)}};
 try{
  for(const navigate of [false,true]){
   let current=DIRECT,clicks=0;
   const contents={isDestroyed:()=>false,getURL:()=>current,executeJavaScriptInIsolatedWorld:async(world,[{code}])=>{
    assert.equal(world,1001);
    if(code.includes('return {composer:'))return {composer:true,empty:true,busy:false};
    // Exercise the generated URL guard, not a fake implementation of ready().
    const sendButton={disabled:false,click(){clicks++}};
    const prompt={textContent:code.includes('s.click()')?'fixture prompt':'',focus(){},dispatchEvent(){},closest(){return {querySelector:()=>sendButton}}};
    const document={querySelector:selector=>selector.includes('send-button')?sendButton:prompt,execCommand:()=>{if(navigate)current=DIRECT+'-other';return true}};
    return Function('location','document','return '+code)({href:current},document);
   }};
   const browser=new EmbeddedBrowser(contents,PROJECT);
   if(navigate)await assert.rejects(browser.send({conversation_url:DIRECT},'fixture prompt',()=>true),/SEND_UNKNOWN/);
   else await browser.send({conversation_url:DIRECT},'fixture prompt',()=>true);
   assert.equal(clicks,navigate?0:1);
   assert.equal(await browser.ready({conversation_url:DIRECT+'-other'}),navigate);
  }
 }finally{
  if(PriorInputEvent===undefined)delete global.InputEvent;else global.InputEvent=PriorInputEvent;
  if(PriorEvent===undefined)delete global.Event;else global.Event=PriorEvent;
 }
});
