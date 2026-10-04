"""Per-assignment cooperative writer using LION's existing enforcement owners.

The composition root supplies already-admitted runtime contexts, trusted sources
and long-lived consumption/budget state. Neither a payload nor this module can
issue an admission. No scheduler, listener, worker restart or authority store is
created here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable

from cyber_lion.contracts.executor_sandbox import (
    ExecutionSandboxPolicy, FleetDispatchBinding, ProvisioningBinding,
    SandboxRuntimeBinding,
)
from cyber_lion.contracts.runtime_currentness import CurrentnessSourceTrustBinding
from cyber_lion.contracts.runtime_execution import RuntimeAdmissionSourceTrustBinding
from cyber_lion.enterprise.cooperative_runtime_writer import (
    CanonicalCooperativeWriter, CooperativeArtifactBackend,
    CooperativeExecutionBinding, CooperativeRuntimeWriterError,
)
from cyber_lion.enterprise.executor_sandbox import (
    ExecutorSandbox, FleetDispatchSource, SandboxBudgetLedger, SandboxReplayGuard,
)
from cyber_lion.enterprise.live_authority_admission import LiveAuthorityAdmission
from cyber_lion.enterprise.runtime_currentness import (
    EffectTimeCurrentnessGuardedSandbox, EffectTimeCurrentnessSource,
)
from cyber_lion.enterprise.runtime_execution import (
    AdmissionConsumptionGuard, RuntimeAdmissionSource, RuntimeExecutionEngine,
)


@dataclass(frozen=True)
class CooperativeRuntimeContext:
    """One exact provisioned context, resolved outside model-controlled data."""
    execution: CooperativeExecutionBinding
    policy: ExecutionSandboxPolicy
    runtime: SandboxRuntimeBinding
    dispatch: FleetDispatchBinding
    provisioning: ProvisioningBinding

    def validate(self) -> "CooperativeRuntimeContext":
        b = self.execution
        if type(b) is not CooperativeExecutionBinding:
            raise CooperativeRuntimeWriterError("exact execution binding required")
        for value, cls in ((self.policy, ExecutionSandboxPolicy),
                           (self.runtime, SandboxRuntimeBinding),
                           (self.dispatch, FleetDispatchBinding),
                           (self.provisioning, ProvisioningBinding)):
            if type(value) is not cls:
                raise CooperativeRuntimeWriterError("exact provisioned context required")
            value.validate()
        b.admission.validate(); b.request.validate(); b.effect.validate(); b.identity.validate()
        self.policy.validate_bindings(self.dispatch, self.provisioning)
        if self.policy.runtime_binding_digest != self.runtime.digest():
            raise CooperativeRuntimeWriterError("sandbox runtime context substitution")
        names = ("mission_id", "executor_id", "runtime_instance_id", "sandbox_id",
                 "workspace_id", "dispatch_id", "fencing_token", "generation")
        if any(getattr(self.policy, n) != getattr(b.request, n) for n in names):
            raise CooperativeRuntimeWriterError("policy/request coordinates mismatch")
        if self.policy.drone_id != b.identity.workload_identity:
            raise CooperativeRuntimeWriterError("workload identity mismatch")
        if b.request.action != "WRITE_FILE":
            raise CooperativeRuntimeWriterError("cooperative writer permits WRITE_FILE only")
        if self.policy.write_scope != (b.request.resource,):
            raise CooperativeRuntimeWriterError("single-artifact write scope required")
        if b.request.provisioned_executor_digest != self.provisioning.provisioned_executor_digest:
            raise CooperativeRuntimeWriterError("provisioned executor context substitution")
        if b.identity.runtime_attestation_digest != self.policy.runtime_attestation_digest:
            raise CooperativeRuntimeWriterError("runtime attestation context substitution")
        return self


class CooperativeRuntimeWriterProvider:
    """Concrete admitted_writer for the existing cooperative assignment adapter.

    Guards and budget_source belong to the long-lived trusted composition root.
    Rebuilding a provider must NOT reset those dependencies. The supplied
    context_source resolves a fresh context on each call; it is not taken from
    the assignment payload. Runtime and effect-time trust pins are independent
    constructor inputs, never derived from the presented sources.
    """
    def __init__(
        self, *, context_source: Callable[[str], CooperativeRuntimeContext],
        admission_source: RuntimeAdmissionSource,
        admission_trust: RuntimeAdmissionSourceTrustBinding,
        authority_admission: LiveAuthorityAdmission,
        currentness_source: EffectTimeCurrentnessSource,
        currentness_trust: CurrentnessSourceTrustBinding,
        dispatch_source: FleetDispatchSource,
        admission_guard: AdmissionConsumptionGuard,
        sandbox_guard: SandboxReplayGuard,
        budget_source: Callable[[ExecutionSandboxPolicy], SandboxBudgetLedger],
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if not callable(context_source) or not callable(budget_source) or not callable(now_fn):
            raise CooperativeRuntimeWriterError("trusted context, budget and clock sources required")
        if not isinstance(authority_admission, LiveAuthorityAdmission):
            raise CooperativeRuntimeWriterError("canonical live authority revalidator required")
        if type(admission_trust) is not RuntimeAdmissionSourceTrustBinding:
            raise CooperativeRuntimeWriterError("admission trust binding required")
        if type(currentness_trust) is not CurrentnessSourceTrustBinding:
            raise CooperativeRuntimeWriterError("currentness trust binding required")
        admission_trust.validate(); currentness_trust.validate()
        for obj, methods in ((admission_guard, ("consume",)), (sandbox_guard, ("consume",)),
                             (dispatch_source, ("current_dispatch",))):
            if not all(callable(getattr(obj, n, None)) for n in methods):
                raise CooperativeRuntimeWriterError("persistent runtime dependencies unavailable")
        self._context = context_source
        self._admission_source, self._admission_trust = admission_source, admission_trust
        self._authority = authority_admission
        self._currentness_source, self._currentness_trust = currentness_source, currentness_trust
        self._dispatch, self._admission_guard, self._sandbox_guard = dispatch_source, admission_guard, sandbox_guard
        self._budgets, self._now = budget_source, now_fn

    def __call__(self, *, claimed, payload, artifact_root, worker_id):
        assignment_id = claimed.get("assignment_id")
        if type(assignment_id) is not str or not assignment_id:
            raise CooperativeRuntimeWriterError("claimed assignment identity required")
        ctx = self._context(assignment_id)
        if type(ctx) is not CooperativeRuntimeContext:
            raise CooperativeRuntimeWriterError("canonical runtime context unavailable")
        ctx.validate()
        if ctx.execution.assignment_id != assignment_id:
            raise CooperativeRuntimeWriterError("context lookup returned another assignment")
        budget = self._budgets(ctx.policy)
        if type(budget) is not SandboxBudgetLedger:
            raise CooperativeRuntimeWriterError("bound sandbox budget unavailable")
        backend = CooperativeArtifactBackend(root=ctx.execution.artifact_root, payload=payload,
                                             worker_id=worker_id, runtime_binding=ctx.runtime)
        sandbox = ExecutorSandbox(policy=ctx.policy, runtime_binding=ctx.runtime,
                                  fleet_dispatch=ctx.dispatch, provisioning_binding=ctx.provisioning,
                                  dispatch_source=self._dispatch, backend=backend,
                                  replay_guard=self._sandbox_guard, budget_ledger=budget)
        guarded = EffectTimeCurrentnessGuardedSandbox(
            inner=sandbox, admission=ctx.execution.admission, effect=ctx.execution.effect,
            runtime_identity=ctx.execution.identity, authority_admission=self._authority,
            currentness_source=self._currentness_source, currentness_trust=self._currentness_trust,
            clock=self._now,
        )
        engine = RuntimeExecutionEngine(admission_source=self._admission_source,
                                        admission_source_trust=self._admission_trust,
                                        consumption_guard=self._admission_guard, sandbox=guarded)
        writer = CanonicalCooperativeWriter(engine=engine,
                                            binding_source=lambda aid: ctx.execution if aid == assignment_id else None,
                                            now_fn=self._now)
        try:
            result = writer(claimed=claimed, payload=payload,
                            artifact_root=artifact_root, worker_id=worker_id)
            evidence = guarded.last_currentness_evidence
            if evidence is None:
                raise CooperativeRuntimeWriterError("effect-time currentness evidence missing")
            evidence.validate()
            return {**result, "effect_time_currentness": asdict(evidence)}
        finally:
            sandbox.close()
