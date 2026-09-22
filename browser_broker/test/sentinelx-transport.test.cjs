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
