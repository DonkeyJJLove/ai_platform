from __future__ import annotations

from dataclasses import dataclass, asdict, replace
from hashlib import sha256
import ast
import json
import re
from pathlib import PurePosixPath
from typing import Mapping, Tuple

from .gap import GapRecord, canonical_target_gaps

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_PLANES = frozenset({"AS_IS", "CANDIDATE"})
_FRESHNESS = frozenset({"CURRENT", "STALE"})
_IMPL = frozenset({"IMPLEMENTED", "UNKNOWN"})


class CurrentTruthError(ValueError):
    pass


def _sha_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _canonical_digest(domain: bytes, payload: object) -> str:
    return sha256(
        domain
        + b"\0"
        + json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, order=True)
class TruthSourceSpec:
    target_id: str
    source_path: str
    symbol: str = ""
    literal_token: str = ""

    def validate(self) -> "TruthSourceSpec":
        if not self.target_id.strip() or not self.source_path.strip():
            raise CurrentTruthError("truth source target_id/source_path required")
        if bool(self.symbol) == bool(self.literal_token):
            raise CurrentTruthError("truth source requires exactly one symbol or literal_token")
        if PurePosixPath(self.source_path).is_absolute() or ".." in PurePosixPath(self.source_path).parts:
            raise CurrentTruthError("truth source path must be repository-relative")
        return self


@dataclass(frozen=True, order=True)
class TruthImplementationRecord:
    target_id: str
    target_status: str
    implementation_status: str
    plane: str
    source_path: str
    symbol_or_token: str
    source_digest: str
    evidence_class: str
    rationale: str

    def validate(self) -> "TruthImplementationRecord":
        if not self.target_id.strip() or not self.source_path.strip() or not self.symbol_or_token.strip():
            raise CurrentTruthError("truth implementation identity incomplete")
        if self.implementation_status not in _IMPL:
            raise CurrentTruthError("truth implementation status invalid")
        if self.plane not in _PLANES:
            raise CurrentTruthError("truth plane invalid")
        if not _SHA64.fullmatch(self.source_digest):
            raise CurrentTruthError("truth source_digest must be sha256")
        if self.evidence_class != "LIVE_CODE":
            raise CurrentTruthError("truth implementation requires LIVE_CODE evidence")
        if not self.rationale.strip():
            raise CurrentTruthError("truth implementation rationale required")
        return self


@dataclass(frozen=True)
class CurrentTruthProjection:
    repository: str
    baseline_head: str
    baseline_tree: str
    candidate_head: str
    candidate_tree: str
    expected_head: str
    expected_tree: str
    freshness: str
    target_gap_digest: str
    implementations: Tuple[TruthImplementationRecord, ...]
    source_backed_target_only_ids: Tuple[str, ...]
    unresolved_unknown_target_ids: Tuple[str, ...]
    candidate_delta_ids: Tuple[str, ...]
    as_is_ids: Tuple[str, ...]
    authority_effect: bool
    repository_effect: bool
    projection_digest: str = ""

    def validate(self) -> "CurrentTruthProjection":
        if not self.repository.strip():
            raise CurrentTruthError("repository required")
        for name in (
            "baseline_head", "baseline_tree", "candidate_head", "candidate_tree",
            "expected_head", "expected_tree",
        ):
            if not _SHA40.fullmatch(getattr(self, name)):
                raise CurrentTruthError(f"{name} must be sha40")
        if self.freshness not in _FRESHNESS:
            raise CurrentTruthError("truth freshness invalid")
        exact = self.candidate_head == self.expected_head and self.candidate_tree == self.expected_tree
        if (self.freshness == "CURRENT") != exact:
            raise CurrentTruthError("CURRENT truth requires exact candidate HEAD/TREE")
        if not _SHA64.fullmatch(self.target_gap_digest):
            raise CurrentTruthError("target_gap_digest invalid")
        if type(self.implementations) is not tuple:
            raise CurrentTruthError("implementations must be tuple")
        seen = set()
        for row in self.implementations:
            row.validate()
            if row.target_id in seen:
                raise CurrentTruthError("duplicate implementation target")
            seen.add(row.target_id)
        for name in (
            "source_backed_target_only_ids", "unresolved_unknown_target_ids",
            "candidate_delta_ids", "as_is_ids",
        ):
            value = getattr(self, name)
            if type(value) is not tuple or len(set(value)) != len(value):
                raise CurrentTruthError(f"{name} must be unique tuple")
        if set(self.candidate_delta_ids) & set(self.as_is_ids):
            raise CurrentTruthError("AS_IS/CANDIDATE overlap")
        if set(self.candidate_delta_ids) | set(self.as_is_ids) != seen:
            raise CurrentTruthError("truth plane coverage mismatch")
        if self.authority_effect or self.repository_effect:
            raise CurrentTruthError("truth projection cannot carry effects")
        if self.projection_digest:
            expected = _canonical_digest(b"LION/CURRENT-TRUTH-PROJECTION/1", self._payload())
            if self.projection_digest != expected:
                raise CurrentTruthError("truth projection digest mismatch")
        return self

    def _payload(self) -> dict:
        data = asdict(self)
        data.pop("projection_digest", None)
        return data

    def sealed(self) -> "CurrentTruthProjection":
        self.validate()
        if self.projection_digest:
            return self
        digest = _canonical_digest(b"LION/CURRENT-TRUTH-PROJECTION/1", self._payload())
        return replace(self, projection_digest=digest).validate()

    def digest(self) -> str:
        self.validate()
        if not self.projection_digest:
            raise CurrentTruthError("unsealed truth projection")
        return self.projection_digest


def canonical_truth_source_specs() -> Tuple[TruthSourceSpec, ...]:
    return tuple(
        spec.validate()
        for spec in (
            TruthSourceSpec("GoalContract", "cyber_lion/contracts/evolutionary_state.py", symbol="GoalContract"),
            TruthSourceSpec("WorldSnapshot", "cyber_lion/contracts/evolutionary_state.py", symbol="WorldSnapshot"),
            TruthSourceSpec("SystemSnapshot", "cyber_lion/contracts/evolutionary_state.py", symbol="SystemSnapshot"),
            TruthSourceSpec("Gap", "cyber_lion/contracts/evolutionary_state.py", symbol="Gap"),
            TruthSourceSpec("BeanSpec", "cyber_lion/contracts/bean.py", symbol="BeanSpec"),
            TruthSourceSpec("BeanCandidate", "cyber_lion/contracts/bean_candidate.py", symbol="BeanCandidate"),
            TruthSourceSpec("BeanInstance", "cyber_lion/contracts/bean.py", symbol="BeanInstance"),
            TruthSourceSpec("CompositionContract", "cyber_lion/contracts/bean_composition.py", symbol="CompositionContract"),
            TruthSourceSpec("CompositionEngine", "cyber_lion/enterprise/bean_composition.py", symbol="CompositionEngine"),
            TruthSourceSpec(
                "ActionSpec", "cyber_lion/contracts/v1/action_spec.schema.json",
                literal_token="lion://schemas/action-spec/v1.3-candidate",
            ),
            TruthSourceSpec("LCMS", "cyber_lion/lcms.py", symbol="parse_lcms"),
            TruthSourceSpec("ReadonlyProcessAdapter", "cyber_lion/readonly_process_exec.py", symbol="ReadonlyProcessAdapter"),
            TruthSourceSpec("HybridRouter", "cyber_lion/hybrid_router.py", symbol="HybridRouter"),
            TruthSourceSpec("PhysicalActionSpec", "cyber_lion/physical_action_simulation.py", symbol="PhysicalActionSpec"),
        )
    )


def _source_proves(spec: TruthSourceSpec, text: str) -> bool:
    spec.validate()
    if not isinstance(text, str):
        raise CurrentTruthError("truth source must be text")
    if spec.symbol:
        if PurePosixPath(spec.source_path).suffix != ".py":
            raise CurrentTruthError("symbol proof requires python source")
        try:
            tree = ast.parse(text, filename=spec.source_path)
        except SyntaxError as exc:
            raise CurrentTruthError(f"truth source is not parseable: {spec.source_path}") from exc
        names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        return spec.symbol in names
    return spec.literal_token in text


def _target_digest(targets: Tuple[GapRecord, ...]) -> str:
    payload = [asdict(row.validate()) for row in targets]
    return _canonical_digest(b"LION/CANONICAL-TARGET-GAPS/1", payload)


def build_current_truth_projection(
    *,
    repository: str,
    baseline_head: str,
    baseline_tree: str,
    candidate_head: str,
    candidate_tree: str,
    expected_head: str,
    expected_tree: str,
    baseline_sources: Mapping[str, str],
    candidate_sources: Mapping[str, str],
    targets: Tuple[GapRecord, ...] | None = None,
    specs: Tuple[TruthSourceSpec, ...] | None = None,
) -> CurrentTruthProjection:
    targets = canonical_target_gaps() if targets is None else targets
    specs = canonical_truth_source_specs() if specs is None else specs
    if type(targets) is not tuple or type(specs) is not tuple:
        raise CurrentTruthError("truth targets/specs must be immutable tuples")
    target_by_id = {row.target_id: row.validate() for row in targets}
    if len(target_by_id) != len(targets):
        raise CurrentTruthError("duplicate target gap id")
    implementations = []
    candidate_ids = []
    as_is_ids = []
    for spec in specs:
        spec.validate()
        text = candidate_sources.get(spec.source_path)
        if text is None:
            continue
        if not _source_proves(spec, text):
            raise CurrentTruthError(f"source binding missing: {spec.target_id}:{spec.source_path}")
        digest = _sha_text(text)
        baseline_text = baseline_sources.get(spec.source_path)
        baseline_same = (
            baseline_text is not None
            and _source_proves(spec, baseline_text)
            and _sha_text(baseline_text) == digest
        )
        plane = "AS_IS" if baseline_same else "CANDIDATE"
        target_status = target_by_id[spec.target_id].status if spec.target_id in target_by_id else "UNKNOWN"
        record = TruthImplementationRecord(
            target_id=spec.target_id,
            target_status=target_status,
            implementation_status="IMPLEMENTED",
            plane=plane,
            source_path=spec.source_path,
            symbol_or_token=spec.symbol or spec.literal_token,
            source_digest=digest,
            evidence_class="LIVE_CODE",
            rationale="exact source bytes contain the required canonical symbol/token",
        ).validate()
        implementations.append(record)
        (as_is_ids if plane == "AS_IS" else candidate_ids).append(spec.target_id)

    impl_ids = {row.target_id for row in implementations}
    source_backed_target_only = tuple(
        sorted(
            row.target_id
            for row in targets
            if row.status == "TARGET_ONLY"
            and row.target_id in impl_ids
            and not any(
                impl.target_id == row.target_id and impl.implementation_status == "IMPLEMENTED"
                for impl in implementations
            )
        )
    )
    unresolved_unknown = tuple(
        sorted(row.target_id for row in targets if row.status == "UNKNOWN" and row.target_id not in impl_ids)
    )
    freshness = "CURRENT" if candidate_head == expected_head and candidate_tree == expected_tree else "STALE"
    projection = CurrentTruthProjection(
        repository=repository,
        baseline_head=baseline_head,
        baseline_tree=baseline_tree,
        candidate_head=candidate_head,
        candidate_tree=candidate_tree,
        expected_head=expected_head,
        expected_tree=expected_tree,
        freshness=freshness,
        target_gap_digest=_target_digest(targets),
        implementations=tuple(sorted(implementations)),
        source_backed_target_only_ids=source_backed_target_only,
        unresolved_unknown_target_ids=unresolved_unknown,
        candidate_delta_ids=tuple(sorted(candidate_ids)),
        as_is_ids=tuple(sorted(as_is_ids)),
        authority_effect=False,
        repository_effect=False,
    )
    return projection.sealed()
