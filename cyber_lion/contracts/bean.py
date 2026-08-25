"""Canonical evolvable capability contracts for LION Bean Factory.

A BeanSpec describes a capability.  It is immutable and may declare an authority
ceiling, but it never carries a credential, grant, executable effect, or permission.
A BeanInstance binds an admitted spec to a concrete runtime identity and lifecycle
state; runtime admission remains external to this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Tuple


class BeanContractError(ValueError):
    pass


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
BEAN_TYPES = frozenset({
    "agent", "observer", "builder", "verifier", "adapter", "tool",
    "deterministic_service", "workflow", "reconciler", "provider",
})
AUTHORITY_CLASSES = frozenset({"none", "read", "local_write", "external_write", "financial", "deploy", "privileged"})
LIFECYCLE_STATES = frozenset({
    "ADMITTED", "RUNNING", "QUIESCING", "SUPERSEDED", "REVOKED", "FAILED", "TERMINATED"
})
TERMINAL_STATES = frozenset({"SUPERSEDED", "REVOKED", "FAILED", "TERMINATED"})


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise BeanContractError(f"{name} is invalid")
    return value


def _sha(value: Any, name: str, *, allow_empty: bool = False) -> str:
    if allow_empty and value == "":
        return value
    value = _text(value, name)
    if not _SHA256.fullmatch(value):
        raise BeanContractError(f"{name} must be sha256 hex")
    return value


def _tuple(value: Any, name: str, *, nonempty: bool = False) -> Tuple[str, ...]:
    if type(value) is not tuple or (nonempty and not value):
        raise BeanContractError(f"{name} must be an immutable tuple")
    for item in value:
        _text(item, name)
    if len(set(value)) != len(value):
        raise BeanContractError(f"{name} must be unique")
    return value


def _canonical(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    if isinstance(value, Mapping):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    return value


def _domain_digest(domain: bytes, value: Any) -> str:
    raw = json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(domain + b"\0" + raw).hexdigest()


def _reject_secret_material(values: Tuple[str, ...], name: str) -> None:
    forbidden = ("-----BEGIN PRIVATE KEY", "sk-", "ghp_", "github_pat_", "password=", "secret=", "token=")
    for value in values:
        lowered = value.lower()
        if any(marker.lower() in lowered for marker in forbidden):
            raise BeanContractError(f"{name} cannot contain credential material")


@dataclass(frozen=True)
class BeanSpec:
    bean_id: str
    bean_type: str
    version: str
    purpose: str
    goal_digest: str
    success_conditions: Tuple[str, ...]
    stop_conditions: Tuple[str, ...]
    defer_conditions: Tuple[str, ...]
    inputs: Tuple[str, ...]
    outputs: Tuple[str, ...]
    interfaces: Tuple[str, ...]
    required_capabilities: Tuple[str, ...]
    provided_capabilities: Tuple[str, ...]
    authority_ceiling: str
    required_grants: Tuple[str, ...]
    epistemic_requirements: Tuple[str, ...]
    evidence_requirements: Tuple[str, ...]
    provenance_policy: Tuple[str, ...]
    memory_policy: Tuple[str, ...]
    context_policy: Tuple[str, ...]
    observability_requirements: Tuple[str, ...]
    resource_budget: Tuple[str, ...]
    cost_budget: str
    time_budget: str
    runtime_class: str
    sandbox_class: str
    dependencies: Tuple[str, ...]
    compatibility_constraints: Tuple[str, ...]
    failure_modes: Tuple[str, ...]
    degradation_policy: Tuple[str, ...]
    revocation_policy: Tuple[str, ...]
    security_invariants: Tuple[str, ...]
    acceptance_tests: Tuple[str, ...]
    falsification_conditions: Tuple[str, ...]
    evolution_hooks: Tuple[str, ...]
    replacement_policy: Tuple[str, ...]
    supersession_policy: Tuple[str, ...]
    lineage_parent_digests: Tuple[str, ...] = ()
    implementation_digest: str = ""

    def validate(self) -> "BeanSpec":
        for name in ("bean_id", "version", "purpose", "cost_budget", "time_budget", "runtime_class", "sandbox_class"):
            _text(getattr(self, name), name)
        if self.bean_type not in BEAN_TYPES:
            raise BeanContractError("bean_type is outside the closed vocabulary")
        if self.authority_ceiling not in AUTHORITY_CLASSES:
            raise BeanContractError("authority_ceiling is outside the closed vocabulary")
        _sha(self.goal_digest, "goal_digest")
        _sha(self.implementation_digest, "implementation_digest", allow_empty=True)
        for name in (
            "success_conditions", "stop_conditions", "defer_conditions", "inputs", "outputs", "interfaces",
            "required_capabilities", "provided_capabilities", "required_grants", "epistemic_requirements",
            "evidence_requirements", "provenance_policy", "memory_policy", "context_policy",
            "observability_requirements", "resource_budget", "dependencies", "compatibility_constraints",
            "failure_modes", "degradation_policy", "revocation_policy", "security_invariants", "acceptance_tests",
            "falsification_conditions", "evolution_hooks", "replacement_policy", "supersession_policy",
        ):
            _tuple(getattr(self, name), name)
        for parent in self.lineage_parent_digests:
            _sha(parent, "lineage_parent_digests")
        if len(set(self.lineage_parent_digests)) != len(self.lineage_parent_digests):
            raise BeanContractError("lineage_parent_digests must be unique")
        if not self.provided_capabilities:
            raise BeanContractError("BeanSpec requires at least one provided capability")
        if not self.success_conditions or not self.stop_conditions:
            raise BeanContractError("BeanSpec requires observable success and stop conditions")
        if not self.acceptance_tests or not self.falsification_conditions:
            raise BeanContractError("BeanSpec requires acceptance and falsification conditions")
        if not self.security_invariants:
            raise BeanContractError("BeanSpec requires security invariants")
        if self.authority_ceiling != "none" and not self.observability_requirements:
            raise BeanContractError("non-zero authority ceiling requires explicit observability requirements")
        if set(self.required_capabilities) & set(self.provided_capabilities):
            raise BeanContractError("required and provided capabilities cannot self-satisfy by declaration")
        _reject_secret_material(self.required_grants, "required_grants")
        _reject_secret_material(self.context_policy, "context_policy")
        _reject_secret_material(self.memory_policy, "memory_policy")
        if self.spec_digest() in self.lineage_parent_digests:
            raise BeanContractError("BeanSpec cannot self-parent")
        return self

    def semantic_payload(self) -> Mapping[str, Any]:
        return asdict(self)

    def spec_digest(self) -> str:
        return _domain_digest(b"LION/BEAN-SPEC/1", self.semantic_payload())


@dataclass(frozen=True)
class BeanInstance:
    instance_id: str
    bean_id: str
    spec_digest: str
    implementation_digest: str
    runtime_identity_digest: str
    mission_id: str
    state: str
    generation: int
    created_at: str
    updated_at: str
    evidence_refs: Tuple[str, ...]
    authority_grant_refs: Tuple[str, ...] = ()
    supersedes_instance_id: str = ""

    def validate(self) -> "BeanInstance":
        for name in ("instance_id", "bean_id", "mission_id", "created_at", "updated_at"):
            _text(getattr(self, name), name)
        for name in ("spec_digest", "implementation_digest", "runtime_identity_digest"):
            _sha(getattr(self, name), name)
        if self.state not in LIFECYCLE_STATES:
            raise BeanContractError("invalid BeanInstance lifecycle state")
        if isinstance(self.generation, bool) or not isinstance(self.generation, int) or self.generation < 0:
            raise BeanContractError("generation must be a non-negative integer")
        _tuple(self.evidence_refs, "evidence_refs", nonempty=True)
        _tuple(self.authority_grant_refs, "authority_grant_refs")
        _reject_secret_material(self.authority_grant_refs, "authority_grant_refs")
        if self.supersedes_instance_id:
            _text(self.supersedes_instance_id, "supersedes_instance_id")
            if self.supersedes_instance_id == self.instance_id:
                raise BeanContractError("BeanInstance cannot supersede itself")
        return self

    def digest(self) -> str:
        self.validate()
        return _domain_digest(b"LION/BEAN-INSTANCE/1", self)


def assert_instance_matches_spec(instance: BeanInstance, spec: BeanSpec) -> None:
    instance.validate()
    spec.validate()
    if instance.bean_id != spec.bean_id:
        raise BeanContractError("BeanInstance bean_id substitution detected")
    if instance.spec_digest != spec.spec_digest():
        raise BeanContractError("BeanInstance spec substitution detected")
    if spec.implementation_digest and instance.implementation_digest != spec.implementation_digest:
        raise BeanContractError("BeanInstance implementation substitution detected")
