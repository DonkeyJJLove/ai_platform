from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import unittest

from cyber_lion.contracts.moon_file_write import MoonFileWriteContractError, MoonFileWriteRequest


def _request(**changes):
    values = dict(
        schema_version="1.0.0", request_id="r9d9a-1", repository="DonkeyJJLove/ai_platform",
        control_issue=144, actor_login="DonkeyJJLove", runner_name="lion-moon-r9d8-test",
        target_path="/home/d2j3/lion-r9d9a-canary-unit.txt", operation_mode="CREATE_ONLY",
        expected_previous_state="ABSENT", expected_previous_sha256=None,
        intended_content_sha256=sha256(b"AAAA").hexdigest(), intended_content_size=4,
        source_event_digest=sha256(b"event").hexdigest(),
    )
    values.update(changes)
    return MoonFileWriteRequest(**values).sealed()


class MoonFileWriteContractTests(unittest.TestCase):
    def test_create_only_is_immutable_sealed_and_deterministic(self):
        a=_request(); b=_request()
        self.assertEqual(a.request_digest,b.request_digest)
        with self.assertRaises(Exception):
            a.target_path="/tmp/x"  # type: ignore[misc]

    def test_replace_requires_exact_previous_digest(self):
        previous=sha256(b"OLD").hexdigest()
        value=_request(operation_mode="REPLACE_EXPECTED_DIGEST", expected_previous_state="PRESENT_EXACT", expected_previous_sha256=previous)
        self.assertEqual(value.expected_previous_sha256, previous)
        with self.assertRaises(MoonFileWriteContractError):
            _request(operation_mode="REPLACE_EXPECTED_DIGEST", expected_previous_state="PRESENT_EXACT", expected_previous_sha256=None)

    def test_scope_context_and_size_widening_denied(self):
        cases=(
            {"target_path":"/tmp/x"}, {"target_path":"/home/d2j3/sub/x"},
            {"repository":"other/repo"}, {"control_issue":145}, {"runner_name":"other"},
            {"intended_content_size":4097},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                with self.assertRaises(MoonFileWriteContractError): _request(**changes)

    def test_digest_substitution_denied(self):
        value=_request()
        with self.assertRaises(MoonFileWriteContractError):
            replace(value, intended_content_size=3).validate()

    def test_request_contains_no_authority_or_secret_material(self):
        fields=set(MoonFileWriteRequest.__dataclass_fields__)
        self.assertFalse(fields & {"token","credential","authority_grant","effect_receipt","admission"})


if __name__ == "__main__": unittest.main()
