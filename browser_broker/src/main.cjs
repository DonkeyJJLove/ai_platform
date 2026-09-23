'use strict';
const {app,BaseWindow,WebContentsView,Menu,dialog}=require('electron');
const fs=require('node:fs');const path=require('node:path');const {randomBytes}=require('node:crypto');
const {Store}=require('./store.cjs');const {Engine}=require('./engine.cjs');
const {Relay}=require('./relay.cjs');
const {ThreadConsumer}=require('./thread-consumer.cjs');
const {projectInfo,conversationInfo}=require('./conversation.cjs');
const {EmbeddedBrowser}=require('./browser.cjs');const {createHttp}=require('./http.cjs');const {webPreferences,brokerAllows}=require('./contract.cjs');
const PROJECT=process.env.LION_PROJECT_URL||'https://chatgpt.com/g/g-p-6a91cabd3f208191a37f295819e9f75b-lion-evolusion/project';
const PANEL=process.env.LION_PANEL_URL||'http://127.0.0.1:8780';
const MC=process.env.LION_MISSION_CONTROL_URL||'http://127.0.0.1:8766';
const INGRESS=process.env.LION_INGRESS_URL||'http://127.0.0.1:8791';
for(const raw of [PANEL,INGRESS,MC]){const u=new URL(raw);if(u.protocol!=='http:'||u.hostname!=='127.0.0.1'||u.username||u.password||u.pathname!=='/'||u.search||u.hash)throw Error('LOOPBACK_SERVICE_REQUIRED')}
projectInfo(PROJECT);
if(process.env.LION_BROWSER_DATA)app.setPath('userData',path.resolve(process.env.LION_BROWSER_DATA));
app.enableSandbox();
if(!app.requestSingleInstanceLock()){app.quit()}else{
 let win,views=[],store,engine,server,timer;let closing=false;let activeRightTab='mission';
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
  views=[panel,saas,mission,tabs];views.forEach(v=>win.contentView.addChildView(v));
  const authHosts=new Set(['chatgpt.com','auth.openai.com','auth0.openai.com','accounts.google.com','login.microsoftonline.com','login.live.com','appleid.apple.com']);
  for(const v of views){
   const wc=v.webContents;
   const allowed=raw=>{try{const u=new URL(raw);if(u.username||u.password)return false;if(v===panel)return u.origin===new URL(PANEL).origin;if(v===mission)return u.origin===new URL(MC).origin;if(v===tabs)return u.protocol==='data:';return u.protocol==='https:'&&authHosts.has(u.hostname)}catch{return false}};
   wc.on('will-navigate',(event,url)=>{if(!allowed(url))event.preventDefault()});
   wc.on('will-redirect',(event,url)=>{if(!allowed(url))event.preventDefault()});
   wc.setWindowOpenHandler(()=>({action:'deny'}));
   wc.on('will-attach-webview',event=>event.preventDefault());
   wc.session.setPermissionRequestHandler((webContents,permission,callback)=>callback(false));
   wc.session.setPermissionCheckHandler(()=>false);
   wc.session.on('will-download',event=>event.preventDefault());
   wc.on('render-process-gone',()=>{store.stop();win.setTitle('LION Broker — renderer stopped; operator required')});
  }
  const TAB_HEIGHT=38;
  const layout=()=>{const {width,height}=win.getContentBounds();const split=Math.floor(width*.5),rightWidth=width-split,bodyHeight=Math.max(0,height-TAB_HEIGHT);panel.setBounds({x:0,y:0,width:split,height});tabs.setBounds({x:split,y:0,width:rightWidth,height:TAB_HEIGHT});const shown={x:split,y:TAB_HEIGHT,width:rightWidth,height:bodyHeight},hidden={x:split,y:TAB_HEIGHT,width:0,height:0};saas.setBounds(activeRightTab==='saas'?shown:hidden);mission.setBounds(activeRightTab==='mission'?shown:hidden)};
  const selectRightTab=name=>{activeRightTab=name==='saas'?'saas':'mission';layout();win.setTitle(activeRightTab==='mission'?'LION Broker — Mission Control':'LION Broker — sesja SaaS')};
  tabs.webContents.on('did-navigate-in-page',(_event,url)=>{try{const hash=new URL(url).hash;if(hash==='#saas')selectRightTab('saas');else if(hash==='#mission')selectRightTab('mission')}catch{}});
  const tabHtml='<!doctype html><meta charset="utf-8"><style>html,body{margin:0;height:100%;background:#0b1117;color:#dce8f2;font:13px system-ui;overflow:hidden}nav{height:100%;display:flex;align-items:end;border-bottom:1px solid #304454;padding:0 8px;box-sizing:border-box;gap:6px}a{color:#b7c9d7;text-decoration:none;padding:9px 14px 8px;border:1px solid #304454;border-bottom:0;border-radius:7px 7px 0 0;background:#121d26}a:hover{background:#1b2a36;color:white}</style><nav><a href="#mission">LION MISSION CONTROL</a><a href="#saas">ChatGPT SaaS</a></nav>';
  win.on('resize',layout);selectRightTab('mission');win.on('closed',()=>app.quit());
  const browser=new EmbeddedBrowser(saas.webContents,PROJECT);
  const request=async(base,headers,route,method='GET',body)=>{
   const response=await fetch(new URL(route,base),{method,headers:{...headers,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(5000),redirect:'error'});
   if(!response.ok)throw Error('DEPENDENCY_HTTP_'+response.status);return response.json();
  };
  const ingress=(route,method,body)=>{if(!ingressToken)throw Error('INGRESS_CREDENTIAL_REQUIRED');return request(INGRESS,{'X-LION-Token':ingressToken},route,method,body)};
  const mc=(route,method,body)=>request(MC,mediatorKey?{'X-LION-Mediator-Key':mediatorKey}:{},route,method,body);
  const getTurn=async id=>(await ingress('/v1/turns/'+encodeURIComponent(id))).turn;
  const remember=()=>{try{store.rememberConversation(saas.webContents.getURL())}catch{}};
  saas.webContents.on('did-navigate',remember);saas.webContents.on('did-navigate-in-page',remember);
  const admit=async v=>{
   if(v.mission_id===null)return relay instanceof ThreadConsumer&&relay.admits(v);
   if(typeof v.mission_id!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$/.test(v.mission_id))return false;
   if(conversationInfo(v.conversation_url,PROJECT).project_membership==='OPERATOR_CONFIRMATION_REQUIRED'&&!(relay?.scope.conversation_url===v.conversation_url&&relay.scope.thread_id===v.panel_thread_id))return false;
   const r=await fetch(MC+'/api/v3/missions/'+encodeURIComponent(v.mission_id)+'/process',{signal:AbortSignal.timeout(15000),redirect:'error'});
   if(!r.ok)return false;const m=await r.json();
   if(!(m.mission_id===v.mission_id&&['RUNNING','AUTHORIZED'].includes(m.state)&&m.execution_preflight?.mission_readiness==='READY_BOUND'))return false;
   const request=await fetch(MC+'/api/v3/saas-broker/requests/'+encodeURIComponent(v.request_id),{signal:AbortSignal.timeout(5000),redirect:'error'});
   if(!request.ok)return false;
   const row=await request.json();
   if(row.status==='WAITING_SUPERVISOR'&&v.claim_generation!==undefined){
    const refreshed=store.refreshQueuedEnvelope(v.request_id,(current)=>{delete current.claim_generation;return current},'BROKER_CLAIM_RELEASED_BEFORE_SEND');
    if(refreshed)Object.keys(v).forEach(k=>delete v[k]),Object.assign(v,refreshed.envelope);
   }
   return brokerAllows(v,row);
  };
  engine=new Engine({store,browser,getTurn,admit});
  const selectedScopeFile=process.env.LION_R19_RELAY_SCOPE_FILE||(fs.existsSync(scopeFile)?scopeFile:null);
  const relayScope=selectedScopeFile?JSON.parse(fs.readFileSync(selectedScopeFile,'utf8')):null;
  if(relayScope&&(!ingressToken||(relayScope.mode!=='THREAD_CONSUMER'&&!mediatorKey)||relayScope.task_sha256!==require('./contract.cjs').TASK))throw Error('RELAY_CONFIGURATION_REQUIRED');
  let relay=relayScope?(relayScope.mode==='THREAD_CONSUMER'?new ThreadConsumer({store,mc,ingress,scope:relayScope}):new Relay({store,browser,mc,ingress,scope:relayScope})):null;
  const startupConversation=relay instanceof ThreadConsumer?relay.scope.conversation_url:store.restoreConversation();
  const source={host:require('node:os').hostname(),entrypoint:__filename,sha256:require('./contract.cjs').hash(fs.readFileSync(__filename))};
  const status=async()=>({observed_at:new Date().toISOString(),runtime:{electron:process.versions.electron,node:process.versions.node,platform:process.platform,source},browser:await browser.inspect(),conversation:browser.bindingReport(),ingress_credential_present:!!ingressToken,mediator_credential_present:!!mediatorKey,transport_error:engine.lastError,engine:{running:engine.running,lastTickAt:engine.lastTickAt,lastDecision:engine.lastDecision},relay:relay?.status()||{state:'NOT_CONFIGURED'},conversation_url:(()=>{try{return require('./contract.cjs').conversation(saas.webContents.getURL(),PROJECT)}catch{return 'PROJECT_OR_AUTH_VIEW'}})()});
  const diagnose=async()=>{
   const probe=async fn=>{try{return await fn()}catch{return {state:'UNREACHABLE_OR_UNAUTHORIZED'}}};
   const [local,broker,health]=await Promise.all([status(),probe(()=>mc('/api/v3/saas/status')),probe(()=>ingress('/health'))]);
   const report={...local,stopped:store.stopped(),queue:store.rows().map(r=>({request_id:r.request_id,state:r.state})),upstream:{mission_control:{state:broker.state,session_attestation_state:broker.session_attestation_state,automatic_hop:broker.automatic_hop},ingress:{ok:health.ok===true,state:health.state}},model_identity:'UNKNOWN',live_e2e:'NOT_PROVEN'};
   fs.writeFileSync(path.join(dir,'diagnostic-r19.json'),JSON.stringify(report,null,2)+'\n',{mode:0o600});return report;
  };
  const writeConfig=(file,data)=>{const temporary=file+'.tmp';fs.writeFileSync(temporary,JSON.stringify(data,null,2)+'\n',{mode:0o600});fs.renameSync(temporary,file)};
  const bindThread=async()=>{
   store.stop();
   const stopRevision=store.stopRevision();
   try{
    const location=conversationInfo(saas.webContents.getURL(),PROJECT),conversationUrl=location.url;
    const needsProjectConfirmation=location.project_membership==='OPERATOR_CONFIRMATION_REQUIRED';
    const pending=await mc('/api/v3/saas-broker/pending');
    const choices=[...new Map((pending.requests||[]).filter(r=>r.scope_type==='THREAD'&&r.mission_id===null&&r.scope_id===r.thread_id&&r.authority_effect==='NONE'&&r.transport==='CHATGPT_SENTINELX_MCP').map(r=>[r.thread_id,r])).values()].slice(-8);
    if(!choices.length)throw Error('PANEL_THREAD_REQUIRED');
    const selection=await dialog.showMessageBox(win,{type:'question',message:'Wybierz wątek panelu dla nowych pytań do tej rozmowy SaaS.',detail:'Rozmowa SaaS: '+conversationUrl+'\nIstniejące i przeterminowane pytania nie zostaną ponownie wysłane.',...(needsProjectConfirmation?{checkboxLabel:'Potwierdzam: rozmowa po prawej należy do projektu LION_EVOLUSION',checkboxChecked:false}:{}),buttons:[...choices.map(r=>String(r.question).slice(0,45)+' · '+r.thread_id.slice(-8)),'Anuluj'],cancelId:choices.length,noLink:true});
    if(selection.response===choices.length)return;
    if(needsProjectConfirmation&&!selection.checkboxChecked)throw Error('PROJECT_CONFIRMATION_REQUIRED');
    if(!ingressToken){
     const picked=await dialog.showOpenDialog(win,{title:'Wskaż istniejący plik dostępu do lokalnego ingress MCP (secure-mcp-ingress.token)',properties:['openFile']});
     if(picked.canceled||!picked.filePaths[0])return;
     const pickedToken=fs.readFileSync(picked.filePaths[0],'utf8').trim();
     const check=await request(INGRESS,{'X-LION-Token':pickedToken},'/v1/state');
     if(!Number.isSafeInteger(check.seq)||check.seq<0)throw Error('INGRESS_CURSOR_REQUIRED');
     ingressTokenFile=picked.filePaths[0];ingressToken=pickedToken;
    }
    const experience=(await browser.inspect()).experience;if(experience!=='CHAT')throw Error('WORK_MODE_FORBIDDEN');
    const scope={mode:'THREAD_CONSUMER',experience:'CHAT',mission_id:null,thread_id:choices[selection.response].thread_id,conversation_url:conversationUrl,task_sha256:require('./contract.cjs').TASK};
    if(needsProjectConfirmation)scope.project_confirmation={method:'NATIVE_OPERATOR',project_url:PROJECT,conversation_url:conversationUrl};
    const candidate=new ThreadConsumer({store,mc,ingress,scope});await candidate.prime();
    if(!await browser.ready({conversation_url:conversationUrl}))throw Error('SAAS_COMPOSER_REQUIRED');
    if(closing||store.stopRevision()!==stopRevision)return;
    writeConfig(serviceFile,{ingress_token_file:ingressTokenFile});writeConfig(scopeFile,scope);
    relay=candidate;store.resume();await diagnose();
    await dialog.showMessageBox(win,{message:'Połączono dla nowych pytań.',detail:'Wyślij jedno nowe pytanie z panelu po lewej. Odpowiedź jest oczekiwana przez rzeczywistą turę MCP; model i pełne dostarczenie nie są jeszcze potwierdzone.'});
   }catch(e){
    if(!closing)store.stop();
    const known={INVALID_CONVERSATION:'Widok nie ma prawidłowego adresu rozmowy ChatGPT.',PROJECT_LANDING_PAGE:'Otwarta jest strona projektu. Wybierz konkretną rozmowę.',PROJECT_ID_MISMATCH:'Identyfikator projektu w adresie rozmowy różni się od skonfigurowanego projektu.',CONVERSATION_ROUTE_UNSUPPORTED:'Nie rozpoznano formatu adresu rozmowy. Adres jest podany poniżej.',CONVERSATION_PARAMETERS_UNSUPPORTED:'Adres zawiera parametry lub fragment. Ich znaczenie wymaga sprawdzenia przed powiązaniem.',PROJECT_CONFIRMATION_REQUIRED:'Adres /c/ nie określa projektu. Zaznacz potwierdzenie projektu przy wyborze wątku.',PANEL_THREAD_REQUIRED:'Brak wątku panelu w kolejce. Wyślij jedno pytanie z wybranym CHATGPT, potem powiąż wątek.',SAAS_COMPOSER_REQUIRED:'Pole wiadomości SaaS nie jest gotowe lub zawiera tekst.',WORK_MODE_FORBIDDEN:'LION wymaga zwyklego Chat w projekcie LION_EVOLUSION. Tryb Work jest zabroniony dla tego kanalu.'};
    const report=browser.bindingReport(),reason=/^[A-Z_0-9]+$/.test(e.message)?e.message:'BINDING_FAILED';
    try{fs.writeFileSync(path.join(dir,'binding-error-r19.json'),JSON.stringify({observed_at:new Date().toISOString(),reason,conversation:report},null,2)+'\n',{mode:0o600})}catch{}
    dialog.showErrorBox('Połączenie LION',(known[e.message]||'Nie udało się zweryfikować usług lokalnych lub pliku dostępu.')+'\n\nKod: '+reason+'\nAdres (bez parametrów): '+report.address+'\nProjekt: '+PROJECT+'\nKolejka pozostaje zatrzymana.');
   }
  };
  server=createHttp({store,token,status}).listen(8793,'127.0.0.1');
  server.on('error',()=>{store.stop();dialog.showErrorBox('LION Broker','Nie można uruchomić portu 8793. Broker pozostaje zatrzymany.');app.quit()});
  Menu.setApplicationMenu(Menu.buildFromTemplate([{label:'LION',submenu:[
   {label:'Połącz rozmowę SaaS z wątkiem panelu',click:bindThread},
   {label:'Adres rozmowy SaaS',click:async()=>{await dialog.showMessageBox(win,{message:'Adres i rozpoznanie rozmowy SaaS',detail:JSON.stringify(browser.bindingReport(),null,2)})}},
   {label:'Stan / diagnostyka',click:async()=>{
    const output=path.join(dir,'diagnostic-r19.json');
    try{const report=await diagnose();await dialog.showMessageBox(win,{message:JSON.stringify(report,null,2),detail:'Raport: '+output})}
    catch{dialog.showErrorBox('LION Broker','Nie można zapisać raportu diagnostycznego.')}
   }},
   {label:'Wznów kolejkę po zalogowaniu',click:async()=>{if(!ingressToken){dialog.showErrorBox('LION Broker','Brak pliku dostępu do lokalnego MCP. Użyj menu połączenia rozmowy.');return}const revision=store.stopRevision();try{if(relay instanceof ThreadConsumer&&relay.cursor===null)await relay.prime();if(!closing&&store.stopRevision()===revision)store.resume()}catch{dialog.showErrorBox('LION Broker','Ingress MCP jest niedostępny. Kolejka pozostaje zatrzymana.')}}},
   {label:'STOP',click:()=>store.stop()},
   {label:'Otwórz projekt SaaS',click:()=>{store.stop();saas.webContents.loadURL(PROJECT).catch(()=>{})}},
   {label:'Zakończ',click:()=>app.quit()}
  ]}]));
  let ticking=false;
  timer=setInterval(async()=>{if(ticking||closing)return;ticking=true;try{await relay?.tick();if(!closing)await engine.tick()}finally{ticking=false}},2000);
  await Promise.allSettled([panel.webContents.loadURL(PANEL),saas.webContents.loadURL(startupConversation),mission.webContents.loadURL(MC),tabs.webContents.loadURL('data:text/html;charset=utf-8,'+encodeURIComponent(tabHtml))]);
  if(!closing)try{await diagnose()}catch{win.setTitle('LION Broker — raport diagnostyczny niedostępny')}
 }).catch(()=>{dialog.showErrorBox('LION Broker','Uruchomienie nie powiodło się. Sprawdź konfigurację, dostęp do plików i wymagany runtime.');app.quit()});
}
