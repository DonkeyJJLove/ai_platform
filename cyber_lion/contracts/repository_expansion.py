"""Fail-closed contracts for processual multi-repository expansion.

The contract separates an observed repository baseline from a claim that the
repository is healthy. PASS is representable only with literal command/exit
code evidence. UNKNOWN is first-class and never upgrades to PASS implicitly.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any

SCHEMA_VERSION = "1.0.0"
RESULTS = frozenset({"PASS", "FAIL", "UNKNOWN"})
FAILURE_CLASSIFICATIONS = frozenset({"NONE", "KNOWN_PREEXISTING_FAILURES", "UNKNOWN"})
FLEET_ROLES = frozenset({"SPECTRA", "TIGER", "LION"})
EVIDENCE_SCOPES = frozenset({"BUILD", "TEST", "CONTRACT", "NEGATIVE", "MUTATION", "SECURITY", "REGRESSION", "CROSS_REPO", "HYGIENE", "OTHER"})
EDGE_RELATIONS = frozenset({
    "IMPORTS", "CALLS", "BUILDS", "TESTS", "DEPLOYS", "CONFIGURES", "SIGNS",
    "PUBLISHES", "OBSERVES", "AUTHORIZES", "GENERATES", "CONSUMES",
    "SHARES_SCHEMA_WITH",
})
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9._:/-]{1,160}$")


class RepositoryExpansionContractError(ValueError):
    pass


def canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RepositoryExpansionContractError("value is not strict JSON") from exc


def digest(value: object, domain: bytes) -> str:
    return sha256(domain + canonical_json(value)).hexdigest()


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RepositoryExpansionContractError(f"{name} must be non-empty text")
    return value


def _require_identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise RepositoryExpansionContractError(f"{name} invalid")
    return value


def _require_repository(value: object, name: str = "repository") -> str:
    if not isinstance(value, str) or _REPOSITORY.fullmatch(value) is None:
        raise RepositoryExpansionContractError(f"{name} invalid")
    return value


def _require_sha40(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA40.fullmatch(value) is None:
        raise RepositoryExpansionContractError(f"{name} must be lowercase sha40")
    return value


def _require_sha256(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise RepositoryExpansionContractError(f"{name} must be sha256")
    return value


def _require_unique_strings(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    if type(values) is not tuple or any(not isinstance(item, str) or not item for item in values):
        raise RepositoryExpansionContractError(f"{name} must be tuple[str, ...]")
    if len(values) != len(set(values)):
        raise RepositoryExpansionContractError(f"{name} contains duplicates")
    return values


@dataclass(frozen=True)
class VerificationEvidence:
    evidence_id: str
    actor: str
    scope: str
    result: str
    command: str | None
    exit_code: int | None
    source_ref: str | None

    def validate(self) -> "VerificationEvidence":
        _require_identifier(self.evidence_id, "evidence_id")
        if self.actor not in FLEET_ROLES:
            raise RepositoryExpansionContractError("evidence actor outside fleet role set")
        if self.scope not in EVIDENCE_SCOPES:
            raise RepositoryExpansionContractError("evidence scope invalid")
        if self.result not in RESULTS:
            raise RepositoryExpansionContractError("evidence result invalid")

        if self.result in {"PASS", "FAIL"}:
            _require_text(self.command, "command")
            if isinstance(self.exit_code, bool) or not isinstance(self.exit_code, int):
                raise RepositoryExpansionContractError("executed evidence requires integer exit_code")
            _require_text(self.source_ref, "source_ref")
            if self.result == "PASS" and self.exit_code != 0:
                raise RepositoryExpansionContractError("PASS requires exit_code=0")
            if self.result == "FAIL" and self.exit_code == 0:
                raise RepositoryExpansionContractError("FAIL requires non-zero exit_code")
        else:
            if self.exit_code is not None:
                raise RepositoryExpansionContractError("UNKNOWN cannot claim an exit_code")
            if self.command is not None and not isinstance(self.command, str):
                raise RepositoryExpansionContractError("UNKNOWN command must be text or null")
            if self.source_ref is not None and not isinstance(self.source_ref, str):
                raise RepositoryExpansionContractError("UNKNOWN source_ref must be text or null")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class RegisteredRepository:
    repository: str
    default_branch: str

    def validate(self) -> "RegisteredRepository":
        _require_repository(self.repository)
        _require_identifier(self.default_branch, "default_branch")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class RepositoryBaseline:
    schema_version: str
    repository: str
    branch: str
    head: str
    tree: str
    dirty: bool | None
    build_result: str
    test_result: str
    failure_classification: str
    known_preexisting_failures: tuple[str, ...]
    dependencies: tuple[str, ...]
    dependents: tuple[str, ...]
    public_contracts: tuple[str, ...]
    security_boundaries: tuple[str, ...]
    manifest_present: bool
    evidence: tuple[VerificationEvidence, ...]

    def validate(self) -> "RepositoryBaseline":
        if self.schema_version != SCHEMA_VERSION:
            raise RepositoryExpansionContractError("baseline schema_version invalid")
        _require_repository(self.repository)
        _require_identifier(self.branch, "branch")
        _require_sha40(self.head, "head")
        _require_sha40(self.tree, "tree")
        if self.dirty is not None and not isinstance(self.dirty, bool):
            raise RepositoryExpansionContractError("dirty must be bool or null")
        if self.build_result not in RESULTS or self.test_result not in RESULTS:
            raise RepositoryExpansionContractError("baseline result invalid")
        if self.failure_classification not in FAILURE_CLASSIFICATIONS:
            raise RepositoryExpansionContractError("failure classification invalid")
        _require_unique_strings(self.known_preexisting_failures, "known_preexisting_failures")
        for name, values in (
            ("dependencies", self.dependencies),
            ("dependents", self.dependents),
            ("public_contracts", self.public_contracts),
            ("security_boundaries", self.security_boundaries),
        ):
            _require_unique_strings(values, name)
        if not isinstance(self.manifest_present, bool):
            raise RepositoryExpansionContractError("manifest_present must be bool")
        if type(self.evidence) is not tuple:
            raise RepositoryExpansionContractError("evidence must be tuple")
        validated = tuple(item.validate() for item in self.evidence)
        ids = [item.evidence_id for item in validated]
        if len(ids) != len(set(ids)):
            raise RepositoryExpansionContractError("duplicate evidence_id")

        if self.build_result == "PASS" and not any(
            item.result == "PASS" and item.scope == "BUILD" for item in validated
        ):
            raise RepositoryExpansionContractError("build PASS lacks literal BUILD evidence")
        if self.build_result == "FAIL" and not any(
            item.result == "FAIL" and item.scope == "BUILD" for item in validated
        ):
            raise RepositoryExpansionContractError("build FAIL lacks literal BUILD evidence")
        if self.test_result == "PASS" and not any(
            item.result == "PASS" and item.scope in {"TEST", "CONTRACT", "NEGATIVE", "MUTATION", "SECURITY", "REGRESSION"}
            for item in validated
        ):
            raise RepositoryExpansionContractError("test PASS lacks literal test evidence")
        if self.test_result == "FAIL" and not any(
            item.result == "FAIL" and item.scope in {"TEST", "CONTRACT", "NEGATIVE", "MUTATION", "SECURITY", "REGRESSION"}
            for item in validated
        ):
            raise RepositoryExpansionContractError("test FAIL lacks literal test evidence")
        if self.failure_classification == "NONE" and self.known_preexisting_failures:
            raise RepositoryExpansionContractError("NONE cannot carry preexisting failures")
        if self.failure_classification == "KNOWN_PREEXISTING_FAILURES" and not self.known_preexisting_failures:
            raise RepositoryExpansionContractError("known failures require literal entries")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        value = asdict(self)
        value["evidence"] = [item.canonical_dict() for item in self.evidence]
        return value

    def evidence_hash(self) -> str:
        return digest(self.canonical_dict(), b"LION/REPOSITORY-BASELINE/1\0")


@dataclass(frozen=True)
class RepositoryDependencyEdge:
    source: str
    target: str
    relation: str
    contract: str | None
    version_assumption: str | None
    failure_mode: str
    security_impact: str
    test_coverage: str
    evidence: str

    def validate(self) -> "RepositoryDependencyEdge":
        _require_repository(self.source, "source")
        _require_repository(self.target, "target")
        if self.source == self.target:
            raise RepositoryExpansionContractError("self dependency denied")
        if self.relation not in EDGE_RELATIONS:
            raise RepositoryExpansionContractError("dependency relation invalid")
        if self.contract is not None:
            _require_text(self.contract, "contract")
        if self.version_assumption is not None:
            _require_text(self.version_assumption, "version_assumption")
        for name, value in (
            ("failure_mode", self.failure_mode),
            ("security_impact", self.security_impact),
            ("test_coverage", self.test_coverage),
            ("evidence", self.evidence),
        ):
            _require_text(value, name)
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class Gate0Decision:
    all_repositories_inventoried: bool
    current_failures_separated_from_new_failures: bool
    cross_repo_dependency_graph_created: bool
    result: str
    baseline_digest: str

    def validate(self) -> "Gate0Decision":
        for name in (
            "all_repositories_inventoried",
            "current_failures_separated_from_new_failures",
            "cross_repo_dependency_graph_created",
        ):
            if not isinstance(getattr(self, name), bool):
                raise RepositoryExpansionContractError(f"{name} must be bool")
        expected = "PASS" if all((
            self.all_repositories_inventoried,
            self.current_failures_separated_from_new_failures,
            self.cross_repo_dependency_graph_created,
        )) else "FAIL"
        if self.result != expected:
            raise RepositoryExpansionContractError("Gate0 result inconsistent with predicates")
        _require_sha256(self.baseline_digest, "baseline_digest")
        return self


@dataclass(frozen=True)
class FleetBaseline:
    schema_version: str
    baseline_id: str
    registered: tuple[RegisteredRepository, ...]
    observations: tuple[RepositoryBaseline, ...]
    edges: tuple[RepositoryDependencyEdge, ...]

    def validate(self) -> "FleetBaseline":
        if self.schema_version != SCHEMA_VERSION:
            raise RepositoryExpansionContractError("fleet schema_version invalid")
        _require_identifier(self.baseline_id, "baseline_id")
        if type(self.registered) is not tuple or not self.registered:
            raise RepositoryExpansionContractError("registered repositories required")
        if type(self.observations) is not tuple:
            raise RepositoryExpansionContractError("observations must be tuple")
        if type(self.edges) is not tuple:
            raise RepositoryExpansionContractError("edges must be tuple")

        registered = tuple(item.validate() for item in self.registered)
        observations = tuple(item.validate() for item in self.observations)
        reg_ids = [item.repository for item in registered]
        obs_ids = [item.repository for item in observations]
        if len(reg_ids) != len(set(reg_ids)):
            raise RepositoryExpansionContractError("duplicate registered repository")
        if len(obs_ids) != len(set(obs_ids)):
            raise RepositoryExpansionContractError("duplicate repository observation")
        if set(reg_ids) != set(obs_ids):
            raise RepositoryExpansionContractError("repository inventory does not exactly cover registry")

        branch_by_repo = {item.repository: item.default_branch for item in registered}
        for observation in observations:
            if observation.branch != branch_by_repo[observation.repository]:
                raise RepositoryExpansionContractError("observed branch differs from registered default")

        edge_keys: set[tuple[str, str, str]] = set()
        known = set(reg_ids)
        outgoing: dict[str, set[str]] = {repo: set() for repo in known}
        incoming: dict[str, set[str]] = {repo: set() for repo in known}
        for edge in self.edges:
            edge.validate()
            if edge.source not in known or edge.target not in known:
                raise RepositoryExpansionContractError("dependency edge escapes registered fleet")
            key = (edge.source, edge.target, edge.relation)
            if key in edge_keys:
                raise RepositoryExpansionContractError("duplicate dependency edge")
            edge_keys.add(key)
            outgoing[edge.source].add(edge.target)
            incoming[edge.target].add(edge.source)

        for observation in observations:
            if set(observation.dependencies) != outgoing[observation.repository]:
                raise RepositoryExpansionContractError("baseline dependencies disagree with repository graph")
            if set(observation.dependents) != incoming[observation.repository]:
                raise RepositoryExpansionContractError("baseline dependents disagree with repository graph")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "baseline_id": self.baseline_id,
            "registered": [item.canonical_dict() for item in self.registered],
            "observations": [item.canonical_dict() for item in self.observations],
            "edges": [item.canonical_dict() for item in self.edges],
        }

    def baseline_digest(self) -> str:
        return digest(self.canonical_dict(), b"LION/FLEET-BASELINE/1\0")

    def gate0(self) -> Gate0Decision:
        self.validate()
        decision = Gate0Decision(
            all_repositories_inventoried=True,
            current_failures_separated_from_new_failures=True,
            cross_repo_dependency_graph_created=True,
            result="PASS",
            baseline_digest=self.baseline_digest(),
        )
        return decision.validate()
