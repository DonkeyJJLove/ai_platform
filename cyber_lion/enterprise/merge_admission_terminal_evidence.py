"""R6 terminal evidence derived from an actual non-consuming merge-admission result.

This module is candidate-only evidence machinery. It never calls GitHub, never consumes
a merge grant, and never creates merge authorization. The required terminal literals are
rendered only from a validated NonConsumingMergeAdmissionResult.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .authority_grant import AuthorityGrant
from .authority_revocation import (
    AuthorityEpochState,
    AuthorityLineageRootAnchor,
    register_canonical_authority_epoch_state,
    register_canonical_authority_lineage_root_anchor,
)
from .authority_source import (
    AuthorityLineageRecord,
    AuthorityLookupKey,
    AuthoritySource,
    canonical_source_lineage_digest,
)
from .authority_verification import AuthorityVerificationContext, IssuerKeyBinding, Verifier
from .merge_admission import (
    MergeIntent,
    NonConsumingMergeAdmissionResult,
    TrustedPullRequestState,
    admit_merge_non_consuming,
    canonical_merge_method_constraint,
    canonical_merge_resource,
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPO = "DonkeyJJLove/ai_platform"
_POLICY = "sha256:" + "1" * 64
_OBS = "sha256:" + "2" * 64


class R6TerminalEvidenceError(ValueError):
    pass


class _StaticAuthoritySource(AuthoritySource):
    def __init__(self, records: tuple[AuthorityLineageRecord, ...]):
        self.records = records

    def _lookup_exact(self, key: AuthorityLookupKey):
        return self.records


def _sha(value: str, name: str) -> str:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value):
        raise R6TerminalEvidenceError(f"{name} must be a full lowercase SHA")
    return value


def validate_exact_identity(*, expected_head: str, expected_tree: str, expected_parent: str,
                            actual_head: str, actual_tree: str, actual_parent: str) -> None:
    expected = tuple(_sha(v, n) for v, n in (
        (expected_head, "expected_head"), (expected_tree, "expected_tree"),
        (expected_parent, "expected_parent")))
    actual = tuple(_sha(v, n) for v, n in (
        (actual_head, "actual_head"), (actual_tree, "actual_tree"),
        (actual_parent, "actual_parent")))
    if actual != expected:
        raise R6TerminalEvidenceError("candidate HEAD/TREE/PARENT mismatch")


def _accepting_verifier(payload: bytes, signature: str, key_id: str, algorithm: str) -> bool:
    del payload
    return signature == "sig" and key_id == "key-r6" and algorithm == "test"


def _rejecting_verifier(payload: bytes, signature: str, key_id: str, algorithm: str) -> bool:
    del payload, signature, key_id, algorithm
    return False


def run_non_consuming_admission(*, head_sha: str, parent_sha: str, suffix: str,
                                verifier: Verifier = _accepting_verifier) -> NonConsumingMergeAdmissionResult:
    head_sha = _sha(head_sha, "head_sha")
    parent_sha = _sha(parent_sha, "parent_sha")
    context = AuthorityVerificationContext(
        trust_domain="github.r6.test", tenant_id="tenant-r6", organization_id="org-r6",
        mission_id=f"mission-r6-{suffix}",
    )
    intent = MergeIntent(
        repository=_REPO, pr_number=248, base_sha=parent_sha, head_sha=head_sha,
        merge_method="merge",
    ).validate()
    grant = AuthorityGrant(
        schema_version="1.1.0", grant_id=f"grant-r6-{suffix}", issuer_subject_id="issuer-r6",
        subject_id="executor-r6", tenant_id=context.tenant_id,
        organization_id=context.organization_id, mission_id=context.mission_id,
        capability_id="github.merge", capability_version="1",
        actions=("merge_pull_request",), resource_scope=(canonical_merge_resource(intent),),
        authority_ceiling="external_write",
        constraints=(canonical_merge_method_constraint(intent),), parent_grant_id=None,
        issued_at="2026-08-20T00:00:00+02:00", expires_at="2026-08-21T00:00:00+02:00",
        epoch=1, policy_digest=_POLICY, observability_contract_digest=_OBS,
        signature="sig", delegation_allowed=False, delegation_depth_budget=0,
    ).validate()
    register_canonical_authority_epoch_state(AuthorityEpochState(
        trust_domain=context.trust_domain, tenant_id=context.tenant_id,
        organization_id=context.organization_id, mission_id=context.mission_id, epoch=1,
    ))
    register_canonical_authority_lineage_root_anchor(
        context, 1, AuthorityLineageRootAnchor(
            root_grant_id=grant.grant_id, root_grant_digest=grant.digest(),
        ),
    )
    keys = (IssuerKeyBinding(
        issuer_subject_id="issuer-r6", trust_domain=context.trust_domain,
        key_id="key-r6", algorithm="test",
    ),)
    trusted = TrustedPullRequestState(
        repository=_REPO, pr_number=248, base_sha=parent_sha, head_sha=head_sha,
        merge_method="merge",
    ).validate()
    key = AuthorityLookupKey(
        repository=_REPO, pr_number=248, base_sha=parent_sha, head_sha=head_sha,
        mission_id=context.mission_id, grant_id=grant.grant_id,
    ).validate()
    lineage = (grant,)
    record = AuthorityLineageRecord(
        lookup_key=key, lineage=lineage,
        lineage_digest=canonical_source_lineage_digest(lineage),
        provenance_id=f"r6:evidence:{suffix}", source_kind="trusted-control-plane",
    ).validate()
    return admit_merge_non_consuming(
        intent=intent, trusted_state=trusted, authority_source=_StaticAuthoritySource((record,)),
        lookup_key=key, issuer_keys=keys, verifier=verifier, context=context,
        admission_id=f"r6-admission-{suffix}",
    )


def render_terminal_evidence(result: NonConsumingMergeAdmissionResult) -> tuple[str, str, str]:
    if type(result) is not NonConsumingMergeAdmissionResult:
        raise R6TerminalEvidenceError("terminal evidence requires exact non-consuming admission result")
    result.validate()
    terminal = "OK" if result.decision == "ALLOW" and result.evidence is not None else "DENY"
    return (
        f"MERGE_ADMISSION_DECISION={result.decision}",
        f"MERGE_ADMISSION_TERMINAL={terminal}",
        "NO_MERGE_AUTHORIZATION_INFERRED=YES",
    )


def validate_terminal_literals(lines: Iterable[str]) -> None:
    values = tuple(lines)
    terminal = [x for x in values if x.startswith("MERGE_ADMISSION_TERMINAL=")]
    no_auth = [x for x in values if x.startswith("NO_MERGE_AUTHORIZATION_INFERRED=")]
    if len(terminal) != 1 or len(no_auth) != 1:
        raise R6TerminalEvidenceError("terminal literal cardinality invalid")
    if terminal[0] not in {"MERGE_ADMISSION_TERMINAL=OK", "MERGE_ADMISSION_TERMINAL=DENY", "MERGE_ADMISSION_TERMINAL=ERROR"}:
        raise R6TerminalEvidenceError("terminal literal value invalid")
    if no_auth[0] != "NO_MERGE_AUTHORIZATION_INFERRED=YES":
        raise R6TerminalEvidenceError("merge-authorization inference literal invalid")


def main() -> int:
    import os
    actual_head = _sha(os.environ["R6_ACTUAL_HEAD"], "R6_ACTUAL_HEAD")
    actual_tree = _sha(os.environ["R6_ACTUAL_TREE"], "R6_ACTUAL_TREE")
    actual_parent = _sha(os.environ["R6_ACTUAL_PARENT"], "R6_ACTUAL_PARENT")
    validate_exact_identity(
        expected_head=os.environ["GITHUB_SHA"], expected_tree=os.environ["R6_EXPECTED_TREE"],
        expected_parent=os.environ["R6_EXPECTED_PARENT"], actual_head=actual_head,
        actual_tree=actual_tree, actual_parent=actual_parent,
    )
    result = run_non_consuming_admission(
        head_sha=actual_head, parent_sha=actual_parent, suffix=actual_head[:12],
    )
    lines = render_terminal_evidence(result)
    validate_terminal_literals(lines)
    print(f"R6_CANDIDATE_HEAD={actual_head}")
    print(f"R6_CANDIDATE_TREE={actual_tree}")
    print(f"R6_CANDIDATE_PARENT={actual_parent}")
    for line in lines:
        print(line)
    return 0 if "MERGE_ADMISSION_TERMINAL=OK" in lines else 2


if __name__ == "__main__":
    raise SystemExit(main())
