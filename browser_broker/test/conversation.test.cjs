'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {conversation,conversationInfo,boundConversation,conversationReport}=require('../src/conversation.cjs');
const {EmbeddedBrowser}=require('../src/browser.cjs');
const {ThreadConsumer}=require('../src/thread-consumer.cjs');
const {Relay}=require('../src/relay.cjs');
const {TASK}=require('../src/contract.cjs');
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
test('thread and mission consumers require native confirmation before binding an unscoped route',()=>{
 const store={projectUrl:PROJECT,handoffs:()=>[]},scope={mode:'THREAD_CONSUMER',mission_id:null,thread_id:'test-thread',conversation_url:DIRECT,task_sha256:TASK};
 assert.throws(()=>new ThreadConsumer({store,scope}),/PROJECT_CONFIRMATION_REQUIRED/);
 const consumer=new ThreadConsumer({store,scope:{...scope,project_confirmation:confirmation}});assert.equal(consumer.scope.conversation_url,DIRECT);
 const mission={...scope,mission_id:'LION-R19-test'};assert.throws(()=>new Relay({store,scope:mission}),/PROJECT_CONFIRMATION_REQUIRED/);
 assert.equal(new Relay({store,scope:{...mission,project_confirmation:confirmation}}).scope.conversation_url,DIRECT);
});
test('browser send binds exact direct conversation and refuses a navigation before click',async()=>{
 for(const navigate of [false,true]){
  let current=DIRECT,clicks=0;
  const contents={isDestroyed:()=>false,getURL:()=>current,executeJavaScriptInIsolatedWorld:async(world,[{code}])=>{
   assert.equal(world,1001);
   if(code.includes('return {composer:'))return {composer:true,empty:true,busy:false};
   // Exercise the generated URL guard, not a fake implementation of ready().
   const document={querySelector:selector=>selector.includes('send-button')?{disabled:false,click(){clicks++}}:{textContent:code.includes('s.click()')?'fixture prompt':'',focus(){}},execCommand:()=>{if(navigate)current=DIRECT+'-other';return true}};
   return Function('location','document','return '+code)({href:current},document);
  }};
  const browser=new EmbeddedBrowser(contents,PROJECT);
  if(navigate)await assert.rejects(browser.send({conversation_url:DIRECT},'fixture prompt',()=>true),/SEND_UNKNOWN/);
  else await browser.send({conversation_url:DIRECT},'fixture prompt',()=>true);
  assert.equal(clicks,navigate?0:1);
  assert.equal(await browser.ready({conversation_url:DIRECT+'-other'}),navigate);
 }
});
