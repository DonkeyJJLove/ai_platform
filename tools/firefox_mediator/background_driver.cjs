"use strict";
const fs=require("fs"), path=require("path"), crypto=require("crypto");
const PLAYWRIGHT=process.env.LION_PLAYWRIGHT_MODULE ||
  "C:/Users/d2j3/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright";
const {chromium}=require(PLAYWRIGHT);
const IPC=process.env.LION_FIREFOX_MEDIATOR_IPC ||
  "\\\\wsl.localhost\\LION-AUTH-LAB\\var\\lib\\sentinelx\\uploads\\lion-mission-control-v3\\firefox-mediator-ipc";
const PROJECT=process.env.LION_FIREFOX_PROJECT_HOME_URL ||
  "https://chatgpt.com/g/g-p-6a91cabd3f208191a37f295819e9f75b-lion-evolusion/project";
const PROFILE=process.env.LION_SAAS_BACKGROUND_PROFILE ||
  "C:/Users/d2j3/AppData/Local/LION/saas-background-profile-r1";
const STATUS=path.join(IPC,"node-background-driver-status.json");
const INBOX=path.join(IPC,"inbox"), OUTBOX=path.join(IPC,"outbox"), JOURNAL=path.join(IPC,"journal"), THREADS=path.join(IPC,"mission-threads");
for(const d of [IPC,INBOX,OUTBOX,JOURNAL,THREADS,PROFILE]) fs.mkdirSync(d,{recursive:true});
const now=()=>new Date().toISOString();
function atomic(p,v){const t=p+".tmp";fs.writeFileSync(t,JSON.stringify(v,null,2));fs.renameSync(t,p)}
function read(p,d=null){try{return JSON.parse(fs.readFileSync(p,"utf8").replace(/^\uFEFF/,""))}catch{return d}}
function digest(s){return crypto.createHash("sha256").update(String(s)).digest("hex")}
function key(w){return w.mission_id?("mission:"+w.mission_id):(w.scope_type&&w.scope_id?("scope:"+w.scope_type+":"+w.scope_id):("thread:"+w.thread_id))}
function threadFile(w){return path.join(THREADS,digest(key(w))+".json")}
let ctx=null,page=null,state="STARTING",authenticated=false,projectVerified=false,currentUrl=null,activeThread=null,conversationUrl=null;
function status(extra={}){atomic(STATUS,{schema:"lion.node-saas-background-driver.status/v1",driver_mode:"NODE_BACKGROUND",state,browser_engine:"chromium-msedge",background:true,visible_window_count:0,authenticated,project_verified:projectVerified,project_url:PROJECT,active_thread_id:activeThread,conversation_url:conversationUrl,observed_at:now(),authority_effect:"NONE",...extra})}
async function verifyProject(){
  await page.goto(PROJECT,{waitUntil:"domcontentloaded",timeout:45000});
  currentUrl=page.url();
  const prompt=page.locator("#prompt-textarea");
  const ok=await prompt.count().catch(()=>0);
  authenticated=!!ok && !/auth|login/i.test(currentUrl);
  projectVerified=authenticated && currentUrl.includes("chatgpt.com/");
  state=projectVerified?"READY":"LOGIN_REQUIRED";
  status({current_url:currentUrl});
  return projectVerified;
}
async function ensureConversation(w){
  const f=threadFile(w), s=read(f,{});
  if(s.active_conversation_url){
    await page.goto(/^https?:/.test(s.active_conversation_url)?s.active_conversation_url:"https://"+s.active_conversation_url,{waitUntil:"domcontentloaded",timeout:45000});
    if(await page.locator("#prompt-textarea").count()){conversationUrl=page.url();activeThread=w.thread_id||null;return}
  }
  await verifyProject(); conversationUrl=null;
}
async function send(w){
  const jp=path.join(JOURNAL,w.request_id+".node.json");
  const old=read(jp,{});
  if(["SEND_CONFIRMED","RESPONSE_RECONCILED","OUTBOX_WRITTEN"].includes(old.state)) return;
  await ensureConversation(w);
  if(state!=="READY") return;
  atomic(jp,{request_id:w.request_id,state:"INTENT_DURABLE",question_digest:w.question_digest,conversation_url:conversationUrl,updated_at:now(),authority_effect:"NONE"});
  const prompt=page.locator("#prompt-textarea");
  await prompt.click(); await prompt.fill(w.question);
  const sendBtn=page.locator('[data-testid="send-button"]');
  if(await sendBtn.count()) await sendBtn.click(); else await prompt.press("Enter");
  atomic(jp,{request_id:w.request_id,state:"SEND_CONFIRMED",question_digest:w.question_digest,conversation_url:page.url(),updated_at:now(),authority_effect:"NONE"});
  const deadline=Date.now()+180000; let answer="";
  while(Date.now()<deadline){
    await page.waitForTimeout(1000);
    const els=page.locator('[data-message-author-role="assistant"]');
    const n=await els.count();
    if(n){const txt=(await els.nth(n-1).innerText().catch(()=>"")).trim();if(txt) answer=txt}
    const stop=await page.locator('[data-testid="stop-button"]').count().catch(()=>0);
    if(answer&&!stop) break;
  }
  if(!answer) throw new Error("ASSISTANT_RESPONSE_TIMEOUT");
  const url=page.url(); conversationUrl=url; activeThread=w.thread_id||null;
  const tf=threadFile(w), ts=read(tf,{mission_key:key(w),generation:1,threads:[]});
  ts.active_conversation_url=url;ts.state="ACTIVE";ts.updated_at=now();
  atomic(tf,ts);
  atomic(path.join(OUTBOX,w.request_id+".json"),{request_id:w.request_id,claim_generation:w.claim_generation,answer,model_identity:"ChatGPT UI / Node background / LION_EVOLUSION",transport:"CHATGPT_FIREFOX_PROJECT_MEDIATED",authority_effect:"NONE",project_title:"LION_EVOLUSION",thread_id:w.thread_id,conversation_url:url,thread_policy:"ONE_CHAT_PER_MISSION_WITH_TERMINAL_ROLLOVER",new_thread_per_request:false});
  atomic(jp,{request_id:w.request_id,state:"OUTBOX_WRITTEN",conversation_url:url,response_digest:digest(answer),updated_at:now(),authority_effect:"NONE"});
}
async function loop(){
  try{
    ctx=await chromium.launchPersistentContext(PROFILE,{channel:"msedge",headless:true,viewport:{width:1280,height:900}});
    page=ctx.pages()[0]||await ctx.newPage();
    await verifyProject();
    while(true){
      status({current_url:page.url()});
      if(state==="READY"){
        const names=fs.readdirSync(INBOX).filter(x=>x.endsWith(".json")).sort();
        for(const n of names){const w=read(path.join(INBOX,n));if(!w||w.transport!=="CHATGPT_FIREFOX_PROJECT_MEDIATED") continue;await send(w);break}
      } else { await verifyProject().catch(()=>{}); }
      await new Promise(r=>setTimeout(r,1500));
    }
  }catch(e){state="DEGRADED";status({error:String(e&&e.message||e)});process.exitCode=1}
}
process.on("SIGTERM",async()=>{try{await ctx?.close()}catch{} process.exit(0)});
loop();
