"""Canonical production composition for one exact GitHub Actions run cancellation.

The repository cannot manufacture cancellation authority. The external runtime module is
pinned by absolute path + SHA-256 and must live outside GITHUB_WORKSPACE. It supplies the
admission resolver and authoritative run reader. The public production surface accepts
only ActionsRunCancelRequest; repository, credential, fence, authority source, reader and
raw POST provider are not caller-selectable.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import importlib.util
import os
from pathlib import Path
import urllib.error
import urllib.request

from cyber_lion.contracts.actions_run_cancel import ActionsRunCancelRequest
from cyber_lion.enterprise.actions_run_cancel_mediation import (
    ActionsRunCancelMediationError,
    CanonicalActionsRunCancelAdmission,
    CanonicalActionsRunCancelMediator,
    DurableActionsRunCancelFence,
    actions_run_cancel_effect_key,
)

_REPOSITORY = "DonkeyJJLove/ai_platform"
_FACTORY = "build_actions_run_cancel_dependencies"
_RUNTIME_PATH_ENV = "LION_ACTIONS_RUN_CANCEL_RUNTIME_MODULE_PATH"
_RUNTIME_DIGEST_ENV = "LION_ACTIONS_RUN_CANCEL_RUNTIME_MODULE_DIGEST"
_FENCE_PATH_ENV = "LION_ACTIONS_RUN_CANCEL_FENCE_DATABASE_PATH"
_TOKEN_ENV = "GITHUB_TOKEN"
_API_ORIGIN = "https://api.github.com"


@dataclass(frozen=True)
class ActionsRunCancelRuntimeDependencies:
    admissions: object
    repository: object

    def validate(self) -> "ActionsRunCancelRuntimeDependencies":
        if not callable(getattr(self.admissions, "resolve", None)):
            raise ActionsRunCancelMediationError(
                "trusted actions-run-cancel admission resolver unavailable"
            )
        if not callable(getattr(self.repository, "get_run", None)):
            raise ActionsRunCancelMediationError(
                "trusted actions-run-cancel repository reader unavailable"
            )
        return self


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def _workspace_outside(path: Path, error: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ActionsRunCancelMediationError(error) from exc
    workspace_raw = os.environ.get("GITHUB_WORKSPACE")
    if workspace_raw:
        workspace = Path(workspace_raw).resolve()
        if resolved == workspace or workspace in resolved.parents:
            raise ActionsRunCancelMediationError(
                "trusted actions-run-cancel runtime must remain outside repository"
            )
    return resolved


def load_pinned_actions_run_cancel_dependencies() -> ActionsRunCancelRuntimeDependencies:
    path_raw = os.environ.get(_RUNTIME_PATH_ENV, "")
    digest = os.environ.get(_RUNTIME_DIGEST_ENV, "")
    if (
        not path_raw
        or len(digest) != 64
        or any(ch not in "0123456789abcdef" for ch in digest)
    ):
        raise ActionsRunCancelMediationError(
            "trusted actions-run-cancel runtime unavailable"
        )
    path = Path(path_raw)
    if not path.is_absolute():
        raise ActionsRunCancelMediationError(
            "trusted actions-run-cancel runtime path must be absolute"
        )
    resolved = _workspace_outside(
        path, "trusted actions-run-cancel runtime unavailable"
    )
    if not resolved.is_file() or resolved.suffix != ".py":
        raise ActionsRunCancelMediationError(
            "trusted actions-run-cancel runtime invalid"
        )
    if sha256(resolved.read_bytes()).hexdigest() != digest:
        raise ActionsRunCancelMediationError(
            "trusted actions-run-cancel runtime digest mismatch"
        )
    spec = importlib.util.spec_from_file_location(
        "_lion_actions_run_cancel_runtime_" + digest[:20], resolved
    )
    if spec is None or spec.loader is None:
        raise ActionsRunCancelMediationError(
            "trusted actions-run-cancel runtime cannot be loaded"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    factory = getattr(module, _FACTORY, None)
    if not callable(factory):
        raise ActionsRunCancelMediationError(
            "trusted actions-run-cancel dependency factory unavailable"
        )
    dependencies = factory()
    if type(dependencies) is not ActionsRunCancelRuntimeDependencies:
        raise ActionsRunCancelMediationError(
            "exact actions-run-cancel runtime dependencies required"
        )
    return dependencies.validate()


def fence_database_path_from_environment() -> str:
    raw = os.environ.get(_FENCE_PATH_ENV, "")
    path = Path(raw)
    if not raw or not path.is_absolute():
        raise ActionsRunCancelMediationError(
            "trusted actions-run-cancel fence database unavailable"
        )
    workspace_raw = os.environ.get("GITHUB_WORKSPACE")
    if workspace_raw:
        workspace = Path(workspace_raw).resolve()
        resolved = path.resolve()
        if resolved == workspace or workspace in resolved.parents:
            raise ActionsRunCancelMediationError(
                "actions-run-cancel fence must remain outside repository"
            )
    return str(path)


def _github_token_from_environment() -> str:
    token = os.environ.get(_TOKEN_ENV, "")
    if not isinstance(token, str) or not token:
        raise ActionsRunCancelMediationError(
            "trusted actions-run-cancel GitHub credential unavailable"
        )
    return token


def execute_actions_run_cancel(request: ActionsRunCancelRequest) -> dict[str, object]:
    """Execute one cancellation only through the canonical mediated runtime."""
    if type(request) is not ActionsRunCancelRequest:
        raise ActionsRunCancelMediationError("exact actions-run-cancel request required")
    request.validate()
    dependencies = load_pinned_actions_run_cancel_dependencies()
    fence = DurableActionsRunCancelFence(fence_database_path_from_environment())
    token = _github_token_from_environment()

    class _RuntimeEffect:
        def __init__(self) -> None:
            self._used = False

        def cancel_exact(
            self,
            exact_request: ActionsRunCancelRequest,
            admission: CanonicalActionsRunCancelAdmission,
        ) -> None:
            if self._used:
                raise ActionsRunCancelMediationError(
                    "actions-run-cancel runtime effect replay denied"
                )
            if type(exact_request) is not ActionsRunCancelRequest:
                raise ActionsRunCancelMediationError(
                    "exact actions-run-cancel request required"
                )
            if type(admission) is not CanonicalActionsRunCancelAdmission:
                raise ActionsRunCancelMediationError(
                    "exact canonical actions-run-cancel admission required"
                )
            admission.validate()
            admission.binds(exact_request)

            current = dependencies.admissions.resolve(exact_request)
            if (
                type(current) is not CanonicalActionsRunCancelAdmission
                or current.validate().admission_digest != admission.admission_digest
            ):
                raise ActionsRunCancelMediationError(
                    "actions-run-cancel authority drift at effect boundary"
                )

            CanonicalActionsRunCancelMediator._validate_run(
                exact_request,
                dependencies.repository.get_run(exact_request.run_id),
            )
            effect_key = actions_run_cancel_effect_key(exact_request, admission)
            if fence.get(effect_key).state != "ATTEMPTED":
                raise ActionsRunCancelMediationError(
                    "actions-run-cancel POST requires durable ATTEMPTED fence"
                )

            path = (
                f"/repos/{_REPOSITORY}/actions/runs/"
                f"{exact_request.run_id}/cancel"
            )
            request_http = urllib.request.Request(
                _API_ORIGIN + path,
                data=b"",
                method="POST",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "lion-canonical-actions-run-cancel/1",
                },
            )
            self._used = True
            try:
                with urllib.request.build_opener(_NoRedirect()).open(
                    request_http, timeout=20
                ) as response:
                    if response.status != 202:
                        raise ActionsRunCancelMediationError(
                            f"cancel not accepted: {response.status}"
                        )
                    response.read()
            except urllib.error.HTTPError as exc:
                raise ActionsRunCancelMediationError(
                    f"cancel failed: {exc.code}"
                ) from exc

    mediator = CanonicalActionsRunCancelMediator(
        admissions=dependencies.admissions,
        repository=dependencies.repository,
        effect=_RuntimeEffect(),
        fence=fence,
    )
    return mediator.execute(request)
