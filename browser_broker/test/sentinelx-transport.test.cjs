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


test('Mission Control, Cluster and System share the left surface with distinct tabs',()=>{
 const main=fs.readFileSync(path.join(__dirname,'../src/main.cjs'),'utf8');
 assert.match(main,/let activeLeftTab='mission',activeRightTab='panel'/);
 assert.match(main,/const leftTabs=new WebContentsView/);
 assert.match(main,/const rightTabs=new WebContentsView/);
 assert.match(main,/mission.setBounds\(activeLeftTab==='mission'\?L:HL\)/);
 assert.match(main,/cluster.setBounds\(activeLeftTab==='cluster'\?L:HL\)/);
 assert.match(main,/system.setBounds\(activeLeftTab==='system'\?L:HL\)/);
 assert.match(main,/saas.setBounds\(activeRightTab==='saas'\?R:HR\)/);
 assert.match(main,/local.setBounds\(activeRightTab==='local'\?R:HR\)/);
 assert.match(main,/saas.webContents.loadURL\(startupConversation\)/);
});
test('independent tab bars limit navigation and never reload SaaS on switch',()=>{
 const main=fs.readFileSync(path.join(__dirname,'../src/main.cjs'),'utf8');
 assert.match(main,/if\(v===mission\)return u.origin===new URL\(MC\).origin/);
 assert.match(main,/if\(v===leftTabs\)return u.protocol==='data:'\|\|u.protocol==='lion-left:'/);
 assert.match(main,/if\(v===rightTabs\)return u.protocol==='data:'\|\|u.protocol==='lion-right:'/);
 for(const label of ['mission','cluster','system'])assert(main.includes('lion-left://'+label));
 for(const label of ['panel','saas','local'])assert(main.includes('lion-right://'+label));
 const lines=main.split('\n');
 for(const name of ['selectLeftTab=name=>','selectRightTab=name=>']){
  const at=lines.findIndex(line=>line.includes(name));
  const part=lines.slice(at,at+4).join('\n');
  assert(at>=0);
  assert(!/loadURL\(|reload\(|\.close\(/.test(part));
 }
});
