"""Pure environment-lifecycle and production-entry derivation.

The sector intentionally has no host, filesystem, network, key, authority,
merge, release, or deployment effect.  It converts observations and bounded
claims into a multidimensional assurance vector and a fail-closed dossier.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Iterable

from cyber_lion.contracts.environment_lifecycle import (
    AssuranceClaimManifest,
    AssuranceDimension,
    AssuranceDimensionRecord,
    AssuranceState,
    AssuranceVector,
    EnvironmentLifecycleContractError,
    EnvironmentWorld,
    LifecycleState,
    LogicalNodeObservation,
    PhysicalControlDomainObservation,
    WorldClass,
)
from cyber_lion.contracts.production_entry import (
    AuthorityState,
    CURRENTNESS_EVIDENCE_REQUIRED,
    LAB_VALIDATION_DIMENSIONS,
    NON_EXPORTABLE_HARDWARE_KEYSTORE_REQUIRED,
    PHYSICAL_EXTERNAL_CONTROL_DOMAIN_REQUIRED,
    PRODUCTION_READINESS_CERTIFICATION_REQUIRED,
    PRODUCTION_REQUIRED_DIMENSIONS,
    ProductionEntryDossier,
    LifecycleTransitionDecision,
    SEPARATE_AUTHORITY_PLANE_REQUIRED,
)


class ProductionEntryError(EnvironmentLifecycleContractError):
    pass


CANONICAL_REPOSITORY = "DonkeyJJLove/ai_platform"
REFERENCE_BASELINE_BRANCH = "mission/e006-r9d-9g3a1-host-authority-separation-deployment-plane"
REFERENCE_BASELINE_SHA = "23df7e5c95dd540aa057c84ade7409304837a12c"
REFERENCE_BASELINE_TREE = "94cb40f0c0cd61ec03b3b9335e88b7b75ec4d220"
REFERENCE_OBSERVED_AT = "2026-08-28T13:30:30Z"

PRODUCTION_PROCESS_CHAIN = (
    "AUTONOMOUS_ENVIRONMENT_LIFECYCLE_AND_PRODUCTION_ENTRY_SECTOR",
    "CURRENT_LAB_EVIDENCE_REGISTRATION_AND_DOSSIER_BASELINE",
    "LAB_RESILIENCE_AND_AUTONOMOUS_ROLE_RESEARCH",
    "PREPRODUCTION_EVIDENCE_COMPILATION",
    "PHYSICAL_EXTERNAL_CONTROL_DOMAIN_ADMISSION",
    "NON_EXPORTABLE_PRODUCTION_KEY_PROVISIONING",
    "EXTERNAL_TRUST_ANCHOR_ROTATION",
    "PRODUCTION_ENTRY_INDEPENDENT_CERTIFICATION",
    "PRODUCTION_READINESS_CERTIFICATION",
    "PRODUCTION_AUTHORITY_DECISION",
    "PRODUCTION_DEPLOYMENT_CANARY",
    "PRODUCTION_EFFECT_RECONCILIATION",
    "PRODUCTION_ACTIVE_OR_ROLLBACK",
)


@dataclass(frozen=True)
class ClaimClassification:
    accepted: tuple[AssuranceClaimManifest, ...]
    rejected: tuple[AssuranceClaimManifest, ...]
    stale: tuple[AssuranceClaimManifest, ...]
    conflicting: tuple[AssuranceClaimManifest, ...]


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProductionEntryError("timestamp invalid") from exc
    if parsed.tzinfo is None:
        raise ProductionEntryError("timestamp must be timezone-aware")
    return parsed


def classify_world(world: EnvironmentWorld) -> WorldClass:
    """Derive, and verify, the world's topology class.

    Host IDs and hostnames are deliberately ignored for physical-domain count.
    """
    world.validate()
    physical_count = world.physical_domain_count
    logical_count = world.logical_node_count
    runtime_classes = {node.runtime_class.upper() for node in world.logical_nodes}
    if physical_count == 1 and logical_count == 1:
        derived = WorldClass.SINGLE_PROCESS_LAB
    elif physical_count == 1 and logical_count > 1:
        derived = WorldClass.MULTI_LOGICAL_NODE_LAB
    elif physical_count > 1 and logical_count > 1:
        derived = WorldClass.MULTI_PHYSICAL_NODE_LAB
    else:
        derived = world.world_class
    if world.world_class in {
        WorldClass.SINGLE_PROCESS_LAB,
        WorldClass.SINGLE_MACHINE_MULTI_RUNTIME_LAB,
        WorldClass.MULTI_LOGICAL_NODE_LAB,
        WorldClass.MULTI_PHYSICAL_NODE_LAB,
    } and derived is not world.world_class:
        if not (
            world.world_class is WorldClass.SINGLE_MACHINE_MULTI_RUNTIME_LAB
            and physical_count == 1
        ):
            raise ProductionEntryError(
                f"world_class {world.world_class.value} contradicts observed topology {derived.value}"
            )
    if "WSL2" in runtime_classes and physical_count > logical_count:
        raise ProductionEntryError("physical domains cannot be inferred from WSL runtime multiplicity")
    return world.world_class


def _claim_is_stale(
    claim: AssuranceClaimManifest,
    *,
    candidate_sha: str,
    candidate_tree: str,
    generated_at: str,
) -> bool:
    if claim.candidate_sha != candidate_sha or claim.candidate_tree != candidate_tree:
        return True
    rule = claim.expires_at_or_currentness_rule
    if rule.startswith("expires:"):
        return _time(generated_at) >= _time(rule[8:])
    return False


def _classify_claims(
    world: EnvironmentWorld,
    claims: tuple[AssuranceClaimManifest, ...],
    *,
    candidate_sha: str,
    candidate_tree: str,
    generated_at: str,
) -> ClaimClassification:
    world.validate()
    if type(claims) is not tuple:
        raise ProductionEntryError("claims must be tuple")
    seen_ids: set[str] = set()
    accepted: list[AssuranceClaimManifest] = []
    rejected: list[AssuranceClaimManifest] = []
    stale: list[AssuranceClaimManifest] = []
    for claim in claims:
        if type(claim) is not AssuranceClaimManifest:
            raise ProductionEntryError("claim type invalid")
        claim.validate()
        if claim.claim_id in seen_ids:
            raise ProductionEntryError("duplicate claim_id")
        seen_ids.add(claim.claim_id)
        if claim.world_id != world.world_id:
            rejected.append(claim)
            continue
        if _claim_is_stale(
            claim,
            candidate_sha=candidate_sha,
            candidate_tree=candidate_tree,
            generated_at=generated_at,
        ):
            stale.append(claim)
            continue
        accepted.append(claim)

    by_kind: dict[str, list[AssuranceClaimManifest]] = {}
    for claim in accepted:
        by_kind.setdefault(claim.claim_kind, []).append(claim)
    conflicting_ids: set[str] = set()
    for rows in by_kind.values():
        if len({row.claim_statement for row in rows}) > 1:
            conflicting_ids.update(row.claim_id for row in rows)
    conflicting = [row for row in accepted if row.claim_id in conflicting_ids]
    accepted = [row for row in accepted if row.claim_id not in conflicting_ids]
    return ClaimClassification(tuple(accepted), tuple(rejected), tuple(stale), tuple(conflicting))


def _physical_externality(world: EnvironmentWorld) -> bool:
    world.validate()
    if world.physical_domain_count < 2:
        return False
    independently_controlled = [
        domain
        for domain in world.physical_domains
        if domain.independently_controlled
        and domain.virtualization_class.upper() not in {"WSL2", "CONTAINER", "SAME-HOST-VM", "LOGICAL"}
    ]
    if not independently_controlled:
        return False
    used = {node.physical_domain_id for node in world.logical_nodes}
    if len(used) < 2:
        return False
    independent_ids = {domain.physical_domain_id for domain in independently_controlled}
    return any(domain_id not in independent_ids for domain_id in used)


def _non_exportable_hardware_keystore(world: EnvironmentWorld) -> bool:
    world.validate()
    return any(
        domain.independently_controlled
        and domain.hardware_tpm_present
        and domain.hardware_tpm_version == 2
        and domain.non_exportable_keystore
        and domain.virtualization_class.upper() not in {"WSL2", "CONTAINER", "SAME-HOST-VM"}
        for domain in world.physical_domains
    )


def _claim_evidence(claims: Iterable[AssuranceClaimManifest], dimension: AssuranceDimension) -> tuple[str, ...]:
    evidence: list[str] = []
    for claim in claims:
        if dimension in claim.supported_assurance_dimensions:
            evidence.extend(claim.evidence_digests)
            evidence.extend(claim.negative_evidence_digests)
    return tuple(sorted(set(evidence)))


def derive_assurance_vector(
    world: EnvironmentWorld,
    claims: tuple[AssuranceClaimManifest, ...],
    *,
    candidate_sha: str,
    candidate_tree: str,
    generated_at: str,
) -> tuple[AssuranceVector, ClaimClassification]:
    """Derive every assurance dimension without reducing them to one score."""
    classify_world(world)
    classification = _classify_claims(
        world,
        claims,
        candidate_sha=candidate_sha,
        candidate_tree=candidate_tree,
        generated_at=generated_at,
    )
    accepted = classification.accepted
    conflict_dims = {
        dimension
        for claim in classification.conflicting
        for dimension in claim.supported_assurance_dimensions + claim.unsupported_assurance_dimensions
    }
    supported = {
        dimension
        for claim in accepted
        for dimension in claim.supported_assurance_dimensions
    }
    unsupported = {
        dimension
        for claim in accepted
        for dimension in claim.unsupported_assurance_dimensions
    }
    rows: list[AssuranceDimensionRecord] = []
    for dimension in AssuranceDimension:
        if dimension in conflict_dims:
            state = AssuranceState.CONFLICT
        elif dimension in supported:
            state = AssuranceState.PASS
        elif dimension in unsupported:
            state = AssuranceState.BLOCKED
        else:
            state = AssuranceState.UNTESTED

        if dimension is AssuranceDimension.IDENTITY_SEPARATION:
            state = AssuranceState.PASS
        elif dimension is AssuranceDimension.LOGICAL_TOPOLOGY:
            state = AssuranceState.PASS
        elif dimension is AssuranceDimension.PHYSICAL_TOPOLOGY:
            state = AssuranceState.PASS if _physical_externality(world) else AssuranceState.FAIL
        elif dimension is AssuranceDimension.FAILURE_DOMAIN_INDEPENDENCE:
            state = AssuranceState.PASS if _physical_externality(world) else AssuranceState.FAIL
        elif dimension is AssuranceDimension.NON_EXPORTABLE_KEY_STORAGE:
            state = (
                AssuranceState.PASS
                if _physical_externality(world) and _non_exportable_hardware_keystore(world)
                else AssuranceState.BLOCKED
            )
        elif dimension is AssuranceDimension.CURRENTNESS:
            if classification.conflicting:
                state = AssuranceState.CONFLICT
            elif classification.stale:
                state = AssuranceState.STALE
            elif accepted:
                state = AssuranceState.PASS
            else:
                state = AssuranceState.UNTESTED
        elif dimension is AssuranceDimension.AUTHORITY:
            state = AssuranceState.BLOCKED
        elif dimension is AssuranceDimension.DEPLOYMENT_READINESS:
            state = AssuranceState.BLOCKED

        evidence = _claim_evidence(accepted, dimension)
        limitations = tuple(
            limitation
            for claim in accepted
            if dimension in claim.supported_assurance_dimensions or dimension in claim.unsupported_assurance_dimensions
            for limitation in claim.limitations
        )
        if dimension in {AssuranceDimension.PHYSICAL_TOPOLOGY, AssuranceDimension.FAILURE_DOMAIN_INDEPENDENCE} and not _physical_externality(world):
            limitations += ("logical node multiplicity does not prove physical-domain independence",)
        if dimension is AssuranceDimension.NON_EXPORTABLE_KEY_STORAGE and not _non_exportable_hardware_keystore(world):
            limitations += ("no independently observed hardware-backed non-exportable production keystore",)
        rows.append(
            AssuranceDimensionRecord(
                dimension=dimension,
                state=state,
                evidence_ids=evidence,
                world_id=world.world_id,
                observed_at=world.observed_at,
                claim_scope="derived from bounded claims plus world invariants",
                limitations=tuple(dict.fromkeys(limitations)),
                currentness_rule="candidate-exact unless explicitly world-current",
            ).validate()
        )
    vector = AssuranceVector(tuple(rows)).validate()
    return vector, classification


def derive_production_entry_dossier(
    world: EnvironmentWorld,
    claims: tuple[AssuranceClaimManifest, ...],
    *,
    repository: str,
    candidate_sha: str,
    candidate_tree: str,
    candidate_branch: str,
    generated_at: str,
) -> ProductionEntryDossier:
    vector, classification = derive_assurance_vector(
        world,
        claims,
        candidate_sha=candidate_sha,
        candidate_tree=candidate_tree,
        generated_at=generated_at,
    )
    blockers: list[str] = []
    if (
        vector.state_for(AssuranceDimension.PHYSICAL_TOPOLOGY) is not AssuranceState.PASS
        or vector.state_for(AssuranceDimension.FAILURE_DOMAIN_INDEPENDENCE) is not AssuranceState.PASS
    ):
        blockers.append(PHYSICAL_EXTERNAL_CONTROL_DOMAIN_REQUIRED)
    elif vector.state_for(AssuranceDimension.NON_EXPORTABLE_KEY_STORAGE) is not AssuranceState.PASS:
        blockers.append(NON_EXPORTABLE_HARDWARE_KEYSTORE_REQUIRED)
    if vector.state_for(AssuranceDimension.CURRENTNESS) is not AssuranceState.PASS:
        blockers.append(CURRENTNESS_EVIDENCE_REQUIRED)

    physical_group = {
        AssuranceDimension.PHYSICAL_TOPOLOGY,
        AssuranceDimension.FAILURE_DOMAIN_INDEPENDENCE,
        AssuranceDimension.NON_EXPORTABLE_KEY_STORAGE,
        AssuranceDimension.CURRENTNESS,
    }
    missing = tuple(
        dimension.value
        for dimension in PRODUCTION_REQUIRED_DIMENSIONS
        if dimension not in physical_group and vector.state_for(dimension) is not AssuranceState.PASS
    )
    eligible = (
        not blockers
        and not missing
        and all(
            vector.state_for(dimension) is AssuranceState.PASS
            for dimension in PRODUCTION_REQUIRED_DIMENSIONS
        )
    )
    lab_validated = all(
        vector.state_for(dimension) is AssuranceState.PASS
        for dimension in LAB_VALIDATION_DIMENSIONS
    )
    if eligible:
        lifecycle = LifecycleState.PRODUCTION_ENTRY_ELIGIBLE
        next_evidence = (PRODUCTION_READINESS_CERTIFICATION_REQUIRED,)
        human = ()
    elif lab_validated:
        lifecycle = LifecycleState.PRODUCTION_ENTRY_BLOCKED
        next_evidence = (
            "SECOND_PHYSICAL_CONTROL_DOMAIN_OBSERVATION",
            "HARDWARE_TPM2_NON_EXPORTABLE_KEYSTORE_OBSERVATION",
        ) if PHYSICAL_EXTERNAL_CONTROL_DOMAIN_REQUIRED in blockers else tuple(missing)
        human = (
            "CONNECT_PHYSICALLY_INDEPENDENT_PRODUCTION_HOST",
        ) if PHYSICAL_EXTERNAL_CONTROL_DOMAIN_REQUIRED in blockers else ()
    else:
        lifecycle = LifecycleState.LAB_ASSURANCE_ACCUMULATING
        next_evidence = tuple(missing)
        human = ()

    dossier = ProductionEntryDossier(
        repository=repository,
        candidate_sha=candidate_sha,
        candidate_tree=candidate_tree,
        candidate_branch=candidate_branch,
        lifecycle_state=lifecycle,
        assurance_vector=vector,
        accepted_claims=tuple(sorted(claim.claim_id for claim in classification.accepted)),
        rejected_claims=tuple(sorted(claim.claim_id for claim in classification.rejected)),
        stale_claims=tuple(sorted(claim.claim_id for claim in classification.stale)),
        conflicting_claims=tuple(sorted(claim.claim_id for claim in classification.conflicting)),
        missing_dimensions=tuple(sorted(missing)),
        current_blockers=tuple(blockers),
        production_eligible=eligible,
        authority_state=AuthorityState.NONE,
        authority_evidence_digest=None,
        required_next_evidence=tuple(next_evidence),
        required_human_decisions=tuple(human),
        generated_at=generated_at,
    )
    return dossier.sealed()


def evaluate_lifecycle_transition(
    current: LifecycleState,
    target: LifecycleState,
    dossier: ProductionEntryDossier,
) -> LifecycleTransitionDecision:
    """Evaluate lifecycle progression; authority is never manufactured here."""
    dossier.validate()
    if not isinstance(current, LifecycleState) or not isinstance(target, LifecycleState):
        raise ProductionEntryError("lifecycle transition state invalid")
    if target in {
        LifecycleState.PRODUCTION_AUTHORIZED,
        LifecycleState.PRODUCTION_DEPLOYMENT_READY,
        LifecycleState.PRODUCTION_CANARY_ACTIVE,
        LifecycleState.PRODUCTION_ACTIVE,
    }:
        return LifecycleTransitionDecision(
            current, target, False, SEPARATE_AUTHORITY_PLANE_REQUIRED, dossier.digest()
        ).validate()
    if target is LifecycleState.PRODUCTION_ENTRY_ELIGIBLE:
        allowed = dossier.production_eligible
        reason = "DOSSIER_PRODUCTION_ENTRY_ELIGIBLE" if allowed else "DOSSIER_NOT_ELIGIBLE"
    elif target is LifecycleState.PRODUCTION_ENTRY_BLOCKED:
        allowed = not dossier.production_eligible and bool(dossier.current_blockers or dossier.missing_dimensions)
        reason = "DOSSIER_FAIL_CLOSED_BLOCKED" if allowed else "BLOCKED_STATE_NOT_DERIVED"
    elif target in {
        LifecycleState.LAB_EXPERIMENT_ACTIVE,
        LifecycleState.LAB_PROTOCOL_VALIDATED,
        LifecycleState.LAB_ASSURANCE_ACCUMULATING,
    }:
        allowed = True
        reason = "LAB_RESEARCH_TRACK_MAY_CONTINUE"
    elif target is LifecycleState.PRODUCTION_READINESS_CERTIFIED:
        allowed = False
        reason = "INDEPENDENT_PRODUCTION_READINESS_CERTIFICATION_REQUIRED"
    else:
        allowed = False
        reason = "UNMODELED_OR_SEPARATELY_GOVERNED_TRANSITION"
    return LifecycleTransitionDecision(current, target, allowed, reason, dossier.digest()).validate()


def _evidence(tag: str) -> str:
    return sha256(tag.encode("utf-8")).hexdigest()


def canonical_three_wsl_world() -> EnvironmentWorld:
    domain = PhysicalControlDomainObservation(
        physical_domain_id="WINDOWS-MOON",
        machine_identity="WINDOWS-MOON",
        virtualization_class="WINDOWS-HOST-WITH-WSL2",
        hardware_tpm_present=False,
        hardware_tpm_version=None,
        non_exportable_keystore=False,
        independently_controlled=False,
        observed_at=REFERENCE_OBSERVED_AT,
    ).validate()
    nodes = (
        LogicalNodeObservation(
            "host_045dbf1af63f49d4", "MOON", "WSL2", "WINDOWS-MOON",
            "LAB-CONTROL-PLANE", "LAB_CONSUMER_OBSERVER", "NONE", REFERENCE_OBSERVED_AT,
        ).validate(),
        LogicalNodeObservation(
            "host_2c67e8a68ffd6360", "LAB-DEBIAN", "WSL2", "WINDOWS-MOON",
            "LAB-CONTROL-PLANE", "LAB_BOUNDED_PRODUCER", "TEST_ONLY", REFERENCE_OBSERVED_AT,
        ).validate(),
        LogicalNodeObservation(
            "host_df0fa36eb7d44d5b", "LAB-UBUNTU", "WSL2", "WINDOWS-MOON",
            "LAB-CONTROL-PLANE", "LAB_INDEPENDENT_VERIFIER", "NONE", REFERENCE_OBSERVED_AT,
        ).validate(),
    )
    return EnvironmentWorld(
        world_id="e006-r9d-9g3a1-three-wsl-lab",
        world_class=WorldClass.MULTI_LOGICAL_NODE_LAB,
        logical_nodes=nodes,
        physical_domains=(domain,),
        signer_locations=("host_2c67e8a68ffd6360",),
        verifier_locations=("host_df0fa36eb7d44d5b", "host_045dbf1af63f49d4"),
        observer_locations=("host_045dbf1af63f49d4", "host_df0fa36eb7d44d5b"),
        authority_locations=(),
        shared_ancestors=("WINDOWS-MOON",),
        known_limitations=(
            "all three logical nodes share one physical Windows host",
            "LAB-DEBIAN signer uses TEST_ONLY software RSA rather than a production non-exportable hardware keystore",
        ),
        observed_at=REFERENCE_OBSERVED_AT,
    ).validate()


def canonical_three_wsl_claim(
    candidate_sha: str = REFERENCE_BASELINE_SHA,
    candidate_tree: str = REFERENCE_BASELINE_TREE,
) -> AssuranceClaimManifest:
    supported = (
        AssuranceDimension.PROTOCOL_CORRECTNESS,
        AssuranceDimension.ROLE_SEPARATION,
        AssuranceDimension.IDENTITY_SEPARATION,
        AssuranceDimension.LOGICAL_TOPOLOGY,
        AssuranceDimension.OBSERVABILITY,
        AssuranceDimension.EVIDENCE_PROVENANCE,
        AssuranceDimension.CRYPTOGRAPHIC_VERIFICATION,
        AssuranceDimension.PRIVATE_KEY_CUSTODY,
        AssuranceDimension.OPERATIONAL_RESILIENCE,
        AssuranceDimension.RECONCILIATION,
        AssuranceDimension.ROLLBACK_READINESS,
        AssuranceDimension.GOVERNANCE,
    )
    unsupported = (
        AssuranceDimension.PHYSICAL_TOPOLOGY,
        AssuranceDimension.NON_EXPORTABLE_KEY_STORAGE,
        AssuranceDimension.FAILURE_DOMAIN_INDEPENDENCE,
    )
    return AssuranceClaimManifest(
        claim_id="e006-r9d-9g3a1-three-wsl-consensus",
        experiment_id="R9D-9G3A1-LAB-THREE-NODE-EVIDENCE-CONSENSUS",
        world_id=canonical_three_wsl_world().world_id,
        candidate_sha=candidate_sha,
        candidate_tree=candidate_tree,
        claim_kind="THREE_NODE_LAB_PROTOCOL_ASSURANCE",
        claim_statement="three logical WSL nodes agree on bounded public evidence without production externality",
        supported_assurance_dimensions=supported,
        unsupported_assurance_dimensions=unsupported,
        evidence_digests=(
            "8aa72665955b21dfad6c6dbeaa89b9cd136eed4d9e41a6dc2ff01f30fce34082",
            "2ede1759e2caa3d92329ef16f0e592846b1168a60a07edede1fa4aab0d8cbc55",
        ),
        negative_evidence_digests=(
            "b7cf507746df9f2a5ba73846dfe9d2b17f70d06621068c4feaba2a48a7442d96",
        ),
        limitations=(
            "logical routing is not physical independence",
            "TEST_ONLY software signing is not a non-exportable production keystore",
            "consensus is evidence, not authority",
        ),
        issued_at=REFERENCE_OBSERVED_AT,
        observed_at=REFERENCE_OBSERVED_AT,
        expires_at_or_currentness_rule="candidate-exact",
        reproducibility_class="THREE_NODE_TEST_ONLY_REPLAYABLE",
        production_relevance="PRODUCTION_RELEVANT",
        authority_effect="NONE",
    ).validate()


def canonical_future_physical_world() -> EnvironmentWorld:
    observed = "2026-08-28T13:31:00Z"
    domains = (
        PhysicalControlDomainObservation(
            "WINDOWS-MOON", "WINDOWS-MOON", "WINDOWS-HOST-WITH-WSL2",
            False, None, False, False, observed,
        ).validate(),
        PhysicalControlDomainObservation(
            "PHYSICAL-TPM-HOST-01", "RASPBERRY-PI-TPM", "BARE_METAL",
            True, 2, True, True, observed,
        ).validate(),
    )
    nodes = (
        LogicalNodeObservation(
            "host-consumer", "MOON", "WSL2", "WINDOWS-MOON",
            "CONTROL-DOMAIN-CONSUMER", "CONSUMER", "NONE", observed,
        ).validate(),
        LogicalNodeObservation(
            "host-producer", "LION-TPM-PROD-01", "BARE_METAL", "PHYSICAL-TPM-HOST-01",
            "EXTERNAL-SEPARATE-CONTROL-DOMAIN", "EXTERNAL_PRODUCER", "PRODUCTION_CANDIDATE", observed,
        ).validate(),
    )
    return EnvironmentWorld(
        world_id="future-two-physical-domain-production-candidate",
        world_class=WorldClass.MULTI_PHYSICAL_NODE_LAB,
        logical_nodes=nodes,
        physical_domains=domains,
        signer_locations=("host-producer",),
        verifier_locations=("host-consumer",),
        observer_locations=("host-consumer", "host-producer"),
        authority_locations=(),
        shared_ancestors=(),
        known_limitations=("fixture proves eligibility semantics only; it does not create or authorize a production key",),
        observed_at=observed,
    ).validate()


def canonical_future_production_claim(
    candidate_sha: str,
    candidate_tree: str,
) -> AssuranceClaimManifest:
    world = canonical_future_physical_world()
    supported = tuple(
        dimension
        for dimension in PRODUCTION_REQUIRED_DIMENSIONS
        if dimension not in {
            AssuranceDimension.PHYSICAL_TOPOLOGY,
            AssuranceDimension.FAILURE_DOMAIN_INDEPENDENCE,
            AssuranceDimension.NON_EXPORTABLE_KEY_STORAGE,
            AssuranceDimension.CURRENTNESS,
        }
    )
    return AssuranceClaimManifest(
        claim_id="future-physical-production-evidence",
        experiment_id="PHYSICAL_EXTERNAL_CONTROL_DOMAIN_ADMISSION",
        world_id=world.world_id,
        candidate_sha=candidate_sha,
        candidate_tree=candidate_tree,
        claim_kind="PRODUCTION_ENTRY_ASSURANCE",
        claim_statement="separate physical control domain and bounded production evidence satisfy entry prerequisites",
        supported_assurance_dimensions=supported,
        unsupported_assurance_dimensions=(),
        evidence_digests=tuple(_evidence(f"future:{dimension.value}") for dimension in supported),
        negative_evidence_digests=(_evidence("future-negative-falsification"),),
        limitations=("eligibility is not authority; v2 remains unpinned until later stages",),
        issued_at=world.observed_at,
        observed_at=world.observed_at,
        expires_at_or_currentness_rule="candidate-exact",
        reproducibility_class="REFERENCE_FIXTURE_ONLY",
        production_relevance="PRODUCTION_REQUIRED",
        authority_effect="NONE",
    ).validate()


def render_production_entry_status(dossier: ProductionEntryDossier, world: EnvironmentWorld) -> str:
    dossier.validate()
    world.validate()
    lines = [
        "# LION environment lifecycle and production-entry sector",
        "",
        "This document is a deterministic rendering of the canonical world model and production-entry dossier.",
        "It is not an authority grant and cannot make a deployment permissible.",
        "",
        "## Environment lifecycle overview",
        "",
        "Experimentation produces observations; observations support bounded claims; claims update assurance dimensions; "
        "the assurance vector populates the production-entry dossier. Readiness eligibility remains separate from authority.",
        "",
        "## Current laboratory topology",
        "",
        f"- World: `{world.world_id}` / `{world.world_class.value}`",
        f"- Logical nodes: `{world.logical_node_count}`",
        f"- Physical domains: `{world.physical_domain_count}`",
    ]
    for node in world.logical_nodes:
        lines.append(
            f"- `{node.hostname}` (`{node.host_id}`): role `{node.role}`, runtime `{node.runtime_class}`, "
            f"physical domain `{node.physical_domain_id}`, trust `{node.trust_eligibility}`"
        )
    lines += [
        "",
        "Three distinct SentinelX host IDs prove routing identity, not physical independence.",
        "",
        "## Laboratory evidence matrix",
        "",
        "| Dimension | State |",
        "| --- | --- |",
    ]
    for dimension in AssuranceDimension:
        lines.append(f"| {dimension.value} | {dossier.assurance_vector.state_for(dimension).value} |")
    lines += [
        "",
        "## Production-entry dossier",
        "",
        f"- Baseline candidate: `{dossier.candidate_sha}`",
        f"- Baseline tree: `{dossier.candidate_tree}`",
        f"- Lifecycle: `{dossier.lifecycle_state.value}`",
        f"- Production eligible: `{str(dossier.production_eligible).lower()}`",
        f"- Authority state: `{dossier.authority_state.value}`",
        f"- Blockers: `{', '.join(dossier.current_blockers) if dossier.current_blockers else 'none'}`",
        f"- Missing dimensions: `{', '.join(dossier.missing_dimensions) if dossier.missing_dimensions else 'none'}`",
        f"- Dossier digest: `{dossier.digest()}`",
        "",
        "## Lab-to-production transition map",
        "",
        "`LAB_RESEARCH_TRACK` may continue while `PRODUCTION_ENTRY_TRACK` remains blocked. "
        "A laboratory PASS never promotes itself to production.",
        "",
        "Required sequence:",
    ]
    for index, stage in enumerate(PRODUCTION_PROCESS_CHAIN, 1):
        lines.append(f"{index}. `{stage}`")
    lines += [
        "",
        "## Production blocker report",
        "",
        "Current three-WSL evidence may support protocol, role, cryptographic, observability, resilience and reconciliation claims. "
        "It does **not** prove a second physical control domain or a non-exportable hardware production keystore.",
        "",
        "## Production transition runbook",
        "",
        "1. Continue rational TEST_ONLY research without erasing production blockers.",
        "2. Re-register evidence against the exact current candidate before using it for readiness.",
        "3. Admit a separately controlled physical host.",
        "4. Observe TPM 2.0 / equivalent non-exportable keystore capability before materializing production key custody.",
        "5. Independently certify production entry and production readiness.",
        "6. Obtain separate, exact, bounded production authority.",
        "7. Execute canary only after currentness, rollback and reconciliation gates pass.",
        "",
        "## Production invalidation and rollback runbook",
        "",
        "Any loss of currentness, provenance, physical observability, key custody, reconciliation, or rollback capability "
        "must regress readiness or invalidate the transition. UNKNOWN is never SUCCESS.",
        "",
        "## Future two-physical-domain topology",
        "",
        "The target pattern is a consumer/control plane on the existing machine plus one separately controlled physical signer "
        "with a hardware-backed non-exportable keystore. Entry eligibility still does not pin v2 or mint authority.",
        "",
        "## Non-promotion invariants",
        "",
        "- `LOGICAL_HOST_COUNT != PHYSICAL_DOMAIN_COUNT`",
        "- `WSL_INSTANCE != PHYSICAL_CONTROL_DOMAIN`",
        "- `MULTI_NODE_CONSENSUS != PHYSICAL_INDEPENDENCE`",
        "- `LAB_VALIDATION_PASS != PRODUCTION_ADMISSION`",
        "- `TEST_ONLY != PRODUCTION_EXTERNAL`",
        "- `SOFTWARE_RSA_ISOLATION != NON_EXPORTABLE_HARDWARE_KEYSTORE`",
        "- `READINESS != AUTHORITY`",
        "- `OBSERVATION != PERMISSION`",
        "- `UNKNOWN != SUCCESS`",
        "",
    ]
    return "\n".join(lines)


def render_reference_document() -> str:
    world = canonical_three_wsl_world()
    dossier = derive_production_entry_dossier(
        world,
        (canonical_three_wsl_claim(),),
        repository=CANONICAL_REPOSITORY,
        candidate_sha=REFERENCE_BASELINE_SHA,
        candidate_tree=REFERENCE_BASELINE_TREE,
        candidate_branch=REFERENCE_BASELINE_BRANCH,
        generated_at=REFERENCE_OBSERVED_AT,
    )
    return render_production_entry_status(dossier, world)
