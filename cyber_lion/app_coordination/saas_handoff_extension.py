from __future__ import annotations

import re

_APPLIED = "_lion_saas_handoff_extension_v1"


def _explicit_saas(message: str) -> bool:
    low = message.lower()
    if "saas" not in low:
        return False
    # Preserve explicit dual-evaluation requests for the existing hybrid route.
    if ("lokaln" in low or "local model" in low or "model lokal" in low) and any(x in low for x in ("to samo", "same question", "porówn", "porown", "i model")):
        return False
    return any(token in low for token in (
        "na saas", "do saas", "wykonaj na saas", "wyślij do saas", "wyslij do saas",
        "handoff", "saas supervisor", "saas:", "saas ->"
    ))


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
        if isinstance(message, str) and _explicit_saas(message):
            return "SAAS_HANDOFF", "explicit operator request for CHATGPT_SAAS_SUPERVISOR"
        return original_route(self, message)

    def state(self):
        out = original_state(self)
        if callable(getattr(self, "control_provider", None)):
            try:
                recent = self.control_provider("recent", {})
                mid = recent.get("focus_mission_id")
                out["saas_session_bridge"] = self.control_provider("saas_status", {"mission_id": mid}) if mid else {"state": "UNBOUND"}
            except Exception as exc:
                out["saas_session_bridge"] = {"state": "UNKNOWN", "error": type(exc).__name__, "authority_effect": "NONE"}
        return out

    def capability_answer(message, mission, state, output_language):
        low = str(message or "").lower()
        if "saas" in low or "chatgpt" in low:
            bridge = (state or {}).get("saas_session_bridge") or {}
            bstate = bridge.get("state") or "UNKNOWN"
            binding = bridge.get("binding") or {}
            pending = bridge.get("pending") or {}
            polish = output_language == "pl" or (output_language == "auto" and bool(re.search(r"[ąćęłńóśźż]|\b(?:masz|czy|jest|łącz|lacz|saas|chatgpt)\b", low)))
            if bstate == "BOUND":
                model = binding.get("model_identity") or "ChatGPT SaaS"
                transport = binding.get("transport") or bridge.get("transport") or "CHATGPT_SENTINELX_SESSION_MEDIATED"
                expires = binding.get("expires_at") or "UNKNOWN"
                if polish:
                    return (f"Tak. LION ma obecnie aktywne, czasowe powiązanie z bieżącą sesją SaaS: {model}. "
                            f"Transport: {transport}; binding wygasa {expires}. "
                            "Nie jest to OpenAI API ani automatyczne przejęcie sesji przeglądarki: żądania SaaS są przekazywane przez kontrolowany handoff tej sesji ChatGPT i wracają z receiptem związanym z exact LPCL. "
                            "SaaS supervisor ma authority_effect=NONE; skutki nadal wymagają aktywnego LPCL i bounded executora.")
                return (f"Yes. LION currently has a time-bounded binding to the live SaaS session: {model}. "
                        f"Transport: {transport}; binding expires at {expires}. This is not OpenAI API or browser-session takeover; SaaS requests use the controlled ChatGPT-session handoff and return with an exact-LPCL-bound receipt. SaaS authority_effect=NONE.")
            if bstate == "PENDING_HANDOFF":
                code = pending.get("request_code") or "UNKNOWN"
                return ((f"Kanał SaaS oczekuje na obsługę bieżącej sesji ChatGPT. Pending handoff: {code}. Wyślij w tej sesji `LION SaaS`; authority_effect=NONE.") if polish else
                        (f"The SaaS channel has a pending handoff ({code}). Send `LION SaaS` in the bound ChatGPT session; authority_effect=NONE."))
            if polish:
                return ("Kanał SaaS jest zaimplementowany, ale bieżąca sesja nie jest teraz związana. Wysłanie jawnego polecenia w rodzaju `Na SaaS: <pytanie>` utworzy kontrolowany handoff; następnie bieżąca sesja ChatGPT musi potwierdzić go gestem `LION SaaS`. Nie używamy OpenAI API.")
            return ("The SaaS bridge is implemented but no live session is currently bound. An explicit `SaaS: <question>` creates a controlled handoff; the current ChatGPT session then acknowledges it with `LION SaaS`. No OpenAI API is used.")
        return original_capability(message, mission, state, output_language) if callable(original_capability) else None

    def chat(self, message, use_web=False, history=None, output_language="auto"):
        if isinstance(message, str) and _explicit_saas(message):
            if not callable(getattr(self, "control_provider", None)):
                raise ValueError("SaaS handoff control provider unavailable")
            recent = self.control_provider("recent", {})
            mission_id = recent.get("focus_mission_id")
            if not mission_id:
                raise ValueError("SaaS handoff requires focus mission")
            question = _question(message)
            handoff = self.control_provider("saas_request", {"mission_id": mission_id, "question": question})
            polish = output_language == "pl" or (output_language == "auto" and bool(re.search(r"[ąćęłńóśźż]|\b(?:kim|co|czy|jak|wykonaj|zapytaj|pytanie)\b", message.lower())))
            if polish:
                answer = ("Żądanie zostało zapisane w kontrolowanym mailboxie SaaS. "
                          f"Kod {handoff['request_code']}; request {handoff['request_id']}. "
                          "W bieżącej sesji ChatGPT wyślij tylko: `LION SaaS`. "
                          "Odpowiedź SaaS zostanie związana z exact LPCL i receipt, ale ma authority_effect=NONE.")
            else:
                answer = ("The request is queued in the controlled SaaS mailbox. "
                          f"Code {handoff['request_code']}; request {handoff['request_id']}. "
                          "In the current ChatGPT session send only: `LION SaaS`. "
                          "The SaaS response will be bound to the exact LPCL with a receipt and authority_effect=NONE.")
            return {
                "route": "SAAS_HANDOFF",
                "answer": answer,
                "authority_boundary": False,
                "rag_sources": [], "currentness": [], "web_sources": [], "web_fetches": [], "source_evidence": [],
                "mission_control": {"focus_mission_id": mission_id},
                "tool_calls": ["lion.saas.handoff.create"],
                "material_receipts": [],
                "saas_handoff": handoff,
                "response_language": output_language,
            }
        return original_chat(self, message, use_web=use_web, history=history, output_language=output_language)

    cls._route = route
    cls._capability_answer = staticmethod(capability_answer)
    cls.state = state
    cls.chat = chat
    setattr(cls, _APPLIED, True)
    return cls
