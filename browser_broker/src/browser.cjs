'use strict';
const {conversation}=require('./contract.cjs');
const {conversationReport,conversationInfo}=require('./conversation.cjs');
// Versioned UI adapter, not a provider-supported API. UI drift stops dispatch.
const chatExperience=(pathname,search,selectedLabels=[])=>{
 const workRoute=/(^|\/)work(\/|$)/i.test(String(pathname||''))||/(?:^|[?&])(?:mode|experience)=work(?:&|$)/i.test(String(search||''));
 const workSelected=selectedLabels.some(x=>/^work$/i.test(String(x||'').trim()));
 return workRoute||workSelected?'WORK':'CHAT';
};
const observeScript=`(() => {
 const p=document.querySelector('#prompt-textarea[contenteditable="true"],#prompt-textarea,textarea[data-testid="prompt-textarea"],[contenteditable="true"][data-lexical-editor="true"],div.ProseMirror[contenteditable="true"]');
 const s=document.querySelector('button[data-testid="send-button"],button[aria-label*="Wyślij" i],button[aria-label*="Send" i]');
 const busy=!!document.querySelector('button[data-testid="stop-button"]');
 const group=[...document.querySelectorAll('[role="radiogroup"]')].find(x=>/wybierz obszar czatu|choose chat area/i.test(x.getAttribute('aria-label')||''));
 const chatRadio=group&&[...group.querySelectorAll('[role="radio"]')].find(x=>/^Chat$/i.test((x.innerText||x.textContent||'').trim()));
 const workRadio=group&&[...group.querySelectorAll('[role="radio"]')].find(x=>/^Work$/i.test((x.innerText||x.textContent||'').trim()));
 const chatOn=!!chatRadio&&chatRadio.getAttribute('data-state')==='on';
 const workOn=!!workRadio&&workRadio.getAttribute('data-state')==='on';
 const selectedSignal=x=>{if(!x)return false;const state=String(x.getAttribute('data-state')||'').toLowerCase(),pressed=String(x.getAttribute('aria-pressed')||'').toLowerCase(),selected=String(x.getAttribute('aria-selected')||'').toLowerCase();return ['on','active','checked','selected'].includes(state)||pressed==='true'||selected==='true'};
 const header=[...document.querySelectorAll('button,[role="tab"],[role="radio"]')].filter(x=>{const r=x.getBoundingClientRect(),t=(x.innerText||x.textContent||'').trim();return x.getClientRects().length>0&&r.top>=0&&r.top<140&&/^(Chat|Work)$/i.test(t)});
 const headerWork=header.some(x=>/^Work$/i.test((x.innerText||x.textContent||'').trim())&&(selectedSignal(x)||selectedSignal(x.parentElement)));
 const headerChat=header.some(x=>/^Chat$/i.test((x.innerText||x.textContent||'').trim())&&(selectedSignal(x)||selectedSignal(x.parentElement)));
 const workRoute=/(^|\\/)work(\\/|$)/i.test(location.pathname)||/(?:^|[?&])(?:mode|experience)=work(?:&|$)/i.test(location.search);
 const experience=workOn||headerWork||(!chatOn&&!headerChat&&workRoute)?'WORK':'CHAT';
 const value=p?('value' in p?String(p.value||''):String(p.textContent||'')):'';
 const editors=[...document.querySelectorAll('textarea,[contenteditable="true"],[role="textbox"]')].filter(x=>x.getClientRects().length>0).slice(0,12).map(x=>({tag:x.tagName,id:x.id||null,role:x.getAttribute('role'),contenteditable:x.getAttribute('contenteditable'),placeholder:x.getAttribute('placeholder'),testid:x.getAttribute('data-testid'),class_name:String(x.className||'').slice(0,180)}));
 const buttons=[...document.querySelectorAll('button')].filter(x=>x.getClientRects().length>0).slice(-40).map(x=>({text:(x.innerText||x.textContent||'').trim().slice(0,120),aria:x.getAttribute('aria-label'),testid:x.getAttribute('data-testid'),disabled:!!x.disabled,class_name:String(x.className||'').slice(0,160)}));
 const form=p?.closest('form');const composer_buttons=form?[...form.querySelectorAll('button')].filter(x=>x.getClientRects().length>0).map(x=>({text:(x.innerText||x.textContent||'').trim().slice(0,120),aria:x.getAttribute('aria-label'),testid:x.getAttribute('data-testid'),disabled:!!x.disabled,class_name:String(x.className||'').slice(0,160)})):[];
 const composer_context=p?.closest('form')?.outerHTML||p?.parentElement?.parentElement?.outerHTML||p?.parentElement?.outerHTML||'';
 return {composer:!!p&&p.getClientRects().length>0,empty:!!p&&!value.trim(),send:!!s,busy,experience,work_selected:experience==='WORK',chat_state:chatRadio?.getAttribute('data-state')||null,work_state:workRadio?.getAttribute('data-state')||null,header_work:headerWork,editors,buttons,composer_buttons,composer_context:String(composer_context).slice(0,12000)};
})()`;
const composerEquivalent=(observed,expected)=>observed===expected||observed===expected.replace(/\r\n|\r|\n/g,'');
class EmbeddedBrowser{
 constructor(contents,projectUrl){this.contents=contents;this.projectUrl=projectUrl;this.state='AUTH_OR_BINDING_REQUIRED'}
 bindingReport(){return conversationReport(this.contents.isDestroyed()?'':this.contents.getURL(),this.projectUrl)}
 async inspect(){
  if(this.contents.isDestroyed())return {state:'RENDERER_UNAVAILABLE'};
  try{
   if(new URL(this.contents.getURL()).origin!=='https://chatgpt.com')return {state:'AUTH_OR_NAVIGATION_REQUIRED'};
   const ui=await this.contents.executeJavaScriptInIsolatedWorld(1001,[{code:observeScript}]);
   return {state:ui.experience==='WORK'?'WORK_MODE_FORBIDDEN':ui.composer?'COMPOSER_OBSERVED_MCP_UNVERIFIED':'AUTH_OR_UI_REQUIRED',...ui};
  }catch{return {state:'AUTH_OR_UI_REQUIRED'}}
 }
 async ready(v){
  try{
   if(this.contents.isDestroyed()||conversation(this.contents.getURL(),this.projectUrl)!==v.conversation_url){this.state='CONVERSATION_BINDING_REQUIRED';return false}
   const o=await this.contents.executeJavaScriptInIsolatedWorld(1001,[{code:observeScript}]);
   if(o.experience==='WORK'){this.state='WORK_MODE_FORBIDDEN';return false}
   const ready=o.composer&&o.empty&&!o.busy;
   this.state=ready?'UI_READY_MCP_UNVERIFIED':'AUTH_OR_UI_REQUIRED';return ready;
  }catch{this.state='AUTH_OR_UI_REQUIRED';return false}
 }
 async _sleep(ms){return new Promise(resolve=>setTimeout(resolve,ms))}
 async _wait(check,timeout=30000,interval=250){
  const deadline=Date.now()+timeout;let last=null;
  while(Date.now()<deadline){
   try{const value=await check();if(value)return value}catch(error){last=error}
   await this._sleep(interval);
  }
  if(last)throw last;throw Error('BROWSER_WAIT_TIMEOUT');
 }
 async navigateExact(url){
  const info=conversationInfo(url,this.projectUrl);
  if(this.contents.isDestroyed())throw Error('RENDERER_UNAVAILABLE');
  const current=this.contents.getURL();
  let same=false;try{same=conversationInfo(current,this.projectUrl).url===info.url}catch{}
  if(!same)await this.contents.loadURL(info.url);
  await this._wait(async()=>await this.ready({conversation_url:info.url}),30000,300);
  this.state='UI_READY_MCP_UNVERIFIED';
  return info;
 }
 async _projectComposerReady(){
  if(this.contents.isDestroyed())return false;
  try{
   const current=new URL(this.contents.getURL()),project=new URL(this.projectUrl);
   if(current.origin!==project.origin||current.pathname!==project.pathname)return false;
   const o=await this.contents.executeJavaScriptInIsolatedWorld(1001,[{code:observeScript}]);
   if(o.experience==='WORK'){this.state='WORK_MODE_FORBIDDEN';return false}
   return !!(o.composer&&o.empty&&!o.busy);
  }catch{return false}
 }
 async _clearProjectComposer(){
  if(this.contents.isDestroyed())return false;
  const project=new URL(this.projectUrl);
  const code=`(() => {
   if(location.origin!==${JSON.stringify(project.origin)}||location.pathname!==${JSON.stringify(project.pathname)})return false;
   const p=document.querySelector('#prompt-textarea[contenteditable="true"],#prompt-textarea,textarea[data-testid="prompt-textarea"],[contenteditable="true"][data-lexical-editor="true"],div.ProseMirror[contenteditable="true"]');
   if(!p)return false;p.focus();
   if('value' in p){
    const proto=p.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
    const setter=Object.getOwnPropertyDescriptor(proto,'value')?.set;if(!setter)return false;setter.call(p,'');
   }else p.innerHTML='<p><br></p>';
   p.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'deleteContentBackward',data:null}));
   return true;
  })()`;
  return !!(await this.contents.executeJavaScriptInIsolatedWorld(1001,[{code}]));
 }
 async _activateProjectNewChat(){
  if(this.contents.isDestroyed())return false;
  const code=`(() => {
    const visible=x=>{const r=x.getBoundingClientRect();return x.getClientRects().length>0&&r.width>0&&r.height>0};
    const rows=[...document.querySelectorAll('button,a,[role="button"]')].filter(visible);
    const target=rows.find(x=>/^(Nowy czat w projekcie|New chat in project)(\\b|\\s|$)/i.test((x.innerText||x.textContent||'').trim()));
    if(!target)return false;target.click();return true;
  })()`;
  return !!(await this.contents.executeJavaScriptInIsolatedWorld(1001,[{code}]));
 }
 async _anyChatComposerReady(){
  if(this.contents.isDestroyed())return false;
  try{
   const u=new URL(this.contents.getURL());if(u.origin!=='https://chatgpt.com')return false;
   const o=await this.contents.executeJavaScriptInIsolatedWorld(1001,[{code:observeScript}]);
   if(o.experience==='WORK'){this.state='WORK_MODE_FORBIDDEN';return false}
   return !!(o.composer&&o.empty&&!o.busy);
  }catch{return false}
 }
 async createProjectConversationWithPrompt(text,admitted){
  if(typeof text!=='string'||!text.trim())throw Error('PROMPT_REQUIRED');
  if(!admitted())throw Error('ADMISSION_REVOKED');
  if(this.contents.isDestroyed())throw Error('RENDERER_UNAVAILABLE');
  const project=new URL(this.projectUrl);
  const current=this.contents.getURL();
  let onProject=false;try{const u=new URL(current);onProject=u.origin===project.origin&&u.pathname===project.pathname}catch{}
  if(!onProject)await this.contents.loadURL(this.projectUrl);
  let ready=false;try{ready=await this._wait(async()=>await this._projectComposerReady(),4500,300)}catch{}
  if(!ready){
   try{await this._clearProjectComposer();ready=await this._wait(async()=>await this._projectComposerReady(),5000,250)}catch{}
  }
  if(!ready){if(!(await this._activateProjectNewChat()))throw Error('PROJECT_NEW_CHAT_CONTROL_REQUIRED');await this._wait(async()=>await this._anyChatComposerReady(),30000,300)}
  if(!admitted())throw Error('ADMISSION_REVOKED');
  const fill=`(() => {
    if(location.origin!==${JSON.stringify(project.origin)})return false;
    const p=document.querySelector('#prompt-textarea[contenteditable="true"],#prompt-textarea,textarea[data-testid="prompt-textarea"],[contenteditable="true"][data-lexical-editor="true"],div.ProseMirror[contenteditable="true"]');
    if(!p)return false;const current=('value' in p?String(p.value||''):String(p.textContent||''));if(current.trim())return false;p.focus();
    if('value' in p){const proto=p.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;const setter=Object.getOwnPropertyDescriptor(proto,'value')?.set;if(!setter)return false;setter.call(p,${JSON.stringify(text)});p.dispatchEvent(new Event('input',{bubbles:true}));return true}
    const ok=document.execCommand('insertText',false,${JSON.stringify(text)});p.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:${JSON.stringify(text)}}));return ok;
  })()`;
  if(!(await this.contents.executeJavaScriptInIsolatedWorld(1001,[{code:fill}])))throw Error('PROJECT_COMPOSER_FILL_FAILED');
  const click=()=>this.contents.executeJavaScriptInIsolatedWorld(1001,[{code:`(() => {
    const p=document.querySelector('#prompt-textarea[contenteditable="true"],#prompt-textarea,textarea[data-testid="prompt-textarea"],[contenteditable="true"][data-lexical-editor="true"],div.ProseMirror[contenteditable="true"]');
    const form=p?.closest('form');const s=(form||document).querySelector('button[data-testid="send-button"],button[aria-label*="Wyślij" i],button[aria-label*="Send" i]');
    const expected=${JSON.stringify(text)},observed=p?('value' in p?String(p.value||''):String(p.textContent||'')):'';
    const ok=(${composerEquivalent.toString()})(observed,expected);
    if(!p||!ok||!s||s.disabled)return false;s.click();return true;
  })()`}]);
  await this._wait(async()=>admitted()&&await click(),12000,250);
  const info=await this._wait(async()=>{
    if(!admitted())throw Error('ADMISSION_REVOKED');
    try{return conversationInfo(this.contents.getURL(),this.projectUrl)}catch{return null}
  },30000,250);
  this.state='AWAITING_MCP_RESULT';
  return {
   conversation_url:info.url,
   external_thread_ref:info.id,
   route:info.route,
   project_membership:info.project_membership,
  };
 }
 async sendToConversation(url,text,admitted){
  const info=await this.navigateExact(url);
  await this.send({conversation_url:info.url},text,admitted);
  return info;
 }
 async send(v,text,admitted){
  if(!admitted()||!(await this.ready(v))||!admitted()){if(this.state==='WORK_MODE_FORBIDDEN')throw Error('WORK_MODE_FORBIDDEN');throw Error('NOT_READY')}
  const fill=`(() => {if(location.href!==${JSON.stringify(v.conversation_url)})return false;
    const p=document.querySelector('#prompt-textarea[contenteditable="true"],#prompt-textarea,textarea[data-testid="prompt-textarea"],[contenteditable="true"][data-lexical-editor="true"],div.ProseMirror[contenteditable="true"]');if(!p||(('value' in p?String(p.value||''):String(p.textContent||'')).trim()))return false;
    p.focus();if('value' in p){const proto=p.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;const setter=Object.getOwnPropertyDescriptor(proto,'value')?.set;if(!setter)return false;setter.call(p,${JSON.stringify(text)});p.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:${JSON.stringify(text)}}));return true}const ok=document.execCommand('insertText',false,${JSON.stringify(text)});p.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:${JSON.stringify(text)}}));return ok;})()`;
  if(!(await this.contents.executeJavaScriptInIsolatedWorld(1001,[{code:fill}]))||!admitted())throw Error('FILL_OR_ADMISSION_UNKNOWN');
  const click=`(() => {if(location.href!==${JSON.stringify(v.conversation_url)})return false;
    const p=document.querySelector('#prompt-textarea[contenteditable="true"],#prompt-textarea,textarea[data-testid="prompt-textarea"],[contenteditable="true"][data-lexical-editor="true"],div.ProseMirror[contenteditable="true"]');const form=p?.closest('form');const s=(form||document).querySelector('button[data-testid="send-button"],button[aria-label*="Wyślij" i],button[aria-label*="Send" i]');
    const expected=${JSON.stringify(text)},observed=p?('value' in p?String(p.value||''):String(p.textContent||'')):'',contentMatches=(${composerEquivalent.toString()})(observed,expected);
    if(!p||!contentMatches||!s||s.disabled)return false;s.click();return true;})()`;
  if(!admitted()||!(await this.contents.executeJavaScriptInIsolatedWorld(1001,[{code:click}])))throw Error('SEND_UNKNOWN');
  this.state='AWAITING_MCP_RESULT';
 }
}
module.exports={EmbeddedBrowser,composerEquivalent,chatExperience,observeScript};
