'use strict';
const {app,BaseWindow,WebContentsView,Menu,dialog}=require('electron');
const fs=require('node:fs');const path=require('node:path');const {randomBytes}=require('node:crypto');
const {Store}=require('./store.cjs');const {Engine}=require('./engine.cjs');
const {Relay}=require('./relay.cjs');
const {ThreadConsumer}=require('./thread-consumer.cjs');
const {EmbeddedBrowser}=require('./browser.cjs');const {createHttp}=require('./http.cjs');const {webPreferences,brokerAllows}=require('./contract.cjs');
const PROJECT=process.env.LION_PROJECT_URL||'https://chatgpt.com/g/g-p-6a91cabd3f208191a37f295819e9f75b-lion-evolusion/project';
const PANEL=process.env.LION_PANEL_URL||'http://127.0.0.1:8780';
const MC=process.env.LION_MISSION_CONTROL_URL||'http://127.0.0.1:8766';
const INGRESS=process.env.LION_INGRESS_URL||'http://127.0.0.1:8791';
for(const raw of [PANEL,INGRESS,MC]){const u=new URL(raw);if(u.protocol!=='http:'||u.hostname!=='127.0.0.1'||u.username||u.password||u.pathname!=='/'||u.search||u.hash)throw Error('LOOPBACK_SERVICE_REQUIRED')}
if(new URL(PROJECT).origin!=='https://chatgpt.com'||!/^\/g\/g-p-[\w-]+\/project$/.test(new URL(PROJECT).pathname))throw Error('PROJECT_REQUIRED');
if(process.env.LION_BROWSER_DATA)app.setPath('userData',path.resolve(process.env.LION_BROWSER_DATA));
app.enableSandbox();
if(!app.requestSingleInstanceLock()){app.quit()}else{
 let win,views=[],store,engine,server,timer;let closing=false;
 const shutdown=()=>{if(closing)return;closing=true;clearInterval(timer);try{store?.stop()}catch{};server?.close();for(const view of views)if(!view.webContents.isDestroyed())view.webContents.close();try{store?.close()}catch{}};
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
  views=[panel,saas];views.forEach(v=>win.contentView.addChildView(v));
  const authHosts=new Set(['chatgpt.com','auth.openai.com','auth0.openai.com','accounts.google.com','login.microsoftonline.com','login.live.com','appleid.apple.com']);
  for(const v of views){
   const wc=v.webContents;
   const allowed=raw=>{try{const u=new URL(raw);return !u.username&&!u.password&&(v===panel?u.origin===new URL(PANEL).origin:u.protocol==='https:'&&authHosts.has(u.hostname))}catch{return false}};
   wc.on('will-navigate',(event,url)=>{if(!allowed(url))event.preventDefault()});
   wc.on('will-redirect',(event,url)=>{if(!allowed(url))event.preventDefault()});
   wc.setWindowOpenHandler(()=>({action:'deny'}));
   wc.on('will-attach-webview',event=>event.preventDefault());
   wc.session.setPermissionRequestHandler((webContents,permission,callback)=>callback(false));
   wc.session.setPermissionCheckHandler(()=>false);
   wc.session.on('will-download',event=>event.preventDefault());
   wc.on('render-process-gone',()=>{store.stop();win.setTitle('LION Broker — renderer stopped; operator required')});
  }
  const layout=()=>{const {width,height}=win.getContentBounds();const split=Math.floor(width*.5);panel.setBounds({x:0,y:0,width:split,height});saas.setBounds({x:split,y:0,width:width-split,height})};
  win.on('resize',layout);layout();win.on('closed',()=>app.quit());
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
   if(!v.mission_id.startsWith('LION-R19-'))return false;
   const r=await fetch(MC+'/api/v3/missions/'+encodeURIComponent(v.mission_id)+'/process',{signal:AbortSignal.timeout(5000),redirect:'error'});
   if(!r.ok)return false;const m=await r.json();
   if(!(m.mission_id===v.mission_id&&['RUNNING','AUTHORIZED'].includes(m.state)&&m.execution_preflight?.mission_readiness==='READY_BOUND'))return false;
   const request=await fetch(MC+'/api/v3/saas/requests/'+encodeURIComponent(v.request_id),{signal:AbortSignal.timeout(5000),redirect:'error'});
   return request.ok&&brokerAllows(v,await request.json());
  };
  engine=new Engine({store,browser,getTurn,admit});
  const selectedScopeFile=process.env.LION_R19_RELAY_SCOPE_FILE||(fs.existsSync(scopeFile)?scopeFile:null);
  const relayScope=selectedScopeFile?JSON.parse(fs.readFileSync(selectedScopeFile,'utf8')):null;
  if(relayScope&&(!ingressToken||(relayScope.mode!=='THREAD_CONSUMER'&&!mediatorKey)||relayScope.task_sha256!==require('./contract.cjs').TASK))throw Error('RELAY_CONFIGURATION_REQUIRED');
  let relay=relayScope?(relayScope.mode==='THREAD_CONSUMER'?new ThreadConsumer({store,mc,ingress,scope:relayScope}):new Relay({store,browser,mc,ingress,scope:relayScope})):null;
  const source={host:require('node:os').hostname(),entrypoint:__filename,sha256:require('./contract.cjs').hash(fs.readFileSync(__filename))};
  const status=async()=>({observed_at:new Date().toISOString(),runtime:{electron:process.versions.electron,node:process.versions.node,platform:process.platform,source},browser:await browser.inspect(),ingress_credential_present:!!ingressToken,mediator_credential_present:!!mediatorKey,transport_error:engine.lastError,relay:relay?.status()||{state:'NOT_CONFIGURED'},conversation_url:(()=>{try{return require('./contract.cjs').conversation(saas.webContents.getURL(),PROJECT)}catch{return 'PROJECT_OR_AUTH_VIEW'}})()});
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
    const conversationUrl=require('./contract.cjs').conversation(saas.webContents.getURL(),PROJECT);
    const pending=await mc('/api/v3/saas-broker/pending');
    const choices=[...new Map((pending.requests||[]).filter(r=>r.scope_type==='THREAD'&&r.mission_id===null&&r.scope_id===r.thread_id&&r.authority_effect==='NONE'&&r.transport==='CHATGPT_OPENAI_SECURE_MCP_TUNNEL').map(r=>[r.thread_id,r])).values()].slice(-8);
    if(!choices.length)throw Error('PANEL_THREAD_REQUIRED');
    const selection=await dialog.showMessageBox(win,{type:'question',message:'Wybierz wątek panelu dla nowych pytań do tej rozmowy SaaS.',detail:'Istniejące i przeterminowane pytania nie zostaną ponownie wysłane.',buttons:[...choices.map(r=>String(r.question).slice(0,45)+' · '+r.thread_id.slice(-8)),'Anuluj'],cancelId:choices.length,noLink:true});
    if(selection.response===choices.length)return;
    if(!ingressToken){
     const picked=await dialog.showOpenDialog(win,{title:'Wskaż istniejący plik dostępu do lokalnego ingress MCP (secure-mcp-ingress.token)',properties:['openFile']});
     if(picked.canceled||!picked.filePaths[0])return;
     const pickedToken=fs.readFileSync(picked.filePaths[0],'utf8').trim();
     const check=await request(INGRESS,{'X-LION-Token':pickedToken},'/v1/state');
     if(!Number.isSafeInteger(check.seq)||check.seq<0)throw Error('INGRESS_CURSOR_REQUIRED');
     ingressTokenFile=picked.filePaths[0];ingressToken=pickedToken;
    }
    const scope={mode:'THREAD_CONSUMER',mission_id:null,thread_id:choices[selection.response].thread_id,conversation_url:conversationUrl,task_sha256:require('./contract.cjs').TASK};
    const candidate=new ThreadConsumer({store,mc,ingress,scope});await candidate.prime();
    if(!await browser.ready({conversation_url:conversationUrl}))throw Error('SAAS_COMPOSER_REQUIRED');
    if(closing||store.stopRevision()!==stopRevision)return;
    writeConfig(serviceFile,{ingress_token_file:ingressTokenFile});writeConfig(scopeFile,scope);
    relay=candidate;store.resume();await diagnose();
    await dialog.showMessageBox(win,{message:'Połączono dla nowych pytań.',detail:'Wyślij jedno nowe pytanie z panelu po lewej. Odpowiedź jest oczekiwana przez rzeczywistą turę MCP; model i pełne dostarczenie nie są jeszcze potwierdzone.'});
   }catch(e){
    const known={INVALID_CONVERSATION:'Otwórz po prawej konkretną rozmowę w projekcie LION, potem wybierz połączenie ponownie.',PANEL_THREAD_REQUIRED:'Brak wątku panelu w kolejce. Wyślij jedno pytanie z wybranym CHATGPT, potem powiąż wątek.',SAAS_COMPOSER_REQUIRED:'Pole wiadomości SaaS nie jest gotowe lub zawiera tekst.'};
    dialog.showErrorBox('Połączenie LION',known[e.message]||'Nie udało się zweryfikować usług lokalnych lub pliku dostępu. Kolejka pozostaje zatrzymana.');
   }
  };
  server=createHttp({store,token,status}).listen(8793,'127.0.0.1');
  server.on('error',()=>{store.stop();dialog.showErrorBox('LION Broker','Nie można uruchomić portu 8793. Broker pozostaje zatrzymany.');app.quit()});
  Menu.setApplicationMenu(Menu.buildFromTemplate([{label:'LION',submenu:[
   {label:'Połącz rozmowę SaaS z wątkiem panelu',click:bindThread},
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
  await Promise.allSettled([panel.webContents.loadURL(PANEL),saas.webContents.loadURL(store.restoreConversation())]);
  if(!closing)try{await diagnose()}catch{win.setTitle('LION Broker — raport diagnostyczny niedostępny')}
 }).catch(()=>{dialog.showErrorBox('LION Broker','Uruchomienie nie powiodło się. Sprawdź konfigurację, dostęp do plików i wymagany runtime.');app.quit()});
}
