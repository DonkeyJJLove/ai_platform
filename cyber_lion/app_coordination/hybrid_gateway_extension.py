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
            'HYBRID · LOCAL + SaaS supervisor<br><span class="ok">SaaS supervisor: SENTINELX session mediated</span><br><small>browser transport: explicit opt-in · RAG: deferred · authority NONE</small>',
        ),
        (
            'AUTO · LOCAL-first<br><span id="sidebarSaas" class="ok">SaaS supervisor: sprawdzanie…</span><br><small id="sidebarSaasMeta">Hybrid required · authority NONE</small>',
            'AUTO · LOCAL-first · browser opt-in<br><span id="sidebarSaas" class="ok">SaaS supervisor: sprawdzanie…</span><br><small id="sidebarSaasMeta">SentinelX default transport · authority NONE</small>',
        ),
        (
            '<div class="k">LOCAL COGNITIVE EXECUTOR</div><h2>LION Local Model</h2><p class="status">Proposal-only GPT‑OSS · live Mission Control/repo/web evidence through material drones · authority NONE</p>',
            '<div class="k">HYBRID COGNITIVE PLANE</div><h2>LION Local + SaaS Supervisor</h2><p class="status">LOCAL gpt-oss-20b-MXFP4 proposal-only · REMOTE CHATGPT_SAAS_SUPERVISOR through controlled mediation · browser transport requires explicit operator activation · authority NONE</p>',
        ),
        (
            '<p class="status">Brokered Firefox-project mediation · exact request tracking · authority NONE</p>',
            '<p class="status">SentinelX session mediation is the default SaaS path · Firefox UI mediation is explicit opt-in · exact request tracking · authority NONE</p>',
        ),
        (
            '<button onclick="firefoxMediatorControl(\'/control/open\')">Otwórz Firefox Mediator</button><button onclick="firefoxMediatorControl(\'/control/pin-current\')">Przypnij bieżący projekt i chat</button><button onclick="firefoxMediatorControl(\'/control/relay/on\')">Relay ON</button><button onclick="firefoxMediatorControl(\'/control/relay/off\')">Relay OFF</button>',
            '<button onclick="firefoxMediatorControl(\'/control/open\')">Browser: otwórz ręcznie</button><button onclick="firefoxMediatorControl(\'/control/pin-current\')">Browser: przypnij chat</button><button onclick="firefoxMediatorControl(\'/control/relay/on\')">Browser relay: WŁĄCZ</button><button onclick="firefoxMediatorControl(\'/control/relay/off\')">Browser relay: WYŁĄCZ</button>',
        ),
        (
            'Jawne polecenie <code>Na SaaS: &lt;pytanie&gt;</code> tworzy request brokera. Gdy widoczny Firefox Developer jest zalogowany, przypięty do projektu <code>LION_EVOLUSION</code> i mediator ma świeży heartbeat READY, nowe requesty używają transportu <code>CHATGPT_FIREFOX_PROJECT_MEDIATED</code>. Bez świeżego mediatora system pozostaje fail-closed w trybie zewnętrznej mediacji manualnej.',
            'Kanał <code>SAAS · SentinelX default</code> nie uruchamia przeglądarki. Firefox Developer jest transportem opcjonalnym i może wejść do puli dopiero po jawnym <code>Browser relay: WŁĄCZ</code>; <code>WYŁĄCZ</code> natychmiast publikuje stan DISABLED, więc broker wraca do ścieżki SentinelX.',
        ),
        (
            '<select id="composerRoute" title="Kanał odpowiedzi"><option value="AUTO">Auto</option><option value="LOCAL">LOCAL</option><option value="SAAS">SAAS</option><option value="DUAL">DUAL</option></select><select id="lang"',
            '<select id="composerRoute" title="Jawny kanał odpowiedzi"><option value="AUTO">AUTO · LOCAL first</option><option value="LOCAL">LOCAL</option><option value="SAAS">SAAS · SentinelX default</option><option value="DUAL">DUAL · LOCAL + SaaS</option></select><span id="chatContext" class="status">CHAT CONTEXT · thread — · mission — · channel AUTO</span><select id="lang"',
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
        "threads=x.threads||[];patchHtml(threadListEl,",
        "threads=(x.threads||[]).slice().sort((a,b)=>Number(b.created_at||0)-Number(a.created_at||0));patchHtml(threadListEl,",
    )

    context_js = r'''function composerChannelLabel(){let value=$('composerRoute')?.value||'AUTO';return ({AUTO:'AUTO · LOCAL-FIRST',LOCAL:'LOCAL',SAAS:'SAAS · SentinelX default',DUAL:'DUAL · LOCAL + SaaS'})[value]||value}
function renderChatContext(){let el=$('chatContext');if(!el)return;let tid=activeThreadId?String(activeThreadId).slice(0,8):'—',bound=lastPayload?.thread_context||{},mission=bound.mission_id||missionFocusId||'NO_FOCUS',binding=bound.binding_state||'VIEW_FOCUS',inspection=(selectedMissionId&&selectedMissionId!==missionFocusId)?' · inspecting '+selectedMissionId:'';el.textContent='CHAT CONTEXT · thread '+tid+' · mission '+mission+' · '+binding+' · channel '+composerChannelLabel()+inspection}
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
        "qEl.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.ctrlKey){e.preventDefault();go()}});$('composerRoute').addEventListener('change',renderChatContext);async function boot(){renderChatContext();",
    )
    ui = ui.replace(
        "activeThreadId=x.thread_id;history=[];lastQuestion='';lastAnswer='';lastPayload=null;resetMessages();",
        "activeThreadId=x.thread_id;history=[];lastQuestion='';lastAnswer='';lastPayload=null;renderChatContext();resetMessages();",
    )
    ui = ui.replace(
        "activeThreadId=id;history=[];lastQuestion='';lastAnswer='';lastPayload=null;resetMessages();",
        "activeThreadId=id;history=[];lastQuestion='';lastAnswer='';lastPayload=null;renderChatContext();resetMessages();",
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
        self.saas_transport = kwargs.pop("saas_transport", "EXTERNAL_SESSION_MEDIATED")
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
        value["saas_capability"] = "EXTERNAL_SESSION_MEDIATED"
        value["saas_supervisor"] = {
            "provider": "CHATGPT_SAAS_SUPERVISOR",
            "transport": self.saas_transport,
            "model": self.saas_model,
            "state": "AVAILABLE_VIA_EXTERNAL_SESSION"
            if self.saas_transport == "EXTERNAL_SESSION_MEDIATED"
            else "DEGRADED",
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
            "provider": "CHATGPT_SAAS_SUPERVISOR",
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
