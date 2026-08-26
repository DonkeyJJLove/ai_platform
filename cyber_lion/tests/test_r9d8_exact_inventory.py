from __future__ import annotations

from hashlib import sha1, sha256
import json
from pathlib import Path
import subprocess
import unittest

from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner

REPOSITORY = "DonkeyJJLove/ai_platform"
BASELINE = "7204b69abe45b028b2bad52b6345711adb832d47"
BASELINE_TREE = "39d1de9966942e93c41eeadad185fd4d60c4bc3b"


def _git(*args: str) -> bytes:
    return subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def _production_path(path: str) -> bool:
    if path.startswith("cyber_lion/") and path.endswith(".py") and "/tests/" not in f"/{path}":
        return True
    return path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return sha1(header + data).hexdigest()


class R9D8ExactInventoryTests(unittest.TestCase):
    def test_exact_current_production_inventory_is_materialized(self):
        raw = _git("ls-files", "-s", "-z")
        entries: list[tuple[str, str, str]] = []
        for record in raw.split(b"\0"):
            if not record:
                continue
            meta, path_raw = record.split(b"\t", 1)
            mode, blob_sha, stage = meta.decode("ascii").split(" ")
            if stage != "0":
                self.fail("unmerged index entry in exact inventory")
            path = path_raw.decode("utf-8")
            if _production_path(path):
                entries.append((path, blob_sha, mode))
        entries.sort()
        self.assertTrue(entries)
        self.assertEqual(len(entries), len({path for path, _, _ in entries}))

        candidate_revision = _git("rev-parse", "HEAD").decode("ascii").strip()
        candidate_tree = _git("write-tree").decode("ascii").strip()
        self.assertRegex(candidate_revision, r"^[0-9a-f]{40}$")
        self.assertRegex(candidate_tree, r"^[0-9a-f]{40}$")

        sources: dict[str, str] = {}
        manifest: list[dict[str, object]] = []
        for path, blob_sha, mode in entries:
            blob = Path(path).read_bytes()
            self.assertEqual(_git_blob_sha(blob), blob_sha, path)
            sources[path] = blob.decode("utf-8")
            manifest.append({
                "path": path,
                "blob_sha": blob_sha,
                "byte_sha256": sha256(blob).hexdigest(),
                "size": len(blob),
                "mode": mode,
            })

        manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        manifest_digest = sha256(b"LION/R9D8/EXACT-PRODUCTION-MANIFEST/1\0" + manifest_bytes).hexdigest()
        inventory = EffectSurfaceScanner().scan(
            repository=REPOSITORY,
            revision=candidate_revision,
            tree_digest=candidate_tree,
            sources=sources,
        )

        print("R9D8_EXACT_INVENTORY " + json.dumps({
            "repository": REPOSITORY,
            "baseline": BASELINE,
            "baseline_tree": BASELINE_TREE,
            "candidate_revision": candidate_revision,
            "candidate_tree": candidate_tree,
            "source_count": len(manifest),
            "manifest_digest": manifest_digest,
            "scan_digest": inventory.scan_digest,
            "inventory_digest": inventory.digest(),
            "surface_count": len(inventory.surfaces),
            "unclassified_count": len(inventory.unclassified_refs),
        }, sort_keys=True, separators=(",", ":")))
        for surface in inventory.surfaces:
            print("R9D8_SURFACE " + json.dumps({
                "surface_id": surface.surface_id,
                "digest": surface.digest(),
                "effect_class": surface.effect_class,
                "authority_class": surface.authority_class,
                "implementation_refs": list(surface.implementation_refs),
                "entrypoints": list(surface.entrypoints),
                "provider": surface.effect_provider,
                "target_class": surface.target_class,
                "mutation_kind": surface.mutation_kind,
            }, sort_keys=True, separators=(",", ":")))
        for ref in inventory.unclassified_refs:
            print("R9D8_UNCLASSIFIED " + ref)

        self.assertEqual(inventory.revision, candidate_revision)
        self.assertEqual(inventory.tree_digest, candidate_tree)
        self.assertTrue(inventory.scan_digest)
        self.assertEqual(len(sources), len(manifest))


if __name__ == "__main__":
    unittest.main()
