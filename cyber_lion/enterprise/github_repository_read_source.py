"""Concrete read-only GitHub REST adapter for F005-K repository observation."""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from hashlib import sha1, sha256
import json
import os
from pathlib import Path
import socket
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from cyber_lion.contracts.fleet_repository_observation_source import (
    DEFAULT_BRANCH,
    REPOSITORY,
    AncestryEvidence,
    FleetRegistryPinLiveReadSource,
    LiveBranch,
)
from cyber_lion.contracts.repository_expansion import (
    FleetRegistryPinSnapshot,
    RepositoryManifestObservation,
    RepositoryPinObservation,
    _parse_registry_payload,
    materialize_registry_pin_snapshot,
    registry_semantic_digest,
)
from cyber_lion.enterprise.conformance import canonical_manifest_digest
from cyber_lion.enterprise.federation import RepositoryManifest
from cyber_lion.enterprise.models import EnterpriseModelError


class GitHubReadSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class ReadOnlyHttpTransport(Protocol):
    def get(self, url: str, *, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        ...


class UrllibReadOnlyTransport:
    """GET-only transport; it deliberately exposes no mutation verb."""

    class _NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    def get(self, url: str, *, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "api.github.com"
            or parsed.port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise GitHubReadSourceError("GitHub transport URL denied")
        request = Request(url=url, headers=dict(headers), method="GET")
        try:
            with build_opener(self._NoRedirect()).open(request, timeout=timeout) as response:
                return HttpResponse(
                    status=int(response.status),
                    headers={str(k): str(v) for k, v in response.headers.items()},
                    body=response.read(),
                )
        except HTTPError as exc:
            return HttpResponse(
                status=int(exc.code),
                headers={str(k): str(v) for k, v in exc.headers.items()},
                body=exc.read(),
            )
        except (TimeoutError, socket.timeout) as exc:
            raise GitHubReadSourceError("GitHub request timeout") from exc
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise GitHubReadSourceError("GitHub request timeout") from exc
            raise GitHubReadSourceError("GitHub transport failure") from exc
        except OSError as exc:
            raise GitHubReadSourceError("GitHub transport failure") from exc


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GitHubReadSourceError("duplicate GitHub JSON key denied")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise GitHubReadSourceError(f"non-standard JSON constant denied: {value}")


def _json(raw: bytes, name: str) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, GitHubReadSourceError) as exc:
        raise GitHubReadSourceError(f"{name} JSON invalid") from exc


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GitHubReadSourceError(f"{name} must be object")
    return value


def _sha(value: object, name: str) -> str:
    if not isinstance(value, str) or len(value) != 40 or any(ch not in "0123456789abcdef" for ch in value):
        raise GitHubReadSourceError(f"{name} invalid")
    return value


def _nonnegative_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GitHubReadSourceError(f"{name} invalid")
    return value


class GitHubRESTReadSource:
    """Concrete GitHubReadSource bound to the canonical repository."""

    TOKEN_ENV = "GITHUB_TOKEN"

    def __init__(
        self,
        *,
        token: str,
        transport: ReadOnlyHttpTransport | None = None,
        api_base: str = "https://api.github.com",
        timeout: float = 10.0,
    ) -> None:
        if not isinstance(token, str) or not token.strip():
            raise GitHubReadSourceError("GitHub bearer token missing")
        if not isinstance(api_base, str) or not api_base.startswith("https://"):
            raise GitHubReadSourceError("GitHub API base must be HTTPS")
        if transport is None and api_base.rstrip("/") != "https://api.github.com":
            raise GitHubReadSourceError("default GitHub transport requires canonical API origin")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise GitHubReadSourceError("GitHub timeout invalid")
        self._token = token.strip()
        self._transport = transport or UrllibReadOnlyTransport()
        self._api_base = api_base.rstrip("/")
        self._timeout = float(timeout)

    @classmethod
    def from_environment(
        cls,
        *,
        transport: ReadOnlyHttpTransport | None = None,
        api_base: str = "https://api.github.com",
        timeout: float = 10.0,
        environ: Mapping[str, str] | None = None,
    ) -> "GitHubRESTReadSource":
        source = os.environ if environ is None else environ
        token = source.get(cls.TOKEN_ENV)
        if token is None or not token.strip():
            raise GitHubReadSourceError(f"{cls.TOKEN_ENV} missing")
        return cls(token=token, transport=transport, api_base=api_base, timeout=timeout)

    def _bind(self, repository: str) -> None:
        if repository != REPOSITORY:
            raise GitHubReadSourceError("repository substitution denied")

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "lion-f005-k2-read-source/1.0",
        }

    def _request_json(
        self,
        path: str,
        *,
        query: Mapping[str, object] | None = None,
        allow_no_common_ancestor: bool = False,
    ) -> Any:
        url = self._api_base + path
        if query:
            url += "?" + urlencode({key: str(value) for key, value in query.items()})
        try:
            response = self._transport.get(url, headers=self._headers(), timeout=self._timeout)
        except GitHubReadSourceError:
            raise
        except Exception as exc:
            raise GitHubReadSourceError("GitHub transport failure") from exc

        if response.status in {403, 429}:
            raise GitHubReadSourceError("GitHub rate-limit or access denial")
        if response.status == 404 and allow_no_common_ancestor:
            value = _object(_json(response.body, "GitHub compare error"), "GitHub compare error")
            message = value.get("message")
            if isinstance(message, str) and "no common ancestor" in message.casefold():
                return {"__no_common_ancestor__": True}
        if response.status < 200 or response.status >= 300:
            raise GitHubReadSourceError(f"GitHub HTTP status denied: {response.status}")
        return _json(response.body, "GitHub response")

    def default_head(self, repository: str, default_branch: str) -> tuple[str, str]:
        self._bind(repository)
        if default_branch != DEFAULT_BRANCH:
            raise GitHubReadSourceError("default branch substitution denied")
        repo = quote(repository, safe="/")
        branch = quote(default_branch, safe="")
        value = _object(
            self._request_json(f"/repos/{repo}/branches/{branch}"),
            "branch response",
        )
        commit = _object(value.get("commit"), "branch commit")
        head = _sha(commit.get("sha"), "default head")

        commit_value = _object(
            self._request_json(f"/repos/{repo}/git/commits/{head}"),
            "commit response",
        )
        tree = _object(commit_value.get("tree"), "commit tree")
        tree_sha = _sha(tree.get("sha"), "default tree")
        return head, tree_sha

    def list_branches_page(
        self,
        repository: str,
        cursor: str | None,
    ) -> tuple[tuple[LiveBranch, ...], str | None]:
        self._bind(repository)
        if cursor is None:
            page = 1
        else:
            if not isinstance(cursor, str) or not cursor.isdigit() or int(cursor) < 1:
                raise GitHubReadSourceError("branch pagination cursor invalid")
            page = int(cursor)

        repo = quote(repository, safe="/")
        value = self._request_json(
            f"/repos/{repo}/branches",
            query={"per_page": 100, "page": page},
        )
        if not isinstance(value, list):
            raise GitHubReadSourceError("branch list must be array")

        branches: list[LiveBranch] = []
        for item in value:
            obj = _object(item, "branch item")
            name = obj.get("name")
            if not isinstance(name, str) or not name or name.startswith("refs/"):
                raise GitHubReadSourceError("branch name invalid")
            commit = _object(obj.get("commit"), "branch item commit")
            head = _sha(commit.get("sha"), "branch head")
            branches.append(LiveBranch(name, head).validate())

        next_cursor = str(page + 1) if len(value) == 100 else None
        return tuple(branches), next_cursor

    def compare_to_default(
        self,
        repository: str,
        default_head: str,
        branch_head: str,
        branch: str,
    ) -> AncestryEvidence:
        self._bind(repository)
        _sha(default_head, "default head")
        _sha(branch_head, "branch head")
        if not isinstance(branch, str) or not branch:
            raise GitHubReadSourceError("branch invalid")

        repo = quote(repository, safe="/")
        comparison = quote(f"{default_head}...{branch_head}", safe=".")
        raw = self._request_json(
            f"/repos/{repo}/compare/{comparison}",
            allow_no_common_ancestor=True,
        )
        value = _object(raw, "compare response")
        if value.get("__no_common_ancestor__") is True:
            return AncestryEvidence(branch, "NO_COMMON_ANCESTOR", None, None).validate()

        status = value.get("status")
        if not isinstance(status, str):
            raise GitHubReadSourceError("compare status invalid")
        ahead = _nonnegative_int(value.get("ahead_by"), "compare ahead_by")
        behind = _nonnegative_int(value.get("behind_by"), "compare behind_by")

        if status == "identical":
            evidence = AncestryEvidence(branch, "IDENTICAL", ahead, behind)
        elif status == "behind":
            evidence = AncestryEvidence(branch, "HEAD_ANCESTOR_OF_DEFAULT", ahead, behind)
        elif status == "ahead":
            evidence = AncestryEvidence(branch, "DEFAULT_ANCESTOR_OF_HEAD", ahead, behind)
        elif status == "diverged":
            evidence = AncestryEvidence(branch, "DIVERGED", ahead, behind)
        else:
            raise GitHubReadSourceError("unknown GitHub ancestry status denied")
        return evidence.validate()


class GitHubFleetPinSourceError(GitHubReadSourceError):
    pass


_CANONICAL_GITHUB_API = "https://api.github.com"
_CANONICAL_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "registry" / "repositories.json"
_FLEET_MANIFEST_PATH = "cyber-lion.repository.json"
_MANIFEST_MAX_BYTES = 1_048_576


class GitHubFleetRegistryPinReadSource:
    """GET-only GitHub source for R2E3/R2E4 fleet repository provenance."""

    TOKEN_ENV = "GITHUB_TOKEN"

    def __init__(
        self,
        *,
        token: str,
        transport: ReadOnlyHttpTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        if not isinstance(token, str) or not token.strip():
            raise GitHubFleetPinSourceError("GitHub bearer token missing")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise GitHubFleetPinSourceError("GitHub timeout invalid")
        self._token = token.strip()
        self._transport = transport or UrllibReadOnlyTransport()
        self._timeout = float(timeout)

    @classmethod
    def from_environment(
        cls,
        *,
        transport: ReadOnlyHttpTransport | None = None,
        timeout: float = 10.0,
        environ: Mapping[str, str] | None = None,
    ) -> "GitHubFleetRegistryPinReadSource":
        source = os.environ if environ is None else environ
        token = source.get(cls.TOKEN_ENV)
        if token is None or not token.strip():
            raise GitHubFleetPinSourceError(f"{cls.TOKEN_ENV} missing")
        return cls(token=token, transport=transport, timeout=timeout)

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "lion-r2e3-fleet-pin-read-source/1.0",
        }

    def _request(self, path: str) -> HttpResponse:
        if not isinstance(path, str) or not path.startswith("/") or "\x00" in path:
            raise GitHubFleetPinSourceError("GitHub request path invalid")
        url = _CANONICAL_GITHUB_API + path
        try:
            response = self._transport.get(url, headers=self._headers(), timeout=self._timeout)
        except GitHubReadSourceError:
            raise
        except Exception as exc:
            raise GitHubFleetPinSourceError("GitHub transport failure") from exc
        if type(response) is not HttpResponse:
            raise GitHubFleetPinSourceError("GitHub transport response invalid")
        return response

    def _request_object(self, path: str, name: str) -> dict[str, Any]:
        response = self._request(path)
        if response.status in {403, 429}:
            raise GitHubFleetPinSourceError("GitHub rate-limit or access denial")
        if response.status < 200 or response.status >= 300:
            raise GitHubFleetPinSourceError(f"GitHub HTTP status denied: {response.status}")
        return _object(_json(response.body, name), name)

    def read_default_head(self, repository: str, default_branch: str) -> tuple[str, str]:
        repo = quote(repository, safe="/")
        branch = quote(default_branch, safe="")
        branch_value = self._request_object(
            f"/repos/{repo}/branches/{branch}",
            "fleet branch response",
        )
        commit = _object(branch_value.get("commit"), "fleet branch commit")
        head = _sha(commit.get("sha"), "fleet default head")
        commit_value = self._request_object(
            f"/repos/{repo}/git/commits/{head}",
            "fleet commit response",
        )
        tree = _object(commit_value.get("tree"), "fleet commit tree")
        return head, _sha(tree.get("sha"), "fleet default tree")

    def _manifest_response(self, repository: str, head: str) -> HttpResponse:
        _sha(head, "fleet manifest head")
        repo = quote(repository, safe="/")
        ref = quote(head, safe="")
        return self._request(
            f"/repos/{repo}/contents/{_FLEET_MANIFEST_PATH}?ref={ref}"
        )

    def manifest_present(self, repository: str, head: str) -> bool:
        response = self._manifest_response(repository, head)
        if response.status == 200:
            return True
        if response.status == 404:
            return False
        if response.status in {403, 429}:
            raise GitHubFleetPinSourceError("GitHub manifest access or rate-limit denial")
        raise GitHubFleetPinSourceError(
            f"GitHub manifest HTTP status denied: {response.status}"
        )

    def _read_manifest_at_pin(
        self,
        pin: RepositoryPinObservation,
    ) -> tuple[RepositoryManifestObservation, RepositoryManifest | None, dict[str, Any] | None]:
        try:
            pin.validate()
        except Exception as exc:
            raise GitHubFleetPinSourceError("fleet manifest pin invalid") from exc

        response = self._manifest_response(pin.repository, pin.head)
        if response.status == 404:
            if pin.manifest_present:
                raise GitHubFleetPinSourceError("fleet manifest state contradicts pinned presence")
            observation = RepositoryManifestObservation(
                repository=pin.repository,
                default_branch=pin.default_branch,
                head=pin.head,
                tree=pin.tree,
                manifest_state="ABSENT",
                manifest_path=_FLEET_MANIFEST_PATH,
                git_blob_sha=None,
                manifest_byte_sha256=None,
                manifest_semantic_digest=None,
                source_ref=_fleet_manifest_source_ref(
                    pin.repository,
                    pin.default_branch,
                    pin.head,
                    pin.tree,
                    "ABSENT",
                    None,
                    None,
                    None,
                ),
            ).validate()
            return observation, None, None
        if response.status != 200:
            if response.status in {403, 429}:
                raise GitHubFleetPinSourceError("GitHub manifest access or rate-limit denial")
            raise GitHubFleetPinSourceError(
                f"GitHub manifest HTTP status denied: {response.status}"
            )
        if not pin.manifest_present:
            raise GitHubFleetPinSourceError("fleet manifest state contradicts pinned absence")

        envelope = _object(_json(response.body, "fleet manifest response"), "fleet manifest response")
        if envelope.get("type") != "file":
            raise GitHubFleetPinSourceError("fleet manifest content type invalid")
        if envelope.get("path") != _FLEET_MANIFEST_PATH:
            raise GitHubFleetPinSourceError("fleet manifest path substitution denied")
        if envelope.get("encoding") != "base64":
            raise GitHubFleetPinSourceError("fleet manifest encoding invalid")
        git_blob_sha = _sha(envelope.get("sha"), "fleet manifest blob sha")
        size = _nonnegative_int(envelope.get("size"), "fleet manifest size")
        if size > _MANIFEST_MAX_BYTES:
            raise GitHubFleetPinSourceError("fleet manifest size limit exceeded")
        content = envelope.get("content")
        if not isinstance(content, str) or not content:
            raise GitHubFleetPinSourceError("fleet manifest base64 content missing")
        if any(ch in content for ch in (" ", "\t", "\v", "\f")):
            raise GitHubFleetPinSourceError("fleet manifest base64 whitespace invalid")
        normalized = content.replace("\r", "").replace("\n", "")
        try:
            encoded = normalized.encode("ascii")
            raw = base64.b64decode(encoded, validate=True)
        except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
            raise GitHubFleetPinSourceError("fleet manifest base64 invalid") from exc
        if len(raw) != size or len(raw) > _MANIFEST_MAX_BYTES:
            raise GitHubFleetPinSourceError("fleet manifest decoded size mismatch")

        reconstructed = sha1(
            b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
        ).hexdigest()
        if reconstructed != git_blob_sha:
            raise GitHubFleetPinSourceError("fleet manifest Git blob identity mismatch")
        byte_sha256 = sha256(raw).hexdigest()
        mapping = _object(_json(raw, "fleet manifest content"), "fleet manifest content")
        try:
            manifest = RepositoryManifest.from_mapping(mapping)
        except EnterpriseModelError as exc:
            raise GitHubFleetPinSourceError("fleet manifest typed validation failed") from exc
        if manifest.repository_id != pin.repository:
            raise GitHubFleetPinSourceError("fleet manifest repository identity mismatch")
        if manifest.default_branch != pin.default_branch:
            raise GitHubFleetPinSourceError("fleet manifest default branch mismatch")
        semantic_digest = canonical_manifest_digest(mapping)
        observation = RepositoryManifestObservation(
            repository=pin.repository,
            default_branch=pin.default_branch,
            head=pin.head,
            tree=pin.tree,
            manifest_state="PRESENT",
            manifest_path=_FLEET_MANIFEST_PATH,
            git_blob_sha=git_blob_sha,
            manifest_byte_sha256=byte_sha256,
            manifest_semantic_digest=semantic_digest,
            source_ref=_fleet_manifest_source_ref(
                pin.repository,
                pin.default_branch,
                pin.head,
                pin.tree,
                "PRESENT",
                git_blob_sha,
                byte_sha256,
                semantic_digest,
            ),
        ).validate()
        return observation, manifest, mapping


def _fleet_pin_source_ref(
    repository: str,
    default_branch: str,
    head: str,
    tree: str,
    manifest_present: bool,
) -> str:
    payload = json.dumps(
        {
            "repository": repository,
            "default_branch": default_branch,
            "head": head,
            "tree": tree,
            "manifest_present": manifest_present,
            "manifest_path": _FLEET_MANIFEST_PATH,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "github-live-v1:" + sha256(
        b"LION/R2E3/FLEET-PIN-LIVE-SOURCE/1\0" + payload
    ).hexdigest()


def _fleet_manifest_source_ref(
    repository: str,
    default_branch: str,
    head: str,
    tree: str,
    manifest_state: str,
    git_blob_sha: str | None,
    manifest_byte_sha256: str | None,
    manifest_semantic_digest: str | None,
) -> str:
    payload = json.dumps(
        {
            "repository": repository,
            "default_branch": default_branch,
            "head": head,
            "tree": tree,
            "manifest_state": manifest_state,
            "manifest_path": _FLEET_MANIFEST_PATH,
            "git_blob_sha": git_blob_sha,
            "manifest_byte_sha256": manifest_byte_sha256,
            "manifest_semantic_digest": manifest_semantic_digest,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "github-manifest-live-v1:" + sha256(
        b"LION/R2E4/REPOSITORY-MANIFEST-LIVE-SOURCE/1\0" + payload
    ).hexdigest()


def _require_canonical_registry_payload(registry_payload: bytes) -> None:
    try:
        canonical_payload = _CANONICAL_REGISTRY_PATH.read_bytes()
    except OSError as exc:
        raise GitHubFleetPinSourceError("canonical fleet registry unavailable") from exc
    try:
        supplied = registry_semantic_digest(registry_payload)
        canonical = registry_semantic_digest(canonical_payload)
    except Exception as exc:
        raise GitHubFleetPinSourceError("fleet registry validation failed") from exc
    if supplied != canonical:
        raise GitHubFleetPinSourceError("fleet registry substitution denied")


def _materialize_live_registry_pin_snapshot_with_source(
    registry_payload: bytes,
    *,
    source: FleetRegistryPinLiveReadSource,
) -> FleetRegistryPinSnapshot:
    _require_canonical_registry_payload(registry_payload)
    try:
        _, members = _parse_registry_payload(registry_payload)
    except Exception as exc:
        raise GitHubFleetPinSourceError("fleet registry parse failed") from exc

    first_pass: dict[str, tuple[str, str]] = {}
    observations: list[RepositoryPinObservation] = []
    for member in members:
        observed = source.read_default_head(member.repository, member.default_branch)
        if type(observed) is not tuple or len(observed) != 2:
            raise GitHubFleetPinSourceError("fleet head source returned invalid type")
        head = _sha(observed[0], "fleet observed head")
        tree = _sha(observed[1], "fleet observed tree")
        manifest_present = source.manifest_present(member.repository, head)
        if type(manifest_present) is not bool:
            raise GitHubFleetPinSourceError("fleet manifest observation must be bool")
        first_pass[member.repository] = (head, tree)
        observations.append(
            RepositoryPinObservation(
                repository=member.repository,
                default_branch=member.default_branch,
                head=head,
                tree=tree,
                manifest_present=manifest_present,
                source_ref=_fleet_pin_source_ref(
                    member.repository,
                    member.default_branch,
                    head,
                    tree,
                    manifest_present,
                ),
            ).validate()
        )

    for member in members:
        observed = source.read_default_head(member.repository, member.default_branch)
        if type(observed) is not tuple or len(observed) != 2:
            raise GitHubFleetPinSourceError("fleet currentness source returned invalid type")
        current = (
            _sha(observed[0], "fleet reobserved head"),
            _sha(observed[1], "fleet reobserved tree"),
        )
        if current != first_pass[member.repository]:
            raise GitHubFleetPinSourceError(
                f"fleet sweep drift denied: {member.repository}"
            )

    try:
        return materialize_registry_pin_snapshot(registry_payload, tuple(observations))
    except Exception as exc:
        raise GitHubFleetPinSourceError("fleet live pin snapshot materialization failed") from exc


def materialize_live_registry_pin_snapshot(
    registry_payload: bytes,
) -> FleetRegistryPinSnapshot:
    """Canonical R2E3 entrypoint: registry bytes are the only caller-controlled input."""
    source = GitHubFleetRegistryPinReadSource.from_environment()
    return _materialize_live_registry_pin_snapshot_with_source(
        registry_payload,
        source=source,
    )


def _materialize_live_registry_manifest_observations_with_source(
    registry_payload: bytes,
    *,
    source: Any,
) -> tuple[
    FleetRegistryPinSnapshot,
    tuple[tuple[RepositoryManifestObservation, RepositoryManifest | None], ...],
]:
    snapshot = _materialize_live_registry_pin_snapshot_with_source(
        registry_payload,
        source=source,
    )
    results: list[tuple[RepositoryManifestObservation, RepositoryManifest | None]] = []
    for pin in snapshot.observations:
        reader = getattr(source, "_read_manifest_at_pin", None)
        if reader is None or not callable(reader):
            raise GitHubFleetPinSourceError("fleet manifest content source unavailable")
        result = reader(pin)
        if type(result) is not tuple or len(result) != 3:
            raise GitHubFleetPinSourceError("fleet manifest content result invalid")
        observation, manifest, mapping = result
        if not isinstance(observation, RepositoryManifestObservation):
            raise GitHubFleetPinSourceError("fleet manifest observation type invalid")
        observation.validate()
        expected_state = "PRESENT" if pin.manifest_present else "ABSENT"
        if observation.manifest_state != expected_state:
            raise GitHubFleetPinSourceError("fleet manifest semantic state differs from pin")
        if (
            observation.repository,
            observation.default_branch,
            observation.head,
            observation.tree,
        ) != (pin.repository, pin.default_branch, pin.head, pin.tree):
            raise GitHubFleetPinSourceError("fleet manifest observation identity differs from pin")
        if expected_state == "PRESENT":
            if not isinstance(manifest, RepositoryManifest) or type(mapping) is not dict:
                raise GitHubFleetPinSourceError("fleet present manifest projection missing")
            if canonical_manifest_digest(mapping) != observation.manifest_semantic_digest:
                raise GitHubFleetPinSourceError("fleet manifest semantic digest rebound mismatch")
        elif manifest is not None or mapping is not None:
            raise GitHubFleetPinSourceError("fleet absent manifest cannot carry semantic projection")
        results.append((observation, manifest))

    for pin in snapshot.observations:
        observed = source.read_default_head(pin.repository, pin.default_branch)
        if type(observed) is not tuple or len(observed) != 2:
            raise GitHubFleetPinSourceError("fleet post-manifest currentness source invalid")
        current = (
            _sha(observed[0], "fleet post-manifest head"),
            _sha(observed[1], "fleet post-manifest tree"),
        )
        if current != (pin.head, pin.tree):
            raise GitHubFleetPinSourceError(
                f"fleet post-manifest drift denied: {pin.repository}"
            )

    return snapshot, tuple(results)


def materialize_live_registry_manifest_observations(
    registry_payload: bytes,
) -> tuple[
    FleetRegistryPinSnapshot,
    tuple[tuple[RepositoryManifestObservation, RepositoryManifest | None], ...],
]:
    """Canonical R2E4 entrypoint: exact-head manifest semantics from the live fleet."""
    source = GitHubFleetRegistryPinReadSource.from_environment()
    return _materialize_live_registry_manifest_observations_with_source(
        registry_payload,
        source=source,
    )
