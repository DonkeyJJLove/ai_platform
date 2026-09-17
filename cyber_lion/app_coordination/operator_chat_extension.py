"""UI/HTTP materializer for mission-bound LION operator chat.

Browser UI uses the existing paired panel proxy; SentinelX remains a separate
transport identity. Both converge on the durable Mission Control operator bus.
"""
from __future__ import annotations

import json
import re

from .operator_chat_store import (
    _binding_get, _binding_put, _binding_delete, _operator_submit, _poll_operator,
)

_APPLIED = "_lion_operator_chat_extension_v1"
_HANDLER_APPLIED = "_lion_operator_chat_handler_v1"

def _patch_ui() -> None:
    from cyber_lion.app_coordination import local_intelligence_gateway as module

    ui = module.UI
    old_select = '<select id="composerRoute" title="Kanał odpowiedzi"><option value="AUTO">Auto</option><option value="LOCAL">LOCAL</option><option value="SAAS">SAAS</option><option value="DUAL">DUAL</option></select>'
    new_select = '<select id="composerRoute" title="Kanał odpowiedzi"><option value="LION_OPERATOR">LION / Operator Bus</option><option value="LOCAL">Local model</option><option value="SAAS">ChatGPT / Firefox</option><option value="DUAL">Dual · Local + ChatGPT/Firefox</option></select>'
    if old_select not in ui:
        raise RuntimeError("operator chat UI base selector drift")
    ui = ui.replace(old_select, new_select, 1)

    ui = ui.replace(
        'AUTO · LOCAL-first<br><span id="sidebarSaas" class="ok">SaaS supervisor: sprawdzanie…</span><br><small id="sidebarSaasMeta">Hybrid required · authority NONE</small>',
        'THREAD CHANNEL · explicit<br><span id="sidebarSaas" class="ok">ChatGPT/Firefox: optional</span><br><small id="sidebarSaasMeta">Operator bus first-class · browser only by explicit channel</small>',
        1,
    )
    ui = ui.replace(
        '<div class="k">REMOTE COGNITIVE SUPERVISOR</div><h2>CHATGPT_SAAS_SUPERVISOR</h2><p class="status">Brokered Firefox-project mediation · exact request tracking · authority NONE</p>',
        '<div class="k">OPTIONAL EXTERNAL PROVIDER</div><h2>ChatGPT / Firefox</h2><p class="status">Uruchamiany wyłącznie po jawnym wyborze kanału ChatGPT/Firefox lub Dual · nie jest transportem domyślnym LION</p>',
        1,
    )

    chat_marker = '<div class="chat"><div id="messages" class="messages">'
    binding_html = '''<div class="chat"><div id="threadBindingBar" class="control-panel"><div class="row"><div><div class="k">CHAT ↔ MISSION BINDING</div><b id="threadBindingMission">UNBOUND</b><div id="threadBindingMeta" class="status">Kanał LOCAL · browser OFF</div></div><label class="grow">Target <input id="threadTarget" placeholder="mission:&lt;id&gt; | drone:&lt;id&gt; | group:architecture"></label><button type="button" onclick="bindSelectedMission()">Podłącz wybraną misję</button><button type="button" onclick="unbindThreadMission()">Odłącz</button></div></div><div id="messages" class="messages">'''
    if chat_marker not in ui:
        raise RuntimeError("operator chat UI binding marker drift")
    ui = ui.replace(chat_marker, binding_html, 1)

    old_add = "function addMsg(role,text){let d=document.createElement('div');d.className='msg '+role;patchHtml(d,'<div class=\"role\">'+(role==='user'?'TY':'LION')+'</div><div class=\"md\">'+md(text)+'</div>');messagesEl.appendChild(d);d.scrollIntoView({behavior:'smooth',block:'end'})}"
    new_add = "function addMsg(role,text,scrollMode='auto'){let d=document.createElement('div');d.className='msg '+role;patchHtml(d,'<div class=\"role\">'+(role==='user'?'TY':'LION')+'</div><div class=\"md\">'+md(text)+'</div>');messagesEl.appendChild(d);if(scrollMode!=='none')d.scrollIntoView({behavior:scrollMode==='instant'?'auto':'smooth',block:role==='assistant'?'start':'nearest'});return d}"
    if old_add not in ui:
        raise RuntimeError("operator chat UI addMsg drift")
    ui = ui.replace(old_add, new_add, 1)
    ui = ui.replace("threads=x.threads||[];patchHtml(threadListEl,", "threads=(x.threads||[]).sort((a,b)=>(b.created_at||0)-(a.created_at||0));patchHtml(threadListEl,", 1)
    ui = ui.replace("addMsg(m.role,m.content);history.push", "addMsg(m.role,m.content,'none');history.push", 1)

    hook = "qEl.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.ctrlKey){e.preventDefault();go()}});async function boot()"
    if hook not in ui:
        raise RuntimeError("operator chat UI boot hook drift")
    extension_js = r'''
let activeThreadBinding=null;const operatorChatPolls=new Map();
function channelBrowserState(channel){return ['SAAS','DUAL'].includes(channel)?'browser ON (explicit)':'browser OFF'}
function renderThreadBinding(binding){
 activeThreadBinding=binding||{mission_id:null,channel:'LOCAL',target:null,persisted:false};
 const mission=activeThreadBinding.mission_id||'UNBOUND',channel=activeThreadBinding.channel||'LOCAL';
 $('threadBindingMission').textContent=mission;$('threadBindingMeta').textContent='Kanał '+channel+' · '+channelBrowserState(channel)+' · ingress '+(channel==='LION_OPERATOR'?'OPERATOR_PRIMARY via panel proxy':'n/a');
 $('threadTarget').value=activeThreadBinding.target||'';if([...$('composerRoute').options].some(o=>o.value===channel))$('composerRoute').value=channel;
}
async function loadThreadBinding(){if(!activeThreadId){renderThreadBinding(null);return null}const r=await fetch('/api/threads/'+encodeURIComponent(activeThreadId)+'/binding',{cache:'no-store'}),x=await r.json();if(!r.ok)throw new Error(x.error||('binding '+r.status));renderThreadBinding(x);return x}
async function saveThreadBinding(value){if(!activeThreadId)throw new Error('Brak aktywnego wątku');const r=await fetch('/api/threads/'+encodeURIComponent(activeThreadId)+'/binding',{method:'POST',headers:{'Content-Type':'application/json','X-LION-CSRF':OPERATOR_CSRF},body:JSON.stringify(value)}),x=await r.json();if(!r.ok)throw new Error(x.error||('binding '+r.status));renderThreadBinding(x);return x}
async function bindSelectedMission(){const mid=selectedMissionId||missionFocusId;if(!mid){routeEl.textContent='Najpierw wybierz misję';return}try{await saveThreadBinding({mission_id:mid,channel:'LION_OPERATOR',target:'mission:'+mid});routeEl.textContent='BOUND · '+mid+' · LION_OPERATOR'}catch(e){routeEl.textContent='BIND DENIED · '+e.message}}
async function unbindThreadMission(){if(!activeThreadId)return;try{const r=await fetch('/api/threads/'+encodeURIComponent(activeThreadId)+'/binding',{method:'DELETE',headers:{'X-LION-CSRF':OPERATOR_CSRF}}),x=await r.json();if(!r.ok)throw new Error(x.error||('unbind '+r.status));renderThreadBinding(x);routeEl.textContent='UNBOUND · LOCAL'}catch(e){routeEl.textContent='UNBIND DENIED · '+e.message}}
$('composerRoute').addEventListener('change',async()=>{if(!activeThreadId)return;const channel=$('composerRoute').value;try{if(channel==='LION_OPERATOR'&&!activeThreadBinding?.mission_id){$('composerRoute').value='LOCAL';routeEl.textContent='LION_OPERATOR wymaga jawnego podpięcia misji';return}await saveThreadBinding({mission_id:activeThreadBinding?.mission_id||null,channel,target:activeThreadBinding?.target||null})}catch(e){routeEl.textContent='CHANNEL DENIED · '+e.message}});
$('threadTarget').addEventListener('change',async()=>{if(!activeThreadId||!activeThreadBinding?.mission_id)return;try{await saveThreadBinding({mission_id:activeThreadBinding.mission_id,channel:activeThreadBinding.channel,target:$('threadTarget').value.trim()||('mission:'+activeThreadBinding.mission_id)})}catch(e){routeEl.textContent='TARGET DENIED · '+e.message}});
const lionBaseOpenThread=openThread;openThread=async function(id){await lionBaseOpenThread(id);if(activeThreadId===id){await loadThreadBinding();messagesEl.lastElementChild?.scrollIntoView({behavior:'auto',block:'start'})}};
const lionBaseCreateThread=createThread;createThread=async function(){await lionBaseCreateThread();if(activeThreadId)await loadThreadBinding()};
async function pollOperatorChat(info){
 if(!info?.client_request_id||!info.thread_id)return;if(operatorChatPolls.has(info.client_request_id))return operatorChatPolls.get(info.client_request_id);
 const p=(async()=>{const deadline=Date.now()+20*60*1000;while(Date.now()<deadline&&activeThreadId===info.thread_id){await new Promise(r=>setTimeout(r,1200));const rr=await fetch('/api/threads/'+encodeURIComponent(info.thread_id)+'/operator-poll',{cache:'no-store'}),x=await rr.json();if(!rr.ok)throw new Error(x.error||('operator poll '+rr.status));for(const response of (x.responses||[])){if(activeThreadId!==info.thread_id)break;addMsg('assistant',response.content);history.push({role:'assistant',content:response.content});history=history.slice(-16);lastAnswer=response.content}const req=(x.requests||[]).find(r=>r.client_request_id===info.client_request_id);if(req){routeEl.textContent='LION_OPERATOR · '+req.state+' · '+String(req.receipt_digest||'').slice(0,16);if(req.state==='NO_RECIPIENT'){busyEl.textContent='LION · brak bieżącego odbiorcy dla targetu';return}if(req.state==='COMPLETE'){busyEl.textContent='';await refreshThreads();return}}busyEl.textContent='LION · oczekiwanie na odpowiedź misji'}})().catch(e=>{routeEl.textContent='LION_OPERATOR · '+e.message;busyEl.textContent=''}).finally(()=>operatorChatPolls.delete(info.client_request_id));operatorChatPolls.set(info.client_request_id,p);return p
}
const lionBaseGo=go;go=async function(question){
 if($('composerRoute').value!=='LION_OPERATOR')return lionBaseGo(question);
 let text=(question??qEl.value).trim();if(!text||sendEl.disabled)return;if(!activeThreadId)await createThread();await loadThreadBinding();if(!activeThreadBinding?.mission_id){routeEl.textContent='UNBOUND · wybierz misję i kliknij Podłącz';return}
 lastQuestion=text;sendEl.disabled=true;busyEl.textContent='LION Operator Bus → Mission Control…';const requestThreadId=activeThreadId,clientRequestId=(crypto.randomUUID?crypto.randomUUID().replaceAll('-',''):Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join(''));addMsg('user',text);qEl.value='';
 try{const r=await fetch('/api/threads/'+encodeURIComponent(requestThreadId)+'/operator-chat',{method:'POST',headers:{'Content-Type':'application/json','X-LION-CSRF':OPERATOR_CSRF},body:JSON.stringify({message:text,client_request_id:clientRequestId})}),x=await r.json();if(!r.ok)throw new Error(x.error||('operator chat '+r.status));history.push({role:'user',content:text});history=history.slice(-16);routeEl.textContent='LION_OPERATOR · '+(x.admission_state||'ACCEPTED')+' · '+String(x.receipt_digest||'').slice(0,16);await refreshThreads();void pollOperatorChat({...x,thread_id:requestThreadId})}
 catch(e){await reportUiRuntimeError(e,'operator.chat.submit');busyEl.textContent='';}
 finally{sendEl.disabled=false}
};
'''
    ui = ui.replace(hook, extension_js + "\n" + hook, 1)
    module.UI = ui


def _patch_handler() -> None:
    from cyber_lion.app_coordination import local_intelligence_gateway as module

    if getattr(module, _HANDLER_APPLIED, False):
        return
    original_make_handler = module.make_handler

    def make_handler(gateway):
        Base = original_make_handler(gateway)

        class H(Base):
            def _json_body(self, maximum=16000):
                n = int(self.headers.get("Content-Length", "0"))
                if n < 0 or n > maximum:
                    raise ValueError("body size")
                if n and "application/json" not in self.headers.get("Content-Type", ""):
                    raise ValueError("content type")
                return json.loads(self.rfile.read(n)) if n else {}

            def do_GET(self):
                from urllib.parse import unquote
                path = unquote(self.path.split("?", 1)[0])
                m = re.fullmatch(r"/api/threads/([0-9a-f]{32})/binding", path)
                if m:
                    try:
                        return self.out(_binding_get(gateway, m.group(1)))
                    except KeyError:
                        return self.out({"error": "thread not found"}, 404)
                    except Exception as exc:
                        return self.out({"error": type(exc).__name__ + ":" + str(exc)}, 400)
                m = re.fullmatch(r"/api/threads/([0-9a-f]{32})/operator-poll", path)
                if m:
                    try:
                        session = self._operator_session(False, True)
                        return self.out(_poll_operator(gateway, session["gateway_session"], m.group(1)))
                    except PermissionError as exc:
                        return self.out({"error": str(exc)}, 403)
                    except KeyError:
                        return self.out({"error": "thread not found"}, 404)
                    except Exception as exc:
                        return self.out({"error": type(exc).__name__ + ":" + str(exc)}, 400)
                return super().do_GET()

            def do_POST(self):
                from urllib.parse import unquote
                path = unquote(self.path.split("?", 1)[0])
                m = re.fullmatch(r"/api/threads/([0-9a-f]{32})/binding", path)
                if m:
                    try:
                        self._operator_session(True, False)
                        return self.out(_binding_put(gateway, m.group(1), self._json_body()), 201)
                    except PermissionError as exc:
                        return self.out({"error": str(exc)}, 403)
                    except KeyError:
                        return self.out({"error": "thread not found"}, 404)
                    except Exception as exc:
                        return self.out({"error": type(exc).__name__ + ":" + str(exc)}, 400)
                m = re.fullmatch(r"/api/threads/([0-9a-f]{32})/operator-chat", path)
                if m:
                    try:
                        session = self._operator_session(True, True)
                        body = self._json_body()
                        if type(body) is not dict or set(body) != {"message", "client_request_id"}:
                            raise ValueError("operator chat schema")
                        return self.out(_operator_submit(gateway, session["gateway_session"], m.group(1), body["message"], body["client_request_id"]), 201)
                    except PermissionError as exc:
                        return self.out({"error": str(exc)}, 403)
                    except KeyError:
                        return self.out({"error": "thread not found"}, 404)
                    except Exception as exc:
                        return self.out({"error": type(exc).__name__ + ":" + str(exc)}, 400)
                return super().do_POST()

            def do_DELETE(self):
                from urllib.parse import unquote
                path = unquote(self.path.split("?", 1)[0])
                m = re.fullmatch(r"/api/threads/([0-9a-f]{32})/binding", path)
                if m:
                    try:
                        self._operator_session(True, False)
                        return self.out(_binding_delete(gateway, m.group(1)))
                    except PermissionError as exc:
                        return self.out({"error": str(exc)}, 403)
                    except KeyError:
                        return self.out({"error": "thread not found"}, 404)
                    except Exception as exc:
                        return self.out({"error": type(exc).__name__ + ":" + str(exc)}, 400)
                return super().do_DELETE()

        return H

    module.make_handler = make_handler
    setattr(module, _HANDLER_APPLIED, True)


def apply_operator_chat_extension(gateway_cls):
    if getattr(gateway_cls, _APPLIED, False):
        return gateway_cls
    _patch_ui()
    _patch_handler()
    original_state = gateway_cls.state

    def state(self):
        out = original_state(self)
        out["conversation_channels"] = {
            "default_unbound": "LOCAL",
            "mission_bound": "LION_OPERATOR",
            "browser_channel": "EXPLICIT_SAAS_OR_DUAL_ONLY",
            "operator_bus": "AVAILABLE" if callable(getattr(self, "operator_provider", None)) else "UNAVAILABLE",
            "authority_effect": "NONE",
        }
        return out

    gateway_cls.state = state
    setattr(gateway_cls, _APPLIED, True)
    return gateway_cls
