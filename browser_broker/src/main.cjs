'use strict';
const {app,BaseWindow,WebContentsView,Menu,dialog}=require('electron');
const fs=require('node:fs');const path=require('node:path');const {randomBytes}=require('node:crypto');
const {Store}=require('./store.cjs');
const {CanonicalConversationSaaSConsumer}=require('./canonical-conversation-consumer.cjs');
const {projectInfo}=require('./conversation.cjs');
const {EmbeddedBrowser}=require('./browser.cjs');const {createHttp}=require('./http.cjs');const {webPreferences}=require('./contract.cjs');
const PROJECT=process.env.LION_PROJECT_URL||'https://chatgpt.com/g/g-p-6a91cabd3f208191a37f295819e9f75b-lion-evolusion/project';
const PANEL=process.env.LION_PANEL_URL||'http://127.0.0.1:8780';
const MC=process.env.LION_MISSION_CONTROL_URL||'http://127.0.0.1:8766';
const INGRESS=process.env.LION_INGRESS_URL||'http://127.0.0.1:8791';
const CONTROL_PORT=Number(process.env.LION_BROWSER_CONTROL_PORT||8793);
if(!Number.isSafeInteger(CONTROL_PORT)||CONTROL_PORT<1024||CONTROL_PORT>65535)throw Error('LOOPBACK_CONTROL_PORT_REQUIRED');
for(const [name,raw] of [['PANEL',PANEL],['INGRESS',INGRESS],['MC',MC]]){const u=new URL(raw);const pathOk=u.pathname==='/';if(u.protocol!=='http:'||u.hostname!=='127.0.0.1'||u.username||u.password||!pathOk||u.search||u.hash)throw Error('LOOPBACK_SERVICE_REQUIRED')}
projectInfo(PROJECT);
if(process.env.LION_BROWSER_DATA)app.setPath('userData',path.resolve(process.env.LION_BROWSER_DATA));
app.enableSandbox();
if(!app.requestSingleInstanceLock()){app.quit()}else{
 let win,views=[],store,canonicalConsumer,server,timer;let closing=false;let activeRightTab='panel';let selectRightTab=()=>{};
 const shutdown=()=>{if(closing)return;closing=true;clearInterval(timer);try{store?.shutdown()}catch{};server?.close();for(const view of views)if(!view.webContents.isDestroyed())view.webContents.close();try{store?.close()}catch{}};
 app.on('before-quit',shutdown);
 app.on('second-instance',()=>{if(win&&!win.isDestroyed()){win.show();win.focus()}});
 app.whenReady().then(async()=>{
  const dir=app.getPath('userData');fs.mkdirSync(dir,{recursive:true});
  const keyFile=path.join(dir,'control.key');
  if(!fs.existsSync(keyFile))fs.writeFileSync(keyFile,randomBytes(32).toString('hex'),{mode:0o600,flag:'wx'});
  const token=fs.readFileSync(keyFile,'utf8').trim();
  const serviceFile=path.join(dir,'services.json'),scopeFile=path.join(dir,'thread-scope.json');
  const savedServices=fs.existsSync(serviceFile)?JSON.parse(fs.readFileSync(serviceFile,'utf8')):{};
  let ingressTokenFile=process.env.LION_INGRESS_TOKEN_FILE||savedServices.ingress_token_file;
  let ingressToken=ingressTokenFile?fs.readFileSync(ingressTokenFile,'utf8').trim():null;
  const mediatorKey=process.env.LION_MEDIATOR_KEY_FILE?fs.readFileSync(process.env.LION_MEDIATOR_KEY_FILE,'utf8').trim():null;
  store=new Store(path.join(dir,'broker.db'),PROJECT);store.recover();
  win=new BaseWindow({width:1500,height:960,title:'LION Broker — sesja SaaS',show:true});
  const panel=new WebContentsView({webPreferences:webPreferences('persist:lion-panel-r19')});
  const saas=new WebContentsView({webPreferences:webPreferences('persist:lion-saas-r19')});
  const mission=new WebContentsView({webPreferences:webPreferences('persist:lion-mission-control-r24')});
  const tabs=new WebContentsView({webPreferences:webPreferences('persist:lion-tabs-r24')});
  views=[saas,panel,mission,tabs];views.forEach(v=>win.contentView.addChildView(v));
  const authHosts=new Set(['chatgpt.com','auth.openai.com','auth0.openai.com','accounts.google.com','login.microsoftonline.com','login.live.com','appleid.apple.com']);
  for(const v of views){
   const wc=v.webContents;
   const allowed=raw=>{try{const u=new URL(raw);if(u.username||u.password)return false;if(v===panel)return u.origin===new URL(PANEL).origin;if(v===mission)return u.origin===new URL(MC).origin;if(v===tabs)return u.protocol==='data:'||u.protocol==='lion-tab:';return u.protocol==='https:'&&authHosts.has(u.hostname)}catch{return false}};
   wc.on('will-navigate',(event,url)=>{
    try{
     const u=new URL(url);
     if(v===tabs&&u.protocol==='lion-tab:'){event.preventDefault();selectRightTab(u.hostname);return}
     if(v===panel&&u.protocol==='lion-saas:'){
      event.preventDefault();
      const conversationId=decodeURIComponent(u.pathname.replace(/^\/+/,''));if(!conversationId)return;
      if(u.hostname==='open')canonicalConsumer?.openBridgeForConversation(conversationId).then(()=>selectRightTab('saas')).catch(()=>{});
      else if(u.hostname==='rotate')canonicalConsumer?.requestRotate(conversationId);
      return;
     }
    }catch{}
    if(!allowed(url))event.preventDefault()
   });
   wc.on('will-redirect',(event,url)=>{if(!allowed(url))event.preventDefault()});
   wc.setWindowOpenHandler(()=>({action:'deny'}));
   wc.on('will-attach-webview',event=>event.preventDefault());
   wc.session.setPermissionRequestHandler((webContents,permission,callback)=>callback(false));
   wc.session.setPermissionCheckHandler(()=>false);
   wc.session.on('will-download',event=>event.preventDefault());
   wc.on('render-process-gone',()=>{store.stop();win.setTitle('LION Broker — renderer stopped; operator required')});
  }
  const TAB_HEIGHT=38;
  const layout=()=>{const {width,height}=win.getContentBounds();const split=Math.floor(width*.5),rightWidth=width-split,bodyHeight=Math.max(0,height-TAB_HEIGHT);mission.setBounds({x:0,y:0,width:split,height});tabs.setBounds({x:split,y:0,width:rightWidth,height:TAB_HEIGHT});const shown={x:split,y:TAB_HEIGHT,width:rightWidth,height:bodyHeight},hidden={x:width+64,y:TAB_HEIGHT,width:rightWidth,height:bodyHeight};saas.setBounds(shown);panel.setBounds(activeRightTab==='panel'?shown:hidden)};
  selectRightTab=name=>{activeRightTab=name==='saas'?'saas':'panel';layout();win.setTitle(activeRightTab==='panel'?'LION Broker — LPCL Panel':'LION Broker — sesja SaaS')};
  const tabHtml='<!doctype html><meta charset="utf-8"><style>html,body{margin:0;height:100%;background:#0b1117;color:#dce8f2;font:13px system-ui;overflow:hidden}nav{height:100%;display:flex;align-items:end;border-bottom:1px solid #304454;padding:0 8px;box-sizing:border-box;gap:6px}a{color:#b7c9d7;text-decoration:none;padding:9px 14px 8px;border:1px solid #304454;border-bottom:0;border-radius:7px 7px 0 0;background:#121d26}a:hover{background:#1b2a36;color:white}</style><nav><a href="lion-tab://panel">LPCL PANEL</a><a href="lion-tab://saas">ChatGPT SaaS</a></nav>';
  win.on('resize',layout);selectRightTab('panel');win.on('closed',()=>app.quit());
  const browser=new EmbeddedBrowser(saas.webContents,PROJECT);
  const request=async(base,headers,route,method='GET',body)=>{
   const response=await fetch(new URL(route,base),{method,headers:{...headers,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(5000),redirect:'error'});
   if(!response.ok)throw Error('DEPENDENCY_HTTP_'+response.status);return response.json();
  };
  const ingress=(route,method,body)=>{if(!ingressToken)throw Error('INGRESS_CREDENTIAL_REQUIRED');return request(INGRESS,{'X-LION-Token':ingressToken},route,method,body)};
  const mc=(route,method,body)=>request(MC,mediatorKey?{'X-LION-Mediator-Key':mediatorKey}:{},route,method,body);
  const panelApi=(route,method,body)=>request(PANEL,{},route,method,body);
  // Legacy ThreadConsumer/AutoProjectConsumer remain retired. The successor consumes
  // only canonical conversation identities and persists explicit native SaaS bridges.
  store.stop('LEGACY_DELIVERY_RETIRED');
  canonicalConsumer=new CanonicalConversationSaaSConsumer({store,panel:panelApi,mc,ingress,browser,projectUrl:PROJECT,conversationFilter:process.env.LION_CANONICAL_SAAS_CONVERSATION_ID||null});
  canonicalConsumer.resume('R24_COMPLEMENTARY_CANONICAL_SAAS');
  const startupConversation=PROJECT;
  const source={host:require('node:os').hostname(),entrypoint:__filename,sha256:require('./contract.cjs').hash(fs.readFileSync(__filename))};
  const status=async()=>({observed_at:new Date().toISOString(),runtime:{electron:process.versions.electron,node:process.versions.node,platform:process.platform,source},ui:{left_surface:'mission_control',right_active:activeRightTab,right_tabs:['panel','saas'],panel_url:PANEL},browser:await browser.inspect(),conversation:browser.bindingReport(),ingress_credential_present:!!ingressToken,mediator_credential_present:!!mediatorKey,transport_error:canonicalConsumer?.lastError||null,engine:{running:false,lastTickAt:null,lastDecision:'RETIRED_LEGACY_DELIVERY'},relay:{state:'RETIRED_ARCHIVAL',mode:'THREAD_CONSUMER',writes_responses:false,authority_effect:'NONE'},wake_plane:{...(canonicalConsumer?.status()||{state:'STARTING'}),mode:'CANONICAL_CONVERSATION_SAAS_CONSUMER',external_saas_semantics:'EXPLICIT_BRIDGE_ONLY',authority_effect:'NONE'},canonical_saas_consumer:canonicalConsumer?.status()||null,conversation_url:'PROJECT_OR_EXPLICIT_BRIDGE_ONLY',legacy_routing_retired:true,authority_effect:'NONE'});
  const diagnose=async()=>{
   const probe=async fn=>{try{return await fn()}catch{return {state:'UNREACHABLE_OR_UNAUTHORIZED'}}};
   const [local,broker,health]=await Promise.all([status(),probe(()=>mc('/api/v3/saas/status')),probe(()=>ingress('/health'))]);
   const report={...local,stopped:store.stopped(),queue:store.rows().map(r=>({request_id:r.request_id,state:r.state})),upstream:{mission_control:{state:broker.state,session_attestation_state:broker.session_attestation_state,automatic_hop:broker.automatic_hop},ingress:{ok:health.ok===true,state:health.state}},model_identity:'UNKNOWN',live_e2e:'NOT_PROVEN'};
   fs.writeFileSync(path.join(dir,'diagnostic-r19.json'),JSON.stringify(report,null,2)+'\n',{mode:0o600});return report;
  };
  const writeConfig=(file,data)=>{const temporary=file+'.tmp';fs.writeFileSync(temporary,JSON.stringify(data,null,2)+'\n',{mode:0o600});fs.renameSync(temporary,file)};
  const bindThread=async()=>{
   store.stop();
   await dialog.showMessageBox(win,{
    type:'info',
    message:'Legacy thread binding zostało wycofane.',
    detail:'Model Chat używa canonical conversation_id. Native ChatGPT SaaS pozostaje zewnętrznym wątkiem i może zostać powiązany wyłącznie przez jawny external bridge w canonical Model Chat.'
   });
  };
  server=createHttp({store,token,status}).listen(CONTROL_PORT,'127.0.0.1');
  server.on('error',()=>{store.stop();dialog.showErrorBox('LION Broker','Nie można uruchomić portu '+CONTROL_PORT+'. Broker pozostaje zatrzymany.');app.quit()});
  Menu.setApplicationMenu(Menu.buildFromTemplate([{label:'LION',submenu:[
   {label:'Legacy thread binding — RETIRED',click:bindThread},
   {label:'Adres rozmowy SaaS',click:async()=>{await dialog.showMessageBox(win,{message:'Adres i rozpoznanie rozmowy SaaS',detail:JSON.stringify(browser.bindingReport(),null,2)})}},
   {label:'Stan / diagnostyka',click:async()=>{
    const output=path.join(dir,'diagnostic-r19.json');
    try{const report=await diagnose();await dialog.showMessageBox(win,{message:JSON.stringify(report,null,2),detail:'Raport: '+output})}
    catch{dialog.showErrorBox('LION Broker','Nie można zapisać raportu diagnostycznego.')}
   }},
   {label:'Canonical SaaS consumer — Wznów',click:()=>canonicalConsumer?.resume('LOCAL_OPERATOR_MENU')},
   {label:'Legacy queue — RETIRED',click:async()=>{store.stop();await dialog.showMessageBox(win,{type:'info',message:'Legacy queue pozostaje wyłączona.',detail:'Canonical delivery używa CanonicalConversationSaaSConsumer. ThreadConsumer i AutoProjectConsumer nie zostaną wznowione.'})}},
   {label:'STOP SaaS consumer',click:()=>canonicalConsumer?.stop('LOCAL_OPERATOR_MENU')},
   {label:'Otwórz projekt SaaS',click:()=>saas.webContents.loadURL(PROJECT).catch(()=>{})},
   {label:'Zakończ',click:()=>app.quit()}
  ]}]));
  let ticking=false;
  timer=setInterval(async()=>{if(closing||ticking)return;ticking=true;try{await canonicalConsumer?.tick()}finally{ticking=false}},1200);
  await Promise.allSettled([panel.webContents.loadURL(PANEL),saas.webContents.loadURL(startupConversation),mission.webContents.loadURL(MC),tabs.webContents.loadURL('data:text/html;charset=utf-8,'+encodeURIComponent(tabHtml))]);
  if(!closing)try{await diagnose()}catch{win.setTitle('LION Broker — raport diagnostyczny niedostępny')}
 }).catch(()=>{dialog.showErrorBox('LION Broker','Uruchomienie nie powiodło się. Sprawdź konfigurację, dostęp do plików i wymagany runtime.');app.quit()});
}
