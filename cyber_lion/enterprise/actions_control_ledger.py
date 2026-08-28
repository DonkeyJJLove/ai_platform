"""Closed-world GitHub issue-comment boundary for the LION Actions control ledger.

This module mediates exactly the issue-comment write class used by the Actions dispatch
bridge.  It cannot dispatch workflows, mutate refs, select another repository, or write
outside control issue 144.  Every accepted write is read back through a distinct
observer before the caller can treat it as successful.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from cyber_lion.contracts.issue_comment_write import IssueCommentWriteRequest, body_digest

CONTROL_ISSUE = 144
_ALLOWED_CREATE_PREFIXES = (
    "LION-DISPATCH-CLAIM v1",
    "LION-RUN-OBSERVATION-RECEIPT v1",
    "LION-GROUP-CHANNEL-OBSERVATION-RECEIPT v1",
    "LION-CODE-PERCEPTION-OBSERVATION-RECEIPT v1",
)
_ALLOWED_UPDATE_PREFIXES = (
    "LION-DISPATCH-CLAIM v1",
    "LION-DISPATCH-RECEIPT v1",
)
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_BODY_BYTES = 64 * 1024
_MAX_RESPONSE_BYTES = 1024 * 1024


class ActionsControlLedgerError(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fields(body: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in body.splitlines()[1:]:
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        # Terminal CLAIM state intentionally appends a second state field.  No other
        # control identity may be duplicated.
        if key in result and key != "state":
            raise ActionsControlLedgerError("duplicate control-ledger identity field")
        result[key] = value
    return result


def _body_digest(body: str) -> str:
    encoded = body.encode("utf-8")
    if not encoded or len(encoded) > _MAX_BODY_BYTES or "\x00" in body:
        raise ActionsControlLedgerError("control-ledger body is invalid or oversized")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ControlLedgerObservation:
    comment_id: int
    body_digest: str
    observed: bool


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class ActionsControlLedgerObserver:
    """Read-only observer for one exact GitHub issue comment."""

    def __init__(self, repository: str, token: str) -> None:
        if not _REPOSITORY_RE.fullmatch(repository):
            raise ActionsControlLedgerError("repository identity invalid")
        if not isinstance(token, str) or not token:
            raise ActionsControlLedgerError("GitHub token unavailable")
        self.repository = repository
        self._token = token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "lion-actions-control-ledger-observer/1",
        }

    def _get_json(self, path: str) -> object:
        if not path.startswith(f"/repos/{self.repository}/issues/") or ".." in path or "\\" in path:
            raise ActionsControlLedgerError("observer route outside control ledger")
        req = urllib.request.Request("https://api.github.com" + path, method="GET", headers=self._headers())
        try:
            with urllib.request.build_opener(_NoRedirect()).open(req, timeout=20) as response:
                if response.status != 200:
                    raise ActionsControlLedgerError("control-ledger observation failed")
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except urllib.error.URLError as exc:
            raise ActionsControlLedgerError("control-ledger observation failed") from exc
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise ActionsControlLedgerError("control-ledger observation oversized")
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ActionsControlLedgerError("control-ledger observation malformed") from exc

    def comment(self, comment_id: int, expected_body: str) -> ControlLedgerObservation:
        if not isinstance(comment_id, int) or isinstance(comment_id, bool) or comment_id <= 0:
            raise ActionsControlLedgerError("comment identity invalid")
        expected = _body_digest(expected_body)
        value = self._get_json(f"/repos/{self.repository}/issues/comments/{comment_id}")
        if not isinstance(value, dict) or value.get("id") != comment_id or not isinstance(value.get("body"), str):
            raise ActionsControlLedgerError("created comment observation malformed")
        observed_body = value["body"]
        observed_digest = _body_digest(observed_body)
        return ControlLedgerObservation(comment_id, observed_digest, observed_body == expected_body and observed_digest == expected)

    def comments(self) -> list[dict]:
        result: list[dict] = []
        for page in range(1, 101):
            value = self._get_json(
                f"/repos/{self.repository}/issues/{CONTROL_ISSUE}/comments?per_page=100&page={page}"
            )
            if not isinstance(value, list):
                raise ActionsControlLedgerError("control-ledger list malformed")
            batch = [item for item in value if isinstance(item, dict)]
            result.extend(batch)
            if len(value) < 100:
                return result
        raise ActionsControlLedgerError("control-ledger pagination limit exceeded")


class ActionsControlLedgerBoundary:
    """Semantic control-ledger boundary; all writes require canonical mediation."""
    _process_lock = threading.RLock()

    def __init__(self, repository: str, token: str, *, observer: ActionsControlLedgerObserver | None = None,
                 mediator=None, expected_repository_head: str = "", authority_context: str = "") -> None:
        if not _REPOSITORY_RE.fullmatch(repository): raise ActionsControlLedgerError("repository identity invalid")
        if not isinstance(token, str) or not token: raise ActionsControlLedgerError("GitHub token unavailable")
        self.repository=repository; self._token=token
        self._observer=observer or ActionsControlLedgerObserver(repository,token)
        if type(self._observer) is not ActionsControlLedgerObserver: raise ActionsControlLedgerError("exact independent observer component required")
        self._mediator=mediator; self._head=expected_repository_head; self._authority_context=authority_context
        self._created_ids:set[int]=set()

    @staticmethod
    def _validate_create_body(body: str) -> tuple[str | None, str | None]:
        if not isinstance(body,str) or not body.startswith(_ALLOWED_CREATE_PREFIXES): raise ActionsControlLedgerError("control-ledger create body not allowlisted")
        _body_digest(body); fields=_fields(body); request_id=fields.get("request_id"); replay_key=fields.get("replay_key")
        if request_id is not None and _REQUEST_ID_RE.fullmatch(request_id) is None: raise ActionsControlLedgerError("request id invalid")
        if replay_key is not None and _HEX64_RE.fullmatch(replay_key) is None: raise ActionsControlLedgerError("replay key invalid")
        return request_id,replay_key

    @staticmethod
    def _validate_update_body(body: str) -> None:
        if not isinstance(body,str) or not body.startswith(_ALLOWED_UPDATE_PREFIXES): raise ActionsControlLedgerError("control-ledger update body not allowlisted")
        _body_digest(body)

    def _require_mediator(self):
        if not callable(getattr(self._mediator,"execute",None)) or _HEX64_RE.fullmatch(sha256(self._head.encode()).hexdigest()) is None or not re.fullmatch(r"^[0-9a-f]{40}$",self._head):
            raise ActionsControlLedgerError("canonical issue-comment mediator/current head unavailable")
        if not self._authority_context: raise ActionsControlLedgerError("issue-comment authority context unavailable")

    def create(self, issue_number: int, body: str) -> int:
        if issue_number!=CONTROL_ISSUE: raise ActionsControlLedgerError("control issue substitution denied")
        request_id,replay_key=self._validate_create_body(body)
        with self._process_lock:
            if request_id is not None or replay_key is not None:
                for item in self._observer.comments():
                    existing=item.get("body")
                    if not isinstance(existing,str): continue
                    fields=_fields(existing)
                    if request_id is not None and fields.get("request_id")==request_id: raise ActionsControlLedgerError("request-id replay denied")
                    if replay_key is not None and fields.get("replay_key")==replay_key: raise ActionsControlLedgerError("replay-key replay denied")
            self._require_mediator()
            rid=request_id or f"ledger:{_body_digest(body)[:32]}"; replay=replay_key or sha256(("ledger:"+_body_digest(body)).encode()).hexdigest()
            req=IssueCommentWriteRequest(self.repository,CONTROL_ISSUE,"CREATE_COMMENT","actions.control-ledger.create",body,rid,replay,self._head,authority_context=self._authority_context).sealed()
            out=self._mediator.execute(req)
            cid=out.get("comment_id") if isinstance(out,dict) else None
            if not isinstance(cid,int) or cid<=0 or out.get("fence_state")!="RECONCILED": raise ActionsControlLedgerError("canonical control-ledger create did not reconcile")
            self._created_ids.add(cid); return cid

    def update(self, comment_id: int, body: str) -> None:
        self._validate_update_body(body)
        if comment_id not in self._created_ids: raise ActionsControlLedgerError("update target was not created by this boundary instance")
        with self._process_lock:
            self._require_mediator()
            old=self._observer._get_json(f"/repos/{self.repository}/issues/comments/{comment_id}")
            old_body=old.get("body") if isinstance(old,dict) else None
            if not isinstance(old_body,str): raise ActionsControlLedgerError("update target observation unavailable")
            bd=_body_digest(body); rid=f"ledger-update:{comment_id}:{bd[:24]}"; replay=sha256((rid+":"+_body_digest(old_body)).encode()).hexdigest()
            req=IssueCommentWriteRequest(self.repository,CONTROL_ISSUE,"UPDATE_OWN_CREATED_COMMENT","actions.control-ledger.update",body,rid,replay,self._head,comment_id,_body_digest(old_body),self._authority_context).sealed()
            out=self._mediator.execute(req)
            if not isinstance(out,dict) or out.get("comment_id")!=comment_id or out.get("fence_state")!="RECONCILED": raise ActionsControlLedgerError("canonical control-ledger update did not reconcile")

