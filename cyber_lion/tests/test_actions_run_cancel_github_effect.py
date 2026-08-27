import hashlib
import inspect
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.contracts.actions_run_cancel import ActionsRunCancelRequest
from cyber_lion.enterprise.actions_run_cancel_github_effect import (
    ExactActionsRunCancelEffectProvider,
)
from cyber_lion.enterprise.actions_run_cancel_mediation import (
    ActionsRunCancelFenceRecord,
    ActionsRunCancelMediationError,
    CanonicalActionsRunCancelAdmission,
    DurableActionsRunCancelFence,
    actions_run_cancel_effect_key,
)
import cyber_lion.enterprise.actions_run_cancel_runtime as runtime


class _Response:
    status = 202

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b""


class _RecordingOpener:
    def __init__(self, fence_path: str):
        self.fence_path = fence_path
        self.calls = []

    def open(self, request, timeout=20):
        with sqlite3.connect(self.fence_path) as connection:
            rows = connection.execute(
                "SELECT state FROM actions_run_cancel_effect"
            ).fetchall()
        if rows != [("ATTEMPTED",)]:
            raise AssertionError(f"raw POST reached before exact ATTEMPTED fence: {rows!r}")
        self.calls.append((request.get_method(), request.full_url, timeout))
        return _Response()


class ActionsRunCancelGithubEffectTests(unittest.TestCase):
    def _request(self):
        return ActionsRunCancelRequest(
            "DonkeyJJLove/ai_platform",
            123,
            "LION Actions Dispatch Bridge",
            "issue_comment",
            "a" * 40,
            "QUEUE_RECOVERY_ONLY",
            "r9d-9g3a1-runtime",
        ).validate()

    @staticmethod
    def _external_module(
        root: Path,
        *,
        authority_drift_call: int = 0,
        currentness_drift_call: int = 0,
        observation_mismatch: bool = False,
    ) -> tuple[Path, str]:
        path = root / "runtime_provider.py"
        source = f"""
from cyber_lion.enterprise.actions_run_cancel_runtime import ActionsRunCancelRuntimeDependencies
from cyber_lion.enterprise.actions_run_cancel_mediation import CanonicalActionsRunCancelAdmission

AUTHORITY_DRIFT_CALL = {authority_drift_call}
CURRENTNESS_DRIFT_CALL = {currentness_drift_call}
OBSERVATION_MISMATCH = {observation_mismatch!r}

class _Admissions:
    def __init__(self):
        self.calls = 0

    def resolve(self, request):
        self.calls += 1
        pdp = "3" * 64 if AUTHORITY_DRIFT_CALL and self.calls >= AUTHORITY_DRIFT_CALL else "2" * 64
        return CanonicalActionsRunCancelAdmission(
            request_digest=request.payload_digest(),
            repository=request.repository,
            run_id=request.run_id,
            expected_workflow=request.expected_workflow,
            expected_event=request.expected_event,
            expected_head_sha=request.expected_head_sha,
            authority_lineage_digest="1" * 64,
            pdp_decision_digest=pdp,
            provider_id="EXTERNAL_PINNED_TEST",
            authority_epoch=7,
        ).sealed()

class _Repository:
    def __init__(self):
        self.calls = 0

    def get_run(self, run_id):
        self.calls += 1
        head = "b" * 40 if CURRENTNESS_DRIFT_CALL and self.calls >= CURRENTNESS_DRIFT_CALL else "a" * 40
        if self.calls >= 4:
            return {{
                "id": 123,
                "name": "LION Actions Dispatch Bridge",
                "event": "issue_comment",
                "head_sha": head,
                "status": "completed",
                "conclusion": "failure" if OBSERVATION_MISMATCH else "cancelled",
            }}
        return {{
            "id": 123,
            "name": "LION Actions Dispatch Bridge",
            "event": "issue_comment",
            "head_sha": head,
            "status": "queued",
            "conclusion": None,
        }}

def build_actions_run_cancel_dependencies():
    return ActionsRunCancelRuntimeDependencies(_Admissions(), _Repository())
""".lstrip()
        path.write_text(source, encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return path, digest

    @staticmethod
    def _environment(provider_path: Path, provider_digest: str, fence_path: Path):
        return {
            "LION_ACTIONS_RUN_CANCEL_RUNTIME_MODULE_PATH": str(provider_path),
            "LION_ACTIONS_RUN_CANCEL_RUNTIME_MODULE_DIGEST": provider_digest,
            "LION_ACTIONS_RUN_CANCEL_FENCE_DATABASE_PATH": str(fence_path),
            "GITHUB_TOKEN": "TEST_ONLY_NON_NETWORK_TOKEN",
            "GITHUB_WORKSPACE": "/definitely/not/the/provider/root",
        }

    def test_caller_created_attempted_fence_and_token_cannot_build_raw_provider(self):
        request = self._request()
        admission = CanonicalActionsRunCancelAdmission(
            request_digest=request.payload_digest(),
            repository=request.repository,
            run_id=request.run_id,
            expected_workflow=request.expected_workflow,
            expected_event=request.expected_event,
            expected_head_sha=request.expected_head_sha,
            authority_lineage_digest="1" * 64,
            pdp_decision_digest="2" * 64,
            provider_id="CALLER_SELECTED",
            authority_epoch=99,
        ).sealed()
        with tempfile.TemporaryDirectory() as td:
            fence = DurableActionsRunCancelFence(str(Path(td) / "caller-fence.sqlite"))
            key = actions_run_cancel_effect_key(request, admission)
            fence.prepare(
                ActionsRunCancelFenceRecord(
                    key,
                    admission.admission_digest,
                    request.payload_digest(),
                    request.repository,
                    request.run_id,
                    "PREPARED",
                    "2026-08-27T00:00:00+00:00",
                )
            )
            fence.mark_attempted(key, "2026-08-27T00:00:01+00:00")
            with self.assertRaisesRegex(
                ActionsRunCancelMediationError,
                "direct actions-run-cancel effect provider disabled",
            ):
                ExactActionsRunCancelEffectProvider(
                    repository="DonkeyJJLove/ai_platform",
                    token="caller-selected",
                    fence=fence,
                )

    def test_constructor_bypass_still_cannot_use_self_sealed_admission(self):
        request = self._request()
        admission = CanonicalActionsRunCancelAdmission(
            request_digest=request.payload_digest(),
            repository=request.repository,
            run_id=request.run_id,
            expected_workflow=request.expected_workflow,
            expected_event=request.expected_event,
            expected_head_sha=request.expected_head_sha,
            authority_lineage_digest="1" * 64,
            pdp_decision_digest="2" * 64,
            provider_id="CALLER_SELECTED",
            authority_epoch=99,
        ).sealed()
        provider = object.__new__(ExactActionsRunCancelEffectProvider)
        with self.assertRaisesRegex(
            ActionsRunCancelMediationError, "direct actions-run-cancel effect provider disabled"
        ):
            provider.cancel_exact(request, admission)

    def test_public_runtime_surface_accepts_request_only(self):
        parameters = list(inspect.signature(runtime.execute_actions_run_cancel).parameters)
        self.assertEqual(parameters, ["request"])
        self.assertNotIn("token", parameters)
        self.assertNotIn("fence", parameters)
        self.assertNotIn("effect", parameters)
        self.assertNotIn("admission", parameters)
        self.assertNotIn("repository", parameters)

    def test_canonical_runtime_reconciles_once_and_replay_has_no_second_post(self):
        request = self._request()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            provider_path, digest = self._external_module(root)
            fence_path = root / "cancel-fence.sqlite"
            opener = _RecordingOpener(str(fence_path))
            with patch.dict(
                os.environ,
                self._environment(provider_path, digest, fence_path),
                clear=False,
            ), patch.object(runtime.urllib.request, "build_opener", return_value=opener):
                result = runtime.execute_actions_run_cancel(request)
                self.assertEqual(result["state"], "RECONCILED")
                self.assertEqual(len(opener.calls), 1)
                self.assertEqual(opener.calls[0][0], "POST")
                self.assertTrue(opener.calls[0][1].endswith("/actions/runs/123/cancel"))
                with sqlite3.connect(fence_path) as connection:
                    self.assertEqual(
                        connection.execute(
                            "SELECT state FROM actions_run_cancel_effect"
                        ).fetchone()[0],
                        "RECONCILED",
                    )
                with self.assertRaises(ActionsRunCancelMediationError):
                    runtime.execute_actions_run_cancel(request)
                self.assertEqual(len(opener.calls), 1)

    def test_authority_drift_at_effect_boundary_denies_before_post(self):
        request = self._request()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            provider_path, digest = self._external_module(
                root, authority_drift_call=3
            )
            fence_path = root / "cancel-fence.sqlite"
            opener = _RecordingOpener(str(fence_path))
            with patch.dict(
                os.environ,
                self._environment(provider_path, digest, fence_path),
                clear=False,
            ), patch.object(runtime.urllib.request, "build_opener", return_value=opener):
                with self.assertRaisesRegex(
                    ActionsRunCancelMediationError, "authority drift at effect boundary"
                ):
                    runtime.execute_actions_run_cancel(request)
                self.assertEqual(opener.calls, [])
                with sqlite3.connect(fence_path) as connection:
                    self.assertEqual(
                        connection.execute(
                            "SELECT state FROM actions_run_cancel_effect"
                        ).fetchone()[0],
                        "UNKNOWN",
                    )

    def test_currentness_drift_at_effect_boundary_denies_before_post(self):
        request = self._request()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            provider_path, digest = self._external_module(
                root, currentness_drift_call=3
            )
            fence_path = root / "cancel-fence.sqlite"
            opener = _RecordingOpener(str(fence_path))
            with patch.dict(
                os.environ,
                self._environment(provider_path, digest, fence_path),
                clear=False,
            ), patch.object(runtime.urllib.request, "build_opener", return_value=opener):
                with self.assertRaisesRegex(
                    ActionsRunCancelMediationError, "run currentness mismatch"
                ):
                    runtime.execute_actions_run_cancel(request)
                self.assertEqual(opener.calls, [])
                with sqlite3.connect(fence_path) as connection:
                    self.assertEqual(
                        connection.execute(
                            "SELECT state FROM actions_run_cancel_effect"
                        ).fetchone()[0],
                        "UNKNOWN",
                    )

    def test_observation_mismatch_fails_closed_after_one_local_post(self):
        request = self._request()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            provider_path, digest = self._external_module(
                root, observation_mismatch=True
            )
            fence_path = root / "cancel-fence.sqlite"
            opener = _RecordingOpener(str(fence_path))
            with patch.dict(
                os.environ,
                self._environment(provider_path, digest, fence_path),
                clear=False,
            ), patch.object(runtime.urllib.request, "build_opener", return_value=opener):
                with self.assertRaisesRegex(
                    ActionsRunCancelMediationError,
                    "independent cancellation observation missing",
                ):
                    runtime.execute_actions_run_cancel(request)
                self.assertEqual(len(opener.calls), 1)
                with sqlite3.connect(fence_path) as connection:
                    self.assertEqual(
                        connection.execute(
                            "SELECT state FROM actions_run_cancel_effect"
                        ).fetchone()[0],
                        "UNKNOWN",
                    )

    def test_runtime_digest_and_fence_are_fail_closed(self):
        request = self._request()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            provider_path, digest = self._external_module(root)
            fence_path = root / "cancel-fence.sqlite"
            env = self._environment(provider_path, "0" * 64, fence_path)
            with patch.dict(os.environ, env, clear=False):
                with self.assertRaisesRegex(
                    ActionsRunCancelMediationError, "runtime digest mismatch"
                ):
                    runtime.execute_actions_run_cancel(request)

            env = self._environment(provider_path, digest, fence_path)
            env["LION_ACTIONS_RUN_CANCEL_FENCE_DATABASE_PATH"] = "relative.sqlite"
            with patch.dict(os.environ, env, clear=False):
                with self.assertRaisesRegex(
                    ActionsRunCancelMediationError, "fence database unavailable"
                ):
                    runtime.execute_actions_run_cancel(request)


if __name__ == "__main__":
    unittest.main()
