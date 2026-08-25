"""Closed-world read-only Git process boundary for Code Perception.

R9D-3 removes raw Git argv construction from the code-perception indexer.  Callers may
request only a small typed set of repository-reading operations.  The boundary owns argv
construction, a minimal Git environment, bounded process output, single-use execution
admissions and post-process observation.  It does not grant authority and exposes no
write-capable Git operation.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import re
import subprocess
from threading import Lock


class GitReadBoundaryError(RuntimeError):
    pass


RESOLVE_COMMIT = "RESOLVE_COMMIT"
RESOLVE_TREE = "RESOLVE_TREE"
LIST_TREE = "LIST_TREE"
READ_BLOB = "READ_BLOB"
HASH_STDIN = "HASH_STDIN"
ALLOWED_OPERATIONS = frozenset({RESOLVE_COMMIT, RESOLVE_TREE, LIST_TREE, READ_BLOB, HASH_STDIN})
_HEX40 = re.compile(r"^[0-9a-f]{40}$")


def _hash(data: bytes) -> str:
    return sha256(data).hexdigest()


def _canon(*parts: str) -> bytes:
    return "\0".join(parts).encode("utf-8")


@dataclass(frozen=True)
class ReadOnlyGitCommand:
    operation: str
    repository_root: str
    arguments: tuple[str, ...]
    stdin_digest: str
    expected_output_class: str
    source_commit_sha: str
    source_tree_sha: str
    command_digest: str


@dataclass(frozen=True)
class GitReadAdmission:
    request_digest: str
    repository_root_digest: str
    source_identity_digest: str
    operation: str
    command_digest: str
    runtime_identity_digest: str
    nonce: str
    epoch: int
    admission_digest: str


@dataclass(frozen=True)
class GitReadObservation:
    operation: str
    argv_digest: str
    returncode: int
    stdout_digest: str
    stderr_digest: str
    stdout_size: int
    stderr_size: int
    source_identity_digest: str
    observed: bool


class CodePerceptionGitBoundary:
    """Typed, read-only Git process executor; never accepts caller-supplied raw argv."""

    STDERR_MAX = 65536
    SMALL_STDOUT_MAX = 256
    TREE_STDOUT_MAX = 16 * 1024 * 1024
    BLOB_MARGIN = 16

    def __init__(self, *, timeout_seconds: float = 20.0, epoch: int = 1) -> None:
        if timeout_seconds <= 0 or isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
            raise GitReadBoundaryError("invalid git read boundary configuration")
        self.timeout_seconds = float(timeout_seconds)
        self.epoch = epoch
        self._lock = Lock()
        self._counter = 0
        self._consumed: set[str] = set()

    @staticmethod
    def _root(repo_root: str | Path) -> Path:
        root = Path(repo_root).resolve()
        if not root.exists() or not root.is_dir():
            raise GitReadBoundaryError("repository root unavailable")
        return root

    @staticmethod
    def _minimal_env() -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
        }
        return env

    @staticmethod
    def _source_digest(repository: str, commit: str, tree: str) -> str:
        if not isinstance(repository, str) or not repository.strip():
            raise GitReadBoundaryError("repository identity required")
        return _hash(_canon(repository, commit or "UNKNOWN", tree or "UNKNOWN"))

    def _admission(self, command: ReadOnlyGitCommand, repository: str) -> GitReadAdmission:
        if command.operation not in ALLOWED_OPERATIONS:
            raise GitReadBoundaryError("git operation not allowed")
        with self._lock:
            self._counter += 1
            nonce = f"git-read:{self.epoch}:{self._counter}"
        root_digest = _hash(command.repository_root.encode("utf-8"))
        source_digest = self._source_digest(repository, command.source_commit_sha, command.source_tree_sha)
        request_digest = _hash(_canon(command.operation, command.command_digest, root_digest, source_digest))
        runtime_digest = _hash(b"LION/CODE-PERCEPTION-GIT-RUNTIME/1")
        admission_digest = _hash(_canon(request_digest, root_digest, source_digest, command.operation, command.command_digest, runtime_digest, nonce, str(self.epoch)))
        return GitReadAdmission(request_digest, root_digest, source_digest, command.operation, command.command_digest, runtime_digest, nonce, self.epoch, admission_digest)

    def _consume(self, admission: GitReadAdmission) -> None:
        with self._lock:
            if admission.admission_digest in self._consumed:
                raise GitReadBoundaryError("git read admission replay denied")
            self._consumed.add(admission.admission_digest)

    @staticmethod
    def _command(*, operation: str, root: Path, arguments: tuple[str, ...], stdin: bytes | None, output_class: str, commit: str = "", tree: str = "") -> ReadOnlyGitCommand:
        if operation not in ALLOWED_OPERATIONS:
            raise GitReadBoundaryError("git operation not allowed")
        stdin_digest = _hash(stdin or b"")
        command_digest = _hash(_canon(operation, str(root), *arguments, stdin_digest, output_class, commit or "UNKNOWN", tree or "UNKNOWN"))
        return ReadOnlyGitCommand(operation, str(root), arguments, stdin_digest, output_class, commit, tree, command_digest)

    def _execute(self, command: ReadOnlyGitCommand, *, repository: str, stdin: bytes | None = None, stdout_max: int) -> tuple[bytes, GitReadObservation]:
        root = self._root(command.repository_root)
        if str(root) != command.repository_root:
            raise GitReadBoundaryError("repository root drift")
        if _hash(stdin or b"") != command.stdin_digest:
            raise GitReadBoundaryError("git stdin substitution")
        admission = self._admission(command, repository)
        self._consume(admission)
        argv = ["git", "-C", str(root), *command.arguments]
        argv_digest = _hash(_canon(*argv))
        try:
            proc = subprocess.run(
                argv,
                input=stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._minimal_env(),
                shell=False,
                check=False,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitReadBoundaryError("git read process unavailable or timed out") from exc
        if len(proc.stderr) > self.STDERR_MAX or len(proc.stdout) > stdout_max:
            raise GitReadBoundaryError("git read output exceeded bound")
        observation = GitReadObservation(
            command.operation,
            argv_digest,
            proc.returncode,
            _hash(proc.stdout),
            _hash(proc.stderr),
            len(proc.stdout),
            len(proc.stderr),
            admission.source_identity_digest,
            True,
        )
        if proc.returncode != 0 or not observation.observed:
            detail = proc.stderr.decode("utf-8", errors="replace")[:1000]
            raise GitReadBoundaryError(f"git read operation failed: {detail}")
        return proc.stdout, observation

    @staticmethod
    def _hex_output(raw: bytes, label: str) -> str:
        try:
            value = raw.decode("ascii").strip().lower()
        except UnicodeDecodeError as exc:
            raise GitReadBoundaryError(f"{label} output encoding invalid") from exc
        if _HEX40.fullmatch(value) is None:
            raise GitReadBoundaryError(f"{label} output is not exact 40-hex")
        return value

    def resolve_commit(self, repo_root: str | Path, repository: str, commit_ref: str) -> str:
        root = self._root(repo_root)
        if not isinstance(commit_ref, str) or not commit_ref.strip() or "\x00" in commit_ref or commit_ref.startswith("-"):
            raise GitReadBoundaryError("invalid commit reference")
        args = ("rev-parse", f"{commit_ref}^{{commit}}")
        cmd = self._command(operation=RESOLVE_COMMIT, root=root, arguments=args, stdin=None, output_class="HEX40")
        raw, _ = self._execute(cmd, repository=repository, stdout_max=self.SMALL_STDOUT_MAX)
        return self._hex_output(raw, "commit")

    def resolve_tree(self, repo_root: str | Path, repository: str, commit_sha: str) -> str:
        root = self._root(repo_root)
        if _HEX40.fullmatch(commit_sha) is None:
            raise GitReadBoundaryError("invalid commit sha")
        args = ("rev-parse", f"{commit_sha}^{{tree}}")
        cmd = self._command(operation=RESOLVE_TREE, root=root, arguments=args, stdin=None, output_class="HEX40", commit=commit_sha)
        raw, _ = self._execute(cmd, repository=repository, stdout_max=self.SMALL_STDOUT_MAX)
        return self._hex_output(raw, "tree")

    def list_tree(self, repo_root: str | Path, repository: str, commit_sha: str, tree_sha: str) -> bytes:
        root = self._root(repo_root)
        if _HEX40.fullmatch(commit_sha) is None or _HEX40.fullmatch(tree_sha) is None:
            raise GitReadBoundaryError("invalid source identity")
        args = ("ls-tree", "-r", "-z", "--long", commit_sha)
        cmd = self._command(operation=LIST_TREE, root=root, arguments=args, stdin=None, output_class="TREE_RECORDS", commit=commit_sha, tree=tree_sha)
        raw, _ = self._execute(cmd, repository=repository, stdout_max=self.TREE_STDOUT_MAX)
        return raw

    def read_blob(self, repo_root: str | Path, repository: str, commit_sha: str, tree_sha: str, blob_sha: str, expected_size: int) -> bytes:
        root = self._root(repo_root)
        if _HEX40.fullmatch(commit_sha) is None or _HEX40.fullmatch(tree_sha) is None or _HEX40.fullmatch(blob_sha) is None:
            raise GitReadBoundaryError("invalid blob source identity")
        if isinstance(expected_size, bool) or not isinstance(expected_size, int) or expected_size < 0:
            raise GitReadBoundaryError("invalid blob size")
        args = ("cat-file", "blob", blob_sha)
        cmd = self._command(operation=READ_BLOB, root=root, arguments=args, stdin=None, output_class="BLOB", commit=commit_sha, tree=tree_sha)
        raw, _ = self._execute(cmd, repository=repository, stdout_max=expected_size + self.BLOB_MARGIN)
        if len(raw) != expected_size:
            raise GitReadBoundaryError("blob size mismatch")
        return raw

    def hash_stdin(self, repo_root: str | Path, repository: str, commit_sha: str, tree_sha: str, data: bytes) -> str:
        root = self._root(repo_root)
        if _HEX40.fullmatch(commit_sha) is None or _HEX40.fullmatch(tree_sha) is None or not isinstance(data, bytes):
            raise GitReadBoundaryError("invalid hash-stdin request")
        args = ("hash-object", "--stdin")
        cmd = self._command(operation=HASH_STDIN, root=root, arguments=args, stdin=data, output_class="HEX40", commit=commit_sha, tree=tree_sha)
        raw, _ = self._execute(cmd, repository=repository, stdin=data, stdout_max=self.SMALL_STDOUT_MAX)
        return self._hex_output(raw, "object id")
