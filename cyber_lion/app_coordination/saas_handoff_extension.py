from __future__ import annotations

import re
from contextvars import ContextVar
from datetime import datetime, timezone

from cyber_lion.mission_control.supervisor_projection import supervisor_projection

THREAD_CONTEXT=ContextVar('lion_saas_thread',default=None)
ROUTE_CONTEXT=ContextVar('lion_composer_route',default='AUTO')
THREAD_BINDING_CONTEXT=ContextVar('lion_thread_binding',default=None)
DIRECT_TRANSPORT='OPENAI_RESPONSES_API_MEDIATED'
FIREFOX_TRANSPORT='CHATGPT_FIREFOX_PROJECT_MEDIATED'
CONTROL_TRANSPORT='SENTINELX_OPERATOR_CONTROL'

_APPLIED = "_lion_saas_handoff_extension_v1"


def _supervisor_status_question(message):
    low = str(message or "").lower()
    return ("saas" in low or "chatgpt" in low) and any(token in low for token in (
        "łączność", "lacznosc", "połączenie", "polaczenie", "kanał", "kanal",
        "binding", "transport", "dostęp", "dostep", "status", "connected", "connection",
    ))


def _explicit_saas(message: str) -> bool:
    if ROUTE_CONTEXT.get()=="LOCAL":return False
    if ROUTE_CONTEXT.get() in {"SAAS","SAAS_DIRECT","LEGACY_BROWSER"}:return True
    low = message.lower()
    if "saas" not in low:
        return False
    # Preserve explicit dual-evaluation requests for the existing hybrid route.
    if ("lokaln" in low or "local model" in low or "model lokal" in low) and any(x in low for x in ("to samo", "same question", "porówn", "porown", "i model")):
        return False
    return any(token in low for token in (
        "na saas", "do saas", "wykonaj na saas", "wyślij do saas", "wyslij do saas",
        "handoff", "saas supervisor", "saas:", "saas ->", "zapytaj saas"
    ))


def _dual_saas_local(message: str) -> bool:
    if ROUTE_CONTEXT.get() in {"LOCAL","SAAS","SAAS_DIRECT","LEGACY_BROWSER"}:return False
    if ROUTE_CONTEXT.get()=="DUAL":return True
    low = message.lower()
    marked = bool(re.search(r"(?is)(?:^|\n)\s*(?:#+\s*)?local\s*:.*(?:^|\n)\s*(?:#+\s*)?saas\s*:", message))
    return marked or (("saas" in low or "chatgpt" in low)
            and ("lokal" in low or "local" in low)
            and any(x in low for x in ("to samo", "same question", "porówn", "porown", "compare", "zapytaj", "zadaj", "ask", "dwa różne", "dwa rozne", "różne pytania", "rozne pytania")))


def _dual_question(message: str) -> str:
    text = message.strip()
    if ":" in text:
        tail = text.split(":", 1)[1].strip()
        if tail:
            return tail
    for pattern in (
        r"(?is)^.*?(?:to samo pytanie|same question)\s*[:\-–—]?\s*(.+)$",
        r"(?is)^.*?(?:zapytaj|ask|porównaj|porownaj|compare).*?(?:o|about)\s+(.+)$",
    ):
        m = re.match(pattern, text)
        if m and m.group(1).strip():
            return m.group(1).strip(" :-–—")
    return text


def _dual_queries(message: str):
    text = message.strip()
    ml = re.search(r"(?is)(?:^|\n)\s*(?:#+\s*)?LOCAL\s*:\s*(.+?)(?=\n\s*(?:#+\s*)?SAAS\s*:)", text)
    ms = re.search(r"(?is)(?:^|\n)\s*(?:#+\s*)?SAAS\s*:\s*(.+)$", text)
    if ml and ms:
        local_q = ml.group(1).strip()
        saas_q = ms.group(1).strip()
        cut = re.search(r"(?is)\n\s*(?:na ko[nń]cu|finally|nie syntetyzuj|do not synthesize|###\s*LOCAL\b)", saas_q)
        if cut: saas_q = saas_q[:cut.start()].strip()
        if local_q and saas_q:
            return local_q, saas_q, True
    q = _dual_question(message)
    return q, q, False


def _question(message: str) -> str:
    text = message.strip()
    # Prefer the explicit payload after a colon when SaaS intent occurs before it.
    if ":" in text and "saas" in text.split(":", 1)[0].lower():
        tail = text.split(":", 1)[1].strip()
        if tail:
            return tail
    patterns = (
        r"(?is)^.*?\bsaas\b\s*(?:zapytanie|pytanie|query|ask)?\s*[-–—>]\s*(.+)$",
        r"(?is)^.*?(?:zapytaj|wyślij|wyslij|ask)\s+(?:model\s+)?saas\s+(?:o\s+)?(.+)$",
        r"(?is)^.*?\b(?:na|do)\s+saas\b\s*(?:zapytanie|pytanie)?\s*(.+)$",
    )
    for pattern in patterns:
        m = re.match(pattern, text)
        if m and m.group(1).strip():
            return m.group(1).strip(" :-–—")
    return text


def apply_saas_handoff_extension(cls):
    if getattr(cls, _APPLIED, False):
        return cls
    original_route = cls._route
    original_chat = cls.chat
    original_state = cls.state
    original_capability = getattr(cls, "_capability_answer", None)

    def route(self, message):
        if _supervisor_status_question(message) and not _explicit_saas(message) and not _dual_saas_local(message):
            return "LION_CAPABILITY_CURRENTNESS", "canonical SaaS supervisor status"
        if isinstance(message, str) and _dual_saas_local(message):
            return "DUAL_EVALUATION_LIVE", "explicit local plus live SaaS comparison requested"
        if isinstance(message, str) and _explicit_saas(message):
            return "SAAS_HANDOFF", "explicit operator request for CHATGPT_SAAS_SUPERVISOR"
        return original_route(self, message)

    def state(self):
        out = original_state(self)
        observed_at = None
        if callable(getattr(self, "control_provider", None)):
            try:
                out["saas_session_bridge"] = self.control_provider("saas_status", {})
                observed_at = datetime.now(timezone.utc).isoformat()
            except Exception as exc:
                out["saas_session_bridge"] = {"state": "UNKNOWN", "error": type(exc).__name__, "authority_effect": "NONE"}
        bridge = out.get("saas_session_bridge") or {}
        supplied = bridge.get("supervisor_projection") if isinstance(bridge, dict) else None
        out["supervisor_projection"] = supplied if isinstance(supplied, dict) else supervisor_projection(
            bridge, now=datetime.now(timezone.utc).isoformat(), observed_at=observed_at,
        )
        return out

    def capability_answer(message, mission, state, output_language):
        low = str(message or "").lower()
        if _supervisor_status_question(message):
            projection = (state or {}).get("supervisor_projection")
            if not isinstance(projection, dict):
                projection = supervisor_projection(None, now=datetime.now(timezone.utc).isoformat())
            polish = output_language == "pl" or (output_language == "auto" and bool(re.search(r"[ąćęłńóśźż]|\b(?:masz|mamy|czy|jest|saas|chatgpt)\b", low)))
            hop = {True: "true", False: "false", None: "UNKNOWN"}.get(projection.get("automatic_hop"), "UNKNOWN")
            pending = projection.get("pending") or {}
            receipt = projection.get("last_receipt") or {}
            lease = projection.get("lease") or {}
            freshness = projection.get("freshness") or {}
            labels = ("Kanał", "sesja", "model", "ważność", "świeżość", "Powody niepewności") if polish else ("Channel", "session", "model", "lease", "freshness", "Unknown reasons")
            answer = (
                f"{labels[0]} SaaS: {projection.get('channel', 'UNKNOWN')}; {labels[1]}: {projection.get('session', 'UNKNOWN')}; "
                f"{labels[2]}: {projection.get('model', 'UNKNOWN')}. "
                f"Control: {projection.get('control_transport', 'UNKNOWN')}; inference: {projection.get('inference_transport', projection.get('transport', 'UNKNOWN'))}; provider: {projection.get('provider', 'UNKNOWN')}; "
                f"{labels[3]}: {lease.get('state', 'UNKNOWN')} ({lease.get('expires_at') or 'UNKNOWN'}); "
                f"{labels[4]}: {freshness.get('state', 'UNKNOWN')}. "
                f"Pending: {pending.get('request_id') or projection.get('pending_state', 'UNKNOWN')}; last_receipt: {receipt.get('receipt_digest') or projection.get('last_receipt_state', 'UNKNOWN')}. "
                f"automatic_local_to_saas_hop={hop}; authority_effect={projection.get('authority', 'NONE')}. "
            )
            answer += ("BOUND oznacza powiązanie sesji, a automatyczny handoff ma osobny stan." if polish else
                       "BOUND describes the session binding; automatic handoff has a separate state.")
            reasons = projection.get("unknown_reasons") or []
            if reasons:
                answer += f" {labels[5]}: " + ", ".join(reasons) + "."
            return answer
        return original_capability(message, mission, state, output_language) if callable(original_capability) else None

    def thread_context(self):
        tid=THREAD_CONTEXT.get();route=ROUTE_CONTEXT.get();binding=THREAD_BINDING_CONTEXT.get()
        if not isinstance(binding,dict):binding={}
        context={"thread_id":tid,"mission_id":binding.get("mission_id"),"phase":binding.get("mission_phase_snapshot"),"composer_route":route,"channel":binding.get("channel") or route,"provider":binding.get("provider"),"binding_revision":binding.get("binding_revision",0),"binding_state":binding.get("binding_state") or "MISSION_UNBOUND","authority_effect":"NONE"}
        mid=context.get("mission_id")
        if mid and callable(getattr(self,"control_provider",None)):
            try:
                snap=self.control_provider("process",{"mission_id":mid});current=(snap.get("process") or {}).get("current_phase") or snap.get("current_phase");state=str(snap.get("state") or (snap.get("process") or {}).get("state") or "").upper();context["current_phase"]=current
                if state in {"COMPLETE","COMPLETED","SUPERSEDED","CANCELLED","FAILED","FAIL","STOPPED"}:context["binding_state"]="MISSION_TERMINAL_CONTEXT"
                elif context.get("phase") and current and context["phase"]!=current:context["binding_state"]="MISSION_BINDING_STALE"
                else:context["binding_state"]="MISSION_BOUND"
            except Exception:context["binding_state"]="MISSION_BINDING_STALE"
        return context

    def chat(self, message, use_web=False, history=None, output_language="auto"):
        context=thread_context(self)
        mission_id=context.get("mission_id")
        if isinstance(message, str) and _dual_saas_local(message):
            if not callable(getattr(self, "control_provider", None)):
                out=original_chat(self, message, use_web=use_web, history=history, output_language=output_language)
                if isinstance(out,dict):out["thread_context"]=context
                return out
            try:
                if not mission_id:raise ValueError("no optional mission context")
                mission_snapshot = self.control_provider("process", {"mission_id": mission_id})
                durable_dual = True
            except Exception:
                mission_snapshot = {"mission_id":mission_id,"state":"UNKNOWN","runtime_state":"UNKNOWN","materialized":None,"ready":None,"process":{}}
                durable_dual = False
            currentness = {
                "mission_id": mission_id,
                "state": mission_snapshot.get("state"),
                "runtime_state": mission_snapshot.get("runtime_state"),
                "materialized": mission_snapshot.get("materialized"),
                "ready": mission_snapshot.get("ready"),
                "process": {k:(mission_snapshot.get("process") or {}).get(k) for k in ("current_phase","progress","authority_state","lpcl_digest")},
                "execution_driver": mission_snapshot.get("execution_driver"),
            }
            if durable_dual:
                dual = self.control_provider("dual_create", {"mission_id":mission_id,"original_request":message,"currentness":currentness})
                local_prompt = dual["local_prompt"]
                saas_prompt = dual["saas_prompt"]
            else:
                local_prompt,saas_prompt,independent=_dual_queries(message)
                dual={"request_id":None,"local_prompt":local_prompt,"saas_prompt":saas_prompt,"independent":independent}
            local = original_chat(self, local_prompt, use_web=use_web, history=None, output_language=output_language)
            if durable_dual:
                self.control_provider("dual_response", {"request_id":dual["request_id"],"provider":"gpt-oss-20b-MXFP4","response_text":str(local.get("answer") or ""),"transport":"LOCAL_MODEL_RUNTIME"})
            if durable_dual:
                handoff_args={"scope_type":"THREAD","thread_id":THREAD_CONTEXT.get(),"mission_id":mission_id,"question":saas_prompt,"authority_effect":"NONE","control_transport":CONTROL_TRANSPORT,"inference_transport":DIRECT_TRANSPORT,"provider":"OPENAI"}
            else:
                scope_type="THREAD" if THREAD_CONTEXT.get() else "CONTROL_PLANE"
                handoff_args={"scope_type":scope_type,"thread_id":THREAD_CONTEXT.get(),"mission_id":mission_id,"question":saas_prompt,"authority_effect":"NONE","control_transport":CONTROL_TRANSPORT,"inference_transport":DIRECT_TRANSPORT,"provider":"OPENAI"}
                if scope_type=="CONTROL_PLANE":
                    handoff_args.pop("thread_id",None)
                    handoff_args.pop("mission_id",None)
            handoff = self.control_provider("saas_request",handoff_args)
            if durable_dual:
                self.control_provider("dual_link_saas", {"request_id":dual["request_id"],"saas_request_id":handoff["request_id"]})
                handoff["dual_request_id"] = dual["request_id"]
            polish = output_language == "pl" or (output_language == "auto" and bool(re.search(r"[ąćęłńóśźż]|\b(?:co|kim|czy|jak|zapytaj|porównaj|porownaj|zadaj)\b", message.lower())))
            local_label = "### LOCAL · gpt-oss-20b-MXFP4\n"
            transport=handoff.get("transport") or "UNKNOWN"
            wait_label = ("\n\n### CHATGPT_SAAS_SUPERVISOR\nOdpowiedź SaaS została zlecona jako niezależna trajektoria. "
                          f"Request `{handoff['request_id']}`, dual `{dual.get('request_id') or 'LEGACY_COMPAT'}`, kod `{handoff['request_code']}`, transport `{transport}`, misja `{mission_id or 'NONE'}`. "
                          "Panel czeka na receipt; końcowy wynik zostanie złączony dopiero po receipt obu modeli.")
            answer = local_label + str(local.get("answer") or "") + wait_label
            return {
                "route": "DUAL_EVALUATION_LIVE",
                "answer": answer,
                "authority_boundary": False,
                "rag_sources": local.get("rag_sources", []),
                "currentness": local.get("currentness", []),
                "web_sources": local.get("web_sources", []),
                "web_fetches": local.get("web_fetches", []),
                "source_evidence": local.get("source_evidence", []),
                "mission_control": mission_snapshot,
                "tool_calls": list(local.get("tool_calls", [])) + ["lion.dual.create","lion.dual.local.receipt","lion.saas.handoff.create","lion.dual.link"],
                "material_receipts": local.get("material_receipts", []),
                "local_evaluation": {"model": "gpt-oss-20b-MXFP4", "question": local_prompt, "answer": local.get("answer"), "route": local.get("route")},
                "saas_question": saas_prompt,
                "independent_questions": True,
                "dual_evaluation": dual,
                "saas_handoff": handoff,
                "thread_context":context,
                "response_language": output_language,
            }
        if isinstance(message, str) and _explicit_saas(message):
            if not callable(getattr(self, "control_provider", None)):
                raise ValueError("SaaS handoff control provider unavailable")
            question = _question(message)
            scope_type="THREAD" if THREAD_CONTEXT.get() else "CONTROL_PLANE"
            chosen_transport=FIREFOX_TRANSPORT if ROUTE_CONTEXT.get()=="LEGACY_BROWSER" else DIRECT_TRANSPORT
            chosen_provider="CHATGPT_UI" if chosen_transport==FIREFOX_TRANSPORT else "OPENAI"
            handoff_args={"scope_type":scope_type,"thread_id":THREAD_CONTEXT.get(),"mission_id":mission_id,"question":question,"authority_effect":"NONE","control_transport":CONTROL_TRANSPORT,"inference_transport":chosen_transport,"provider":chosen_provider}
            if scope_type=="CONTROL_PLANE":
                handoff_args.pop("thread_id",None)
                # CONTROL_PLANE forbids a mission_id; the context remains visible
                # in thread_context but is not falsely encoded as broker scope.
                handoff_args.pop("mission_id",None)
            handoff = self.control_provider("saas_request", handoff_args)
            transport=handoff.get("transport") or "UNKNOWN"
            polish = output_language == "pl" or (output_language == "auto" and bool(re.search(r"[ąćęłńóśźż]|\b(?:kim|co|czy|jak|wykonaj|zapytaj|pytanie)\b", message.lower())))
            firefox_transport=transport==FIREFOX_TRANSPORT
            if polish:
                transport_text=("Firefox UI został jawnie włączony i broker wybrał CHATGPT_FIREFOX_PROJECT_MEDIATED. " if firefox_transport else f"Broker wybrał transport {transport}; Firefox nie jest automatycznie uruchamiany. ")
                answer = ("Żądanie zostało zapisane w kontrolowanym kanale SaaS. "
                          f"Kod {handoff['request_code']}; request {handoff['request_id']}; misja kontekstowa {mission_id or 'NONE'}. "
                          "Panel śledzi dokładnie ten request automatycznie i po otrzymaniu realnego receiptu dopisze odpowiedź do tego samego wątku. "
                          +transport_text+
                          "Powtórzenie identycznego unresolved pytania jest wiązane przez dedupe/retry lineage zamiast mnożyć aktywną kolejkę. Odpowiedź ma authority_effect=NONE.")
            else:
                transport_text=("Firefox UI was explicitly enabled and the broker selected CHATGPT_FIREFOX_PROJECT_MEDIATED. " if firefox_transport else f"The broker selected transport {transport}; Firefox is not launched automatically. ")
                answer = ("The request is queued in the controlled SaaS channel. "
                          f"Code {handoff['request_code']}; request {handoff['request_id']}; contextual mission {mission_id or 'NONE'}. "
                          "The panel follows this exact request and appends the real supervisor response to the same thread when its receipt arrives. "
                          +transport_text+
                          "Repeating the same unresolved question is bound through dedupe/retry lineage instead of multiplying the active queue. authority_effect=NONE.")
            return {
                "route": "SAAS_HANDOFF",
                "answer": answer,
                "authority_boundary": False,
                "rag_sources": [], "currentness": [], "web_sources": [], "web_fetches": [], "source_evidence": [],
                "mission_control": {"focus_mission_id": mission_id},
                "tool_calls": ["lion.saas.handoff.create"],
                "material_receipts": [],
                "saas_handoff": handoff,
                "thread_context":context,
                "response_language": output_language,
            }
        out=original_chat(self, message, use_web=use_web, history=history, output_language=output_language)
        if isinstance(out,dict):out["thread_context"]=context
        return out

    cls._route = route
    cls._capability_answer = staticmethod(capability_answer)
    cls.state = state
    cls.chat = chat
    setattr(cls, _APPLIED, True)
    return cls