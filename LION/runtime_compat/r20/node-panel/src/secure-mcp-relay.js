'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { jsonRequest } = require('./http-client');
const { readProtectedSecret } = require('./secrets');

const SECURE = 'CHATGPT_SENTINELX_MCP';
const ATTEST = 'OPERATOR_SESSION_PLUS_CONNECTOR_ROUNDTRIP';
const WAITING = new Set(['PENDING','CREATED','QUEUED','WAITING_SUPERVISOR','WAITING_OPERATOR_OVERDUE']);
const FINAL = new Set(['RECONCILED','SUPERSEDED','FAILED','CANCELLED']);

function now() { return new Date().toISOString(); }
function sha(text) { return crypto.createHash('sha256').update(String(text), 'utf8').digest('hex'); }
function claimUsable(claim, brokerState, nowMs = Date.now()) {
  if (!claim || !brokerState || brokerState.status !== 'CLAIMED') return false;
  if (Number(brokerState.claim_generation) !== Number(claim.claim_generation)) return false;
  const expiry = Date.parse(claim.claim_expires_at || brokerState.claim_expires_at || '');
  return !Number.isFinite(expiry) || expiry > nowMs + 1000;
}
function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    if (!argv[i].startsWith('--')) continue;
    const key = argv[i].slice(2); const value = argv[i + 1];
    if (value && !value.startsWith('--')) { out[key] = value; i += 1; } else out[key] = true;
  }
  return out;
}
function readJson(file, fallback = null) { try { return JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, '')); } catch { return fallback; } }
function atomicJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temp = `${file}.tmp`;
  fs.writeFileSync(temp, JSON.stringify(value, null, 2), { encoding: 'utf8', mode: 0o600 });
  fs.renameSync(temp, file);
}

function makeTurn(row) {
  const rid = row.request_id;
  return {
    command_id: `MC-${rid}`,
    session_id: 'CHATGPT-SAAS',
    thread_id: row.thread_id || null,
    parent_event_id: 'saas_request:' + rid,
    input: `LION Mission Control SaaS request.\nAuthority effect: NONE. This is a cognitive request, not permission for external effects.\nBroker request id: ${rid}\nQuestion: ${row.question}\n\nReturn the answer text to the enclosing SentinelX transport. Do not perform external effects from this turn input.`,
    metadata: {
      source: 'LION_MISSION_CONTROL', broker_request_id: rid, parent_event_id: 'saas_request:' + rid, request_code: row.request_code || null,
      scope_type: row.scope_type || null, scope_id: row.scope_id || null, thread_id: row.thread_id || null,
      transport: SECURE, authority_effect: 'NONE', browser_automation: 'DISABLED_BY_POLICY',
    },
  };
}

class BrowserlessSecureMcpRelay {
  constructor(config) {
    this.config = config;
    this.mediatorKey = readProtectedSecret(config.mediatorKeyFile, config.unprotectHelper);
    this.ingressToken = readProtectedSecret(config.ingressTokenFile, config.unprotectHelper);
    this.claims = new Map();
    fs.mkdirSync(config.stateDir, { recursive: true });
    this.importLegacyMap();
  }

  stateFile(rid) { return path.join(this.config.stateDir, `${rid}.json`); }
  statusFile() { return path.join(this.config.stateDir, 'relay-status.json'); }
  save(rec) { atomicJson(this.stateFile(rec.request_id), rec); return rec; }
  loadStates() {
    return fs.readdirSync(this.config.stateDir).filter((name) => /^saas-[A-Za-z0-9._:-]+\.json$/.test(name)).sort().map((name) => readJson(path.join(this.config.stateDir, name))).filter((x) => x && x.request_id);
  }

  importLegacyMap() {
    const map = readJson(this.config.legacyTurnMap, []);
    if (!Array.isArray(map)) return;
    for (const row of map) {
      if (!row || !row.request_id || !row.turn_id || fs.existsSync(this.stateFile(row.request_id))) continue;
      this.save({
        schema: 'lion.node-secure-mcp-relay.state/v1', request_id: row.request_id,
        question_digest: row.question_digest || null, thread_id: row.thread_id || null,
        turn_id: row.turn_id, turn_command_id: row.turn_command_id || row.command_id || `MC-${row.request_id}`,
        state: 'SAAS_ACTIVE_IMPORTED', created_at: row.created_at || now(), last_observed_at: now(),
        browser_automation: 'DISABLED_BY_POLICY', authority_effect: 'NONE', reconciliation_state: 'OPEN',
      });
    }
  }

  broker(pathname, options = {}) {
    return jsonRequest(this.config.broker, pathname, { ...options, headers: { ...(options.headers || {}), ...(options.method === 'POST' ? { 'X-LION-Mediator-Key': this.mediatorKey } : {}) } });
  }
  ingress(pathname, options = {}) {
    return jsonRequest(this.config.ingress, pathname, { ...options, headers: { ...(options.headers || {}), 'X-LION-Token': this.ingressToken } });
  }

  async readiness() {
    let ingressReady = false; let sentinelxReady = false; let sentinelxStatus = null;
    try { const value = await this.ingress('/health', { timeoutMs: 2500 }); ingressReady = value.ok === true; } catch {}
    try {
      sentinelxStatus = readJson(this.config.sentinelxStatusFile, null);
      const age = sentinelxStatus && sentinelxStatus.observed_at ? Date.now() - Date.parse(sentinelxStatus.observed_at) : Infinity;
      sentinelxReady = Boolean(
        sentinelxStatus && sentinelxStatus.state === 'READY' &&
        sentinelxStatus.agent_active === true && sentinelxStatus.helper_ready === true &&
        age >= 0 && age <= 30000
      );
    } catch {}
    let brokerReady = false;
    try { await jsonRequest(this.config.broker, '/api/v3/saas-broker/status', { timeoutMs: 2500 }); brokerReady = true; } catch {}
    return {
      broker_ready: brokerReady,
      turn_ingress_ready: ingressReady,
      mcp_transport_ready: sentinelxReady,
      sentinelx_transport_ready: sentinelxReady,
      durable_turn_dispatch_ready: brokerReady && ingressReady && sentinelxReady,
      model_executor_ready: false,
      autonomous_dispatch_ready: false,
      browser_automation: 'DISABLED_BY_POLICY',
      transport: SECURE,
      sentinelx_hub: 'https://mcp.sentinelx.app',
      openai_tunnel_required: false,
      tunnel_instance: null
    };
  }

  async claimAndCreate(row, existing = null) {
    const rid = row.request_id;
    let claim;
    try {
      claim = await this.broker(`/api/v3/saas-broker/requests/${encodeURIComponent(rid)}/claim`, { method: 'POST', body: {}, timeoutMs: 8000 });
      this.claims.set(rid, claim);
    } catch (error) {
      this.save({
        ...(existing || {}), schema: 'lion.node-secure-mcp-relay.state/v1', request_id: rid,
        question_digest: row.question_digest || existing?.question_digest || null, thread_id: row.thread_id || existing?.thread_id || null,
        state: 'CLAIM_UNKNOWN_RECONCILE_REQUIRED', error_class: error.name, error: String(error.message).slice(0, 400),
        last_observed_at: now(), authority_effect: 'NONE', reconciliation_state: 'RECONCILE_BEFORE_RETRY',
      });
      return null;
    }
    const base = {
      ...(existing || {}), schema: 'lion.node-secure-mcp-relay.state/v1', request_id: rid, request_code: row.request_code || existing?.request_code || null,
      question_digest: row.question_digest || existing?.question_digest || null, scope_type: row.scope_type || existing?.scope_type || null, scope_id: row.scope_id || existing?.scope_id || null,
      thread_id: row.thread_id || existing?.thread_id || null, broker_transport: SECURE, claim_generation: claim.claim_generation,
      claim_expires_at: claim.claim_expires_at || null, created_at: existing?.created_at || now(), last_observed_at: now(),
      state: 'TURN_CREATE_ATTEMPT', response_digest: existing?.response_digest || null, broker_receipt_digest: existing?.broker_receipt_digest || null,
      browser_automation: 'DISABLED_BY_POLICY', authority_effect: 'NONE', reconciliation_state: 'OPEN',
    };
    this.save(base);
    try {
      const created = await this.ingress('/v1/turns', { method: 'POST', body: makeTurn(row), timeoutMs: 10000 });
      const turn = created.turn || {};
      if (!turn.turn_id) throw new Error('turn create missing turn_id');
      return this.save({ ...base, state: 'SAAS_ACTIVE', turn_id: turn.turn_id, turn_command_id: `MC-${rid}`, turn_request_hash: turn.request_hash || null, last_observed_at: now() });
    } catch (error) {
      return this.save({ ...base, state: 'TURN_CREATE_UNKNOWN_RECONCILE_REQUIRED', error_class: error.name, error: String(error.message).slice(0, 400), last_observed_at: now(), reconciliation_state: 'NO_BLIND_RETRY' });
    }
  }

  async claimNew(readiness) {
    if (!readiness.durable_turn_dispatch_ready) return null;
    const pending = await jsonRequest(this.config.broker, '/api/v3/saas-broker/pending', { timeoutMs: 5000 });
    const row = (pending.requests || []).find((r) => r && r.transport === SECURE && WAITING.has(r.status) && !fs.existsSync(this.stateFile(r.request_id)));
    if (!row) return null;
    return this.claimAndCreate(row, null);
  }

  async reconcile(rec) {
    const rid = rec.request_id;
    let brokerState;
    try { brokerState = await jsonRequest(this.config.broker, `/api/v3/saas-broker/requests/${encodeURIComponent(rid)}`, { timeoutMs: 5000 }); }
    catch { return; }
    rec.last_observed_at = now();
    if (['SUPERSEDED','CANCELLED','FAILED','REJECTED'].includes(brokerState.status)) {
      rec.state = ['SUPERSEDED','CANCELLED'].includes(brokerState.status) ? 'SUPERSEDED' : 'FAILED'; rec.reconciliation_state = `BROKER_TERMINAL_${brokerState.status}`; this.save(rec); return;
    }
    if (brokerState.status === 'RESPONDED' && brokerState.receipt_digest) {
      rec.state = 'RECONCILED'; rec.broker_receipt_digest = brokerState.receipt_digest; rec.reconciliation_state = 'BROKER_RECEIPT_BOUND'; this.save(rec); return;
    }
    if (!rec.turn_id) {
      // A lost/expired claim is safe to reacquire only if turn creation was never attempted.
      // Once the create call itself becomes UNKNOWN we fail closed because ingress has no
      // command-id lookup endpoint in the captured contract; blind replay could duplicate a turn.
      if (rec.state === 'CLAIM_UNKNOWN_RECONCILE_REQUIRED' && WAITING.has(brokerState.status)) {
        await this.claimAndCreate(brokerState, rec);
        return;
      }
      if (rec.state === 'TURN_CREATE_ATTEMPT') {
        rec.state = 'TURN_CREATE_UNKNOWN_RECONCILE_REQUIRED';
        rec.reconciliation_state = 'NO_BLIND_RETRY_AFTER_PROCESS_RESTART';
      }
      this.save(rec); return;
    }
    if (rec.state === 'TURN_CREATE_UNKNOWN_RECONCILE_REQUIRED') { this.save(rec); return; }
    let turn;
    try { turn = (await this.ingress(`/v1/turns/${encodeURIComponent(rec.turn_id)}`, { timeoutMs: 5000 })).turn || {}; }
    catch { this.save(rec); return; }
    if (turn.status !== 'COMPLETED') { this.save(rec); return; }
    const answer = turn.response && typeof turn.response === 'object' ? turn.response.text : turn.response;
    if (typeof answer !== 'string' || !answer.trim()) { rec.state = 'FAILED'; rec.error = 'completed turn missing response text'; this.save(rec); return; }
    rec.response_digest = sha(answer);
    let claim = this.claims.get(rid);
    if (claim && !claimUsable(claim, brokerState)) {
      this.claims.delete(rid); claim = null;
    }
    if (!claim) {
      if (brokerState.status === 'CLAIMED') { this.save(rec); return; }
      if (!WAITING.has(brokerState.status)) { this.save(rec); return; }
      try {
        claim = await this.broker(`/api/v3/saas-broker/requests/${encodeURIComponent(rid)}/claim`, { method: 'POST', body: {}, timeoutMs: 8000 });
        this.claims.set(rid, claim); rec.claim_generation = claim.claim_generation; rec.claim_expires_at = claim.claim_expires_at || null;
      } catch { this.save(rec); return; }
    }
    rec.state = 'BROKER_RESPOND_ATTEMPT'; this.save(rec);
    try {
      const result = await this.broker(`/api/v3/saas-broker/requests/${encodeURIComponent(rid)}/respond`, {
        method: 'POST', timeoutMs: 30000,
        body: { response_token: claim.response_token, claim_generation: claim.claim_generation, answer, model_identity: 'ChatGPT SaaS / SentinelX MCP / durable turn completion', transport: SECURE, attestation_class: ATTEST },
      });
      const receipt = result.receipt || {};
      rec.broker_receipt_digest = receipt.receipt_digest || null;
      rec.state = rec.broker_receipt_digest ? 'RECONCILED' : 'BROKER_RESPONDED';
      rec.reconciliation_state = rec.broker_receipt_digest ? 'BROKER_RECEIPT_BOUND' : 'RECEIPT_PENDING';
      this.claims.delete(rid); this.save(rec);
    } catch (error) {
      rec.state = 'BROKER_RESPOND_UNKNOWN_RECONCILE_REQUIRED'; rec.error_class = error.name; rec.error = String(error.message).slice(0, 400); rec.reconciliation_state = 'RECONCILE_BEFORE_RETRY'; this.save(rec);
    }
  }

  async heartbeat(readiness) {
    try {
      await this.broker('/api/v3/saas-broker/mediator/heartbeat', {
        method: 'POST', timeoutMs: 5000, body: {
          mediator_id: 'LION_SENTINELX_MCP_BRIDGE_R1',
          transport: SECURE,
          state: readiness.durable_turn_dispatch_ready ? 'READY' : 'DEGRADED',
          project_title: 'LION_EVOLUSION',
          chat_title: 'MISSION_SCOPED_THREAD',
          browser: 'ChatGPT project + SentinelX connector',
          authority_effect: 'NONE'
        }
      });
    } catch {}
  }

  async once() {
    const readiness = await this.readiness();
    await this.heartbeat(readiness);
    for (const rec of this.loadStates()) if (!FINAL.has(rec.state)) await this.reconcile(rec);
    for (let i = 0; i < 4; i += 1) { const created = await this.claimNew(readiness); if (!created) break; }
    atomicJson(this.statusFile(), { schema: 'lion.node-secure-mcp-relay.status/v1', observed_at: now(), status: readiness.durable_turn_dispatch_ready ? 'READY' : 'DEGRADED', ...readiness, active_request_ids: this.loadStates().filter((x) => !FINAL.has(x.state)).map((x) => x.request_id), authority_effect: 'NONE' });
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const helper = path.resolve(__dirname, '..', 'scripts', 'unprotect_secret.ps1');
  const config = {
    broker: args.broker || 'http://127.0.0.1:8766', ingress: args.ingress || 'http://127.0.0.1:8791',
    mediatorKeyFile: path.resolve(args['mediator-key-file']), ingressTokenFile: path.resolve(args['ingress-token-file']),
    stateDir: path.resolve(args['state-dir']), legacyTurnMap: path.resolve(args['legacy-turn-map']), unprotectHelper: helper,
    sentinelxStatusFile: path.resolve(args['sentinelx-status-file'] || path.join(process.env.LOCALAPPDATA || '.', 'LION', 'sentinelx-bridge', 'status.json')),
    intervalMs: Math.max(250, Number(args['interval-ms'] || 1000)),
  };
  const relay = new BrowserlessSecureMcpRelay(config);
  console.log(JSON.stringify({ event: 'lion.node-secure-mcp-relay.started', pid: process.pid, browser_automation: 'DISABLED_BY_POLICY', model_executor_ready: false, authority_effect: 'NONE' }));
  let stopping = false;
  process.on('SIGTERM', () => { stopping = true; }); process.on('SIGINT', () => { stopping = true; });
  while (!stopping) {
    try { await relay.once(); } catch (error) { atomicJson(relay.statusFile(), { schema: 'lion.node-secure-mcp-relay.status/v1', observed_at: now(), status: 'DEGRADED', error_class: error.name, error: String(error.message).slice(0, 400), browser_automation: 'DISABLED_BY_POLICY', model_executor_ready: false, autonomous_dispatch_ready: false, authority_effect: 'NONE' }); }
    await new Promise((resolve) => setTimeout(resolve, config.intervalMs));
  }
}

if (require.main === module) main().catch((error) => { console.error(error); process.exitCode = 1; });
module.exports = { BrowserlessSecureMcpRelay, makeTurn, parseArgs, claimUsable };
