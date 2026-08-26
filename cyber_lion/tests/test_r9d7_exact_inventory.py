from __future__ import annotations

from hashlib import sha256
import json
import subprocess
import unittest

from cyber_lion.enterprise.complete_mediation import EffectSurfaceScanner

REPOSITORY = "DonkeyJJLove/ai_platform"
BASELINE = "aa7c6367457ff329f712618a26ab377ba6305e1a"
BASELINE_TREE = "690da17d0ff9abbd2bf69c8df8bc2782ab4bf0cc"


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


class R9D7ExactInventoryTests(unittest.TestCase):
    def test_exact_baseline_tree_inventory_is_materialized(self):
        raw = _git("ls-tree", "-r", "-z", BASELINE_TREE)
        entries = []
        for record in raw.split(b"\0"):
            if not record:
                continue
            meta, path_raw = record.split(b"\t", 1)
            mode, obj_type, blob_sha = meta.decode("ascii").split(" ")
            path = path_raw.decode("utf-8")
            if obj_type == "blob" and _production_path(path):
                entries.append((path, blob_sha, mode))
        self.assertTrue(entries)
        self.assertEqual(entries, sorted(entries))

        sources: dict[str, str] = {}
        manifest = []
        for path, blob_sha, mode in entries:
            blob = _git("cat-file", "blob", blob_sha)
            text = blob.decode("utf-8")
            sources[path] = text
            manifest.append(
                {
                    "path": path,
                    "blob_sha": blob_sha,
                    "byte_sha256": sha256(blob).hexdigest(),
                    "size": len(blob),
                    "mode": mode,
                }
            )

        manifest_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        manifest_digest = sha256(b"LION/R9D7/EXACT-PRODUCTION-MANIFEST/1\0" + manifest_bytes).hexdigest()
        inventory = EffectSurfaceScanner().scan(
            repository=REPOSITORY,
            revision=BASELINE,
            tree_digest=BASELINE_TREE,
            sources=sources,
        )

        print(
            "R9D7_EXACT_INVENTORY "
            + json.dumps(
                {
                    "repository": REPOSITORY,
                    "revision": BASELINE,
                    "tree": BASELINE_TREE,
                    "source_count": len(manifest),
                    "manifest_digest": manifest_digest,
                    "scan_digest": inventory.scan_digest,
                    "inventory_digest": inventory.digest(),
                    "surface_count": len(inventory.surfaces),
                    "unclassified_count": len(inventory.unclassified_refs),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        for item in manifest:
            print("R9D7_SOURCE " + json.dumps(item, sort_keys=True, separators=(",", ":")))
        for surface in inventory.surfaces:
            print(
                "R9D7_SURFACE "
                + json.dumps(
                    {
                        "surface_id": surface.surface_id,
                        "digest": surface.digest(),
                        "effect_class": surface.effect_class,
                        "authority_class": surface.authority_class,
                        "implementation_refs": list(surface.implementation_refs),
                        "entrypoints": list(surface.entrypoints),
                        "provider": surface.effect_provider,
                        "target_class": surface.target_class,
                        "mutation_kind": surface.mutation_kind,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        for ref in inventory.unclassified_refs:
            print("R9D7_UNCLASSIFIED " + ref)

        self.assertEqual(inventory.revision, BASELINE)
        self.assertEqual(inventory.tree_digest, BASELINE_TREE)
        self.assertTrue(inventory.scan_digest)
        self.assertEqual(len(sources), len(manifest))


if __name__ == "__main__":
    unittest.main()
