"""Canonical production composition for exact GitHub issue-comment writes.

The repository cannot manufacture issue-comment authority. A pinned runtime module outside
GITHUB_WORKSPACE supplies the admission resolver and authoritative repository reader. The
public production surface accepts only IssueCommentWriteRequest; repository, credential,
fence, authority source, reader, and raw POST/PATCH provider are not caller-selectable.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from cyber_lion.contracts.issue_comment_write import (
    CanonicalIssueCommentWriteAdmission,
    IssueCommentWriteRequest,
    body_digest,
)
from cyber_lion.enterprise.issue_comment_write_mediation import (
    CanonicalIssueCommentWriteMediator,
    DurableIssueCommentWriteFence,
    IssueCommentWriteMediationError,
    issue_comment_effect_key,
)

_REPOSITORY = "DonkeyJJLove/ai_platform"
_FACTORY = "build_issue_comment_write_dependencies"
_RUNTIME_PATH_ENV = "LION_ISSUE_COMMENT_RUNTIME_MODULE_PATH"
_RUNTIME_DIGEST_ENV = "LION_ISSUE_COMMENT_RUNTIME_MODULE_DIGEST"
_FENCE_PATH_ENV = "LION_ISSUE_COMMENT_FENCE_DATABASE_PATH"
_TOKEN_ENV = "GITHUB_TOKEN"
_API_ORIGIN = "https://api.github.com"
_MAX_RESPONSE_BYTES = 1024 * 1024


@dataclass(frozen=True)
class IssueCommentWriteRuntimeDependencies:
    admissions: object
    repository: object

    def validate(self) -> "IssueCommentWriteRuntimeDependencies":
        if not callable(getattr(self.admissions, "resolve", None)):
            raise IssueCommentWriteMediationError(
                "trusted issue-comment admission resolver unavailable"
            )
        if not callable(getattr(self.repository, "ref_head", None)):
            raise IssueCommentWriteMediationError(
                "trusted issue-comment repository head reader unavailable"
            )
        if not callable(getattr(self.repository, "get_comment", None)):
            raise IssueCommentWriteMediationError(
                "trusted issue-comment repository comment reader unavailable"
            )
        return self


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _workspace_outside(path: Path, error: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise IssueCommentWriteMediationError(error) from exc
    workspace_raw = os.environ.get("GITHUB_WORKSPACE")
    if workspace_raw:
        workspace = Path(workspace_raw).resolve()
        if resolved == workspace or workspace in resolved.parents:
            raise IssueCommentWriteMediationError(
                "trusted issue-comment runtime must remain outside repository"
            )
    return resolved


def load_pinned_issue_comment_write_dependencies() -> IssueCommentWriteRuntimeDependencies:
    path_raw = os.environ.get(_RUNTIME_PATH_ENV, "")
    digest = os.environ.get(_RUNTIME_DIGEST_ENV, "")
    if (
        not path_raw
        or len(digest) != 64
        or any(ch not in "0123456789abcdef" for ch in digest)
    ):
        raise IssueCommentWriteMediationError(
            "trusted issue-comment runtime unavailable"
        )
    path = Path(path_raw)
    if not path.is_absolute():
        raise IssueCommentWriteMediationError(
            "trusted issue-comment runtime path must be absolute"
        )
    resolved = _workspace_outside(path, "trusted issue-comment runtime unavailable")
    if not resolved.is_file() or resolved.suffix != ".py":
        raise IssueCommentWriteMediationError(
            "trusted issue-comment runtime invalid"
        )
    if sha256(resolved.read_bytes()).hexdigest() != digest:
        raise IssueCommentWriteMediationError(
            "trusted issue-comment runtime digest mismatch"
        )
    spec = importlib.util.spec_from_file_location(
        "_lion_issue_comment_runtime_" + digest[:20], resolved
    )
    if spec is None or spec.loader is None:
        raise IssueCommentWriteMediationError(
            "trusted issue-comment runtime cannot be loaded"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    factory = getattr(module, _FACTORY, None)
    if not callable(factory):
        raise IssueCommentWriteMediationError(
            "trusted issue-comment dependency factory unavailable"
        )
    dependencies = factory()
    if type(dependencies) is not IssueCommentWriteRuntimeDependencies:
        raise IssueCommentWriteMediationError(
            "exact issue-comment runtime dependencies required"
        )
    return dependencies.validate()


def fence_database_path_from_environment() -> str:
    raw = os.environ.get(_FENCE_PATH_ENV, "")
    path = Path(raw)
    if not raw or not path.is_absolute():
        raise IssueCommentWriteMediationError(
            "trusted issue-comment fence database unavailable"
        )
    workspace_raw = os.environ.get("GITHUB_WORKSPACE")
    if workspace_raw:
        workspace = Path(workspace_raw).resolve()
        resolved = path.resolve()
        if resolved == workspace or workspace in resolved.parents:
            raise IssueCommentWriteMediationError(
                "issue-comment fence must remain outside repository"
            )
    return str(path)


def _github_token_from_environment() -> str:
    token = os.environ.get(_TOKEN_ENV, "")
    if not isinstance(token, str) or not token:
        raise IssueCommentWriteMediationError(
            "trusted issue-comment GitHub credential unavailable"
        )
    return token


def execute_issue_comment_write(
    request: IssueCommentWriteRequest,
) -> dict[str, object]:
    """Execute one issue-comment write only through the canonical mediated runtime."""
    if type(request) is not IssueCommentWriteRequest:
        raise IssueCommentWriteMediationError(
            "exact issue-comment request required"
        )
    request.validate()
    dependencies = load_pinned_issue_comment_write_dependencies()
    fence = DurableIssueCommentWriteFence(fence_database_path_from_environment())
    token = _github_token_from_environment()

    class _RuntimeEffect:
        def __init__(self) -> None:
            self._used = False

        def write_exact(
            self,
            exact_request: IssueCommentWriteRequest,
            admission: CanonicalIssueCommentWriteAdmission,
        ) -> int:
            if self._used:
                raise IssueCommentWriteMediationError(
                    "issue-comment runtime effect replay denied"
                )
            if type(exact_request) is not IssueCommentWriteRequest:
                raise IssueCommentWriteMediationError(
                    "exact issue-comment request required"
                )
            if type(admission) is not CanonicalIssueCommentWriteAdmission:
                raise IssueCommentWriteMediationError(
                    "exact canonical issue-comment admission required"
                )
            admission.validate()
            admission.binds(exact_request)

            current = dependencies.admissions.resolve(exact_request)
            if (
                type(current) is not CanonicalIssueCommentWriteAdmission
                or current.validate().admission_digest != admission.admission_digest
            ):
                raise IssueCommentWriteMediationError(
                    "issue-comment authority drift at effect boundary"
                )

            if dependencies.repository.ref_head("master") != exact_request.expected_repository_head:
                raise IssueCommentWriteMediationError(
                    "issue-comment repository head drift at effect boundary"
                )

            if exact_request.action == "UPDATE_OWN_CREATED_COMMENT":
                old = dependencies.repository.get_comment(
                    exact_request.expected_existing_comment_id
                )
                if (
                    not isinstance(old, dict)
                    or old.get("id") != exact_request.expected_existing_comment_id
                    or not isinstance(old.get("body"), str)
                    or body_digest(old["body"])
                    != exact_request.expected_existing_body_digest
                ):
                    raise IssueCommentWriteMediationError(
                        "issue-comment target drift at effect boundary"
                    )

            effect_key = issue_comment_effect_key(exact_request, admission)
            record = fence.get(effect_key)
            if (
                record.state != "ATTEMPTED"
                or record.request_digest != exact_request.request_digest
                or record.admission_digest != admission.admission_digest
            ):
                raise IssueCommentWriteMediationError(
                    "issue-comment write requires exact durable ATTEMPTED fence"
                )

            payload = json.dumps(
                {"body": exact_request.body},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
                "User-Agent": "lion-canonical-issue-comment-write/1",
            }
            if exact_request.action == "CREATE_COMMENT":
                path = (
                    f"/repos/{_REPOSITORY}/issues/"
                    f"{exact_request.issue_number}/comments"
                )
                request_http = urllib.request.Request(
                    _API_ORIGIN + path,
                    data=payload,
                    method="POST",
                    headers=headers,
                )
                expected_status = 201
            elif exact_request.action == "UPDATE_OWN_CREATED_COMMENT":
                path = (
                    f"/repos/{_REPOSITORY}/issues/comments/"
                    f"{exact_request.expected_existing_comment_id}"
                )
                request_http = urllib.request.Request(
                    _API_ORIGIN + path,
                    data=payload,
                    method="PATCH",
                    headers=headers,
                )
                expected_status = 200
            else:
                raise IssueCommentWriteMediationError(
                    "unsupported issue-comment action"
                )

            self._used = True
            try:
                with urllib.request.build_opener(_NoRedirect()).open(
                    request_http, timeout=20
                ) as response:
                    raw = response.read(_MAX_RESPONSE_BYTES + 1)
                    if response.status != expected_status:
                        raise IssueCommentWriteMediationError(
                            "GitHub issue-comment write rejected"
                        )
            except urllib.error.URLError as exc:
                raise IssueCommentWriteMediationError(
                    "GitHub issue-comment write failed"
                ) from exc

            if len(raw) > _MAX_RESPONSE_BYTES:
                raise IssueCommentWriteMediationError(
                    "GitHub issue-comment response oversized"
                )
            try:
                value = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise IssueCommentWriteMediationError(
                    "GitHub issue-comment response malformed"
                ) from exc
            comment_id = value.get("id") if isinstance(value, dict) else None
            if (
                not isinstance(comment_id, int)
                or isinstance(comment_id, bool)
                or comment_id <= 0
            ):
                raise IssueCommentWriteMediationError(
                    "GitHub issue-comment identity missing"
                )
            if (
                exact_request.action == "UPDATE_OWN_CREATED_COMMENT"
                and comment_id != exact_request.expected_existing_comment_id
            ):
                raise IssueCommentWriteMediationError(
                    "GitHub issue-comment update identity changed"
                )
            return comment_id

    mediator = CanonicalIssueCommentWriteMediator(
        admissions=dependencies.admissions,
        repository=dependencies.repository,
        effect=_RuntimeEffect(),
        fence=fence,
    )
    return mediator.execute(request)


class EnvironmentIssueCommentMediator:
    """Compatibility facade that does not accept caller-selected effect dependencies."""

    def __init__(
        self,
        repository: str | None = None,
        token: str | None = None,
    ) -> None:
        if repository is not None and repository != _REPOSITORY:
            raise IssueCommentWriteMediationError(
                "repository substitution denied"
            )
        del token

    def execute(self, request: IssueCommentWriteRequest) -> dict[str, object]:
        return execute_issue_comment_write(request)
