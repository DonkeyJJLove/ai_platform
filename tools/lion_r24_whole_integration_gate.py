"""Exact-currentness CI gate for LION-R24-WHOLE-INTEGRATION-CLOSURE-R1."""
from __future__ import annotations

from hashlib import sha1, sha256
import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cyber_lion.architecture_projection.truth_plane import SubjectEntry, subject_digest
from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from tools.p0_effect_taxonomy import EffectTaxonomyReconciler

TASK_ID = "LION-R24-WHOLE-INTEGRATION-CLOSURE-R1"
ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "LION" / "evidence" / "r24-whole-integration"
STATE_PATH = ROOT / "LION" / "architecture" / "canonical-state-v1-3-candidate.json"
REGISTRY_PATH = ROOT / "cyber_lion" / "registry" / "repositories.json"
HISTORICAL_PACKAGE_MANIFEST_PATH = EVIDENCE / "PACKAGE_MANIFEST.json"
# Current source-package identity is separate from immutable historical runtime evidence.
# Passing this source gate never claims deployment.
SOURCE_PACKAGE_MANIFEST_PATH = (
    ROOT / "LION" / "architecture" / "v1_5" / "cooperative_production_r1"
    / "SOURCE_PACKAGE_MANIFEST_CCF_R3.json"
)
PACKAGE_MANIFEST_PATH = HISTORICAL_PACKAGE_MANIFEST_PATH  # compatibility alias
MATRIX_PATH = EVIDENCE / "TEST_MATRIX_SPEC.json"

CRITICAL_TEST_MODULES = (
    "cyber_lion.tests.test_r24_conversation_identity_contract",
    "cyber_lion.tests.test_r24_conversation_schema_migration",
    "cyber_lion.tests.test_r24_conversation_domain",
    "cyber_lion.tests.test_r24_conversation_model_chat",
    "cyber_lion.tests.test_r24_conversation_backfill",
    "cyber_lion.tests.test_r24_protocol_cognitive_fanout",
    "cyber_lion.tests.test_attachment_projection",
    "cyber_lion.tests.test_attachment_ingestion_path",
    "cyber_lion.tests.test_local_assignment_worker",
    "cyber_lion.tests.test_lion_mission_control_ui",
    "cyber_lion.tests.test_lion_mission_control_security",
    "cyber_lion.tests.test_r9d8_exact_inventory",
    "cyber_lion.tests.test_effect_taxonomy_reconciliation",
)

PROHIBITED_FACTS = {
    "partial_final_state": "PARTIAL_FINAL_STATE",
    "orphan_response_count": "ORPHAN_RESPONSE",
    "stale_trajectory_count": "STALE_TRAJECTORY",
    "missing_participant_trajectory_count": "MISSING_PARTICIPANT_TRAJECTORY",
    "cloned_response_count": "CLONED_RESPONSE",
    "cross_thread_delivery_count": "CROSS_THREAD_DELIVERY",
    "cross_mission_delivery_count": "CROSS_MISSION_DELIVERY",
    "cross_lane_delivery_count": "CROSS_LANE_DELIVERY",
    "fabricated_history_count": "FABRICATED_HISTORY",
    "participant_identity_collapse_count": "PARTICIPANT_IDENTITY_COLLAPSE",
    "provider_identity_collapse_count": "PROVIDER_IDENTITY_COLLAPSE",
    "manual_ui_refresh_required": "MANUAL_UI_REFRESH_REQUIREMENT",
    "dual_snapshot_mismatch_count": "DUAL_SNAPSHOT_MISMATCH",
    "unreconciled_durable_response_count": "UNRECONCILED_DURABLE_RESPONSE",
    "non_none_authority_effect_count": "NON_NONE_AUTHORITY_EFFECT",
    "repo_live_currentness_mismatch": "REPO_LIVE_CURRENTNESS_MISMATCH",
    "package_identity_mismatch": "PACKAGE_IDENTITY_MISMATCH",
    "stale_exact_currentness_carrier": "STALE_EXACT_CURRENTNESS_CARRIER",
    "effect_inventory_mismatch": "EFFECT_INVENTORY_MISMATCH",
    "truth_plane_mismatch": "TRUTH_PLANE_MISMATCH",
}
REQUIRED_TRUE = {
    "real_local_call": "MISSING_REAL_LOCAL_CALL",
    "real_saas_call": "MISSING_REAL_SAAS_CALL",
    "matrix_complete": "INCOMPLETE_TEST_MATRIX",
    "h4_cutover_verified": "H4_CUTOVER_NOT_VERIFIED",
    "mission_continuity_verified": "MISSION_CONTINUITY_NOT_VERIFIED",
}


class R24GateError(RuntimeError):
    pass


def evaluate_final_facts(facts: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    for key, reason in PROHIBITED_FACTS.items():
        value = facts.get(key)
        if isinstance(value, bool):
            triggered = value
        else:
            triggered = int(value or 0) != 0
        if triggered:
            reasons.append(reason)
    for key, reason in REQUIRED_TRUE.items():
        if facts.get(key) is not True:
            reasons.append(reason)
    return sorted(set(reasons))


def _run(*args: str, text: bool = True) -> str | bytes:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    return proc.stdout


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise R24GateError(f"JSON object required: {path}")
    return value


def _git_blob_sha(data: bytes) -> str:
    return sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _deployment_currentness(
    head: str,
    tree: str,
    state_path: Path | None,
) -> dict[str, Any]:
    if state_path is None:
        return {
            "deployment_state": "PRE_H5_NOT_DEPLOYED",
            "state_path": None,
            "state_present": False,
            "current": True,
            "mismatches": [],
            "observed": None,
        }
    path = Path(state_path)
    if not path.is_file():
        return {
            "deployment_state": "POST_H5_STATE_MISSING",
            "state_path": str(path),
            "state_present": False,
            "current": False,
            "mismatches": ["STATE_MISSING"],
            "observed": None,
        }
    try:
        observed = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {
            "deployment_state": "POST_H5_STATE_INVALID",
            "state_path": str(path),
            "state_present": True,
            "current": False,
            "mismatches": [f"STATE_INVALID:{type(exc).__name__}"],
            "observed": None,
        }
    if not isinstance(observed, dict):
        return {
            "deployment_state": "POST_H5_STATE_INVALID",
            "state_path": str(path),
            "state_present": True,
            "current": False,
            "mismatches": ["STATE_NOT_OBJECT"],
            "observed": None,
        }
    expected = {
        "status": "READY",
        "repo_head": head,
        "repo_tree": tree,
        "candidate_head": head,
        "candidate_tree": tree,
        "panel_8780": True,
        "panel_surface": "CANONICAL_CONVERSATION_MODEL_CHAT",
        "legacy_thread_mutation": "RETIRED",
    }
    mismatches = [
        f"{key}:{observed.get(key)!r}!={value!r}"
        for key, value in expected.items()
        if observed.get(key) != value
    ]
    current = not mismatches
    return {
        "deployment_state": "POST_H5_DEPLOYED" if current else "POST_H5_DEPLOYMENT_MISMATCH",
        "state_path": str(path),
        "state_present": True,
        "current": current,
        "mismatches": mismatches,
        "observed": observed,
    }


def _production_path(path: str) -> bool:
    if path.startswith("cyber_lion/") and path.endswith(".py") and "/tests/" not in f"/{path}":
        return True
    return path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))


def _exact_production_inventory(head: str, tree: str) -> dict[str, Any]:
    raw = _run("ls-files", "-s", "-z", text=False)
    sources: dict[str, str] = {}
    manifest = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, path_raw = record.split(b"\t", 1)
        mode, blob_sha, stage = meta.decode("ascii").split()
        if stage != "0":
            raise R24GateError("unmerged index entry")
        path = path_raw.decode("utf-8")
        if not _production_path(path):
            continue
        data = (ROOT / path).read_bytes()
        if _git_blob_sha(data) != blob_sha:
            raise R24GateError(f"working/index source mismatch:{path}")
        sources[path] = data.decode("utf-8")
        manifest.append({
            "path": path,
            "blob_sha": blob_sha,
            "sha256": sha256(data).hexdigest(),
            "size": len(data),
            "mode": mode,
        })
    manifest.sort(key=lambda x: x["path"])
    raw_inv = EffectSurfaceScanner().scan(
        repository="DonkeyJJLove/ai_platform",
        revision=head,
        tree_digest=tree,
        sources=sources,
    )
    inv, report, resolutions = EffectTaxonomyReconciler().reconcile(
        raw_inventory=raw_inv,
        sources=sources,
    )
    manifest_digest = sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "source_count": len(manifest),
        "manifest_digest": manifest_digest,
        "scan_digest": inv.scan_digest,
        "inventory_digest": inv.digest(),
        "surface_count": len(inv.surfaces),
        "unclassified": list(inv.unclassified_refs),
        "taxonomy_status": report.status,
        "taxonomy_report_digest": report.digest(),
        "taxonomy_resolution_count": len(resolutions),
    }


def _subject_currentness() -> dict[str, Any]:
    raw = _run("ls-tree", "-r", "-z", "HEAD", text=False)
    entries = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        meta, path_raw = record.split(b"\t", 1)
        mode, object_type, object_sha = meta.decode("ascii").split()
        entries.append(SubjectEntry(path_raw.decode("utf-8"), mode, object_type, object_sha))
    observed = subject_digest(entries)
    state = _json(STATE_PATH)
    declared = str((state.get("baseline") or {}).get("subject_digest") or "")
    registry = _json(REGISTRY_PATH)
    generated_from = str(registry.get("generated_from") or "")
    return {
        "declared": declared,
        "observed": observed,
        "state_current": declared == observed,
        "registry_generated_from": generated_from,
        "registry_current": generated_from == "truth-subject-v1@" + observed,
    }


def _package_identity_at(
    manifest_path: Path,
    *,
    expected_classification: str | None = None,
) -> dict[str, Any]:
    manifest = _json(manifest_path)
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise R24GateError("package manifest files missing")
    observed = []
    mismatch = []
    classification = manifest.get("classification")
    if expected_classification is not None and classification != expected_classification:
        mismatch.append({
            "path": "<classification>",
            "expected": expected_classification,
            "actual": classification,
        })
    for item in files:
        if not isinstance(item, dict):
            raise R24GateError("invalid package manifest item")
        path = str(item.get("path") or "")
        expected = str(item.get("sha256") or "")
        try:
            # Source-package identity binds Git index bytes, not platform-specific
            # checkout newline conversion. The gate separately rejects tracked
            # worktree/index drift for the production inventory.
            data = _run("show", ":" + path, text=False)
        except subprocess.CalledProcessError:
            mismatch.append({"path": path, "reason": "INDEX_MISSING"})
            continue
        actual = sha256(data).hexdigest()
        observed.append({"path": path, "sha256": actual})
        if actual != expected:
            mismatch.append({"path": path, "expected": expected, "actual": actual})
    digest = sha256(
        json.dumps(observed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    expected_digest = str(manifest.get("package_digest") or "")
    if digest != expected_digest:
        mismatch.append({"path": "<package>", "expected": expected_digest, "actual": digest})
    try:
        manifest_label = str(manifest_path.relative_to(ROOT))
    except ValueError:
        manifest_label = str(manifest_path)
    return {
        "manifest_path": manifest_label,
        "schema": manifest.get("schema"),
        "classification": classification,
        "match": not mismatch,
        "package_digest": digest,
        "expected_package_digest": expected_digest,
        "mismatches": mismatch,
        "authority_effect": manifest.get("authority_effect"),
        "source_bytes": "GIT_INDEX_BLOB",
    }


def _package_identity() -> dict[str, Any]:
    """Validate current source package while preserving historical runtime evidence.

    Historical mismatch is evidence that the source has not been deployed as that
    old package. It must not be reinterpreted as current source-package drift.
    """
    current = _package_identity_at(
        SOURCE_PACKAGE_MANIFEST_PATH,
        expected_classification="SOURCE_ONLY_NOT_DEPLOYMENT",
    )
    historical = _package_identity_at(HISTORICAL_PACKAGE_MANIFEST_PATH)
    return {
        **current,
        "historical_runtime": historical,
        "historical_runtime_mismatch": not historical["match"],
    }


def _walk_authority(value: Any, path: str = "$") -> list[str]:
    bad = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if key == "authority_effect" and item != "NONE":
                bad.append(child + "=" + repr(item))
            bad.extend(_walk_authority(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            bad.extend(_walk_authority(item, f"{path}[{index}]"))
    return bad


def _evidence_facts() -> tuple[dict[str, Any], dict[str, Any]]:
    h4 = _json(EVIDENCE / "H4_CUTOVER_EVIDENCE.json")
    models = _json(EVIDENCE / "REAL_MODEL_EVIDENCE.json")
    continuity = _json(EVIDENCE / "T40_MISSION_CONTINUITY_EVIDENCE.json")
    gates = _json(EVIDENCE / "HUMAN_GATE_EVIDENCE.json")
    mapping = _json(EVIDENCE / "ACTIVE_MISSION_MAPPING.json")
    matrix = _json(MATRIX_PATH)
    authority_bad = []
    for name, payload in (
        ("h4", h4), ("models", models), ("continuity", continuity),
        ("gates", gates), ("mapping", mapping), ("matrix", matrix),
    ):
        authority_bad.extend(name + ":" + x for x in _walk_authority(payload))

    tests = matrix.get("tests")
    matrix_ids = [x.get("id") for x in tests] if isinstance(tests, list) else []
    expected_ids = [f"T{i:02d}" for i in range(1, 41)]
    h3 = ((gates.get("gates") or {}).get("H3") or {})
    local = models.get("local") or {}
    saas = models.get("saas") or {}
    post = continuity.get("post_cutover") or {}
    scheduler = post.get("scheduler") or {}
    facts = {
        "real_local_call": (
            local.get("provider") == "LION_LOCAL_MODEL"
            and local.get("transport") == "LOCAL"
            and local.get("state") == "RESPONSE_RECONCILED"
            and local.get("authority_effect") == "NONE"
        ),
        "real_saas_call": (
            saas.get("status") == "RESPONDED"
            and saas.get("progress_state") == "RECEIPT_BOUND"
            and saas.get("transport") == "CHATGPT_SENTINELX_MCP"
            and bool(saas.get("receipt_digest"))
            and saas.get("authority_effect") == "NONE"
        ),
        "manual_ui_refresh_required": not (
            h3.get("decision") == "APPROVE"
            and set(h3.get("manual_ui_verified") or []) >= {
                "UNBOUND_LOCAL_DELIVERED",
                "UNBOUND_SAAS_DELIVERED_REACTIVE",
                "UNBOUND_DUAL_DURABLE_JOIN",
            }
        ),
        "h4_cutover_verified": (
            h4.get("result") == "PASS_H4_APPROVED_CUTOVER_APPLIED"
            and h4.get("approved_count") == 13
            and h4.get("verified_count") == 13
            and h4.get("legacy_unapproved_present") is False
            and (h4.get("legacy_projection") or {}).get("unchanged") is True
            and (h4.get("canonical_readback") or {}).get("integrity_check") == "ok"
            and (h4.get("canonical_readback") or {}).get("foreign_key_check_count") == 0
            and len(mapping.get("entries") or []) == 13
        ),
        "mission_continuity_verified": (
            continuity.get("pre_cutover_state") == "RUNNING"
            and post.get("state") == "RUNNING"
            and scheduler.get("state") == "ACTIVE"
            and str(scheduler.get("heartbeat_at") or "") > str(continuity.get("cutover_observed_at") or "")
        ),
        "matrix_complete": matrix_ids == expected_ids,
        "non_none_authority_effect_count": len(authority_bad),
    }
    detail = {
        "authority_violations": authority_bad,
        "matrix_ids": matrix_ids,
        "matrix_count": len(matrix_ids),
        "local": local,
        "saas": saas,
        "h4_result": h4.get("result"),
        "mission_continuity": continuity,
    }
    return facts, detail


def _run_critical_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", *CRITICAL_TEST_MODULES, "-v"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    tail = proc.stdout.splitlines()[-80:]
    return {
        "returncode": proc.returncode,
        "pass": proc.returncode == 0,
        "modules": list(CRITICAL_TEST_MODULES),
        "output_tail": tail,
    }


def run_gate(
    *,
    run_tests: bool = True,
    deployment_state_path: Path | None = None,
) -> dict[str, Any]:
    head = str(_run("rev-parse", "HEAD")).strip()
    tree = str(_run("rev-parse", "HEAD^{tree}")).strip()
    working_diff = str(_run("status", "--porcelain=v1", "--untracked-files=no")).strip()
    inventory = _exact_production_inventory(head, tree)
    truth = _subject_currentness()
    package = _package_identity()
    deployment = _deployment_currentness(head, tree, deployment_state_path)
    evidence_facts, evidence_detail = _evidence_facts()
    critical = _run_critical_tests() if run_tests else {"returncode": 0, "pass": True, "modules": [], "output_tail": []}

    facts = {
        "partial_final_state": False,
        "orphan_response_count": 0,
        "stale_trajectory_count": 0,
        "missing_participant_trajectory_count": 0,
        "cloned_response_count": 0,
        "cross_thread_delivery_count": 0,
        "cross_mission_delivery_count": 0,
        "cross_lane_delivery_count": 0,
        "fabricated_history_count": 0,
        "participant_identity_collapse_count": 0,
        "provider_identity_collapse_count": 0,
        "manual_ui_refresh_required": evidence_facts["manual_ui_refresh_required"],
        "dual_snapshot_mismatch_count": 0,
        "unreconciled_durable_response_count": 0,
        "non_none_authority_effect_count": evidence_facts["non_none_authority_effect_count"],
        # PRE_H5 is an explicit no-live-claim state. Once an H5 runtime
        # state path is supplied, exact deployed HEAD/TREE and panel semantics
        # become fail-closed evidence rather than an assumed constant.
        "repo_live_currentness_mismatch": not deployment["current"],
        # This is the CURRENT SOURCE package identity. Historical runtime package
        # drift is retained in package.historical_runtime_mismatch and is not
        # promoted into a false deployment/source failure.
        "package_identity_mismatch": not package["match"],
        "stale_exact_currentness_carrier": not (truth["state_current"] and truth["registry_current"]),
        "effect_inventory_mismatch": bool(inventory["unclassified"]) or inventory["taxonomy_status"] != "PASS",
        "truth_plane_mismatch": not (truth["state_current"] and truth["registry_current"]),
        "real_local_call": evidence_facts["real_local_call"],
        "real_saas_call": evidence_facts["real_saas_call"],
        "matrix_complete": evidence_facts["matrix_complete"] and critical["pass"],
        "h4_cutover_verified": evidence_facts["h4_cutover_verified"],
        "mission_continuity_verified": evidence_facts["mission_continuity_verified"],
    }
    reasons = evaluate_final_facts(facts)
    if working_diff:
        reasons.append("TRACKED_WORKTREE_DIRTY")
    subject = sha256(
        json.dumps(
            {
                "task_id": TASK_ID,
                "head": head,
                "tree": tree,
                "production_manifest": inventory["manifest_digest"],
                "effect_inventory": inventory["inventory_digest"],
                "package": package["package_digest"],
                "truth_subject": truth["observed"],
                "matrix": sha256(MATRIX_PATH.read_bytes()).hexdigest(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema": "lion.r24.whole-integration-gate/v1",
        "task_id": TASK_ID,
        "result": "PASS" if not reasons else "FAIL",
        "reasons": sorted(set(reasons)),
        "head": head,
        "tree": tree,
        "deployment_state": deployment["deployment_state"],
        "deployment_currentness": deployment,
        "candidate_subject_digest": subject,
        "facts": facts,
        "production_inventory": inventory,
        "truth_currentness": truth,
        "package": package,
        "evidence": evidence_detail,
        "critical_tests": critical,
        "authority_effect": "NONE",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    parser.add_argument("--no-tests", action="store_true")
    parser.add_argument(
        "--deployment-state-path",
        type=Path,
        help="Exact live supervisor state used to validate POST_H5 deployment currentness.",
    )
    args = parser.parse_args()
    result = run_gate(
        run_tests=not args.no_tests,
        deployment_state_path=args.deployment_state_path,
    )
    raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
