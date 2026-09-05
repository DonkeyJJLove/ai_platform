from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple

FENCE_SURFACES = (
    "135df096a721d0932a9ee3b51f93bb19a130f2bd68e96535e646d5e78311fd0c",
    "39ad42d545df0e5fd80b99266dc419a84dc1528746e398ecbdeb69b63f631484",
    "478e559a2f8762b471ec9d69eca2bf03ed2744ab0e4f34593ab5060ae95cad9d",
    "99cfcdb99882099f89c90f9247e1bf13eaacb48422c7e276bed43e216e419fad",
    "e5e829051f5e73e2d4f8135c1b6e1bc76e4712b6e4a91162ddd6cd218eac406b",
    "e631906532cb4c60aa69736270432263cb1d5346afde33cbb01fecec6c793de0",
)
PERMISSION_SURFACE = "dbff98ee0801784d8616fc32d67dfbb2ea19fbfcc1cfbda829cf904953f5631b"
PREPARED_SURFACE = "e5e829051f5e73e2d4f8135c1b6e1bc76e4712b6e4a91162ddd6cd218eac406b"
LIVE_ATTACK_IDS = (
    "WRONG_EXPECTED_STATE",
    "REPLAYED_EFFECT_KEY",
    "REPOSITORY_SUBSTITUTION",
    "ACTOR_SUBSTITUTION",
    "CONTROL_ISSUE_SUBSTITUTION",
)

@dataclass(frozen=True)
class CanonicalMoonAttack:
    attack_id: str
    surface_digests: Tuple[str, ...]
    family: str
    pep: str
    expected_denial: str
    execution_class: str
    conversion_rule: str
    legacy_entrypoint: str

_CANONICAL = (
    CanonicalMoonAttack("STALE_EFFECT_KEY", FENCE_SURFACES, "fence", "DurableMoonFileWriteFence.get", "effect unknown", "STRUCTURAL_ONLY", "EVIDENCE_ONLY", "DurableMoonFileWriteFence.get"),
    CanonicalMoonAttack("WRONG_EXPECTED_STATE", FENCE_SURFACES, "fence", "MoonFileWriteRequest.validate", "REPLACE_EXPECTED_DIGEST requires exact pre-state", "SAFE_LIVE_DENIAL", "FAMILY_EVIDENCE_ONLY", "MoonFileWriteRequest.validate"),
    CanonicalMoonAttack("REPLAYED_EFFECT_KEY", FENCE_SURFACES, "fence", "DurableMoonFileWriteFence.prepare", "durable file-write replay denied", "SAFE_LIVE_DENIAL", "NARROW_TO_PREPARED_IF_SOURCE_PROVES", "DurableMoonFileWriteFence.prepare"),
    CanonicalMoonAttack("CROSS_EPOCH_BINDING", FENCE_SURFACES, "binding", "MediationBindingRegistry.register", "cross-epoch binding replay", "STRUCTURAL_ONLY", "EVIDENCE_ONLY", "MediationBindingRegistry.register"),
    CanonicalMoonAttack("SURFACE_SUBSTITUTION", FENCE_SURFACES, "binding", "SurfaceBindingResolver.resolve", "surface substitution", "STRUCTURAL_ONLY", "EVIDENCE_ONLY", "SurfaceBindingResolver.resolve"),
    CanonicalMoonAttack("PROVIDER_SUBSTITUTION", FENCE_SURFACES, "binding", "SurfaceBindingResolver.resolve", "provider substitution", "STRUCTURAL_ONLY", "EVIDENCE_ONLY", "SurfaceBindingResolver.resolve"),
    CanonicalMoonAttack("ENTRYPOINT_SUBSTITUTION", FENCE_SURFACES, "binding", "SurfaceBindingResolver.resolve", "entrypoint substitution", "STRUCTURAL_ONLY", "EVIDENCE_ONLY", "SurfaceBindingResolver.resolve"),
    CanonicalMoonAttack("REPOSITORY_SUBSTITUTION", (PERMISSION_SURFACE,), "permission", "MoonFileWriteRequest.validate", "fixed execution context mismatch", "SAFE_LIVE_DENIAL", "PERMISSION_IF_REQUEST_GUARD_BOUND", "MoonFileWriteRequest.validate"),
    CanonicalMoonAttack("ACTOR_SUBSTITUTION", (PERMISSION_SURFACE,), "permission", "_PermissionAdmissionResolver.resolve", "authority subject substitution", "SAFE_LIVE_DENIAL", "PERMISSION_IF_BINDING_PEP_MATCHES", "_PermissionAdmissionResolver.resolve"),
    CanonicalMoonAttack("UNTRUSTED_PERMISSION", (PERMISSION_SURFACE,), "permission", "_PermissionAdmissionResolver.resolve", "actor permission is not trusted", "BLOCKED_LIVE", "EVIDENCE_REQUIRED", "_PermissionAdmissionResolver.resolve"),
    CanonicalMoonAttack("STALE_AUTHORITY_SOURCE", (PERMISSION_SURFACE,), "permission", "CanonicalMoonFileWriteMediator.execute", "authority drift", "BLOCKED_LIVE", "EVIDENCE_REQUIRED", "CanonicalMoonFileWriteMediator.execute"),
    CanonicalMoonAttack("CONTROL_ISSUE_SUBSTITUTION", (PERMISSION_SURFACE,), "permission", "MoonFileWriteRequest.validate", "fixed execution context mismatch", "SAFE_LIVE_DENIAL", "PERMISSION_IF_REQUEST_GUARD_BOUND", "MoonFileWriteRequest.validate"),
)
ATTACKS = {a.attack_id: a for a in _CANONICAL}
if len(ATTACKS) != len(_CANONICAL):
    raise RuntimeError("duplicate canonical MOON attack id")

def attack(attack_id: str) -> CanonicalMoonAttack:
    try: return ATTACKS[attack_id]
    except KeyError as exc: raise KeyError(f"unknown canonical MOON attack: {attack_id}") from exc

def live_attacks() -> Tuple[CanonicalMoonAttack, ...]:
    return tuple(attack(a) for a in LIVE_ATTACK_IDS)
