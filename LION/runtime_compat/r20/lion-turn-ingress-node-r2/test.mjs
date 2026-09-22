import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const root = dirname(fileURLToPath(import.meta.url));
const data = await mkdtemp(join(tmpdir(), "lion-ingress-test-"));
const port = 18791;
const child = spawn(process.execPath, [join(root, "server.mjs")], {
  env: { ...process.env, LION_INGRESS_PORT: String(port), LION_INGRESS_DATA: data },
  stdio: ["ignore", "pipe", "pipe"]
});
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const base = `http://127.0.0.1:${port}`;
async function req(path, init = {}) {
  const r = await fetch(base + path, { ...init, headers: { "content-type": "application/json", ...(init.headers || {}) } });
  const j = await r.json();
  return { status: r.status, body: j };
}
function assert(x, m) { if (!x) throw new Error(m); }

try {
  let healthy = false;
  for (let i=0; i<50; i++) {
    try { const r = await req("/health"); if (r.status === 200) { healthy = true; break; } } catch {}
    await sleep(40);
  }
  assert(healthy, "server did not become healthy");

  const payload = {
    command_id: "TEST-CMD-001",
    mission_id: "TEST-MISSION",
    session_id: "TEST-SESSION",
    thread_id: "TEST-THREAD",
    cursor: 1,
    parent_event_id: "saas_request:saas-TEST-CMD-001",
    input: "ping"
  };
  const a = await req("/v1/turns", { method:"POST", body: JSON.stringify(payload) });
  assert(a.status === 202, "first submit must be 202");
  const id = a.body.turn.turn_id;
  assert(a.body.turn.parent_event_id === payload.parent_event_id, "parent event lineage missing");

  const b = await req("/v1/turns", { method:"POST", body: JSON.stringify(payload) });
  assert(b.status === 200 && b.body.duplicate === true, "duplicate must collapse exactly-once");
  assert(b.body.turn.turn_id === id, "duplicate must resolve same turn");

  const c = await req("/v1/turns", { method:"POST", body: JSON.stringify({ ...payload, input:"different" }) });
  assert(c.status === 409, "command_id payload mismatch must conflict");

  const lineageConflict = await req("/v1/turns", { method:"POST", body: JSON.stringify({ ...payload, parent_event_id:"saas_request:saas-DIFFERENT" }) });
  assert(lineageConflict.status === 409, "parent event substitution must conflict");

  const q = await req("/v1/queue/next?after=0");
  assert(q.body.turn.turn_id === id, "queue must return pending turn");

  const claim = await req(`/v1/turns/${id}/claim`, { method:"POST", body: JSON.stringify({actor:"test-runner"}) });
  assert(claim.status === 200 && claim.body.turn.status === "CLAIMED", "claim failed");

  const done = await req(`/v1/turns/${id}/complete`, { method:"POST", body: JSON.stringify({response:{text:"pong"},actor:"test-runner"}) });
  assert(done.status === 200 && done.body.turn.status === "COMPLETED", "complete failed");

  const state = await req("/v1/state");
  assert(state.body.completed === 1 && state.body.pending === 0, "state counters wrong");

  const mcp = await req("/mcp", { method:"POST", body: JSON.stringify({jsonrpc:"2.0",id:1,method:"tools/list",params:{}}) });
  assert(mcp.status === 200 && mcp.body.result.tools.length >= 3, "mcp tools/list failed");

  console.log(JSON.stringify({
    test:"PASS",
    exactly_once:"PASS",
    conflict_on_payload_change:"PASS",
    parent_event_lineage:"PASS",
    claim_complete:"PASS",
    persistence_surface:"PASS",
    mcp_tools_list:"PASS",
    turn_id:id
  }));
} finally {
  child.kill("SIGTERM");
  await sleep(50);
  await rm(data, {recursive:true,force:true});
}
