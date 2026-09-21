'use strict';
const {conversation}=require('./contract.cjs');
const {conversationReport}=require('./conversation.cjs');
// Versioned UI adapter, not a provider-supported API. UI drift stops dispatch.
const observeScript=`(() => {
 const p=document.querySelector('#prompt-textarea[contenteditable="true"]');
 const s=document.querySelector('button[data-testid="send-button"]');
 const busy=!!document.querySelector('button[data-testid="stop-button"]');
 return {composer:!!p&&p.getClientRects().length>0,empty:!!p&&!p.textContent.trim(),send:!!s,busy};
})()`;
class EmbeddedBrowser{
 constructor(contents,projectUrl){this.contents=contents;this.projectUrl=projectUrl;this.state='AUTH_OR_BINDING_REQUIRED'}
 bindingReport(){return conversationReport(this.contents.isDestroyed()?'':this.contents.getURL(),this.projectUrl)}
 async inspect(){
  if(this.contents.isDestroyed())return {state:'RENDERER_UNAVAILABLE'};
  try{
   if(new URL(this.contents.getURL()).origin!=='https://chatgpt.com')return {state:'AUTH_OR_NAVIGATION_REQUIRED'};
   const ui=await this.contents.executeJavaScriptInIsolatedWorld(1001,[{code:observeScript}]);
   return {state:ui.composer?'COMPOSER_OBSERVED_MCP_UNVERIFIED':'AUTH_OR_UI_REQUIRED',...ui};
  }catch{return {state:'AUTH_OR_UI_REQUIRED'}}
 }
 async ready(v){
  try{
   if(this.contents.isDestroyed()||conversation(this.contents.getURL(),this.projectUrl)!==v.conversation_url){this.state='CONVERSATION_BINDING_REQUIRED';return false}
   const o=await this.contents.executeJavaScriptInIsolatedWorld(1001,[{code:observeScript}]);
   // The send button may appear only after the initially empty composer is filled.
   const ready=o.composer&&o.empty&&!o.busy;
   this.state=ready?'UI_READY_MCP_UNVERIFIED':'AUTH_OR_UI_REQUIRED';return ready;
  }catch{this.state='AUTH_OR_UI_REQUIRED';return false}
 }
 async send(v,text,admitted){
  if(!admitted()||!(await this.ready(v))||!admitted())throw Error('NOT_READY');
  const fill=`(() => {if(location.href!==${JSON.stringify(v.conversation_url)})return false;
    const p=document.querySelector('#prompt-textarea[contenteditable="true"]');if(!p||p.textContent.trim())return false;
    p.focus();return document.execCommand('insertText',false,${JSON.stringify(text)});})()`;
  if(!(await this.contents.executeJavaScriptInIsolatedWorld(1001,[{code:fill}]))||!admitted())throw Error('FILL_OR_ADMISSION_UNKNOWN');
  const click=`(() => {if(location.href!==${JSON.stringify(v.conversation_url)})return false;
    const p=document.querySelector('#prompt-textarea[contenteditable="true"]');const s=document.querySelector('button[data-testid="send-button"]');
    if(!p||p.textContent.trim()!==${JSON.stringify(text)}||!s||s.disabled)return false;s.click();return true;})()`;
  if(!admitted()||!(await this.contents.executeJavaScriptInIsolatedWorld(1001,[{code:click}])))throw Error('SEND_UNKNOWN');
  this.state='AWAITING_MCP_RESULT';
 }
}
module.exports={EmbeddedBrowser};
