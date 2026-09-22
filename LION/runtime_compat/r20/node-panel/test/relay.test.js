'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { makeTurn, claimUsable } = require('../src/secure-mcp-relay');

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
