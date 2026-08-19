"""Read-only provider conformance primitives for bounded dry-runs."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping

from .federation import RepositoryFederationRegistry, RepositoryManifest
from .models import EnterpriseModelError

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_STATUS = {"PASS", "FAIL", "PARTIAL", "UNKNOWN"}


def canonical_manifest_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReadOnlyProviderSnapshot:
    provider_id: str
    provider_commit: str
    manifest_digest: str
    capability: str
    manifest_maximum_authority: str
    runtime_authority: str = "read"

    def validate(self) -> "ReadOnlyProviderSnapshot":
        if not self.provider_id or not self.capability or not _SHA40.fullmatch(self.provider_commit):
            raise EnterpriseModelError("provider identity/capability/exact commit required")
        if not re.fullmatch(r"[0-9a-f]{64}", self.manifest_digest):
            raise EnterpriseModelError("manifest digest must be sha256 hex")
        if self.runtime_authority != "read":
            raise EnterpriseModelError("dry-run provider must remain read-only")
        return self


@dataclass(frozen=True)
class ControlledChangeDryRunReceipt:
    provider_id: str
    provider_commit: str
    manifest_digest: str
    proposal_id: str
    gate_event_id: str
    gate_decision: str
    requested_effect_digest: str
    conformance_digest: str
    executed: bool = False
    actual_effect_digest: str | None = None

    def validate(self, proposal: Any = None, decision: Any = None) -> "ControlledChangeDryRunReceipt":
        required = (self.provider_id, self.provider_commit, self.manifest_digest,
                    self.proposal_id, self.gate_event_id, self.requested_effect_digest,
                    self.conformance_digest)
        if not all(required) or self.gate_decision not in {"ALLOW", "DENY"}:
            raise EnterpriseModelError("invalid dry-run receipt")
        if self.executed or self.actual_effect_digest is not None:
            raise EnterpriseModelError("dry-run receipt cannot claim an effect")
        if proposal is None or decision is None or (self.proposal_id, self.gate_event_id, self.gate_decision) != (proposal.proposal_id, decision.gate_event_id, decision.decision) or decision.proposal_id != proposal.proposal_id:
            raise EnterpriseModelError("dry-run receipt binding mismatch")
        return self


@dataclass(frozen=True)
class ConformanceResult:
    schema: str
    compatibility: str
    authority: str
    failure_semantics: str
    replay_revocation: str
    observability: str
    tenant_scope: str
    supply_chain: str
    overall: str
    promotion_decision: str

    def validate(self) -> "ConformanceResult":
        components = (self.schema, self.compatibility, self.authority, self.failure_semantics,
                      self.replay_revocation, self.observability, self.tenant_scope,
                      self.supply_chain)
        if any(v not in _STATUS for v in (*components, self.overall)):
            raise EnterpriseModelError("invalid conformance status")
        if "FAIL" in components and (self.overall != "FAIL" or self.promotion_decision == "PROMOTE"):
            raise EnterpriseModelError("failure requires overall FAIL")
        elif any(v in {"PARTIAL", "UNKNOWN"} for v in components):
            if self.overall != "PARTIAL" or self.promotion_decision != "HOLD":
                raise EnterpriseModelError("partial/unknown conformance cannot promote")
        return self

    def digest(self) -> str:
        raw = json.dumps(self.__dict__, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def evaluate_read_only_provider(manifest_mapping: Mapping[str, Any], *, provider_id: str,
                                provider_commit: str, expected_commit: str, capability: str,
                                expected_manifest_digest: str) -> tuple[ReadOnlyProviderSnapshot, RepositoryManifest]:
    if provider_commit != expected_commit:
        raise EnterpriseModelError("provider commit does not match pinned dependency")
    manifest = RepositoryFederationRegistry().register_mapping(manifest_mapping)
    if manifest.repository_id != provider_id:
        raise EnterpriseModelError("provider identity mismatch")
    if capability not in manifest.capabilities:
        raise EnterpriseModelError("requested capability absent")
    digest = canonical_manifest_digest(manifest_mapping)
    if digest != expected_manifest_digest:
        raise EnterpriseModelError("provider manifest digest mismatch")
    return ReadOnlyProviderSnapshot(provider_id, provider_commit, digest, capability,
                                    manifest.maximum_authority).validate(), manifest


def current_partial_conformance() -> ConformanceResult:
    return ConformanceResult("PASS", "PASS", "PASS", "PASS", "UNKNOWN", "UNKNOWN",
                             "UNKNOWN", "UNKNOWN", "PARTIAL", "HOLD").validate()
