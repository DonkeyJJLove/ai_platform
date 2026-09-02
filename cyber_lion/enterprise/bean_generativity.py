"""Candidate-only two-unseen-problem generativity protocol for The Bean Factory.

The protocol is deliberately non-effectful. It uses one generic deterministic program
synthesizer for heterogeneous problem descriptors, binds the result through the existing
Gap -> CapabilityNeed -> BeanSpec -> Composition -> Mosaic -> BeanCandidate chain, and
requires an independently identified verifier over holdout evidence. It never attaches a
candidate, invokes a repository builder, mints authority, performs network I/O, or mutates
external state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import permutations
import json
from typing import Any, Mapping, Tuple

from cyber_lion.contracts.bean import BeanContractError, BeanSpec
from cyber_lion.contracts.bean_candidate import BeanCandidate, verify_candidate
from cyber_lion.contracts.bean_composition import CompositionRequest
from cyber_lion.contracts.capability_need import derive_capability_needs
from cyber_lion.contracts.evolutionary_state import (
    GoalContract,
    SystemSnapshot,
    WorldSnapshot,
    derive_gap,
)
from cyber_lion.contracts.mosaic import advance_mosaic
from cyber_lion.enterprise.bean_composition import BeanDescriptor, CompositionEngine
from cyber_lion.enterprise.capability_need import CapabilityNeedResolver
from cyber_lion.enterprise.mosaic import HeterogeneousMosaicPlanner


class GenerativityProtocolError(RuntimeError):
    pass


_INPUT_KINDS = frozenset({"text-list", "int-list"})
_OUTPUT_KINDS = frozenset({"text-list", "int"})
_TERMINAL = frozenset({"PASS", "FALSIFIED"})
_WORKFLOW_TYPE = "GENERIC_BEAN_GENERATIVITY_PROTOCOL_V1"


def _canonical(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    if isinstance(value, Mapping):
        return {
            str(k): _canonical(v)
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, tuple):
        return [_canonical(v) for v in value]
    if isinstance(value, list):
        return [_canonical(v) for v in value]
    return value


def _digest(domain: bytes, value: Any) -> str:
    raw = json.dumps(
        _canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256(domain + b"\0" + raw).hexdigest()


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise GenerativityProtocolError(f"{name} invalid")
    return value


@dataclass(frozen=True)
class GenerativityExample:
    example_id: str
    input_value: Tuple[Any, ...]
    expected_output: Any

    def validate(
        self, *, input_kind: str, output_kind: str
    ) -> "GenerativityExample":
        _text(self.example_id, "example_id")
        if type(self.input_value) is not tuple:
            raise GenerativityProtocolError("input_value must be immutable tuple")
        if input_kind == "text-list":
            if any(not isinstance(v, str) for v in self.input_value):
                raise GenerativityProtocolError(
                    "text-list example contains non-text input"
                )
        elif input_kind == "int-list":
            if any(
                isinstance(v, bool) or not isinstance(v, int)
                for v in self.input_value
            ):
                raise GenerativityProtocolError(
                    "int-list example contains non-int input"
                )
        else:
            raise GenerativityProtocolError("unsupported input kind")
        if output_kind == "text-list":
            if type(self.expected_output) is not tuple or any(
                not isinstance(v, str) for v in self.expected_output
            ):
                raise GenerativityProtocolError("text-list expected_output invalid")
        elif output_kind == "int":
            if isinstance(self.expected_output, bool) or not isinstance(
                self.expected_output, int
            ):
                raise GenerativityProtocolError("int expected_output invalid")
        else:
            raise GenerativityProtocolError("unsupported output kind")
        return self

    def digest(self) -> str:
        return _digest(b"LION/B0-GENERATIVITY-EXAMPLE/1", self)


@dataclass(frozen=True)
class GenerativityProblem:
    problem_id: str
    problem_family: str
    required_capability: str
    input_kind: str
    output_kind: str
    training_examples: Tuple[GenerativityExample, ...]
    holdout_examples: Tuple[GenerativityExample, ...]
    provenance_refs: Tuple[str, ...]
    baseline_revision: str
    baseline_tree_digest: str

    def validate(self) -> "GenerativityProblem":
        for name in (
            "problem_id",
            "problem_family",
            "required_capability",
            "baseline_revision",
            "baseline_tree_digest",
        ):
            _text(getattr(self, name), name)
        if self.input_kind not in _INPUT_KINDS or self.output_kind not in _OUTPUT_KINDS:
            raise GenerativityProtocolError(
                "problem kind outside closed experiment vocabulary"
            )
        if type(self.training_examples) is not tuple or not self.training_examples:
            raise GenerativityProtocolError("training examples required")
        if type(self.holdout_examples) is not tuple or not self.holdout_examples:
            raise GenerativityProtocolError("holdout examples required")
        ids = []
        for example in self.training_examples + self.holdout_examples:
            if type(example) is not GenerativityExample:
                raise GenerativityProtocolError("exact GenerativityExample required")
            example.validate(
                input_kind=self.input_kind,
                output_kind=self.output_kind,
            )
            ids.append(example.example_id)
        if len(ids) != len(set(ids)):
            raise GenerativityProtocolError("example ids must be unique")
        if type(self.provenance_refs) is not tuple or not self.provenance_refs:
            raise GenerativityProtocolError("provenance refs required")
        if any(not isinstance(v, str) or not v for v in self.provenance_refs):
            raise GenerativityProtocolError("provenance refs invalid")
        if len(set(self.provenance_refs)) != len(self.provenance_refs):
            raise GenerativityProtocolError("provenance refs must be unique")
        return self

    def digest(self) -> str:
        self.validate()
        return _digest(b"LION/B0-GENERATIVITY-PROBLEM/1", self)


@dataclass(frozen=True)
class SynthesizedProgram:
    input_kind: str
    output_kind: str
    operations: Tuple[str, ...]
    constant: int | None = None

    def validate(self) -> "SynthesizedProgram":
        if self.input_kind not in _INPUT_KINDS or self.output_kind not in _OUTPUT_KINDS:
            raise GenerativityProtocolError("program kind invalid")
        if type(self.operations) is not tuple or not self.operations:
            raise GenerativityProtocolError("program operations required")
        if any(not isinstance(op, str) or not op for op in self.operations):
            raise GenerativityProtocolError("program operation invalid")
        if self.constant is not None and (
            isinstance(self.constant, bool) or not isinstance(self.constant, int)
        ):
            raise GenerativityProtocolError("program constant invalid")
        return self

    def digest(self) -> str:
        self.validate()
        return _digest(b"LION/B0-SYNTHESIZED-PROGRAM/1", self)


@dataclass(frozen=True)
class GenerativityTerminalEvidence:
    problem_id: str
    problem_family: str
    problem_digest: str
    workflow_type: str
    gap_digest: str
    capability_need_digest: str
    resolution_disposition: str
    generated_spec_digest: str
    synthesized_program_digest: str
    composition_digest: str
    dissolved_mosaic_digest: str
    built_candidate_digest: str
    verified_candidate_digest: str
    training_evidence_digest: str
    holdout_evidence_digest: str
    status: str
    failure_reason: str
    authority_effect: str = "NONE"
    execution_effect: str = "NONE"
    repository_ref_effect: str = "NONE"
    external_effect: str = "NONE"

    def validate(self) -> "GenerativityTerminalEvidence":
        for name in (
            "problem_id",
            "problem_family",
            "problem_digest",
            "workflow_type",
            "gap_digest",
            "capability_need_digest",
            "resolution_disposition",
            "generated_spec_digest",
            "synthesized_program_digest",
            "composition_digest",
            "dissolved_mosaic_digest",
            "built_candidate_digest",
            "training_evidence_digest",
            "holdout_evidence_digest",
        ):
            _text(getattr(self, name), name)
        if self.workflow_type != _WORKFLOW_TYPE:
            raise GenerativityProtocolError("workflow type substitution detected")
        if self.resolution_disposition != "GENERATE_SPEC":
            raise GenerativityProtocolError(
                "terminal generativity evidence requires generated spec"
            )
        if self.status not in _TERMINAL:
            raise GenerativityProtocolError("terminal status invalid")
        if self.status == "PASS":
            _text(self.verified_candidate_digest, "verified_candidate_digest")
            if self.failure_reason:
                raise GenerativityProtocolError("PASS cannot carry failure reason")
        else:
            if not self.failure_reason:
                raise GenerativityProtocolError("FALSIFIED requires failure reason")
            if self.verified_candidate_digest:
                raise GenerativityProtocolError(
                    "FALSIFIED cannot claim verified candidate"
                )
        if (
            self.authority_effect,
            self.execution_effect,
            self.repository_ref_effect,
            self.external_effect,
        ) != ("NONE", "NONE", "NONE", "NONE"):
            raise GenerativityProtocolError("terminal evidence cannot carry effects")
        return self

    def digest(self) -> str:
        self.validate()
        return _digest(b"LION/B0-GENERATIVITY-TERMINAL/1", self)


class DeterministicProgramSynthesizer:
    """Fixed grammar search; it never switches on problem id or family."""

    _TEXT_OPS = ("strip", "lower", "dedupe", "sort")

    def synthesize(self, problem: GenerativityProblem) -> SynthesizedProgram:
        problem.validate()
        candidates = self._programs(problem)
        passing = []
        for candidate in candidates:
            if all(
                self._training_execute(candidate, ex.input_value)
                == ex.expected_output
                for ex in problem.training_examples
            ):
                passing.append(candidate)
        if not passing:
            raise GenerativityProtocolError(
                "no program in fixed grammar satisfies training evidence"
            )
        return sorted(
            passing,
            key=lambda program: (len(program.operations), program.digest()),
        )[0]

    def _programs(
        self, problem: GenerativityProblem
    ) -> Tuple[SynthesizedProgram, ...]:
        if (problem.input_kind, problem.output_kind) == (
            "text-list",
            "text-list",
        ):
            result = []
            for size in range(1, len(self._TEXT_OPS) + 1):
                for ops in permutations(self._TEXT_OPS, size):
                    result.append(
                        SynthesizedProgram(
                            "text-list", "text-list", tuple(ops)
                        ).validate()
                    )
            return tuple(result)
        if (problem.input_kind, problem.output_kind) == ("int-list", "int"):
            values = sorted(
                {
                    item
                    for ex in problem.training_examples
                    for item in ex.input_value
                }
            )
            result = [
                SynthesizedProgram("int-list", "int", (op,)).validate()
                for op in ("len", "sum", "min", "max")
            ]
            for op in ("count_gt", "count_ge", "count_lt", "count_le"):
                for constant in values:
                    result.append(
                        SynthesizedProgram(
                            "int-list", "int", (op,), constant
                        ).validate()
                    )
            return tuple(result)
        raise GenerativityProtocolError("no grammar for problem kinds")

    @staticmethod
    def _training_execute(
        program: SynthesizedProgram, value: Tuple[Any, ...]
    ) -> Any:
        program.validate()
        if program.input_kind == "text-list":
            current = list(value)
            for op in program.operations:
                if op == "strip":
                    current = [v.strip() for v in current]
                elif op == "lower":
                    current = [v.lower() for v in current]
                elif op == "dedupe":
                    seen = set()
                    current = [
                        v
                        for v in current
                        if not (v in seen or seen.add(v))
                    ]
                elif op == "sort":
                    current = sorted(current)
                else:
                    raise GenerativityProtocolError("unknown text operation")
            return tuple(current)
        nums = list(value)
        op = program.operations[0]
        if op == "len":
            return len(nums)
        if op == "sum":
            return sum(nums)
        if op == "min":
            return min(nums)
        if op == "max":
            return max(nums)
        constant = program.constant
        if constant is None:
            raise GenerativityProtocolError("threshold reducer missing constant")
        if op == "count_gt":
            return sum(1 for v in nums if v > constant)
        if op == "count_ge":
            return sum(1 for v in nums if v >= constant)
        if op == "count_lt":
            return sum(1 for v in nums if v < constant)
        if op == "count_le":
            return sum(1 for v in nums if v <= constant)
        raise GenerativityProtocolError("unknown integer operation")


def _reference_execute(
    program: SynthesizedProgram, value: Tuple[Any, ...]
) -> Any:
    """Independent holdout evaluator with a separate implementation path."""
    program.validate()
    if program.input_kind == "text-list":
        data = tuple(value)
        for op in program.operations:
            if op == "strip":
                data = tuple(map(str.strip, data))
            elif op == "lower":
                data = tuple(map(str.lower, data))
            elif op == "dedupe":
                data = tuple(dict.fromkeys(data))
            elif op == "sort":
                data = tuple(sorted(data))
            else:
                raise GenerativityProtocolError(
                    "reference evaluator rejected operation"
                )
        return data
    op = program.operations[0]
    data = tuple(int(v) for v in value)
    reducers = {
        "len": lambda: len(data),
        "sum": lambda: sum(data),
        "min": lambda: min(data),
        "max": lambda: max(data),
        "count_gt": lambda: len(
            tuple(filter(lambda v: v > program.constant, data))
        ),
        "count_ge": lambda: len(
            tuple(filter(lambda v: v >= program.constant, data))
        ),
        "count_lt": lambda: len(
            tuple(filter(lambda v: v < program.constant, data))
        ),
        "count_le": lambda: len(
            tuple(filter(lambda v: v <= program.constant, data))
        ),
    }
    if op not in reducers:
        raise GenerativityProtocolError("reference evaluator rejected reducer")
    return reducers[op]()


def _support_spec(
    *,
    bean_id: str,
    bean_type: str,
    capability: str,
    goal_digest: str,
    observability: Tuple[str, ...],
) -> BeanSpec:
    return BeanSpec(
        bean_id=bean_id,
        bean_type=bean_type,
        version="1.0.0",
        purpose=f"B0 generic {bean_type}",
        goal_digest=goal_digest,
        success_conditions=(f"{capability} evidence emitted",),
        stop_conditions=("terminal evidence emitted",),
        defer_conditions=("required evidence unavailable",),
        inputs=(),
        outputs=(),
        interfaces=(f"capability:{capability}:v1",),
        required_capabilities=(),
        provided_capabilities=(capability,),
        authority_ceiling="none",
        required_grants=(),
        epistemic_requirements=("OBSERVED",),
        evidence_requirements=("b0-problem-evidence",),
        provenance_policy=("candidate-only",),
        memory_policy=("candidate-only-until-promotion",),
        context_policy=("typed-input-only",),
        observability_requirements=observability,
        resource_budget=("bounded",),
        cost_budget="1",
        time_budget="60s",
        runtime_class="deterministic-local",
        sandbox_class="no-effect",
        dependencies=(),
        compatibility_constraints=(f"capability:{capability}:v1",),
        failure_modes=("verification-failure",),
        degradation_policy=("DEFER",),
        revocation_policy=("discard-candidate",),
        security_invariants=("no-authority-minting", "no-attach"),
        acceptance_tests=(f"{capability} evidence emitted",),
        falsification_conditions=(f"{capability} evidence mismatch",),
        evolution_hooks=("b0-generativity",),
        replacement_policy=("exact-lineage",),
        supersession_policy=("preserve-history",),
    ).validate()


class BeanGenerativityProtocol:
    def __init__(self) -> None:
        self._resolver = CapabilityNeedResolver()
        self._synthesizer = DeterministicProgramSynthesizer()
        self._composer = CompositionEngine()
        self._mosaic = HeterogeneousMosaicPlanner()

    def run(self, problem: GenerativityProblem) -> GenerativityTerminalEvidence:
        problem.validate()
        goal = GoalContract(
            goal_id=f"b0:{problem.problem_id}",
            revision=1,
            objective=(
                f"Materialize missing capability {problem.required_capability} "
                "from evidence"
            ),
            constraints=("candidate-only", "no-attach", "no-authority-minting"),
            success_conditions=(
                "holdout evidence satisfies expected output",
            ),
            stop_conditions=(
                "terminal PASS or FALSIFIED evidence emitted",
            ),
            defer_conditions=("fixed grammar has no satisfying candidate",),
            authority_ceiling="none",
            source_ref=f"problem:{problem.digest()}",
        ).validate()
        training_set_digest = _digest(
            b"LION/B0-TRAINING-SET/1", problem.training_examples
        )
        holdout_set_digest = _digest(
            b"LION/B0-HOLDOUT-SET/1", problem.holdout_examples
        )
        world = WorldSnapshot(
            snapshot_id=f"world:{problem.problem_id}",
            observed_at="2026-09-02T00:00:00Z",
            captured_at="2026-09-02T00:00:00Z",
            epistemic_state="CURRENT",
            observations=(
                ("problem_family", problem.problem_family),
                ("training_evidence_digest", training_set_digest),
                ("holdout_evidence_digest", holdout_set_digest),
            ),
            source_refs=problem.provenance_refs,
            evidence_refs=tuple(
                ex.digest()
                for ex in problem.training_examples + problem.holdout_examples
            ),
            freshness_deadline="2099-01-01T00:00:00Z",
        ).validate()
        system = SystemSnapshot(
            snapshot_id=f"system:{problem.problem_id}",
            observed_at="2026-09-02T00:00:00Z",
            captured_at="2026-09-02T00:00:00Z",
            epistemic_state="CURRENT",
            repository="DonkeyJJLove/ai_platform",
            revision=problem.baseline_revision,
            tree_digest=problem.baseline_tree_digest,
            implementation_facts=(
                ("generativity_workflow", _WORKFLOW_TYPE),
                ("synthesizer", "fixed-grammar-deterministic"),
                ("repository_attach", "forbidden"),
            ),
            test_evidence_refs=(),
            observation_refs=(f"problem:{problem.digest()}",),
            freshness_deadline="2099-01-01T00:00:00Z",
        ).validate()
        gap = derive_gap(
            gap_id=f"gap:{problem.problem_id}",
            goal=goal,
            world=world,
            system=system,
            missing_capabilities=(problem.required_capability,),
            unsatisfied_conditions=(
                "required capability has no compatible BeanSpec in experiment catalog",
            ),
            evidence_refs=problem.provenance_refs,
            falsification_conditions=(
                "no fixed-grammar program satisfies training evidence",
                "holdout evidence mismatch",
            ),
        )
        need = derive_capability_needs(
            gap=gap,
            goal_digest=goal.digest(),
            capability_requirements=(
                (
                    problem.required_capability,
                    ("problem_input",),
                    ("problem_output",),
                    "none",
                ),
            ),
            provenance_refs=problem.provenance_refs,
        )[0]
        resolution = self._resolver.resolve(need=need, catalog=())
        if (
            resolution.disposition != "GENERATE_SPEC"
            or resolution.generated_spec is None
        ):
            raise GenerativityProtocolError(
                "unseen problem did not require generated BeanSpec"
            )
        generated = resolution.generated_spec
        program = self._synthesizer.synthesize(problem)
        training_digest = _digest(
            b"LION/B0-TRAINING-RESULT/1",
            tuple(
                (
                    ex.example_id,
                    self._synthesizer._training_execute(
                        program, ex.input_value
                    ),
                    ex.expected_output,
                )
                for ex in problem.training_examples
            ),
        )
        verifier_identity = _digest(
            b"LION/B0-VERIFIER-IDENTITY/1",
            {"implementation": "reference-evaluator-v1"},
        )
        observer_identity = _digest(
            b"LION/B0-OBSERVER-IDENTITY/1",
            {"implementation": "terminal-observer-v1"},
        )
        builder_identity = _digest(
            b"LION/B0-BUILDER-IDENTITY/1",
            {"implementation": "fixed-grammar-synthesizer-v1"},
        )
        verifier_spec = _support_spec(
            bean_id="b0-generic-verifier",
            bean_type="verifier",
            capability="candidate-verification",
            goal_digest=goal.digest(),
            observability=("verification-evidence",),
        )
        observer_spec = _support_spec(
            bean_id="b0-generic-observer",
            bean_type="observer",
            capability="candidate-observation",
            goal_digest=goal.digest(),
            observability=("pre-state", "post-state"),
        )
        request = CompositionRequest(
            composition_id=f"composition:{problem.problem_id}",
            mission_id=f"b0-mission:{problem.problem_id}",
            goal_digest=goal.digest(),
            required_capabilities=(problem.required_capability,),
            external_allowed_capabilities=(),
            mission_inputs=("problem_input",),
            max_resource_units=8,
            max_cost_units=8,
            required_observability_channels=("pre-state", "post-state"),
            observability_quorum=1,
            consequential=True,
            mission_authority_ceiling="none",
            conflict_pairs=(),
            provenance_refs=(gap.digest(), need.digest(), problem.digest()),
        ).validate()
        descriptors = (
            BeanDescriptor(
                generated,
                program.digest(),
                "candidate-synthesizer",
                1,
                1,
            ).validate(),
            BeanDescriptor(
                verifier_spec,
                verifier_identity,
                "independent-verifier",
                1,
                1,
            ).validate(),
            BeanDescriptor(
                observer_spec,
                observer_identity,
                "independent-observer",
                1,
                1,
            ).validate(),
        )
        composition = self._composer.compose(
            request=request,
            candidates=descriptors,
        )
        specs = {
            spec.bean_id: spec
            for spec in (generated, verifier_spec, observer_spec)
        }
        mosaic = self._mosaic.form(
            mosaic_id=f"mosaic:{problem.problem_id}",
            composition=composition,
            specs=specs,
            evidence_refs=(gap.digest(), need.digest(), composition.digest()),
        )
        mosaic = advance_mosaic(
            mosaic,
            "ATTEST",
            evidence_refs=(
                generated.spec_digest(),
                program.digest(),
                builder_identity,
                verifier_identity,
                observer_identity,
            ),
        )
        built = BeanCandidate(
            candidate_id=(
                f"b0-candidate:{problem.problem_id}:{program.digest()}"
            ),
            bean_id=generated.bean_id,
            spec_digest=generated.spec_digest(),
            implementation_digest=program.digest(),
            builder_identity_digest=builder_identity,
            build_evidence_refs=(
                gap.digest(),
                need.digest(),
                program.digest(),
                composition.digest(),
            ),
        ).validate()
        mosaic = advance_mosaic(
            mosaic,
            "OPERATE",
            evidence_refs=(built.digest(), program.digest()),
        )
        observed = []
        failures = []
        for ex in problem.holdout_examples:
            actual = _reference_execute(program, ex.input_value)
            observed.append((ex.example_id, actual, ex.expected_output))
            if actual != ex.expected_output:
                failures.append(ex.example_id)
        holdout_digest = _digest(
            b"LION/B0-HOLDOUT-RESULT/1", tuple(observed)
        )
        mosaic = advance_mosaic(
            mosaic,
            "OBSERVE",
            evidence_refs=(holdout_digest, observer_identity),
        )
        verified_digest = ""
        status = "PASS"
        failure_reason = ""
        if failures:
            status = "FALSIFIED"
            failure_reason = "holdout mismatch:" + ",".join(sorted(failures))
            reconcile_ref = _digest(
                b"LION/B0-RECONCILIATION/1",
                {
                    "status": status,
                    "failures": tuple(sorted(failures)),
                    "candidate": built.digest(),
                },
            )
        else:
            verified = verify_candidate(
                candidate=built,
                spec=generated,
                verifier_identity_digests=(verifier_identity,),
                verification_evidence_refs=(
                    holdout_digest,
                    verifier_identity,
                ),
                acceptance_evidence_refs=tuple(
                    f"holdout:{ex.digest()}"
                    for ex in problem.holdout_examples
                ),
            )
            verified_digest = verified.digest()
            reconcile_ref = _digest(
                b"LION/B0-RECONCILIATION/1",
                {
                    "status": status,
                    "candidate": verified_digest,
                    "holdout": holdout_digest,
                },
            )
        mosaic = advance_mosaic(
            mosaic,
            "RECONCILE",
            evidence_refs=(reconcile_ref,),
        )
        mosaic = advance_mosaic(
            mosaic,
            "DISSOLVE",
            evidence_refs=(reconcile_ref,),
            reason="candidate-only generativity experiment terminal",
        )
        return GenerativityTerminalEvidence(
            problem_id=problem.problem_id,
            problem_family=problem.problem_family,
            problem_digest=problem.digest(),
            workflow_type=_WORKFLOW_TYPE,
            gap_digest=gap.digest(),
            capability_need_digest=need.digest(),
            resolution_disposition=resolution.disposition,
            generated_spec_digest=generated.spec_digest(),
            synthesized_program_digest=program.digest(),
            composition_digest=composition.digest(),
            dissolved_mosaic_digest=mosaic.digest(),
            built_candidate_digest=built.digest(),
            verified_candidate_digest=verified_digest,
            training_evidence_digest=training_digest,
            holdout_evidence_digest=holdout_digest,
            status=status,
            failure_reason=failure_reason,
        ).validate()
