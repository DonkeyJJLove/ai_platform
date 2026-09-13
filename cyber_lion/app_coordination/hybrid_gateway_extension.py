"""R10-R3 hybrid cognitive-plane extension for the canonical local gateway.

The extension is applied by the user-level runtime.  Keeping it separate from the
large gateway/UI carrier makes provider semantics explicit and independently
reviewable.  It adds no authority and never pretends an external SaaS session was
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
    from cyber_lion.app_coordination import local_intelligence_gateway as module

    replacements = (
        (
            'AUTO · LOCAL-first<br><span class="saas-unavailable">SaaS supervisor: unavailable</span><br><small>RAG: deferred · authority NONE</small>',
            'HYBRID · LOCAL + SaaS supervisor<br><span class="ok">SaaS supervisor: EXTERNAL_SESSION_MEDIATED</span><br><small>automatic SaaS hop: not materialized · RAG: deferred · authority NONE</small>',
        ),
        (
            '<div class="k">LOCAL COGNITIVE EXECUTOR</div><h2>LION Local Model</h2><p class="status">Proposal-only GPT‑OSS · live Mission Control/repo/web evidence through material drones · authority NONE</p>',
            '<div class="k">HYBRID COGNITIVE PLANE</div><h2>LION Local + SaaS Supervisor</h2><p class="status">LOCAL gpt-oss-20b-MXFP4 proposal-only · REMOTE CHATGPT_SAAS_SUPERVISOR via EXTERNAL_SESSION_MEDIATED · automatic hop not materialized · authority NONE</p>',
        ),
    )
    ui = module.UI
    for old, new in replacements:
        ui = ui.replace(old, new)
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
