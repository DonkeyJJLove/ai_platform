"""Trusted bridge from existing cooperative runtime evidence to private worker bytes.

This module does not mint authority, create a scheduler/PDP, issue RuntimeAdmission,
or infer permission from an assignment/model payload. The caller supplies an already
composed CooperativeRuntimeContext and independently supplied artifact-transfer binding.

The bridge performs two bounded transports:
1. serialize a context reference without embedding RuntimeAdmission, materialize it in a
   fresh private workspace, and create an independent CooperativeContextPin;
2. copy the exact observed artifact bytes into a fresh verifier workspace, preserving
   the original mission/generation/path and expected digest.

The returned writer still executes only through PinnedCooperativeContextResolver,
CooperativeRuntimeWriterProvider, EffectTimeCurrentnessGuardedSandbox,
RuntimeExecutionEngine and ExecutorSandbox.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from cyber_lion.contracts.runtime_currentness import CurrentnessSourceTrustBinding
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.enterprise.cooperative_context_resolver import (
    CooperativeContextPin,
    PinnedCooperativeContextResolver,
    context_reference_bytes,
)
from cyber_lion.enterprise.cooperative_runtime_composition import (
    CooperativeRuntimeContext,
    CooperativeRuntimeWriterProvider,
)
from cyber_lion.enterprise.live_authority_admission import LiveAuthorityAdmission
from cyber_lion.enterprise.executor_sandbox import SandboxBudgetLedger
from cyber_lion.mission_control.artifact_transfer import (
    _binding,
    create_bundle,
    materialize_bundle,
    verify_workspace,
)
from cyber_lion.mission_control.cooperative_artifacts import (
    VERIFY_KIND,
    CooperativeArtifactError,
    read_artifact_bytes,
)

CONTEXT_FILENAME = "context.json"
PROVIDER_ID = "COOPERATIVE_RUNTIME_WRITER_R5"
CONTEXT_RESOLVER_ID = "PINNED_COOPERATIVE_CONTEXT_RESOLVER"
EXECUTION_ENGINE_ID = "RUNTIME_EXECUTION_ENGINE"
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class CooperativeProviderMaterializationError(ValueError):
    pass


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise CooperativeProviderMaterializationError(reason)


def _private_directory(value: str | Path, label: str) -> Path:
    path = Path(value)
    _require(path.is_absolute() and path.is_dir() and not path.is_symlink(), label)
    _require(path == path.resolve(strict=True), label + " symlink indirection")
    return path


def _transfer_binding(value: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return _binding(value)
    except Exception as exc:
        raise CooperativeProviderMaterializationError("exact artifact-transfer binding required") from exc


@dataclass(frozen=True)
class CooperativeContextMaterialization:
    assignment_id: str
    workspace: Path
    pin: CooperativeContextPin
    transfer_sha256: str
    transfer_binding: Mapping[str, Any]
    artifact_root: Path

    def validate(self) -> "CooperativeContextMaterialization":
        _require(type(self.assignment_id) is str and _ID.fullmatch(self.assignment_id) is not None,
                 "assignment identity")
        workspace = _private_directory(self.workspace, "context workspace")
        artifact_root = _private_directory(self.artifact_root, "artifact root")
        _require(type(self.pin) is CooperativeContextPin, "context pin type")
        self.pin.validate()
        _require(self.pin.assignment_id == self.assignment_id and self.pin.filename == CONTEXT_FILENAME,
                 "context pin association")
        _require(type(self.transfer_sha256) is str and _SHA.fullmatch(self.transfer_sha256) is not None,
                 "context transfer digest")
        binding = _transfer_binding(self.transfer_binding)
        _require(binding["assignment_id"] == self.assignment_id, "transfer assignment substitution")
        carrier = workspace / "_LION_TRANSFER.json"
        _require(carrier.is_file() and not carrier.is_symlink(), "context transfer carrier")
        raw = carrier.read_bytes()
        _require(sha256(raw).hexdigest() == self.transfer_sha256, "context transfer carrier digest")
        verify_workspace(workspace, raw, self.transfer_sha256, binding)
        context_file = workspace / self.pin.filename
        _require(context_file.is_file() and not context_file.is_symlink(), "context file")
        _require(sha256(context_file.read_bytes()).hexdigest() == self.pin.sha256, "context file pin")
        _require(artifact_root == self.artifact_root, "artifact root identity")
        return self


@dataclass(frozen=True)
class CooperativeVerifierMaterialization:
    source_assignment_id: str
    workspace: Path
    transfer_sha256: str
    transfer_binding: Mapping[str, Any]
    artifact_sha256: str
    artifact_path: str

    def validate(self) -> "CooperativeVerifierMaterialization":
        _require(type(self.source_assignment_id) is str and _ID.fullmatch(self.source_assignment_id) is not None,
                 "source assignment identity")
        workspace = _private_directory(self.workspace, "verifier workspace")
        _require(type(self.transfer_sha256) is str and _SHA.fullmatch(self.transfer_sha256) is not None,
                 "verifier transfer digest")
        _require(type(self.artifact_sha256) is str and _SHA.fullmatch(self.artifact_sha256) is not None,
                 "verifier artifact digest")
        binding = _transfer_binding(self.transfer_binding)
        carrier = workspace / "_LION_TRANSFER.json"
        _require(carrier.is_file() and not carrier.is_symlink(), "verifier transfer carrier")
        raw = carrier.read_bytes()
        _require(sha256(raw).hexdigest() == self.transfer_sha256, "verifier carrier digest")
        verify_workspace(workspace, raw, self.transfer_sha256, binding)
        target = workspace / self.artifact_path
        _require(target.is_file() and not target.is_symlink(), "verifier artifact")
        _require(sha256(target.read_bytes()).hexdigest() == self.artifact_sha256,
                 "verifier artifact readback")
        return self


def provider_status_marker() -> dict[str, Any]:
    """Exact live marker expected by Mission Control readiness.

    Returning this function's value alone is not sufficient for readiness. A worker
    may publish it only after its concrete provider factory has been built from
    canonical dependencies and private storage.
    """
    return {
        "state": "READY",
        "provider_id": PROVIDER_ID,
        "context_resolver": CONTEXT_RESOLVER_ID,
        "execution_engine": EXECUTION_ENGINE_ID,
        "authority_effect": "NONE",
    }


def materialize_context_reference(
    *,
    context: CooperativeRuntimeContext,
    coordinates: Mapping[str, Any],
    expected_binding: Mapping[str, Any],
    private_parent: str | Path,
) -> CooperativeContextMaterialization:
    """Serialize existing runtime evidence into a fresh private pinned workspace."""
    if type(context) is not CooperativeRuntimeContext:
        raise CooperativeProviderMaterializationError("exact CooperativeRuntimeContext required")
    context.validate()
    binding = _transfer_binding(expected_binding)
    execution = context.execution
    _require(binding["assignment_id"] == execution.assignment_id, "context transfer assignment mismatch")
    _require(binding["mission_id"] == execution.request.mission_id, "context transfer mission mismatch")
    _require(binding["generation"] == execution.request.generation, "context transfer generation mismatch")
    _require(binding["lease_generation"] == execution.request.generation, "context transfer lease mismatch")
    parent = _private_directory(private_parent, "context private parent")
    data = context_reference_bytes(context, dict(coordinates))
    raw = create_bundle({CONTEXT_FILENAME: data}, binding)
    transfer_sha = sha256(raw).hexdigest()
    result = materialize_bundle(raw, transfer_sha, binding, parent)
    workspace = Path(result["workspace"]).resolve(strict=True)
    pin = CooperativeContextPin(execution.assignment_id, CONTEXT_FILENAME, sha256(data).hexdigest()).validate()
    materialized = CooperativeContextMaterialization(
        execution.assignment_id,
        workspace,
        pin,
        transfer_sha,
        binding,
        Path(execution.artifact_root),
    )
    return materialized.validate()


def build_runtime_writer_provider(
    *,
    materialization: CooperativeContextMaterialization,
    mission_db: str | Path,
    admission_source,
    admission_trust: RuntimeAdmissionSourceTrustBinding,
    authority_admission: LiveAuthorityAdmission,
    currentness_source,
    currentness_trust: CurrentnessSourceTrustBinding,
    dispatch_source,
    runtime_identity_source: Callable[[str], Any],
    admission_guard,
    sandbox_guard,
    budget_source: Callable[[Any], SandboxBudgetLedger],
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> tuple[PinnedCooperativeContextResolver, CooperativeRuntimeWriterProvider]:
    """Build the existing R5 resolver/writer around independently supplied owners."""
    materialization.validate()
    if type(admission_trust) is not RuntimeAdmissionSourceTrustBinding:
        raise CooperativeProviderMaterializationError("exact admission trust required")
    if type(currentness_trust) is not CurrentnessSourceTrustBinding:
        raise CooperativeProviderMaterializationError("exact currentness trust required")
    if not isinstance(authority_admission, LiveAuthorityAdmission):
        raise CooperativeProviderMaterializationError("canonical LiveAuthorityAdmission required")
    admission_trust.validate(); currentness_trust.validate()
    if not callable(runtime_identity_source) or not callable(budget_source) or not callable(now_fn):
        raise CooperativeProviderMaterializationError("trusted provider sources required")
    resolver = PinnedCooperativeContextResolver(
        mission_db=Path(mission_db),
        context_directory=materialization.workspace,
        pins=(materialization.pin,),
        admission_source=admission_source,
        admission_trust=admission_trust,
        dispatch_source=dispatch_source,
        runtime_identity_source=runtime_identity_source,
        now_fn=now_fn,
    )
    provider = CooperativeRuntimeWriterProvider(
        context_source=resolver,
        admission_source=admission_source,
        admission_trust=admission_trust,
        authority_admission=authority_admission,
        currentness_source=currentness_source,
        currentness_trust=currentness_trust,
        dispatch_source=dispatch_source,
        admission_guard=admission_guard,
        sandbox_guard=sandbox_guard,
        budget_source=budget_source,
        now_fn=now_fn,
    )
    return resolver, provider


def materialize_verifier_view(
    *,
    artifact_root: str | Path,
    verify_payload: Mapping[str, Any],
    expected_binding: Mapping[str, Any],
    private_parent: str | Path,
) -> CooperativeVerifierMaterialization:
    """Transport exact observed artifact bytes into a fresh verifier workspace.

    This function does not claim that verification has happened. The distinct verifier
    must still call verify_text() on the returned workspace using its own worker identity.
    """
    if not isinstance(verify_payload, Mapping) or verify_payload.get("kind") != VERIFY_KIND:
        raise CooperativeProviderMaterializationError("verify payload kind")
    mission = verify_payload.get("mission_id")
    assignment = verify_payload.get("source_assignment_id")
    generation = verify_payload.get("generation")
    name = verify_payload.get("artifact_name")
    expected = verify_payload.get("expected_sha256")
    producer = verify_payload.get("expected_producer_worker_id")
    _require(type(mission) is str and _ID.fullmatch(mission) is not None, "verify mission")
    _require(type(assignment) is str and _ID.fullmatch(assignment) is not None, "verify source assignment")
    _require(type(generation) is int and 1 <= generation <= 2147483647, "verify generation")
    _require(type(name) is str and _NAME.fullmatch(name) is not None, "verify artifact name")
    _require(type(expected) is str and _SHA.fullmatch(expected) is not None, "verify artifact digest")
    _require(type(producer) is str and _ID.fullmatch(producer) is not None, "verify producer identity")
    binding = _transfer_binding(expected_binding)
    _require(binding["mission_id"] == mission, "verifier transfer mission mismatch")
    _require(binding["assignment_id"] == assignment, "verifier transfer source assignment mismatch")
    _require(binding["generation"] == generation and binding["lease_generation"] == generation,
             "verifier transfer generation mismatch")
    parent = _private_directory(private_parent, "verifier private parent")
    data = read_artifact_bytes(
        artifact_root, mission_id=mission, generation=generation, artifact_name=name,
    )
    actual = sha256(data).hexdigest()
    _require(actual == expected, "builder artifact digest mismatch before transfer")
    rel = f"{mission}/g{generation:08d}/{name}"
    raw = create_bundle({rel: data}, binding)
    transfer_sha = sha256(raw).hexdigest()
    result = materialize_bundle(raw, transfer_sha, binding, parent)
    materialized = CooperativeVerifierMaterialization(
        assignment,
        Path(result["workspace"]).resolve(strict=True),
        transfer_sha,
        binding,
        actual,
        rel,
    )
    return materialized.validate()
