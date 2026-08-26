"""Closed-world GitHub issue-comment boundary for repository-maintenance receipts.

The boundary accepts only the canonical repository-maintenance control event on issue 144,
derives either one failure receipt or one successful observation receipt, checks a durable
issue-comment replay ledger before the write, posts to the single canonical issue-comments
endpoint, and read-backs the exact created comment before success. It cannot dispatch
workflows, mutate refs, or accept caller-selected URLs or methods.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

from cyber_lion.contracts.repository_maintenance_sandbox import (
    RepositoryMaintenanceExecutionReceipt,
)
from cyber_lion.enterprise.repository_maintenance_mediated_cleanup import (
    RepositoryMaintenanceRequestEvidence,
    load_request_evidence,
)

CONTROL_ISSUE = 144
_FAILURE_PREFIX = "LION-REPOSITORY-MAINTENANCE-CONTROL-FAILURE v2"
_OBSERVATION_PREFIX = "LION-REPOSITORY-MAINTENANCE-OBSERVATION-RECEIPT v2"
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class RepositoryMaintenanceReceiptError(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(*parts: str) -> str:
    return sha256(
        b"LION/REPOSITORY-MAINTENANCE-RECEIPT/2\0"
        + "\0".join(parts).encode("utf-8")
    ).hexdigest()


def _bounded_diagnostic(path: Path) -> str:
    try:
        text = (
            path.read_text(encoding="utf-8", errors="replace").strip()
            if path.exists()
            else ""
        )
    except OSError:
        text = ""
    value = text.splitlines()[-1] if text else "no-diagnostic"
    value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~-]+", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)(token|secret|password)=\S+", r"\1=[REDACTED]", value)
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())[:500]


def _request(path: Path, repository: str) -> RepositoryMaintenanceRequestEvidence:
    if not _REPOSITORY.fullmatch(repository):
        raise RepositoryMaintenanceReceiptError("repository identity invalid")
    try:
        request = load_request_evidence(event_path=path, repository=repository)
    except Exception as exc:
        raise RepositoryMaintenanceReceiptError(
            "maintenance control request binding mismatch"
        ) from exc
    if type(request) is not RepositoryMaintenanceRequestEvidence:
        raise RepositoryMaintenanceReceiptError(
            "canonical maintenance request parser returned invalid type"
        )
    try:
        return request.validate()
    except Exception as exc:
        raise RepositoryMaintenanceReceiptError(
            "canonical maintenance request validation failed"
        ) from exc


def _sha40(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA40.fullmatch(value) is None:
        raise RepositoryMaintenanceReceiptError(f"{name} must be exact lowercase sha40")
    return value


def _hex64(value: object, name: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise RepositoryMaintenanceReceiptError(f"{name} must be sha256 hex")
    return value


def _validate_run(run_id: int, run_attempt: int, checked_out_sha: str) -> str:
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
        raise RepositoryMaintenanceReceiptError("workflow run id invalid")
    if not isinstance(run_attempt, int) or isinstance(run_attempt, bool) or run_attempt <= 0:
        raise RepositoryMaintenanceReceiptError("workflow run attempt invalid")
    return _sha40(checked_out_sha, "checked-out sha")


def _execution_receipt(value: object) -> RepositoryMaintenanceExecutionReceipt:
    if not isinstance(value, dict):
        raise RepositoryMaintenanceReceiptError("maintenance execution receipt malformed")
    wire = dict(value)
    refs = wire.get("observed_event_refs")
    if isinstance(refs, list):
        wire["observed_event_refs"] = tuple(refs)
    try:
        return RepositoryMaintenanceExecutionReceipt(**wire).validate()
    except Exception as exc:
        raise RepositoryMaintenanceReceiptError(
            "maintenance execution receipt invalid"
        ) from exc


@dataclass(frozen=True)
class MaintenanceReceiptAdmission:
    repository: str
    control_comment_id: int
    kind: str
    workflow_run_id: int
    workflow_run_attempt: int
    checked_out_sha: str
    request_digest: str
    branch: str
    expected_head: str
    receipt_body: str
    receipt_digest: str
    receipt_key: str

    @classmethod
    def failure(
        cls,
        *,
        event_path: Path,
        repository: str,
        workflow_run_id: int,
        workflow_run_attempt: int,
        checked_out_sha: str,
        exit_code: int,
        stderr_path: Path,
    ) -> "MaintenanceReceiptAdmission":
        request = _request(event_path, repository)
        sha = _validate_run(workflow_run_id, workflow_run_attempt, checked_out_sha)
        if not isinstance(exit_code, int) or isinstance(exit_code, bool) or exit_code == 0:
            raise RepositoryMaintenanceReceiptError(
                "failure receipt requires non-zero exit code"
            )
        request_digest = request.digest()
        diagnostic = _bounded_diagnostic(stderr_path)
        diagnostic_digest = sha256(diagnostic.encode("utf-8")).hexdigest()
        receipt_key = _digest(
            repository,
            str(request.control_comment_id),
            "FAILURE",
            request_digest,
            request.branch,
            request.expected_branch_head,
            request.event_digest,
            str(workflow_run_id),
            str(workflow_run_attempt),
            sha,
            str(exit_code),
            diagnostic_digest,
        )
        body = "\n".join((
            _FAILURE_PREFIX,
            f"control_comment_id={request.control_comment_id}",
            f"branch={request.branch}",
            f"expected_head={request.expected_branch_head}",
            f"request_digest={request_digest}",
            f"run_id={workflow_run_id}",
            f"run_attempt={workflow_run_attempt}",
            f"checked_out_sha={sha}",
            f"exit_code={exit_code}",
            f"event_digest={request.event_digest}",
            f"receipt_key={receipt_key}",
            f"diagnostic={diagnostic}",
            "result=FAILED_CLOSED",
            "authority_effect=false",
            "master_effect=false",
            "receipt_is_evidence_not_authority=true",
        ))
        return cls(
            repository,
            request.control_comment_id,
            "FAILURE",
            workflow_run_id,
            workflow_run_attempt,
            sha,
            request_digest,
            request.branch,
            request.expected_branch_head,
            body,
            sha256(body.encode("utf-8")).hexdigest(),
            receipt_key,
        )

    @classmethod
    def observation(
        cls,
        *,
        event_path: Path,
        repository: str,
        workflow_run_id: int,
        workflow_run_attempt: int,
        checked_out_sha: str,
        result_path: Path,
    ) -> "MaintenanceReceiptAdmission":
        request = _request(event_path, repository)
        sha = _validate_run(workflow_run_id, workflow_run_attempt, checked_out_sha)
        try:
            raw = result_path.read_bytes()
            result = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise RepositoryMaintenanceReceiptError("maintenance result unavailable") from exc
        if not isinstance(result, dict):
            raise RepositoryMaintenanceReceiptError("maintenance result malformed")
        required = (
            "schema_version",
            "effect",
            "branch",
            "expected_head",
            "master",
            "tree",
            "bundle_digest",
            "context_digest",
            "authority_lineage_digest",
            "pdp_decision_digest",
            "admission_digest",
            "effect_key",
            "observation_digest",
            "reconciliation_digest",
            "fence_state",
            "receipt",
        )
        if any(key not in result for key in required):
            raise RepositoryMaintenanceReceiptError("canonical maintenance result incomplete")
        if result["schema_version"] != "1.0.0":
            raise RepositoryMaintenanceReceiptError("maintenance result schema invalid")
        if result["effect"] != "repository_ref.delete":
            raise RepositoryMaintenanceReceiptError("maintenance result effect invalid")
        if result["branch"] != request.branch:
            raise RepositoryMaintenanceReceiptError(
                "maintenance result branch substitution denied"
            )
        if result["expected_head"] != request.expected_branch_head:
            raise RepositoryMaintenanceReceiptError(
                "maintenance result expected-head substitution denied"
            )
        if result["fence_state"] != "RECONCILED":
            raise RepositoryMaintenanceReceiptError("maintenance result is not reconciled")
        request_digest = request.digest()
        if "request_digest" in result and result["request_digest"] != request_digest:
            raise RepositoryMaintenanceReceiptError(
                "maintenance result request binding mismatch"
            )
        master = _sha40(result["master"], "maintenance result master")
        tree = _sha40(result["tree"], "maintenance result tree")
        digest_names = (
            "bundle_digest",
            "context_digest",
            "authority_lineage_digest",
            "pdp_decision_digest",
            "admission_digest",
            "effect_key",
            "observation_digest",
            "reconciliation_digest",
        )
        digests = {name: _hex64(result[name], name) for name in digest_names}
        execution_receipt = _execution_receipt(result["receipt"])
        if execution_receipt.repository != repository:
            raise RepositoryMaintenanceReceiptError(
                "maintenance execution receipt repository mismatch"
            )
        if execution_receipt.branch_name != request.branch:
            raise RepositoryMaintenanceReceiptError(
                "maintenance execution receipt branch substitution denied"
            )
        if execution_receipt.branch_head_before != request.expected_branch_head:
            raise RepositoryMaintenanceReceiptError(
                "maintenance execution receipt expected-head mismatch"
            )
        if execution_receipt.master_sha_before != master or execution_receipt.master_sha_after != master:
            raise RepositoryMaintenanceReceiptError(
                "maintenance execution receipt master mismatch"
            )
        if execution_receipt.branch_exists_after is not False:
            raise RepositoryMaintenanceReceiptError(
                "maintenance execution receipt did not observe branch absence"
            )
        if execution_receipt.effect != "DELETE_BRANCH_REF" or execution_receipt.outcome != "SUCCEEDED":
            raise RepositoryMaintenanceReceiptError(
                "maintenance execution receipt does not prove exact delete"
            )
        if execution_receipt.authority_effect is not False or execution_receipt.master_effect is not False:
            raise RepositoryMaintenanceReceiptError(
                "maintenance execution receipt effect flags invalid"
            )
        result_digest = sha256(raw).hexdigest()
        receipt_key = _digest(
            repository,
            str(request.control_comment_id),
            "OBSERVATION",
            request_digest,
            request.branch,
            request.expected_branch_head,
            str(workflow_run_id),
            str(workflow_run_attempt),
            sha,
            result_digest,
            digests["admission_digest"],
            digests["effect_key"],
            digests["observation_digest"],
            digests["reconciliation_digest"],
        )
        body = "\n".join((
            _OBSERVATION_PREFIX,
            f"control_comment_id={request.control_comment_id}",
            f"branch={request.branch}",
            f"expected_head={request.expected_branch_head}",
            f"request_digest={request_digest}",
            f"run_id={workflow_run_id}",
            f"run_attempt={workflow_run_attempt}",
            f"checked_out_sha={sha}",
            f"master={master}",
            f"tree={tree}",
            f"bundle_digest={digests['bundle_digest']}",
            f"context_digest={digests['context_digest']}",
            f"authority_lineage_digest={digests['authority_lineage_digest']}",
            f"pdp_decision_digest={digests['pdp_decision_digest']}",
            f"admission_digest={digests['admission_digest']}",
            f"effect_key={digests['effect_key']}",
            f"observation_digest={digests['observation_digest']}",
            f"reconciliation_digest={digests['reconciliation_digest']}",
            "fence_state=RECONCILED",
            f"result_sha256={result_digest}",
            f"receipt_key={receipt_key}",
            "authority_effect=false",
            "master_effect=false",
            "observation_result=OBSERVED_VERIFIED",
            "receipt_is_evidence_not_authority=true",
        ))
        return cls(
            repository,
            request.control_comment_id,
            "OBSERVATION",
            workflow_run_id,
            workflow_run_attempt,
            sha,
            request_digest,
            request.branch,
            request.expected_branch_head,
            body,
            sha256(body.encode("utf-8")).hexdigest(),
            receipt_key,
        )


@dataclass(frozen=True)
class MaintenanceReceiptObservation:
    comment_id: int
    receipt_key: str
    observed_body_digest: str
    observed: bool


class MaintenanceReceiptObserver:
    def verify(self, value: object, admission: MaintenanceReceiptAdmission) -> MaintenanceReceiptObservation:
        if not isinstance(value, dict):
            raise RepositoryMaintenanceReceiptError("created maintenance receipt malformed")
        comment_id, body = value.get("id"), value.get("body")
        if not isinstance(comment_id, int) or comment_id <= 0 or not isinstance(body, str):
            raise RepositoryMaintenanceReceiptError(
                "maintenance receipt observation identity invalid"
            )
        digest = sha256(body.encode("utf-8")).hexdigest()
        return MaintenanceReceiptObservation(
            comment_id,
            admission.receipt_key,
            digest,
            body == admission.receipt_body and digest == admission.receipt_digest,
        )


class GitHubMaintenanceReceiptBoundary:
    """One fixed GitHub issue-comment POST with durable replay check and exact read-back."""

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    def __init__(self, *, observer: MaintenanceReceiptObserver | None = None) -> None:
        self._observer = observer or MaintenanceReceiptObserver()
        if type(self._observer) is not MaintenanceReceiptObserver:
            raise RepositoryMaintenanceReceiptError(
                "exact MaintenanceReceiptObserver required"
            )

    @staticmethod
    def _headers(token: str, *, json_body: bool) -> dict[str, str]:
        if not isinstance(token, str) or not token.strip():
            raise RepositoryMaintenanceReceiptError("GitHub token unavailable")
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "lion-repository-maintenance-receipt/2",
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    def _open(self, request: urllib.request.Request):
        return urllib.request.build_opener(self._NoRedirect()).open(request, timeout=20)

    def _existing_receipt_keys(self, admission: MaintenanceReceiptAdmission, *, token: str) -> set[str]:
        base = f"https://api.github.com/repos/{admission.repository}"
        keys: set[str] = set()
        for page in range(1, 101):
            url = f"{base}/issues/{CONTROL_ISSUE}/comments?per_page=100&page={page}"
            request = urllib.request.Request(
                url,
                method="GET",
                headers=self._headers(token, json_body=False),
            )
            try:
                with self._open(request) as response:
                    raw = response.read()
                    if response.status != 200:
                        raise RepositoryMaintenanceReceiptError(
                            "maintenance replay ledger read rejected"
                        )
                    value = json.loads(raw) if raw else None
            except (urllib.error.URLError, json.JSONDecodeError) as exc:
                raise RepositoryMaintenanceReceiptError(
                    "maintenance replay ledger read failed"
                ) from exc
            if not isinstance(value, list):
                raise RepositoryMaintenanceReceiptError(
                    "maintenance replay ledger malformed"
                )
            for item in value:
                body = item.get("body") if isinstance(item, dict) else None
                if isinstance(body, str):
                    for line in body.splitlines():
                        if line.startswith("receipt_key="):
                            keys.add(line.removeprefix("receipt_key="))
            if len(value) < 100:
                return keys
        raise RepositoryMaintenanceReceiptError(
            "maintenance replay ledger pagination limit exceeded"
        )

    def post(self, admission: MaintenanceReceiptAdmission, *, token: str) -> MaintenanceReceiptObservation:
        if type(admission) is not MaintenanceReceiptAdmission:
            raise RepositoryMaintenanceReceiptError(
                "exact MaintenanceReceiptAdmission required"
            )
        if admission.receipt_key in self._existing_receipt_keys(admission, token=token):
            raise RepositoryMaintenanceReceiptError("maintenance receipt replay denied")
        base = f"https://api.github.com/repos/{admission.repository}"
        url = f"{base}/issues/{CONTROL_ISSUE}/comments"
        request = urllib.request.Request(
            url,
            data=_canonical({"body": admission.receipt_body}),
            method="POST",
            headers=self._headers(token, json_body=True),
        )
        try:
            with self._open(request) as response:
                raw = response.read()
                if response.status != 201:
                    raise RepositoryMaintenanceReceiptError(
                        "maintenance receipt POST rejected"
                    )
                created = json.loads(raw) if raw else None
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RepositoryMaintenanceReceiptError("maintenance receipt POST failed") from exc
        if not isinstance(created, dict) or not isinstance(created.get("id"), int):
            raise RepositoryMaintenanceReceiptError(
                "maintenance receipt creation response malformed"
            )
        comment_id = int(created["id"])
        readback = urllib.request.Request(
            f"{base}/issues/comments/{comment_id}",
            method="GET",
            headers=self._headers(token, json_body=False),
        )
        try:
            with self._open(readback) as response:
                raw = response.read()
                if response.status != 200:
                    raise RepositoryMaintenanceReceiptError(
                        "maintenance receipt observation rejected"
                    )
                observed_value = json.loads(raw) if raw else None
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RepositoryMaintenanceReceiptError(
                "maintenance receipt observation failed"
            ) from exc
        observation = self._observer.verify(observed_value, admission)
        if observation.comment_id != comment_id or not observation.observed:
            raise RepositoryMaintenanceReceiptError(
                "maintenance receipt read-back mismatch"
            )
        return observation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Post one bounded repository-maintenance receipt"
    )
    parser.add_argument("--kind", choices=("failure", "observation"), required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--token-env", required=True)
    parser.add_argument("--checked-out-sha", required=True)
    parser.add_argument("--exit-code", type=int)
    parser.add_argument("--stderr")
    parser.add_argument("--result")
    args = parser.parse_args(argv)
    token = os.environ.get(args.token_env, "")
    run_id = int(os.environ.get("GITHUB_RUN_ID", "0"))
    run_attempt = int(os.environ.get("GITHUB_RUN_ATTEMPT", "0"))
    try:
        if args.kind == "failure":
            if args.exit_code is None or args.stderr is None:
                raise RepositoryMaintenanceReceiptError("failure inputs incomplete")
            admission = MaintenanceReceiptAdmission.failure(
                event_path=Path(args.event),
                repository=args.repository,
                workflow_run_id=run_id,
                workflow_run_attempt=run_attempt,
                checked_out_sha=args.checked_out_sha,
                exit_code=args.exit_code,
                stderr_path=Path(args.stderr),
            )
        else:
            if args.result is None:
                raise RepositoryMaintenanceReceiptError(
                    "observation result path required"
                )
            admission = MaintenanceReceiptAdmission.observation(
                event_path=Path(args.event),
                repository=args.repository,
                workflow_run_id=run_id,
                workflow_run_attempt=run_attempt,
                checked_out_sha=args.checked_out_sha,
                result_path=Path(args.result),
            )
        observation = GitHubMaintenanceReceiptBoundary().post(admission, token=token)
    except (RepositoryMaintenanceReceiptError, ValueError) as exc:
        print(f"LION_REPOSITORY_MAINTENANCE_RECEIPT_FAILED_CLOSED error={exc}")
        return 2
    print(
        "LION_REPOSITORY_MAINTENANCE_RECEIPT_OBSERVED "
        f"comment_id={observation.comment_id} receipt_key={observation.receipt_key}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
