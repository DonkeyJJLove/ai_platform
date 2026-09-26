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
    """Legacy hybrid backend compatibility must never rewrite the LPCL LION BUS UI."""
    return


def apply_hybrid_gateway_extension(gateway_cls) -> None:
    """Install hybrid semantics exactly once on ``gateway_cls``."""
    if getattr(gateway_cls, "_lion_hybrid_extension", False):
        return

    original_init = gateway_cls.__init__
    original_state = gateway_cls.state
    original_route = gateway_cls._route
    original_chat = gateway_cls.chat

    def init(self, *args, **kwargs):
        self.saas_transport = kwargs.pop("saas_transport", None)
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
        transport=value.get("saas_transport") or self.saas_transport or "UNKNOWN"
        channel=value.get("saas_bridge_state") or "UNKNOWN"
        value["saas_supervisor"] = {
            "provider": "CHATGPT_SAAS_SUPERVISOR",
            "transport": transport,
            "model": self.saas_model,
            "state": channel,
            "session_attestation_state": value.get("saas_session_attestation_state") or "UNKNOWN",
            "automatic_hop_materialized": bool(value.get("automatic_saas_hop_available")),
            "pending_count": value.get("saas_pending_count"),
            "authority_effect": "NONE",
        }
        value["execution_policy"] = "HYBRID_EVIDENCE_FIRST_AUTHORITY_BOUND"
        return value

    def route(self, message):
        low = str(message).lower()
        base = original_route(self, message)
        if base[0] == "AUTHORITY_BOUNDARY":
            return base
        if re.match(r"^\s*(?:co to|czym jest|what is)\s+lion\s*[?.!]*$", low):
            return "SYSTEM_CONTEXT", "canonical LION identity from system context"
        # Provider selection is owned by the explicit composer route layer.
        # This compatibility extension must not infer SAAS/DUAL from prose.
        return base

    def chat(self, message, use_web=False, history=None, output_language="auto"):
        # SaaS/DUAL execution belongs to saas_handoff_extension, which reads
        # current Mission Control transport state.  This legacy compatibility
        # layer only preserves hybrid identity/system-context semantics.
        return original_chat(
            self,
            message,
            use_web=use_web,
            history=history,
            output_language=output_language,
        )

    gateway_cls.__init__ = init
    gateway_cls.state = state
    gateway_cls._route = route
    gateway_cls.chat = chat
    gateway_cls._lion_hybrid_extension = True
    _patch_ui()
