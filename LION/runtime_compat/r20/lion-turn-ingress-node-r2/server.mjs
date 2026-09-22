import http from "node:http";
import { readFileSync } from "node:fs";
import { createHash, randomUUID, timingSafeEqual } from "node:crypto";
import { appendFile, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = resolve(process.env.LION_INGRESS_DATA || `${HERE}/data`);
const HOST = process.env.LION_INGRESS_HOST || "127.0.0.1";
const PORT = Number(process.env.LION_INGRESS_PORT || "8791");
const TOKEN_FILE = process.env.LION_INGRESS_TOKEN_FILE || "";
const TOKEN = process.env.LION_INGRESS_TOKEN || (TOKEN_FILE ? readFileSync(TOKEN_FILE, "utf8").trim() : "");
const TOKEN_SHA256_FILE = process.env.LION_INGRESS_TOKEN_SHA256_FILE || "";
const TOKEN_SHA256_ALLOW = new Set(
  TOKEN_SHA256_FILE
    ? readFileSync(TOKEN_SHA256_FILE, "utf8").split(/\r?\n/).map(x => x.trim().toLowerCase()).filter(x => /^[0-9a-f]{64}$/.test(x))
    : []
);
const MAX_BODY = Number(process.env.LION_INGRESS_MAX_BODY || String(1024 * 1024));

const TURNS_LOG = resolve(DATA_DIR, "turns.jsonl");
const EVENTS_LOG = resolve(DATA_DIR, "events.jsonl");
const SNAPSHOT = resolve(DATA_DIR, "snapshot.json");

const turns = new Map();
const commandIndex = new Map();
const sseClients = new Set();
let seq = 0;

const now = () => new Date().toISOString();
const sha256 = (s) => createHash("sha256").update(s).digest("hex");
const safeJson = (s) => { try { return JSON.parse(s); } catch { return null; } };

async function ensureData() {
  await mkdir(DATA_DIR, { recursive: true });
  for (const p of [TURNS_LOG, EVENTS_LOG]) {
    try { await readFile(p); } catch { await writeFile(p, ""); }
  }
}

async function replay() {
  await ensureData();
  const raw = await readFile(TURNS_LOG, "utf8");
  for (const line of raw.split(/\r?\n/)) {
    if (!line.trim()) continue;
    const rec = safeJson(line);
    if (!rec?.turn_id) continue;
    turns.set(rec.turn_id, rec);
    if (rec.command_id) commandIndex.set(rec.command_id, rec.turn_id);
    seq = Math.max(seq, rec.seq || 0);
  }
}

async function persistTurn(rec) {
  await appendFile(TURNS_LOG, JSON.stringify(rec) + "\n", "utf8");
  turns.set(rec.turn_id, rec);
  if (rec.command_id) commandIndex.set(rec.command_id, rec.turn_id);
  const values = [...turns.values()];
  await writeFile(SNAPSHOT, JSON.stringify({
    schema: "lion.turn-ingress.snapshot/v1",
    generated_at: now(),
    seq,
    turns: values.length,
    pending: values.filter(x => x.status === "PENDING").length,
    claimed: values.filter(x => x.status === "CLAIMED").length,
    completed: values.filter(x => x.status === "COMPLETED").length
  }, null, 2) + "\n", "utf8");
}

async function emit(type, data) {
  const ev = { schema: "lion.turn-ingress.event/v1", seq: ++seq, at: now(), type, data };
  await appendFile(EVENTS_LOG, JSON.stringify(ev) + "\n", "utf8");
  const frame = `id: ${ev.seq}\nevent: ${type}\ndata: ${JSON.stringify(ev)}\n\n`;
  for (const res of sseClients) {
    try { res.write(frame); } catch { sseClients.delete(res); }
  }
  return ev;
}

function jsonResponse(res, status, body, headers = {}) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "content-length": Buffer.byteLength(payload),
    ...headers
  });
  res.end(payload);
}

function authorized(req) {
  if (String(req.url || "").startsWith("/.well-known/")) return true;
  if (!TOKEN && TOKEN_SHA256_ALLOW.size === 0) return true;
  const localToken = req.headers["x-lion-token"];
  const h = req.headers.authorization || "";
  const presented = typeof localToken === "string" ? localToken : (h.startsWith("Bearer ") ? h.slice(7) : "");
  if (!presented) return false;

  if (TOKEN) {
    const got = Buffer.from(presented);
    const want = Buffer.from(TOKEN);
    if (got.length === want.length && timingSafeEqual(got, want)) return true;
  }

  if (TOKEN_SHA256_ALLOW.size > 0) {
    const digest = sha256(presented);
    for (const allowed of TOKEN_SHA256_ALLOW) {
      const got = Buffer.from(digest);
      const want = Buffer.from(allowed);
      if (got.length === want.length && timingSafeEqual(got, want)) return true;
    }
  }
  return false;
}

async function body(req) {
  let size = 0;
  const chunks = [];
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY) throw Object.assign(new Error("body too large"), { status: 413 });
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  const raw = Buffer.concat(chunks).toString("utf8");
  const value = safeJson(raw);
  if (value === null) throw Object.assign(new Error("invalid json"), { status: 400 });
  return value;
}

function publicTurn(t) {
  return {
    schema: t.schema,
    turn_id: t.turn_id,
    command_id: t.command_id,
    mission_id: t.mission_id,
    session_id: t.session_id,
    thread_id: t.thread_id,
    cursor: t.cursor,
    parent_event_id: t.parent_event_id ?? null,
    status: t.status,
    created_at: t.created_at,
    updated_at: t.updated_at,
    claimed_at: t.claimed_at || null,
    completed_at: t.completed_at || null,
    request_hash: t.request_hash,
    input: t.input,
    response: t.response ?? null,
    claim: t.claim ?? null
  };
}

function findNext(after = 0) {
  return [...turns.values()]
    .filter(x => (x.seq || 0) > after && x.status === "PENDING")
    .sort((a,b) => (a.seq || 0) - (b.seq || 0))[0] || null;
}

async function createTurn(payload) {
  const command_id = String(payload.command_id || "").trim();
  if (!command_id) throw Object.assign(new Error("command_id required"), { status: 400 });
  const requestCore = {
    command_id,
    mission_id: payload.mission_id ?? null,
    session_id: payload.session_id ?? null,
    thread_id: payload.thread_id ?? null,
    cursor: Number.isInteger(payload.cursor) ? payload.cursor : null,
    parent_event_id: payload.parent_event_id ?? null,
    input: payload.input ?? payload.message ?? null,
    metadata: payload.metadata ?? {}
  };
  if (requestCore.input === null || requestCore.input === "") {
    throw Object.assign(new Error("input required"), { status: 400 });
  }
  if (requestCore.parent_event_id !== null &&
      !/^saas_request:saas-[A-Za-z0-9-]+$/.test(String(requestCore.parent_event_id))) {
    throw Object.assign(new Error("parent_event_id invalid"), { status: 400 });
  }
  const request_hash = sha256(JSON.stringify(requestCore));
  const existingId = commandIndex.get(command_id);
  if (existingId) {
    const existing = turns.get(existingId);
    if (existing.request_hash !== request_hash) {
      throw Object.assign(new Error("command_id conflict"), { status: 409 });
    }
    return { duplicate: true, turn: existing };
  }

  const ev = await emit("turn.accepted", { command_id });
  const at = now();
  const rec = {
    schema: "lion.turn-ingress.turn/v1",
    seq: ev.seq,
    turn_id: `turn_${randomUUID()}`,
    command_id,
    mission_id: requestCore.mission_id,
    session_id: requestCore.session_id,
    thread_id: requestCore.thread_id,
    cursor: requestCore.cursor,
    parent_event_id: requestCore.parent_event_id,
    status: "PENDING",
    created_at: at,
    updated_at: at,
    request_hash,
    input: requestCore.input,
    metadata: requestCore.metadata,
    claim: null,
    response: null
  };
  await persistTurn(rec);
  await emit("turn.pending", { turn_id: rec.turn_id, command_id });
  return { duplicate: false, turn: rec };
}

async function updateTurn(turn, patch, eventType) {
  const rec = { ...turn, ...patch, updated_at: now() };
  await persistTurn(rec);
  await emit(eventType, { turn_id: rec.turn_id, command_id: rec.command_id, status: rec.status });
  return rec;
}

async function listEventsAfter(after) {
  const raw = await readFile(EVENTS_LOG, "utf8");
  return raw.split(/\r?\n/).filter(Boolean).map(safeJson).filter(Boolean).filter(e => (e.seq || 0) > after);
}

function mcpToolList() {
  return [
    {
      name: "lion_next_turn",
      description: "Read the next pending LION turn after an event cursor. Read-only.",
      annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false, idempotentHint: true },
      inputSchema: { type: "object", properties: { after: { type: "integer", minimum: 0 } }, additionalProperties: false }
    },
    {
      name: "lion_get_turn",
      description: "Read one LION turn by turn_id. Read-only.",
      annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false, idempotentHint: true },
      inputSchema: { type: "object", properties: { turn_id: { type: "string" } }, required: ["turn_id"], additionalProperties: false }
    },
    {
      name: "lion_complete_turn",
      description: "Complete a LION turn with an assistant response. This changes durable turn state but is idempotent for an already completed turn.",
      annotations: { readOnlyHint: false, destructiveHint: false, openWorldHint: false, idempotentHint: true },
      inputSchema: {
        type: "object",
        properties: { turn_id: { type: "string" }, response: {}, actor: { type: "string" } },
        required: ["turn_id", "response"],
        additionalProperties: false
      }
    }
  ];
}

async function handleMcp(req, res) {
  const rpc = await body(req);
  const id = rpc.id ?? null;
  const ok = (result) => jsonResponse(res, 200, { jsonrpc: "2.0", id, result });
  const fail = (code, message) => jsonResponse(res, 200, { jsonrpc: "2.0", id, error: { code, message } });

  if (rpc.method === "initialize") {
    return ok({
      protocolVersion: rpc.params?.protocolVersion || "2025-03-26",
      capabilities: { tools: { listChanged: false } },
      serverInfo: { name: "lion-turn-ingress-node", version: "0.2.0" }
    });
  }
  if (rpc.method === "notifications/initialized") return jsonResponse(res, 202, {});
  if (rpc.method === "ping") return ok({});
  if (rpc.method === "tools/list") return ok({ tools: mcpToolList() });
  if (rpc.method !== "tools/call") return fail(-32601, "Method not found");

  const name = rpc.params?.name;
  const args = rpc.params?.arguments || {};
  if (name === "lion_next_turn") {
    const t = findNext(Number(args.after || 0));
    return ok({ content: [{ type: "text", text: JSON.stringify(t ? publicTurn(t) : null) }] });
  }
  if (name === "lion_get_turn") {
    const t = turns.get(String(args.turn_id || ""));
    return ok({ content: [{ type: "text", text: JSON.stringify(t ? publicTurn(t) : null) }] });
  }
  if (name === "lion_complete_turn") {
    const t = turns.get(String(args.turn_id || ""));
    if (!t) return fail(-32004, "turn not found");
    if (!["PENDING","CLAIMED"].includes(t.status)) return fail(-32009, `turn is ${t.status}`);
    const rec = await updateTurn(t, {
      status: "COMPLETED",
      completed_at: now(),
      response: args.response,
      completed_by: args.actor || "chatgpt"
    }, "turn.completed");
    return ok({ content: [{ type: "text", text: JSON.stringify(publicTurn(rec)) }] });
  }
  return fail(-32602, "unknown tool");
}

async function route(req, res) {
  if (!authorized(req)) return jsonResponse(res, 401, { error: "unauthorized" });
  const url = new URL(req.url, `http://${req.headers.host || `${HOST}:${PORT}`}`);
  const p = url.pathname;

  if (req.method === "GET" && p === "/health") {
    return jsonResponse(res, 200, {
      ok: true, service: "lion-turn-ingress-node", version: "0.2.0",
      host: HOST, port: PORT, auth: (TOKEN || TOKEN_SHA256_ALLOW.size) ? "token" : "none-loopback-only",
      seq, turns: turns.size
    });
  }
  if (req.method === "GET" && p === "/v1/state") {
    const values = [...turns.values()];
    return jsonResponse(res, 200, {
      schema: "lion.turn-ingress.state/v1", seq, turns: values.length,
      pending: values.filter(x => x.status === "PENDING").length,
      claimed: values.filter(x => x.status === "CLAIMED").length,
      completed: values.filter(x => x.status === "COMPLETED").length
    });
  }
  if (req.method === "POST" && p === "/v1/turns") {
    const result = await createTurn(await body(req));
    return jsonResponse(res, result.duplicate ? 200 : 202, { duplicate: result.duplicate, turn: publicTurn(result.turn) });
  }
  if (req.method === "GET" && p === "/v1/queue/next") {
    const after = Math.max(0, Number(url.searchParams.get("after") || "0") || 0);
    const t = findNext(after);
    return jsonResponse(res, 200, { after, turn: t ? publicTurn(t) : null });
  }
  if (req.method === "GET" && p === "/v1/events") {
    const after = Math.max(0, Number(url.searchParams.get("after") || "0") || 0);
    return jsonResponse(res, 200, { after, events: await listEventsAfter(after) });
  }
  if (req.method === "GET" && p === "/v1/events/stream") {
    res.writeHead(200, {
      "content-type": "text/event-stream",
      "cache-control": "no-cache",
      "connection": "keep-alive"
    });
    res.write(`event: ready\ndata: ${JSON.stringify({ seq, at: now() })}\n\n`);
    sseClients.add(res);
    req.on("close", () => sseClients.delete(res));
    return;
  }

  const m = p.match(/^\/v1\/turns\/([^/]+)(?:\/(claim|complete))?$/);
  if (m) {
    const turn = turns.get(decodeURIComponent(m[1]));
    if (!turn) return jsonResponse(res, 404, { error: "turn_not_found" });

    if (req.method === "GET" && !m[2]) return jsonResponse(res, 200, { turn: publicTurn(turn) });

    if (req.method === "POST" && m[2] === "claim") {
      if (turn.status === "CLAIMED") return jsonResponse(res, 200, { duplicate: true, turn: publicTurn(turn) });
      if (turn.status !== "PENDING") return jsonResponse(res, 409, { error: `turn_is_${turn.status.toLowerCase()}` });
      const payload = await body(req);
      const rec = await updateTurn(turn, {
        status: "CLAIMED",
        claimed_at: now(),
        claim: { actor: payload.actor || "chatgpt", lease_id: payload.lease_id || randomUUID() }
      }, "turn.claimed");
      return jsonResponse(res, 200, { duplicate: false, turn: publicTurn(rec) });
    }

    if (req.method === "POST" && m[2] === "complete") {
      if (turn.status === "COMPLETED") return jsonResponse(res, 200, { duplicate: true, turn: publicTurn(turn) });
      if (!["PENDING","CLAIMED"].includes(turn.status)) return jsonResponse(res, 409, { error: `turn_is_${turn.status.toLowerCase()}` });
      const payload = await body(req);
      if (!Object.prototype.hasOwnProperty.call(payload, "response")) return jsonResponse(res, 400, { error: "response_required" });
      const rec = await updateTurn(turn, {
        status: "COMPLETED",
        completed_at: now(),
        response: payload.response,
        completed_by: payload.actor || "chatgpt"
      }, "turn.completed");
      return jsonResponse(res, 200, { duplicate: false, turn: publicTurn(rec) });
    }
  }

  if (req.method === "POST" && p === "/mcp") return handleMcp(req, res);
  if (req.method === "GET" && p === "/mcp") return jsonResponse(res, 200, {
    name: "lion-turn-ingress-node", version: "0.2.0",
    transport: "http-jsonrpc",
    note: "REST ingress is canonical in R2; MCP compatibility is intentionally minimal."
  });

  return jsonResponse(res, 404, { error: "not_found" });
}

await replay();
const server = http.createServer((req, res) => {
  route(req, res).catch(err => {
    const status = err.status || 500;
    if (!res.headersSent) jsonResponse(res, status, {
      error: status >= 500 ? "internal_error" : err.message,
      detail: status >= 500 ? undefined : err.message
    });
    else res.destroy();
  });
});
server.on("clientError", (_err, socket) => socket.end("HTTP/1.1 400 Bad Request\r\n\r\n"));
server.listen(PORT, HOST, () => {
  console.log(JSON.stringify({
    event: "lion.turn-ingress.started", at: now(), host: HOST, port: PORT,
    data_dir: DATA_DIR, auth: (TOKEN || TOKEN_SHA256_ALLOW.size) ? "token" : "none-loopback-only"
  }));
});
