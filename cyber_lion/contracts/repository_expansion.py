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
    expected_head: str
    expected_tree: str

    def validate(self) -> "RegisteredRepository":
        _require_repository(self.repository)
        _require_identifier(self.default_branch, "default_branch")
        _require_sha40(self.expected_head, "expected_head")
        _require_sha40(self.expected_tree, "expected_tree")
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
        value["known_preexisting_failures"] = sorted(self.known_preexisting_failures)
        value["dependencies"] = sorted(self.dependencies)
        value["dependents"] = sorted(self.dependents)
        value["public_contracts"] = sorted(self.public_contracts)
        value["security_boundaries"] = sorted(self.security_boundaries)
        value["evidence"] = [
            item.canonical_dict()
            for item in sorted(self.evidence, key=lambda item: item.evidence_id)
        ]
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

        pin_by_repo = {
            item.repository: (item.default_branch, item.expected_head, item.expected_tree)
            for item in registered
        }
        for observation in observations:
            default_branch, expected_head, expected_tree = pin_by_repo[observation.repository]
            if observation.branch != default_branch:
                raise RepositoryExpansionContractError("observed branch differs from registered default")
            if observation.head != expected_head:
                raise RepositoryExpansionContractError("observed head differs from registered expected head")
            if observation.tree != expected_tree:
                raise RepositoryExpansionContractError("observed tree differs from registered expected tree")

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
        registered = sorted(self.registered, key=lambda item: item.repository)
        observations = sorted(self.observations, key=lambda item: item.repository)
        edges = sorted(
            self.edges,
            key=lambda item: (
                item.source,
                item.target,
                item.relation,
                item.contract or "",
                item.version_assumption or "",
                item.failure_mode,
                item.security_impact,
                item.test_coverage,
                item.evidence,
            ),
        )
        return {
            "schema_version": self.schema_version,
            "baseline_id": self.baseline_id,
            "registered": [item.canonical_dict() for item in registered],
            "observations": [item.canonical_dict() for item in observations],
            "edges": [item.canonical_dict() for item in edges],
        }

    def baseline_digest(self) -> str:
        return digest(self.canonical_dict(), b"LION/FLEET-BASELINE/1\0")

    def gate0(self) -> Gate0Decision:
        self.validate()
        failures_classified = all(
            observation.failure_classification != "UNKNOWN"
            for observation in self.observations
        )
        decision = Gate0Decision(
            all_repositories_inventoried=True,
            current_failures_separated_from_new_failures=failures_classified,
            cross_repo_dependency_graph_created=True,
            result="PASS" if failures_classified else "FAIL",
            baseline_digest=self.baseline_digest(),
        )
        return decision.validate()


REGISTRY_SCHEMA_VERSION = "1.0.0"
REGISTRY_MAX_BYTES = 1_048_576
_REGISTRY_ROOT_KEYS = frozenset({"schema_version", "generated_from", "repositories"})
_REGISTRY_MEMBER_KEYS = frozenset({
    "id", "default_branch", "roles", "layers", "maturity", "disposition",
})


def _strict_registry_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RepositoryExpansionContractError("duplicate registry JSON key")
        result[key] = value
    return result


def _registry_text(value: object, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or "\x00" in value
        or len(value) > 512
    ):
        raise RepositoryExpansionContractError(f"{name} invalid")
    return value


def _registry_string_list(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise RepositoryExpansionContractError(f"{name} must be a non-empty array")
    items = tuple(_registry_text(item, name) for item in value)
    if len(items) != len(set(items)):
        raise RepositoryExpansionContractError(f"{name} contains duplicates")
    return items


@dataclass(frozen=True)
class RegistryMember:
    repository: str
    default_branch: str

    def validate(self) -> "RegistryMember":
        _require_repository(self.repository)
        _require_identifier(self.default_branch, "default_branch")
        return self

    def canonical_dict(self) -> dict[str, str]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class RepositoryPinObservation:
    repository: str
    default_branch: str
    head: str
    tree: str
    manifest_present: bool
    source_ref: str

    def validate(self) -> "RepositoryPinObservation":
        _require_repository(self.repository)
        _require_identifier(self.default_branch, "default_branch")
        _require_sha40(self.head, "head")
        _require_sha40(self.tree, "tree")
        if not isinstance(self.manifest_present, bool):
            raise RepositoryExpansionContractError("manifest_present must be bool")
        _registry_text(self.source_ref, "source_ref")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class FleetRegistryPinSnapshot:
    schema_version: str
    registry_digest: str
    members: tuple[RegistryMember, ...]
    observations: tuple[RepositoryPinObservation, ...]

    def validate(self) -> "FleetRegistryPinSnapshot":
        if self.schema_version != SCHEMA_VERSION:
            raise RepositoryExpansionContractError("pin snapshot schema_version invalid")
        _require_sha256(self.registry_digest, "registry_digest")
        if type(self.members) is not tuple or not self.members:
            raise RepositoryExpansionContractError("registry members required")
        if type(self.observations) is not tuple:
            raise RepositoryExpansionContractError("pin observations must be tuple")

        members = tuple(item.validate() for item in self.members)
        observations = tuple(item.validate() for item in self.observations)
        member_ids = [item.repository for item in members]
        observation_ids = [item.repository for item in observations]
        if len(member_ids) != len(set(member_ids)):
            raise RepositoryExpansionContractError("duplicate registry member")
        if len(observation_ids) != len(set(observation_ids)):
            raise RepositoryExpansionContractError("duplicate pin observation")
        if set(member_ids) != set(observation_ids):
            raise RepositoryExpansionContractError("pin observations do not exactly cover registry")

        branch_by_repository = {
            member.repository: member.default_branch for member in members
        }
        for observation in observations:
            if observation.default_branch != branch_by_repository[observation.repository]:
                raise RepositoryExpansionContractError("pin observation default branch substitution")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "registry_digest": self.registry_digest,
            "members": [
                item.canonical_dict()
                for item in sorted(self.members, key=lambda item: item.repository)
            ],
            "observations": [
                item.canonical_dict()
                for item in sorted(self.observations, key=lambda item: item.repository)
            ],
        }

    def snapshot_digest(self) -> str:
        return digest(
            self.canonical_dict(),
            b"LION/FLEET-REGISTRY-PIN-SNAPSHOT/1\0",
        )

    def registered_repositories(self) -> tuple[RegisteredRepository, ...]:
        self.validate()
        by_repository = {item.repository: item for item in self.observations}
        return tuple(
            RegisteredRepository(
                repository=member.repository,
                default_branch=member.default_branch,
                expected_head=by_repository[member.repository].head,
                expected_tree=by_repository[member.repository].tree,
            ).validate()
            for member in sorted(self.members, key=lambda item: item.repository)
        )


def _parse_registry_payload(payload: bytes) -> tuple[dict[str, Any], tuple[RegistryMember, ...]]:
    if type(payload) is not bytes or not payload or len(payload) > REGISTRY_MAX_BYTES:
        raise RepositoryExpansionContractError("registry payload size/type invalid")
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_registry_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RepositoryExpansionContractError("registry JSON invalid") from exc
    if not isinstance(value, dict) or set(value) != _REGISTRY_ROOT_KEYS:
        raise RepositoryExpansionContractError("registry root shape invalid")
    if value.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise RepositoryExpansionContractError("registry schema_version invalid")
    _registry_text(value.get("generated_from"), "generated_from")
    repositories = value.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise RepositoryExpansionContractError("registry repositories required")

    members: list[RegistryMember] = []
    for item in repositories:
        if not isinstance(item, dict) or set(item) != _REGISTRY_MEMBER_KEYS:
            raise RepositoryExpansionContractError("registry member shape invalid")
        repository = _require_repository(item.get("id"), "registry repository")
        default_branch = _require_identifier(item.get("default_branch"), "default_branch")
        _registry_string_list(item.get("roles"), "roles")
        _registry_string_list(item.get("layers"), "layers")
        _registry_text(item.get("maturity"), "maturity")
        _registry_string_list(item.get("disposition"), "disposition")
        members.append(RegistryMember(repository, default_branch).validate())

    ids = [item.repository for item in members]
    if len(ids) != len(set(ids)):
        raise RepositoryExpansionContractError("duplicate repository in registry")
    return value, tuple(sorted(members, key=lambda item: item.repository))


def registry_semantic_digest(payload: bytes) -> str:
    value, _ = _parse_registry_payload(payload)
    return digest(value, b"LION/FLEET-REGISTRY/1\0")


def materialize_registry_pin_snapshot(
    registry_payload: bytes,
    observations: tuple[RepositoryPinObservation, ...],
) -> FleetRegistryPinSnapshot:
    value, members = _parse_registry_payload(registry_payload)
    snapshot = FleetRegistryPinSnapshot(
        schema_version=SCHEMA_VERSION,
        registry_digest=digest(value, b"LION/FLEET-REGISTRY/1\0"),
        members=members,
        observations=observations,
    )
    return snapshot.validate()
