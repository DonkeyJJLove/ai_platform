'use strict';
const {conversation}=require('./contract.cjs');
const {conversationReport}=require('./conversation.cjs');
// Versioned UI adapter, not a provider-supported API. UI drift stops dispatch.
const chatExperience=(pathname,search,selectedLabels=[])=>{
 const workRoute=/(^|\/)work(\/|$)/i.test(String(pathname||''))||/(?:^|[?&])(?:mode|experience)=work(?:&|$)/i.test(String(search||''));
 const workSelected=selectedLabels.some(x=>/^work$/i.test(String(x||'').trim()));
 return workRoute||workSelected?'WORK':'CHAT';
};
const observeScript=`(() => {
 const p=document.querySelector('#prompt-textarea[contenteditable="true"]');
 const s=document.querySelector('button[data-testid="send-button"]');
 const busy=!!document.querySelector('button[data-testid="stop-button"]');
 const group=[...document.querySelectorAll('[role="radiogroup"]')].find(x=>/wybierz obszar czatu|choose chat area/i.test(x.getAttribute('aria-label')||''));
 const chatRadio=group&&[...group.querySelectorAll('[role="radio"]')].find(x=>/^Chat$/i.test((x.innerText||x.textContent||'').trim()));
 const workRadio=group&&[...group.querySelectorAll('[role="radio"]')].find(x=>/^Work$/i.test((x.innerText||x.textContent||'').trim()));
 const chatOn=!!chatRadio&&chatRadio.getAttribute('data-state')==='on';
 const workOn=!!workRadio&&workRadio.getAttribute('data-state')==='on';
 const headerWork=!group&&[...document.querySelectorAll('span,div')].some(x=>{const t=((x.innerText||x.textContent||'').trim());const r=x.getBoundingClientRect();return x.getClientRects().length>0&&r.top>=0&&r.top<120&&/^Work$/i.test(t);});
 const workRoute=/(^|\\/)work(\\/|$)/i.test(location.pathname)||/(?:^|[?&])(?:mode|experience)=work(?:&|$)/i.test(location.search);
 const experience=workOn||(!chatOn&&(headerWork||workRoute))?'WORK':'CHAT';
 return {composer:!!p&&p.getClientRects().length>0,empty:!!p&&!p.textContent.trim(),send:!!s,busy,experience,work_selected:experience==='WORK',chat_state:chatRadio?.getAttribute('data-state')||null,work_state:workRadio?.getAttribute('data-state')||null,header_work:headerWork};
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
 async send(v,text,admitted){
  if(!admitted()||!(await this.ready(v))||!admitted()){if(this.state==='WORK_MODE_FORBIDDEN')throw Error('WORK_MODE_FORBIDDEN');throw Error('NOT_READY')}
  const fill=`(() => {if(location.href!==${JSON.stringify(v.conversation_url)})return false;
    const p=document.querySelector('#prompt-textarea[contenteditable="true"]');if(!p||p.textContent.trim())return false;
    p.focus();return document.execCommand('insertText',false,${JSON.stringify(text)});})()`;
  if(!(await this.contents.executeJavaScriptInIsolatedWorld(1001,[{code:fill}]))||!admitted())throw Error('FILL_OR_ADMISSION_UNKNOWN');
  const click=`(() => {if(location.href!==${JSON.stringify(v.conversation_url)})return false;
    const p=document.querySelector('#prompt-textarea[contenteditable="true"]');const s=document.querySelector('button[data-testid="send-button"]');
    const expected=${JSON.stringify(text)},observed=p?.textContent||'',contentMatches=(${composerEquivalent.toString()})(observed,expected);
    if(!p||!contentMatches||!s||s.disabled)return false;s.click();return true;})()`;
  if(!admitted()||!(await this.contents.executeJavaScriptInIsolatedWorld(1001,[{code:click}])))throw Error('SEND_UNKNOWN');
  this.state='AWAITING_MCP_RESULT';
 }
}
module.exports={EmbeddedBrowser,composerEquivalent,chatExperience,observeScript};
