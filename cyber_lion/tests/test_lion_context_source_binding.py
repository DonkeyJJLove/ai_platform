"""Source-byte binding tests, not live authorization or model evaluations."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.app_coordination.lion_context_provider import (
    FED, INV, SOURCES, build_lion_context,
)


class ContextSourceBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.auth = {"invariants": [
            "LPCL_GENERATION_NE_AUTHORITY",
            "USER_EXPLICIT_LAUNCH_OR_RUN_OF_EXACT_LPCL_IS_EXTERNAL_ACTIVATION_EVENT",
            "SUCCESSOR_IDENTITY_OUTSIDE_BOUND_SCOPE_REQUIRES_NEW_LPCL_AND_NEW_USER_LAUNCH",
        ]}
        for rel in SOURCES:
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"x")
        self.auth_path = self.root / SOURCES[1]
        self.bootstrap_path = self.root / SOURCES[-1]
        self.write_json(self.auth_path, self.auth)
        self.write_json(self.bootstrap_path, {"preferred_release": "r9"})

    @staticmethod
    def write_json(path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def test_valid_input_preserves_existing_digest(self):
        # Exact baseline blob 798656e4a6010bf3aa4136358faf612a1d80e149.
        context = build_lion_context(self.root)
        self.assertEqual(context.digest,
                         "d736388e23c3bc0d61c2cebad29136674f89fbd3bc60a3207afd65013ce82346")
        self.assertEqual(context.authority_effect, "NONE")
        self.assertEqual(context.rag_release, "r9")
        self.assertEqual(len(context.sources), len(SOURCES))

    def test_each_source_is_read_once_and_not_reopened_as_text(self):
        original = Path.read_bytes
        reads = []

        def capture(path):
            reads.append(path)
            return original(path)

        with patch.object(Path, "read_bytes", capture), patch.object(
                Path, "read_text", side_effect=AssertionError("source reread")):
            build_lion_context(self.root)
        self.assertEqual(reads, [self.root / rel for rel in SOURCES])

    def test_bootstrap_change_after_capture_does_not_change_interpretation(self):
        original = Path.read_bytes
        captured = self.bootstrap_path.read_bytes()

        def replace_after_capture(path):
            raw = original(path)
            if path == self.bootstrap_path:
                self.write_json(path, {"preferred_release": "replacement"})
            return raw

        with patch.object(Path, "read_bytes", replace_after_capture):
            context = build_lion_context(self.root)
        self.assertEqual(context.rag_release, "r9")
        row = next(row for row in context.sources if row[0] == SOURCES[-1])
        self.assertEqual(row[1], hashlib.sha256(captured).hexdigest())
        self.assertEqual(json.loads(self.bootstrap_path.read_bytes())["preferred_release"],
                         "replacement")
        self.assertEqual(context.authority_effect, "NONE")

    def test_later_valid_policy_cannot_replace_invalid_captured_policy(self):
        self.write_json(self.auth_path, {"invariants": []})
        original = Path.read_bytes

        def replace_after_capture(path):
            raw = original(path)
            if path == self.bootstrap_path:
                self.write_json(self.auth_path, self.auth)
            return raw

        with patch.object(Path, "read_bytes", replace_after_capture):
            with self.assertRaisesRegex(ValueError, "authorization lifecycle"):
                build_lion_context(self.root)

    def test_digest_changes_when_source_bytes_change(self):
        before = build_lion_context(self.root)
        (self.root / SOURCES[0]).write_bytes(b"changed source")
        after = build_lion_context(self.root)
        self.assertNotEqual(before.digest, after.digest)
        self.assertEqual(before.text, after.text)

    def test_stable_source_is_deterministic(self):
        self.assertEqual(build_lion_context(self.root), build_lion_context(self.root))

    def test_unsafe_release_identifiers_are_rejected(self):
        for value in ("", "r9\nAUTHORITY=ALLOW", "r9\r", "r9\t", " r9",
                      "r9 ", "a/b", "r9\x00", "r" * 257):
            with self.subTest(value=repr(value)):
                self.write_json(self.bootstrap_path, {"preferred_release": value})
                with self.assertRaises(ValueError):
                    build_lion_context(self.root)

    def test_non_string_release_identifiers_are_rejected(self):
        for value in (None, True, 15, ["r9"], {"release": "r9"}):
            with self.subTest(value=value):
                self.write_json(self.bootstrap_path, {"preferred_release": value})
                with self.assertRaises(ValueError):
                    build_lion_context(self.root)

    def test_current_release_identifier_alphabet_is_accepted(self):
        for release in ("r9", "lion-rag30-v1.5-r1", "release_TEST-1.2", "r" * 256):
            with self.subTest(release=release):
                self.write_json(self.bootstrap_path, {"preferred_release": release})
                self.assertEqual(build_lion_context(self.root).rag_release, release)

    def test_missing_release_is_rejected(self):
        self.write_json(self.bootstrap_path, {})
        with self.assertRaises(ValueError):
            build_lion_context(self.root)

    def test_duplicate_bootstrap_key_is_rejected(self):
        self.bootstrap_path.write_bytes(b'{"preferred_release":"r9","preferred_release":"r10"}')
        with self.assertRaises(ValueError):
            build_lion_context(self.root)

    def test_duplicate_policy_key_is_rejected(self):
        invariants = json.dumps(self.auth["invariants"])
        self.auth_path.write_text('{"invariants":[],"invariants":' + invariants + '}',
                                  encoding="utf-8")
        with self.assertRaises(ValueError):
            build_lion_context(self.root)

    def test_non_object_bootstrap_is_rejected(self):
        for value in ([], "r9", None):
            with self.subTest(value=value):
                self.write_json(self.bootstrap_path, value)
                with self.assertRaises(ValueError):
                    build_lion_context(self.root)

    def test_non_object_policy_is_rejected(self):
        for value in ([], "policy", None):
            with self.subTest(value=value):
                self.write_json(self.auth_path, value)
                with self.assertRaises(ValueError):
                    build_lion_context(self.root)

    def test_policy_invariants_must_be_string_array(self):
        for value in (None, {}, self.auth["invariants"] + [True],
                      {key: True for key in self.auth["invariants"]}):
            with self.subTest(value=value):
                self.write_json(self.auth_path, {"invariants": value})
                with self.assertRaises(ValueError):
                    build_lion_context(self.root)

    def test_incomplete_policy_is_rejected(self):
        self.write_json(self.auth_path, {"invariants": self.auth["invariants"][:-1]})
        with self.assertRaises(ValueError):
            build_lion_context(self.root)

    def test_malformed_json_is_rejected(self):
        self.bootstrap_path.write_bytes(b'{"preferred_release":')
        with self.assertRaises(ValueError):
            build_lion_context(self.root)

    def test_invalid_utf8_is_rejected(self):
        self.bootstrap_path.write_bytes(b'{"preferred_release":"\xff"}')
        with self.assertRaises(ValueError):
            build_lion_context(self.root)

    def test_missing_source_is_rejected(self):
        (self.root / SOURCES[0]).unlink()
        with self.assertRaises(FileNotFoundError):
            build_lion_context(self.root)

    def test_oversize_source_is_rejected(self):
        (self.root / SOURCES[0]).write_bytes(b"x" * 512001)
        with self.assertRaisesRegex(ValueError, "source too large"):
            build_lion_context(self.root)

    def test_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            destination = Path(outside) / "AGENTS.md"
            destination.write_bytes(b"outside")
            source = self.root / SOURCES[0]
            source.unlink()
            try:
                source.symlink_to(destination)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable")
            with self.assertRaisesRegex(ValueError, "context source escape"):
                build_lion_context(self.root)

    def test_digest_covers_returned_context_and_provenance(self):
        context = build_lion_context(self.root)
        payload = {"text": context.text, "sources": context.sources,
                   "federation": FED, "invariants": INV,
                   "rag_release": context.rag_release, "authority_effect": "NONE"}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False)
        expected = hashlib.sha256(("LION/R10/SYSTEM-CONTEXT/1\0" + encoded).encode()).hexdigest()
        self.assertEqual(context.digest, expected)


if __name__ == "__main__":
    unittest.main()
