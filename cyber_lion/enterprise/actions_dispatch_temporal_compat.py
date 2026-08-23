"""Bounded compatibility shim for Actions run observation.

Legacy dispatch receipts may timestamp acceptance just after GitHub creates the run, so
run discovery permits at most a 60-second lookback while preserving exact event/ref/head
and ambiguity checks. Artifact downloads are also handled as a two-hop trust transition:
the GitHub API request is authenticated, while the returned signed blob URL is fetched
without forwarding the GitHub bearer token. This shim does not dispatch on observation
and does not mint authority.
"""
from __future__ import annotations

from datetime import timedelta
import urllib.error
import urllib.parse
import urllib.request

from cyber_lion.enterprise import actions_dispatch_bridge as bridge

LEGACY_LOOKBACK_SECONDS = 60
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_ALLOWED_ARCHIVE_SUFFIXES = (".blob.core.windows.net",)


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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_archive_location(location: str) -> str:
    parsed = urllib.parse.urlparse(location)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise RuntimeError("artifact redirect target is not safe HTTPS")
    if not any(host.endswith(suffix) for suffix in _ALLOWED_ARCHIVE_SUFFIXES):
        raise RuntimeError("artifact redirect host is not allowlisted")
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
        headers={"User-Agent": "lion-actions-artifact-download/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(MAX_ARTIFACT_BYTES + 1)
    except urllib.error.HTTPError as exc:
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
    bridge.GitHubApi.download_artifact = _download_artifact_compat
    return bridge.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
