'use strict';
const ORIGIN='https://chatgpt.com';
const projectKey=segment=>segment.match(/^g-p-([a-f0-9]{32})(?:-|$)/)?.[1]||segment;
function projectInfo(value){
 let u;try{u=new URL(value)}catch{throw Error('INVALID_PROJECT')}
 const m=u.pathname.match(/^\/g\/(g-p-[A-Za-z0-9-]+)\/project\/?$/);
 if(u.origin!==ORIGIN||u.username||u.password||u.search||u.hash||!m)throw Error('INVALID_PROJECT');
 return {url:u.href,key:projectKey(m[1])};
}
function conversationInfo(value,projectUrl){
 const p=projectInfo(projectUrl);let u;try{u=new URL(value)}catch{throw Error('INVALID_CONVERSATION')}
 if(u.origin!==ORIGIN||u.username||u.password)throw Error('INVALID_CONVERSATION');
 if(u.search||u.hash)throw Error('CONVERSATION_PARAMETERS_UNSUPPORTED');
 const plain=u.pathname.match(/^\/c\/([A-Za-z0-9-]{1,160})\/?$/);
 if(plain)return {url:u.href,id:plain[1],route:'CONVERSATION',project_membership:'OPERATOR_CONFIRMATION_REQUIRED'};
 const scoped=u.pathname.match(/^\/g\/(g-p-[A-Za-z0-9-]+)\/c\/([A-Za-z0-9-]{1,160})\/?$/);
 if(scoped){
  if(projectKey(scoped[1])!==p.key)throw Error('PROJECT_ID_MISMATCH');
  return {url:u.href,id:scoped[2],route:'PROJECT_CONVERSATION',project_membership:'URL_PROJECT_ID_MATCH'};
 }
 if(/^\/g\/g-p-[A-Za-z0-9-]+\/project\/?$/.test(u.pathname))throw Error('PROJECT_LANDING_PAGE');
 throw Error('CONVERSATION_ROUTE_UNSUPPORTED');
}
function conversation(value,projectUrl){return conversationInfo(value,projectUrl).url}
function boundConversation(scope,projectUrl){
 const info=conversationInfo(scope.conversation_url,projectUrl),confirmation=scope.project_confirmation;
 if(info.project_membership==='OPERATOR_CONFIRMATION_REQUIRED'&&!(confirmation?.method==='NATIVE_OPERATOR'&&confirmation.project_url===projectUrl&&confirmation.conversation_url===info.url))throw Error('PROJECT_CONFIRMATION_REQUIRED');
 return info.url;
}
function conversationReport(value,projectUrl){
 // Never copy auth URLs, credentials, query values or fragments into reports.
 let address='AUTH_OR_EXTERNAL_VIEW',has_query=false,has_fragment=false;
 try{const u=new URL(value);if(u.origin===ORIGIN&&!u.username&&!u.password){address=u.origin+u.pathname;has_query=!!u.search;has_fragment=!!u.hash}}catch{}
 try{return {address,has_query,has_fragment,expected_project:projectUrl,...conversationInfo(value,projectUrl),error:null}}
 catch(e){return {address,has_query,has_fragment,expected_project:projectUrl,error:e.message}}
}
module.exports={projectInfo,conversation,conversationInfo,boundConversation,conversationReport};
