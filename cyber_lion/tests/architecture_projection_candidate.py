from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import subprocess
import tempfile


def _git(repo_root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        input=input_bytes,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def staged_tree(repo_root: Path) -> str:
    return _git(repo_root, "write-tree").decode("ascii").strip()


def staged_sources(repo_root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in _git(repo_root, "ls-files", "-z").split(b"\0"):
        if not raw:
            continue
        path = raw.decode("utf-8")
        try:
            data = _git(repo_root, "show", ":" + path)
            out[path] = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
    return out


@contextmanager
def clean_git_repo():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "t03@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "T03 Test"], check=True)
        (root / "sentinel.txt").write_text("canonical\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "sentinel.txt"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "fixture"], check=True)
        tree = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"],
            check=True, stdout=subprocess.PIPE, text=True
        ).stdout.strip()
        yield root, tree
