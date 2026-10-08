'use strict';
const {app,BaseWindow,WebContentsView,Menu,dialog,ipcMain,shell}=require('electron');
const fs=require('node:fs');const path=require('node:path');const {randomBytes}=require('node:crypto');const {pathToFileURL}=require('node:url');
const {Store}=require('./store.cjs');
const {CanonicalConversationSaaSConsumer}=require('./canonical-conversation-consumer.cjs');
const {projectInfo}=require('./conversation.cjs');
const {EmbeddedBrowser}=require('./browser.cjs');const {createHttp}=require('./http.cjs');const {webPreferences}=require('./contract.cjs');
const {createReadModel}=require('./desktop-read-model.cjs');
const {createLocalAdvisory}=require('./local-advisory.cjs');
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
 let win,views=[],store,canonicalConsumer,server,timer;let closing=false;
 let activeLeftTab='mission',activeRightTab='panel';
 let operatorViewProof={state:'NOT_YET_OBSERVED',authority_effect:'NONE'};
 let selectLeftTab=()=>{},selectRightTab=()=>{},refreshVisible=()=>{};
 const shutdown=()=>{if(closing)return;closing=true;clearInterval(timer);
  for(const name of ['lion:observe-readonly','lion:local-health','lion:local-advisory'])ipcMain.removeHandler(name);
  try{store?.shutdown()}catch{};server?.close();
  for(const view of views)if(!view.webContents.isDestroyed())view.webContents.close();
  try{store?.close()}catch{}
 };
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
  const overviewFile=path.join(__dirname,'..','observability-preview','LION_Cluster_System_Tabs_Preview.html');
  const overviewSha256='e80ed7f07087194f0b051738147e6bf43a314e3e1ef935899986fa86a63eae01';
  const localFile=path.join(__dirname,'..','local-gpt.html');
  const localSha256='642bd04bfc9f8e7bc59c2bdac94cf18cd8207f9fadfd6e92afe99743d2e51468';
  const pinned={'desktop-read-model.cjs':'002986161495e6ebb2ae95f1bb2d569d86582635965a2bd9c1c9a5b2f105d62c','local-advisory.cjs':'9ca8278b2f70435e71689723bfb8e749d73166a775abf20749ae8870aa36e987','fleet-carrier-read-model.cjs':'6aa301a6d435ac2a7c20e12e9dad8ba5168b77cacdab9e0aefc4acf84856ae7c','observer-preload.cjs':'d8be9fbf23c3208d455fd584792ac8e7753a87cdbbd4ec1ab38458975f1b978c','local-preload.cjs':'79bc4b5d86fa853b725b05e89ce37b65527e0da1c8f1a5895e42a5485bf61322'};
  for(const [name,expected] of Object.entries(pinned)){
   const f=path.join(__dirname,name);
   if(!fs.existsSync(f)||require('./contract.cjs').hash(fs.readFileSync(f))!==expected)
    throw Error('LION_PINNED_MODULE_IDENTITY_DRIFT_'+name);
  }
  for(const [f,expected] of [[overviewFile,overviewSha256],[localFile,localSha256]]){
   if(!fs.existsSync(f)||require('./contract.cjs').hash(fs.readFileSync(f))!==expected)
    throw Error('LION_PINNED_UI_IDENTITY_DRIFT');
  }
  const overviewURL=pathToFileURL(overviewFile).href;
  const localURL=pathToFileURL(localFile).href;
  const readModel=createReadModel({root:path.resolve(__dirname,'..','..','..','..')});
  const localAdvisory=createLocalAdvisory();
  win=new BaseWindow({width:1500,height:960,title:'LION Broker — sesja SaaS',show:true});
  const panel=new WebContentsView({webPreferences:webPreferences('persist:lion-panel-r19')});
  const saas=new WebContentsView({webPreferences:webPreferences('persist:lion-saas-r19')});
  const mission=new WebContentsView({webPreferences:webPreferences('persist:lion-mission-control-r24')});
  const leftTabs=new WebContentsView({webPreferences:webPreferences('lion-left-tabs-r4')});
  const rightTabs=new WebContentsView({webPreferences:webPreferences('lion-right-tabs-r4')});
  const observerPrefs=label=>({...webPreferences(label),preload:path.join(__dirname,'observer-preload.cjs')});
  const cluster=new WebContentsView({webPreferences:observerPrefs('lion-cluster-readonly-r4')});
  const system=new WebContentsView({webPreferences:observerPrefs('lion-system-readonly-r4')});
  const local=new WebContentsView({webPreferences:{...webPreferences('lion-local-advisory-r4'),preload:path.join(__dirname,'local-preload.cjs')}});
  views=[saas,panel,local,cluster,system,mission,leftTabs,rightTabs];
  views.forEach(v=>win.contentView.addChildView(v));
  ipcMain.handle('lion:observe-readonly',async(event)=>{
   if(event.sender===cluster.webContents)return readModel.observe('cluster');
   if(event.sender===system.webContents)return readModel.observe('system');
   throw Error('OBSERVATION_SENDER_NOT_ADMITTED');
  });
  ipcMain.handle('lion:local-health',async(event)=>{
   if(event.sender!==local.webContents)throw Error('LOCAL_SENDER_NOT_ADMITTED');
   return localAdvisory.status();
  });
  ipcMain.handle('lion:local-advisory',async(event,payload)=>{
   if(event.sender!==local.webContents)throw Error('LOCAL_SENDER_NOT_ADMITTED');
   return localAdvisory.ask(payload);
  });
  const authHosts=new Set(['chatgpt.com','auth.openai.com','auth0.openai.com','accounts.google.com','login.microsoftonline.com','login.live.com','appleid.apple.com']);
  for(const v of views){
   const wc=v.webContents;
   const allowed=raw=>{try{const u=new URL(raw);if(u.username||u.password)return false;if(v===panel)return u.origin===new URL(PANEL).origin;if(v===mission)return u.origin===new URL(MC).origin;if(v===cluster||v===system)return u.href.split('#')[0]===overviewURL&&['','#system'].includes(u.hash)&&!u.search;
     if(v===local)return u.href.split('#')[0]===localURL&&!u.hash&&!u.search;
     if(v===leftTabs)return u.protocol==='data:'||u.protocol==='lion-left:';
     if(v===rightTabs)return u.protocol==='data:'||u.protocol==='lion-right:';return u.protocol==='https:'&&authHosts.has(u.hostname)}catch{return false}};
   wc.on('will-navigate',(event,url)=>{
    try{
     const u=new URL(url);
     if(v===leftTabs&&u.protocol==='lion-left:'){event.preventDefault();selectLeftTab(u.hostname);return}
      if(v===rightTabs&&u.protocol==='lion-right:'){event.preventDefault();selectRightTab(u.hostname);return}
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
  const TAB_HEIGHT=39;
  const tabStyle='<!doctype html><meta charset="utf-8"><style>*{box-sizing:border-box}html,body{margin:0;height:100%;background:#0b1722;color:#e1f0f7;font:12px Segoe UI,Arial;overflow:hidden}nav{height:100%;display:flex;gap:5px;padding:5px;border-bottom:1px solid #36586d}a{display:block;color:#d5e8f1;text-decoration:none;padding:8px 12px;border:1px solid #34556a;border-radius:5px;background:#163147;white-space:nowrap}a:hover{background:#26516e}</style><nav>';
  const leftTabHtml=tabStyle+'<a href="lion-left://mission">MISSION CONTROL</a><a href="lion-left://cluster">CLUSTER</a><a href="lion-left://system">SYSTEM</a></nav>';
  const rightTabHtml=tabStyle+'<a href="lion-right://panel">LPCL PANEL</a><a href="lion-right://saas">ChatGPT SaaS</a><a href="lion-right://local">LOCAL GPT</a></nav>';
  const layout=()=>{
   const {width,height}=win.getContentBounds(),split=Math.floor(width*.5);
   const rightWidth=width-split,bodyHeight=Math.max(0,height-TAB_HEIGHT);
   leftTabs.setBounds({x:0,y:0,width:split,height:TAB_HEIGHT});
   rightTabs.setBounds({x:split,y:0,width:rightWidth,height:TAB_HEIGHT});
   const L={x:0,y:TAB_HEIGHT,width:split,height:bodyHeight};
   const R={x:split,y:TAB_HEIGHT,width:rightWidth,height:bodyHeight};
   const HL={x:-split-64,y:TAB_HEIGHT,width:split,height:bodyHeight};
   const HR={x:width+64,y:TAB_HEIGHT,width:rightWidth,height:bodyHeight};
   mission.setBounds(activeLeftTab==='mission'?L:HL);
   cluster.setBounds(activeLeftTab==='cluster'?L:HL);
   system.setBounds(activeLeftTab==='system'?L:HL);
   panel.setBounds(activeRightTab==='panel'?R:HR);
   saas.setBounds(activeRightTab==='saas'?R:HR);
   local.setBounds(activeRightTab==='local'?R:HR);
  };
  const updateTitle=()=>win.setTitle('LION | '+activeLeftTab.toUpperCase()+' • '+activeRightTab.toUpperCase());
  selectLeftTab=name=>{
   if(!['mission','cluster','system'].includes(name))return;
   activeLeftTab=name;layout();updateTitle();
  };
  selectRightTab=name=>{
   if(!['panel','saas','local'].includes(name))return;
   activeRightTab=name;layout();updateTitle();
  };
  refreshVisible=()=>{
   const v={mission,cluster,system}[activeLeftTab];
   if(activeLeftTab==='mission')v.webContents.reloadIgnoringCache();
   else v.webContents.executeJavaScript('window.dispatchEvent(new Event("lion-refresh"))').catch(()=>{});
  };
  win.on('resize',layout);layout();updateTitle();win.on('closed',()=>app.quit());
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
  canonicalConsumer.stop('RECOVERY_OPERATOR_RESUME_REQUIRED');
  const startupConversation=PROJECT;
  const source={host:require('node:os').hostname(),entrypoint:__filename,sha256:require('./contract.cjs').hash(fs.readFileSync(__filename))};
  const status=async()=>({observed_at:new Date().toISOString(),runtime:{electron:process.versions.electron,node:process.versions.node,platform:process.platform,source},ui:{left_surface:'mission_control',left_active:activeLeftTab,left_tabs:['mission','cluster','system'],
   right_active:activeRightTab,right_tabs:['panel','saas','local'],
   panel_url:PANEL,local_model_api:'http://127.0.0.1:8772',
   cluster_loaded_url:cluster.webContents.getURL(),system_loaded_url:system.webContents.getURL(),
   local_loaded_url:local.webContents.getURL(),
   cluster_loading:cluster.webContents.isLoading(),system_loading:system.webContents.isLoading(),
   local_loading:local.webContents.isLoading(),operator_view_proof:operatorViewProof},browser:await browser.inspect(),conversation:browser.bindingReport(),ingress_credential_present:!!ingressToken,mediator_credential_present:!!mediatorKey,transport_error:canonicalConsumer?.lastError||null,engine:{running:false,lastTickAt:null,lastDecision:'RETIRED_LEGACY_DELIVERY'},relay:{state:'RETIRED_ARCHIVAL',mode:'THREAD_CONSUMER',writes_responses:false,authority_effect:'NONE'},wake_plane:{...(canonicalConsumer?.status()||{state:'STARTING'}),mode:'CANONICAL_CONVERSATION_SAAS_CONSUMER',external_saas_semantics:'EXPLICIT_BRIDGE_ONLY',authority_effect:'NONE'},canonical_saas_consumer:canonicalConsumer?.status()||null,conversation_url:'PROJECT_OR_EXPLICIT_BRIDGE_ONLY',legacy_routing_retired:true,authority_effect:'NONE'});
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
  const showInfo=(title,detail)=>dialog.showMessageBox(win,{
   type:'info',message:title,detail:String(detail).slice(0,5000),buttons:['OK']
  });
  const inspectSaaS=async()=>{
   const rows=Object.values(canonicalConsumer?.dispatchMap||{});
   const unresolved=rows.filter(v=>v&&['PROVISIONING','DISPATCHING','SEND_COMMITTED','BOUND_SENT','SEND_UNKNOWN','RESULT_OBSERVED'].includes(v.state));
   let upstream={};
   try{upstream=await mc('/api/v3/saas-broker/status')}
   catch(error){upstream={state:'UNAVAILABLE',error:String(error.name||'ERROR')}}
   return {consumer_state:canonicalConsumer?.status()?.state,
    unresolved_count:unresolved.length,upstream_state:upstream.state,
    upstream_pending:upstream.pending_count,authority_effect:'NONE'};
  };
  // Existing exact Mission Control receipts can be acknowledged locally
  // WITHOUT restarting the automatic sender or issuing new SaaS messages.
  const reconcileExistingSaaSReceipts=async()=>{
   const before=await inspectSaaS();
   try{
    const result=await canonicalConsumer.reconcileReceiptsOnly({limit:32});
    const after=await inspectSaaS();
    await showInfo('Odpowiedzi SaaS — tylko rekonsyliacja',
     'Bez ponowienia wysyłki SaaS. Zmiana dotyczy wyłącznie lokalnego ledgeru.\n'+
     JSON.stringify({result,before,after},null,2));
   }catch(error){
    await showInfo('Odpowiedzi SaaS — NIEUZGODNIONE',
      'Nie ponowiono żądania. Wynik UNKNOWN — przeprowadź niezależny odczyt ledgeru.\n'+
      String(error?.name||'ERROR').slice(0,100));
   }
  };
  const safeResume=async()=>{
   const snapshot=await inspectSaaS();
   if(snapshot.unresolved_count||snapshot.upstream_pending!==0||snapshot.upstream_state==='UNAVAILABLE'){
    await showInfo('Relay SaaS: wymagana rekonsyliacja',
     'Interaktywny ChatGPT SaaS pozostaje dostępny. Automatycznego relay nie uruchomiono. Oczekujące wiadomości wymagają dokładnych response/receipt digest.\n'+JSON.stringify(snapshot,null,2));
    return;
   }
   canonicalConsumer?.resume('LOCAL_OPERATOR_MENU_EXACT_BOUNDED');
   await showInfo('Relay SaaS','Operator wydał polecenie wznowienia. Uprawnienia misji i transport są odrębne.');
  };
  const knownRepos=['ai_platform','swarm','HA2D','mosaic_lab_pro.py','glitchlab','hipotezy_nadawcze_LLM','chunk-chunk','sbom','SymulacjaKaskadySieciowej','writeups'];
  const openRepo=async name=>{
   if(!knownRepos.includes(name))return;
   await shell.openExternal('https://github.com/DonkeyJJLove/'+encodeURIComponent(name));
  };
  Menu.setApplicationMenu(Menu.buildFromTemplate([
   {label:'LION',submenu:[
    {label:'Stan Desktop i widoków',click:async()=>{const state=await status();await showInfo('LION Desktop',JSON.stringify({ui:state.ui,consumer:state.canonical_saas_consumer,authority_effect:state.authority_effect},null,2))}},
    {label:'Odśwież aktywny widok lewy',accelerator:'F5',click:refreshVisible},
    {type:'separator'},{label:'Zakończ',role:'quit'}
   ]},
   {label:'Control Plane',submenu:[
    {label:'Mission Control',click:()=>selectLeftTab('mission')},
    {label:'Cluster i logi',click:()=>selectLeftTab('cluster')},
    {label:'System i federacja',click:()=>selectLeftTab('system')},
    {type:'separator'},
    {label:'Mission Control + kanoniczny Model Chat',click:()=>{selectLeftTab('mission');selectRightTab('panel')}},
    {label:'Odśwież aktualne odczyty',click:refreshVisible}
   ]},
   {label:'Intelligence',submenu:[
    {label:'LPCL Panel / Model Chat',click:()=>selectRightTab('panel')},
    {label:'ChatGPT SaaS',click:()=>selectRightTab('saas')},
    {label:'Local GPT • 8772',click:()=>selectRightTab('local')},
    {type:'separator'},
    {label:'Sprawdź lokalny model',click:async()=>showInfo('Local GPT',JSON.stringify(await localAdvisory.status(),null,2))},
    {label:'Stan canonical SaaS bridge',click:async()=>showInfo('SaaS / Model Chat',JSON.stringify(await inspectSaaS(),null,2))},
    {label:'Rozlicz istniejące receipty SaaS (bez wysyłania)',click:reconcileExistingSaaSReceipts},
    {label:'Wznów relay po rozliczeniu turnów',click:safeResume},
    {label:'Wstrzymaj automatyczny relay',click:()=>canonicalConsumer?.stop('LOCAL_OPERATOR_MENU')},
    {label:'Przejdź do ChatGPT SaaS',click:()=>selectRightTab('saas')}
   ]},
   {label:'Diagnostyka',submenu:[
    {label:'Bieżące endpointy',click:async()=>showInfo('Kontrolery',JSON.stringify((await readModel.observe('cluster')).endpoints,null,2))},
    {label:'Zapisz raport',click:async()=>{try{await diagnose();await showInfo('Raport',path.join(dir,'diagnostic-r19.json'))}catch(error){await showInfo('Błąd diagnostyki',String(error.message))}}},
    {label:'Logi Desktop',click:()=>{selectLeftTab('cluster');refreshVisible()}}
   ]},
   {label:'Federacja',submenu:[
    {label:'10 repozytoriów — podgląd',click:()=>selectLeftTab('system')},
    {type:'separator'},
    ...knownRepos.map(name=>({label:name,click:()=>openRepo(name)}))
   ]},
   {label:'Pomoc',submenu:[
    {label:'Jak działa synchronizacja?',click:async()=>showInfo('Kanały LION',
     'Model Chat i LPCL wiążą misję, conversation_id, binding_epoch i receipts. Czat ad hoc LOCAL jest UNBOUND; SaaS pozostaje zewnętrznym wątkiem. Żadna karta UI nie mintuje authority ani nie kończy fazy.')},
    {label:'O LION Desktop R4',click:async()=>showInfo('LION Desktop R4','Dwa niezależne tab bary. Lewe: Mission Control/Cluster/System. Prawe: LPCL/SaaS/Local GPT. Model output != effect != completion.')}
   ]}
  ]));
  let ticking=false;
  timer=setInterval(async()=>{if(closing||ticking)return;ticking=true;try{await canonicalConsumer?.tick()}finally{ticking=false}},1200);
  await Promise.allSettled([
   panel.webContents.loadURL(PANEL),
   saas.webContents.loadURL(startupConversation),
   mission.webContents.loadURL(MC),
   cluster.webContents.loadURL(overviewURL),
   system.webContents.loadURL(overviewURL+'#system'),
   local.webContents.loadURL(localURL),
   leftTabs.webContents.loadURL('data:text/html;charset=utf-8,'+encodeURIComponent(leftTabHtml)),
   rightTabs.webContents.loadURL('data:text/html;charset=utf-8,'+encodeURIComponent(rightTabHtml))
  ]);
  try{
   const clusterProbe=await cluster.webContents.executeJavaScript(
    'window.lionObserver ? window.lionObserver.snapshot() : null');
   const modelProbe=await local.webContents.executeJavaScript(
    'window.lionLocal ? window.lionLocal.status() : null');
   operatorViewProof={
    state:clusterProbe?.schema==='lion.operator-read-model/v1'
      &&clusterProbe?.authority_effect==='NONE'
      &&modelProbe?.authority_effect==='NONE'?'PASS':'UNVERIFIED',
    cluster_observation_at:clusterProbe?.observed_at||null,
    cluster_mission_control:clusterProbe?.endpoints?.mission_control||null,
    local_model_status:modelProbe?.state||null,
    local_model_label:modelProbe?.model_label||null,
    authority_effect:'NONE'
   };
  }catch(error){
   operatorViewProof={state:'UNVERIFIED',reason:String(error.name||'ERROR').slice(0,80),authority_effect:'NONE'};
  }
  if(!closing)try{await diagnose()}catch{win.setTitle('LION Broker — raport diagnostyczny niedostępny')}
 }).catch(()=>{dialog.showErrorBox('LION Broker','Uruchomienie nie powiodło się. Sprawdź konfigurację, dostęp do plików i wymagany runtime.');app.quit()});
}
