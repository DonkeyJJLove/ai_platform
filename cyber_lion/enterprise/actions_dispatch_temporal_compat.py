"""Bounded compatibility shim for Actions run observation.

Legacy dispatch receipts may timestamp acceptance just after GitHub creates the run, so
run discovery permits at most a 60-second lookback while preserving exact event/ref/head
and ambiguity checks. Historical group-channel runs that collide in that bounded window
are disambiguated only by independently verified canonical artifact/envelope binding.
Artifact downloads are handled as an explicit two-hop trust transition: the GitHub API
request is authenticated, while the returned GitHub Actions signed blob URL is fetched
without forwarding the GitHub bearer token or cookies and without following another
redirect. This shim does not dispatch on observation and does not mint authority.
"""
from __future__ import annotations

from datetime import timedelta
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from cyber_lion.enterprise import actions_dispatch_bridge as bridge

LEGACY_LOOKBACK_SECONDS = 60
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_GITHUB_ACTIONS_ARCHIVE_HOST = re.compile(
    r"^productionresultssa[0-9]+\.blob\.core\.windows\.net$"
)
_ORIGINAL_WAIT_TERMINAL = bridge._wait_terminal
_ORIGINAL_DISCOVER_RUN = bridge._discover_run


def _matching_runs_compat(runs: list[dict], receipt: bridge.DispatchReceipt) -> list[dict]:
    accepted = bridge._parse_time(receipt.accepted_at)
    lower_bound = accepted - timedelta(seconds=LEGACY_LOOKBACK_SECONDS)
    matches: list[dict] = []
    for run in runs:
        try:
            created = bridge._parse_time(str(run["created_at"]))
            run_id = int(run["id"])
        except (KeyError, ValueError, TypeError):
            continue
        if (
            run.get("event") == "workflow_dispatch"
            and run.get("head_branch") == receipt.ref
            and str(run.get("head_sha", "")).lower() == receipt.expected_head
            and created >= lower_bound
            and run_id > 0
        ):
            matches.append(run)
    matches.sort(key=lambda item: int(item["id"]))
    return matches


def _group_envelope_for_discovery(api, receipt: bridge.DispatchReceipt):
    comments = api.issue_comments(bridge.DEFAULT_POLICY.control_issue)
    original = bridge._original_dispatch_request(
        comments,
        receipt,
        bridge.DEFAULT_POLICY,
        api.repository,
    )
    inputs = dict(original.inputs())
    if set(inputs) != {"envelope_b64"} or not isinstance(inputs.get("envelope_b64"), str):
        raise RuntimeError("group-channel original input set invalid during discovery")
    accepted = bridge._parse_time(receipt.accepted_at)
    try:
        envelope = bridge.decode_envelope(inputs["envelope_b64"], now=accepted)
    except bridge.GroupChannelContractError as exc:
        raise RuntimeError("historical group-channel envelope invalid during discovery") from exc
    if envelope.repository != api.repository or envelope.expected_master_head != receipt.expected_head:
        raise RuntimeError("historical group-channel envelope binding mismatch during discovery")
    return envelope


def _group_candidate_verifies(api, receipt: bridge.DispatchReceipt, envelope, candidate: dict) -> bool:
    try:
        run_id = int(candidate["id"])
        terminal = api.workflow_run(run_id)
        if (
            int(terminal.get("id", 0)) != run_id
            or terminal.get("event") != "workflow_dispatch"
            or terminal.get("head_branch") != receipt.ref
            or str(terminal.get("head_sha", "")).lower() != receipt.expected_head
            or terminal.get("status") != "completed"
            or terminal.get("conclusion") != "success"
        ):
            return False
        run_attempt = int(terminal.get("run_attempt", 0))
        if run_attempt <= 0:
            return False
        expected_name = f"lion-group-channel-receipt-{run_id}-{run_attempt}"
        artifacts = [
            item for item in api.run_artifacts(run_id)
            if item.get("name") == expected_name and item.get("expired") is False
        ]
        if len(artifacts) != 1:
            return False
        artifact = artifacts[0]
        artifact_id = int(artifact["id"])
        artifact_size = int(artifact["size_in_bytes"])
        artifact_digest = str(artifact["digest"])
        if artifact_id <= 0 or artifact_size <= 0 or not artifact_digest.startswith("sha256:"):
            return False
        data = api.download_artifact(artifact_id)
        if bridge._artifact_digest_bytes(data) != artifact_digest:
            return False
        bridge._verify_group_artifact(
            data,
            envelope=envelope,
            run_id=run_id,
            run_attempt=run_attempt,
        )
        return True
    except (KeyError, TypeError, ValueError, RuntimeError):
        return False


def _discover_run_compat(api, receipt: bridge.DispatchReceipt, *, timeout_seconds: float, poll_seconds: float) -> dict:
    """Resolve legacy group collisions by receipt content; preserve all other discovery."""
    if receipt.workflow != "lion-group-channel.yml":
        return _ORIGINAL_DISCOVER_RUN(
            api,
            receipt,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
        )

    envelope = _group_envelope_for_discovery(api, receipt)
    deadline = time.monotonic() + timeout_seconds
    while True:
        matches = _matching_runs_compat(api.workflow_runs(receipt.workflow, receipt.ref), receipt)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            verified = [
                candidate for candidate in matches
                if _group_candidate_verifies(api, receipt, envelope, candidate)
            ]
            if len(verified) > 1:
                raise RuntimeError("ambiguous group-channel runs remain after artifact binding")
            if len(verified) == 1:
                return verified[0]
        if time.monotonic() >= deadline:
            if matches:
                raise RuntimeError("matching group-channel run could not be uniquely artifact-bound")
            raise RuntimeError("matching workflow_dispatch run not observed before timeout")
        time.sleep(poll_seconds)


def _wait_terminal_diagnostic(api, run_id: int, *, timeout_seconds: float, poll_seconds: float) -> dict:
    """Preserve terminal semantics while exposing exact non-success run evidence."""
    terminal = _ORIGINAL_WAIT_TERMINAL(
        api,
        run_id,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )
    if terminal.get("status") == "completed" and terminal.get("conclusion") != "success":
        raise RuntimeError(
            "workflow run terminal non-success: "
            f"run_id={run_id} event={terminal.get('event')} "
            f"branch={terminal.get('head_branch')} head={terminal.get('head_sha')} "
            f"status={terminal.get('status')} conclusion={terminal.get('conclusion')}"
        )
    return terminal


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_signed_query(query: str) -> None:
    if not query:
        raise RuntimeError("artifact redirect is missing signed query")
    try:
        pairs = urllib.parse.parse_qsl(
            query,
            keep_blank_values=True,
            strict_parsing=True,
        )
    except ValueError as exc:
        raise RuntimeError("artifact redirect signed query is malformed") from exc
    signatures = [value for key, value in pairs if key == "sig"]
    if len(signatures) != 1:
        raise RuntimeError("artifact redirect must contain exactly one sig parameter")
    if not signatures[0]:
        raise RuntimeError("artifact redirect sig parameter must be non-empty")


def _validate_archive_location(location: str) -> str:
    parsed = urllib.parse.urlparse(location)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise RuntimeError("artifact redirect target is not safe HTTPS")
    if parsed.port not in (None, 443):
        raise RuntimeError("artifact redirect target uses non-HTTPS port")
    if _GITHUB_ACTIONS_ARCHIVE_HOST.fullmatch(host) is None:
        raise RuntimeError("artifact redirect host is not an allowlisted GitHub Actions archive host")
    if not parsed.path.startswith("/actions-results/"):
        raise RuntimeError("artifact redirect path is not GitHub Actions results storage")
    _validate_signed_query(parsed.query)
    return location


def _artifact_redirect(api: bridge.GitHubApi, artifact_id: int) -> str:
    if artifact_id <= 0:
        raise RuntimeError("artifact id invalid")
    path = f"/repos/{api.repository}/actions/artifacts/{artifact_id}/zip"
    request = urllib.request.Request(
        api.api_url + path,
        method="GET",
        headers=api._headers(),
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=20) as response:
            code = response.status
            location = response.headers.get("Location")
    except urllib.error.HTTPError as exc:
        if exc.code not in _REDIRECT_CODES:
            raise RuntimeError(f"artifact API redirect request failed: {exc.code}") from exc
        code = exc.code
        location = exc.headers.get("Location")
    if code not in _REDIRECT_CODES or not location:
        raise RuntimeError("artifact API did not return a signed redirect")
    return _validate_archive_location(location)


def _download_signed_archive(location: str) -> bytes:
    safe_location = _validate_archive_location(location)
    request = urllib.request.Request(
        safe_location,
        method="GET",
        headers={"User-Agent": "lion-actions-artifact-download/2"},
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError(f"signed artifact download non-terminal status: {response.status}")
            data = response.read(MAX_ARTIFACT_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in _REDIRECT_CODES:
            raise RuntimeError("signed artifact download attempted a second redirect") from exc
        raise RuntimeError(f"signed artifact download failed: {exc.code}") from exc
    if not data:
        raise RuntimeError("artifact archive is empty")
    if len(data) > MAX_ARTIFACT_BYTES:
        raise RuntimeError("artifact archive exceeds size limit")
    return data


def _download_artifact_compat(api: bridge.GitHubApi, artifact_id: int) -> bytes:
    return _download_signed_archive(_artifact_redirect(api, artifact_id))


def main(argv: list[str] | None = None) -> int:
    bridge._matching_runs = _matching_runs_compat
    bridge._discover_run = _discover_run_compat
    bridge._wait_terminal = _wait_terminal_diagnostic
    bridge.GitHubApi.download_artifact = _download_artifact_compat
    return bridge.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
