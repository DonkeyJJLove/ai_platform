"""Portable byte-transport tests; neither model inference nor Docker E2E."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cyber_lion.mission_control import artifact_transfer as t


class ArtifactTransferTests(unittest.TestCase):
    def setUp(self):
        self.binding = {
            "repository": "fixture/new-repository", "source_head": "a" * 40,
            "mission_id": "fixture-mission", "assignment_id": "fixture-assignment",
            "conversation_id": "fixture-conversation", "binding_epoch": 1,
            "generation": 2, "lease_generation": 3, "context_digest": "b" * 64,
            "projection_digest": "c" * 64, "request_id": "fixture-request",
            "producer_ref": "fixture-producer",
        }
        self.files = {"src/component.py": b"def twice(x):\r\n    return 2*x\r\n",
                      "data/config.json": '{"opis":"Zażółć gęślą jaźń"}\n'.encode(),
                      "data/raw.bin": bytes(range(256))}
        self.raw = t.create_bundle(self.files, self.binding)
        self.digest = hashlib.sha256(self.raw).hexdigest()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def accept(self, raw=None, binding=None):
        raw = self.raw if raw is None else raw
        return t.verify_bundle(raw, hashlib.sha256(raw).hexdigest(), self.binding if binding is None else binding)

    def reject_mutation(self, update):
        value = json.loads(self.raw)
        update(value)
        raw = json.dumps(value).encode()
        with self.assertRaises(t.ArtifactTransferError):
            self.accept(raw)

    def test_bytes_polish_crlf_and_binary_roundtrip(self):
        self.assertEqual(self.accept()[1], self.files)

    def test_deterministic_order(self):
        self.assertEqual(self.raw, t.create_bundle(dict(reversed(list(self.files.items()))), self.binding))

    def test_every_binding_coordinate_is_enforced(self):
        for key in self.binding:
            with self.subTest(key=key):
                other = dict(self.binding)
                if key in t.INTEGER_FIELDS:
                    other[key] += 1
                elif key in t.DIGEST_FIELDS:
                    other[key] = "d" * 64
                elif key == "source_head":
                    other[key] = "d" * 40
                else:
                    other[key] = "other-identity"
                with self.assertRaises(t.ArtifactTransferError):
                    self.accept(binding=other)

    def test_missing_extra_and_boolean_binding_rejected(self):
        for change in (lambda b: b.pop("mission_id"), lambda b: b.update(extra=1),
                       lambda b: b.update(binding_epoch=True), lambda b: b.update(generation=-1),
                       lambda b: b.update(context_digest="bad")):
            bad = dict(self.binding)
            change(bad)
            with self.assertRaises(t.ArtifactTransferError):
                t.create_bundle(self.files, bad)

    def test_wire_checksum_tamper_rejected(self):
        with self.assertRaises(t.ArtifactTransferError):
            t.verify_bundle(self.raw + b" ", self.digest, self.binding)

    def test_inner_checksum_tamper_rejected_with_new_wire_hash(self):
        self.reject_mutation(lambda v: v["files"][0].update(sha256="0" * 64))

    def test_duplicate_json_key_rejected(self):
        raw = self.raw.replace(b'"schema":', b'"schema":"wrong","schema":', 1)
        with self.assertRaises(t.ArtifactTransferError):
            self.accept(raw)

    def test_invalid_utf8_and_json_rejected(self):
        for raw in (b"\xff", b"{", b"[]", b"null", b'{"bad":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(t.ArtifactTransferError):
                self.accept(raw)

    def test_authority_and_schema_not_promoted(self):
        self.reject_mutation(lambda v: v.update(authority_effect="ALLOW"))
        self.reject_mutation(lambda v: v.update(schema="other/v1"))
        self.reject_mutation(lambda v: v.update(runtime_admission=True))

    def test_path_traversal_and_platform_aliases_rejected(self):
        paths = ("../x", "/etc/x", "C:/x", "a\\b", "a//b", "x/../b", "./a", "a/",
                 "a.", "a ", "a:b", "CON", "con.txt", "LPT1.txt", "COM0", ".git/config",
                 ".env", "src/credentials.json", "src/id_rsa", "ą.py")
        for path in paths:
            with self.subTest(path=path), self.assertRaises(t.ArtifactTransferError):
                t.create_bundle({path: b"x"}, self.binding)

    def test_case_and_file_directory_collisions_rejected(self):
        for files in ({"a.py": b"a", "A.py": b"b"}, {"a": b"a", "a/b": b"b"}):
            with self.assertRaises(t.ArtifactTransferError):
                t.create_bundle(files, self.binding)

    def test_duplicate_member_rejected(self):
        self.reject_mutation(lambda v: v["files"].append(v["files"][0]))

    def test_receiver_rechecks_paths(self):
        self.reject_mutation(lambda v: v["files"][0].update(path="../../escape"))

    def test_limits_checked_before_decoding(self):
        self.reject_mutation(lambda v: v["files"][0].update(size=t.MAX_FILE_BYTES + 1))
        with patch.object(t.base64, "b64decode", side_effect=AssertionError("must not decode")):
            self.reject_mutation(lambda v: v["files"][0].update(data_b64="A" * (t.MAX_FILE_BYTES * 2)))

    def test_file_and_aggregate_limits(self):
        for files in ({"a": b"x" * (t.MAX_FILE_BYTES + 1)},
                      {str(i): b"x" * t.MAX_FILE_BYTES for i in range(5)}):
            with self.assertRaises(t.ArtifactTransferError):
                t.create_bundle(files, self.binding)

    def test_empty_files_supported_but_empty_bundle_rejected(self):
        raw = t.create_bundle({"empty": b""}, self.binding)
        self.assertEqual(self.accept(raw)[1], {"empty": b""})
        with self.assertRaises(t.ArtifactTransferError):
            t.create_bundle({}, self.binding)

    def test_file_count_and_wire_limits(self):
        with self.assertRaises(t.ArtifactTransferError):
            t.create_bundle({str(i): b"" for i in range(t.MAX_FILES + 1)}, self.binding)
        with self.assertRaises(t.ArtifactTransferError):
            self.accept(b" " * (t.MAX_BUNDLE_BYTES + 1))

    def test_base64_and_size_rejected(self):
        self.reject_mutation(lambda v: v["files"][0].update(data_b64="!!!!"))
        self.reject_mutation(lambda v: v["files"][0].update(size=True))
        self.reject_mutation(lambda v: v["files"][0].update(size=0))

    def test_parent_digest_preserved(self):
        raw = t.create_bundle(self.files, self.binding, parent_transfer_sha256=self.digest)
        value, _ = self.accept(raw)
        self.assertEqual(value["parent_transfer_sha256"], self.digest)
        self.assertNotEqual(hashlib.sha256(raw).hexdigest(), self.digest)

    def test_bad_parent_digest_rejected_on_both_sides(self):
        with self.assertRaises(t.ArtifactTransferError):
            t.create_bundle(self.files, self.binding, parent_transfer_sha256="wrong")
        self.reject_mutation(lambda v: v.update(parent_transfer_sha256=False))

    def test_fresh_workspace_and_independent_readback(self):
        result = t.materialize_bundle(self.raw, self.digest, self.binding, self.root)
        self.assertFalse(result["execution_performed"])
        self.assertEqual(result["authority_effect"], "NONE")
        self.assertTrue(result["readback_match"])
        self.assertTrue(t.verify_workspace(result["workspace"], self.raw, self.digest, self.binding)["readback_match"])
        for name, data in self.files.items():
            self.assertEqual((Path(result["workspace"]) / name).read_bytes(), data)

    def test_repeated_materialization_never_overwrites_workspace(self):
        one = t.materialize_bundle(self.raw, self.digest, self.binding, self.root)
        two = t.materialize_bundle(self.raw, self.digest, self.binding, self.root)
        self.assertNotEqual(one["workspace"], two["workspace"])
        self.assertEqual(t.verify_workspace(one["workspace"], self.raw, self.digest, self.binding)["file_count"], 3)

    def test_invalid_bundle_does_not_create_workspace(self):
        with self.assertRaises(t.ArtifactTransferError):
            t.materialize_bundle(self.raw, "0" * 64, self.binding, self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_tampered_workspace_rejected(self):
        result = t.materialize_bundle(self.raw, self.digest, self.binding, self.root)
        (Path(result["workspace"]) / "src/component.py").write_bytes(b"wrong")
        with self.assertRaises(t.ArtifactTransferError):
            t.verify_workspace(result["workspace"], self.raw, self.digest, self.binding)

    def test_extra_file_rejected(self):
        result = t.materialize_bundle(self.raw, self.digest, self.binding, self.root)
        (Path(result["workspace"]) / "extra").write_bytes(b"x")
        with self.assertRaises(t.ArtifactTransferError):
            t.verify_workspace(result["workspace"], self.raw, self.digest, self.binding)

    def test_carrier_tampering_rejected(self):
        result = t.materialize_bundle(self.raw, self.digest, self.binding, self.root)
        (Path(result["workspace"]) / "_LION_TRANSFER.json").write_bytes(b"{}")
        with self.assertRaises(t.ArtifactTransferError):
            t.verify_workspace(result["workspace"], self.raw, self.digest, self.binding)

    def test_reserved_carrier_rejected(self):
        for name in ("_LION_TRANSFER.json", "_lion_transfer.json/a"):
            with self.assertRaises(t.ArtifactTransferError):
                t.create_bundle({name: b"x"}, self.binding)
        self.reject_mutation(lambda v: v["files"][0].update(path="_LION_TRANSFER.json"))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_missing_parent_is_not_created(self):
        with self.assertRaises(t.ArtifactTransferError):
            t.materialize_bundle(self.raw, self.digest, self.binding, self.root / "absent")

    def test_fresh_interpreter_cli(self):
        bundle = self.root / "bundle.json"
        binding = self.root / "binding.json"
        bundle.write_bytes(self.raw)
        binding.write_text(json.dumps(self.binding), encoding="utf-8")
        command = [sys.executable, "-I", str(Path(t.__file__).resolve()), "materialize", "--bundle", str(bundle),
                   "--binding", str(binding), "--expected-sha256", self.digest, "--private-parent", str(self.root)]
        result = subprocess.run(command, capture_output=True, timeout=15, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(json.loads(result.stdout)["readback_match"])

    def test_cli_bad_digest_nonzero(self):
        bundle = self.root / "bundle.json"
        binding = self.root / "binding.json"
        bundle.write_bytes(self.raw)
        binding.write_text(json.dumps(self.binding), encoding="utf-8")
        result = subprocess.run([sys.executable, "-I", str(Path(t.__file__).resolve()), "verify", "--bundle", str(bundle),
                                 "--binding", str(binding), "--expected-sha256", "0" * 64],
                                capture_output=True, timeout=15, encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "REJECTED")


if __name__ == "__main__":
    unittest.main()
