"use strict";

const fs = require("fs");
const path = require("path");
const http = require("http");
const crypto = require("crypto");
const { spawn } = require("child_process");

const HERE = __dirname;
const HOST = process.env.LION_FIREFOX_MANAGER_HOST || "127.0.0.1";
const PORT = Number(process.env.LION_FIREFOX_MANAGER_PORT || "8790");
const IPC =
  process.env.LION_FIREFOX_MEDIATOR_IPC ||
  "\\\\wsl.localhost\\LION-AUTH-LAB\\var\\lib\\sentinelx\\uploads\\lion-mission-control-v3\\firefox-mediator-ipc";
const PROJECT_HOME_URL =
  process.env.LION_FIREFOX_PROJECT_HOME_URL ||
  "https://chatgpt.com/g/g-p-6a91cabd3f208191a37f295819e9f75b-lion-evolusion/project";
const PROJECT_TITLE = process.env.LION_FIREFOX_PROJECT || "LION_EVOLUSION";
const POWERSHELL =
  process.env.LION_POWERSHELL ||
  "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe";
const WORKER_SCRIPT =
  process.env.LION_UIA_MEDIATOR_SCRIPT ||
  path.resolve(HERE, "..", "firefox-mediator-app-open-session", "open_session_mediator.ps1");

const STATUS_FILE = path.join(IPC, "mediator-status.json");
const THREADS_DIR = path.join(IPC, "mission-threads");
const WORKER_STDOUT = path.join(HERE, "uia-worker.stdout.log");
const WORKER_STDERR = path.join(HERE, "uia-worker.stderr.log");
const THREAD_POLICY = "ONE_CHAT_PER_MISSION_WITH_TERMINAL_ROLLOVER";

let child = null;
let shuttingDown = false;
let restartTimer = null;

function now() {
  return new Date().toISOString();
}

function safeJsonFile(file, def = null) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8").replace(/^\uFEFF/, ""));
  } catch {
    return def;
  }
}

function atomicJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = file + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2), "utf8");
  fs.renameSync(tmp, file);
}

function missionKey(payload) {
  const mission = String(payload?.mission_id || "").trim();
  if (mission) return "mission:" + mission;
  const st = String(payload?.scope_type || "").trim();
  const si = String(payload?.scope_id || "").trim();
  if (st && si) return "scope:" + st + ":" + si;
  const thread = String(payload?.thread_id || "").trim();
  if (thread) return "lion-thread:" + thread;
  return null;
}

function missionStatePath(payload) {
  const key = missionKey(payload);
  if (!key) return null;
  const digest = crypto.createHash("sha256").update(key).digest("hex");
  return path.join(THREADS_DIR, digest + ".json");
}

function listThreads() {
  try {
    if (!fs.existsSync(THREADS_DIR)) return [];
    return fs
      .readdirSync(THREADS_DIR)
      .filter((x) => x.endsWith(".json"))
      .sort()
      .map((name) => safeJsonFile(path.join(THREADS_DIR, name), null))
      .filter(Boolean);
  } catch {
    return [];
  }
}

function startWorker() {
  if (shuttingDown || child) return;
  fs.mkdirSync(HERE, { recursive: true });
  const out = fs.openSync(WORKER_STDOUT, "a");
  const err = fs.openSync(WORKER_STDERR, "a");

  child = spawn(
    POWERSHELL,
    [
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-File",
      WORKER_SCRIPT,
      "-Ipc",
      IPC,
      "-ProjectHomeUrl",
      PROJECT_HOME_URL,
      "-ProjectTitle",
      PROJECT_TITLE,
    ],
    {
      windowsHide: true,
      detached: false,
      stdio: ["ignore", out, err],
    }
  );

  const pid = child.pid;
  child.once("exit", (code, signal) => {
    child = null;
    if (!shuttingDown) {
      restartTimer = setTimeout(() => {
        restartTimer = null;
        startWorker();
      }, 1000);
    }
  });
  child.once("error", () => {
    child = null;
    if (!shuttingDown && !restartTimer) {
      restartTimer = setTimeout(() => {
        restartTimer = null;
        startWorker();
      }, 1000);
    }
  });
  return pid;
}

function stopWorker() {
  if (restartTimer) {
    clearTimeout(restartTimer);
    restartTimer = null;
  }
  const c = child;
  child = null;
  if (c) {
    try {
      c.kill();
    } catch {}
  }
}

function json(res, status, value) {
  const body = JSON.stringify(value);
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(body),
    "cache-control": "no-store",
  });
  res.end(body);
}

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  if (!chunks.length) return {};
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    return {};
  }
}

async function route(req, res) {
  const u = new URL(req.url, `http://${HOST}:${PORT}`);

  if (req.method === "GET" && u.pathname === "/health") {
    return json(res, 200, {
      ok: true,
      service: "lion-firefox-uia-node-manager",
      node_pid: process.pid,
      worker_pid: child?.pid || null,
      worker_alive: !!child,
      project: PROJECT_TITLE,
      thread_policy: THREAD_POLICY,
    });
  }

  if (req.method === "GET" && u.pathname === "/status") {
    return json(res, 200, {
      manager: {
        node_pid: process.pid,
        worker_pid: child?.pid || null,
        worker_alive: !!child,
        worker_script: WORKER_SCRIPT,
        project: PROJECT_TITLE,
        thread_policy: THREAD_POLICY,
        observed_at: now(),
      },
      mediator: safeJsonFile(STATUS_FILE, {}),
    });
  }

  if (req.method === "GET" && u.pathname === "/threads") {
    return json(res, 200, {
      schema: "lion.firefox-mediator.thread-index/v3",
      thread_policy: THREAD_POLICY,
      missions: listThreads(),
    });
  }

  if (req.method === "POST" && u.pathname === "/control/open") {
    if (!child) startWorker();
    return json(res, 200, {
      ok: true,
      worker_pid: child?.pid || null,
      mediator: safeJsonFile(STATUS_FILE, {}),
    });
  }

  if (req.method === "POST" && u.pathname === "/control/worker/restart") {
    stopWorker();
    const pid = startWorker();
    return json(res, 200, { ok: true, worker_pid: pid || child?.pid || null });
  }

  if (req.method === "POST" && u.pathname === "/control/rollover") {
    const payload = await readBody(req);
    const file = missionStatePath(payload);
    if (!file) return json(res, 400, { error: "mission identity required" });
    const state = safeJsonFile(file, null);
    if (!state) return json(res, 404, { error: "mission thread not found" });

    const generation = Number(state.generation || 0);
    for (const t of Array.isArray(state.threads) ? state.threads : []) {
      if (Number(t.generation || 0) === generation && t.state === "ACTIVE") {
        t.state = "CLOSED";
        t.close_reason = "OPERATOR_REQUESTED_ROLLOVER";
        t.closed_at = now();
        t.updated_at = t.closed_at;
      }
    }
    state.active_conversation_url = null;
    state.state = "ROLLOVER_REQUIRED";
    state.updated_at = now();
    atomicJson(file, state);
    return json(res, 200, {
      ok: true,
      mission_key: state.mission_key,
      generation,
      next_request_creates_successor: true,
    });
  }

  return json(res, 404, { error: "not_found" });
}

startWorker();

const server = http.createServer((req, res) => {
  route(req, res).catch((err) =>
    json(res, 500, { error: "internal_error", detail: String(err?.message || err) })
  );
});

server.listen(PORT, HOST, () => {
  console.log(
    JSON.stringify({
      event: "lion.firefox-uia-node-manager.started",
      at: now(),
      host: HOST,
      port: PORT,
      node_pid: process.pid,
      worker_pid: child?.pid || null,
      project: PROJECT_TITLE,
      thread_policy: THREAD_POLICY,
    })
  );
});

async function shutdown() {
  shuttingDown = true;
  stopWorker();
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 1500).unref();
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
