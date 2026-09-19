"use strict";
const fs=require("fs"), path=require("path");
const {spawn,spawnSync}=require("child_process");
const IPC=process.env.LION_FIREFOX_MEDIATOR_IPC||"\\\\wsl.localhost\\LION-AUTH-LAB\\var\\lib\\sentinelx\\uploads\\lion-mission-control-v3\\firefox-mediator-ipc";
const PROJECT=process.env.LION_FIREFOX_PROJECT_HOME_URL||"https://chatgpt.com/g/g-p-6a91cabd3f208191a37f295819e9f75b-lion-evolusion/project";
const PROFILE="C:/Users/d2j3/AppData/Local/LION/saas-background-profile-r1";
const EDGE="C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const PS="C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe";
const WORKER=process.env.LION_EDGE_UIA_WORKER||path.resolve(__dirname,"edge_session_worker.ps1");
const STATUS=path.join(IPC,"node-background-driver-status.json");
const MEDIATOR_STATUS=path.join(IPC,"mediator-status.json");
const now=()=>new Date().toISOString();
function read(p,d={}){try{return JSON.parse(fs.readFileSync(p,"utf8").replace(/^\uFEFF/,""))}catch{return d}}
function atomic(p,v){fs.mkdirSync(path.dirname(p),{recursive:true});const t=p+".tmp";fs.writeFileSync(t,JSON.stringify(v,null,2));fs.renameSync(t,p)}
let edge=null,worker=null,stopping=false;
function write(){
 const m=read(MEDIATOR_STATUS,{});
 const ready=!!edge&&!!worker&&m.state==="READY"&&m.project_verified===true;
 atomic(STATUS,{schema:"lion.node-saas-background-driver.status/v1",driver_mode:"NODE_BACKGROUND",execution_bridge:"MINIMIZED_EDGE_UIA",state:ready?"READY":m.state||"STARTING",browser_engine:"msedge",background:true,visible_window_count:0,authenticated:ready,project_verified:ready,project_url:PROJECT,edge_pid:edge?.pid||null,worker_pid:worker?.pid||null,observed_at:now(),authority_effect:"NONE",mediator:m});
}
function killTree(p){if(!p?.pid)return;try{spawnSync("taskkill.exe",["/PID",String(p.pid),"/T","/F"],{windowsHide:true,stdio:"ignore",cwd:"C:/Windows/System32"})}catch{}}
function launch(){
 edge=spawn(EDGE,[`--user-data-dir=${PROFILE}`,"--start-minimized","--no-first-run","--no-default-browser-check","--disable-session-crashed-bubble","--hide-crash-restore-bubble","--force-renderer-accessibility",PROJECT],{windowsHide:true,stdio:"ignore",cwd:"C:/Windows/System32"});
 worker=spawn(PS,["-NoProfile","-ExecutionPolicy","Bypass","-File",WORKER,"-Ipc",IPC,"-ProjectHomeUrl",PROJECT,"-ProjectTitle","LION_EVOLUSION"],{windowsHide:true,stdio:"ignore",cwd:"C:/Windows/System32"});
 const fail=()=>{if(stopping)return;write();setTimeout(()=>{if(!stopping){killTree(worker);killTree(edge);launch()}},3000)};
 edge.once("exit",fail);worker.once("exit",fail);edge.once("error",fail);worker.once("error",fail);
}
process.on("SIGTERM",()=>{stopping=true;killTree(worker);killTree(edge);process.exit(0)});
launch();setInterval(write,2000).unref();write();
