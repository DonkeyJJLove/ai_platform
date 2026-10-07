'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { BrowserlessSecureMcpRelay, makeTurn, claimUsable } = require('../src/secure-mcp-relay');

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
