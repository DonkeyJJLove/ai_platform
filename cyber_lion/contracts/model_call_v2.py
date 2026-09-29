"""Compatible successor projection for lion.model-call/v2.

The v2 object preserves the complete semantic payload of lion.model-call/v1 and
adds cognitive-invocation provenance. Existing mission_model_calls/v1 storage is
not mutated by this module.
"""
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import re

SCHEMA_ID = "lion.model-call/v2"
V1_SCHEMA_ID = "lion.model-call/v1"
AUTHORITY_EFFECT = "NONE"
TRANSPORTS = frozenset({
    "LOCAL",
    "SENTINELX_MEDIATED_SAAS",
    "CHATGPT_OPENAI_SECURE_MCP_TUNNEL",
    "CHATGPT_FIREFOX_PROJECT_MEDIATED",
    "OTHER_MEDIATED",
})
HEX = re.compile(r"^[0-9a-f]{64}$")


class ModelCallV2Error(ValueError):
    pass


def _text(value, name, *, allow_none=False):
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ModelCallV2Error(name)
    return value


def _hex(value, name, *, allow_none=False):
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ModelCallV2Error(name)
    return value


@dataclass(frozen=True)
class ModelCallV2:
    # v1 semantic payload
    model_call_id: str
    mission_id: str
    phase_id: str
    task_id: str
    assignment_id: str
    logical_drone_id: str
    material_worker_id: str
    requested_capability: str
    provider: str
    model_requested: str | None
    model_declared: str | None
    model_attested: str | None
    transport: str
    selection_reason: str
    candidate_set_digest: str
    context_revision: int
    state: str
    input_digest: str | None
    result_digest: str | None
    downstream_consumer: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    updated_at: str
    intent_digest: str

    # v2 provenance
    invocation_ref: str
    attempt_ref: str
    provider_ref: str
    model_release_ref: str
    transport_profile_ref: str
    causal_group_ref: str

    authority_effect: str = "NONE"
    source_schema_id: str = V1_SCHEMA_ID
    record_digest: str = ""
    schema_id: str = SCHEMA_ID

    def payload(self):
        data = asdict(self)
        data.pop("record_digest", None)
        return data

    def compute_digest(self):
        encoded = json.dumps(
            self.payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return sha256(b"LION/MODEL-CALL-V2/1\0" + encoded).hexdigest()

    def validate(self, require_digest=True):
        for name in (
            "model_call_id", "mission_id", "phase_id", "task_id", "assignment_id",
            "logical_drone_id", "material_worker_id", "requested_capability",
            "provider", "selection_reason", "state", "created_at", "updated_at",
            "invocation_ref", "attempt_ref", "provider_ref", "model_release_ref",
            "transport_profile_ref", "causal_group_ref",
        ):
            _text(getattr(self, name), name)
        for name in ("model_requested", "model_declared", "model_attested",
                     "downstream_consumer", "started_at", "finished_at"):
            _text(getattr(self, name), name, allow_none=True)
        _hex(self.candidate_set_digest, "candidate_set_digest")
        _hex(self.input_digest, "input_digest", allow_none=True)
        _hex(self.result_digest, "result_digest", allow_none=True)
        _hex(self.intent_digest, "intent_digest")
        if isinstance(self.context_revision, bool) or not isinstance(self.context_revision, int) or self.context_revision < 0:
            raise ModelCallV2Error("context_revision")
        if self.transport not in TRANSPORTS:
            raise ModelCallV2Error("transport")
        if self.authority_effect != AUTHORITY_EFFECT:
            raise ModelCallV2Error("authority")
        if self.source_schema_id != V1_SCHEMA_ID or self.schema_id != SCHEMA_ID:
            raise ModelCallV2Error("schema")
        if require_digest:
            _hex(self.record_digest, "record_digest")
            if self.record_digest != self.compute_digest():
                raise ModelCallV2Error("record digest")
        return self

    def sealed(self):
        return replace(self, record_digest=self.compute_digest()).validate()


def project_v1_to_v2(
    v1: dict,
    *,
    invocation_ref: str,
    attempt_ref: str,
    provider_ref: str,
    model_release_ref: str,
    transport_profile_ref: str,
    causal_group_ref: str,
) -> ModelCallV2:
    if not isinstance(v1, dict):
        raise ModelCallV2Error("v1 record")

    required = {
        "model_call_id", "mission_id", "phase_id", "task_id", "assignment_id",
        "logical_drone_id", "material_worker_id", "requested_capability", "provider",
        "model_requested", "model_declared", "model_attested", "transport",
        "selection_reason", "candidate_set_digest", "context_revision", "state",
        "input_digest", "result_digest", "downstream_consumer", "created_at",
        "started_at", "finished_at", "updated_at", "authority_effect", "intent_digest",
    }
    missing = sorted(required.difference(v1))
    if missing:
        raise ModelCallV2Error(f"v1 record missing fields: {missing}")
    if v1["authority_effect"] != "NONE":
        raise ModelCallV2Error("v1 authority")

    transport_map = {
        "LOCAL": "LOCAL",
        "CHATGPT_OPENAI_SECURE_MCP_TUNNEL": "CHATGPT_OPENAI_SECURE_MCP_TUNNEL",
        "CHATGPT_FIREFOX_PROJECT_MEDIATED": "CHATGPT_FIREFOX_PROJECT_MEDIATED",
    }

    return ModelCallV2(
        model_call_id=v1["model_call_id"],
        mission_id=v1["mission_id"],
        phase_id=v1["phase_id"],
        task_id=v1["task_id"],
        assignment_id=v1["assignment_id"],
        logical_drone_id=v1["logical_drone_id"],
        material_worker_id=v1["material_worker_id"],
        requested_capability=v1["requested_capability"],
        provider=v1["provider"],
        model_requested=v1["model_requested"],
        model_declared=v1["model_declared"],
        model_attested=v1["model_attested"],
        transport=transport_map.get(v1["transport"], "OTHER_MEDIATED"),
        selection_reason=v1["selection_reason"],
        candidate_set_digest=v1["candidate_set_digest"],
        context_revision=v1["context_revision"],
        state=v1["state"],
        input_digest=v1["input_digest"],
        result_digest=v1["result_digest"],
        downstream_consumer=v1["downstream_consumer"],
        created_at=v1["created_at"],
        started_at=v1["started_at"],
        finished_at=v1["finished_at"],
        updated_at=v1["updated_at"],
        intent_digest=v1["intent_digest"],
        invocation_ref=invocation_ref,
        attempt_ref=attempt_ref,
        provider_ref=provider_ref,
        model_release_ref=model_release_ref,
        transport_profile_ref=transport_profile_ref,
        causal_group_ref=causal_group_ref,
    ).sealed()


# Absence of a v1 model-call row is not evidence that no SaaS invocation occurred.
