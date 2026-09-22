'use strict';

const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const { jsonRequest } = require('./http-client');

const ID_RE = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const SHA64 = /^[0-9a-f]{64}$/;
const PROTOCOLS = new Set(['LPCL','AUTHORITY','CURRENTNESS','ASSIGNMENT','HEARTBEAT','EVIDENCE','VALIDATION','RECEIPT','RECOVERY','GITHUB','HUMAN','CONTROL','LIFECYCLE','HISTORY','LINEAGE','TRANSPORT','BROKER','MEDIATOR','THREAD']);
const SENTINELX_TRANSPORT = 'CHATGPT_SENTINELX_MCP';

function parsePairs(text) {
  const lines = String(text).replaceAll('\r\n', '\n').replaceAll('\r', '\n').split('\n');
  const out = {}; let i = 0;
  while (i < lines.length) {
    const match = lines[i].trim().match(/^([A-Z][A-Z0-9_]*)\s*=\s*(.*)$/);
    if (!match) { i += 1; continue; }
    const key = match[1]; let value = match[2].trim(); i += 1;
    if (!value) {
      const buf = [];
      while (i < lines.length) {
        const row = lines[i].trim();
        if (/^([A-Z][A-Z0-9_]*)\s*=\s*(.*)$/.test(row)) break;
        if (row && !row.startsWith('#')) buf.push(row);
        i += 1;
      }
      value = buf.join(' ').trim();
    }
    out[key] = value;
  }
  return out;
}

class MissionControlAdapter {
  constructor({ baseUrl, repo, gitExe }) {
    this.base = String(baseUrl || 'http://127.0.0.1:8766').replace(/\/$/, '');
    this.repo = repo;
    this.gitExe = gitExe || 'git';
  }
  get(pathname, timeoutMs = 8000) { return jsonRequest(this.base, pathname, { timeoutMs }); }
  post(pathname, body, timeoutMs = 15000, headers = {}) { return jsonRequest(this.base, pathname, { method: 'POST', body, timeoutMs, headers }); }

  recent(view = 'operational') { return this.get(`/api/v3/missions/recent?view=${encodeURIComponent(view)}`); }
  process(missionId) { return this.get(`/api/v3/missions/${encodeURIComponent(missionId)}/process`); }
  missionDeletePreview(missionId) { return this.get(`/api/v3/missions/${encodeURIComponent(missionId)}/delete-preview`); }
  missionDelete(missionId, specDigest) { return this.post(`/api/v3/missions/${encodeURIComponent(missionId)}/delete`, { spec_digest: specDigest }); }
  missionAction(missionId, action, payload = {}) { return this.post(`/api/v3/missions/${encodeURIComponent(missionId)}/actions`, { action, ...payload }, 240000); }
  phaseAction(missionId, value) { return this.post(`/api/v3/missions/${encodeURIComponent(missionId)}/phase-actions`, value); }
  currentAction(value) { return this.post('/api/v3/missions/current/actions', value, 240000); }
  capabilityRegistry() { return this.get('/api/v3/capabilities/process-contracts'); }

  saasStatus() { return this.get('/api/v3/saas-broker/status'); }
  saasRequestStatus(requestId) { return this.get(`/api/v3/saas-broker/requests/${encodeURIComponent(requestId)}`); }
  saasRequest({ threadId, question }) {
    return this.post('/api/v3/saas-broker/requests', {
      scope_type: 'THREAD', thread_id: threadId, question,
      authority_effect: 'NONE', transport: SENTINELX_TRANSPORT,
    });
  }
  saasCancel(requestId) { return this.post('/api/v3/saas/cancel', { request_id: requestId }); }
  dualResult(requestId) { return this.get(`/api/v3/dual/${encodeURIComponent(requestId)}`); }

  _localIdentity() {
    const run = (args) => execFileSync(this.gitExe, ['-C', this.repo, ...args], { encoding: 'utf8', windowsHide: true, timeout: 10000 }).trim();
    return { head: run(['rev-parse', 'HEAD']), tree: run(['rev-parse', 'HEAD^{tree}']) };
  }

  async validateLpcl(source) {
    if (typeof source !== 'string' || source.length < 20 || source.length > 200000) throw new Error('lpcl text');
    const kv = parsePairs(source);
    if (!kv.MISSION_DESCRIPTION && kv.MISSION_OBJECTIVE) kv.MISSION_DESCRIPTION = kv.MISSION_OBJECTIVE;
    if (!kv.LOGICAL_DRONE_COUNT && kv.LOGICAL_DRONES) kv.LOGICAL_DRONE_COUNT = kv.LOGICAL_DRONES;
    if (!kv.MATERIAL_DRONE_COUNT && kv.MATERIAL_FLEET_TARGET) kv.MATERIAL_DRONE_COUNT = kv.MATERIAL_FLEET_TARGET;
    const required = ['PROJECT','MODE','CONTROL_LANGUAGE','MISSION_ID','MISSION_TITLE','MISSION_OBJECTIVE','MISSION_DESCRIPTION','LOGICAL_DRONE_COUNT','MATERIAL_DRONE_COUNT','PROTOCOLS'];
    const missing = required.filter((key) => !kv[key]);
    if (missing.length) throw new Error(`LPCL_MISSING_REQUIRED:${missing.join(',')}`);
    if (kv.PROJECT !== 'LION_EVOLUSION' || kv.MODE !== 'AUTONOMOUS_EXECUTE' || !['LPCL/1.1','LPCL/1.2'].includes(kv.CONTROL_LANGUAGE)) throw new Error('lpcl envelope');
    if (!ID_RE.test(kv.MISSION_ID)) throw new Error('mission_id');
    const logical = Number(kv.LOGICAL_DRONE_COUNT); const material = Number(kv.MATERIAL_DRONE_COUNT);
    if (!Number.isInteger(logical) || logical < 1 || logical > 512 || !Number.isInteger(material) || material < 0 || material > 4096) throw new Error('fleet cardinality');
    const protocols = kv.PROTOCOLS.split(/[,;\s]+/).filter(Boolean);
    if (!protocols.length || protocols.some((p) => !PROTOCOLS.has(p))) throw new Error('protocols');
    const phases = Object.keys(kv).filter((key) => /^PHASE_[0-9]{2}$/.test(key)).sort().map((key) => {
      const raw = kv[key]; const parts = raw.includes('|') ? raw.split('|', 2).map((x) => x.trim()) : [raw.trim(), raw.trim().split('_').map((x) => x[0] ? x[0].toUpperCase() + x.slice(1).toLowerCase() : '').join(' ')];
      if (!ID_RE.test(parts[0]) || !parts[1]) throw new Error(`LPCL_PHASE_INVALID:${key}`);
      return { id: parts[0], title: parts[1].slice(0, 180) };
    });
    if (!phases.length) throw new Error('no phases');
    const identity = this._localIdentity();
    const digest = crypto.createHash('sha256').update(source, 'utf8').digest('hex');
    let registryState = 'UNAVAILABLE_FALLBACK_EMPTY'; let registryDigest = null;
    try {
      const registry = await this.capabilityRegistry(); registryState = 'LIVE_RUNTIME_REGISTRY'; registryDigest = registry.registry_digest || null;
    } catch {}
    const preflight = {
      mission_readiness: 'WAITING_FOR_CAPABILITIES',
      phase_count: phases.length,
      contract_count: phases.length,
      bound_count: 0,
      unbound_count: phases.length,
      invalid_count: 0,
      capability_closure: 'PARTIAL',
      note: 'R17 Node intake performs structural validation; Mission Control performs authoritative phase-contract compilation on registration.',
    };
    const spec = {
      mission_id: kv.MISSION_ID, title: kv.MISSION_TITLE.slice(0, 180), objective: kv.MISSION_OBJECTIVE.slice(0, 4000),
      description: kv.MISSION_DESCRIPTION.slice(0, 8000), lpcl_digest: digest, lpcl_text: source,
      source_head: identity.head, source_tree: identity.tree, logical_count: logical, material_target: material, phases, protocols,
    };
    return { valid: true, lpcl_digest: digest, source_currentness: identity, spec, execution_preflight: preflight, capability_registry_state: registryState, capability_registry_digest: registryDigest, phase_execution_contracts: [], parsed: { run: kv.RUN || null, project: kv.PROJECT, mode: kv.MODE, control_language: kv.CONTROL_LANGUAGE, phase_count: phases.length } };
  }

  async registerLpcl(source) {
    const validated = await this.validateLpcl(source);
    const out = await this.post('/api/v3/missions/register-lpcl', validated.spec, 30000);
    const mission = out && out.mission;
    const backendMid = mission && (mission.mission_id || (mission.process || {}).mission_id);
    const backendDigest = mission && (mission.spec_digest || (mission.process || {}).lpcl_digest);
    if (backendMid !== validated.spec.mission_id || backendDigest !== validated.lpcl_digest) throw new Error('REGISTERED_SOURCE_DRIFT');
    return { ...out, registration_confirmation: { mission_id: backendMid, lpcl_digest: backendDigest, source_length: source.length, authority_effect: 'NONE' } };
  }

  async activateLpcl(missionId, digest) {
    if (!ID_RE.test(missionId) || !SHA64.test(digest)) throw new Error('activation');
    const out = await this.post(`/api/v3/missions/${encodeURIComponent(missionId)}/activate`, { lpcl_digest: digest, activation_event: 'EXPLICIT_UI_ACTIVATION' });
    if (!out || out.mission_id !== missionId) throw new Error('ACTIVATION_SOURCE_DRIFT');
    return { ...out, activation_confirmation: { mission_id: missionId, lpcl_digest: digest, authority_effect: 'EXPLICIT_USER_ACTIVATION' } };
  }
}

module.exports = { MissionControlAdapter, parsePairs, SENTINELX_TRANSPORT };
