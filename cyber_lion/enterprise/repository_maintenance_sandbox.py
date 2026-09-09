"""Fail-closed repository-maintenance sandbox and GitHub branch cleanup backend."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from cyber_lion.contracts.branch_ownership_registry import BranchOwnershipRecord
from cyber_lion.contracts.repository_maintenance_sandbox import (
    REPOSITORY,
    MAINTENANCE_BRANCH_ALLOWLIST,
    RepositoryMaintenanceContractError,
    RepositoryMaintenanceExecutionReceipt,
    RepositoryMaintenanceOperation,
    RepositoryMaintenancePolicy,
    canonical_json,
    evidence_digest,
    validate_branch_name,
)


class RepositoryMaintenanceError(RuntimeError):
    pass


CLOSURE_MANIFEST_PATH = "LION/maintenance/branch-closure-manifest-v1.json"
CLOSURE_SCHEMA_VERSION = "lion.branch-closure-manifest/v1"
CLOSURE_RESEARCH_BASE_SHA = "c50465888d55257ff676712bc7de8431a843ad63"
CLOSURE_RESEARCH_BASE_TREE = "ea4f7bd2c11cbc84d7283ae0b3b4bfc006bca5a6"
CLOSURE_RESEARCH_MANIFEST_SHA256 = "ccfad8dbd1cc5adee8058dedeea578fe9c8f8178466b910a4c3a389dd2b92b79"
CLOSURE_ARCHIVE_BUNDLE_SHA256 = "2c77fb2da36cfda82e97b9a5852172ffae783a1e299821d25dc678b7c2d7dd5e"
CLOSURE_RESEARCH_CLASSES = frozenset({"A", "B", "C", "G", "H", "I"})
CLOSURE_DISPOSITIONS = frozenset({
    "ALREADY_INTEGRATED", "ARCHIVE_ONLY", "CONTENT_IDENTICAL", "OBSOLETE_ARCHITECTURE",
    "SEMANTICALLY_IN_MASTER", "SUPERSEDED_BY_MASTER", "TEST_OR_NEGATIVE_CONTROL",
})


def _closure_evidence_from_manifest(value: object, *, branch: str, expected_head: str, master_sha: str, master_parents: tuple[str, ...]) -> str | None:
    if not isinstance(value, dict):
        raise RepositoryMaintenanceError("closure manifest must be object")
    exact = {
        "schema_version": CLOSURE_SCHEMA_VERSION,
        "repository": REPOSITORY,
        "research_base_sha": CLOSURE_RESEARCH_BASE_SHA,
        "research_base_tree": CLOSURE_RESEARCH_BASE_TREE,
        "research_manifest_sha256": CLOSURE_RESEARCH_MANIFEST_SHA256,
        "archive_bundle_sha256": CLOSURE_ARCHIVE_BUNDLE_SHA256,
    }
    for key, expected in exact.items():
        if value.get(key) != expected:
            raise RepositoryMaintenanceError(f"closure manifest binding drift: {key}")
    entries = value.get("entries")
    count = value.get("count")
    if not isinstance(entries, list) or isinstance(count, bool) or not isinstance(count, int) or count != len(entries):
        raise RepositoryMaintenanceError("closure manifest count invalid")
    names: list[str] = []
    for item in entries:
        if not isinstance(item, dict):
            raise RepositoryMaintenanceError("closure manifest entry invalid")
        b = item.get("branch")
        h = item.get("expected_head")
        validate_branch_name(b)
        if not isinstance(h, str) or re.fullmatch(r"[0-9a-f]{40}", h) is None:
            raise RepositoryMaintenanceError("closure manifest head invalid")
        if item.get("research_class") not in CLOSURE_RESEARCH_CLASSES:
            raise RepositoryMaintenanceError("closure manifest research class invalid")
        if item.get("cleanup_class") not in {"A", "B"}:
            raise RepositoryMaintenanceError("closure manifest cleanup class invalid")
        if item.get("disposition") not in CLOSURE_DISPOSITIONS:
            raise RepositoryMaintenanceError("closure manifest disposition invalid")
        if item.get("archive_proven") is not True or item.get("archive_bundle_sha256") != CLOSURE_ARCHIVE_BUNDLE_SHA256:
            raise RepositoryMaintenanceError("closure manifest archive proof invalid")
        names.append(b)
    if len(names) != len(set(names)) or names != sorted(names):
        raise RepositoryMaintenanceError("closure manifest branches must be unique and sorted")
    if CLOSURE_RESEARCH_BASE_SHA not in set(master_parents):
        raise RepositoryMaintenanceError("closure manifest is stale for current master")
    matches = [item for item in entries if item.get("branch") == branch]
    if not matches:
        return None
    if len(matches) != 1:
        raise RepositoryMaintenanceError("closure manifest target cardinality invalid")
    item = matches[0]
    if item.get("expected_head") != expected_head or item.get("cleanup_class") != "B":
        return None
    payload = {
        "schema_version": CLOSURE_SCHEMA_VERSION,
        "repository": REPOSITORY,
        "research_base_sha": CLOSURE_RESEARCH_BASE_SHA,
        "research_manifest_sha256": CLOSURE_RESEARCH_MANIFEST_SHA256,
        "archive_bundle_sha256": CLOSURE_ARCHIVE_BUNDLE_SHA256,
        "current_master": master_sha,
        "entry": item,
    }
    return evidence_digest(payload, "CLOSURE")


@dataclass(frozen=True)
class BranchObservation:
    branch: str
    head_sha: str
    compare_status: str
    ahead_by: int
    behind_by: int
    open_pr_count: int
    ownership_state: str
    ownership_source: str
    classification: str

    def canonical(self) -> dict[str, object]:
        return asdict(self)


class ReplayGuard:
    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()

    def consume(self, mission_id: str, operation_id: str) -> bool:
        key = (mission_id, operation_id)
        if key in self._seen:
            return False
        self._seen.add(key)
        return True


class GitHubRepositoryMaintenanceBackend:
    """Read-capable GitHub REST backend; repository mutation is denied here.

    The production ref-delete effect is available only through the separately
    mediated SlashSafeGitHubRepositoryMaintenanceBackend in
    repository_maintenance_cleanup. Keeping this base adapter fail-closed makes
    the historical CLI/helper path incapable of bypassing the effect boundary.
    """

    def __init__(self, repository: str, token: str, api_url: str = "https://api.github.com") -> None:
        if repository != REPOSITORY:
            raise RepositoryMaintenanceError("repository substitution denied")
        parsed = urllib.parse.urlsplit(api_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "api.github.com"
            or parsed.port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise RepositoryMaintenanceError("GitHub API origin must be canonical HTTPS api.github.com")
        if not isinstance(token, str) or not token:
            raise RepositoryMaintenanceError("runtime credential unavailable")
        self.repository = repository
        self._token = token
        self.api_url = "https://api.github.com"
        self.backend_id = "github-rest-ref-maintenance-v1"
        self.backend_identity_digest = sha256(
            f"{self.backend_id}\0{self.repository}\0{self.api_url}".encode()
        ).hexdigest()
        self.backend_implementation_digest = sha256(__file__.encode()).hexdigest()

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "lion-repository-maintenance-sandbox/1",
        }

    def _request_get_exact(self, path: str, *, allow_404: bool = False) -> tuple[int, object | None]:
        if not isinstance(path, str) or not path.startswith("/") or ".." in path:
            raise RepositoryMaintenanceError("unsafe GitHub API path")
        req = urllib.request.Request(
            self.api_url + path,
            data=None,
            method="GET",
            headers=self._headers(),
        )
        try:
            with urllib.request.build_opener(self._NoRedirect()).open(req, timeout=30) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            if allow_404 and exc.code == 404:
                return 404, None
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RepositoryMaintenanceError(f"GitHub API GET {path} failed: {exc.code}: {detail}") from exc

    def _request(self, method: str, path: str, body: object | None = None, *, allow_404: bool = False) -> tuple[int, object | None]:
        """Compatibility read surface. Caller-selected consequential methods are unrepresentable."""
        if method != "GET" or body is not None:
            raise RepositoryMaintenanceError("historical maintenance transport is GET-only")
        return self._request_get_exact(path, allow_404=allow_404)

    def master_sha(self) -> str:
        status, value = self._request("GET", f"/repos/{self.repository}/git/ref/heads/master")
        try:
            sha = value["object"]["sha"]
        except Exception as exc:
            raise RepositoryMaintenanceError("unable to resolve master") from exc
        if status != 200 or not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{40}", sha) is None:
            raise RepositoryMaintenanceError("invalid master observation")
        return sha

    def branch_sha(self, branch: str) -> str | None:
        validate_branch_name(branch)
        encoded = urllib.parse.quote(branch, safe="")
        status, value = self._request("GET", f"/repos/{self.repository}/git/ref/heads/{encoded}", allow_404=True)
        if status == 404:
            return None
        try:
            sha = value["object"]["sha"]
        except Exception as exc:
            raise RepositoryMaintenanceError("unable to resolve branch") from exc
        if status != 200 or not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{40}", sha) is None:
            raise RepositoryMaintenanceError("invalid branch observation")
        return sha

    def list_branches(self) -> list[str]:
        result: list[str] = []
        for page in range(1, 101):
            status, value = self._request("GET", f"/repos/{self.repository}/branches?per_page=100&page={page}")
            if status != 200 or not isinstance(value, list):
                raise RepositoryMaintenanceError("unable to enumerate branches")
            names = [item.get("name") for item in value if isinstance(item, dict)]
            if any(not isinstance(name, str) for name in names):
                raise RepositoryMaintenanceError("invalid branch list")
            result.extend(names)
            if len(value) < 100:
                break
        return sorted(set(result))

    def compare_branch_to_master(self, branch: str) -> dict[str, object]:
        validate_branch_name(branch)
        base = urllib.parse.quote(branch, safe="")
        status, value = self._request("GET", f"/repos/{self.repository}/compare/{base}...master")
        if status != 200 or not isinstance(value, dict):
            raise RepositoryMaintenanceError("compare unavailable")
        required = ("status", "ahead_by", "behind_by")
        if any(key not in value for key in required):
            raise RepositoryMaintenanceError("compare response incomplete")
        return {key: value[key] for key in required}

    def open_prs_for_branch(self, branch: str) -> list[dict]:
        validate_branch_name(branch)
        owner = self.repository.split("/", 1)[0]
        query = urllib.parse.urlencode({"state": "open", "head": f"{owner}:{branch}", "per_page": "100"})
        status, value = self._request("GET", f"/repos/{self.repository}/pulls?{query}")
        if status != 200 or not isinstance(value, list):
            raise RepositoryMaintenanceError("unable to inspect open PRs")
        return [item for item in value if isinstance(item, dict)]

    def _content_json(self, path: str, ref: str) -> object:
        encoded_path = "/".join(urllib.parse.quote(piece, safe="") for piece in path.split("/"))
        query = urllib.parse.urlencode({"ref": ref})
        status, value = self._request("GET", f"/repos/{self.repository}/contents/{encoded_path}?{query}")
        if status != 200 or not isinstance(value, dict):
            raise RepositoryMaintenanceError(f"unable to read {path}")
        import base64
        content = value.get("content")
        encoding = value.get("encoding")
        if encoding != "base64" or not isinstance(content, str):
            raise RepositoryMaintenanceError(f"unexpected content encoding for {path}")
        try:
            raw = base64.b64decode(content, validate=False)
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise RepositoryMaintenanceError(f"invalid JSON projection {path}") from exc

    def master_parents(self, master_sha: str) -> tuple[str, ...]:
        if not isinstance(master_sha, str) or re.fullmatch(r"[0-9a-f]{40}", master_sha) is None:
            raise RepositoryMaintenanceError("invalid master for parent observation")
        status, value = self._request("GET", f"/repos/{self.repository}/git/commits/{master_sha}")
        if status != 200 or not isinstance(value, dict):
            raise RepositoryMaintenanceError("master parent observation unavailable")
        parents = value.get("parents")
        if not isinstance(parents, list):
            raise RepositoryMaintenanceError("master parent observation invalid")
        result: list[str] = []
        for parent in parents:
            sha = parent.get("sha") if isinstance(parent, dict) else None
            if not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{40}", sha) is None:
                raise RepositoryMaintenanceError("master parent SHA invalid")
            result.append(sha)
        return tuple(result)

    def closure_evidence(self, branch: str, expected_head: str, master_sha: str) -> str | None:
        validate_branch_name(branch)
        value = self._content_json(CLOSURE_MANIFEST_PATH, master_sha)
        return _closure_evidence_from_manifest(
            value,
            branch=branch,
            expected_head=expected_head,
            master_sha=master_sha,
            master_parents=self.master_parents(master_sha),
        )

    @staticmethod
    def _contains_active_branch(value: object, branch: str) -> bool:
        active_states = {"PLANNED", "ACCEPTED", "STARTED", "IN_PROGRESS", "BLOCKED", "VERIFYING", "ACTIVE", "ASSIGNED", "BUILDING", "READY", "OPEN"}
        if isinstance(value, dict):
            branch_value = value.get("branch")
            state = value.get("state")
            if branch_value == branch and isinstance(state, str) and state in active_states:
                return True
            return any(GitHubRepositoryMaintenanceBackend._contains_active_branch(v, branch) for v in value.values())
        if isinstance(value, list):
            return any(GitHubRepositoryMaintenanceBackend._contains_active_branch(v, branch) for v in value)
        return False

    def ownership_observation(self, branch: str, master_sha: str) -> BranchOwnershipRecord:
        validate_branch_name(branch)
        projections = {
            "status": self._content_json("LION/status.json", master_sha),
            "drones": self._content_json("LION/ops/drone-registry.json", master_sha),
            "missions": self._content_json("LION/ops/mission-registry.json", master_sha),
        }
        active = any(self._contains_active_branch(value, branch) for value in projections.values())
        head = self.branch_sha(branch)
        if head is None:
            raise RepositoryMaintenanceError("branch disappeared during ownership observation")
        if active:
            return BranchOwnershipRecord(repository=self.repository, branch=branch, branch_head_sha=head, ownership_state="ACTIVE", mission_id="repository-projection-active-owner", baseline_sha=master_sha, superseded_by_branch=None, supersession_provenance_ref=None, source_provenance_ref=f"github:{master_sha}:LION/projections", epistemic_class="OBSERVED", record_revision=1).validate()
        return BranchOwnershipRecord(repository=self.repository, branch=branch, branch_head_sha=head, ownership_state="UNOWNED", mission_id=None, baseline_sha=None, superseded_by_branch=None, supersession_provenance_ref=None, source_provenance_ref=f"github:{master_sha}:LION/projections", epistemic_class="OBSERVED", record_revision=1).validate()

    def delete_exact_branch_ref(self, branch: str, expected_head: str) -> None:
        validate_branch_name(branch)
        if re.fullmatch(r"[0-9a-f]{40}", expected_head) is None:
            raise RepositoryMaintenanceError("invalid expected branch head")
        raise RepositoryMaintenanceError("direct repository ref delete denied; mediated boundary required")


def _observe_delete_classification(*, backend: object, branch: str, master_sha: str) -> tuple[str, dict[str, object], list[dict], BranchOwnershipRecord, BranchObservation, str | None]:
    head = backend.branch_sha(branch)
    if head is None:
        raise RepositoryMaintenanceError("branch disappeared during classification")
    compare = backend.compare_branch_to_master(branch)
    prs = backend.open_prs_for_branch(branch)
    ownership = backend.ownership_observation(branch, master_sha)
    eligible_a = compare["status"] in {"ahead", "identical"} and int(compare["behind_by"]) == 0 and not prs and ownership.ownership_state == "UNOWNED"
    closure_digest = None
    classification = "A" if eligible_a else "F"
    if not eligible_a and compare["status"] == "diverged" and not prs and ownership.ownership_state == "UNOWNED":
        resolver = getattr(backend, "closure_evidence", None)
        if callable(resolver):
            closure_digest = resolver(branch, head, master_sha)
        if closure_digest is not None:
            classification = "B"
    obs = BranchObservation(
        branch=branch,
        head_sha=head,
        compare_status=str(compare["status"]),
        ahead_by=int(compare["ahead_by"]),
        behind_by=int(compare["behind_by"]),
        open_pr_count=len(prs),
        ownership_state=ownership.ownership_state,
        ownership_source=ownership.source_provenance_ref,
        classification=classification,
    )
    return head, compare, prs, ownership, obs, closure_digest


def _classification_payload(*, classification: str, branch: str, head: str, master: str, ancestry: str, pr: str, ownership: str, closure: str | None) -> dict[str, object]:
    payload: dict[str, object] = {
        "classification": classification,
        "branch": branch,
        "head": head,
        "master": master,
        "ancestry": ancestry,
        "pr": pr,
        "ownership": ownership,
    }
    if classification == "B":
        if closure is None:
            raise RepositoryMaintenanceError("class B requires closure evidence")
        payload["closure"] = closure
    return payload


class RepositoryMaintenanceSandbox:
    def __init__(self, *, policy: RepositoryMaintenancePolicy, backend: GitHubRepositoryMaintenanceBackend, replay_guard: ReplayGuard | None = None) -> None:
        self.policy = policy.validate()
        self.backend = backend
        self.replay_guard = replay_guard or ReplayGuard()
        self._deletions = 0

    def _receipt(self, operation: RepositoryMaintenanceOperation, *, before_master: str, after_master: str, before_head: str, exists_after: bool, outcome: str, events: tuple[str, ...]) -> RepositoryMaintenanceExecutionReceipt:
        return RepositoryMaintenanceExecutionReceipt.build(schema_version="1.0.0", receipt_id=f"{operation.dispatch_id}:{operation.operation_id}", operation_id=operation.operation_id, operation_digest=operation.operation_digest(), policy_digest=self.policy.digest(), mission_id=operation.mission_id, drone_id=operation.drone_id, dispatch_id=operation.dispatch_id, fencing_token=operation.fencing_token, generation=operation.generation, repository=operation.repository, master_sha_before=before_master, master_sha_after=after_master, branch_name=operation.branch_name, branch_head_before=before_head, branch_exists_after=exists_after, effect="DELETE_BRANCH_REF", outcome=outcome, observed_event_refs=events, authority_effect=False, master_effect=False)

    def execute_delete(self, operation: RepositoryMaintenanceOperation) -> RepositoryMaintenanceExecutionReceipt:
        operation.validate()
        if operation.policy_digest != self.policy.digest():
            raise RepositoryMaintenanceError("policy binding mismatch")
        if operation.repository != self.policy.repository or operation.mission_id != self.policy.mission_id:
            raise RepositoryMaintenanceError("mission/repository substitution denied")
        if not self.replay_guard.consume(operation.mission_id, operation.operation_id):
            raise RepositoryMaintenanceError("operation replay denied")
        if self._deletions >= self.policy.max_deletions:
            raise RepositoryMaintenanceError("sandbox deletion budget exhausted")
        before_master = self.backend.master_sha()
        if before_master != operation.protected_master_sha:
            raise RepositoryMaintenanceError("stale master denied")
        before_head = self.backend.branch_sha(operation.branch_name)
        if before_head is None:
            return self._receipt(operation, before_master=before_master, after_master=before_master, before_head=operation.expected_branch_head, exists_after=False, outcome="ALREADY_ABSENT", events=(f"github:branch:{operation.branch_name}:absent",))
        if before_head != operation.expected_branch_head:
            raise RepositoryMaintenanceError("stale branch head denied")
        observed_head, compare, prs, ownership, observation, closure_digest = _observe_delete_classification(
            backend=self.backend, branch=operation.branch_name, master_sha=before_master
        )
        if observed_head != before_head:
            raise RepositoryMaintenanceError("branch changed during classification")
        ancestry_evidence = {"branch": operation.branch_name, "head": before_head, "master": before_master, "status": compare["status"], "ahead_by": compare["ahead_by"], "behind_by": compare["behind_by"]}
        pr_evidence = {"branch": operation.branch_name, "open_pr_ids": sorted(int(item["number"]) for item in prs if isinstance(item.get("number"), int) and not isinstance(item.get("number"), bool))}
        ownership_evidence = ownership.canonical_dict()
        if evidence_digest(ancestry_evidence, "ANCESTRY") != operation.ancestry_evidence_digest:
            raise RepositoryMaintenanceError("ancestry evidence substitution denied")
        if evidence_digest(pr_evidence, "PR") != operation.pr_state_evidence_digest:
            raise RepositoryMaintenanceError("PR evidence substitution denied")
        if evidence_digest(ownership_evidence, "OWNERSHIP") != operation.ownership_evidence_digest:
            raise RepositoryMaintenanceError("ownership evidence substitution denied")
        if observation.classification != operation.classification or operation.classification not in {"A", "B"}:
            raise RepositoryMaintenanceError("branch no longer deletion eligible")
        classification_payload = _classification_payload(
            classification=operation.classification,
            branch=operation.branch_name,
            head=before_head,
            master=before_master,
            ancestry=operation.ancestry_evidence_digest,
            pr=operation.pr_state_evidence_digest,
            ownership=operation.ownership_evidence_digest,
            closure=closure_digest,
        )
        if evidence_digest(classification_payload, "CLASSIFICATION") != operation.classification_digest:
            raise RepositoryMaintenanceError("classification evidence substitution denied")
        self.backend.delete_exact_branch_ref(operation.branch_name, before_head)
        self._deletions += 1
        after_head = self.backend.branch_sha(operation.branch_name)
        after_master = self.backend.master_sha()
        if after_head is not None:
            raise RepositoryMaintenanceError("branch still exists after delete")
        if after_master != before_master:
            raise RepositoryMaintenanceError("master changed during cleanup")
        return self._receipt(operation, before_master=before_master, after_master=after_master, before_head=before_head, exists_after=False, outcome="SUCCEEDED", events=(f"github:ref:heads/{operation.branch_name}:deleted", f"github:master:{after_master}:unchanged"))


def _build_operation(*, sandbox: RepositoryMaintenanceSandbox, branch: str, index: int, master_sha: str) -> tuple[RepositoryMaintenanceOperation, BranchObservation]:
    head, compare, prs, ownership, obs, closure_digest = _observe_delete_classification(
        backend=sandbox.backend, branch=branch, master_sha=master_sha
    )
    if obs.classification not in {"A", "B"}:
        raise RepositoryMaintenanceError("branch requires retention or additional evidence: " + json.dumps(obs.canonical(), sort_keys=True))
    ancestry = {"branch": branch, "head": head, "master": master_sha, "status": compare["status"], "ahead_by": compare["ahead_by"], "behind_by": compare["behind_by"]}
    pr_state = {"branch": branch, "open_pr_ids": sorted(int(item["number"]) for item in prs if isinstance(item.get("number"), int) and not isinstance(item.get("number"), bool))}
    ownership_state = ownership.canonical_dict()
    a_digest = evidence_digest(ancestry, "ANCESTRY")
    p_digest = evidence_digest(pr_state, "PR")
    o_digest = evidence_digest(ownership_state, "OWNERSHIP")
    class_payload = _classification_payload(
        classification=obs.classification,
        branch=branch,
        head=head,
        master=master_sha,
        ancestry=a_digest,
        pr=p_digest,
        ownership=o_digest,
        closure=closure_digest,
    )
    op = RepositoryMaintenanceOperation(schema_version="1.0.0", repository=REPOSITORY, mission_id=sandbox.policy.mission_id, drone_id=f"F48-{index:03d}", operation_id=f"delete-{index:03d}-{sha256(branch.encode()).hexdigest()[:12]}", dispatch_id="E003-BRANCH-ZERO-SANDBOX-01", fencing_token=1, generation=1, protected_master_sha=master_sha, branch_name=branch, expected_branch_head=head, ancestry_evidence_digest=a_digest, pr_state_evidence_digest=p_digest, ownership_evidence_digest=o_digest, classification_digest=evidence_digest(class_payload, "CLASSIFICATION"), classification=obs.classification, requested_effect="DELETE_EXACT_REF", policy_digest=sandbox.policy.digest()).validate()
    return op, obs


def run_cleanup(*, token: str, expected_master: str | None = None) -> dict[str, object]:
    backend = GitHubRepositoryMaintenanceBackend(REPOSITORY, token)
    master = backend.master_sha()
    if expected_master is not None and master != expected_master:
        raise RepositoryMaintenanceError("expected master binding failed")
    policy = RepositoryMaintenancePolicy(schema_version="1.0.0", repository=REPOSITORY, mission_id="E003-BRANCH-ZERO-SANDBOX-AUTONOMIZATION", protected_ref="master", allowed_prefixes=MAINTENANCE_BRANCH_ALLOWLIST, max_deletions=100).validate()
    sandbox = RepositoryMaintenanceSandbox(policy=policy, backend=backend)
    branches = [name for name in backend.list_branches() if name != "master"]
    observations: list[dict[str, object]] = []
    receipts: list[dict[str, object]] = []
    retained: list[dict[str, object]] = []
    for index, branch in enumerate(branches, start=1):
        try:
            validate_branch_name(branch)
        except RepositoryMaintenanceContractError:
            retained.append({"branch": branch, "reason": "OUTSIDE_MAINTENANCE_ALLOWLIST"})
            continue
        try:
            operation, observation = _build_operation(sandbox=sandbox, branch=branch, index=index, master_sha=master)
            observations.append(observation.canonical())
            receipt = sandbox.execute_delete(operation)
            receipts.append(asdict(receipt))
        except (RepositoryMaintenanceError, RepositoryMaintenanceContractError) as exc:
            retained.append({"branch": branch, "reason": str(exc)})
    final_master = backend.master_sha()
    if final_master != master:
        raise RepositoryMaintenanceError("master changed during cleanup mission")
    final_branches = backend.list_branches()
    return {"schema_version": "1.0.0", "mission_id": policy.mission_id, "master_before": master, "master_after": final_master, "initial_non_master_count": len(branches), "deleted_count": len(receipts), "retained_count": len([b for b in final_branches if b != "master"]), "deleted": [r["branch_name"] for r in receipts], "retained": retained, "final_branches": final_branches, "receipts": receipts, "authority_effect": False, "master_effect": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-cleanup", action="store_true")
    parser.add_argument("--expected-master")
    args = parser.parse_args(argv)
    if not args.execute_cleanup:
        parser.error("--execute-cleanup required")
    token = os.environ.get("GITHUB_TOKEN", "")
    try:
        result = run_cleanup(token=token, expected_master=args.expected_master or None)
    except Exception as exc:
        print(f"LION_REPOSITORY_MAINTENANCE_FAILED type={type(exc).__name__} detail={exc}", file=sys.stderr)
        return 1
    print("LION_REPOSITORY_MAINTENANCE_RESULT " + json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())