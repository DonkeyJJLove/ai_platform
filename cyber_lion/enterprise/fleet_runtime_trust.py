"""F005-I runtime trust-root provisioning.

The provisioner reads explicit immutable manifests and exact external artifact bytes,
derives the existing fleet trust-pin contracts, and materializes only trust-binding
JSON. It does not produce verification evidence, reconciliation evidence, mission
state, fleet closure, or operational authority.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from cyber_lion.contracts.fleet_reconciliation import ReconciliationTrustPins
from cyber_lion.contracts.fleet_runtime_trust import (
    F005_H_PINS_PATH,
    PROVISIONING_RECEIPT_PATH,
    RECONCILIATION_TRUST_PATH,
    REPOSITORY,
    RUNTIME_INSTANCE_ID,
    TRUST_ROOT,
    VERIFICATION_TRUST_PATH,
    RuntimeTrustProvisioningConfig,
    RuntimeTrustProvisioningReceipt,
    canonical_json,
    f005_h_pins_payload,
)
from cyber_lion.contracts.fleet_status import VerificationTrustPins
from cyber_lion.enterprise.verifier_identity_runtime import RUNTIME_FACTORY_VERSION


class FleetRuntimeTrustError(RuntimeError):
    pass


_SHA256_HEX = frozenset("0123456789abcdef")
_MAX_MANIFEST_BYTES = 1024 * 1024


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise FleetRuntimeTrustError("duplicate JSON key denied")
        value[key] = item
    return value


def _read_json(path: Path) -> tuple[dict[str, Any], bytes, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise FleetRuntimeTrustError(f"runtime manifest unavailable: {path}") from exc
    if not raw or len(raw) > _MAX_MANIFEST_BYTES:
        raise FleetRuntimeTrustError("runtime manifest size invalid")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FleetRuntimeTrustError("runtime manifest must be UTF-8") from exc
    try:
        value = json.loads(decoded, object_pairs_hook=_strict_object)
    except (json.JSONDecodeError, FleetRuntimeTrustError) as exc:
        raise FleetRuntimeTrustError("runtime manifest JSON invalid") from exc
    if not isinstance(value, dict):
        raise FleetRuntimeTrustError("runtime manifest must be a JSON object")
    canonical = canonical_json(value)
    return value, raw, sha256(canonical).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            while True:
                block = handle.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
    except OSError as exc:
        raise FleetRuntimeTrustError(f"external runtime artifact unavailable: {path}") from exc
    return digest.hexdigest()


def _sha256_hex(value: object, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in _SHA256_HEX for char in value)
    ):
        raise FleetRuntimeTrustError(f"{name} must be lowercase sha256 hex")
    return value


def _text(value: object, name: str, *, limit: int = 4096) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or "\x00" in value
    ):
        raise FleetRuntimeTrustError(f"{name} invalid")
    return value


def _exact_keys(value: Mapping[str, Any], required: set[str], name: str) -> None:
    if set(value) != required:
        raise FleetRuntimeTrustError(f"{name} keys do not match canonical contract")


def _resolve_repository_root(raw: str) -> Path:
    path = Path(_text(raw, "repository_root"))
    if not path.is_absolute():
        raise FleetRuntimeTrustError("repository root must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise FleetRuntimeTrustError("repository root unavailable") from exc
    if not resolved.is_dir():
        raise FleetRuntimeTrustError("repository root must be a directory")
    return resolved


def _external_file(raw: str, repository_root: Path, name: str) -> Path:
    path = Path(_text(raw, name))
    if not path.is_absolute():
        raise FleetRuntimeTrustError(f"{name} must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise FleetRuntimeTrustError(f"{name} unavailable") from exc
    if not resolved.is_file():
        raise FleetRuntimeTrustError(f"{name} must be a file")
    if resolved == repository_root or repository_root in resolved.parents:
        raise FleetRuntimeTrustError(f"{name} must remain outside repository")
    return resolved


def _physical_output_paths(
    repository_root: Path,
    physical_output_root: Path | None,
) -> dict[str, Path]:
    if physical_output_root is None:
        if os.name != "nt":
            raise FleetRuntimeTrustError(
                "F005-I production provisioning requires Windows lion-runtime"
            )
        root = Path(TRUST_ROOT)
    else:
        root = Path(physical_output_root)
        if not root.is_absolute():
            raise FleetRuntimeTrustError("physical trust output root must be absolute")
    resolved_root = root.resolve(strict=False)
    if resolved_root == repository_root or repository_root in resolved_root.parents:
        raise FleetRuntimeTrustError("runtime trust outputs must remain outside repository")
    return {
        "root": resolved_root,
        "verification": resolved_root / Path(VERIFICATION_TRUST_PATH).name,
        "reconciliation": resolved_root / Path(RECONCILIATION_TRUST_PATH).name,
        "pins": resolved_root / Path(F005_H_PINS_PATH).name,
        "receipt": resolved_root / Path(PROVISIONING_RECEIPT_PATH).name,
    }


def _validate_anchor_manifest(
    value: Mapping[str, Any],
    *,
    kind: str,
    expected_anchor_id: str,
) -> None:
    _exact_keys(
        value,
        {
            "schema_version",
            "kind",
            "repository",
            "runtime_instance_id",
            "trust_anchor_id",
            "anchor",
        },
        "trust anchor manifest",
    )
    if value["schema_version"] != "1.0.0" or value["kind"] != kind:
        raise FleetRuntimeTrustError("trust anchor manifest version/kind mismatch")
    if value["repository"] != REPOSITORY:
        raise FleetRuntimeTrustError("trust anchor repository substitution denied")
    if value["runtime_instance_id"] != RUNTIME_INSTANCE_ID:
        raise FleetRuntimeTrustError("trust anchor runtime substitution denied")
    if value["trust_anchor_id"] != expected_anchor_id:
        raise FleetRuntimeTrustError("trust anchor substitution denied")
    if not isinstance(value["anchor"], dict) or not value["anchor"]:
        raise FleetRuntimeTrustError("trust anchor manifest material missing")


def _validate_verification_manifest(
    value: Mapping[str, Any],
    *,
    config: RuntimeTrustProvisioningConfig,
    implementation_digest: str,
    anchor_digest: str,
) -> None:
    _exact_keys(
        value,
        {
            "schema_version",
            "kind",
            "repository",
            "runtime_instance_id",
            "runtime_factory_version",
            "verifier_id",
            "verifier_identity",
            "verifier_implementation_sha256",
            "trust_anchor_id",
            "trust_anchor_sha256",
        },
        "verification runtime manifest",
    )
    if value["schema_version"] != "1.0.0" or value["kind"] != "VERIFICATION_RUNTIME_TRUST":
        raise FleetRuntimeTrustError("verification runtime manifest version/kind mismatch")
    if value["repository"] != config.repository:
        raise FleetRuntimeTrustError("verification repository substitution denied")
    if value["runtime_instance_id"] != config.runtime_instance_id:
        raise FleetRuntimeTrustError("verification runtime substitution denied")
    if value["runtime_factory_version"] != RUNTIME_FACTORY_VERSION:
        raise FleetRuntimeTrustError("verifier identity runtime contract version mismatch")
    if value["verifier_id"] != config.expected_verifier_id:
        raise FleetRuntimeTrustError("verifier identity substitution denied")
    if value["trust_anchor_id"] != config.expected_verification_trust_anchor_id:
        raise FleetRuntimeTrustError("verification trust anchor substitution denied")
    if not isinstance(value["verifier_identity"], dict) or not value["verifier_identity"]:
        raise FleetRuntimeTrustError("explicit verifier identity manifest missing")
    if _sha256_hex(
        value["verifier_implementation_sha256"],
        "verifier_implementation_sha256",
    ) != implementation_digest:
        raise FleetRuntimeTrustError("verifier implementation digest mismatch")
    if _sha256_hex(value["trust_anchor_sha256"], "trust_anchor_sha256") != anchor_digest:
        raise FleetRuntimeTrustError("verification trust anchor digest mismatch")


def _validate_reconciliation_manifest(
    value: Mapping[str, Any],
    *,
    config: RuntimeTrustProvisioningConfig,
    implementation_digest: str,
    anchor_digest: str,
) -> None:
    _exact_keys(
        value,
        {
            "schema_version",
            "kind",
            "repository",
            "runtime_instance_id",
            "source_id",
            "source_instance_id",
            "source_identity",
            "source_implementation_sha256",
            "trust_anchor_id",
            "trust_anchor_sha256",
        },
        "reconciliation runtime manifest",
    )
    if value["schema_version"] != "1.0.0" or value["kind"] != "RECONCILIATION_RUNTIME_TRUST":
        raise FleetRuntimeTrustError("reconciliation runtime manifest version/kind mismatch")
    if value["repository"] != config.repository:
        raise FleetRuntimeTrustError("reconciliation repository substitution denied")
    if value["runtime_instance_id"] != config.runtime_instance_id:
        raise FleetRuntimeTrustError("reconciliation runtime substitution denied")
    if value["source_id"] != config.expected_reconciliation_source_id:
        raise FleetRuntimeTrustError("reconciliation source substitution denied")
    if value["source_instance_id"] != config.expected_reconciliation_source_instance_id:
        raise FleetRuntimeTrustError("reconciliation source instance substitution denied")
    if value["trust_anchor_id"] != config.expected_reconciliation_trust_anchor_id:
        raise FleetRuntimeTrustError("reconciliation trust anchor substitution denied")
    if not isinstance(value["source_identity"], dict) or not value["source_identity"]:
        raise FleetRuntimeTrustError("explicit reconciliation source identity missing")
    if _sha256_hex(
        value["source_implementation_sha256"],
        "source_implementation_sha256",
    ) != implementation_digest:
        raise FleetRuntimeTrustError("reconciliation source implementation digest mismatch")
    if _sha256_hex(value["trust_anchor_sha256"], "trust_anchor_sha256") != anchor_digest:
        raise FleetRuntimeTrustError("reconciliation trust anchor digest mismatch")


def _verifier_identity_digest(
    manifest: Mapping[str, Any],
    *,
    implementation_digest: str,
    anchor_digest: str,
) -> str:
    payload = {
        "schema_version": manifest["schema_version"],
        "repository": manifest["repository"],
        "runtime_instance_id": manifest["runtime_instance_id"],
        "runtime_factory_version": manifest["runtime_factory_version"],
        "verifier_id": manifest["verifier_id"],
        "verifier_identity": manifest["verifier_identity"],
        "verifier_implementation_digest": implementation_digest,
        "trust_anchor_id": manifest["trust_anchor_id"],
        "trust_anchor_digest": anchor_digest,
    }
    return sha256(
        b"LION/F005-I-VERIFIER-IDENTITY/1\0" + canonical_json(payload)
    ).hexdigest()


def _immutable_output_set(paths: Mapping[str, Path], payloads: Mapping[str, bytes]) -> None:
    root = paths["root"]
    root.mkdir(parents=True, exist_ok=True)
    targets = {name: paths[name] for name in ("verification", "reconciliation", "pins", "receipt")}
    existing = {name: path.is_file() for name, path in targets.items()}
    if any(existing.values()) and not all(existing.values()):
        raise FleetRuntimeTrustError("partial runtime trust output set denied")
    if all(existing.values()):
        for name, target in targets.items():
            try:
                current = target.read_bytes()
            except OSError as exc:
                raise FleetRuntimeTrustError("existing trust output unreadable") from exc
            if current != payloads[name]:
                raise FleetRuntimeTrustError("immutable runtime trust output substitution denied")
        return

    created: list[Path] = []
    temporary: list[Path] = []
    try:
        for name, target in targets.items():
            fd, temp_name = tempfile.mkstemp(prefix=".f005-i-", dir=str(root))
            temp_path = Path(temp_name)
            temporary.append(temp_path)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(payloads[name])
                    handle.flush()
                    os.fsync(handle.fileno())
                os.link(temp_path, target)
                created.append(target)
            finally:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
        for target in targets.values():
            if not target.is_file():
                raise FleetRuntimeTrustError("runtime trust output materialization incomplete")
    except Exception:
        for target in created:
            try:
                target.unlink()
            except FileNotFoundError:
                pass
        raise
    finally:
        for temp_path in temporary:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass


def provision_runtime_trust(
    config: RuntimeTrustProvisioningConfig,
    *,
    repository_root: str,
    verification_manifest_path: str,
    verifier_implementation_path: str,
    verification_anchor_manifest_path: str,
    reconciliation_manifest_path: str,
    reconciliation_implementation_path: str,
    reconciliation_anchor_manifest_path: str,
    physical_output_root: Path | None = None,
) -> RuntimeTrustProvisioningReceipt:
    config.validate()
    repo_root = _resolve_repository_root(repository_root)
    paths = {
        "verification_manifest": _external_file(
            verification_manifest_path, repo_root, "verification_manifest_path"
        ),
        "verifier_implementation": _external_file(
            verifier_implementation_path, repo_root, "verifier_implementation_path"
        ),
        "verification_anchor": _external_file(
            verification_anchor_manifest_path,
            repo_root,
            "verification_anchor_manifest_path",
        ),
        "reconciliation_manifest": _external_file(
            reconciliation_manifest_path, repo_root, "reconciliation_manifest_path"
        ),
        "reconciliation_implementation": _external_file(
            reconciliation_implementation_path,
            repo_root,
            "reconciliation_implementation_path",
        ),
        "reconciliation_anchor": _external_file(
            reconciliation_anchor_manifest_path,
            repo_root,
            "reconciliation_anchor_manifest_path",
        ),
    }
    outputs = _physical_output_paths(repo_root, physical_output_root)

    verification_manifest, _, verification_manifest_digest = _read_json(
        paths["verification_manifest"]
    )
    verification_anchor, verification_anchor_raw, _ = _read_json(
        paths["verification_anchor"]
    )
    reconciliation_manifest, _, reconciliation_manifest_digest = _read_json(
        paths["reconciliation_manifest"]
    )
    reconciliation_anchor, reconciliation_anchor_raw, _ = _read_json(
        paths["reconciliation_anchor"]
    )

    verifier_implementation_digest = _sha256_file(paths["verifier_implementation"])
    reconciliation_implementation_digest = _sha256_file(
        paths["reconciliation_implementation"]
    )
    verification_anchor_digest = sha256(verification_anchor_raw).hexdigest()
    reconciliation_anchor_digest = sha256(reconciliation_anchor_raw).hexdigest()

    _validate_anchor_manifest(
        verification_anchor,
        kind="VERIFICATION_TRUST_ANCHOR",
        expected_anchor_id=config.expected_verification_trust_anchor_id,
    )
    _validate_anchor_manifest(
        reconciliation_anchor,
        kind="RECONCILIATION_TRUST_ANCHOR",
        expected_anchor_id=config.expected_reconciliation_trust_anchor_id,
    )
    _validate_verification_manifest(
        verification_manifest,
        config=config,
        implementation_digest=verifier_implementation_digest,
        anchor_digest=verification_anchor_digest,
    )
    _validate_reconciliation_manifest(
        reconciliation_manifest,
        config=config,
        implementation_digest=reconciliation_implementation_digest,
        anchor_digest=reconciliation_anchor_digest,
    )

    verifier_identity_digest = _verifier_identity_digest(
        verification_manifest,
        implementation_digest=verifier_implementation_digest,
        anchor_digest=verification_anchor_digest,
    )
    verification_pins = VerificationTrustPins(
        verifier_id=_text(verification_manifest["verifier_id"], "verifier_id", limit=256),
        verifier_identity_digest=verifier_identity_digest,
        verifier_implementation_digest=verifier_implementation_digest,
        trust_anchor_id=_text(
            verification_manifest["trust_anchor_id"], "trust_anchor_id", limit=256
        ),
        trust_anchor_digest=verification_anchor_digest,
    ).validate()
    reconciliation_pins = ReconciliationTrustPins(
        source_id=_text(reconciliation_manifest["source_id"], "source_id", limit=256),
        source_instance_id=_text(
            reconciliation_manifest["source_instance_id"],
            "source_instance_id",
            limit=256,
        ),
        source_implementation_digest=reconciliation_implementation_digest,
        trust_anchor_id=_text(
            reconciliation_manifest["trust_anchor_id"],
            "reconciliation_trust_anchor_id",
            limit=256,
        ),
    ).validate()

    pins = f005_h_pins_payload(verification_pins, reconciliation_pins)
    verification_bytes = canonical_json(asdict(verification_pins)) + b"\n"
    reconciliation_bytes = canonical_json(asdict(reconciliation_pins)) + b"\n"
    pins_bytes = canonical_json(pins) + b"\n"
    pins_digest = sha256(pins_bytes).hexdigest()
    outputs_digest = sha256(
        b"LION/F005-I-OUTPUTS/1\0"
        + canonical_json(
            {
                "verification_trust_digest": sha256(verification_bytes).hexdigest(),
                "reconciliation_trust_digest": sha256(reconciliation_bytes).hexdigest(),
                "f005_h_pins_digest": pins_digest,
            }
        )
    ).hexdigest()

    receipt_payload = {
        "repository": config.repository,
        "current_master": config.current_master,
        "current_master_tree": config.current_master_tree,
        "runtime_instance_id": config.runtime_instance_id,
        "config_digest": config.digest(),
        "verification_manifest_digest": verification_manifest_digest,
        "verifier_identity_digest": verifier_identity_digest,
        "verifier_implementation_digest": verifier_implementation_digest,
        "verification_anchor_manifest_digest": verification_anchor_digest,
        "reconciliation_manifest_digest": reconciliation_manifest_digest,
        "reconciliation_source_implementation_digest": reconciliation_implementation_digest,
        "reconciliation_anchor_manifest_digest": reconciliation_anchor_digest,
        "f005_h_pins_digest": pins_digest,
        "outputs_digest": outputs_digest,
        "asserts_verification_pass": False,
        "asserts_fleet_closure": False,
    }
    receipt_id = sha256(
        b"LION/F005-I-RUNTIME-TRUST-RECEIPT/1\0" + canonical_json(receipt_payload)
    ).hexdigest()
    receipt = RuntimeTrustProvisioningReceipt(
        schema_version="1.0.0",
        receipt_id=receipt_id,
        **receipt_payload,
    ).validate()
    receipt_bytes = canonical_json(asdict(receipt)) + b"\n"

    _immutable_output_set(
        outputs,
        {
            "verification": verification_bytes,
            "reconciliation": reconciliation_bytes,
            "pins": pins_bytes,
            "receipt": receipt_bytes,
        },
    )
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--expected-master", required=True)
    parser.add_argument("--expected-master-tree", required=True)
    parser.add_argument("--runtime-instance", required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--expected-verifier-id", required=True)
    parser.add_argument("--expected-verification-trust-anchor-id", required=True)
    parser.add_argument("--expected-reconciliation-source-id", required=True)
    parser.add_argument("--expected-reconciliation-source-instance-id", required=True)
    parser.add_argument("--expected-reconciliation-trust-anchor-id", required=True)
    parser.add_argument("--verification-manifest", required=True)
    parser.add_argument("--verifier-implementation", required=True)
    parser.add_argument("--verification-anchor-manifest", required=True)
    parser.add_argument("--reconciliation-manifest", required=True)
    parser.add_argument("--reconciliation-implementation", required=True)
    parser.add_argument("--reconciliation-anchor-manifest", required=True)
    args = parser.parse_args(argv)

    config = RuntimeTrustProvisioningConfig(
        repository=args.repository,
        current_master=args.expected_master,
        current_master_tree=args.expected_master_tree,
        runtime_instance_id=args.runtime_instance,
        expected_verifier_id=args.expected_verifier_id,
        expected_verification_trust_anchor_id=args.expected_verification_trust_anchor_id,
        expected_reconciliation_source_id=args.expected_reconciliation_source_id,
        expected_reconciliation_source_instance_id=args.expected_reconciliation_source_instance_id,
        expected_reconciliation_trust_anchor_id=args.expected_reconciliation_trust_anchor_id,
    ).validate()
    receipt = provision_runtime_trust(
        config,
        repository_root=args.repository_root,
        verification_manifest_path=args.verification_manifest,
        verifier_implementation_path=args.verifier_implementation,
        verification_anchor_manifest_path=args.verification_anchor_manifest,
        reconciliation_manifest_path=args.reconciliation_manifest,
        reconciliation_implementation_path=args.reconciliation_implementation,
        reconciliation_anchor_manifest_path=args.reconciliation_anchor_manifest,
    )
    print(
        json.dumps(
            {
                "schema_version": receipt.schema_version,
                "receipt_id": receipt.receipt_id,
                "outputs_digest": receipt.outputs_digest,
                "f005_h_pins_digest": receipt.f005_h_pins_digest,
                "asserts_verification_pass": receipt.asserts_verification_pass,
                "asserts_fleet_closure": receipt.asserts_fleet_closure,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
