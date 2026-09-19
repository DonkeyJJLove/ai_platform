"use strict";

const fs=require("fs");
const path=require("path");
const http=require("http");
const crypto=require("crypto");
const {spawn}=require("child_process");

const HERE=__dirname;
const HOST=process.env.LION_FIREFOX_MANAGER_HOST||"127.0.0.1";
const PORT=Number(process.env.LION_FIREFOX_MANAGER_PORT||"8790");
const IPC=process.env.LION_FIREFOX_MEDIATOR_IPC||
  "\\\\wsl.localhost\\LION-AUTH-LAB\\var\\lib\\sentinelx\\uploads\\lion-mission-control-v3\\firefox-mediator-ipc";
const PROJECT_HOME_URL=process.env.LION_FIREFOX_PROJECT_HOME_URL||
  "https://chatgpt.com/g/g-p-6a91cabd3f208191a37f295819e9f75b-lion-evolusion/project";
const PROJECT_TITLE=process.env.LION_FIREFOX_PROJECT||"LION_EVOLUSION";
const POWERSHELL=process.env.LION_POWERSHELL||
  "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe";
const UIA_SCRIPT=process.env.LION_UIA_MEDIATOR_SCRIPT||
  path.resolve(HERE,"..","firefox-mediator-app-open-session","open_session_mediator.ps1");
const BACKGROUND_SCRIPT=process.env.LION_BACKGROUND_DRIVER_SCRIPT||
  path.resolve(HERE,"background_driver.cjs");
const BG_STATUS=path.join(IPC,"node-background-driver-status.json");
const MANAGER_STATUS=path.join(IPC,"node-manager-status.json");
const THREADS_DIR=path.join(IPC,"mission-threads");
const THREAD_POLICY="ONE_CHAT_PER_MISSION_WITH_TERMINAL_ROLLOVER";

let backgroundChild=null;
let bootstrapChild=null;
let shuttingDown=false;
let restartTimer=null;

const now=()=>new Date().toISOString();
function safeJson(file,def=null){try{return JSON.parse(fs.readFileSync(file,"utf8").replace(/^\uFEFF/,""))}catch{return def}}
function atomicJson(file,value){fs.mkdirSync(path.dirname(file),{recursive:true});const t=file+".tmp";fs.writeFileSync(t,JSON.stringify(value,null,2),"utf8");fs.renameSync(t,file)}
function missionKey(payload){const m=String(payload?.mission_id||"").trim();if(m)return "mission:"+m;const st=String(payload?.scope_type||"").trim(),si=String(payload?.scope_id||"").trim();if(st&&si)return "scope:"+st+":"+si;const th=String(payload?.thread_id||"").trim();return th?"lion-thread:"+th:null}
function missionStatePath(payload){const k=missionKey(payload);return k?path.join(THREADS_DIR,crypto.createHash("sha256").update(k).digest("hex")+".json"):null}
function listThreads(){try{return fs.existsSync(THREADS_DIR)?fs.readdirSync(THREADS_DIR).filter(x=>x.endsWith(".json")).sort().map(x=>safeJson(path.join(THREADS_DIR,x))).filter(Boolean):[]}catch{return[]}}

function startBackground(){
  if(shuttingDown||backgroundChild)return backgroundChild?.pid||null;
  backgroundChild=spawn(process.execPath,[BACKGROUND_SCRIPT],{
    windowsHide:true,detached:false,stdio:["ignore","ignore","ignore"],
    env:{...process.env,LION_FIREFOX_MEDIATOR_IPC:IPC,LION_FIREFOX_PROJECT_HOME_URL:PROJECT_HOME_URL,LION_FIREFOX_PROJECT:PROJECT_TITLE}
  });
  const pid=backgroundChild.pid;
  backgroundChild.once("exit",()=>{backgroundChild=null;if(!shuttingDown){restartTimer=setTimeout(()=>{restartTimer=null;startBackground()},2000)}});
  backgroundChild.once("error",()=>{backgroundChild=null;if(!shuttingDown&&!restartTimer){restartTimer=setTimeout(()=>{restartTimer=null;startBackground()},2000)}});
  return pid;
}
function stopBackground(){
  if(restartTimer){clearTimeout(restartTimer);restartTimer=null}
  const c=backgroundChild;backgroundChild=null;
  if(c){try{c.kill()}catch{}}
}
function startBootstrap(){
  if(bootstrapChild)return bootstrapChild.pid;
  bootstrapChild=spawn(POWERSHELL,["-NoProfile","-ExecutionPolicy","Bypass","-File",UIA_SCRIPT,"-Ipc",IPC,"-ProjectHomeUrl",PROJECT_HOME_URL,"-ProjectTitle",PROJECT_TITLE],{windowsHide:false,detached:false,stdio:["ignore","ignore","ignore"]});
  const pid=bootstrapChild.pid;
  bootstrapChild.once("exit",()=>bootstrapChild=null);
  bootstrapChild.once("error",()=>bootstrapChild=null);
  return pid;
}
function stopBootstrap(){const c=bootstrapChild;bootstrapChild=null;if(c){try{c.kill()}catch{}}}

function managerSnapshot(){
  const bg=safeJson(BG_STATUS,{});
  return {
    schema:"lion.node-saas-manager.status/v1",
    service:"lion-node-saas-background-manager",
    node_pid:process.pid,
    background_driver_pid:backgroundChild?.pid||null,
    background_driver_alive:!!backgroundChild,
    bootstrap_pid:bootstrapChild?.pid||null,
    bootstrap_alive:!!bootstrapChild,
    driver_mode:"NODE_BACKGROUND",
    project:PROJECT_TITLE,
    thread_policy:THREAD_POLICY,
    observed_at:now(),
    authority_effect:"NONE",
    background: bg
  };
}
function writeManagerStatus(){try{atomicJson(MANAGER_STATUS,managerSnapshot())}catch{}}
function json(res,status,value){const body=JSON.stringify(value);res.writeHead(status,{"content-type":"application/json; charset=utf-8","content-length":Buffer.byteLength(body),"cache-control":"no-store"});res.end(body)}
async function readBody(req){const chunks=[];for await(const c of req)chunks.push(c);if(!chunks.length)return{};try{return JSON.parse(Buffer.concat(chunks).toString("utf8"))}catch{return{}}}

async function route(req,res){
  const u=new URL(req.url,`http://${HOST}:${PORT}`);
  if(req.method==="GET"&&u.pathname==="/health") return json(res,200,{ok:true,...managerSnapshot()});
  if(req.method==="GET"&&u.pathname==="/status") return json(res,200,{manager:managerSnapshot(),background:safeJson(BG_STATUS,{})});
  if(req.method==="GET"&&u.pathname==="/threads") return json(res,200,{schema:"lion.firefox-mediator.thread-index/v3",thread_policy:THREAD_POLICY,missions:listThreads()});
  if(req.method==="POST"&&u.pathname==="/control/background/restart"){stopBackground();const pid=startBackground();return json(res,200,{ok:true,background_driver_pid:pid})}
  if(req.method==="POST"&&u.pathname==="/control/bootstrap/start"){
    return json(res,200,{ok:true,bootstrap_pid:startBootstrap(),driver_mode:"LEGACY_UIA_MANUAL",interactive:true,operator_action_required:true,authority_effect:"NONE"});
  }
  if(req.method==="POST"&&u.pathname==="/control/bootstrap/stop"){stopBootstrap();return json(res,200,{ok:true})}
  if(req.method==="POST"&&u.pathname==="/control/open"){
    return json(res,409,{error:"legacy_normal_open_disabled",driver_mode:"NODE_BACKGROUND",bootstrap_endpoint:"/control/bootstrap/start"});
  }
  if(req.method==="POST"&&u.pathname==="/control/worker/restart"){
    return json(res,409,{error:"legacy_uia_worker_disabled",driver_mode:"NODE_BACKGROUND",background_restart_endpoint:"/control/background/restart"});
  }
  if(req.method==="POST"&&u.pathname==="/control/rollover"){
    const payload=await readBody(req),file=missionStatePath(payload);
    if(!file)return json(res,400,{error:"mission identity required"});
    const state=safeJson(file,null);if(!state)return json(res,404,{error:"mission thread not found"});
    const gen=Number(state.generation||0);
    for(const t of Array.isArray(state.threads)?state.threads:[])if(Number(t.generation||0)===gen&&t.state==="ACTIVE"){t.state="CLOSED";t.close_reason="OPERATOR_REQUESTED_ROLLOVER";t.closed_at=now();t.updated_at=t.closed_at}
    state.active_conversation_url=null;state.state="ROLLOVER_REQUIRED";state.updated_at=now();atomicJson(file,state);
    return json(res,200,{ok:true,mission_key:state.mission_key,generation:gen,next_request_creates_successor:true});
  }
  return json(res,404,{error:"not_found"});
}

startBackground();
writeManagerStatus();
const timer=setInterval(writeManagerStatus,5000);timer.unref();
const server=http.createServer((req,res)=>route(req,res).catch(e=>json(res,500,{error:"internal_error",detail:String(e?.message||e)})));
server.listen(PORT,HOST,()=>console.log(JSON.stringify({event:"lion.node-saas-background-manager.started",at:now(),host:HOST,port:PORT,node_pid:process.pid,background_driver_pid:backgroundChild?.pid||null,driver_mode:"NODE_BACKGROUND"})));
async function shutdown(){shuttingDown=true;stopBootstrap();stopBackground();server.close(()=>process.exit(0));setTimeout(()=>process.exit(0),1500).unref()}
process.on("SIGINT",shutdown);process.on("SIGTERM",shutdown);
