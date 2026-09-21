'use strict';
const {app,BaseWindow,WebContentsView,Menu,dialog}=require('electron');
const fs=require('node:fs');const path=require('node:path');const {randomBytes}=require('node:crypto');
const {Store}=require('./store.cjs');const {Engine}=require('./engine.cjs');
const {EmbeddedBrowser}=require('./browser.cjs');const {createHttp}=require('./http.cjs');const {webPreferences}=require('./contract.cjs');
const PROJECT=process.env.LION_PROJECT_URL||'https://chatgpt.com/g/g-p-6a91cabd3f208191a37f295819e9f75b-lion-evolusion/project';
const PANEL=process.env.LION_PANEL_URL||'http://127.0.0.1:8780';
const MC='http://127.0.0.1:8766';
const INGRESS=process.env.LION_INGRESS_URL||'http://127.0.0.1:8791';
for(const raw of [PANEL,INGRESS]){const u=new URL(raw);if(u.protocol!=='http:'||u.hostname!=='127.0.0.1'||u.username||u.password||u.pathname!=='/'||u.search||u.hash)throw Error('LOOPBACK_SERVICE_REQUIRED')}
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
  const ingressToken=process.env.LION_INGRESS_TOKEN_FILE?fs.readFileSync(process.env.LION_INGRESS_TOKEN_FILE,'utf8').trim():null;
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
  const getTurn=async id=>{
   if(!ingressToken)throw Error('INGRESS_CREDENTIAL_REQUIRED');
   const response=await fetch(new URL('/v1/turns/'+encodeURIComponent(id),INGRESS),{headers:{'X-LION-Token':ingressToken},signal:AbortSignal.timeout(5000),redirect:'error'});
   if(!response.ok)throw Error('INGRESS_UNAVAILABLE');return (await response.json()).turn;
  };
  const admit=async v=>{
   if(!v.mission_id.startsWith('LION-R19-'))return false;
   const r=await fetch(MC+'/api/v3/missions/'+encodeURIComponent(v.mission_id)+'/process',{signal:AbortSignal.timeout(5000),redirect:'error'});
   if(!r.ok)return false;const m=await r.json();
   return m.mission_id===v.mission_id&&['RUNNING','AUTHORIZED'].includes(m.state)&&m.execution_preflight?.mission_readiness==='READY_BOUND';
  };
  engine=new Engine({store,browser,getTurn,admit});
  server=createHttp({store,token,status:()=>({browser:browser.state,ingress_credential_present:!!ingressToken,transport_error:engine.lastError})}).listen(8793,'127.0.0.1');
  server.on('error',()=>{store.stop();dialog.showErrorBox('LION Broker','Nie można uruchomić portu 8793. Broker pozostaje zatrzymany.');app.quit()});
  Menu.setApplicationMenu(Menu.buildFromTemplate([{label:'LION',submenu:[
   {label:'Stan / diagnostyka',click:async()=>{
    const report={observed_at:new Date().toISOString(),runtime:{electron:process.versions.electron,node:process.versions.node,platform:process.platform},browser:await browser.inspect(),stopped:store.stopped(),ingress_credential_present:!!ingressToken,conversation_url:new URL(saas.webContents.getURL()||PROJECT).origin==='https://chatgpt.com'?saas.webContents.getURL().split(/[?#]/)[0]:'AUTH_OR_NAVIGATION_REQUIRED',queue:store.rows().map(r=>({request_id:r.request_id,state:r.state})),model_identity:'UNKNOWN',live_e2e:'NOT_PROVEN'};
    const output=path.join(dir,'diagnostic-r19.json');
    try{fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n',{mode:0o600});await dialog.showMessageBox(win,{message:JSON.stringify(report,null,2),detail:'Raport: '+output})}
    catch{dialog.showErrorBox('LION Broker','Nie można zapisać raportu diagnostycznego.')}
   }},
   {label:'Wznów kolejkę po zalogowaniu',click:()=>{if(!ingressToken){dialog.showErrorBox('LION Broker','Brak LION_INGRESS_TOKEN_FILE. Nie można weryfikować tur.');return}store.resume()}},
   {label:'STOP',click:()=>store.stop()},
   {label:'Otwórz projekt SaaS',click:()=>{store.stop();saas.webContents.loadURL(PROJECT).catch(()=>{})}},
   {label:'Zakończ',click:()=>app.quit()}
  ]}]));
  timer=setInterval(()=>engine.tick(),2000);
  await Promise.allSettled([panel.webContents.loadURL(PANEL),saas.webContents.loadURL(PROJECT)]);
 }).catch(()=>{dialog.showErrorBox('LION Broker','Uruchomienie nie powiodło się. Sprawdź konfigurację, dostęp do plików i wymagany runtime.');app.quit()});
}
