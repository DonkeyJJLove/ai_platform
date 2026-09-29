'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {prompt}=require('../src/contract.cjs');

test('browser wakeup uses only the SentinelX bounded turn helper',()=>{
 const text=prompt({turn_id:'turn_12345678-abcd',request_id:'saas-1234'});
 assert.match(text,/Use the SentinelX connector only/);
 assert.match(text,/\/usr\/local\/bin\/lion-sentinelx-turn get turn_12345678-abcd/);
 assert.match(text,/\/usr\/local\/bin\/lion-sentinelx-turn complete turn_12345678-abcd chatgpt-saas-sentinelx/);
 assert.doesNotMatch(text,/Call lion_get_turn|Then call lion_complete_turn/);
});

test('thread consumer and relay use SentinelX transport identity',()=>{
 const consumer=fs.readFileSync(path.join(__dirname,'../src/thread-consumer.cjs'),'utf8');
 const relay=fs.readFileSync(path.join(__dirname,'../src/relay.cjs'),'utf8');
 assert.match(consumer,/CHATGPT_SENTINELX_MCP/);
 assert.match(relay,/CHATGPT_SENTINELX_MCP/);
 assert.match(relay,/OPERATOR_SESSION_PLUS_CONNECTOR_ROUNDTRIP/);
});

test('canonical startup opens project landing and exact native thread only through explicit bridge',()=>{
 const main=fs.readFileSync(path.join(__dirname,'../src/main.cjs'),'utf8');
 assert.match(main,/CanonicalConversationSaaSConsumer/);
 assert.match(main,/const startupConversation=PROJECT/);
 assert.match(main,/saas\.webContents\.loadURL\(startupConversation\)/);
 assert.match(main,/openBridgeForConversation\(conversationId\)/);
 assert.match(main,/LEGACY_DELIVERY_RETIRED/);
});

test('canonical SaaS admission uses current broker and canonical conversation queue without R19 prefix gates',()=>{
 const consumer=fs.readFileSync(path.join(__dirname,'../src/canonical-conversation-consumer.cjs'),'utf8');
 assert.doesNotMatch(consumer,/startsWith\('LION-R19-'\)/);
 assert.match(consumer,/\/api\/v3\/saas-broker\/requests\//);
 assert.match(consumer,/\/api\/conversations\/saas\/pending\?limit=128/);
 assert.match(consumer,/CANONICAL_BRIDGE_WINS/);
});


test('Mission Control stays on the left while LPCL Panel and SaaS are persistent right-side siblings',()=>{
 const main=fs.readFileSync(path.join(__dirname,'../src/main.cjs'),'utf8');
 assert.match(main,/let activeRightTab='panel'/);
 assert.match(main,/const mission=new WebContentsView/);
 assert.match(main,/const tabs=new WebContentsView/);
 assert.match(main,/views=\[saas,panel,mission,tabs\]/);
 assert.match(main,/mission\.setBounds\(\{x:0,y:0,width:split,height\}\)/);
 assert.match(main,/panel\.setBounds\(activeRightTab==='panel'\?shown:hidden\)/);
 assert.match(main,/saas\.setBounds\(shown\)/);
 assert.match(main,/selectRightTab\('panel'\)/);
 assert.match(main,/mission\.webContents\.loadURL\(MC\)/);
 assert.match(main,/saas\.webContents\.loadURL\(startupConversation\)/);
});

test('Mission Control left surface is loopback-origin constrained and right tab chrome has no external navigation',()=>{
 const main=fs.readFileSync(path.join(__dirname,'../src/main.cjs'),'utf8');
 assert.match(main,/if\(v===mission\)return u\.origin===new URL\(MC\)\.origin/);
 assert.match(main,/if\(v===tabs\)return u\.protocol==='data:'\|\|u\.protocol==='lion-tab:'/);
 assert.match(main,/lion-tab:\/\/panel/);
 assert.match(main,/lion-tab:\/\/saas/);
 assert.match(main,/LPCL PANEL/);
 assert.match(main,/ChatGPT SaaS/);
});

test('switching right tabs changes bounds only and never reloads the SaaS conversation',()=>{
 const main=fs.readFileSync(path.join(__dirname,'../src/main.cjs'),'utf8');
 const line=main.split('\n').find(x=>x.includes('selectRightTab=name=>'));
 assert.ok(line);
 assert.doesNotMatch(line,/loadURL|reload|close/);
 assert.match(line,/activeRightTab=name==='saas'\?'saas':'panel'/);
 assert.match(line,/layout\(\)/);
});
