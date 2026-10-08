"""Historical P0 effect-surface inventory, pinned to its proven source epoch.

The MOON P0/attested campaigns were certified against an exact source
inventory on master b6cc132 (567 surfaces, scan eeb9ec6f...).  They are
HISTORICAL evidence, not tests of the newest candidate's inventory.

This loader reconstructs the original Git tree from immutable local Git
objects, verifies every selected blob, and fails closed on any missing or
substituted source.  It performs no network request, checkout, fetch, state
mutation or effect.  Current source must be evaluated independently.
"""
from __future__ import annotations

from hashlib import sha1
from pathlib import Path
import subprocess

from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner
from tools.p0_effect_taxonomy import EffectTaxonomyReconciler

HISTORICAL_HEAD = "b6cc132095deb268b2754d2afc0634aeac5a7ac4"
HISTORICAL_TREE = "7f6a2bbb2efa6551340b24873ea3e21f5205ee95"
HISTORICAL_SCAN_DIGEST = "eeb9ec6f043c9e454999aee2f02c3ee42d65878eee0a5d8015e752e887f11173"
REPOSITORY = "DonkeyJJLove/ai_platform"


class HistoricalP0SourceError(RuntimeError):
    pass


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, timeout=30,
    )
    if result.returncode:
        raise HistoricalP0SourceError("pinned historical Git object unavailable")
    return result.stdout


def _production_path(path: str) -> bool:
    return (
        path.startswith("cyber_lion/")
        and path.endswith(".py")
        and "/tests/" not in "/" + path
    ) or (
        path.startswith(".github/workflows/")
        and path.endswith((".yml", ".yaml"))
    )


def pinned_p0_inventory(root: Path | None = None):
    """Return (inventory, taxonomy) for the exact certified P0 source epoch.

    Caller-provided root is only the repository object store path. It never
    supplies current working-tree source bytes or changes the historical pin.
    """
    if root is None:
        root = Path(__file__).resolve().parents[2]
    root = Path(root).resolve(strict=True)
    if _git(root, "cat-file", "-t", HISTORICAL_HEAD).strip() != b"commit":
        raise HistoricalP0SourceError("pinned P0 commit type mismatch")
    observed_tree = _git(root, "rev-parse", f"{HISTORICAL_HEAD}^{{tree}}").decode("ascii").strip()
    if observed_tree != HISTORICAL_TREE:
        raise HistoricalP0SourceError("pinned P0 source tree substitution")

    sources: dict[str, str] = {}
    for entry in _git(root, "ls-tree", "-r", "-z", HISTORICAL_HEAD).split(b"\x00"):
        if not entry:
            continue
        try:
            descriptor, raw_path = entry.split(b"\t", 1)
            mode, object_type, object_sha = descriptor.decode("ascii").split()
            path = raw_path.decode("utf-8", "strict")
        except (ValueError, UnicodeError) as exc:
            raise HistoricalP0SourceError("pinned P0 tree entry invalid") from exc
        if not _production_path(path):
            continue
        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise HistoricalP0SourceError("pinned P0 production object type invalid")
        raw = _git(root, "cat-file", "blob", object_sha)
        computed = sha1(b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw).hexdigest()
        if computed != object_sha:
            raise HistoricalP0SourceError("pinned P0 Git blob digest mismatch")
        try:
            sources[path] = raw.decode("utf-8", "strict")
        except UnicodeError as exc:
            raise HistoricalP0SourceError("pinned P0 production source encoding invalid") from exc

    raw_inventory = EffectSurfaceScanner().scan(
        repository=REPOSITORY,
        revision=HISTORICAL_HEAD,
        tree_digest=HISTORICAL_TREE,
        sources=sources,
    )
    inventory, taxonomy, _ = EffectTaxonomyReconciler().reconcile(
        raw_inventory=raw_inventory, sources=sources,
    )
    if (
        inventory.scan_digest != HISTORICAL_SCAN_DIGEST
        or len(inventory.surfaces) != 567
        or inventory.unclassified_refs
        or taxonomy.unresolved_refs
    ):
        raise HistoricalP0SourceError("pinned P0 inventory currentness drift")
    return inventory, taxonomy


def pinned_p0_checkout(root: Path):
    """Return a disposable, exact historical checkout context for HEAD-bound tests.

    Uses only local Git objects; never changes refs or worktrees in the parent
    repository and performs no fetch/network/runtime action.
    """
    from contextlib import contextmanager
    import tempfile

    @contextmanager
    def _checkout():
        source = Path(root).resolve(strict=True)
        with tempfile.TemporaryDirectory(prefix="lion-p0-historical-") as temp:
            target = Path(temp) / "pinned"
            cmd = subprocess.run(
                ["git", "clone", "--shared", "--no-checkout", "--quiet",
                 str(source), str(target)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                check=False, timeout=45,
            )
            if cmd.returncode:
                raise HistoricalP0SourceError("isolated historical P0 clone failed")
            _git(target, "checkout", "--detach", "--quiet", HISTORICAL_HEAD)
            if _git(target, "rev-parse", "HEAD").decode("ascii").strip() != HISTORICAL_HEAD:
                raise HistoricalP0SourceError("isolated historical P0 checkout head drift")
            if _git(target, "rev-parse", "HEAD^{tree}").decode("ascii").strip() != HISTORICAL_TREE:
                raise HistoricalP0SourceError("isolated historical P0 checkout tree drift")
            yield target

    return _checkout()
