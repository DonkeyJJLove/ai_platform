'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
// This source slice has no deployed Windows secret/http modules. Isolate
// the original relay functions with non-networking test doubles only.
const Module = require('node:module');
const originalLoad = Module._load;
Module._load = function(request, parent, isMain) {
  if(typeof parent?.filename==='string'&&/[\\/]secure-mcp-relay\.js$/.test(parent.filename)){
    if(request==='./http-client')return {jsonRequest:()=>{throw Error('TEST_NETWORK_DENIED')}};
    if(request==='./secrets')return {readProtectedSecret:()=>{throw Error('TEST_SECRET_DENIED')}};
  }
  return originalLoad.apply(this,arguments);
};
let relayExports;
try {relayExports=require('../src/secure-mcp-relay')} finally{Module._load=originalLoad}
const { BrowserlessSecureMcpRelay, makeTurn, claimUsable } = relayExports;

test('SentinelX relay creates authority-NONE durable turn with causal lineage', () => {
  const rid = 'saas-686efeb1627247548d52ec4a2576f1fa';
  const value = makeTurn({ request_id: rid, question: 'Reply exactly: CANARY', thread_id: 'e75cdf2a60af48b6a68ef55ac18db17e', scope_type: 'THREAD' });
  assert.equal(value.command_id, `MC-${rid}`);
  assert.equal(value.thread_id, 'e75cdf2a60af48b6a68ef55ac18db17e');
  assert.equal(value.parent_event_id, 'saas_request:' + rid);
  assert.equal(value.metadata.parent_event_id, 'saas_request:' + rid);
  assert.equal(value.metadata.authority_effect, 'NONE');
  assert.equal(value.metadata.transport, 'CHATGPT_SENTINELX_MCP');
  assert.equal(value.metadata.browser_automation, 'DISABLED_BY_POLICY');
  assert.match(value.input, /Return the answer text to the enclosing SentinelX transport/);
  assert.doesNotMatch(value.input, /lion_complete_turn|LION-MCP-R2/);
  assert.doesNotMatch(value.input, /Edge|UIA|browser wakeup/i);
});

const fs = require('node:fs');
const path = require('node:path');

test('relay preserves legacy turn identity and fails closed across unknown creation state', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '../src/secure-mcp-relay.js'), 'utf8');
  assert.match(source, /row\.turn_command_id \|\| row\.command_id/);
  assert.match(source, /CLAIM_UNKNOWN_RECONCILE_REQUIRED[\s\S]*WAITING\.has\(brokerState\.status\)/);
  assert.match(source, /TURN_CREATE_UNKNOWN_RECONCILE_REQUIRED/);
  assert.match(source, /NO_BLIND_RETRY_AFTER_PROCESS_RESTART/);
  assert.doesNotMatch(source, /msedge\.exe|edge_session_worker|saas-background-profile-r1/i);
});

test('expired or released cached claim is never reused', () => {
  const future = new Date(Date.now()+60000).toISOString();
  const past = new Date(Date.now()-1000).toISOString();
  const claim={claim_generation:2,claim_expires_at:future};
  assert.equal(claimUsable(claim,{status:'CLAIMED',claim_generation:2,claim_expires_at:future}),true);
  assert.equal(claimUsable(claim,{status:'WAITING_SUPERVISOR',claim_generation:2,claim_expires_at:null}),false);
  assert.equal(claimUsable({...claim,claim_expires_at:past},{status:'CLAIMED',claim_generation:2,claim_expires_at:past}),false);
  assert.equal(claimUsable(claim,{status:'CLAIMED',claim_generation:3,claim_expires_at:future}),false);
});


test('secure MCP relay records canonical attachment dispatch evidence before broker response', () => {
  const source = fs.readFileSync(path.resolve(__dirname, '../src/secure-mcp-relay.js'), 'utf8');
  assert.match(source, /recordCanonicalDispatch\(rec, turn\)/);
  assert.match(source, /\/api\/conversations\/saas\/pending\?limit=128/);
  assert.match(source, /\/api\/conversations\/saas\/dispatch/);
  assert.match(source, /actual_payload_bytes_digest: payloadDigest/);
  assert.match(source, /attachment_payload_bytes_digest: payloadDigest/);
  assert.match(source, /CANONICAL_ATTACHMENT_EVIDENCE_REQUIRED/);
  assert.match(source, /panel: args\.panel \|\| 'http:\/\/127\.0\.0\.1:8780'/);
});


test('recordCanonicalDispatch finalizes attachment evidence from exact completed turn input', async () => {
  const relay = Object.create(BrowserlessSecureMcpRelay.prototype);
  const recorded = [];
  relay.save = value => value;
  relay.panel = async (route, options = {}) => {
    if (route === '/api/conversations/saas/pending?limit=128') return {
      candidates: [{
        request_id: 'saas-1',
        conversation_id: 'conv-1',
        request_message_id: 'msg-1',
        binding_epoch: 1,
        lane_id: 'lane-1',
        shared_context_digest: 'a'.repeat(64),
        projection_digest: 'b'.repeat(64),
        attachment_projections: [{ projection_id: 'ap-1' }],
      }],
    };
    if (route === '/api/conversations/saas/dispatch') {
      recorded.push(options.body);
      return { authority_effect: 'NONE' };
    }
    throw new Error('unexpected route');
  };
  const rec = { request_id: 'saas-1' };
  const turn = { turn_id: 'turn_1', request_hash: 'c'.repeat(64), input: 'exact transport payload\nLION_ATTACHMENT_DATA={"content":"x"}' };
  const out = await relay.recordCanonicalDispatch(rec, turn);
  assert.deepEqual(out, { required: true, recorded: true });
  assert.equal(recorded.length, 1);
  assert.equal(recorded[0].bridge_id, 'sentinelx-mcp');
  assert.equal(recorded[0].external_thread_ref, 'turn_1');
  assert.equal(recorded[0].actual_payload_bytes_digest, recorded[0].attachment_payload_bytes_digest);
  assert.match(recorded[0].actual_payload_bytes_digest, /^[0-9a-f]{64}$/);
  assert.equal(rec.dispatch_evidence_recorded_at !== undefined, true);
});


test('attachment turn fails closed when canonical panel lookup is unavailable', async () => {
  const relay = Object.create(BrowserlessSecureMcpRelay.prototype);
  relay.save = value => value;
  relay.panel = async () => { throw new Error('panel unavailable'); };
  const rec = { request_id: 'saas-2' };
  const turn = { turn_id: 'turn_2', request_hash: 'd'.repeat(64), input: 'USER: x\nLION_ATTACHMENT_DATA={"content":"x"}' };
  const out = await relay.recordCanonicalDispatch(rec, turn);
  assert.deepEqual(out, { required: true, recorded: false });
  assert.equal(rec.dispatch_evidence_error, 'PANEL_PENDING:Error');
});

test('attachment turn fails closed when canonical candidate is missing', async () => {
  const relay = Object.create(BrowserlessSecureMcpRelay.prototype);
  relay.save = value => value;
  relay.panel = async () => ({ candidates: [] });
  const rec = { request_id: 'saas-3' };
  const turn = { turn_id: 'turn_3', request_hash: 'e'.repeat(64), input: 'LION_ATTACHMENT_DATA={"content":"x"}' };
  const out = await relay.recordCanonicalDispatch(rec, turn);
  assert.deepEqual(out, { required: true, recorded: false });
  assert.equal(rec.dispatch_evidence_error, 'CANONICAL_ATTACHMENT_CANDIDATE_REQUIRED');
});

const renewedFixture=()=>{
  const rid='saas-late-response-r11', hash='a'.repeat(64), questionDigest='b'.repeat(64);
  const turn={turn_id:'turn_late_r11',command_id:'MC-'+rid,request_hash:hash,
    status:'COMPLETED',input:'LION Mission Control SaaS request',
    response:{text:'SAAS_R11_LATE_RESPONSE_OK'}};
  const rec={schema:'lion.node-secure-mcp-relay.state/v1',request_id:rid,
    question_digest:questionDigest,turn_id:turn.turn_id,turn_command_id:turn.command_id,
    turn_request_hash:hash,broker_transport:'CHATGPT_SENTINELX_MCP',
    browser_automation:'DISABLED_BY_POLICY',claim_generation:1,
    state:'STALE_TURN_GENERATION',reconciliation_state:'CURRENT_BROKER_CLAIM_REQUIRED'};
  const brokerState={request_id:rid,status:'WAITING_OPERATOR_OVERDUE',claim_generation:1,
    question_digest:questionDigest,authority_effect:'NONE'};
  const relay=Object.create(BrowserlessSecureMcpRelay.prototype);
  relay.claims=new Map();relay.saved=[];
  relay.save=value=>{relay.saved.push(JSON.parse(JSON.stringify(value)));return value};
  relay.ingress=async route=>{assert.equal(route,'/v1/turns/'+turn.turn_id);return {turn}};
  relay.recordCanonicalDispatch=async()=>({required:false,recorded:true});
  const calls=[];
  relay.broker=async(route,options={})=>{
    calls.push([route,options.method||'GET']);
    if(options.method==='POST'&&route.endsWith('/claim')){
      return {request_id:rid,question_digest:questionDigest,claim_generation:2,
        claim_expires_at:new Date(Date.now()+180000).toISOString(),
        response_token:'response-token-2',authority_effect:'NONE'};
    }
    if(options.method==='POST'&&route.endsWith('/respond')){
      assert.equal(options.body.claim_generation,2);
      assert.equal(options.body.answer,'SAAS_R11_LATE_RESPONSE_OK');
      return {receipt:{receipt_digest:'c'.repeat(64)},authority_effect:'NONE'};
    }
    if((options.method||'GET')==='GET')return brokerState;
    throw Error('unexpected broker operation');
  };
  return {relay,rec,turn,brokerState,calls,rid};
};

test('expired transport claim renews only a completed exact ingress turn, without another model send',async()=>{
  const f=renewedFixture();
  await f.relay.reconcile(f.rec);
  assert.equal(f.rec.state,'RECONCILED');
  assert.equal(f.rec.claim_generation,2);
  assert.equal(f.rec.broker_receipt_digest,'c'.repeat(64));
  assert.equal(f.calls.filter(x=>x[1]==='POST'&&x[0].endsWith('/claim')).length,1);
  assert.equal(f.calls.filter(x=>x[1]==='POST'&&x[0].endsWith('/respond')).length,1);
  assert.equal(f.rec.broker_respond_attempted_generation,2);
  assert.equal(f.rec.reclaim_intent_generation,1);
});

test('reclaim requires exact broker digest and claim generation',async()=>{
  for(const mutation of [
    f=>{f.brokerState.question_digest='e'.repeat(64)},
    f=>{f.brokerState.claim_generation=3},
    f=>{f.brokerState.status='CLAIMED'},
  ]){
    const f=renewedFixture();mutation(f);
    await f.relay.reconcile(f.rec);
    assert.equal(f.rec.state,'STALE_TURN_GENERATION');
    assert.equal(f.calls.filter(x=>x[1]==='POST').length,0);
  }
});

test('lost reclaim response never triggers a second blind claim',async()=>{
  const f=renewedFixture(),base=f.relay.broker;
  let count=0;
  f.relay.broker=async(route,options={})=>{
    if(options.method==='POST'&&route.endsWith('/claim')){count++;throw Error('claim outcome unknown')}
    return base(route,options);
  };
  await f.relay.reconcile(f.rec);
  assert.equal(count,1);
  assert.equal(f.rec.state,'RECLAIM_UNKNOWN_RECONCILE_REQUIRED');
  assert.equal(f.rec.reconciliation_state,'NO_BLIND_RECLAIM_RETRY');
  await f.relay.reconcile(f.rec);
  assert.equal(count,1);
  assert.equal(f.rec.reclaim_intent_generation,1);
});

test('unknown prior broker response does not re-claim or re-send',async()=>{
  const f=renewedFixture();
  f.rec.state='BROKER_RESPOND_UNKNOWN_RECONCILE_REQUIRED';
  f.rec.reconciliation_state='RECONCILE_BEFORE_RETRY';
  await f.relay.reconcile(f.rec);
  assert.equal(f.calls.filter(x=>x[1]==='POST').length,0);
  assert.equal(f.rec.reconciliation_state,'RECONCILE_BEFORE_RETRY');
});
