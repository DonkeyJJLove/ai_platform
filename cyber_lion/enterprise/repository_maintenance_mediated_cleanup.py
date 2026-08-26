"""Canonical production entrypoint for one exact repository branch-ref delete.

An issue comment is request evidence only. Effect authority is admitted only through the
trusted MaintenanceBundle, RepositoryMaintenancePDPContext, LiveAuthorityAdmission,
CanonicalPolicyDecisionPoint and a durable RepositoryDeleteFence. No live effect is
performed merely because this module exists or is imported.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from types import ModuleType
from typing import Mapping

from cyber_lion.contracts.repository_maintenance_sandbox import (
    REPOSITORY,
    RepositoryMaintenanceOperation,
    RepositoryMaintenancePolicy,
    canonical_json,
    validate_branch_name,
)
from cyber_lion.enterprise.authority_source import AuthorityLookupKey
from cyber_lion.enterprise.control_plane import ActionProposal
from cyber_lion.enterprise.live_authority_admission import LiveAuthorityAdmission
from cyber_lion.enterprise.maintenance_bundle import (
    CAPABILITY_REPOSITORY_REF_DELETE,
    HttpMaintenanceBundleSource,
    MaintenanceBundle,
    MaintenanceBundleError,
)
from cyber_lion.enterprise.models import authority_rank
from cyber_lion.enterprise.policy_gate import CanonicalPolicyDecisionPoint
from cyber_lion.enterprise.repository_delete_fence import (
    RepositoryDeleteFence,
    RepositoryDeleteFenceRecord,
)
from cyber_lion.enterprise.repository_maintenance_cleanup import (
    SlashSafeGitHubRepositoryMaintenanceBackend,
)
from cyber_lion.enterprise.repository_maintenance_pdp_context import (
    RepositoryMaintenancePDPContextResolver,
    ResolvedRepositoryMaintenancePDPContext,
)
from cyber_lion.enterprise.repository_maintenance_sandbox import (
    RepositoryMaintenanceError,
    RepositoryMaintenanceSandbox,
    _build_operation,
)

_CONTROL_ISSUE = 144
_COMMAND = "LION-REPOSITORY-REF-DELETE v2"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_RUNTIME_FACTORY = "build_repository_maintenance_dependencies"
_ADMISSION_DOMAIN = b"LION/E006-R9D8U-CANONICAL-REPOSITORY-DELETE-ADMISSION/1\0"
_EFFECT_DOMAIN = b"LION/E006-R9D8U-CANONICAL-REPOSITORY-DELETE-EFFECT/1\0"
_OBSERVATION_DOMAIN = b"LION/E006-R9D8U-CANONICAL-REPOSITORY-DELETE-OBSERVATION/1\0"
_RECONCILIATION_DOMAIN = b"LION/E006-R9D8U-CANONICAL-REPOSITORY-DELETE-RECONCILIATION/1\0"


class MediatedRepositoryMaintenanceError(RuntimeError):
    pass


def _text(value: object, name: str, *, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise MediatedRepositoryMaintenanceError(f"{name} is invalid")
    return value


def _sha40(value: object, name: str) -> str:
    value = _text(value, name, limit=40)
    if _SHA40.fullmatch(value) is None:
        raise MediatedRepositoryMaintenanceError(f"{name} must be exact lowercase sha40")
    return value


def _hex64(value: object, name: str) -> str:
    value = _text(value, name, limit=64)
    if _HEX64.fullmatch(value) is None:
        raise MediatedRepositoryMaintenanceError(f"{name} must be sha256 hex")
    return value


def _hash(domain: bytes, value: object) -> str:
    return sha256(domain + canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class RepositoryMaintenanceRequestEvidence:
    repository: str
    control_comment_id: int
    actor_login: str
    owner_login: str
    branch: str
    expected_branch_head: str
    event_digest: str

    def validate(self) -> "RepositoryMaintenanceRequestEvidence":
        if self.repository != REPOSITORY:
            raise MediatedRepositoryMaintenanceError("request repository substitution denied")
        if not isinstance(self.control_comment_id, int) or isinstance(self.control_comment_id, bool) or self.control_comment_id <= 0:
            raise MediatedRepositoryMaintenanceError("request comment id invalid")
        if not self.actor_login or self.actor_login != self.owner_login:
            raise MediatedRepositoryMaintenanceError("repository owner request actor required")
        validate_branch_name(self.branch)
        _sha40(self.expected_branch_head, "expected_branch_head")
        _hex64(self.event_digest, "event_digest")
        return self

    def digest(self) -> str:
        self.validate()
        return sha256(b"LION/E006-R9D8U-MAINTENANCE-REQUEST/1\0" + canonical_json(asdict(self))).hexdigest()


def load_request_evidence(*, event_path: Path, repository: str) -> RepositoryMaintenanceRequestEvidence:
    try:
        raw = event_path.read_bytes()
        event = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise MediatedRepositoryMaintenanceError("maintenance request event unavailable") from exc
    if not isinstance(event, dict) or event.get("action") != "created":
        raise MediatedRepositoryMaintenanceError("only created issue_comment request is accepted")
    issue = event.get("issue")
    comment = event.get("comment")
    repo = event.get("repository")
    if not isinstance(issue, dict) or not isinstance(comment, dict) or not isinstance(repo, dict):
        raise MediatedRepositoryMaintenanceError("maintenance request event malformed")
    if issue.get("number") != _CONTROL_ISSUE or repo.get("full_name") != repository or repository != REPOSITORY:
        raise MediatedRepositoryMaintenanceError("maintenance request issue/repository mismatch")
    body = comment.get("body")
    if not isinstance(body, str):
        raise MediatedRepositoryMaintenanceError("maintenance request body invalid")
    lines = body.splitlines()
    if len(lines) != 3 or lines[0] != _COMMAND:
        raise MediatedRepositoryMaintenanceError("maintenance request command shape invalid")
    if not lines[1].startswith("branch=") or not lines[2].startswith("expected_head="):
        raise MediatedRepositoryMaintenanceError("maintenance request fields invalid")
    branch = lines[1].split("=", 1)[1]
    expected_head = lines[2].split("=", 1)[1]
    owner = repo.get("owner") or {}
    actor = comment.get("user") or {}
    comment_id = comment.get("id")
    return RepositoryMaintenanceRequestEvidence(
        repository=repository,
        control_comment_id=comment_id,
        actor_login=str(actor.get("login") or ""),
        owner_login=str(owner.get("login") or ""),
        branch=branch,
        expected_branch_head=expected_head,
        event_digest=sha256(raw).hexdigest(),
    ).validate()


@dataclass(frozen=True)
class RepositoryMaintenanceTrustedDependencies:
    context_resolver: object
    authority_admission: LiveAuthorityAdmission
    authority_key: AuthorityLookupKey
    provider_id: str

    def validate(self, *, bundle: MaintenanceBundle, require_canonical_resolver: bool = False) -> "RepositoryMaintenanceTrustedDependencies":
        bundle.validate()
        if require_canonical_resolver and type(self.context_resolver) is not RepositoryMaintenancePDPContextResolver:
            raise MediatedRepositoryMaintenanceError("external dependency provider must supply canonical context resolver")
        if not callable(getattr(self.context_resolver, "resolve", None)):
            raise MediatedRepositoryMaintenanceError("maintenance context resolver unavailable")
        if type(self.authority_admission) is not LiveAuthorityAdmission:
            raise MediatedRepositoryMaintenanceError("exact LiveAuthorityAdmission required")
        if type(self.authority_key) is not AuthorityLookupKey:
            raise MediatedRepositoryMaintenanceError("exact AuthorityLookupKey required")
        self.authority_key.validate()
        _hex64(self.provider_id, "provider_id")
        if self.authority_key.repository != bundle.binding.repository or self.authority_key.mission_id != bundle.binding.mission_id:
            raise MediatedRepositoryMaintenanceError("external authority key does not bind maintenance bundle")
        if self.authority_admission.context.mission_id != bundle.binding.mission_id:
            raise MediatedRepositoryMaintenanceError("LiveAuthorityAdmission context does not bind maintenance bundle")
        return self


@dataclass(frozen=True)
class CanonicalRepositoryDeleteAdmission:
    repository: str
    mission_id: str
    branch: str
    expected_branch_head: str
    expected_master: str
    expected_master_tree: str
    operation_digest: str
    repository_policy_digest: str
    canonical_policy_content_digest: str
    bundle_digest: str
    request_evidence_digest: str
    context_digest: str
    authority_lineage_digest: str
    authority_epoch: int
    authority_state_version: int
    pdp_request_digest: str
    pdp_decision_digest: str
    pdp_replay_key: str
    provider_id: str
    execution_id: str
    admission_digest: str = ""

    def canonical_payload(self) -> dict[str, object]:
        value = asdict(self)
        value.pop("admission_digest")
        return value

    def compute_digest(self) -> str:
        return _hash(_ADMISSION_DOMAIN, self.canonical_payload())

    def validate(self) -> "CanonicalRepositoryDeleteAdmission":
        if self.repository != REPOSITORY:
            raise MediatedRepositoryMaintenanceError("canonical delete admission repository mismatch")
        for name in ("mission_id", "branch", "canonical_policy_content_digest", "provider_id", "execution_id"):
            _text(getattr(self, name), name)
        validate_branch_name(self.branch)
        for name in ("expected_branch_head", "expected_master", "expected_master_tree"):
            _sha40(getattr(self, name), name)
        for name in (
            "operation_digest",
            "repository_policy_digest",
            "bundle_digest",
            "request_evidence_digest",
            "context_digest",
            "authority_lineage_digest",
            "pdp_request_digest",
            "pdp_decision_digest",
            "pdp_replay_key",
        ):
            _hex64(getattr(self, name), name)
        if not self.canonical_policy_content_digest.startswith("sha256:") or len(self.canonical_policy_content_digest) != 71:
            raise MediatedRepositoryMaintenanceError("canonical policy content digest invalid")
        _hex64(self.canonical_policy_content_digest[7:], "canonical_policy_content_digest")
        if not isinstance(self.authority_epoch, int) or isinstance(self.authority_epoch, bool) or self.authority_epoch < 0:
            raise MediatedRepositoryMaintenanceError("authority epoch invalid")
        if not isinstance(self.authority_state_version, int) or isinstance(self.authority_state_version, bool) or self.authority_state_version < 1:
            raise MediatedRepositoryMaintenanceError("authority state version invalid")
        if self.admission_digest:
            _hex64(self.admission_digest, "admission_digest")
            if self.admission_digest != self.compute_digest():
                raise MediatedRepositoryMaintenanceError("canonical delete admission digest mismatch")
        return self

    def sealed(self) -> "CanonicalRepositoryDeleteAdmission":
        self.validate()
        return CanonicalRepositoryDeleteAdmission(
            **{**asdict(self), "admission_digest": self.compute_digest()}
        ).validate()


class CanonicalSlashSafeGitHubRepositoryMaintenanceBackend(SlashSafeGitHubRepositoryMaintenanceBackend):
    """Effect boundary that accepts only a canonical PDP+fence admission."""

    _GET_PREFIXES = SlashSafeGitHubRepositoryMaintenanceBackend._GET_PREFIXES + (
        f"/repos/{REPOSITORY}/git/commits/",
    )

    def authorize_delete(self, *args, **kwargs):
        del args, kwargs
        raise MediatedRepositoryMaintenanceError(
            "legacy caller-constructible repository delete authority is disabled"
        )

    def master_tree(self, master_sha: str) -> str:
        _sha40(master_sha, "master_sha")
        status, value = self._request("GET", f"/repos/{self.repository}/git/commits/{master_sha}")
        try:
            tree = value["tree"]["sha"]
        except Exception as exc:
            raise MediatedRepositoryMaintenanceError("master tree observation unavailable") from exc
        if status != 200:
            raise MediatedRepositoryMaintenanceError("master tree observation rejected")
        return _sha40(tree, "master_tree")

    def authorize_canonical_delete(
        self,
        *,
        operation: RepositoryMaintenanceOperation,
        policy: RepositoryMaintenancePolicy,
        admission: CanonicalRepositoryDeleteAdmission,
        effect_key: str,
        fence: RepositoryDeleteFence,
    ) -> str:
        operation.validate()
        policy.validate()
        admission.validate()
        _hex64(effect_key, "effect_key")
        if operation.repository != self.repository or policy.repository != self.repository:
            raise MediatedRepositoryMaintenanceError("canonical delete repository mismatch")
        if operation.policy_digest != policy.digest() or admission.repository_policy_digest != policy.digest():
            raise MediatedRepositoryMaintenanceError("repository maintenance policy binding mismatch")
        if (
            admission.repository != operation.repository
            or admission.mission_id != operation.mission_id
            or admission.branch != operation.branch_name
            or admission.expected_branch_head != operation.expected_branch_head
            or admission.expected_master != operation.protected_master_sha
            or admission.operation_digest != operation.operation_digest()
        ):
            raise MediatedRepositoryMaintenanceError("canonical delete operation substitution denied")
        record = fence.get(effect_key)
        if (
            record.state != "PREPARED"
            or record.admission_digest != admission.admission_digest
            or record.repository != admission.repository
            or record.mission_id != admission.mission_id
            or record.authority_lineage_digest != admission.authority_lineage_digest
            or record.branch != admission.branch
            or record.expected_branch_head != admission.expected_branch_head
            or record.expected_master != admission.expected_master
            or record.expected_master_tree != admission.expected_master_tree
            or record.provider_id != admission.provider_id
            or record.execution_id != admission.execution_id
            or record.authority_epoch != admission.authority_epoch
        ):
            raise MediatedRepositoryMaintenanceError("canonical delete durable fence binding mismatch")
        master = self.master_sha()
        head = self.branch_sha(operation.branch_name)
        tree = self.master_tree(master)
        if master != admission.expected_master or head != admission.expected_branch_head or tree != admission.expected_master_tree:
            raise MediatedRepositoryMaintenanceError("canonical delete currentness failed")
        compare = self.compare_branch_to_master(operation.branch_name)
        prs = self.open_prs_for_branch(operation.branch_name)
        ownership = self.ownership_observation(operation.branch_name, master)
        if not (
            operation.classification == "A"
            and compare["status"] in {"ahead", "identical"}
            and int(compare["behind_by"]) == 0
            and not prs
            and ownership.ownership_state == "UNOWNED"
        ):
            raise MediatedRepositoryMaintenanceError("canonical delete eligibility failed")
        if admission.admission_digest in self._consumed_delete_admissions:
            raise MediatedRepositoryMaintenanceError("canonical delete admission replay denied")
        self._pending_delete = (
            operation.branch_name,
            operation.expected_branch_head,
            operation.protected_master_sha,
            admission.admission_digest,
            admission.authority_lineage_digest,
        )
        return admission.admission_digest


class RepositoryMaintenanceAdmissionRuntime:
    def __init__(
        self,
        *,
        bundle_source: object,
        dependencies: RepositoryMaintenanceTrustedDependencies,
        fence: RepositoryDeleteFence,
    ) -> None:
        if not callable(getattr(bundle_source, "resolve_exact", None)):
            raise MediatedRepositoryMaintenanceError("maintenance bundle source unavailable")
        if type(dependencies) is not RepositoryMaintenanceTrustedDependencies:
            raise MediatedRepositoryMaintenanceError("trusted maintenance dependencies invalid")
        if type(fence) is not RepositoryDeleteFence:
            raise MediatedRepositoryMaintenanceError("exact RepositoryDeleteFence required")
        self.bundle_source = bundle_source
        self.dependencies = dependencies
        self.fence = fence

    @staticmethod
    def _select_agents(resolved: ResolvedRepositoryMaintenancePDPContext, capability: str):
        members = resolved.swarm.member_agent_ids
        proposer_id = None
        for agent_id in members:
            agent = resolved.agents.get(agent_id)
            if agent is None or agent.is_verifier:
                continue
            if capability in agent.capabilities and authority_rank(agent.authority_ceiling) >= authority_rank("external_write"):
                proposer_id = agent_id
                break
        verifier_id = None
        for agent_id in resolved.swarm.verifier_agent_ids:
            agent = resolved.agents.get(agent_id)
            if agent is not None and agent.is_verifier and agent_id != proposer_id:
                verifier_id = agent_id
                break
        if proposer_id is None or verifier_id is None:
            raise MediatedRepositoryMaintenanceError("canonical proposer/independent verifier unavailable")
        observed = tuple(sorted({event for agent in resolved.agents.values() for event in agent.observability_events}))
        if not observed:
            raise MediatedRepositoryMaintenanceError("canonical maintenance observability unavailable")
        required = tuple(resolved.agents[proposer_id].observability_events)
        if not required:
            raise MediatedRepositoryMaintenanceError("canonical proposer observability unavailable")
        return proposer_id, verifier_id, observed, required

    @staticmethod
    def _authority_snapshot(admission: LiveAuthorityAdmission, key: AuthorityLookupKey, now: datetime):
        try:
            record, state, root = admission._snapshot(key)
            admission._authenticate_record(record, state, root, now=now)
        except Exception as exc:
            raise MediatedRepositoryMaintenanceError("live authority final currentness unavailable") from exc
        return record, state, root

    def execute_one(
        self,
        *,
        request: RepositoryMaintenanceRequestEvidence,
        bundle: MaintenanceBundle,
        operation: RepositoryMaintenanceOperation,
        policy: RepositoryMaintenancePolicy,
        sandbox: RepositoryMaintenanceSandbox,
        backend: CanonicalSlashSafeGitHubRepositoryMaintenanceBackend,
        expected_master_tree: str,
        execution_id: str,
    ) -> dict[str, object]:
        request.validate()
        bundle.validate()
        operation.validate()
        policy.validate()
        _sha40(expected_master_tree, "expected_master_tree")
        _text(execution_id, "execution_id")
        deps = self.dependencies.validate(bundle=bundle)
        if operation.branch_name != request.branch or operation.expected_branch_head != request.expected_branch_head:
            raise MediatedRepositoryMaintenanceError("request/operation branch binding mismatch")
        if operation.mission_id != bundle.binding.mission_id:
            raise MediatedRepositoryMaintenanceError("operation mission does not bind trusted bundle")
        current_bundle = self.bundle_source.resolve_exact(
            repository=bundle.binding.repository, capability=bundle.binding.capability
        )
        if type(current_bundle) is not MaintenanceBundle or current_bundle.validate().bundle_digest != bundle.bundle_digest:
            raise MediatedRepositoryMaintenanceError("maintenance bundle changed before canonical admission")
        resolved = deps.context_resolver.resolve(
            observed_master=operation.protected_master_sha,
            observed_tree=expected_master_tree,
            exact_master_relation_proven=True,
        )
        if type(resolved) is not ResolvedRepositoryMaintenancePDPContext:
            raise MediatedRepositoryMaintenanceError("canonical maintenance context resolver returned invalid type")
        resolved.context.validate()
        trusted_policy = bundle.policy()
        trusted_mission = bundle.mission()
        if resolved.policy != trusted_policy or resolved.mission != trusted_mission:
            raise MediatedRepositoryMaintenanceError("canonical state does not equal trusted maintenance bundle")
        if resolved.context.observability_state != "HEALTHY" or resolved.lion_status.get("epistemic_state") != "CURRENT":
            raise MediatedRepositoryMaintenanceError("maintenance context is not CURRENT/HEALTHY")
        if resolved.context.master != operation.protected_master_sha or resolved.context.tree != expected_master_tree:
            raise MediatedRepositoryMaintenanceError("maintenance context master/tree mismatch")
        proposer, verifier, observed_events, required_observability = self._select_agents(
            resolved, bundle.binding.capability
        )
        if deps.authority_key.mission_id != trusted_mission.mission_id:
            raise MediatedRepositoryMaintenanceError("authority mission mismatch")
        proposal = ActionProposal(
            proposal_id=f"repo-delete:{operation.operation_id}",
            mission_id=trusted_mission.mission_id,
            swarm_id=resolved.swarm.swarm_id,
            proposer_agent_id=proposer,
            capability=bundle.binding.capability,
            requested_authority="external_write",
            action_class="repository_ref.delete",
            target=f"github:repo:{REPOSITORY}:ref:heads/{operation.branch_name}",
            consequential=True,
            evidence_refs=(
                f"maintenance-bundle:{bundle.bundle_digest}",
                f"maintenance-request:{request.digest()}",
                f"maintenance-context:{resolved.context.context_digest}",
            ),
            required_observability=required_observability,
            verifier_agent_id=verifier,
            payload_digest=operation.operation_digest(),
        ).validate()
        pdp = CanonicalPolicyDecisionPoint(authority_admission=deps.authority_admission)
        now = datetime.now(timezone.utc)
        pdp_result = pdp.evaluate(
            request_id=f"r9d8u:{execution_id}:{operation.operation_id}",
            gate_event_id=f"r9d8u-gate:{execution_id}:{operation.operation_id}",
            proposal=proposal,
            mission=trusted_mission,
            swarm=resolved.swarm,
            agents=resolved.agents,
            policy=trusted_policy,
            authority_key=deps.authority_key,
            graph_projection=resolved.graph_projection,
            status=resolved.lion_status,
            observability_state=resolved.context.observability_state,
            observed_event_types=observed_events,
            evidence_refs=proposal.evidence_refs,
            trusted_now=now,
        )
        if pdp_result.applied.decision != "ALLOW" or pdp_result.applied.effective_authority != "external_write":
            raise MediatedRepositoryMaintenanceError("canonical PDP denied repository_ref.delete")
        record, state, _ = self._authority_snapshot(deps.authority_admission, deps.authority_key, now)
        if record.lineage_digest != pdp_result.applied.authority_lineage_digest:
            raise MediatedRepositoryMaintenanceError("PDP/live authority lineage mismatch")
        leaf = record.lineage[-1]
        if leaf.capability_id != bundle.binding.capability or leaf.policy_digest != trusted_policy.content_digest:
            raise MediatedRepositoryMaintenanceError("live authority leaf does not bind capability/policy")
        policy_fence_digest = sha256(trusted_policy.binding.encode("utf-8")).hexdigest()
        admission = CanonicalRepositoryDeleteAdmission(
            repository=REPOSITORY,
            mission_id=trusted_mission.mission_id,
            branch=operation.branch_name,
            expected_branch_head=operation.expected_branch_head,
            expected_master=operation.protected_master_sha,
            expected_master_tree=expected_master_tree,
            operation_digest=operation.operation_digest(),
            repository_policy_digest=policy.digest(),
            canonical_policy_content_digest=trusted_policy.content_digest,
            bundle_digest=bundle.bundle_digest,
            request_evidence_digest=request.digest(),
            context_digest=resolved.context.context_digest,
            authority_lineage_digest=record.lineage_digest,
            authority_epoch=state.epoch,
            authority_state_version=state.version,
            pdp_request_digest=pdp_result.requested.request_digest,
            pdp_decision_digest=pdp_result.applied.decision_digest,
            pdp_replay_key=pdp_result.receipt.replay_key,
            provider_id=deps.provider_id,
            execution_id=execution_id,
        ).sealed()
        effect_key = sha256(
            _EFFECT_DOMAIN
            + admission.admission_digest.encode("ascii")
            + operation.operation_digest().encode("ascii")
        ).hexdigest()
        prepared_at = datetime.now(timezone.utc).isoformat()
        self.fence.prepare(
            RepositoryDeleteFenceRecord(
                effect_key=effect_key,
                admission_digest=admission.admission_digest,
                repository=REPOSITORY,
                mission_id=trusted_mission.mission_id,
                authority_lineage_digest=record.lineage_digest,
                policy_digest=policy_fence_digest,
                control_comment_id=request.control_comment_id,
                branch=operation.branch_name,
                expected_branch_head=operation.expected_branch_head,
                expected_master=operation.protected_master_sha,
                expected_master_tree=expected_master_tree,
                provider_id=deps.provider_id,
                execution_id=execution_id,
                authority_epoch=state.epoch,
                state="PREPARED",
                prepared_at=prepared_at,
            ).validate()
        )
        try:
            current_bundle = self.bundle_source.resolve_exact(
                repository=bundle.binding.repository, capability=bundle.binding.capability
            )
            if current_bundle.bundle_digest != bundle.bundle_digest:
                raise MediatedRepositoryMaintenanceError("maintenance bundle drift after PREPARED")
            current_context = deps.context_resolver.resolve(
                observed_master=operation.protected_master_sha,
                observed_tree=expected_master_tree,
                exact_master_relation_proven=True,
            )
            if type(current_context) is not ResolvedRepositoryMaintenancePDPContext or current_context.context.context_digest != resolved.context.context_digest:
                raise MediatedRepositoryMaintenanceError("canonical maintenance context drift after PREPARED")
            current_record, current_state, _ = self._authority_snapshot(
                deps.authority_admission, deps.authority_key, datetime.now(timezone.utc)
            )
            if (
                current_record.lineage_digest != admission.authority_lineage_digest
                or current_state.epoch != admission.authority_epoch
                or current_state.version != admission.authority_state_version
            ):
                raise MediatedRepositoryMaintenanceError("live authority drift after PREPARED")
            master = backend.master_sha()
            tree = backend.master_tree(master)
            head = backend.branch_sha(operation.branch_name)
            if master != admission.expected_master or tree != admission.expected_master_tree or head != admission.expected_branch_head:
                raise MediatedRepositoryMaintenanceError("repository currentness drift after PREPARED")
            backend.authorize_canonical_delete(
                operation=operation,
                policy=policy,
                admission=admission,
                effect_key=effect_key,
                fence=self.fence,
            )
            self.fence.mark_attempted(effect_key, attempted_at=datetime.now(timezone.utc).isoformat())
            receipt = sandbox.execute_delete(operation)
            final_master = backend.master_sha()
            final_tree = backend.master_tree(final_master)
            final_head = backend.branch_sha(operation.branch_name)
            if final_master != admission.expected_master or final_tree != admission.expected_master_tree or final_head is not None:
                raise MediatedRepositoryMaintenanceError("independent repository effect observation failed")
            observation_payload = {
                "effect_key": effect_key,
                "admission_digest": admission.admission_digest,
                "receipt_digest": receipt.receipt_digest,
                "branch_absent": True,
                "master": final_master,
                "tree": final_tree,
            }
            observation_digest = _hash(_OBSERVATION_DOMAIN, observation_payload)
            self.fence.mark_observed(
                effect_key,
                observation_digest=observation_digest,
                observed_at=datetime.now(timezone.utc).isoformat(),
            )
            reconciliation_payload = {
                **observation_payload,
                "observation_digest": observation_digest,
                "pdp_request_digest": admission.pdp_request_digest,
                "pdp_decision_digest": admission.pdp_decision_digest,
                "pdp_replay_key": admission.pdp_replay_key,
                "bundle_digest": admission.bundle_digest,
                "context_digest": admission.context_digest,
                "authority_lineage_digest": admission.authority_lineage_digest,
                "state": "RECONCILED",
            }
            reconciliation_digest = _hash(_RECONCILIATION_DOMAIN, reconciliation_payload)
            final_fence = self.fence.mark_reconciled(
                effect_key,
                reconciliation_digest=reconciliation_digest,
                reconciled_at=datetime.now(timezone.utc).isoformat(),
            )
            return {
                "schema_version": "1.0.0",
                "effect": CAPABILITY_REPOSITORY_REF_DELETE,
                "branch": operation.branch_name,
                "expected_head": operation.expected_branch_head,
                "master": final_master,
                "tree": final_tree,
                "bundle_digest": bundle.bundle_digest,
                "context_digest": admission.context_digest,
                "authority_lineage_digest": admission.authority_lineage_digest,
                "pdp_decision_digest": admission.pdp_decision_digest,
                "admission_digest": admission.admission_digest,
                "effect_key": effect_key,
                "observation_digest": observation_digest,
                "reconciliation_digest": reconciliation_digest,
                "fence_state": final_fence.state,
                "receipt": asdict(receipt),
            }
        except Exception:
            backend._pending_delete = None
            try:
                existing = self.fence.get(effect_key)
                if existing.state in {"PREPARED", "ATTEMPTED", "OBSERVED"}:
                    self.fence.mark_unknown(effect_key)
            except Exception:
                pass
            raise


def _load_external_module(path: Path, expected_digest: str) -> ModuleType:
    workspace_raw = os.environ.get("GITHUB_WORKSPACE")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise MediatedRepositoryMaintenanceError("trusted maintenance runtime provider unavailable") from exc
    if not resolved.is_file() or resolved.suffix != ".py":
        raise MediatedRepositoryMaintenanceError("trusted maintenance runtime provider invalid")
    if workspace_raw:
        workspace = Path(workspace_raw).resolve()
        if resolved == workspace or workspace in resolved.parents:
            raise MediatedRepositoryMaintenanceError("trusted maintenance runtime provider must be outside repository")
    _hex64(expected_digest, "runtime provider digest")
    if sha256(resolved.read_bytes()).hexdigest() != expected_digest:
        raise MediatedRepositoryMaintenanceError("trusted maintenance runtime provider digest mismatch")
    name = "_lion_maintenance_runtime_" + expected_digest[:20]
    spec = importlib.util.spec_from_file_location(name, resolved)
    if spec is None or spec.loader is None:
        raise MediatedRepositoryMaintenanceError("trusted maintenance runtime provider cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_pinned_external_dependencies(*, bundle: MaintenanceBundle) -> RepositoryMaintenanceTrustedDependencies:
    path_raw = _text(os.environ.get("LION_MAINTENANCE_RUNTIME_MODULE_PATH"), "runtime module path")
    digest = _text(os.environ.get("LION_MAINTENANCE_RUNTIME_MODULE_DIGEST"), "runtime module digest", limit=64)
    module = _load_external_module(Path(path_raw), digest)
    factory = getattr(module, _RUNTIME_FACTORY, None)
    if not callable(factory):
        raise MediatedRepositoryMaintenanceError("trusted maintenance runtime factory unavailable")
    value = factory(bundle.to_wire())
    if not isinstance(value, Mapping) or set(value) != {"context_resolver", "authority_admission", "authority_key"}:
        raise MediatedRepositoryMaintenanceError("trusted maintenance runtime dependency shape invalid")
    deps = RepositoryMaintenanceTrustedDependencies(
        context_resolver=value["context_resolver"],
        authority_admission=value["authority_admission"],
        authority_key=value["authority_key"],
        provider_id=digest,
    )
    return deps.validate(bundle=bundle, require_canonical_resolver=True)


def _bundle_source_from_environment() -> HttpMaintenanceBundleSource:
    base_url = _text(os.environ.get("LION_MAINTENANCE_BUNDLE_URL"), "maintenance bundle URL")
    credential = _text(os.environ.get("LION_MAINTENANCE_BUNDLE_TOKEN"), "maintenance bundle token", limit=16384)
    return HttpMaintenanceBundleSource(base_url=base_url, credential=credential)


def _fence_from_environment() -> RepositoryDeleteFence:
    raw = _text(os.environ.get("LION_REPOSITORY_DELETE_FENCE_DATABASE_PATH"), "repository delete fence database path")
    path = Path(raw)
    if not path.is_absolute():
        raise MediatedRepositoryMaintenanceError("repository delete fence path must be absolute")
    workspace_raw = os.environ.get("GITHUB_WORKSPACE")
    if workspace_raw:
        workspace = Path(workspace_raw).resolve()
        resolved = path.resolve()
        if resolved == workspace or workspace in resolved.parents:
            raise MediatedRepositoryMaintenanceError("repository delete fence must be outside repository")
    return RepositoryDeleteFence(str(path))


def run_exact_request(
    *,
    token: str,
    expected_master: str,
    expected_tree: str,
    event_path: Path,
    repository: str,
    execution_id: str,
) -> dict[str, object]:
    _sha40(expected_master, "expected_master")
    _sha40(expected_tree, "expected_tree")
    request = load_request_evidence(event_path=event_path, repository=repository)
    bundle_source = _bundle_source_from_environment()
    bundle = bundle_source.resolve_exact(repository=repository, capability=CAPABILITY_REPOSITORY_REF_DELETE)
    deps = load_pinned_external_dependencies(bundle=bundle)
    fence = _fence_from_environment()
    backend = CanonicalSlashSafeGitHubRepositoryMaintenanceBackend(REPOSITORY, token)
    observed_master = backend.master_sha()
    observed_tree = backend.master_tree(observed_master)
    if observed_master != expected_master or observed_tree != expected_tree:
        raise MediatedRepositoryMaintenanceError("workflow checkout/master tree currentness mismatch")
    observed_head = backend.branch_sha(request.branch)
    if observed_head != request.expected_branch_head:
        raise MediatedRepositoryMaintenanceError("requested branch head is not current")
    policy = RepositoryMaintenancePolicy(
        schema_version="1.0.0",
        repository=REPOSITORY,
        mission_id=bundle.binding.mission_id,
        protected_ref="master",
        allowed_prefixes=("docs/", "mission/"),
        max_deletions=1,
    ).validate()
    sandbox = RepositoryMaintenanceSandbox(policy=policy, backend=backend)
    operation, observation = _build_operation(
        sandbox=sandbox,
        branch=request.branch,
        index=1,
        master_sha=observed_master,
    )
    if operation.expected_branch_head != request.expected_branch_head:
        raise MediatedRepositoryMaintenanceError("classified branch head differs from exact request")
    runtime = RepositoryMaintenanceAdmissionRuntime(
        bundle_source=bundle_source,
        dependencies=deps,
        fence=fence,
    )
    result = runtime.execute_one(
        request=request,
        bundle=bundle,
        operation=operation,
        policy=policy,
        sandbox=sandbox,
        backend=backend,
        expected_master_tree=observed_tree,
        execution_id=execution_id,
    )
    return {**result, "request_digest": request.digest(), "classification": observation.canonical()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-exact-request", action="store_true")
    parser.add_argument("--expected-master", required=True)
    parser.add_argument("--expected-tree", required=True)
    args = parser.parse_args(argv)
    if not args.execute_exact_request:
        parser.error("--execute-exact-request required")
    try:
        token = _text(os.environ.get("GITHUB_TOKEN"), "GITHUB_TOKEN", limit=16384)
        repository = _text(os.environ.get("GITHUB_REPOSITORY"), "GITHUB_REPOSITORY")
        event_path = Path(_text(os.environ.get("GITHUB_EVENT_PATH"), "GITHUB_EVENT_PATH"))
        run_id = _text(os.environ.get("GITHUB_RUN_ID"), "GITHUB_RUN_ID", limit=64)
        run_attempt = _text(os.environ.get("GITHUB_RUN_ATTEMPT"), "GITHUB_RUN_ATTEMPT", limit=64)
        result = run_exact_request(
            token=token,
            expected_master=args.expected_master,
            expected_tree=args.expected_tree,
            event_path=event_path,
            repository=repository,
            execution_id=f"github:{run_id}:{run_attempt}",
        )
    except Exception as exc:
        print(f"LION mediated repository maintenance denied: {exc}", file=sys.stderr)
        return 2
    print("LION_REPOSITORY_MAINTENANCE_RESULT " + json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
