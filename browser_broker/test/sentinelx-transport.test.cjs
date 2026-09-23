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

test('bound thread startup reopens the verified project Chat conversation',()=>{
 const main=fs.readFileSync(path.join(__dirname,'../src/main.cjs'),'utf8');
 assert.match(main,/startupConversation=relay instanceof ThreadConsumer\?relay\.scope\.conversation_url:store\.restoreConversation\(\)/);
 assert.match(main,/saas\.webContents\.loadURL\(startupConversation\)/);
});

test('mission-scoped SaaS admission uses current broker and no R19 prefix gate',()=>{
 const main=fs.readFileSync(path.join(__dirname,'../src/main.cjs'),'utf8');
 assert.doesNotMatch(main,/startsWith\('LION-R19-'\)/);
 assert.match(main,/\/api\/v3\/saas-broker\/requests\//);
 assert.match(main,/execution_preflight\?\.mission_readiness==='READY_BOUND'/);
});


test('right pane defaults to Mission Control and keeps SaaS alive as a sibling tab',()=>{
 const main=fs.readFileSync(path.join(__dirname,'../src/main.cjs'),'utf8');
 assert.match(main,/let activeRightTab='mission'/);
 assert.match(main,/const mission=new WebContentsView/);
 assert.match(main,/const tabs=new WebContentsView/);
 assert.match(main,/views=\[panel,saas,mission,tabs\]/);
 assert.match(main,/saas\.setBounds\(activeRightTab==='saas'\?shown:hidden\)/);
 assert.match(main,/mission\.setBounds\(activeRightTab==='mission'\?shown:hidden\)/);
 assert.match(main,/selectRightTab\('mission'\)/);
 assert.match(main,/mission\.webContents\.loadURL\(MC\)/);
 assert.match(main,/saas\.webContents\.loadURL\(startupConversation\)/);
});

test('Mission Control tab is loopback-origin constrained and tab chrome has no external navigation',()=>{
 const main=fs.readFileSync(path.join(__dirname,'../src/main.cjs'),'utf8');
 assert.match(main,/if\(v===mission\)return u\.origin===new URL\(MC\)\.origin/);
 assert.match(main,/if\(v===tabs\)return u\.protocol==='data:'/);
 assert.match(main,/LION MISSION CONTROL/);
 assert.match(main,/ChatGPT SaaS/);
 assert.match(main,/did-navigate-in-page/);
});

test('switching right tabs changes bounds only and never reloads the SaaS conversation',()=>{
 const main=fs.readFileSync(path.join(__dirname,'../src/main.cjs'),'utf8');
 const match=main.match(/const selectRightTab=name=>\{([^}]+)\}/);
 assert.ok(match);
 assert.doesNotMatch(match[1],/loadURL|reload|close/);
 assert.match(match[1],/layout\(\)/);
});
