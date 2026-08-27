from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import inspect
import unittest

from cyber_lion.enterprise.moon_file_write_mediation import (
    CanonicalMoonFileWriteMediator,
    MoonFileTargetObservation,
)


TARGET = "/home/d2j3/lion-r9d9b-canary-repair-test.txt"


def _absent(observed_at: str, observer_id: str = "moon-host-file-observer-v1") -> MoonFileTargetObservation:
    return MoonFileTargetObservation(
        target_path=TARGET,
        exists=False,
        regular_file=False,
        symlink=False,
        size=None,
        sha256=None,
        device=None,
        inode=None,
        base_device=11,
        base_inode=22,
        observer_id=observer_id,
        observed_at=observed_at,
    ).sealed()


def _present(observed_at: str, *, digest: str | None = None, inode: int = 44) -> MoonFileTargetObservation:
    return MoonFileTargetObservation(
        target_path=TARGET,
        exists=True,
        regular_file=True,
        symlink=False,
        size=1,
        sha256=digest or sha256(b"A").hexdigest(),
        device=33,
        inode=inode,
        base_device=11,
        base_inode=22,
        observer_id="moon-host-file-observer-v1",
        observed_at=observed_at,
    ).sealed()


class MoonFileWriteCurrentnessTests(unittest.TestCase):
    def test_timestamp_changes_receipt_digest_but_not_state_digest(self):
        first = _absent("2026-08-27T07:13:10+00:00")
        second = _absent("2026-08-27T07:13:11+00:00")
        self.assertNotEqual(first.observation_digest, second.observation_digest)
        self.assertEqual(first.state_digest(), second.state_digest())

    def test_observer_identity_changes_receipt_but_not_target_state(self):
        first = _absent("2026-08-27T07:13:10+00:00", "observer-a")
        second = _absent("2026-08-27T07:13:10+00:00", "observer-b")
        self.assertNotEqual(first.observation_digest, second.observation_digest)
        self.assertEqual(first.state_digest(), second.state_digest())

    def test_existence_change_changes_state_digest(self):
        absent = _absent("2026-08-27T07:13:10+00:00")
        present = _present("2026-08-27T07:13:11+00:00")
        self.assertNotEqual(absent.state_digest(), present.state_digest())

    def test_content_change_changes_state_digest(self):
        first = _present("2026-08-27T07:13:10+00:00", digest=sha256(b"A").hexdigest())
        second = _present("2026-08-27T07:13:11+00:00", digest=sha256(b"B").hexdigest())
        self.assertNotEqual(first.state_digest(), second.state_digest())

    def test_inode_change_changes_state_digest(self):
        first = _present("2026-08-27T07:13:10+00:00", inode=44)
        second = _present("2026-08-27T07:13:11+00:00", inode=45)
        self.assertNotEqual(first.state_digest(), second.state_digest())

    def test_state_payload_excludes_epistemic_metadata(self):
        observation = _absent("2026-08-27T07:13:10+00:00")
        self.assertNotIn("observed_at", observation.state_payload())
        self.assertNotIn("observer_id", observation.state_payload())
        self.assertNotIn("observation_digest", observation.state_payload())

    def test_mediator_currentness_uses_state_digest_not_receipt_digest(self):
        source = inspect.getsource(CanonicalMoonFileWriteMediator.execute)
        self.assertIn("current_pre.state_digest() != pre.state_digest()", source)
        self.assertNotIn("current_pre.observation_digest != pre.observation_digest", source)


if __name__ == "__main__":
    unittest.main()
