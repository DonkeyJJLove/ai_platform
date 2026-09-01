from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cyber_lion.enterprise.merge_authority_consumption import (
    MergeAuthorityConsumptionKey,
    MergeAuthorityConsumptionState,
)
from cyber_lion.enterprise.merge_authority_consumption_store import (
    SQLiteMergeAuthorityConsumptionStore,
)
from cyber_lion.enterprise.merge_authority_control_plane import (
    LABMergeAuthorityControlPlane,
)
from cyber_lion.enterprise.trusted_control_plane_service import (
    TrustedControlPlaneService,
    TrustedControlPlaneStore,
    TrustedSignatureVerifier,
)


BASE = "a" * 40
HEAD = "b" * 40
DIGEST = "c" * 64
LINEAGE = "d" * 64


class Store(TrustedControlPlaneStore):
    def lookup_pr_bootstrap_exact(self, **kwargs):
        return ()

    def lookup_authority_exact(self, **kwargs):
        return ()

    def lookup_builder_subject_exact(self, **kwargs):
        return ()

    def ready(self):
        return True


class Verifier(TrustedSignatureVerifier):
    def verify(self, payload, signature, key_id, algorithm):
        return False

    def ready(self):
        return True


class LabControlPlaneTests(unittest.TestCase):
    def key(self):
        return MergeAuthorityConsumptionKey(
            repository="DonkeyJJLove/ai_platform",
            pr_number=248,
            base_sha=BASE,
            head_sha=HEAD,
            grant_id="grant-1",
            grant_digest=DIGEST,
            lineage_digest=LINEAGE,
            epoch=1,
            merge_method="merge",
        ).validate()

    def test_consumption_store_outside_repo_and_replay(self):
        with TemporaryDirectory() as td:
            root = Path(td) / "repo"
            state = Path(td) / "state"
            root.mkdir()
            state.mkdir()
            store = SQLiteMergeAuthorityConsumptionStore(
                str(state / "authority.db"), repository_root=str(root)
            )
            first = store.observe_consumption_exact(self.key())
            self.assertEqual(first.state, MergeAuthorityConsumptionState.AVAILABLE)
            consumed = store.consume_exact(self.key())
            self.assertEqual(consumed.state, MergeAuthorityConsumptionState.CONSUMED)
            replay = store.consume_exact(self.key())
            self.assertEqual(replay, consumed)
            with self.assertRaises(Exception):
                SQLiteMergeAuthorityConsumptionStore(
                    str(root / "authority.db"), repository_root=str(root)
                )

    def test_runtime_endpoints_are_authenticated_and_exact(self):
        with TemporaryDirectory() as td:
            root = Path(td) / "repo"
            state = Path(td) / "state"
            root.mkdir()
            state.mkdir()
            consumption = SQLiteMergeAuthorityConsumptionStore(
                str(state / "authority.db"), repository_root=str(root)
            )
            base = TrustedControlPlaneService(
                store=Store(), verifier=Verifier(), credential="token"
            )
            service = LABMergeAuthorityControlPlane(
                base=base,
                consumption_store=consumption,
                clock_source_id="lab-debian:system-clock:test",
            )
            denied = service.dispatch(
                method="GET",
                target="/v1/trusted-clock",
                headers={},
                body=b"",
            )
            self.assertEqual(denied.status, 401)
            clock = service.dispatch(
                method="GET",
                target="/v1/trusted-clock",
                headers={"Authorization": "Bearer token"},
                body=b"",
            )
            self.assertEqual(clock.status, 200)
            self.assertEqual(
                set(clock.payload),
                {"provider_version", "observed_at", "trusted_clock_source_id"},
            )
            self.assertTrue(clock.payload["observed_at"].endswith("Z"))
            q = (
                "/v1/merge-authority-consumption?"
                "repository=DonkeyJJLove%2Fai_platform"
                f"&pr_number=248&base_sha={BASE}&head_sha={HEAD}"
                "&grant_id=grant-1"
                f"&grant_digest={DIGEST}&lineage_digest={LINEAGE}"
                "&epoch=1&merge_method=merge"
            )
            response = service.dispatch(
                method="GET",
                target=q,
                headers={"Authorization": "Bearer token"},
                body=b"",
            )
            self.assertEqual(response.status, 200)
            self.assertEqual(response.payload["state"], "AVAILABLE")

    def test_systemd_asset_has_hardening(self):
        text = Path(
            "deploy/systemd/cyber-lion-control-plane.service"
        ).read_text()
        for required in (
            "NoNewPrivileges=true",
            "PrivateTmp=true",
            "ProtectSystem=strict",
            "ProtectHome=true",
            "ReadWritePaths=/var/lib/cyber-lion-control-plane",
        ):
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
