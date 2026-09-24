'use strict';

const crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');
const { jsonRequest } = require('./http-client');

const ID_RE = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const SHA64 = /^[0-9a-f]{64}$/;
const PROTOCOLS = new Set(['LPCL','AUTHORITY','CURRENTNESS','ASSIGNMENT','HEARTBEAT','EVIDENCE','VALIDATION','RECEIPT','RECOVERY','GITHUB','HUMAN','CONTROL','LIFECYCLE','HISTORY','LINEAGE','TRANSPORT','BROKER','MEDIATOR','THREAD']);
const SENTINELX_TRANSPORT = 'CHATGPT_SENTINELX_MCP';

function inferFleetCardinality(question, fallbackLogical = 76, fallbackMaterial = 32) {
  const text = String(question || '').trim();
  const explicit = text.match(/(?:^|\s)(\d{1,3})\s*(?:\/|x|×|:)\s*(\d{1,4})(?=\s|$|[.,;!?])/i);
  if (!explicit) return { logical_count: fallbackLogical, material_target: fallbackMaterial, source: 'DEFAULT' };
  const logical = Number(explicit[1]); const material = Number(explicit[2]);
  if (!Number.isInteger(logical) || logical < 1 || logical > 512 || !Number.isInteger(material) || material < 0 || material > 4096) throw new Error('fleet cardinality');
  return { logical_count: logical, material_target: material, source: 'EXPLICIT_N_M' };
}

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
  saasRequest({ threadId, question, missionId = null }) {
    const body = {
      scope_type: 'THREAD', thread_id: threadId, question,
      authority_effect: 'NONE', transport: SENTINELX_TRANSPORT,
    };
    if (missionId) body.mission_id = missionId;
    return this.post('/api/v3/saas-broker/requests', body);
  }

  async autoMission({ threadId, question, logicalCount = null, materialTarget = null }) {
    const clean = String(question || '').trim().replace(/\s+/g, ' ');
    if (!clean || clean.length > 4000) throw new Error('auto mission objective');
    const inferred = inferFleetCardinality(clean);
    logicalCount = logicalCount == null ? inferred.logical_count : Number(logicalCount);
    materialTarget = materialTarget == null ? inferred.material_target : Number(materialTarget);
    if (!Number.isInteger(logicalCount) || logicalCount < 1 || logicalCount > 512 || !Number.isInteger(materialTarget) || materialTarget < 0 || materialTarget > 4096) throw new Error('fleet cardinality');
    const key = crypto.createHash('sha256').update(String(threadId) + '\0' + clean, 'utf8').digest('hex').slice(0, 24).toUpperCase();
    const missionId = 'LION-AUTO-' + key;
    const title = ('AUTO · ' + clean).slice(0, 180);
    const lines = [
      'PROJECT=LION_EVOLUSION',
      'MODE=AUTONOMOUS_EXECUTE',
      'CONTROL_LANGUAGE=LPCL/1.2',
      'MISSION_ID=' + missionId,
      'MISSION_TITLE=' + title,
      'MISSION_OBJECTIVE=' + clean,
      'MISSION_DESCRIPTION=Autonomous mission created from the LION panel composer. Phase 1 performs bounded cognitive and currentness analysis before any effectful successor phase.',
      'LOGICAL_DRONE_COUNT=' + logicalCount,
      'MATERIAL_DRONE_COUNT=' + materialTarget,
      'MATERIAL_RUNTIME=DOCKER_LOCAL_MODEL',
      'LOGICAL_ROLE_PREFIX=AUTONOMOUS',
      'PROTOCOLS=LPCL,AUTHORITY,CURRENTNESS,ASSIGNMENT,HEARTBEAT,EVIDENCE,VALIDATION,RECEIPT,RECOVERY,CONTROL,TRANSPORT,BROKER,THREAD',
      'PHASE_01=AUTO_GOAL_ANALYSIS|Autonomous goal analysis',
      'PHASE_01_EXECUTION_CLASS=OBSERVE',
      'PHASE_01_CAPABILITY_CLASS=CONTROL_PLANE_RECONNAISSANCE',
      'PHASE_01_EFFECT_CEILING=NONE',
      'PHASE_01_BINDING_MODE=DYNAMIC',
      'PHASE_01_ON_MISSING_CAPABILITY=WAIT',
      'PHASE_01_AUTO_RESUME=TRUE',
      'PHASE_01_VERIFY_BEFORE_MUTATE=TRUE',
      'PHASE_01_CURRENTNESS=LIVE_8766_PACKAGE,LIVE_8780_RUNTIME,CURRENT_BROKER_DB',
      'PHASE_01_EVIDENCE=TRANSPORT_CLASSIFICATION,FIELD_BY_FIELD_PROJECTION_COMPARISON',
      'PHASE_01_COMPLETION_01=BROKER_TRANSPORT_TRUTHFUL=PASS',
    ];
    const lpcl = lines.join('\n') + '\n';
    const validated = await this.validateLpcl(lpcl);
    const registered = await this.registerLpcl(lpcl);
    const activated = await this.activateLpcl(missionId, validated.lpcl_digest);
    let saas = null;
    if (!registered.idempotent) {
      saas = await this.saasRequest({
        threadId,
        missionId,
        question: 'LION autonomous mission ' + missionId + '. User objective: ' + clean + '. Analyze the objective as the SaaS cognitive supervisor. Do not claim material effects; return a bounded advisory for the mission ledger.',
      });
    }
    return {
      route: 'AUTO_MISSION',
      mission_id: missionId,
      lpcl_digest: validated.lpcl_digest,
      logical_count: logicalCount,
      material_target: materialTarget,
      registered,
      activated,
      saas,
      authority_effect: 'EXPLICIT_USER_ACTIVATION',
    };
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

module.exports = { MissionControlAdapter, parsePairs, inferFleetCardinality, SENTINELX_TRANSPORT };
