"""Capability-reduced exact GitHub workflow-dispatch effect provider."""
from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request

from cyber_lion.contracts.actions_dispatch_bridge import DispatchRequest, canonical_json
from cyber_lion.enterprise.workflow_dispatch_mediation import (
    CanonicalWorkflowDispatchAdmission,
    DurableWorkflowDispatchFence,
    WorkflowDispatchMediationError,
    workflow_dispatch_effect_key,
)


class ExactWorkflowDispatchEffectProvider:
    """The sole raw workflow-dispatch network effect in the production slice."""

    API_ORIGIN = "https://api.github.com"

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    def __init__(
        self,
        *,
        repository: str,
        token: str,
        fence: DurableWorkflowDispatchFence,
    ) -> None:
        if not repository or "/" not in repository or repository.startswith("/") or repository.endswith("/"):
            raise WorkflowDispatchMediationError("workflow dispatch repository invalid")
        if not isinstance(token, str) or not token:
            raise WorkflowDispatchMediationError("workflow dispatch credential unavailable")
        if type(fence) is not DurableWorkflowDispatchFence:
            raise WorkflowDispatchMediationError("exact workflow dispatch fence required")
        self._repository = repository
        self._token = token
        self._fence = fence

    def execute_exact(
        self,
        request: DispatchRequest,
        admission: CanonicalWorkflowDispatchAdmission,
    ) -> None:
        if type(request) is not DispatchRequest:
            raise WorkflowDispatchMediationError("exact dispatch request required")
        if type(admission) is not CanonicalWorkflowDispatchAdmission:
            raise WorkflowDispatchMediationError("exact canonical dispatch admission required")
        admission.validate()
        admission.binds(request)
        if request.repository != self._repository or admission.repository != self._repository:
            raise WorkflowDispatchMediationError("workflow dispatch repository substitution")
        effect_key = workflow_dispatch_effect_key(request, admission)
        if self._fence.get(effect_key).state != "ATTEMPTED":
            raise WorkflowDispatchMediationError("workflow dispatch effect requires ATTEMPTED fence")

        workflow = urllib.parse.quote(request.workflow, safe="")
        path = f"/repos/{self._repository}/actions/workflows/{workflow}/dispatches"
        payload = canonical_json({"ref": request.ref, "inputs": dict(request.inputs())})
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "lion-canonical-workflow-dispatch/1",
        }
        req = urllib.request.Request(
            self.API_ORIGIN + path, data=payload, method="POST", headers=headers
        )
        try:
            with urllib.request.build_opener(self._NoRedirect()).open(req, timeout=20) as response:
                if response.status != 204:
                    raise WorkflowDispatchMediationError(
                        f"workflow dispatch not accepted: {response.status}"
                    )
                response.read()
        except urllib.error.HTTPError as exc:
            raise WorkflowDispatchMediationError(
                f"workflow dispatch failed: {exc.code}"
            ) from exc