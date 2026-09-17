"""R10-R3 hybrid cognitive-plane extension for the canonical local gateway.

The extension is applied by the user-level runtime. Keeping it separate from the
large gateway/UI carrier makes provider semantics explicit and independently
reviewable. It adds no authority and never pretends an external SaaS session was
called when only a handoff envelope was created.
"""
from __future__ import annotations

from hashlib import sha256
import re


def _dual_question(message: str) -> str:
    text = str(message).strip()
    for sep in (":", "\n"):
        if sep in text:
            tail = text.rsplit(sep, 1)[-1].strip()
            if len(tail) >= 3:
                return tail
    match = re.search(r"(?:pytanie|question)\s*[—-]?\s*(.+)$", text, re.IGNORECASE)
    if match and match.group(1).strip():
        return match.group(1).strip()
    return text


def _patch_ui() -> None:
    """Patch the legacy carrier without turning the browser into transport policy.

    The panel must make three different things visible instead of conflating them:
    the cognitive channel selected for a turn, the Mission Control focus supplying
    live mission context, and the optional Firefox UI mediator. Firefox stays an
    operator-triggered transport and is never implied by AUTO or SAAS selection.
    """
    from cyber_lion.app_coordination import local_intelligence_gateway as module

    replacements = (
        (
            'AUTO · LOCAL-first<br><span class="saas-unavailable">SaaS supervisor: unavailable</span><br><small>RAG: deferred · authority NONE</small>',
            'HYBRID · LOCAL + SaaS supervisor<br><span class="ok">Remote supervisor: OpenAI Responses direct</span><br><small>browser transport: explicit opt-in · RAG: deferred · authority NONE</small>',
        ),
        (
            'AUTO · LOCAL-first<br><span id="sidebarSaas" class="ok">SaaS supervisor: sprawdzanie…</span><br><small id="sidebarSaasMeta">Hybrid required · authority NONE</small>',
            'AUTO · LOCAL-first · browser opt-in<br><span id="sidebarSaas" class="ok">SaaS supervisor: sprawdzanie…</span><br><small id="sidebarSaasMeta">CONTROL SentinelX · REMOTE OpenAI Responses · authority NONE</small>',
        ),
        (
            '<div class="k">LOCAL COGNITIVE EXECUTOR</div><h2>LION Local Model</h2><p class="status">Proposal-only GPT‑OSS · live Mission Control/repo/web evidence through material drones · authority NONE</p>',
            '<div class="k">HYBRID COGNITIVE PLANE</div><h2>LION Local + SaaS Supervisor</h2><p class="status">LOCAL gpt-oss-20b-MXFP4 proposal-only · REMOTE OpenAI Responses API via direct bridge :8768 · CONTROL SentinelX via :8767 · browser legacy only · authority NONE</p>',
        ),
        (
            '<p class="status">Brokered Firefox-project mediation · exact request tracking · authority NONE</p>',
            '<p class="status">Direct provider mediation through :8768 · control through SentinelX/:8767 · Firefox UI is LEGACY_BROWSER explicit opt-in only · authority NONE</p>',
        ),
        (
            '<button onclick="firefoxMediatorControl(\'/control/open\')">Otwórz Firefox Mediator</button><button onclick="firefoxMediatorControl(\'/control/pin-current\')">Przypnij bieżący projekt i chat</button><button onclick="firefoxMediatorControl(\'/control/relay/on\')">Relay ON</button><button onclick="firefoxMediatorControl(\'/control/relay/off\')">Relay OFF</button>',
            '<button onclick="firefoxMediatorControl(\'/control/open\')">Browser: otwórz ręcznie</button><button onclick="firefoxMediatorControl(\'/control/pin-current\')">Browser: przypnij chat</button><button onclick="firefoxMediatorControl(\'/control/relay/on\')">Browser relay: WŁĄCZ</button><button onclick="firefoxMediatorControl(\'/control/relay/off\')">Browser relay: WYŁĄCZ</button>',
        ),
        (
            'Jawne polecenie <code>Na SaaS: &lt;pytanie&gt;</code> tworzy request brokera. Gdy widoczny Firefox Developer jest zalogowany, przypięty do projektu <code>LION_EVOLUSION</code> i mediator ma świeży heartbeat READY, nowe requesty używają transportu <code>CHATGPT_FIREFOX_PROJECT_MEDIATED</code>. Bez świeżego mediatora system pozostaje fail-closed w trybie zewnętrznej mediacji manualnej.',
            'Kanał <code>SAAS_DIRECT</code> wymaga bridge <code>:8768</code> i transportu <code>OPENAI_RESPONSES_API_MEDIATED</code>. SentinelX jest wyłącznie kanałem CONTROL. <code>LEGACY_BROWSER</code> jest osobnym, jawnym fallbackiem i nigdy nie jest wybierany automatycznie.',
        ),
        (
            '<select id="composerRoute" title="Kanał odpowiedzi"><option value="AUTO">Auto</option><option value="LOCAL">LOCAL</option><option value="SAAS">SAAS</option><option value="DUAL">DUAL</option></select><select id="lang"',
            '<select id="composerRoute" title="Jawny kanał odpowiedzi"><option value="AUTO">AUTO · LOCAL first</option><option value="LOCAL">LOCAL</option><option value="SAAS_DIRECT">SAAS_DIRECT · OpenAI Responses</option><option value="DUAL">DUAL · LOCAL + OpenAI</option><option value="LEGACY_BROWSER">LEGACY_BROWSER · manual Firefox</option></select><span id="chatContext" class="status">CHAT CONTEXT · thread — · mission UNBOUND · channel AUTO</span><button onclick="bindFocusedMission()">Bind mission</button><button onclick="unbindMission()">Unbind</button><select id="lang"',
        ),
    )
    ui = module.UI
    for old, new in replacements:
        ui = ui.replace(old, new)

    # Guard Mission Control polling from restoring a stale viewport after a new
    # chat turn changed the operator's scroll intent.
    if "lionViewportEpoch" not in ui:
        ui = ui.replace("function captureViewport(){let app=", "let lionViewportEpoch=0;function captureViewport(){let app=")
        ui = ui.replace(
            "return {app,appScroll:app?.scrollTop||0,proto,protoScroll:proto?.scrollTop||0,active,selection:",
            "return {epoch:lionViewportEpoch,app,appScroll:app?.scrollTop||0,proto,protoScroll:proto?.scrollTop||0,active,selection:",
        )
        ui = ui.replace("function restoreViewport(v){if(!v)return;", "function restoreViewport(v){if(!v||v.epoch!==lionViewportEpoch)return;")

    # A new assistant turn should reveal the beginning of the answer, not jump
    # to its tail. Thread replay is silent so opening history does not animate
    # through every message. Incrementing lionViewportEpoch invalidates stale
    # mission-refresh snapshots that would otherwise pull the view backwards.
    ui = ui.replace(
        "function addMsg(role,text){let d=document.createElement('div');d.className='msg '+role;patchHtml(d,'<div class=\"role\">'+(role==='user'?'TY':'LION')+'</div><div class=\"md\">'+md(text)+'</div>');messagesEl.appendChild(d);d.scrollIntoView({behavior:'smooth',block:'end'})}",
        "function addMsg(role,text,opts={}){lionViewportEpoch++;let d=document.createElement('div');d.className='msg '+role;patchHtml(d,'<div class=\"role\">'+(role==='user'?'TY':'LION')+'</div><div class=\"md\">'+md(text)+'</div>');messagesEl.appendChild(d);if(opts.scroll!==false)requestAnimationFrame(()=>{try{d.scrollIntoView({behavior:'smooth',block:role==='assistant'?'start':'end'})}catch(_){}})}",
    )
    ui = ui.replace(
        "addMsg(m.role,m.content);history.push({role:m.role,content:m.content});",
        "addMsg(m.role,m.content,{scroll:false});history.push({role:m.role,content:m.content});",
    )

    # Conversation navigation remains stable while a thread receives turns or
    # asynchronous SaaS receipts. Recency still exists in backend metadata but
    # no longer reorders the operator's sidebar under the pointer.
    ui = ui.replace(
        "let history=[];let lastQuestion='';let lastAnswer='';let lastPayload=null;let activeThreadId=null;let threads=[];",
        "let history=[];let lastQuestion='';let lastAnswer='';let lastPayload=null;let activeThreadId=null;let activeThreadContext=null;let threads=[];",
    )
    ui = ui.replace(
        "threads=x.threads||[];patchHtml(threadListEl,",
        "threads=(x.threads||[]).slice().sort((a,b)=>Number(b.created_at||0)-Number(a.created_at||0));patchHtml(threadListEl,",
    )

    context_js = r'''const threadRemoteState=new Map();let lastSupervisorProjection=null;
function composerChannelLabel(){let value=$('composerRoute')?.value||'AUTO';return ({AUTO:'AUTO · LOCAL-FIRST',LOCAL:'LOCAL',SAAS_DIRECT:'SAAS_DIRECT · OpenAI Responses',DUAL:'DUAL · LOCAL + OpenAI',LEGACY_BROWSER:'LEGACY_BROWSER · manual Firefox'})[value]||value}
function channelProvider(value){return value==='SAAS_DIRECT'||value==='DUAL'?'OPENAI':value==='LEGACY_BROWSER'?'CHATGPT_UI':null}
function threadContext(){return lastPayload?.thread_context||activeThreadContext||{}}
function activeRemoteState(){return activeThreadId?(threadRemoteState.get(activeThreadId)||{}):{}}
function setThreadRemoteState(threadId,patch){if(!threadId)return;let next={...(threadRemoteState.get(threadId)||{}),...(patch||{})};threadRemoteState.set(threadId,next);if(threadId===activeThreadId)renderChatContext()}
function hydrateThreadRemoteState(messages,threadId){let latest={};for(const m of (messages||[])){let meta=m.meta||{},rid=meta.saas_request_id||((String(meta.external_receipt_key||'').startsWith('saas:'))?String(meta.external_receipt_key).slice(5):null);if(!rid)continue;latest={request_id:rid,request_state:meta.external_receipt_key?'DELIVERED':'RECORDED',receipt_digest:meta.receipt_digest||latest.receipt_digest||null,remote_model:meta.model_identity||latest.remote_model||null,inference_transport:meta.inference_transport||meta.transport||latest.inference_transport||null}}if(latest.request_id)threadRemoteState.set(threadId,latest);else threadRemoteState.delete(threadId)}
const lionRenderSupervisorCore=renderSupervisor;renderSupervisor=function(view){lastSupervisorProjection=view||{};let out=lionRenderSupervisorCore(view);renderChatContext();return out}
function renderChatContext(){let el=$('chatContext');if(!el)return;let tid=activeThreadId?String(activeThreadId).slice(0,8):'—',bound=threadContext(),remote=activeRemoteState(),mission=bound.mission_id||'UNBOUND',binding=bound.binding_state||'MISSION_UNBOUND',phase=bound.current_phase||bound.mission_phase_snapshot||bound.phase||'—',provider=bound.provider||channelProvider($('composerRoute')?.value)||'NONE',model=remote.remote_model||lastPayload?.supervisor_projection?.model||lastSupervisorProjection?.model||'UNKNOWN',owner=operatorProjection?.control?.control_owner||'UNKNOWN',pair=operatorSessionPaired?'PAIRED':'UNPAIRED',request=remote.request_id?String(remote.request_id).slice(0,18)+'…':'NONE',requestState=remote.request_state||'NONE',receipt=remote.receipt_digest?String(remote.receipt_digest).slice(0,16)+'…':'NONE',inspection=(selectedMissionId&&selectedMissionId!==missionFocusId)?' · inspecting '+selectedMissionId:'';el.textContent='CHAT CONTEXT · thread '+tid+' · mission '+mission+' · phase '+phase+' · '+binding+' · channel '+composerChannelLabel()+' · provider '+provider+' · remote-model '+model+' · CONTROL SentinelX · owner '+owner+' · operator '+pair+' · request '+request+' / '+requestState+' · receipt '+receipt+inspection}
async function persistThreadContext(missionId){if(!activeThreadId)return;let channel=$('composerRoute')?.value||'AUTO',body={mission_id:missionId??null,channel,provider:channelProvider(channel)},r=await fetch('/api/threads/'+encodeURIComponent(activeThreadId)+'/context',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),x=await r.json();if(!r.ok)throw new Error(x.error||('thread context '+r.status));activeThreadContext=x;lastPayload=null;renderChatContext();await refreshThreads();return x}
async function bindFocusedMission(){if(!missionFocusId){alert('Brak aktywnego Mission Control focus do jawnego związania.');return}try{await persistThreadContext(missionFocusId)}catch(e){alert(e.message)}}
async function unbindMission(){try{await persistThreadContext(null)}catch(e){alert(e.message)}}
async function persistThreadChannel(){let current=threadContext();try{await persistThreadContext(current.mission_id||null)}catch(e){alert(e.message)}}
'''
    if "function composerChannelLabel()" not in ui:
        ui = ui.replace("async function state(){", context_js + "async function state(){renderChatContext();")
    ui = ui.replace(
        "missionFocusId=x.focus_mission_id||missions[0]?.mission_id||null;",
        "missionFocusId=x.focus_mission_id||missions[0]?.mission_id||null;renderChatContext();",
    )
    ui = ui.replace(
        "lastPayload=x;if(x.supervisor_projection)",
        "lastPayload=x;renderChatContext();if(x.supervisor_projection)",
    )
    ui = ui.replace(
        "qEl.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.ctrlKey){e.preventDefault();go()}});async function boot(){",
        "qEl.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.ctrlKey){e.preventDefault();go()}});$('composerRoute').addEventListener('change',()=>{renderChatContext();persistThreadChannel()});async function boot(){renderChatContext();",
    )
    ui = ui.replace(
        "activeThreadId=x.thread_id;history=[];lastQuestion='';lastAnswer='';lastPayload=null;resetMessages();",
        "activeThreadId=x.thread_id;activeThreadContext=x;history=[];lastQuestion='';lastAnswer='';lastPayload=null;renderChatContext();resetMessages();",
    )
    ui = ui.replace(
        "activeThreadId=id;history=[];lastQuestion='';lastAnswer='';lastPayload=null;resetMessages();",
        "activeThreadId=id;activeThreadContext=x;hydrateThreadRemoteState(x.messages||[],id);history=[];lastQuestion='';lastAnswer='';lastPayload=null;if(['AUTO','LOCAL','SAAS_DIRECT','DUAL','LEGACY_BROWSER'].includes(x.channel))$('composerRoute').value=x.channel;renderChatContext();resetMessages();",
    )

    ui = ui.replace(
        " const key=h.request_id,threadId=h.thread_id;\n if(pendingSaasPolls.has(key))return pendingSaasPolls.get(key).promise;",
        " const key=h.request_id,threadId=h.thread_id;setThreadRemoteState(threadId,{request_id:key,request_state:h.progress_state||h.status||'WAITING',receipt_digest:h.receipt_digest||null,inference_transport:h.inference_transport||h.transport||null});\n if(pendingSaasPolls.has(key))return pendingSaasPolls.get(key).promise;",
    )
    ui = ui.replace(
        "    if(controller.signal.aborted)return;\n    if(x.status==='RESPONDED'){\n     let meta={};try{meta=JSON.parse(x.response_meta_json||'{}')}catch{}",
        "    if(controller.signal.aborted)return;\n    let polledMeta={};try{polledMeta=JSON.parse(x.response_meta_json||'{}')}catch{};setThreadRemoteState(threadId,{request_id:key,request_state:x.progress_state||x.status||'UNKNOWN',receipt_digest:x.receipt_digest||null,remote_model:polledMeta.model_identity||null,inference_transport:polledMeta.inference_transport||polledMeta.transport||x.inference_transport||x.transport||null});\n    if(x.status==='RESPONDED'){\n     let meta=polledMeta",
    )
    ui = ui.replace(
        "     if(!delivered){handoffBusy(threadId,'SAAS · RESPONDED · zapis do rozmowy');continue}\n     if(!controller.signal.aborted&&threadId===activeThreadId&&!renderedSaasReceipts.has(key))",
        "     if(!delivered){handoffBusy(threadId,'SAAS · RESPONDED · zapis do rozmowy');continue}\n     setThreadRemoteState(threadId,{request_id:key,request_state:'DELIVERED',receipt_digest:x.receipt_digest||meta.receipt_digest||null,remote_model:meta.model_identity||null,inference_transport:meta.inference_transport||meta.transport||x.inference_transport||x.transport||null});\n     if(!controller.signal.aborted&&threadId===activeThreadId&&!renderedSaasReceipts.has(key))",
    )
    ui = ui.replace(
        "if(activeThreadId===id){threadViewGeneration++;chatGeneration++;activeChatController?.abort();activeThreadId=null;history=[];lastQuestion='';lastAnswer='';lastPayload=null;resetMessages();",
        "if(activeThreadId===id){threadViewGeneration++;chatGeneration++;activeChatController?.abort();threadRemoteState.delete(id);activeThreadId=null;activeThreadContext=null;history=[];lastQuestion='';lastAnswer='';lastPayload=null;resetMessages();",
    )

    # Operator controls previously looked clickable while the 8767 operator
    # session was unpaired. Gate only the effect/control buttons, keep Pair,
    # Unpair and Refresh usable, and state the reason directly in the panel.
    operator_guard_js = r'''let operatorSessionPaired=false;
function setOperatorControlAvailability(paired){document.querySelectorAll('#operatorPanel button').forEach(button=>{const action=button.getAttribute('onclick')||'';if(action.startsWith('operatorSend')||action.startsWith('operatorControl'))button.disabled=!paired})}
const lionRefreshOperatorCore=refreshOperator;
refreshOperator=async function(){const mid=selectedMissionId||missionFocusId;if(!mid){operatorSessionPaired=false;setOperatorControlAvailability(false);$('operatorPairState').textContent='UNPAIRED · NO MISSION';$('operatorResult').textContent='Operator control: wybierz aktywną misję.';return}try{const session=await operatorApi('/api/operator/session');operatorSessionPaired=!!session.paired;$('operatorPairState').textContent=operatorSessionPaired?'PAIRED · OPERATOR_PRIMARY':'UNPAIRED · CONTROLS DISABLED';setOperatorControlAvailability(operatorSessionPaired);if(!operatorSessionPaired){$('operatorResult').textContent='Operator control: najpierw Sparuj operatora; sterowanie misją jest jawnie zablokowane.';return}return await lionRefreshOperatorCore()}catch(e){operatorSessionPaired=false;setOperatorControlAvailability(false);$('operatorPairState').textContent='OPERATOR SESSION UNKNOWN';$('operatorResult').textContent='Operator control: '+e.message}}
const lionOperatorSubmitCore=operatorSubmit;
operatorSubmit=async function(action,payload={},target=null){if(!operatorSessionPaired)throw new Error('Operator nie jest sparowany — użyj przycisku Sparuj przed wysłaniem komendy.');return lionOperatorSubmitCore(action,payload,target)};
const lionOperatorUnpairCore=operatorUnpair;
operatorUnpair=async function(){try{return await lionOperatorUnpairCore()}finally{operatorSessionPaired=false;setOperatorControlAvailability(false)}};
setOperatorControlAvailability(false);
'''
    if "operatorSessionPaired=false" not in ui:
        ui = ui.replace("function toggleDebug(){", operator_guard_js + "function toggleDebug(){")

    module.UI = ui


def apply_hybrid_gateway_extension(gateway_cls) -> None:
    """Install hybrid semantics exactly once on ``gateway_cls``."""
    if getattr(gateway_cls, "_lion_hybrid_extension", False):
        return

    original_init = gateway_cls.__init__
    original_state = gateway_cls.state
    original_route = gateway_cls._route
    original_chat = gateway_cls.chat

    def init(self, *args, **kwargs):
        self.saas_transport = kwargs.pop("saas_transport", "OPENAI_RESPONSES_API_MEDIATED")
        self.saas_model = kwargs.pop("saas_model", "UNKNOWN")
        original_init(self, *args, **kwargs)

    def state(self):
        value = original_state(self)
        value["system_class"] = "HYBRID_AI_NATIVE_CONTROL_AND_EXECUTION_ENVIRONMENT"
        material = value.get("material") or {}
        value["material_read_plane"] = material
        mission = value.get("mission_control") or {}
        focus = mission.get("focus") if isinstance(mission, dict) else None
        value["mission_material_plane"] = {
            "mission_id": (focus or {}).get("mission_id"),
            "target": (focus or {}).get("material_target"),
            "materialized": (focus or {}).get("materialized"),
            "ready": (focus or {}).get("ready"),
        }
        value["saas_capability"] = "DIRECT_PROVIDER_BRIDGE"
        value["saas_supervisor"] = {
            "provider": "OPENAI",
            "transport": self.saas_transport,
            "model": self.saas_model,
            "state": "DIRECT_PROVIDER_CONFIGURED" if self.saas_transport == "OPENAI_RESPONSES_API_MEDIATED" else "DEGRADED",
            "automatic_hop_materialized": False,
            "authority_effect": "NONE",
        }
        value["execution_policy"] = "HYBRID_EVIDENCE_FIRST_AUTHORITY_BOUND"
        return value

    def route(self, message):
        low = str(message).lower()
        base = original_route(self, message)
        if base[0] == "AUTHORITY_BOUNDARY":
            return base
        # Explicit composer LOCAL is a hard routing constraint. It must win over
        # content heuristics that would otherwise recognize words such as SaaS +
        # local and synthesize a DUAL_EVALUATION route.
        try:
            from cyber_lion.app_coordination.saas_handoff_extension import ROUTE_CONTEXT
            if ROUTE_CONTEXT.get() == "LOCAL":
                return base
        except Exception:
            pass
        dual = (
            ("saas" in low or "chatgpt" in low)
            and ("lokal" in low or "local" in low)
            and any(
                token in low
                for token in (
                    "zapytaj",
                    "ask",
                    "porównaj",
                    "porownaj",
                    "compare",
                    "to samo pytanie",
                    "same question",
                )
            )
        )
        if dual:
            return "DUAL_EVALUATION", "explicit local plus SaaS comparison requested"
        if re.match(r"^\s*(?:co to|czym jest|what is)\s+lion\s*[?.!]*$", low):
            return "SYSTEM_CONTEXT", "canonical LION identity from system context"
        return base

    def chat(self, message, use_web=False, history=None, output_language="auto"):
        route_name, _ = route(self, message)
        if route_name != "DUAL_EVALUATION":
            return original_chat(
                self,
                message,
                use_web=use_web,
                history=history,
                output_language=output_language,
            )
        question = _dual_question(message)
        local = original_chat(
            self,
            question,
            use_web=use_web,
            history=history,
            output_language=output_language,
        )
        request_id = sha256((self.ctx.digest + "\0" + question).encode("utf-8")).hexdigest()
        handoff = {
            "schema": "LION_SAAS_HANDOFF/1",
            "request_id": request_id,
            "question": question,
            "provider": "OPENAI",
            "transport": self.saas_transport,
            "saas_model": self.saas_model,
            "status": "AWAITING_EXTERNAL_SESSION_MEDIATION",
            "automatic_hop_materialized": False,
            "authority_effect": "NONE",
            "system_context_digest": self.ctx.digest,
        }
        answer = (
            "### Model lokalny · gpt-oss-20b-MXFP4\n"
            + str(local.get("answer") or "")
            + "\n\n### CHATGPT_SAAS_SUPERVISOR\n"
            + "Żądanie zostało przygotowane dla kanału "
            + self.saas_transport
            + ". Automatyczny hop z lokalnego UI do bieżącej sesji SaaS nie jest jeszcze "
            + "zmaterializowany, więc LION nie będzie udawał odpowiedzi zdalnego modelu. "
            + "Handoff ID: `"
            + request_id[:16]
            + "`."
        )
        return {
            "route": "DUAL_EVALUATION",
            "answer": answer,
            "authority_boundary": False,
            "rag_sources": local.get("rag_sources", []),
            "currentness": local.get("currentness", []),
            "web_sources": local.get("web_sources", []),
            "web_fetches": local.get("web_fetches", []),
            "source_evidence": local.get("source_evidence", []),
            "mission_control": local.get("mission_control", {}),
            "tool_calls": local.get("tool_calls", []),
            "material_receipts": local.get("material_receipts", []),
            "response_language": output_language,
            "local_evaluation": {
                "model": "gpt-oss-20b-MXFP4",
                "answer": local.get("answer"),
                "route": local.get("route"),
            },
            "saas_handoff": handoff,
        }

    gateway_cls.__init__ = init
    gateway_cls.state = state
    gateway_cls._route = route
    gateway_cls.chat = chat
    gateway_cls._lion_hybrid_extension = True
    _patch_ui()
