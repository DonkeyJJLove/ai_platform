'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const express = require('express');
const { ThreadStore, THREAD_ID_RE } = require('./thread-store');
const { MissionControlAdapter } = require('./mission-control');
const { OperatorControlAdapter } = require('./operator-control');
const { LocalModelAdapter } = require('./local-model');
const { readProtectedSecret } = require('./secrets');
const { startDeliveryLoop } = require('./saas-delivery');
const { runtimeReadiness } = require('./readiness');

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    if (!argv[i].startsWith('--')) continue;
    const key = argv[i].slice(2); const value = argv[i + 1];
    if (value && !value.startsWith('--')) { out[key] = value; i += 1; } else out[key] = true;
  }
  return out;
}

function parseCookies(value) {
  const out = {};
  for (const part of String(value || '').split(';')) {
    const i = part.indexOf('='); if (i < 0) continue;
    out[part.slice(0, i).trim()] = part.slice(i + 1).trim();
  }
  return out;
}

function sendError(res, error, fallback = 400) {
  const status = Number(error && error.status) || (error && error.code === 'THREAD_NOT_FOUND' ? 404 : fallback);
  res.status(status).json({ error: `${error && error.name || 'Error'}:${error && error.message || String(error)}` });
}

function randomToken(bytes = 24) { return crypto.randomBytes(bytes).toString('base64url'); }

function createApp(config) {
  const app = express();
  app.disable('x-powered-by');
  app.use(express.json({ limit: '220kb', strict: true }));
  app.use((req, res, next) => { res.set('Cache-Control', 'no-store'); next(); });

  const store = new ThreadStore(config.threadDb);
  const mission = new MissionControlAdapter({ baseUrl: config.missionControlUrl, repo: config.repo, gitExe: config.gitExe });
  const model = new LocalModelAdapter({ baseUrl: config.modelUrl });
  let operator = null;
  if (config.operatorProxyKeyFile) {
    try {
      const key = readProtectedSecret(config.operatorProxyKeyFile, config.unprotectHelper);
      operator = new OperatorControlAdapter({ baseUrl: config.operatorControlUrl, panelProxyKey: key });
    } catch (error) {
      console.error(JSON.stringify({ event: 'operator_proxy_init_failed', error_class: error.name, message: error.message }));
    }
  }

  const uiTemplate = fs.readFileSync(config.uiPath, 'utf8');
  const frontendRevision = crypto.createHash('sha256').update(uiTemplate).digest('hex');
  const sessions = new Map();
  const stopDelivery = startDeliveryLoop(store, mission, { onError: (error) => console.error(JSON.stringify({ event: 'saas_delivery_deferred', error_class: error.name })) });

  function newSession() {
    const sid = randomToken(32); const csrf = randomToken(32);
    sessions.set(sid, { csrf, expires: Date.now() + 8 * 3600 * 1000, gatewaySession: null, paired: false });
    return { sid, csrf };
  }

  function operatorSession(req, { mutating = false, paired = false } = {}) {
    const host = String(req.hostname || '').toLowerCase();
    if (!['127.0.0.1','localhost','::1'].includes(host)) { const e = new Error('operator host denied'); e.status = 403; throw e; }
    const cookies = parseCookies(req.headers.cookie); const sid = cookies.lion_operator_session;
    let session = sid && sessions.get(sid);
    if (session && session.expires <= Date.now()) { sessions.delete(sid); session = null; }
    if (!session) { const e = new Error('operator browser session required; reload panel'); e.status = 403; throw e; }
    if (paired && !session.gatewaySession) { const e = new Error('operator pairing required'); e.status = 403; throw e; }
    if (mutating) {
      const supplied = String(req.headers['x-lion-csrf'] || '');
      if (!supplied || supplied.length !== session.csrf.length || !crypto.timingSafeEqual(Buffer.from(supplied), Buffer.from(session.csrf))) { const e = new Error('operator csrf denied'); e.status = 403; throw e; }
      const origin = req.headers.origin;
      if (origin) {
        const parsed = new URL(origin); if (!['127.0.0.1','localhost','::1'].includes(String(parsed.hostname).toLowerCase())) { const e = new Error('operator origin denied'); e.status = 403; throw e; }
      }
    }
    return session;
  }

  app.get('/', (req, res) => {
    const { sid, csrf } = newSession();
    const html = uiTemplate.replace('__FRONTEND_REVISION__', frontendRevision).replace('__OPERATOR_CSRF__', csrf);
    res.set('Content-Type', 'text/html; charset=utf-8');
    res.set('Set-Cookie', `lion_operator_session=${sid}; Path=/; HttpOnly; SameSite=Strict`);
    res.send(html);
  });

  app.get('/favicon.ico', (req, res) => res.status(204).end());
  app.get('/health', (req, res) => res.json({ status: 'ok', runtime: 'NODE_EXPRESS_R17', authority_effect: 'NONE' }));

  app.get('/api/state', async (req, res) => {
    try {
      const [readiness, broker, localHealth, recent] = await Promise.all([
        runtimeReadiness(config),
        mission.saasStatus().catch(() => null),
        model.health(),
        mission.recent('operational').catch(() => ({ missions: [], focus_mission_id: null })),
      ]);
      const focus = (recent.missions || []).find((m) => m.mission_id === recent.focus_mission_id) || null;
      const supervisor = broker && broker.supervisor_projection ? { ...broker.supervisor_projection } : {};
      Object.assign(supervisor, {
        control_plane_ready: readiness.control_plane_ready,
        turn_ingress_ready: readiness.turn_ingress_ready,
        mcp_transport_ready: readiness.mcp_transport_ready,
        model_executor_ready: readiness.model_executor_ready,
        autonomous_dispatch_ready: readiness.autonomous_dispatch_ready,
        durable_turn_dispatch_ready: readiness.durable_turn_dispatch_ready,
        browser_automation: readiness.browser_automation,
      });
      res.json({
        status: 'ok', product: 'LION CONTROL LPCL PANEL', runtime: 'NODE_EXPRESS_R17',
        model: 'gpt-oss-20b-MXFP4', gpu: 'NVIDIA GeForce RTX 5090 / Vulkan0', rag_status: 'NODE_MIGRATION_COMPAT',
        web_capability: 'MISSION_CONTROL_COMPATIBILITY_ONLY', repository_capability: 'LOCAL_GIT_READ_ONLY',
        mission_control: { status: readiness.control_plane_ready ? 'OK' : 'UNKNOWN', focus_mission_id: recent.focus_mission_id || null, mission_count: (recent.missions || []).length, focus },
        material: { requested: 0, healthy: 0, rows: [], authority_effect: 'NONE' },
        authority_effect: 'NONE', browser_automation: readiness.browser_automation,
        external_chatgpt_auto_inference: readiness.autonomous_dispatch_ready,
        supervisor_projection: supervisor,
        readiness,
        local_model: localHealth,
      });
    } catch (error) { sendError(res, error, 500); }
  });

  // Threads
  app.get('/api/threads', (req, res) => res.json(store.list()));
  app.post('/api/threads', (req, res) => { try { res.status(201).json(store.create(req.body || {})); } catch (e) { sendError(res, e); } });
  app.post('/api/threads/import', (req, res) => { try { res.status(201).json(store.importMessages(req.body && req.body.messages)); } catch (e) { sendError(res, e); } });
  app.get('/api/threads/:threadId', (req, res) => { try { res.json(store.get(req.params.threadId)); } catch (e) { sendError(res, e); } });
  app.patch('/api/threads/:threadId', (req, res) => { try { res.json(store.rename(req.params.threadId, req.body && req.body.title)); } catch (e) { sendError(res, e); } });
  app.delete('/api/threads/:threadId', async (req, res) => {
    try {
      const tids = store.get(req.params.threadId); // proves ownership before remote cancellation
      const requestIds = [...new Set((tids.messages || []).map((m) => m.meta && m.meta.saas_request_id).filter(Boolean))].sort();
      const cancelled = [];
      for (const rid of requestIds) cancelled.push(await mission.saasCancel(rid));
      const result = store.delete(req.params.threadId, () => ({ cancellation_already_observed: true }));
      result.handoffs = cancelled; res.json(result);
    } catch (e) { sendError(res, e); }
  });
  app.post('/api/threads/:threadId/user', (req, res) => {
    try { const x = req.body || {}; res.status(201).json(store.appendUserOnce(req.params.threadId, x.content, x.dedupe_key, x.meta)); } catch (e) { sendError(res, e); }
  });
  app.post('/api/threads/:threadId/assistant', (req, res) => {
    try { const x = req.body || {}; res.status(201).json(store.appendAssistantOnce(req.params.threadId, x.content, x.dedupe_key, x.meta)); } catch (e) {
      if (e.code === 'THREAD_NOT_FOUND' && req.body && req.body.meta && req.body.meta.delivery_kind === 'SWARM_RESPONSE') return res.json({ inserted: false, orphaned_thread: true, thread_id: req.params.threadId, dedupe_key: req.body.dedupe_key });
      sendError(res, e);
    }
  });

  app.post('/api/threads/:threadId/chat', async (req, res) => {
    try {
      const x = req.body || {}; const message = String(x.message || '').trim(); const route = String(x.route || 'AUTO').toUpperCase();
      if (!message || message.length > 8000) throw new Error('message');
      if (!['AUTO','LOCAL','CHATGPT'].includes(route)) throw new Error('composer route');
      const thread = store.get(req.params.threadId);
      if (route === 'AUTO') {
        const auto = await mission.autoMission({ threadId: req.params.threadId, question: message });
        const rid = auto.saas && auto.saas.request_id;
        try {
          store.appendUserOnce(req.params.threadId, message, 'auto-user:' + auto.mission_id, {
            route: 'AUTO_MISSION', delivery_kind: 'LION_AUTONOMOUS_MISSION', mission_id: auto.mission_id,
            logical_count: auto.logical_count, material_target: auto.material_target,
            lpcl_digest: auto.lpcl_digest, saas_request_id: rid || null,
            saas_request_code: auto.saas && auto.saas.request_code || null,
            transport: auto.saas && auto.saas.transport || 'CHATGPT_SENTINELX_MCP',
            authority_effect: 'EXPLICIT_USER_ACTIVATION',
          });
        } catch (error) {
          if (rid) await mission.saasCancel(rid).catch(() => {});
          throw error;
        }
        return res.status(202).json({
          route: 'AUTO_MISSION', status: 'RUNNING', mission_id: auto.mission_id,
          logical_count: auto.logical_count, material_target: auto.material_target,
          lpcl_digest: auto.lpcl_digest, saas_request_id: rid || null,
          authority_effect: 'EXPLICIT_USER_ACTIVATION', mission: auto.activated,
          thread_id: req.params.threadId, thread_title: store.get(req.params.threadId).title,
        });
      }
      if (route === 'CHATGPT') {
        const handoff = await mission.saasRequest({ threadId: req.params.threadId, question: message });
        const rid = handoff.request_id; if (!rid) throw new Error('saas handoff request id');
        try {
          store.appendUserOnce(req.params.threadId, message, `saas-user:${rid}`, {
            route: 'SAAS_HANDOFF', delivery_kind: 'CHATGPT_SAAS_REQUEST', saas_request_id: rid,
            saas_request_code: handoff.request_code, transport: handoff.transport, authority_effect: 'NONE',
          });
        } catch (error) { await mission.saasCancel(rid).catch(() => {}); throw error; }
        return res.status(202).json({ route: 'SAAS_HANDOFF', status: 'QUEUED', request_id: rid, request_code: handoff.request_code, transport: handoff.transport, authority_effect: 'NONE', saas_handoff: handoff, thread_id: req.params.threadId, thread_title: store.get(req.params.threadId).title });
      }
      const history = (thread.messages || []).slice(-12).map((m) => ({ role: m.role, content: m.content }));
      const local = await model.chat(message, history, x.output_language || 'auto');
      const saved = store.appendPair(req.params.threadId, message, local.answer, { route: 'LOCAL_MODEL_DIRECT', authority_effect: 'NONE' });
      return res.json({ route: 'LOCAL_MODEL_DIRECT', answer: local.answer, authority_boundary: false, tool_calls: [], material_receipts: [], thread_id: req.params.threadId, thread_title: saved.title, response_language: x.output_language || 'auto' });
    } catch (e) { sendError(res, e); }
  });

  app.get('/api/saas/requests/:requestId', async (req, res) => { try { res.json(await mission.saasRequestStatus(req.params.requestId)); } catch (e) { sendError(res, e); } });

  // Mission compatibility surface.
  app.get('/api/missions/recent', async (req, res) => { try { res.json(await mission.recent(String(req.query.view || 'operational'))); } catch (e) { sendError(res, e); } });
  app.get('/api/missions/:missionId/process', async (req, res) => { try { res.json(await mission.process(req.params.missionId)); } catch (e) { sendError(res, e); } });
  app.get('/api/missions/:missionId/delete-preview', async (req, res) => { try { res.json(await mission.missionDeletePreview(req.params.missionId)); } catch (e) { sendError(res, e); } });
  app.post('/api/missions/:missionId/delete', async (req, res) => { try { res.json(await mission.missionDelete(req.params.missionId, req.body && req.body.spec_digest)); } catch (e) { sendError(res, e); } });
  app.post('/api/missions/:missionId/action', async (req, res) => { try { const x = req.body || {}; res.json(await mission.missionAction(req.params.missionId, x.action, x.payload || {})); } catch (e) { sendError(res, e); } });
  app.post('/api/missions/:missionId/phase-actions', async (req, res) => { try { res.json(await mission.phaseAction(req.params.missionId, req.body || {})); } catch (e) { sendError(res, e); } });
  app.post('/api/missions/:missionId/phase-operations', async (req, res) => { try { res.json(await mission.phaseOperation(req.params.missionId, req.body || {})); } catch (e) { sendError(res, e); } });
  app.post('/api/lpcl/validate', async (req, res) => { try { res.json(await mission.validateLpcl(req.body && req.body.lpcl_text)); } catch (e) { sendError(res, e); } });
  app.post('/api/lpcl/register', async (req, res) => { try { res.status(201).json(await mission.registerLpcl(req.body && req.body.lpcl_text)); } catch (e) { sendError(res, e); } });
  app.post('/api/lpcl/activate', async (req, res) => { try { const x = req.body || {}; res.json(await mission.activateLpcl(x.mission_id, x.lpcl_digest)); } catch (e) { sendError(res, e); } });
  app.post('/api/ui-runtime-events', (req, res) => { try { res.status(201).json(store.recordUiRuntimeEvent(req.body)); } catch (e) { sendError(res, e); } });

  // Operator compatibility surface. Pairing secret is provided by the user; the panel proxy key is loaded once at startup.
  app.get('/api/operator/session', async (req, res) => {
    if (!operator) return res.json({ paired: false, principal_id: null, authority_effect: 'NONE', unavailable: true });
    try { const s = operatorSession(req); if (!s.gatewaySession) return res.json({ paired: false, principal_id: null, authority_effect: 'NONE' }); res.json(await operator.session(s.gatewaySession)); } catch (e) { sendError(res, e, 403); }
  });
  app.post('/api/operator/pair', async (req, res) => { try { if (!operator) throw new Error('operator control unavailable'); const s = operatorSession(req, { mutating: true }); const value = await operator.pair(req.body && req.body.pairing_code); if (!value.session_token) throw new Error('pairing session token missing'); s.gatewaySession = value.session_token; s.paired = true; const { session_token, ...publicValue } = value; res.status(201).json(publicValue); } catch (e) { sendError(res, e, e.status || 403); } });
  app.post('/api/operator/unpair', async (req, res) => { try { if (!operator) throw new Error('operator control unavailable'); const s = operatorSession(req, { mutating: true, paired: true }); const value = await operator.unpair(s.gatewaySession); s.gatewaySession = null; s.paired = false; res.json(value); } catch (e) { sendError(res, e, e.status || 403); } });
  app.get('/api/operator/state', async (req, res) => { try { if (!operator) throw new Error('operator control unavailable'); const s = operatorSession(req); res.json(await operator.state(req.query.mission_id, s.gatewaySession)); } catch (e) { sendError(res, e, e.status || 400); } });
  app.get('/api/operator/participants', async (req, res) => { try { if (!operator) throw new Error('operator control unavailable'); const s = operatorSession(req); res.json(await operator.participants(s.gatewaySession)); } catch (e) { sendError(res, e); } });
  app.get('/api/operator/channel', async (req, res) => { try { if (!operator) throw new Error('operator control unavailable'); const s = operatorSession(req); res.json(await operator.channelRead(req.query.after, req.query.limit, s.gatewaySession)); } catch (e) { sendError(res, e); } });
  app.post('/api/operator/channel', async (req, res) => { try { if (!operator) throw new Error('operator control unavailable'); const s = operatorSession(req, { mutating: true }); res.status(201).json(await operator.channelSend(req.body || {}, s.gatewaySession)); } catch (e) { sendError(res, e, e.status || 400); } });
  app.get('/api/operator/swarm/active', async (req, res) => { try { if (!operator) throw new Error('operator control unavailable'); const s = operatorSession(req); res.json(await operator.swarmActive(s.gatewaySession)); } catch (e) { sendError(res, e); } });
  app.get('/api/operator/swarm', async (req, res) => { try { if (!operator) throw new Error('operator control unavailable'); const s = operatorSession(req); res.json(await operator.swarmRead(req.query.session_id, req.query.after, req.query.limit, s.gatewaySession)); } catch (e) { sendError(res, e); } });
  app.post('/api/operator/swarm/open', async (req, res) => { try { if (!operator) throw new Error('operator control unavailable'); const s = operatorSession(req, { mutating: true }); res.status(201).json(await operator.swarmOpen(req.body || {}, s.gatewaySession)); } catch (e) { sendError(res, e); } });
  app.post('/api/operator/swarm/send', async (req, res) => { try { if (!operator) throw new Error('operator control unavailable'); const s = operatorSession(req, { mutating: true }); const x = req.body || {}; res.status(201).json(await operator.swarmSend(x.session_id, x, s.gatewaySession)); } catch (e) { sendError(res, e); } });
  app.post('/api/operator/swarm/close', async (req, res) => { try { if (!operator) throw new Error('operator control unavailable'); const s = operatorSession(req, { mutating: true }); res.json(await operator.swarmClose(req.body && req.body.session_id, s.gatewaySession)); } catch (e) { sendError(res, e); } });
  app.get('/api/operator/events', async (req, res) => { try { if (!operator) throw new Error('operator control unavailable'); const s = operatorSession(req); res.json(await operator.events(req.query.mission_id, req.query.after, req.query.limit, s.gatewaySession)); } catch (e) { sendError(res, e); } });
  app.post('/api/operator/commands', async (req, res) => { try { if (!operator) throw new Error('operator control unavailable'); const s = operatorSession(req, { mutating: true, paired: true }); res.status(201).json(await operator.command(req.body || {}, s.gatewaySession)); } catch (e) { sendError(res, e, e.status || 400); } });
  app.get('/api/operator/commands/:commandId', async (req, res) => { try { if (!operator) throw new Error('operator control unavailable'); const s = operatorSession(req); res.json(await operator.commandStatus(req.params.commandId, s.gatewaySession)); } catch (e) { sendError(res, e); } });
  app.post('/api/operator/events/ack', async (req, res) => { try { if (!operator) throw new Error('operator control unavailable'); const s = operatorSession(req, { mutating: true, paired: true }); res.json(await operator.ack(req.body || {}, s.gatewaySession)); } catch (e) { sendError(res, e); } });
  app.get('/api/operator/stream', async (req, res) => {
    if (!operator) return res.status(503).end();
    let session; try { session = operatorSession(req); } catch (e) { return res.status(403).end(); }
    let cursor = Math.max(Number(req.query.after || 0), Number(req.headers['last-event-id'] || 0));
    const missionId = String(req.query.mission_id || '');
    res.status(200); res.set({ 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-store', Connection: 'keep-alive' }); res.flushHeaders();
    const deadline = Date.now() + 25000; let closed = false; req.on('close', () => { closed = true; });
    while (!closed && Date.now() < deadline) {
      try {
        const batch = await operator.events(missionId, cursor, 100, session.gatewaySession);
        for (const event of batch.events || []) { const eid = Number(event.event_id || 0); res.write(`id: ${eid}\nevent: message\ndata: ${JSON.stringify(event)}\n\n`); cursor = Math.max(cursor, eid); }
        res.write(': keepalive\n\n');
      } catch {}
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    if (!res.writableEnded) res.end();
  });

  app.post('/api/chat', async (req, res) => {
    try { const x = req.body || {}; const local = await model.chat(x.message, x.history, x.output_language || 'auto'); res.json({ route: 'LOCAL_MODEL_DIRECT', answer: local.answer, authority_effect: 'NONE' }); } catch (e) { sendError(res, e); }
  });
  app.post('/v1/chat/completions', async (req, res) => {
    try {
      const rows = Array.isArray(req.body && req.body.messages) ? req.body.messages.filter((m) => m && ['user','assistant'].includes(m.role) && typeof m.content === 'string') : [];
      const users = rows.filter((m) => m.role === 'user'); if (!users.length) throw new Error('user message'); const latest = users.at(-1).content;
      const history = rows.slice(0, Math.max(0, rows.lastIndexOf(users.at(-1)))); const local = await model.chat(latest, history, req.body.lion_output_language || 'auto');
      res.json({ id: 'lion-node-express', object: 'chat.completion', model: 'gpt-oss-20b-MXFP4', choices: [{ index: 0, message: { role: 'assistant', content: local.answer }, finish_reason: 'stop' }], lion: { route: 'LOCAL_MODEL_DIRECT', authority_effect: 'NONE' } });
    } catch (e) { sendError(res, e); }
  });

  app.use((req, res) => res.status(404).json({ error: 'not found' }));
  app.use((error, req, res, next) => { if (res.headersSent) return next(error); sendError(res, error, 500); });

  return { app, store, stop: () => { stopDelivery(); store.close(); } };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const repo = path.resolve(args.repo || process.env.LION_REPO || path.resolve(__dirname, '..', '..'));
  const runtime = path.resolve(args.runtime || process.env.LION_RUNTIME || path.dirname(args['thread-db'] || path.resolve(repo, 'runtime')));
  const config = {
    repo, runtime,
    port: Number(args.port || process.env.LION_PANEL_PORT || 8780),
    threadDb: path.resolve(args['thread-db'] || process.env.LION_THREAD_DB || path.join(runtime, 'threads', 'lion-local-model.db')),
    modelUrl: args.model || process.env.LION_MODEL_URL || 'http://127.0.0.1:8772',
    missionControlUrl: args['mission-control-url'] || process.env.LION_MISSION_CONTROL_URL || 'http://127.0.0.1:8766',
    operatorControlUrl: args['operator-control-url'] || process.env.LION_OPERATOR_CONTROL_URL || 'http://127.0.0.1:8767',
    operatorProxyKeyFile: args['operator-panel-proxy-key-file'] || process.env.LION_OPERATOR_PANEL_PROXY_KEY_FILE || null,
    gitExe: args.git || process.env.LION_GIT || 'C:\\Program Files\\Git\\cmd\\git.exe',
    uiPath: path.resolve(__dirname, '..', 'static', 'index.html'),
    unprotectHelper: path.resolve(__dirname, '..', 'scripts', 'unprotect_secret.ps1'),
    relayStatusPath: path.resolve(args['relay-status'] || process.env.LION_NODE_RELAY_STATUS || path.join(runtime, 'node-secure-mcp-relay', 'relay-status.json')),
    browserDisableMarker: path.resolve(args['browser-disable-marker'] || process.env.LION_BROWSER_DISABLE_MARKER || path.join(runtime, 'firefox-mediator-app-next', 'browser-automation.disabled')),
    tunnelUrl: args['tunnel-url'] || process.env.LION_TUNNEL_URL || 'http://127.0.0.1:8792',
  };
  if (!Number.isInteger(config.port) || config.port < 1024 || config.port > 65535) throw new Error('invalid port');
  if (!THREAD_ID_RE) throw new Error('thread contract unavailable');
  const { app, stop } = createApp(config);
  const server = app.listen(config.port, '127.0.0.1', () => console.log(JSON.stringify({ event: 'lion.node-express-panel.started', port: config.port, pid: process.pid, browser_automation: 'DISABLED_BY_POLICY', authority_effect: 'NONE' })));
  const shutdown = () => server.close(() => { stop(); process.exit(0); });
  process.on('SIGTERM', shutdown); process.on('SIGINT', shutdown);
}

if (require.main === module) main();
module.exports = { createApp, parseArgs, parseCookies };
