"""Pure fail-closed evidence and admission brokers for host authority separation.

Primary evidence may be supplied as bytes/records, but it is never certified by those bytes alone.
Every production primary evidence class must carry a receipt signed by the pinned independent-origin
trust anchor.  This module has no signer, private key, callback verifier, network, filesystem,
SQLite, process, host, merge, deploy, or migration effect.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha1, sha256
import json
import re
from typing import Any

from cyber_lion.contracts.host_authority_separation import (
    BrokerPermit,
    CANONICAL_REPOSITORY,
    CANONICAL_REPOSITORY_PROVIDER,
    CANONICAL_SNAPSHOTTER_IDENTITY,
    CONTROL_PLANE_GROUP,
    DEPLOYER_USER,
    DeploymentReceipt,
    DeploymentRequest,
    ExternalAuthorityIdentity,
    HostAuthorityContractError,
    HostAuthorityObservation,
    HostAuthoritySeparationPlan,
    HostOperation,
    HostTransitionPlan,
    LIVE_DB_PATH,
    MIGRATOR_USER,
    MigrationReceipt,
    PRESERVED_TABLES,
    PROVISIONING_TABLES,
    PROVISIONING_TRIGGERS,
    RUNTIME_CODE_PATH,
    RUNTIME_USER,
    RUNNER_USER,
    SERVICE_ENV_PATH,
    SERVICE_UNIT_PATH,
    SNAPSHOT_DIR,
    SchemaMigrationRequest,
    SchemaObservation,
    SnapshotAttestation,
    TRUST_CLIENT_GROUP,
    TrustedRuntimeReadBinding,
)
from cyber_lion.contracts.independent_evidence_origin import IndependentEvidenceOriginReceipt
from cyber_lion.enterprise.authority_provisioning import authority_provisioning_schema_sql
from cyber_lion.enterprise.independent_evidence_origin import (
    CANDIDATE_TREE_PROVIDER,
    ORIGIN_CANDIDATE_TREE,
    ORIGIN_PRE_SCHEMA,
    ORIGIN_REPOSITORY_CURRENTNESS,
    ORIGIN_SNAPSHOT,
    SCHEMA_MANIFEST_PROVIDER,
    IndependentEvidenceOriginError,
    verify_independent_evidence_origin,
)


class HostAuthoritySeparationError(HostAuthorityContractError):
    pass


def _canon(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(domain: bytes, value: Any) -> str:
    return sha256(domain + _canon(value)).hexdigest()


def _utc(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception as exc:
        raise HostAuthoritySeparationError("timestamp invalid") from exc
    if parsed.tzinfo is None:
        raise HostAuthoritySeparationError("timestamp must be timezone-aware")


def _sha256_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise HostAuthoritySeparationError(f"{name} must be sha256")
    return value


def _bundle_digest(domain: bytes, *parts: bytes) -> str:
    h = sha256()
    h.update(domain)
    for part in parts:
        if type(part) is not bytes:
            raise HostAuthoritySeparationError("primary evidence bundle must be bytes")
        h.update(len(part).to_bytes(8, "big"))
        h.update(part)
    return h.hexdigest()


def _verify_origin(
    receipt: IndependentEvidenceOriginReceipt,
    *,
    kind: str,
    identity: str,
    object_digest: str,
    payload_digest: str,
) -> IndependentEvidenceOriginReceipt:
    try:
        return verify_independent_evidence_origin(
            receipt,
            observation_kind=kind,
            observed_object_identity=identity,
            observed_object_digest=object_digest,
            payload_digest=payload_digest,
        )
    except (IndependentEvidenceOriginError, ValueError) as exc:
        raise HostAuthoritySeparationError(str(exc)) from exc


def schema_sql_digest() -> str:
    return sha256(authority_provisioning_schema_sql().encode()).hexdigest()


CANONICAL_SCHEMA_SQL_SHA256 = "7e9f8873a4b5fb943f183d9546d1a9f08ed9ede19d73e55400dab7f6612a976b"
if schema_sql_digest() != CANONICAL_SCHEMA_SQL_SHA256:
    raise RuntimeError("canonical authority provisioning SQL digest drift")


def _production_path(path: str) -> bool:
    return (
        path.startswith("cyber_lion/")
        and path.endswith(".py")
        and "/tests/" not in f"/{path}"
    ) or (
        path.startswith(".github/workflows/")
        and path.endswith((".yml", ".yaml"))
    )


def _path(path: Any) -> str:
    if not isinstance(path, str) or not path or path.startswith("/") or "\x00" in path:
        raise HostAuthoritySeparationError("manifest path invalid")
    parts = path.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise HostAuthoritySeparationError("manifest path invalid")
    return path


def _mode(mode: Any) -> str:
    if mode not in {"100644", "100755", "120000"}:
        raise HostAuthoritySeparationError("manifest mode invalid")
    return mode


def _git_blob_sha(data: bytes) -> str:
    if type(data) is not bytes:
        raise HostAuthoritySeparationError("candidate file bytes required")
    return sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def _git_tree_sha(entries: tuple[tuple[str, str, str], ...]) -> str:
    root: dict[str, Any] = {}
    for path, mode, blob_sha in entries:
        _path(path)
        _mode(mode)
        if not re.fullmatch(r"[0-9a-f]{40}", blob_sha):
            raise HostAuthoritySeparationError("blob sha invalid")
        node = root
        parts = path.split("/")
        for part in parts[:-1]:
            current = node.get(part)
            if current is None:
                current = {}
                node[part] = current
            if not isinstance(current, dict):
                raise HostAuthoritySeparationError("manifest file/directory collision")
            node = current
        if parts[-1] in node:
            raise HostAuthoritySeparationError("manifest duplicate path")
        node[parts[-1]] = (mode, blob_sha)

    def emit(node: dict[str, Any]) -> str:
        rows: list[tuple[str, bool, str, str]] = []
        for name, value in node.items():
            if isinstance(value, dict):
                rows.append((name, True, "40000", emit(value)))
            else:
                rows.append((name, False, value[0], value[1]))
        rows.sort(key=lambda row: row[0] + ("/" if row[1] else ""))
        raw = b"".join(
            f"{mode} {name}\0".encode() + bytes.fromhex(oid)
            for name, _, mode, oid in rows
        )
        return sha1(f"tree {len(raw)}\0".encode() + raw).hexdigest()

    return emit(root)


def _candidate_tree_payload_digest(full_entries: tuple[tuple[str, str, str, str, int], ...]) -> str:
    return _digest(
        b"LION/CANDIDATE-TREE-PRIMARY-PAYLOAD/1\0",
        {"full_entries": full_entries},
    )


def _candidate_tree_object_digest(
    tree_sha: str,
    tracked_file_count: int,
    production_manifest_sha256: str,
    production_entry_count: int,
) -> str:
    return _digest(
        b"LION/CANDIDATE-TREE-OBSERVED-OBJECT/1\0",
        {
            "tree_sha": tree_sha,
            "tracked_file_count": tracked_file_count,
            "production_manifest_sha256": production_manifest_sha256,
            "production_entry_count": production_entry_count,
        },
    )


@dataclass(frozen=True)
class CandidateTreeEvidence:
    tree_sha: str
    tracked_file_count: int
    production_manifest_sha256: str
    production_entry_count: int
    provider_observation_id: str
    provider_instance_id: str
    full_entries: tuple[tuple[str, str, str, str, int], ...]
    origin_receipt: IndependentEvidenceOriginReceipt
    provenance_digest: str

    def validate(self) -> "CandidateTreeEvidence":
        if not re.fullmatch(r"[0-9a-f]{40}", self.tree_sha):
            raise HostAuthoritySeparationError("candidate tree evidence sha invalid")
        if type(self.full_entries) is not tuple or not self.full_entries:
            raise HostAuthoritySeparationError("candidate tree evidence empty")
        git_entries: list[tuple[str, str, str]] = []
        production: list[dict[str, Any]] = []
        for row in self.full_entries:
            if type(row) is not tuple or len(row) != 5:
                raise HostAuthoritySeparationError("candidate tree entry invalid")
            path, mode, blob_sha, byte_sha, size = row
            _path(path)
            _mode(mode)
            if (
                not re.fullmatch(r"[0-9a-f]{40}", blob_sha)
                or not re.fullmatch(r"[0-9a-f]{64}", byte_sha)
                or type(size) is not int
                or size < 0
            ):
                raise HostAuthoritySeparationError("candidate tree entry identity invalid")
            git_entries.append((path, mode, blob_sha))
            if _production_path(path):
                production.append(
                    {
                        "path": path,
                        "blob_sha": blob_sha,
                        "byte_sha256": byte_sha,
                        "size": size,
                        "mode": mode,
                    }
                )
        if len({row[0] for row in self.full_entries}) != len(self.full_entries):
            raise HostAuthoritySeparationError("candidate tree duplicate path")
        if _git_tree_sha(tuple(git_entries)) != self.tree_sha:
            raise HostAuthoritySeparationError("candidate tree reconstruction mismatch")
        manifest = sha256(
            b"LION/R9D8/EXACT-PRODUCTION-MANIFEST/1\0"
            + _canon(sorted(production, key=lambda row: row["path"]))
        ).hexdigest()
        if (
            manifest != self.production_manifest_sha256
            or len(production) != self.production_entry_count
            or len(self.full_entries) != self.tracked_file_count
        ):
            raise HostAuthoritySeparationError("candidate production manifest derivation mismatch")
        payload_digest = _candidate_tree_payload_digest(self.full_entries)
        object_digest = _candidate_tree_object_digest(
            self.tree_sha,
            self.tracked_file_count,
            manifest,
            self.production_entry_count,
        )
        receipt = _verify_origin(
            self.origin_receipt,
            kind=ORIGIN_CANDIDATE_TREE,
            identity=self.tree_sha,
            object_digest=object_digest,
            payload_digest=payload_digest,
        )
        if (
            self.provider_observation_id != receipt.observation_id
            or self.provider_instance_id != receipt.provider_instance_id
        ):
            raise HostAuthoritySeparationError("candidate tree provider observation mismatch")
        expected = _digest(
            b"LION/CANDIDATE-TREE-EVIDENCE/2\0",
            {
                "tree_sha": self.tree_sha,
                "tracked_file_count": self.tracked_file_count,
                "production_manifest_sha256": manifest,
                "production_entry_count": self.production_entry_count,
                "provider_observation_id": self.provider_observation_id,
                "provider_instance_id": self.provider_instance_id,
                "full_entries": self.full_entries,
                "origin_receipt_digest": receipt.digest(),
            },
        )
        if expected != self.provenance_digest:
            raise HostAuthoritySeparationError("candidate tree evidence digest mismatch")
        return self

    def digest(self) -> str:
        self.validate()
        return self.provenance_digest

    def origin_digest(self) -> str:
        self.validate()
        return self.origin_receipt.digest()

    def source_manifest_origin_digest(self) -> str:
        self.validate()
        return _digest(
            b"LION/SOURCE-MANIFEST-ORIGIN/1\0",
            {
                "origin_receipt": self.origin_receipt.digest(),
                "tree_sha": self.tree_sha,
                "production_manifest_sha256": self.production_manifest_sha256,
            },
        )


def derive_candidate_tree_evidence(
    origin_receipt: IndependentEvidenceOriginReceipt,
    files: tuple[tuple[str, str, bytes], ...],
) -> CandidateTreeEvidence:
    if type(files) is not tuple or not files:
        raise HostAuthoritySeparationError("candidate file evidence required")
    rows: list[tuple[str, str, str, str, int]] = []
    git_entries: list[tuple[str, str, str]] = []
    production: list[dict[str, Any]] = []
    for item in files:
        if type(item) is not tuple or len(item) != 3:
            raise HostAuthoritySeparationError("candidate file evidence invalid")
        path, mode, data = item
        _path(path)
        _mode(mode)
        if type(data) is not bytes:
            raise HostAuthoritySeparationError("candidate file bytes required")
        blob = _git_blob_sha(data)
        byte_sha = sha256(data).hexdigest()
        row = (path, mode, blob, byte_sha, len(data))
        rows.append(row)
        git_entries.append((path, mode, blob))
        if _production_path(path):
            production.append(
                {
                    "path": path,
                    "blob_sha": blob,
                    "byte_sha256": byte_sha,
                    "size": len(data),
                    "mode": mode,
                }
            )
    rows_tuple = tuple(sorted(rows, key=lambda row: row[0]))
    tree = _git_tree_sha(tuple(git_entries))
    manifest = sha256(
        b"LION/R9D8/EXACT-PRODUCTION-MANIFEST/1\0"
        + _canon(sorted(production, key=lambda row: row["path"]))
    ).hexdigest()
    payload_digest = _candidate_tree_payload_digest(rows_tuple)
    object_digest = _candidate_tree_object_digest(
        tree, len(rows_tuple), manifest, len(production)
    )
    receipt = _verify_origin(
        origin_receipt,
        kind=ORIGIN_CANDIDATE_TREE,
        identity=tree,
        object_digest=object_digest,
        payload_digest=payload_digest,
    )
    provenance = _digest(
        b"LION/CANDIDATE-TREE-EVIDENCE/2\0",
        {
            "tree_sha": tree,
            "tracked_file_count": len(rows_tuple),
            "production_manifest_sha256": manifest,
            "production_entry_count": len(production),
            "provider_observation_id": receipt.observation_id,
            "provider_instance_id": receipt.provider_instance_id,
            "full_entries": rows_tuple,
            "origin_receipt_digest": receipt.digest(),
        },
    )
    return CandidateTreeEvidence(
        tree,
        len(rows_tuple),
        manifest,
        len(production),
        receipt.observation_id,
        receipt.provider_instance_id,
        rows_tuple,
        receipt,
        provenance,
    ).validate()


def _commit_identity(raw: bytes) -> tuple[str, str, tuple[str, ...]]:
    if type(raw) is not bytes or not raw:
        raise HostAuthoritySeparationError("git commit object bytes required")
    oid = sha1(f"commit {len(raw)}\0".encode() + raw).hexdigest()
    header = raw.split(b"\n\n", 1)[0].splitlines()
    trees: list[str] = []
    parents: list[str] = []
    for line in header:
        if line.startswith(b"tree "):
            trees.append(line[5:].decode())
        elif line.startswith(b"parent "):
            parents.append(line[7:].decode())
    if (
        len(trees) != 1
        or not re.fullmatch(r"[0-9a-f]{40}", trees[0])
        or any(not re.fullmatch(r"[0-9a-f]{40}", parent) for parent in parents)
    ):
        raise HostAuthoritySeparationError("git commit object header invalid")
    return oid, trees[0], tuple(parents)


def _repository_object_digest(
    *,
    repository: str,
    pr_number: int,
    base_ref: str,
    base_sha: str,
    base_tree: str,
    head_ref: str,
    head_sha: str,
    head_tree: str,
    synthetic_sha: str,
    synthetic_tree: str,
    synthetic_parents: tuple[str, str],
) -> str:
    return _digest(
        b"LION/REPOSITORY-CURRENTNESS-OBSERVED-OBJECT/1\0",
        {
            "repository": repository,
            "pr_number": pr_number,
            "base_ref": base_ref,
            "base_sha": base_sha,
            "base_tree": base_tree,
            "head_ref": head_ref,
            "head_sha": head_sha,
            "head_tree": head_tree,
            "synthetic_sha": synthetic_sha,
            "synthetic_tree": synthetic_tree,
            "synthetic_parents": synthetic_parents,
        },
    )


@dataclass(frozen=True)
class RepositoryCurrentnessEvidence:
    provider_id: str
    provider_instance_id: str
    repository: str
    pr_number: int
    base_ref: str
    base_sha: str
    base_tree: str
    head_ref: str
    head_sha: str
    head_tree: str
    synthetic_sha: str
    synthetic_tree: str
    synthetic_parents: tuple[str, str]
    provider_payload_sha256: str
    provider_observation_id: str
    observed_at: str
    origin_receipt: IndependentEvidenceOriginReceipt
    provenance_digest: str

    def validate(self) -> "RepositoryCurrentnessEvidence":
        if self.provider_id != CANONICAL_REPOSITORY_PROVIDER:
            raise HostAuthoritySeparationError("repository evidence provider substitution denied")
        if self.repository != CANONICAL_REPOSITORY or type(self.pr_number) is not int or self.pr_number < 1:
            raise HostAuthoritySeparationError("repository evidence identity invalid")
        if not isinstance(self.provider_instance_id, str) or not self.provider_instance_id:
            raise HostAuthoritySeparationError("repository provider instance invalid")
        for ref in (self.base_ref, self.head_ref):
            if not isinstance(ref, str) or not ref or ref.startswith("refs/") or ref.startswith("-"):
                raise HostAuthoritySeparationError("repository evidence ref invalid")
        for oid in (
            self.base_sha,
            self.base_tree,
            self.head_sha,
            self.head_tree,
            self.synthetic_sha,
            self.synthetic_tree,
            *self.synthetic_parents,
        ):
            if not re.fullmatch(r"[0-9a-f]{40}", oid):
                raise HostAuthoritySeparationError("repository evidence git oid invalid")
        if (
            self.synthetic_tree != self.head_tree
            or self.synthetic_parents != (self.base_sha, self.head_sha)
        ):
            raise HostAuthoritySeparationError("repository synthetic topology invalid")
        _sha256_text(self.provider_payload_sha256, "repository provider payload")
        _utc(self.observed_at)
        object_digest = _repository_object_digest(
            repository=self.repository,
            pr_number=self.pr_number,
            base_ref=self.base_ref,
            base_sha=self.base_sha,
            base_tree=self.base_tree,
            head_ref=self.head_ref,
            head_sha=self.head_sha,
            head_tree=self.head_tree,
            synthetic_sha=self.synthetic_sha,
            synthetic_tree=self.synthetic_tree,
            synthetic_parents=self.synthetic_parents,
        )
        receipt = _verify_origin(
            self.origin_receipt,
            kind=ORIGIN_REPOSITORY_CURRENTNESS,
            identity=f"{self.repository}#PR{self.pr_number}",
            object_digest=object_digest,
            payload_digest=self.provider_payload_sha256,
        )
        if (
            self.provider_observation_id != receipt.observation_id
            or self.provider_instance_id != receipt.provider_instance_id
            or self.observed_at != receipt.issued_at
        ):
            raise HostAuthoritySeparationError("repository origin observation mismatch")
        expected = _digest(
            b"LION/REPOSITORY-CURRENTNESS-EVIDENCE/2\0",
            {
                "provider_id": self.provider_id,
                "provider_instance_id": self.provider_instance_id,
                "repository": self.repository,
                "pr_number": self.pr_number,
                "base_ref": self.base_ref,
                "base_sha": self.base_sha,
                "base_tree": self.base_tree,
                "head_ref": self.head_ref,
                "head_sha": self.head_sha,
                "head_tree": self.head_tree,
                "synthetic_sha": self.synthetic_sha,
                "synthetic_tree": self.synthetic_tree,
                "synthetic_parents": self.synthetic_parents,
                "provider_payload_sha256": self.provider_payload_sha256,
                "provider_observation_id": self.provider_observation_id,
                "observed_at": self.observed_at,
                "origin_receipt_digest": receipt.digest(),
            },
        )
        if expected != self.provenance_digest:
            raise HostAuthoritySeparationError("repository evidence provenance digest mismatch")
        return self

    def digest(self) -> str:
        self.validate()
        return self.provenance_digest

    def origin_digest(self) -> str:
        self.validate()
        return self.origin_receipt.digest()


def derive_repository_currentness_evidence(
    origin_receipt: IndependentEvidenceOriginReceipt,
    *,
    pr_payload: bytes,
    base_commit_object: bytes,
    head_commit_object: bytes,
    synthetic_commit_object: bytes,
) -> RepositoryCurrentnessEvidence:
    if type(pr_payload) is not bytes or not pr_payload:
        raise HostAuthoritySeparationError("repository provider PR payload required")
    try:
        pr = json.loads(pr_payload.decode("utf-8"))
    except Exception as exc:
        raise HostAuthoritySeparationError("repository provider PR payload invalid") from exc

    base_oid, base_tree, _ = _commit_identity(base_commit_object)
    head_oid, head_tree, _ = _commit_identity(head_commit_object)
    synthetic_oid, synthetic_tree, synthetic_parents = _commit_identity(synthetic_commit_object)
    try:
        number = pr["number"]
        base = pr["base"]
        head = pr["head"]
        merge = pr["merge_commit_sha"]
        repository = base["repo"]["full_name"]
        if head["repo"]["full_name"] != repository:
            raise KeyError("cross-repository head denied")
        base_ref = base["ref"]
        base_sha = base["sha"]
        head_ref = head["ref"]
        head_sha = head["sha"]
    except Exception as exc:
        raise HostAuthoritySeparationError("repository provider PR shape invalid") from exc

    if (
        repository != CANONICAL_REPOSITORY
        or base_sha != base_oid
        or head_sha != head_oid
        or merge != synthetic_oid
    ):
        raise HostAuthoritySeparationError("repository provider object identity mismatch")
    if synthetic_tree != head_tree or synthetic_parents != (base_oid, head_oid):
        raise HostAuthoritySeparationError("repository provider synthetic topology mismatch")

    payload_digest = _bundle_digest(
        b"LION/REPOSITORY-CURRENTNESS-PRIMARY-PAYLOAD/1\0",
        pr_payload,
        base_commit_object,
        head_commit_object,
        synthetic_commit_object,
    )
    object_digest = _repository_object_digest(
        repository=repository,
        pr_number=number,
        base_ref=base_ref,
        base_sha=base_oid,
        base_tree=base_tree,
        head_ref=head_ref,
        head_sha=head_oid,
        head_tree=head_tree,
        synthetic_sha=synthetic_oid,
        synthetic_tree=synthetic_tree,
        synthetic_parents=synthetic_parents,
    )
    receipt = _verify_origin(
        origin_receipt,
        kind=ORIGIN_REPOSITORY_CURRENTNESS,
        identity=f"{repository}#PR{number}",
        object_digest=object_digest,
        payload_digest=payload_digest,
    )
    data = {
        "provider_id": CANONICAL_REPOSITORY_PROVIDER,
        "provider_instance_id": receipt.provider_instance_id,
        "repository": repository,
        "pr_number": number,
        "base_ref": base_ref,
        "base_sha": base_oid,
        "base_tree": base_tree,
        "head_ref": head_ref,
        "head_sha": head_oid,
        "head_tree": head_tree,
        "synthetic_sha": synthetic_oid,
        "synthetic_tree": synthetic_tree,
        "synthetic_parents": synthetic_parents,
        "provider_payload_sha256": payload_digest,
        "provider_observation_id": receipt.observation_id,
        "observed_at": receipt.issued_at,
    }
    provenance = _digest(
        b"LION/REPOSITORY-CURRENTNESS-EVIDENCE/2\0",
        data | {"origin_receipt_digest": receipt.digest()},
    )
    return RepositoryCurrentnessEvidence(
        **data,
        origin_receipt=receipt,
        provenance_digest=provenance,
    ).validate()


def _normalize_sql(sql: str) -> str:
    if not isinstance(sql, str) or not sql.strip():
        raise HostAuthoritySeparationError("schema SQL definition invalid")
    return " ".join(sql.strip().split())


def _schema_manifest_digest(entries: tuple[tuple[str, str, str, str], ...]) -> str:
    wire = [
        {"type": typ, "name": name, "table": table, "definition": definition}
        for typ, name, table, definition in entries
    ]
    return sha256(b"LION/SCHEMA-OBJECT-MANIFEST/1\0" + _canon(wire)).hexdigest()


def _pre_schema_payload_digest(
    source_database_sha256: str,
    entries: tuple[tuple[str, str, str, str], ...],
) -> str:
    return _digest(
        b"LION/PRE-SCHEMA-PRIMARY-PAYLOAD/1\0",
        {"source_database_sha256": source_database_sha256, "entries": entries},
    )


def _pre_schema_object_digest(source_database_sha256: str, manifest_digest: str) -> str:
    return _digest(
        b"LION/PRE-SCHEMA-OBSERVED-OBJECT/1\0",
        {
            "source_database_sha256": source_database_sha256,
            "manifest_digest": manifest_digest,
        },
    )


@dataclass(frozen=True)
class SchemaManifestEvidence:
    entries: tuple[tuple[str, str, str, str], ...]
    manifest_digest: str
    source_database_sha256: str
    provider_observation_id: str
    provider_instance_id: str
    provenance_digest: str
    origin_receipt: IndependentEvidenceOriginReceipt | None = None
    derived_from_pre_schema_provenance_digest: str | None = None

    def validate(self) -> "SchemaManifestEvidence":
        _sha256_text(self.source_database_sha256, "schema source database")
        if type(self.entries) is not tuple:
            raise HostAuthoritySeparationError("schema manifest evidence invalid")
        seen: set[tuple[str, str]] = set()
        for row in self.entries:
            if type(row) is not tuple or len(row) != 4:
                raise HostAuthoritySeparationError("schema manifest row invalid")
            typ, name, table, definition = row
            if (
                typ not in {"table", "trigger", "index", "view"}
                or not all(isinstance(item, str) and item for item in (name, table, definition))
            ):
                raise HostAuthoritySeparationError("schema manifest row invalid")
            if (typ, name) in seen:
                raise HostAuthoritySeparationError("schema manifest duplicate object")
            seen.add((typ, name))
        manifest = _schema_manifest_digest(self.entries)
        if manifest != self.manifest_digest:
            raise HostAuthoritySeparationError("schema manifest digest mismatch")

        if self.origin_receipt is not None:
            if self.derived_from_pre_schema_provenance_digest is not None:
                raise HostAuthoritySeparationError("schema evidence origin class confusion")
            payload_digest = _pre_schema_payload_digest(
                self.source_database_sha256, self.entries
            )
            object_digest = _pre_schema_object_digest(
                self.source_database_sha256, manifest
            )
            receipt = _verify_origin(
                self.origin_receipt,
                kind=ORIGIN_PRE_SCHEMA,
                identity=LIVE_DB_PATH,
                object_digest=object_digest,
                payload_digest=payload_digest,
            )
            if (
                self.provider_observation_id != receipt.observation_id
                or self.provider_instance_id != receipt.provider_instance_id
            ):
                raise HostAuthoritySeparationError("schema provider observation mismatch")
            expected = _digest(
                b"LION/PRE-SCHEMA-EVIDENCE/2\0",
                {
                    "entries": self.entries,
                    "manifest_digest": manifest,
                    "source_database_sha256": self.source_database_sha256,
                    "provider_observation_id": self.provider_observation_id,
                    "provider_instance_id": self.provider_instance_id,
                    "origin_receipt_digest": receipt.digest(),
                },
            )
        else:
            _sha256_text(
                self.derived_from_pre_schema_provenance_digest,
                "derived pre-schema provenance",
            )
            if self.provider_instance_id != "deterministic-post-schema/v1":
                raise HostAuthoritySeparationError("post-schema provider instance invalid")
            expected_observation = (
                "derived-post-schema:"
                + self.derived_from_pre_schema_provenance_digest[:32]
            )
            if self.provider_observation_id != expected_observation:
                raise HostAuthoritySeparationError("post-schema derivation identity invalid")
            expected = _digest(
                b"LION/DERIVED-POST-SCHEMA-EVIDENCE/1\0",
                {
                    "entries": self.entries,
                    "manifest_digest": manifest,
                    "source_database_sha256": self.source_database_sha256,
                    "derived_from_pre_schema_provenance_digest": self.derived_from_pre_schema_provenance_digest,
                },
            )
        if expected != self.provenance_digest:
            raise HostAuthoritySeparationError("schema manifest provenance mismatch")
        return self

    def digest(self) -> str:
        self.validate()
        return self.manifest_digest

    def require_independent_pre_schema(self) -> "SchemaManifestEvidence":
        self.validate()
        if self.origin_receipt is None or self.derived_from_pre_schema_provenance_digest is not None:
            raise HostAuthoritySeparationError("independent pre-schema origin required")
        return self

    def origin_digest(self) -> str:
        self.require_independent_pre_schema()
        assert self.origin_receipt is not None
        return self.origin_receipt.digest()


def derive_schema_manifest_evidence(
    origin_receipt: IndependentEvidenceOriginReceipt,
    rows: tuple[tuple[str, str, str, str], ...],
    *,
    source_database_sha256: str,
) -> SchemaManifestEvidence:
    _sha256_text(source_database_sha256, "schema source database")
    if type(rows) is not tuple:
        raise HostAuthoritySeparationError("schema rows must be tuple")
    entries: list[tuple[str, str, str, str]] = []
    for typ, name, table, sql in rows:
        if name.startswith("sqlite_"):
            continue
        entries.append((typ, name, table, _normalize_sql(sql)))
    entries_tuple = tuple(sorted(entries, key=lambda row: (row[0], row[1])))
    manifest = _schema_manifest_digest(entries_tuple)
    payload_digest = _pre_schema_payload_digest(
        source_database_sha256, entries_tuple
    )
    object_digest = _pre_schema_object_digest(
        source_database_sha256, manifest
    )
    receipt = _verify_origin(
        origin_receipt,
        kind=ORIGIN_PRE_SCHEMA,
        identity=LIVE_DB_PATH,
        object_digest=object_digest,
        payload_digest=payload_digest,
    )
    provenance = _digest(
        b"LION/PRE-SCHEMA-EVIDENCE/2\0",
        {
            "entries": entries_tuple,
            "manifest_digest": manifest,
            "source_database_sha256": source_database_sha256,
            "provider_observation_id": receipt.observation_id,
            "provider_instance_id": receipt.provider_instance_id,
            "origin_receipt_digest": receipt.digest(),
        },
    )
    return SchemaManifestEvidence(
        entries_tuple,
        manifest,
        source_database_sha256,
        receipt.observation_id,
        receipt.provider_instance_id,
        provenance,
        receipt,
        None,
    ).validate()


def _canonical_provisioning_schema_entries() -> tuple[tuple[str, str, str, str], ...]:
    sql = authority_provisioning_schema_sql()
    rows: list[tuple[str, str, str, str]] = []
    for match in re.finditer(
        r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\);", sql, re.I | re.S
    ):
        rows.append(
            (
                "table",
                match.group(1),
                match.group(1),
                _normalize_sql(match.group(0)[:-1]),
            )
        )
    for match in re.finditer(
        r"CREATE TRIGGER IF NOT EXISTS\s+(\w+)\s+BEFORE\s+(?:UPDATE|DELETE)\s+ON\s+(\w+)\s+BEGIN\s+.*?\s+END;",
        sql,
        re.I | re.S,
    ):
        rows.append(
            (
                "trigger",
                match.group(1),
                match.group(2),
                _normalize_sql(match.group(0)[:-1]),
            )
        )
    if len(rows) != 7:
        raise HostAuthoritySeparationError("canonical schema object extraction mismatch")
    return tuple(rows)


def derive_expected_post_schema_evidence(
    pre: SchemaManifestEvidence,
) -> SchemaManifestEvidence:
    if type(pre) is not SchemaManifestEvidence:
        raise HostAuthoritySeparationError("exact pre-schema evidence required")
    pre.require_independent_pre_schema()
    merged = {(typ, name): (typ, name, table, definition) for typ, name, table, definition in pre.entries}
    for row in _canonical_provisioning_schema_entries():
        merged.setdefault((row[0], row[1]), row)
    entries = tuple(sorted(merged.values(), key=lambda row: (row[0], row[1])))
    manifest = _schema_manifest_digest(entries)
    provenance = _digest(
        b"LION/DERIVED-POST-SCHEMA-EVIDENCE/1\0",
        {
            "entries": entries,
            "manifest_digest": manifest,
            "source_database_sha256": pre.source_database_sha256,
            "derived_from_pre_schema_provenance_digest": pre.provenance_digest,
        },
    )
    return SchemaManifestEvidence(
        entries,
        manifest,
        pre.source_database_sha256,
        "derived-post-schema:" + pre.provenance_digest[:32],
        "deterministic-post-schema/v1",
        provenance,
        None,
        pre.provenance_digest,
    ).validate()


def _snapshot_object_digest(
    *,
    snapshot_path: str,
    source_database_sha256: str,
    snapshot_sha256: str,
    snapshot_size: int,
    source_observation_digest: str,
    integrity_check: str,
    created_at: str,
) -> str:
    return _digest(
        b"LION/SNAPSHOT-OBSERVED-OBJECT/1\0",
        {
            "snapshot_path": snapshot_path,
            "source_database_sha256": source_database_sha256,
            "snapshot_sha256": snapshot_sha256,
            "snapshot_size": snapshot_size,
            "source_observation_digest": source_observation_digest,
            "integrity_check": integrity_check,
            "created_at": created_at,
        },
    )


@dataclass(frozen=True)
class SnapshotProvenanceEvidence:
    attestation: SnapshotAttestation
    origin_receipt: IndependentEvidenceOriginReceipt

    def validate(self) -> "SnapshotProvenanceEvidence":
        if type(self.attestation) is not SnapshotAttestation:
            raise HostAuthoritySeparationError("snapshot attestation required")
        self.attestation.validate()
        att = self.attestation
        object_digest = _snapshot_object_digest(
            snapshot_path=att.snapshot_path,
            source_database_sha256=att.source_database_sha256,
            snapshot_sha256=att.snapshot_sha256,
            snapshot_size=att.snapshot_size,
            source_observation_digest=att.source_observation_digest,
            integrity_check=att.integrity_check,
            created_at=att.created_at,
        )
        receipt = _verify_origin(
            self.origin_receipt,
            kind=ORIGIN_SNAPSHOT,
            identity=att.snapshot_path,
            object_digest=object_digest,
            payload_digest=att.snapshot_sha256,
        )
        if (
            att.snapshotter_identity != CANONICAL_SNAPSHOTTER_IDENTITY
            or receipt.provider_id != CANONICAL_SNAPSHOTTER_IDENTITY
            or att.created_at != receipt.issued_at
        ):
            raise HostAuthoritySeparationError("snapshot origin identity mismatch")
        wire = {
            "snapshot_path": att.snapshot_path,
            "source_database_sha256": att.source_database_sha256,
            "snapshot_sha256": att.snapshot_sha256,
            "snapshot_size": att.snapshot_size,
            "snapshotter_identity": att.snapshotter_identity,
            "source_observation_digest": att.source_observation_digest,
            "integrity_check": att.integrity_check,
            "created_at": att.created_at,
            "provider_instance_id": receipt.provider_instance_id,
            "provider_observation_id": receipt.observation_id,
            "origin_receipt_digest": receipt.digest(),
        }
        expected = _digest(b"LION/SNAPSHOT-BYTE-PROVENANCE/2\0", wire)
        if att.provenance_digest != expected:
            raise HostAuthoritySeparationError("snapshot provenance digest mismatch")
        return self

    def digest(self) -> str:
        self.validate()
        return self.attestation.provenance_digest

    def origin_digest(self) -> str:
        self.validate()
        return self.origin_receipt.digest()


def derive_snapshot_provenance(
    origin_receipt: IndependentEvidenceOriginReceipt,
    *,
    source_observation: SchemaObservation,
    snapshot_path: str,
    snapshot_bytes: bytes,
    integrity_check: str,
) -> SnapshotProvenanceEvidence:
    if type(source_observation) is not SchemaObservation or type(snapshot_bytes) is not bytes or not snapshot_bytes:
        raise HostAuthoritySeparationError("snapshot primary evidence invalid")
    source_observation.validate()
    snapshot_sha = sha256(snapshot_bytes).hexdigest()
    source_observation_digest = source_observation.digest()
    receipt_time = origin_receipt.issued_at
    object_digest = _snapshot_object_digest(
        snapshot_path=snapshot_path,
        source_database_sha256=source_observation.database_sha256,
        snapshot_sha256=snapshot_sha,
        snapshot_size=len(snapshot_bytes),
        source_observation_digest=source_observation_digest,
        integrity_check=integrity_check,
        created_at=receipt_time,
    )
    receipt = _verify_origin(
        origin_receipt,
        kind=ORIGIN_SNAPSHOT,
        identity=snapshot_path,
        object_digest=object_digest,
        payload_digest=snapshot_sha,
    )
    wire = {
        "snapshot_path": snapshot_path,
        "source_database_sha256": source_observation.database_sha256,
        "snapshot_sha256": snapshot_sha,
        "snapshot_size": len(snapshot_bytes),
        "snapshotter_identity": CANONICAL_SNAPSHOTTER_IDENTITY,
        "source_observation_digest": source_observation_digest,
        "integrity_check": integrity_check,
        "created_at": receipt.issued_at,
        "provider_instance_id": receipt.provider_instance_id,
        "provider_observation_id": receipt.observation_id,
        "origin_receipt_digest": receipt.digest(),
    }
    provenance = _digest(b"LION/SNAPSHOT-BYTE-PROVENANCE/2\0", wire)
    attestation = SnapshotAttestation(
        snapshot_path,
        source_observation.database_sha256,
        snapshot_sha,
        len(snapshot_bytes),
        CANONICAL_SNAPSHOTTER_IDENTITY,
        source_observation_digest,
        provenance,
        integrity_check,
        receipt.issued_at,
    ).validate()
    return SnapshotProvenanceEvidence(attestation, receipt).validate()


def _validate_add_only_schema_sql(sql: str) -> None:
    low = sql.lower()
    if low.count("create table if not exists ") != 5 or low.count("create trigger if not exists ") != 2:
        raise HostAuthoritySeparationError("canonical add-only object count mismatch")
    if re.search(
        r"\bdrop\b|\balter\b|\binsert\s+into\b|\bupdate\s+\w+\s+set\b|\bdelete\s+from\b|\breplace\s+into\b|\bvacuum\b|\battach\b|\bdetach\b",
        low,
    ):
        raise HostAuthoritySeparationError("destructive or data-mutating schema SQL denied")
    for trigger in PROVISIONING_TRIGGERS:
        if trigger not in low:
            raise HostAuthoritySeparationError("append-only trigger missing")
    if low.count("select raise(abort") != 2:
        raise HostAuthoritySeparationError("append-only trigger guards missing")
    required = set(PROVISIONING_TABLES + PRESERVED_TABLES + PROVISIONING_TRIGGERS)
    if any(name not in low for name in required):
        raise HostAuthoritySeparationError("schema SQL missing canonical objects")


class HostAuthoritySeparationBroker:
    @staticmethod
    def canonical_plan(
        *,
        repository_evidence: RepositoryCurrentnessEvidence,
        candidate_tree_evidence: CandidateTreeEvidence,
        pre_schema_evidence: SchemaManifestEvidence,
        trusted_runtime_reads: tuple[TrustedRuntimeReadBinding, ...],
        generated_at: str,
    ) -> HostAuthoritySeparationPlan:
        if (
            type(repository_evidence) is not RepositoryCurrentnessEvidence
            or type(candidate_tree_evidence) is not CandidateTreeEvidence
            or type(pre_schema_evidence) is not SchemaManifestEvidence
        ):
            raise HostAuthoritySeparationError("canonical provenance evidence required")
        repository_evidence.validate()
        candidate_tree_evidence.validate()
        pre_schema_evidence.require_independent_pre_schema()
        if repository_evidence.head_tree != candidate_tree_evidence.tree_sha:
            raise HostAuthoritySeparationError("candidate tree evidence not bound to repository head")
        post = derive_expected_post_schema_evidence(pre_schema_evidence)
        plan = HostAuthoritySeparationPlan(
            plan_id=f"host-separation:{repository_evidence.head_sha}",
            repository=repository_evidence.repository,
            pr_number=repository_evidence.pr_number,
            baseline_ref=repository_evidence.base_ref,
            baseline_sha=repository_evidence.base_sha,
            baseline_tree=repository_evidence.base_tree,
            certified_candidate_ref=repository_evidence.head_ref,
            certified_candidate_sha=repository_evidence.head_sha,
            certified_candidate_tree=repository_evidence.head_tree,
            certified_synthetic_sha=repository_evidence.synthetic_sha,
            certified_repository_evidence_digest=repository_evidence.digest(),
            certified_source_manifest_sha256=candidate_tree_evidence.production_manifest_sha256,
            certified_pre_schema_manifest_digest=pre_schema_evidence.digest(),
            certified_post_schema_digest=post.digest(),
            runtime_user=RUNTIME_USER,
            runner_user=RUNNER_USER,
            deployer_user=DEPLOYER_USER,
            migrator_user=MIGRATOR_USER,
            control_plane_group=CONTROL_PLANE_GROUP,
            trust_client_group=TRUST_CLIENT_GROUP,
            runtime_code_path=RUNTIME_CODE_PATH,
            live_db_path=LIVE_DB_PATH,
            service_env_path=SERVICE_ENV_PATH,
            service_unit_path=SERVICE_UNIT_PATH,
            runtime_code_owner="root",
            runtime_code_group=CONTROL_PLANE_GROUP,
            runtime_code_dir_mode=0o550,
            runtime_code_file_mode=0o440,
            runner_target_groups=(RUNNER_USER, TRUST_CLIENT_GROUP),
            trusted_runtime_reads=trusted_runtime_reads,
            production_private_key_on_host=False,
            generated_at=generated_at,
        )
        return plan.validate()

    @staticmethod
    def derive_transition(
        observation: HostAuthorityObservation,
        plan: HostAuthoritySeparationPlan,
        *,
        generated_at: str,
    ) -> HostTransitionPlan:
        if type(observation) is not HostAuthorityObservation or type(plan) is not HostAuthoritySeparationPlan:
            raise HostAuthoritySeparationError("exact observation and plan required")
        observation.validate()
        plan.validate()
        if (observation.runtime_user, observation.runner_user) != (
            plan.runtime_user,
            plan.runner_user,
        ):
            raise HostAuthoritySeparationError("host principal currentness drift")
        operations: list[HostOperation] = []
        if CONTROL_PLANE_GROUP in observation.runner_groups:
            operations.append(
                HostOperation(
                    "REMOVE_RUNNER_CONTROL_PLANE_GROUP",
                    RUNNER_USER,
                    CONTROL_PLANE_GROUP,
                    None,
                    "remove runner from control-plane supplementary group",
                )
            )
        if TRUST_CLIENT_GROUP not in observation.runner_groups:
            operations.extend(
                (
                    HostOperation(
                        "ENSURE_TRUST_CLIENT_GROUP",
                        DEPLOYER_USER,
                        TRUST_CLIENT_GROUP,
                        None,
                        "ensure dedicated non-authority trust-client group",
                    ),
                    HostOperation(
                        "ADD_RUNNER_TRUST_CLIENT_GROUP",
                        RUNNER_USER,
                        TRUST_CLIENT_GROUP,
                        None,
                        "grant only bounded external-runtime read membership",
                    ),
                )
            )
        operations.extend(
            (
                HostOperation(
                    "REOWN_RUNTIME_CODE_ROOT",
                    DEPLOYER_USER,
                    RUNTIME_CODE_PATH,
                    observation.deployed_manifest_sha256,
                    "root owns immutable runtime code",
                ),
                HostOperation(
                    "SET_RUNTIME_CODE_READ_ONLY",
                    DEPLOYER_USER,
                    RUNTIME_CODE_PATH,
                    observation.deployed_manifest_sha256,
                    "directories 0550 files 0440; runtime is read-only",
                ),
            )
        )
        for binding in plan.trusted_runtime_reads:
            operations.append(
                HostOperation(
                    "PIN_TRUST_CLIENT_RUNTIME_READ",
                    DEPLOYER_USER,
                    binding.path,
                    binding.sha256_digest,
                    "expose this file read-only to trust-client group only",
                )
            )
        operations.extend(
            (
                HostOperation(
                    "DENY_RUNNER_DB_ACCESS",
                    DEPLOYER_USER,
                    LIVE_DB_PATH,
                    observation.live_db_sha256,
                    "runner must have neither read nor write access",
                ),
                HostOperation(
                    "DENY_RUNNER_SERVICE_ENV_ACCESS",
                    DEPLOYER_USER,
                    SERVICE_ENV_PATH,
                    None,
                    "runner must not read service credential environment",
                ),
                HostOperation(
                    "INSTALL_BOUNDED_DEPLOYMENT_BROKER",
                    DEPLOYER_USER,
                    RUNTIME_CODE_PATH,
                    None,
                    "fixed operation, fixed destination, no arbitrary shell",
                ),
                HostOperation(
                    "INSTALL_BOUNDED_SCHEMA_MIGRATION_BROKER",
                    MIGRATOR_USER,
                    LIVE_DB_PATH,
                    None,
                    "exact add-only schema transition only",
                ),
            )
        )
        unique: list[HostOperation] = []
        seen: set[tuple[str, str]] = set()
        for operation in operations:
            operation.validate()
            key = (operation.kind, operation.target)
            if key not in seen:
                seen.add(key)
                unique.append(operation)
        return HostTransitionPlan(
            f"host-transition:{observation.digest()[:20]}:{plan.digest()[:20]}",
            observation.digest(),
            plan.digest(),
            tuple(unique),
            generated_at,
        ).validate()

    @staticmethod
    def target_observation_is_separated(observation: HostAuthorityObservation) -> bool:
        observation.validate()
        return (
            CONTROL_PLANE_GROUP not in observation.runner_groups
            and TRUST_CLIENT_GROUP in observation.runner_groups
            and not observation.runner_db_read
            and not observation.runner_db_write
            and not observation.runner_service_env_read
            and not observation.runtime_code_write
            and not observation.runner_actions_private_key_read
            and not observation.runner_authority_private_key_read
        )


def _assert_repo_plan(
    repository_evidence: RepositoryCurrentnessEvidence,
    plan: HostAuthoritySeparationPlan,
) -> None:
    repository_evidence.validate()
    plan.validate()
    exact = (
        repository_evidence.repository,
        repository_evidence.pr_number,
        repository_evidence.base_ref,
        repository_evidence.base_sha,
        repository_evidence.base_tree,
        repository_evidence.head_ref,
        repository_evidence.head_sha,
        repository_evidence.head_tree,
        repository_evidence.synthetic_sha,
        repository_evidence.digest(),
    )
    wanted = (
        plan.repository,
        plan.pr_number,
        plan.baseline_ref,
        plan.baseline_sha,
        plan.baseline_tree,
        plan.certified_candidate_ref,
        plan.certified_candidate_sha,
        plan.certified_candidate_tree,
        plan.certified_synthetic_sha,
        plan.certified_repository_evidence_digest,
    )
    if exact != wanted:
        raise HostAuthoritySeparationError(
            "repository currentness evidence not bound to certified plan"
        )


def _deployment_currentness_digest(
    request: DeploymentRequest,
    repository_evidence: RepositoryCurrentnessEvidence,
    tree: CandidateTreeEvidence,
    current_deployed_manifest_sha256: str,
    current_service_unit_sha256: str,
) -> str:
    return _digest(
        b"LION/DEPLOYMENT-CURRENTNESS/3\0",
        {
            "request": request.digest(),
            "repository_evidence": repository_evidence.digest(),
            "repository_origin_digest": repository_evidence.origin_digest(),
            "candidate_tree_evidence": tree.digest(),
            "candidate_tree_origin_digest": tree.origin_digest(),
            "source_manifest_origin_digest": tree.source_manifest_origin_digest(),
            "payload_digest": tree.production_manifest_sha256,
            "deployed_manifest_sha256": current_deployed_manifest_sha256,
            "service_unit_sha256": current_service_unit_sha256,
        },
    )


def _migration_currentness_digest(
    request: SchemaMigrationRequest,
    repository_evidence: RepositoryCurrentnessEvidence,
    before: SchemaObservation,
    pre: SchemaManifestEvidence,
    snapshot: SnapshotProvenanceEvidence,
    post: SchemaManifestEvidence,
) -> str:
    return _digest(
        b"LION/MIGRATION-CURRENTNESS/3\0",
        {
            "request": request.digest(),
            "repository_evidence": repository_evidence.digest(),
            "repository_origin_digest": repository_evidence.origin_digest(),
            "before": before.digest(),
            "pre_schema_manifest_digest": pre.digest(),
            "pre_schema_provenance_digest": pre.provenance_digest,
            "pre_schema_origin_digest": pre.origin_digest(),
            "snapshot_provenance": snapshot.digest(),
            "snapshot_origin_digest": snapshot.origin_digest(),
            "canonical_schema_sql_digest": CANONICAL_SCHEMA_SQL_SHA256,
            "derived_post_schema_digest": post.digest(),
            "derived_post_schema_provenance_digest": post.provenance_digest,
        },
    )


class BoundedDeploymentBroker:
    @staticmethod
    def admit(
        request: DeploymentRequest,
        *,
        plan: HostAuthoritySeparationPlan,
        authority: ExternalAuthorityIdentity,
        repository_evidence: RepositoryCurrentnessEvidence,
        candidate_tree_evidence: CandidateTreeEvidence,
        current_deployed_manifest_sha256: str,
        current_service_unit_sha256: str,
        issued_at: str,
    ) -> BrokerPermit:
        if (
            type(request) is not DeploymentRequest
            or type(plan) is not HostAuthoritySeparationPlan
            or type(authority) is not ExternalAuthorityIdentity
            or type(repository_evidence) is not RepositoryCurrentnessEvidence
            or type(candidate_tree_evidence) is not CandidateTreeEvidence
        ):
            raise HostAuthoritySeparationError("exact deployment admission evidence required")
        request.validate()
        plan.validate()
        authority.validate()
        repository_evidence.validate()
        candidate_tree_evidence.validate()
        _assert_repo_plan(repository_evidence, plan)
        if authority.host_principal in {
            plan.deployer_user,
            plan.migrator_user,
            plan.runtime_user,
            plan.runner_user,
        }:
            raise HostAuthoritySeparationError(
                "authority issuer overlaps host execution principal"
            )
        if request.separation_plan_digest != plan.digest():
            raise HostAuthoritySeparationError("deployment plan digest mismatch")
        request_repository = (
            request.repository,
            request.pr_number,
            request.baseline_ref,
            request.baseline_sha,
            request.baseline_tree,
            request.candidate_ref,
            request.candidate_sha,
            request.candidate_tree,
            request.synthetic_sha,
            request.repository_evidence_digest,
        )
        evidence_repository = (
            repository_evidence.repository,
            repository_evidence.pr_number,
            repository_evidence.base_ref,
            repository_evidence.base_sha,
            repository_evidence.base_tree,
            repository_evidence.head_ref,
            repository_evidence.head_sha,
            repository_evidence.head_tree,
            repository_evidence.synthetic_sha,
            repository_evidence.digest(),
        )
        if request_repository != evidence_repository:
            raise HostAuthoritySeparationError(
                "deployment request repository provenance mismatch"
            )
        if (
            candidate_tree_evidence.tree_sha != repository_evidence.head_tree
            or request.source_manifest_sha256
            != candidate_tree_evidence.production_manifest_sha256
            or request.source_manifest_sha256
            != plan.certified_source_manifest_sha256
        ):
            raise HostAuthoritySeparationError(
                "deployment source manifest provenance mismatch"
            )
        for value, name in (
            (current_deployed_manifest_sha256, "deployed manifest"),
            (current_service_unit_sha256, "service unit"),
        ):
            _sha256_text(value, name)
        if (
            request.current_deployed_manifest_sha256,
            request.service_unit_sha256,
        ) != (current_deployed_manifest_sha256, current_service_unit_sha256):
            raise HostAuthoritySeparationError("deployed host currentness drift")
        authority_identity_digest = _digest(
            b"LION/EXTERNAL-AUTHORITY-IDENTITY/1\0", asdict(authority)
        )
        currentness = _deployment_currentness_digest(
            request,
            repository_evidence,
            candidate_tree_evidence,
            current_deployed_manifest_sha256,
            current_service_unit_sha256,
        )
        return BrokerPermit(
            f"deployment-permit:{request.digest()}",
            "DEPLOY_EXACT_CANDIDATE",
            request.digest(),
            plan.digest(),
            DEPLOYER_USER,
            RUNTIME_CODE_PATH,
            candidate_tree_evidence.production_manifest_sha256,
            currentness,
            current_deployed_manifest_sha256,
            authority_identity_digest,
            issued_at,
        ).validate()

    @staticmethod
    def revalidate_before_effect(
        request: DeploymentRequest,
        permit: BrokerPermit,
        *,
        plan: HostAuthoritySeparationPlan,
        repository_evidence: RepositoryCurrentnessEvidence,
        candidate_tree_evidence: CandidateTreeEvidence,
        current_deployed_manifest_sha256: str,
        current_service_unit_sha256: str,
    ) -> BrokerPermit:
        request.validate()
        permit.validate()
        plan.validate()
        repository_evidence.validate()
        candidate_tree_evidence.validate()
        _assert_repo_plan(repository_evidence, plan)
        if (
            permit.operation_kind != "DEPLOY_EXACT_CANDIDATE"
            or permit.fixed_executor_principal != DEPLOYER_USER
            or permit.fixed_destination != RUNTIME_CODE_PATH
        ):
            raise HostAuthoritySeparationError("deployment permit identity mismatch")
        if (
            permit.request_digest != request.digest()
            or permit.separation_plan_digest != plan.digest()
        ):
            raise HostAuthoritySeparationError("deployment permit binding mismatch")
        if (
            request.repository_evidence_digest != repository_evidence.digest()
            or request.source_manifest_sha256
            != candidate_tree_evidence.production_manifest_sha256
            or candidate_tree_evidence.tree_sha != repository_evidence.head_tree
        ):
            raise HostAuthoritySeparationError("deployment provenance drift")
        if permit.fixed_payload_digest != candidate_tree_evidence.production_manifest_sha256:
            raise HostAuthoritySeparationError("deployment payload digest mismatch")
        if (
            request.current_deployed_manifest_sha256,
            request.service_unit_sha256,
        ) != (current_deployed_manifest_sha256, current_service_unit_sha256):
            raise HostAuthoritySeparationError("deployed host currentness drift")
        expected = _deployment_currentness_digest(
            request,
            repository_evidence,
            candidate_tree_evidence,
            current_deployed_manifest_sha256,
            current_service_unit_sha256,
        )
        if (
            permit.currentness_digest != expected
            or permit.recovery_evidence_digest != current_deployed_manifest_sha256
        ):
            raise HostAuthoritySeparationError(
                "deployment permit stale currentness evidence"
            )
        return permit

    @staticmethod
    def verify_receipt(
        request: DeploymentRequest,
        permit: BrokerPermit,
        receipt: DeploymentReceipt,
    ) -> DeploymentReceipt:
        request.validate()
        permit.validate()
        receipt.validate()
        if (
            permit.operation_kind != "DEPLOY_EXACT_CANDIDATE"
            or permit.request_digest != request.digest()
        ):
            raise HostAuthoritySeparationError("deployment permit/request mismatch")
        if (
            receipt.request_digest != request.digest()
            or receipt.permit_digest != permit.digest()
        ):
            raise HostAuthoritySeparationError("deployment receipt binding mismatch")
        if receipt.pre_manifest_sha256 != request.current_deployed_manifest_sha256:
            raise HostAuthoritySeparationError("deployment receipt pre-state mismatch")
        if (
            receipt.deployed_candidate_sha,
            receipt.deployed_candidate_tree,
        ) != (request.candidate_sha, request.candidate_tree):
            raise HostAuthoritySeparationError("deployment receipt candidate mismatch")
        if (
            receipt.status == "ROLLED_BACK"
            and receipt.post_manifest_sha256 != receipt.pre_manifest_sha256
        ):
            raise HostAuthoritySeparationError("deployment rollback receipt mismatch")
        return receipt


class BoundedSchemaMigrationBroker:
    @staticmethod
    def admit(
        request: SchemaMigrationRequest,
        *,
        plan: HostAuthoritySeparationPlan,
        authority: ExternalAuthorityIdentity,
        repository_evidence: RepositoryCurrentnessEvidence,
        before: SchemaObservation,
        pre_schema_evidence: SchemaManifestEvidence,
        snapshot_evidence: SnapshotProvenanceEvidence,
        issued_at: str,
    ) -> BrokerPermit:
        if (
            type(request) is not SchemaMigrationRequest
            or type(plan) is not HostAuthoritySeparationPlan
            or type(authority) is not ExternalAuthorityIdentity
            or type(repository_evidence) is not RepositoryCurrentnessEvidence
            or type(before) is not SchemaObservation
            or type(pre_schema_evidence) is not SchemaManifestEvidence
            or type(snapshot_evidence) is not SnapshotProvenanceEvidence
        ):
            raise HostAuthoritySeparationError("exact migration admission evidence required")
        request.validate()
        plan.validate()
        authority.validate()
        repository_evidence.validate()
        before.validate()
        pre_schema_evidence.require_independent_pre_schema()
        snapshot_evidence.validate()
        _assert_repo_plan(repository_evidence, plan)
        if authority.host_principal in {
            plan.deployer_user,
            plan.migrator_user,
            plan.runtime_user,
            plan.runner_user,
        }:
            raise HostAuthoritySeparationError(
                "authority issuer overlaps migration principal"
            )
        _validate_add_only_schema_sql(authority_provisioning_schema_sql())
        if request.schema_sql_sha256 != CANONICAL_SCHEMA_SQL_SHA256:
            raise HostAuthoritySeparationError("schema digest substitution denied")
        if request.separation_plan_digest != plan.digest():
            raise HostAuthoritySeparationError("migration plan digest mismatch")
        request_repository = (
            request.repository,
            request.pr_number,
            request.candidate_ref,
            request.candidate_sha,
            request.candidate_tree,
            request.synthetic_sha,
            request.repository_evidence_digest,
        )
        evidence_repository = (
            repository_evidence.repository,
            repository_evidence.pr_number,
            repository_evidence.head_ref,
            repository_evidence.head_sha,
            repository_evidence.head_tree,
            repository_evidence.synthetic_sha,
            repository_evidence.digest(),
        )
        if request_repository != evidence_repository:
            raise HostAuthoritySeparationError(
                "migration request repository provenance mismatch"
            )
        if (
            request.live_database_sha256 != before.database_sha256
            or request.pre_schema_digest != before.schema_digest
            or before.schema_digest != pre_schema_evidence.digest()
            or pre_schema_evidence.source_database_sha256 != before.database_sha256
            or plan.certified_pre_schema_manifest_digest != pre_schema_evidence.digest()
        ):
            raise HostAuthoritySeparationError("pre-schema provenance mismatch")
        snapshot = snapshot_evidence.attestation
        if (
            snapshot.source_database_sha256 != before.database_sha256
            or snapshot.source_observation_digest != before.digest()
            or request.snapshot_sha256 != snapshot.snapshot_sha256
        ):
            raise HostAuthoritySeparationError("snapshot provenance mismatch")
        post = derive_expected_post_schema_evidence(pre_schema_evidence)
        if (
            request.expected_post_schema_digest != post.digest()
            or plan.certified_post_schema_digest != post.digest()
        ):
            raise HostAuthoritySeparationError("post-schema provenance mismatch")
        authority_identity_digest = _digest(
            b"LION/EXTERNAL-AUTHORITY-IDENTITY/1\0", asdict(authority)
        )
        currentness = _migration_currentness_digest(
            request,
            repository_evidence,
            before,
            pre_schema_evidence,
            snapshot_evidence,
            post,
        )
        return BrokerPermit(
            f"migration-permit:{request.digest()}",
            "MIGRATE_EXACT_SCHEMA",
            request.digest(),
            plan.digest(),
            MIGRATOR_USER,
            LIVE_DB_PATH,
            CANONICAL_SCHEMA_SQL_SHA256,
            currentness,
            snapshot_evidence.digest(),
            authority_identity_digest,
            issued_at,
        ).validate()

    @staticmethod
    def revalidate_before_effect(
        request: SchemaMigrationRequest,
        permit: BrokerPermit,
        *,
        plan: HostAuthoritySeparationPlan,
        repository_evidence: RepositoryCurrentnessEvidence,
        before: SchemaObservation,
        pre_schema_evidence: SchemaManifestEvidence,
        snapshot_evidence: SnapshotProvenanceEvidence,
    ) -> BrokerPermit:
        request.validate()
        permit.validate()
        plan.validate()
        repository_evidence.validate()
        before.validate()
        pre_schema_evidence.require_independent_pre_schema()
        snapshot_evidence.validate()
        _assert_repo_plan(repository_evidence, plan)
        if (
            permit.operation_kind != "MIGRATE_EXACT_SCHEMA"
            or permit.fixed_executor_principal != MIGRATOR_USER
            or permit.fixed_destination != LIVE_DB_PATH
        ):
            raise HostAuthoritySeparationError("migration permit identity mismatch")
        if (
            permit.request_digest != request.digest()
            or permit.separation_plan_digest != plan.digest()
            or permit.fixed_payload_digest != CANONICAL_SCHEMA_SQL_SHA256
        ):
            raise HostAuthoritySeparationError("migration permit binding mismatch")
        if (
            request.repository_evidence_digest != repository_evidence.digest()
            or request.pre_schema_digest != pre_schema_evidence.digest()
            or before.schema_digest != pre_schema_evidence.digest()
            or before.database_sha256 != pre_schema_evidence.source_database_sha256
        ):
            raise HostAuthoritySeparationError("migration provenance drift")
        snapshot = snapshot_evidence.attestation
        if (
            request.live_database_sha256 != before.database_sha256
            or request.snapshot_sha256 != snapshot.snapshot_sha256
            or snapshot.source_observation_digest != before.digest()
        ):
            raise HostAuthoritySeparationError("snapshot currentness drift")
        post = derive_expected_post_schema_evidence(pre_schema_evidence)
        if (
            request.expected_post_schema_digest != post.digest()
            or plan.certified_post_schema_digest != post.digest()
        ):
            raise HostAuthoritySeparationError("post-schema provenance drift")
        expected = _migration_currentness_digest(
            request,
            repository_evidence,
            before,
            pre_schema_evidence,
            snapshot_evidence,
            post,
        )
        if (
            permit.currentness_digest != expected
            or permit.recovery_evidence_digest != snapshot_evidence.digest()
        ):
            raise HostAuthoritySeparationError(
                "migration permit stale currentness evidence"
            )
        return permit

    @staticmethod
    def verify_postcondition(
        before: SchemaObservation,
        after: SchemaObservation,
        *,
        pre_schema_evidence: SchemaManifestEvidence,
        after_schema_evidence: SchemaManifestEvidence,
    ) -> SchemaObservation:
        before.validate()
        after.validate()
        pre_schema_evidence.require_independent_pre_schema()
        after_schema_evidence.validate()
        if (
            before.schema_digest != pre_schema_evidence.digest()
            or before.database_sha256 != pre_schema_evidence.source_database_sha256
            or after.schema_digest != after_schema_evidence.digest()
        ):
            raise HostAuthoritySeparationError("schema observation provenance mismatch")
        expected = derive_expected_post_schema_evidence(pre_schema_evidence)
        if (
            after_schema_evidence.digest() != expected.digest()
            or after_schema_evidence.provenance_digest != expected.provenance_digest
        ):
            raise HostAuthoritySeparationError("post-schema manifest mismatch")
        if (
            before.pr_bootstrap_rows != after.pr_bootstrap_rows
            or before.authority_lineage_rows != after.authority_lineage_rows
        ):
            raise HostAuthoritySeparationError(
                "historical authority rows changed during migration"
            )
        required = set(PROVISIONING_TABLES + PRESERVED_TABLES + PROVISIONING_TRIGGERS)
        if not required.issubset(set(after.objects)):
            raise HostAuthoritySeparationError("partial migration denied")
        if after.database_sha256 == before.database_sha256:
            raise HostAuthoritySeparationError(
                "migration produced no database state change"
            )
        return after

    @staticmethod
    def verify_receipt(
        request: SchemaMigrationRequest,
        permit: BrokerPermit,
        before: SchemaObservation,
        pre_schema_evidence: SchemaManifestEvidence,
        snapshot_evidence: SnapshotProvenanceEvidence,
        after: SchemaObservation,
        after_schema_evidence: SchemaManifestEvidence,
        receipt: MigrationReceipt,
    ) -> MigrationReceipt:
        request.validate()
        permit.validate()
        before.validate()
        pre_schema_evidence.require_independent_pre_schema()
        snapshot_evidence.validate()
        after.validate()
        after_schema_evidence.validate()
        receipt.validate()
        snapshot = snapshot_evidence.attestation
        if (
            permit.operation_kind != "MIGRATE_EXACT_SCHEMA"
            or permit.request_digest != request.digest()
        ):
            raise HostAuthoritySeparationError("migration permit/request mismatch")
        if (
            receipt.request_digest != request.digest()
            or receipt.permit_digest != permit.digest()
        ):
            raise HostAuthoritySeparationError("migration receipt binding mismatch")
        if (
            receipt.snapshot_sha256 != request.snapshot_sha256
            or receipt.snapshot_sha256 != snapshot.snapshot_sha256
        ):
            raise HostAuthoritySeparationError("migration receipt snapshot mismatch")
        if (
            receipt.pre_schema_digest != request.pre_schema_digest
            or receipt.pre_schema_digest != before.schema_digest
            or receipt.pre_schema_digest != pre_schema_evidence.digest()
        ):
            raise HostAuthoritySeparationError("migration receipt pre-schema mismatch")
        if (
            receipt.preserved_pr_bootstrap_rows,
            receipt.preserved_authority_lineage_rows,
        ) != (before.pr_bootstrap_rows, before.authority_lineage_rows):
            raise HostAuthoritySeparationError(
                "migration receipt historical row mismatch"
            )
        if receipt.status == "MIGRATED":
            BoundedSchemaMigrationBroker.verify_postcondition(
                before,
                after,
                pre_schema_evidence=pre_schema_evidence,
                after_schema_evidence=after_schema_evidence,
            )
            if receipt.post_schema_digest != after.schema_digest:
                raise HostAuthoritySeparationError(
                    "migration receipt post-schema mismatch"
                )
        else:
            if (
                after.database_sha256 != before.database_sha256
                or after.schema_digest != before.schema_digest
                or receipt.post_schema_digest != before.schema_digest
            ):
                raise HostAuthoritySeparationError(
                    "migration rollback receipt mismatch"
                )
        return receipt
