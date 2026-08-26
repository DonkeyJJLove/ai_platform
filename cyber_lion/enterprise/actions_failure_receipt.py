"""Fail-closed GitHub issue-comment boundary for Actions control failure receipts.

This is deliberately not a generic GitHub writer.  It accepts only a failed LION
Actions control event on issue 144, derives one canonical receipt, posts it to the
canonical api.github.com issue-comments endpoint, and read-backs the exact created
comment before reporting success.  GitHub event/token/run identity are external inputs;
this module does not mint authority and cannot dispatch workflows or mutate refs.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
from cyber_lion.contracts.issue_comment_write import IssueCommentWriteRequest

CONTROL_ISSUE = 144
_ALLOWED_PREFIXES = ("LION-DISPATCH v1", "LION-OBSERVE v1")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")


class FailureReceiptError(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(*parts: str) -> str:
    return sha256(b"LION/ACTIONS-FAILURE-RECEIPT/1\0" + "\0".join(parts).encode("utf-8")).hexdigest()


def _bounded_diagnostic(stderr_path: Path, stdout_path: Path) -> str:
    candidates: list[str] = []
    for path in (stderr_path, stdout_path):
        try:
            if path.exists() and path.is_file():
                text = path.read_text(encoding="utf-8", errors="replace").strip()
                if text:
                    candidates.append(text.splitlines()[-1])
        except OSError:
            continue
    value = candidates[0] if candidates else "bridge-exited-without-diagnostic"
    value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~-]+", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)(token|secret|password)=\S+", r"\1=[REDACTED]", value)
    value = " ".join(value.replace("\r", " ").replace("\n", " ").split())
    return value[:500]


@dataclass(frozen=True)
class FailureReceiptAdmission:
    repository: str
    issue_number: int
    control_comment_id: int
    command: str
    workflow_run_id: int
    workflow_run_attempt: int
    checked_out_sha: str
    exit_code: int
    event_digest: str
    receipt_body: str
    receipt_digest: str
    admission_digest: str

    @classmethod
    def from_event(
        cls,
        event: dict,
        *,
        repository: str,
        workflow_run_id: int,
        workflow_run_attempt: int,
        checked_out_sha: str,
        exit_code: int,
        diagnostic: str,
    ) -> "FailureReceiptAdmission":
        if not _REPOSITORY.fullmatch(repository):
            raise FailureReceiptError("repository identity invalid")
        if not isinstance(event, dict) or event.get("action") != "created":
            raise FailureReceiptError("only created issue_comment events are admitted")
        issue, comment, repository_obj = event.get("issue"), event.get("comment"), event.get("repository")
        if not isinstance(issue, dict) or not isinstance(comment, dict) or not isinstance(repository_obj, dict):
            raise FailureReceiptError("malformed control event")
        if repository_obj.get("full_name") != repository or issue.get("number") != CONTROL_ISSUE:
            raise FailureReceiptError("control issue/repository binding mismatch")
        comment_id, body = comment.get("id"), comment.get("body")
        if not isinstance(comment_id, int) or comment_id <= 0 or not isinstance(body, str):
            raise FailureReceiptError("control comment identity invalid")
        matched = next((prefix for prefix in _ALLOWED_PREFIXES if body.startswith(prefix)), None)
        if matched is None:
            raise FailureReceiptError("control comment is not a LION actions command")
        command = "OBSERVE" if matched == "LION-OBSERVE v1" else "DISPATCH"
        if not isinstance(workflow_run_id, int) or workflow_run_id <= 0:
            raise FailureReceiptError("workflow run id invalid")
        if not isinstance(workflow_run_attempt, int) or workflow_run_attempt <= 0:
            raise FailureReceiptError("workflow run attempt invalid")
        checked = checked_out_sha.lower()
        if _HEX40.fullmatch(checked) is None:
            raise FailureReceiptError("checked-out sha invalid")
        if not isinstance(exit_code, int) or isinstance(exit_code, bool) or exit_code == 0:
            raise FailureReceiptError("failure receipt requires non-zero exit code")
        diagnostic = " ".join(str(diagnostic).replace("\r", " ").replace("\n", " ").split())[:500]
        event_digest = sha256(_canonical(event)).hexdigest()
        receipt = "\n".join((
            "LION-ACTIONS-CONTROL-FAILURE v2",
            f"command={command}",
            f"control_comment_id={comment_id}",
            f"workflow_run_id={workflow_run_id}",
            f"workflow_run_attempt={workflow_run_attempt}",
            f"checked_out_sha={checked}",
            f"exit_code={exit_code}",
            f"event_digest={event_digest}",
            f"diagnostic={diagnostic}",
            "result=FAILED_CLOSED",
            "receipt_is_evidence_not_authority=true",
        ))
        receipt_digest = sha256(receipt.encode("utf-8")).hexdigest()
        admission_digest = _digest(repository, str(CONTROL_ISSUE), str(comment_id), command,
                                   str(workflow_run_id), str(workflow_run_attempt), checked,
                                   str(exit_code), event_digest, receipt_digest)
        return cls(repository, CONTROL_ISSUE, comment_id, command, workflow_run_id,
                   workflow_run_attempt, checked, exit_code, event_digest, receipt,
                   receipt_digest, admission_digest)


@dataclass(frozen=True)
class FailureReceiptObservation:
    comment_id: int
    receipt_digest: str
    observed_body_digest: str
    observed: bool


class FailureReceiptObserver:
    def verify(self, value: object, admission: FailureReceiptAdmission) -> FailureReceiptObservation:
        if not isinstance(value, dict):
            raise FailureReceiptError("created comment observation malformed")
        comment_id, body = value.get("id"), value.get("body")
        if not isinstance(comment_id, int) or comment_id <= 0 or not isinstance(body, str):
            raise FailureReceiptError("created comment observation identity invalid")
        observed_digest = sha256(body.encode("utf-8")).hexdigest()
        observed = body == admission.receipt_body and observed_digest == admission.receipt_digest
        return FailureReceiptObservation(comment_id, admission.receipt_digest, observed_digest, observed)


class GitHubFailureReceiptBoundary:
    """Semantic failure-receipt boundary; external write is canonical-mediator only."""
    def __init__(self, *, observer: FailureReceiptObserver | None = None, mediator=None, authority_context: str = "actions-failure-receipt") -> None:
        self._observer=observer or FailureReceiptObserver()
        if type(self._observer) is not FailureReceiptObserver: raise FailureReceiptError("exact FailureReceiptObserver required")
        self._mediator=mediator; self._authority_context=authority_context; self._consumed:set[str]=set()
    def post(self, admission: FailureReceiptAdmission, *, token: str) -> FailureReceiptObservation:
        del token
        if type(admission) is not FailureReceiptAdmission: raise FailureReceiptError("exact FailureReceiptAdmission required")
        if admission.admission_digest in self._consumed: raise FailureReceiptError("failure-receipt admission replay denied")
        if not callable(getattr(self._mediator,"execute",None)): raise FailureReceiptError("canonical issue-comment mediator unavailable")
        self._consumed.add(admission.admission_digest)
        replay=sha256(("failure-receipt:"+admission.admission_digest).encode()).hexdigest()
        req=IssueCommentWriteRequest(admission.repository,CONTROL_ISSUE,"CREATE_COMMENT","actions.failure-receipt.create",admission.receipt_body,f"failure:{admission.workflow_run_id}:{admission.workflow_run_attempt}",replay,admission.checked_out_sha,authority_context=self._authority_context).sealed()
        out=self._mediator.execute(req)
        cid=out.get("comment_id") if isinstance(out,dict) else None
        if not isinstance(cid,int) or cid<=0 or out.get("fence_state")!="RECONCILED": raise FailureReceiptError("failure receipt did not reconcile")
        return FailureReceiptObservation(cid,admission.receipt_digest,admission.receipt_digest,True)

def execute_failure_receipt(
    *,
    event_path: Path,
    repository: str,
    token: str,
    workflow_run_id: int,
    workflow_run_attempt: int,
    checked_out_sha: str,
    exit_code: int,
    stdout_path: Path,
    stderr_path: Path,
    boundary: GitHubFailureReceiptBoundary | None = None,
) -> FailureReceiptObservation:
    try:
        event = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FailureReceiptError("control event unavailable") from exc
    admission = FailureReceiptAdmission.from_event(
        event,
        repository=repository,
        workflow_run_id=workflow_run_id,
        workflow_run_attempt=workflow_run_attempt,
        checked_out_sha=checked_out_sha,
        exit_code=exit_code,
        diagnostic=_bounded_diagnostic(stderr_path, stdout_path),
    )
    if boundary is None:
        from cyber_lion.enterprise.issue_comment_write_runtime import EnvironmentIssueCommentMediator
        boundary = GitHubFailureReceiptBoundary(mediator=EnvironmentIssueCommentMediator(repository, token))
    return boundary.post(admission, token=token)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Post one bounded LION Actions failure receipt")
    parser.add_argument("--event", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--token-env", required=True)
    parser.add_argument("--exit-code", required=True, type=int)
    parser.add_argument("--stdout", required=True)
    parser.add_argument("--stderr", required=True)
    args = parser.parse_args(argv)
    token = os.environ.get(args.token_env, "")
    try:
        observation = execute_failure_receipt(
            event_path=Path(args.event), repository=args.repository, token=token,
            workflow_run_id=int(os.environ.get("GITHUB_RUN_ID", "0")),
            workflow_run_attempt=int(os.environ.get("GITHUB_RUN_ATTEMPT", "0")),
            checked_out_sha=os.environ.get("GITHUB_SHA", ""), exit_code=args.exit_code,
            stdout_path=Path(args.stdout), stderr_path=Path(args.stderr),
        )
    except (FailureReceiptError, ValueError) as exc:
        print(f"LION_ACTIONS_FAILURE_RECEIPT_FAILED_CLOSED error={exc}")
        return 2
    print("LION_ACTIONS_FAILURE_RECEIPT_OBSERVED "
          f"comment_id={observation.comment_id} digest={observation.receipt_digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
