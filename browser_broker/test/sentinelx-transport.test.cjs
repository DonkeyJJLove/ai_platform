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


test('Mission Control stays left while the right pane defaults to LPCL Panel and keeps SaaS alive',()=>{
 const main=fs.readFileSync(path.join(__dirname,'../src/main.cjs'),'utf8');
 assert.match(main,/let activeRightTab='panel'/);
 assert.match(main,/const mission=new WebContentsView/);
 assert.match(main,/const tabs=new WebContentsView/);
 assert.match(main,/views=\[panel,saas,mission,tabs\]/);
 assert.match(main,/mission\.setBounds\(\{x:0,y:0,width:split,height\}\)/);
 assert.match(main,/panel\.setBounds\(activeRightTab==='panel'\?shown:hidden\)/);
 assert.match(main,/saas\.setBounds\(activeRightTab==='saas'\?shown:hidden\)/);
 assert.match(main,/selectRightTab\('panel'\)/);
 assert.match(main,/mission\.webContents\.loadURL\(MC\)/);
 assert.match(main,/panel\.webContents\.loadURL\(PANEL\)/);
 assert.match(main,/saas\.webContents\.loadURL\(startupConversation\)/);
});

test('right tab chrome uses bounded lion-tab navigation and exposes LPCL Panel plus ChatGPT SaaS',()=>{
 const main=fs.readFileSync(path.join(__dirname,'../src/main.cjs'),'utf8');
 assert.match(main,/if\(v===mission\)return u\.origin===new URL\(MC\)\.origin/);
 assert.match(main,/u\.protocol==='lion-tab:'/);
 assert.match(main,/selectRightTab\(u\.hostname\)/);
 assert.match(main,/lion-tab:\/\/panel/);
 assert.match(main,/lion-tab:\/\/saas/);
 assert.match(main,/LPCL PANEL/);
 assert.match(main,/ChatGPT SaaS/);
 assert.doesNotMatch(main,/tabs\.webContents\.on\('did-navigate-in-page'/);
});

test('switching right tabs changes bounds only and never reloads the LPCL or SaaS views',()=>{
 const main=fs.readFileSync(path.join(__dirname,'../src/main.cjs'),'utf8');
 const match=main.match(/selectRightTab=name=>\{([^}]+)\}/);
 assert.ok(match);
 assert.doesNotMatch(match[1],/loadURL|reload|close/);
 assert.match(match[1],/layout\(\)/);
});
