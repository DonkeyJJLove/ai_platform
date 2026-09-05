from __future__ import annotations

from hashlib import sha256
import inspect
from pathlib import Path
import subprocess

from cyber_lion.contracts.complete_mediation import EffectSurfaceInventory
from cyber_lion.contracts.moon_file_write import CONTROL_ISSUE, REPOSITORY, RUNNER_NAME
from cyber_lion.enterprise.moon_file_write import _require_trusted_permission
from cyber_lion.enterprise.moon_file_write_mediation import (
    CanonicalMoonFileWriteAdmission,
    MoonFileWriteMediationError,
    _require_current_admission,
)
from tools.p0_effect_taxonomy_contract import EffectTaxonomyReconciliationReport
from tools.p0_global_mediation_contract import mediation_closure_record_digest
from tools.p0_moon_permission_policy_reclassification import materialize_policy_v2_readiness
from tools.p0_moon_security_boundary_evidence_contract import (
    SecurityBoundaryEvidenceReport,
    SecurityBoundaryNegativeEvidenceRecord,
    SecurityRequirementEvidenceSatisfaction,
)

PROVIDER_PATH = "cyber_lion/enterprise/moon_file_write.py"
MEDIATION_PATH = "cyber_lion/enterprise/moon_file_write_mediation.py"
VERIFIER_VERSION = "P0-MOON-SECURITY-BOUNDARY-NEGATIVE-EVIDENCE/1"
UNTRUSTED_VALUES = ("read", "triage", "none")
TARGET_PATH = "/home/d2j3/lion-p0-moon-replace-live-cert-r1.canary"


class MoonSecurityBoundaryEvidenceError(RuntimeError):
    pass


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _pep_digest(fn) -> str:
    source = inspect.getsource(fn).encode("utf-8")
    return sha256(b"LION/MOON-SECURITY-BOUNDARY-PEP/1\0" + source).hexdigest()


def _verifier_digest() -> str:
    return sha256(b"LION/MOON-SECURITY-BOUNDARY-VERIFIER/1\0" + VERIFIER_VERSION.encode()).hexdigest()


def _admission(authority_source: str, pdp: str) -> CanonicalMoonFileWriteAdmission:
    return CanonicalMoonFileWriteAdmission(
        request_digest="1" * 64,
        repository=REPOSITORY,
        control_issue=CONTROL_ISSUE,
        actor_login="DonkeyJJLove",
        runner_name=RUNNER_NAME,
        target_path=TARGET_PATH,
        operation_mode="REPLACE_EXPECTED_DIGEST",
        expected_previous_state="PRESENT_EXACT",
        expected_previous_sha256="9" * 64,
        intended_content_sha256="8" * 64,
        intended_content_size=48,
        source_event_digest="2" * 64,
        authority_source_digest=authority_source,
        pdp_decision_digest=pdp,
        authority_epoch=None,
        provider_id="fixed-in-memory-security-evidence",
    ).sealed()


def _capture_untrusted_permission() -> tuple[tuple[str, ...], tuple[str, ...]]:
    denials = []
    types = []
    for permission in UNTRUSTED_VALUES:
        try:
            _require_trusted_permission(permission)
        except MoonFileWriteMediationError as exc:
            denials.append(str(exc)); types.append(type(exc).__name__)
        else:
            raise MoonSecurityBoundaryEvidenceError("untrusted permission unexpectedly accepted")
    return tuple(denials), tuple(types)


def _capture_stale_authority() -> tuple[str, str, tuple[str, ...], tuple[str, ...]]:
    baseline = _admission("3" * 64, "4" * 64)
    current = _admission("5" * 64, "6" * 64)
    if baseline.admission_digest == current.admission_digest:
        raise MoonSecurityBoundaryEvidenceError("fixed stale-authority admissions unexpectedly equal")
    try:
        _require_current_admission(baseline, current)
    except MoonFileWriteMediationError as exc:
        return baseline.admission_digest, current.admission_digest, (str(exc),), (type(exc).__name__,)
    raise MoonSecurityBoundaryEvidenceError("stale authority unexpectedly accepted")


def materialize_security_boundary_evidence(*, inventory: EffectSurfaceInventory, taxonomy_report: EffectTaxonomyReconciliationReport, repo_root: Path):
    mappings, policy, closure, carrier, topology_report = materialize_policy_v2_readiness(inventory=inventory, taxonomy_report=taxonomy_report, repo_root=repo_root)
    revision = _git(repo_root, "rev-parse", "HEAD")
    tree = _git(repo_root, "rev-parse", "HEAD^{tree}")
    if revision != inventory.revision or tree != inventory.tree_digest:
        raise MoonSecurityBoundaryEvidenceError("security evidence revision/tree mismatch")
    provider_blob = _git(repo_root, "hash-object", PROVIDER_PATH)
    mediation_blob = _git(repo_root, "hash-object", MEDIATION_PATH)
    by_req = {x.attack_id: x for x in policy.security_requirements}
    if set(by_req) != {"UNTRUSTED_PERMISSION", "STALE_AUTHORITY_SOURCE"}:
        raise MoonSecurityBoundaryEvidenceError("security requirement set drift")
    verifier = _verifier_digest()

    untrusted = by_req["UNTRUSTED_PERMISSION"]
    denials, types = _capture_untrusted_permission()
    untrusted_record = SecurityBoundaryNegativeEvidenceRecord(
        attack_id=untrusted.attack_id,
        classification=untrusted.classification,
        target_surface_digest=untrusted.target_surface_digest,
        required_evidence_class=untrusted.required_evidence_class,
        requirement_digest=untrusted.digest(),
        policy_pep_name=untrusted.pep_name,
        evidence_boundary_pep_name="_require_trusted_permission",
        pep_digest=_pep_digest(_require_trusted_permission),
        source_path=PROVIDER_PATH,
        source_blob_sha=provider_blob,
        revision=revision,
        tree=tree,
        verifier_identity_digest=verifier,
        input_cases=UNTRUSTED_VALUES,
        expected_denial="actor permission is not trusted",
        observed_denials=denials,
        observed_exception_types=types,
        execution_mode="PURE_BOUNDARY_DIRECT",
        network_effect=False,
        filesystem_effect=False,
        database_effect=False,
        authority_mutation=False,
        repository_mutation=False,
        target_mutation=False,
        evidence_refs=(f"policy-v2:{policy.digest()}", f"requirement:{untrusted.digest()}", f"source:{PROVIDER_PATH}@{provider_blob}", "fixed-untrusted-values:read,triage,none"),
    ).sealed()

    stale = by_req["STALE_AUTHORITY_SOURCE"]
    first, current, stale_denials, stale_types = _capture_stale_authority()
    stale_record = SecurityBoundaryNegativeEvidenceRecord(
        attack_id=stale.attack_id,
        classification=stale.classification,
        target_surface_digest=stale.target_surface_digest,
        required_evidence_class=stale.required_evidence_class,
        requirement_digest=stale.digest(),
        policy_pep_name=stale.pep_name,
        evidence_boundary_pep_name="_require_current_admission",
        pep_digest=_pep_digest(_require_current_admission),
        source_path=MEDIATION_PATH,
        source_blob_sha=mediation_blob,
        revision=revision,
        tree=tree,
        verifier_identity_digest=verifier,
        input_cases=(f"baseline={first};current={current}",),
        expected_denial="authority drift",
        observed_denials=stale_denials,
        observed_exception_types=stale_types,
        execution_mode="PURE_BOUNDARY_DIRECT",
        network_effect=False,
        filesystem_effect=False,
        database_effect=False,
        authority_mutation=False,
        repository_mutation=False,
        target_mutation=False,
        evidence_refs=(f"policy-v2:{policy.digest()}", f"requirement:{stale.digest()}", f"source:{MEDIATION_PATH}@{mediation_blob}", "fixed-in-memory-admission-sequence:A-not-equal-B", "pre-fence-boundary:no-fence-call"),
    ).sealed()

    records = tuple(sorted((untrusted_record, stale_record), key=lambda x: x.attack_id))
    satisfactions = tuple(
        SecurityRequirementEvidenceSatisfaction(
            attack_id=record.attack_id,
            classification=record.classification,
            required_evidence_class=record.required_evidence_class,
            requirement_digest=record.requirement_digest,
            evidence_record_digest=record.digest(),
            status="CANONICAL_NEGATIVE_EVIDENCE_PRESENT",
            evidence_refs=(f"record:{record.digest()}", f"policy-v2:{policy.digest()}", "non-bypass-security-evidence"),
        ).validate()
        for record in records
    )
    report = SecurityBoundaryEvidenceReport(
        inventory_digest=inventory.digest(),
        taxonomy_digest=taxonomy_report.digest(),
        policy_v2_digest=policy.digest(),
        policy_v2_topology_report_digest=topology_report.digest(),
        negative_evidence_record_digests=tuple(record.digest() for record in records),
        satisfaction_digests=tuple(item.digest() for item in satisfactions),
        closure_record_digests=tuple(sorted(mediation_closure_record_digest(item) for item in closure)),
        global_carrier_digest=carrier.digest(),
        remaining_security_requirement_keys=(),
        global_status=carrier.global_status,
        next_evidence_plan=("NO_ADDITIONAL_NEGATIVE_EVIDENCE_FOR_REHOMED_MOON_SECURITY_REQUIREMENTS",),
        evidence_refs=(f"policy-v2:{policy.digest()}", f"topology-report:{topology_report.digest()}", "effect-free-boundary-evidence-only", "no-live-execution"),
    ).validate()
    return records, satisfactions, report, policy, closure, carrier, topology_report
