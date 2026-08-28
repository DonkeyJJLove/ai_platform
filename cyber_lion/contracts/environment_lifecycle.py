"""Canonical environment, assurance, and evidence-claim contracts.

This module is intentionally effect-free.  It models *what world an observation
came from* and *what that observation may support*.  Logical routing identities,
hostnames, processes, and consensus are never treated as evidence of physical
or authority separation by themselves.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Any

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EnvironmentLifecycleContractError(ValueError):
    pass


class AssuranceState(str, Enum):
    UNTESTED = "UNTESTED"
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    STALE = "STALE"
    CONFLICT = "CONFLICT"
    BLOCKED = "BLOCKED"


class AssuranceDimension(str, Enum):
    PROTOCOL_CORRECTNESS = "PROTOCOL_CORRECTNESS"
    ROLE_SEPARATION = "ROLE_SEPARATION"
    IDENTITY_SEPARATION = "IDENTITY_SEPARATION"
    LOGICAL_TOPOLOGY = "LOGICAL_TOPOLOGY"
    PHYSICAL_TOPOLOGY = "PHYSICAL_TOPOLOGY"
    OBSERVABILITY = "OBSERVABILITY"
    EVIDENCE_PROVENANCE = "EVIDENCE_PROVENANCE"
    CRYPTOGRAPHIC_VERIFICATION = "CRYPTOGRAPHIC_VERIFICATION"
    PRIVATE_KEY_CUSTODY = "PRIVATE_KEY_CUSTODY"
    NON_EXPORTABLE_KEY_STORAGE = "NON_EXPORTABLE_KEY_STORAGE"
    FAILURE_DOMAIN_INDEPENDENCE = "FAILURE_DOMAIN_INDEPENDENCE"
    OPERATIONAL_RESILIENCE = "OPERATIONAL_RESILIENCE"
    RECONCILIATION = "RECONCILIATION"
    ROLLBACK_READINESS = "ROLLBACK_READINESS"
    CURRENTNESS = "CURRENTNESS"
    GOVERNANCE = "GOVERNANCE"
    AUTHORITY = "AUTHORITY"
    DEPLOYMENT_READINESS = "DEPLOYMENT_READINESS"


class WorldClass(str, Enum):
    UNIT_TEST_WORLD = "UNIT_TEST_WORLD"
    SIMULATION_WORLD = "SIMULATION_WORLD"
    SINGLE_PROCESS_LAB = "SINGLE_PROCESS_LAB"
    SINGLE_MACHINE_MULTI_RUNTIME_LAB = "SINGLE_MACHINE_MULTI_RUNTIME_LAB"
    MULTI_LOGICAL_NODE_LAB = "MULTI_LOGICAL_NODE_LAB"
    MULTI_PHYSICAL_NODE_LAB = "MULTI_PHYSICAL_NODE_LAB"
    PREPRODUCTION = "PREPRODUCTION"
    PRODUCTION_CANDIDATE = "PRODUCTION_CANDIDATE"
    PRODUCTION = "PRODUCTION"
    RECOVERY = "RECOVERY"


class LifecycleState(str, Enum):
    EXPERIMENTAL_UNCLASSIFIED = "EXPERIMENTAL_UNCLASSIFIED"
    LAB_EXPERIMENT_ACTIVE = "LAB_EXPERIMENT_ACTIVE"
    LAB_PROTOCOL_VALIDATED = "LAB_PROTOCOL_VALIDATED"
    LAB_ASSURANCE_ACCUMULATING = "LAB_ASSURANCE_ACCUMULATING"
    PREPRODUCTION_CANDIDATE = "PREPRODUCTION_CANDIDATE"
    PREPRODUCTION_BLOCKED = "PREPRODUCTION_BLOCKED"
    PREPRODUCTION_READY = "PREPRODUCTION_READY"
    PRODUCTION_ENTRY_EVIDENCE_ACCUMULATING = "PRODUCTION_ENTRY_EVIDENCE_ACCUMULATING"
    PRODUCTION_ENTRY_BLOCKED = "PRODUCTION_ENTRY_BLOCKED"
    PRODUCTION_ENTRY_ELIGIBLE = "PRODUCTION_ENTRY_ELIGIBLE"
    PRODUCTION_READINESS_CERTIFIED = "PRODUCTION_READINESS_CERTIFIED"
    PRODUCTION_AUTHORITY_REQUIRED = "PRODUCTION_AUTHORITY_REQUIRED"
    PRODUCTION_AUTHORIZED = "PRODUCTION_AUTHORIZED"
    PRODUCTION_DEPLOYMENT_READY = "PRODUCTION_DEPLOYMENT_READY"
    PRODUCTION_CANARY_ACTIVE = "PRODUCTION_CANARY_ACTIVE"
    PRODUCTION_ACTIVE = "PRODUCTION_ACTIVE"
    PRODUCTION_RECONCILIATION_REQUIRED = "PRODUCTION_RECONCILIATION_REQUIRED"
    PRODUCTION_INVALIDATED = "PRODUCTION_INVALIDATED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


def _text(value: Any, name: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise EnvironmentLifecycleContractError(f"{name} invalid")
    return value


def _sha40(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _SHA40.fullmatch(value):
        raise EnvironmentLifecycleContractError(f"{name} must be sha40")
    return value


def _sha256(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise EnvironmentLifecycleContractError(f"{name} must be sha256")
    return value


def _utc(value: Any, name: str) -> datetime:
    _text(value, name, 128)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EnvironmentLifecycleContractError(f"{name} invalid") from exc
    if parsed.tzinfo is None:
        raise EnvironmentLifecycleContractError(f"{name} must be timezone aware")
    return parsed


def _enum(value: Any, cls: type[Enum], name: str):
    if not isinstance(value, cls):
        raise EnvironmentLifecycleContractError(f"{name} invalid")
    return value


def _tuple_text(values: Any, name: str, *, unique: bool = True) -> tuple[str, ...]:
    if type(values) is not tuple:
        raise EnvironmentLifecycleContractError(f"{name} must be tuple")
    for value in values:
        _text(value, name)
    if unique and len(values) != len(set(values)):
        raise EnvironmentLifecycleContractError(f"{name} must be unique")
    return values


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_digest(domain: bytes, value: Any) -> str:
    if type(domain) is not bytes or not domain:
        raise EnvironmentLifecycleContractError("digest domain invalid")
    return sha256(domain + canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class LogicalNodeObservation:
    host_id: str
    hostname: str
    runtime_class: str
    physical_domain_id: str
    control_domain_id: str
    role: str
    trust_eligibility: str
    observed_at: str

    def validate(self) -> "LogicalNodeObservation":
        for name in (
            "host_id", "hostname", "runtime_class", "physical_domain_id",
            "control_domain_id", "role", "trust_eligibility",
        ):
            _text(getattr(self, name), name)
        _utc(self.observed_at, "observed_at")
        if self.trust_eligibility not in {"NONE", "TEST_ONLY", "PRODUCTION_CANDIDATE", "PRODUCTION"}:
            raise EnvironmentLifecycleContractError("trust_eligibility invalid")
        return self

    def digest(self) -> str:
        self.validate()
        return canonical_digest(b"LION/LOGICAL-NODE-OBSERVATION/1\0", asdict(self))


@dataclass(frozen=True)
class PhysicalControlDomainObservation:
    physical_domain_id: str
    machine_identity: str
    virtualization_class: str
    hardware_tpm_present: bool
    hardware_tpm_version: int | None
    non_exportable_keystore: bool
    independently_controlled: bool
    observed_at: str

    def validate(self) -> "PhysicalControlDomainObservation":
        for name in ("physical_domain_id", "machine_identity", "virtualization_class"):
            _text(getattr(self, name), name)
        if type(self.hardware_tpm_present) is not bool:
            raise EnvironmentLifecycleContractError("hardware_tpm_present invalid")
        if self.hardware_tpm_version is not None and (
            type(self.hardware_tpm_version) is not int or self.hardware_tpm_version <= 0
        ):
            raise EnvironmentLifecycleContractError("hardware_tpm_version invalid")
        if self.hardware_tpm_present is False and self.hardware_tpm_version is not None:
            raise EnvironmentLifecycleContractError("TPM version without TPM")
        if type(self.non_exportable_keystore) is not bool or type(self.independently_controlled) is not bool:
            raise EnvironmentLifecycleContractError("physical-domain boolean invalid")
        _utc(self.observed_at, "observed_at")
        return self

    def digest(self) -> str:
        self.validate()
        return canonical_digest(b"LION/PHYSICAL-CONTROL-DOMAIN-OBSERVATION/1\0", asdict(self))


@dataclass(frozen=True)
class EnvironmentWorld:
    world_id: str
    world_class: WorldClass
    logical_nodes: tuple[LogicalNodeObservation, ...]
    physical_domains: tuple[PhysicalControlDomainObservation, ...]
    signer_locations: tuple[str, ...]
    verifier_locations: tuple[str, ...]
    observer_locations: tuple[str, ...]
    authority_locations: tuple[str, ...]
    shared_ancestors: tuple[str, ...]
    known_limitations: tuple[str, ...]
    observed_at: str

    def validate(self) -> "EnvironmentWorld":
        _text(self.world_id, "world_id")
        _enum(self.world_class, WorldClass, "world_class")
        if type(self.logical_nodes) is not tuple or not self.logical_nodes:
            raise EnvironmentLifecycleContractError("logical_nodes required")
        if type(self.physical_domains) is not tuple or not self.physical_domains:
            raise EnvironmentLifecycleContractError("physical_domains required")
        for node in self.logical_nodes:
            if type(node) is not LogicalNodeObservation:
                raise EnvironmentLifecycleContractError("logical node invalid")
            node.validate()
        for domain in self.physical_domains:
            if type(domain) is not PhysicalControlDomainObservation:
                raise EnvironmentLifecycleContractError("physical domain invalid")
            domain.validate()
        host_ids = tuple(node.host_id for node in self.logical_nodes)
        if len(host_ids) != len(set(host_ids)):
            raise EnvironmentLifecycleContractError("logical host_id collision")
        domain_ids = tuple(domain.physical_domain_id for domain in self.physical_domains)
        if len(domain_ids) != len(set(domain_ids)):
            raise EnvironmentLifecycleContractError("physical domain identity collision")
        known_domains = set(domain_ids)
        for node in self.logical_nodes:
            if node.physical_domain_id not in known_domains:
                raise EnvironmentLifecycleContractError("logical node references unknown physical domain")
        host_set = set(host_ids)
        for name in ("signer_locations", "verifier_locations", "observer_locations", "authority_locations"):
            locations = _tuple_text(getattr(self, name), name)
            if not set(locations).issubset(host_set):
                raise EnvironmentLifecycleContractError(f"{name} references unknown host")
        _tuple_text(self.shared_ancestors, "shared_ancestors")
        _tuple_text(self.known_limitations, "known_limitations", unique=False)
        _utc(self.observed_at, "observed_at")
        return self

    @property
    def logical_node_count(self) -> int:
        self.validate()
        return len(self.logical_nodes)

    @property
    def physical_domain_count(self) -> int:
        self.validate()
        return len(self.physical_domains)

    def digest(self) -> str:
        self.validate()
        payload = asdict(self)
        payload["world_class"] = self.world_class.value
        return canonical_digest(b"LION/ENVIRONMENT-WORLD/1\0", payload)


@dataclass(frozen=True)
class AssuranceClaimManifest:
    claim_id: str
    experiment_id: str
    world_id: str
    candidate_sha: str
    candidate_tree: str
    claim_kind: str
    claim_statement: str
    supported_assurance_dimensions: tuple[AssuranceDimension, ...]
    unsupported_assurance_dimensions: tuple[AssuranceDimension, ...]
    evidence_digests: tuple[str, ...]
    negative_evidence_digests: tuple[str, ...]
    limitations: tuple[str, ...]
    issued_at: str
    observed_at: str
    expires_at_or_currentness_rule: str
    reproducibility_class: str
    production_relevance: str
    authority_effect: str

    def validate(self) -> "AssuranceClaimManifest":
        for name in (
            "claim_id", "experiment_id", "world_id", "claim_kind", "claim_statement",
            "expires_at_or_currentness_rule", "reproducibility_class", "production_relevance",
            "authority_effect",
        ):
            _text(getattr(self, name), name)
        _sha40(self.candidate_sha, "candidate_sha")
        _sha40(self.candidate_tree, "candidate_tree")
        if type(self.supported_assurance_dimensions) is not tuple or type(self.unsupported_assurance_dimensions) is not tuple:
            raise EnvironmentLifecycleContractError("assurance dimensions must be tuples")
        supported = set()
        unsupported = set()
        for dim in self.supported_assurance_dimensions:
            _enum(dim, AssuranceDimension, "supported assurance dimension")
            supported.add(dim)
        for dim in self.unsupported_assurance_dimensions:
            _enum(dim, AssuranceDimension, "unsupported assurance dimension")
            unsupported.add(dim)
        if len(supported) != len(self.supported_assurance_dimensions) or len(unsupported) != len(self.unsupported_assurance_dimensions):
            raise EnvironmentLifecycleContractError("assurance dimensions must be unique")
        if supported & unsupported:
            raise EnvironmentLifecycleContractError("assurance dimension cannot be both supported and unsupported")
        if type(self.evidence_digests) is not tuple or not self.evidence_digests:
            raise EnvironmentLifecycleContractError("positive evidence required")
        for digest in self.evidence_digests + self.negative_evidence_digests:
            _sha256(digest, "evidence_digest")
        _tuple_text(self.limitations, "limitations", unique=False)
        issued = _utc(self.issued_at, "issued_at")
        observed = _utc(self.observed_at, "observed_at")
        if observed > issued:
            raise EnvironmentLifecycleContractError("claim observation after issuance")
        if self.expires_at_or_currentness_rule.startswith("expires:"):
            expiry = _utc(self.expires_at_or_currentness_rule[8:], "expires_at")
            if expiry <= issued:
                raise EnvironmentLifecycleContractError("claim already expired at issuance")
        elif self.expires_at_or_currentness_rule not in {"candidate-exact", "world-current", "never"}:
            raise EnvironmentLifecycleContractError("currentness rule invalid")
        if self.production_relevance not in {"LAB_ONLY", "PRODUCTION_RELEVANT", "PRODUCTION_REQUIRED"}:
            raise EnvironmentLifecycleContractError("production_relevance invalid")
        if self.authority_effect != "NONE":
            raise EnvironmentLifecycleContractError("assurance claim authority_effect must be NONE")
        return self

    def digest(self) -> str:
        self.validate()
        payload = asdict(self)
        payload["supported_assurance_dimensions"] = tuple(x.value for x in self.supported_assurance_dimensions)
        payload["unsupported_assurance_dimensions"] = tuple(x.value for x in self.unsupported_assurance_dimensions)
        return canonical_digest(b"LION/ASSURANCE-CLAIM-MANIFEST/1\0", payload)


@dataclass(frozen=True)
class AssuranceDimensionRecord:
    dimension: AssuranceDimension
    state: AssuranceState
    evidence_ids: tuple[str, ...]
    world_id: str
    observed_at: str
    claim_scope: str
    limitations: tuple[str, ...]
    currentness_rule: str

    def validate(self) -> "AssuranceDimensionRecord":
        _enum(self.dimension, AssuranceDimension, "dimension")
        _enum(self.state, AssuranceState, "state")
        _text(self.world_id, "world_id")
        _utc(self.observed_at, "observed_at")
        _text(self.claim_scope, "claim_scope")
        _text(self.currentness_rule, "currentness_rule")
        if type(self.evidence_ids) is not tuple:
            raise EnvironmentLifecycleContractError("evidence_ids must be tuple")
        for evidence_id in self.evidence_ids:
            _sha256(evidence_id, "evidence_id")
        _tuple_text(self.limitations, "limitations", unique=False)
        return self


@dataclass(frozen=True)
class AssuranceVector:
    records: tuple[AssuranceDimensionRecord, ...]

    def validate(self) -> "AssuranceVector":
        if type(self.records) is not tuple:
            raise EnvironmentLifecycleContractError("assurance records must be tuple")
        for record in self.records:
            if type(record) is not AssuranceDimensionRecord:
                raise EnvironmentLifecycleContractError("assurance record invalid")
            record.validate()
        dimensions = tuple(record.dimension for record in self.records)
        if len(dimensions) != len(set(dimensions)):
            raise EnvironmentLifecycleContractError("duplicate assurance dimension")
        if set(dimensions) != set(AssuranceDimension):
            raise EnvironmentLifecycleContractError("assurance vector must contain every dimension")
        return self

    def state_for(self, dimension: AssuranceDimension) -> AssuranceState:
        self.validate()
        _enum(dimension, AssuranceDimension, "dimension")
        for record in self.records:
            if record.dimension is dimension:
                return record.state
        raise EnvironmentLifecycleContractError("dimension missing")

    def record_for(self, dimension: AssuranceDimension) -> AssuranceDimensionRecord:
        self.validate()
        for record in self.records:
            if record.dimension is dimension:
                return record
        raise EnvironmentLifecycleContractError("dimension missing")

    def digest(self) -> str:
        self.validate()
        payload = []
        for record in self.records:
            row = asdict(record)
            row["dimension"] = record.dimension.value
            row["state"] = record.state.value
            payload.append(row)
        return canonical_digest(b"LION/ASSURANCE-VECTOR/1\0", payload)
