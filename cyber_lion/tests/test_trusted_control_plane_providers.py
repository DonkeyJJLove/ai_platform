from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cyber_lion.enterprise.trusted_control_plane_providers import (
    SQLiteTrustedControlPlaneStore,
    TrustedControlPlaneProviderError,
    TrustedSignatureVerifierAdapter,
)


REPO = "DonkeyJJLove/ai_platform"
BASE = "1" * 40
HEAD = "2" * 40


class TrustedControlPlaneProviderTests(unittest.TestCase):
    def test_exact_records_survive_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "control-plane.sqlite3")
            store = SQLiteTrustedControlPlaneStore(path)
            self.assertTrue(store.ready())
            bootstrap = {
                "lookup_key": {
                    "repository": REPO,
                    "pr_number": 41,
                    "base_sha": BASE,
                    "head_sha": HEAD,
                    "merge_method": "merge",
                },
                "payload": "bootstrap",
            }
            authority = {
                "lookup_key": {
                    "repository": REPO,
                    "pr_number": 41,
                    "base_sha": BASE,
                    "head_sha": HEAD,
                    "mission_id": "mission-n2",
                    "grant_id": "grant-n2",
                },
                "lineage": [],
            }
            store.put_pr_bootstrap(bootstrap)
            store.put_authority_record(authority)

            restarted = SQLiteTrustedControlPlaneStore(path)
            self.assertEqual(
                restarted.lookup_pr_bootstrap_exact(
                    repository=REPO,
                    pr_number=41,
                    base_sha=BASE,
                    head_sha=HEAD,
                    merge_method="merge",
                ),
                (bootstrap,),
            )
            self.assertEqual(
                restarted.lookup_authority_exact(
                    repository=REPO,
                    pr_number=41,
                    base_sha=BASE,
                    head_sha=HEAD,
                    mission_id="mission-n2",
                    grant_id="grant-n2",
                ),
                (authority,),
            )

    def test_wrong_exact_key_returns_zero_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteTrustedControlPlaneStore(str(Path(directory) / "cp.db"))
            self.assertEqual(
                store.lookup_authority_exact(
                    repository=REPO,
                    pr_number=41,
                    base_sha=BASE,
                    head_sha=HEAD,
                    mission_id="missing",
                    grant_id="missing",
                ),
                (),
            )

    def test_duplicate_distinct_records_remain_ambiguous_for_caller(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteTrustedControlPlaneStore(str(Path(directory) / "cp.db"))
            lookup = {
                "repository": REPO,
                "pr_number": 41,
                "base_sha": BASE,
                "head_sha": HEAD,
                "mission_id": "mission-n2",
                "grant_id": "grant-n2",
            }
            store.put_authority_record({"lookup_key": lookup, "value": "a"})
            store.put_authority_record({"lookup_key": lookup, "value": "b"})
            records = store.lookup_authority_exact(**lookup)
            self.assertEqual(len(records), 2)

    def test_signature_adapter_is_runtime_bound_and_fail_closed(self) -> None:
        seen = []

        def verifier(payload, signature, key_id, algorithm):
            seen.append((payload, signature, key_id, algorithm))
            return signature == "ok"

        adapter = TrustedSignatureVerifierAdapter(verifier, ready=lambda: True)
        self.assertTrue(adapter.ready())
        self.assertTrue(adapter.verify(b"payload", "ok", "key-1", "ed25519"))
        self.assertFalse(adapter.verify(b"payload", "bad", "key-1", "ed25519"))
        self.assertEqual(len(seen), 2)

        broken = TrustedSignatureVerifierAdapter(lambda *_: (_ for _ in ()).throw(RuntimeError("down")))
        with self.assertRaises(TrustedControlPlaneProviderError):
            broken.verify(b"payload", "sig", "key", "alg")

    def test_readiness_callback_fails_closed(self) -> None:
        adapter = TrustedSignatureVerifierAdapter(lambda *_: True, ready=lambda: False)
        self.assertFalse(adapter.ready())
        broken = TrustedSignatureVerifierAdapter(
            lambda *_: True,
            ready=lambda: (_ for _ in ()).throw(RuntimeError("down")),
        )
        self.assertFalse(broken.ready())


if __name__ == "__main__":
    unittest.main()
