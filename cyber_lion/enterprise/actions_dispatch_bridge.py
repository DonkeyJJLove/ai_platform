"""Canonical entrypoint for bounded GitHub Actions dispatch and observation.

The legacy observation implementation is retained in a separate module, but production
workflow dispatch is overridden here so the raw POST can be reached only through the
canonical workflow-dispatch mediator. Issue comments, actors, GITHUB_TOKEN and CI state
remain evidence, never authority.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path

from cyber_lion.enterprise import actions_dispatch_bridge_legacy as _legacy
from cyber_lion.enterprise.actions_dispatch_bridge_legacy import *  # noqa: F401,F403
from cyber_lion.contracts.actions_dispatch_bridge import DispatchRequest, DispatchReceipt

_RAW_DISPATCH = _legacy.GitHubApi.dispatch


class GitHubApi(_legacy.GitHubApi):
    """Production API with direct workflow dispatch disabled."""

    def dispatch(self, workflow: str, ref: str, inputs: dict[str, object]) -> None:
        raise RuntimeError("direct workflow dispatch disabled; canonical mediator required")

    def _dispatch_effect(self, request: DispatchRequest, admission) -> None:
        from cyber_lion.enterprise.workflow_dispatch_mediation import CanonicalWorkflowDispatchAdmission
        if type(admission) is not CanonicalWorkflowDispatchAdmission:
            raise RuntimeError("exact canonical workflow dispatch admission required")
        admission.validate(); admission.binds(request)
        if request.repository != self.repository:
            raise RuntimeError("workflow dispatch repository substitution")
        _RAW_DISPATCH(self, request.workflow, request.ref, dict(request.inputs()))

    def dispatch_mediated(self, request: DispatchRequest) -> dict[str, object]:
        from cyber_lion.enterprise.workflow_dispatch_mediation import (
            CanonicalWorkflowDispatchMediator,
            DurableWorkflowDispatchFence,
        )
        from cyber_lion.enterprise.workflow_dispatch_runtime import (
            fence_database_path_from_environment,
            load_pinned_workflow_dispatch_admission_resolver,
        )

        class _Effect:
            def __init__(self, api):
                self._api = api
            def execute_exact(self, req, admission):
                self._api._dispatch_effect(req, admission)

        mediator = CanonicalWorkflowDispatchMediator(
            admissions=load_pinned_workflow_dispatch_admission_resolver(),
            repository=self,
            effect=_Effect(self),
            fence=DurableWorkflowDispatchFence(fence_database_path_from_environment()),
        )
        return mediator.execute(request)


def execute(event: dict, api, *, policy=DEFAULT_POLICY) -> DispatchReceipt:
    issue_number, comment_id, body, actor, _ = _legacy._event_parts(event, api, policy)
    request = _legacy.parse_envelope(
        body,
        repository=api.repository,
        issue_number=issue_number,
        comment_id=comment_id,
        actor=actor,
        policy=policy,
    )
    permission = api.actor_permission(actor)
    if permission not in policy.trusted_permissions:
        raise RuntimeError("untrusted actor permission")
    if api.ref_head(request.ref) != request.expected_head:
        raise RuntimeError("stale expected head")
    if not api.workflow_exists(request.workflow, request.expected_head):
        raise RuntimeError("allowlisted workflow missing at expected head")
    replay = _legacy._ledger_match(api.issue_comments(policy.control_issue), request)
    if replay:
        raise RuntimeError(replay)
    claim_id = api.post_issue_comment(policy.control_issue, _legacy._claim_body(request, permission))
    if api.ref_head(request.ref) != request.expected_head:
        api.patch_issue_comment(
            claim_id,
            _legacy._claim_body(request, permission) + "\nstate=DENIED_HEAD_MOVED_BEFORE_DISPATCH",
        )
        raise RuntimeError("ref moved before dispatch")

    accepted_at = _legacy._now()
    try:
        if type(api) is GitHubApi:
            mediation = api.dispatch_mediated(request)
            if mediation.get("fence_state") != "RECONCILED":
                raise RuntimeError("canonical workflow dispatch did not reconcile")
        else:
            # Compatibility path for capability-reduced unit-test fakes only. Production
            # run_event always constructs the exact GitHubApi above.
            api.dispatch(request.workflow, request.ref, dict(request.inputs()))
    except Exception:
        api.patch_issue_comment(
            claim_id,
            _legacy._claim_body(request, permission) + "\nstate=DISPATCH_API_FAILED_REQUEST_CONSUMED",
        )
        raise

    receipt = DispatchReceipt(
        schema_version="1.0.0",
        request_id=request.request_id,
        control_comment_id=request.comment_id,
        actor=request.actor,
        permission=permission,
        workflow=request.workflow,
        ref=request.ref,
        expected_head=request.expected_head,
        canonical_inputs_digest=sha256(request.canonical_inputs.encode("utf-8")).hexdigest(),
        accepted_at=accepted_at,
        replay_key=request.replay_key(),
        bridge_implementation_digest=sha256(Path(__file__).read_bytes()).hexdigest(),
        trust_decision="ALLOW",
        github_api_result="ACCEPTED_204",
    ).validate()
    api.patch_issue_comment(claim_id, _legacy._receipt_body(receipt))
    return receipt


def observe(event: dict, api, *, policy=DEFAULT_POLICY, discovery_timeout: float = 180.0,
            terminal_timeout: float = 300.0, poll_seconds: float = 2.0):
    return _legacy.observe(
        event,
        api,
        policy=policy,
        discovery_timeout=discovery_timeout,
        terminal_timeout=terminal_timeout,
        poll_seconds=poll_seconds,
    )


def run_event(event_path: Path, repository: str, token: str):
    event = json.loads(event_path.read_text(encoding="utf-8"))
    if not isinstance(event, dict):
        raise RuntimeError("event must be an object")
    body = event.get("comment", {}).get("body") if isinstance(event.get("comment"), dict) else None
    api = GitHubApi(repository, token)
    if isinstance(body, str) and body.startswith(OBSERVE_PREFIX):
        return observe(event, api)
    return execute(event, api)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    args = parser.parse_args(argv)
    token = os.environ.get(args.token_env, "")
    if not token:
        raise SystemExit("GitHub token unavailable")
    receipt = run_event(Path(args.event), args.repository, token)
    print(canonical_json(asdict(receipt)).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
