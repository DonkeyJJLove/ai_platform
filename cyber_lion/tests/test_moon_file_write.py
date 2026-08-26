from __future__ import annotations

import base64
import hashlib
import json
import unittest
from unittest import mock

from cyber_lion.enterprise import moon_file_write as mfw


def _body(path: str, data: bytes = b"AAAA", request_id: str = "test-1") -> str:
    encoded = base64.b64encode(data).decode("ascii")
    digest = hashlib.sha256(data).hexdigest()
    return "\n".join(
        [
            mfw.PREFIX,
            f"path={path}",
            f"content_b64={encoded}",
            f"expected_sha256={digest}",
            f"request_id={request_id}",
        ]
    )


class _FakeResponse:
    def __init__(self, *, status: int = 200, payload: bytes = b'{"permission":"admin"}') -> None:
        self.status = status
        self._payload = payload
        self.read_limit = None

    def read(self, limit: int) -> bytes:
        self.read_limit = limit
        return self._payload[:limit]


class _FakeHTTPSConnection:
    instances: list["_FakeHTTPSConnection"] = []
    response = _FakeResponse()
    request_error: Exception | None = None

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.calls: list[tuple[str, str, dict[str, str]]] = []
        self.closed = False
        type(self).instances.append(self)

    def request(self, method: str, path: str, *, headers: dict[str, str]) -> None:
        if type(self).request_error is not None:
            raise type(self).request_error
        self.calls.append((method, path, headers))

    def getresponse(self) -> _FakeResponse:
        return type(self).response

    def close(self) -> None:
        self.closed = True


class MoonFileWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        _FakeHTTPSConnection.instances = []
        _FakeHTTPSConnection.response = _FakeResponse()
        _FakeHTTPSConnection.request_error = None

    def test_parse_accepts_exact_envelope(self) -> None:
        values = mfw._parse_envelope(_body("/home/d2j3/probe.txt"))
        self.assertEqual(values["path"], "/home/d2j3/probe.txt")
        self.assertEqual(values["content_b64"], "QUFBQQ==")

    def test_target_rejects_non_direct_child(self) -> None:
        for path in (
            "/home/d2j3/../escape.txt",
            "/home/d2j3/subdir/file.txt",
            "/tmp/file.txt",
            "relative.txt",
            "/home/d2j3/",
        ):
            with self.subTest(path=path):
                with self.assertRaises(RuntimeError):
                    mfw._target_name(path)

    def test_decode_rejects_noncanonical_base64(self) -> None:
        with self.assertRaises(RuntimeError):
            mfw._decode_content("QUFBQQ")

    def test_decode_rejects_oversized_payload(self) -> None:
        encoded = base64.b64encode(b"A" * (mfw.MAX_CONTENT_BYTES + 1)).decode("ascii")
        with self.assertRaises(RuntimeError):
            mfw._decode_content(encoded)

    @mock.patch.object(mfw.http.client, "HTTPSConnection", _FakeHTTPSConnection)
    def test_permission_lookup_is_fixed_origin_https_get_and_actor_escaped(self) -> None:
        permission = mfw._github_permission(
            "DonkeyJJLove/ai_platform",
            "actor/name?x=1",
            "secret-token",
        )
        self.assertEqual(permission, "admin")
        self.assertEqual(len(_FakeHTTPSConnection.instances), 1)
        connection = _FakeHTTPSConnection.instances[0]
        self.assertEqual(connection.host, "api.github.com")
        self.assertEqual(connection.port, 443)
        self.assertEqual(connection.timeout, 20)
        self.assertTrue(connection.closed)
        self.assertEqual(len(connection.calls), 1)
        method, path, headers = connection.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(
            path,
            "/repos/DonkeyJJLove/ai_platform/collaborators/actor%2Fname%3Fx%3D1/permission",
        )
        self.assertEqual(headers["Accept"], "application/vnd.github+json")
        self.assertEqual(headers["X-GitHub-Api-Version"], "2022-11-28")
        self.assertEqual(
            _FakeHTTPSConnection.response.read_limit,
            mfw.MAX_PERMISSION_RESPONSE_BYTES + 1,
        )

    @mock.patch.object(mfw.http.client, "HTTPSConnection", _FakeHTTPSConnection)
    def test_permission_lookup_rejects_non_200(self) -> None:
        _FakeHTTPSConnection.response = _FakeResponse(status=302, payload=b"")
        with self.assertRaisesRegex(RuntimeError, "unable to resolve actor permission"):
            mfw._github_permission("DonkeyJJLove/ai_platform", "actor", "x")

    @mock.patch.object(mfw.http.client, "HTTPSConnection", _FakeHTTPSConnection)
    def test_permission_lookup_rejects_oversized_response(self) -> None:
        _FakeHTTPSConnection.response = _FakeResponse(
            status=200,
            payload=b"A" * (mfw.MAX_PERMISSION_RESPONSE_BYTES + 1),
        )
        with self.assertRaisesRegex(RuntimeError, "unable to resolve actor permission"):
            mfw._github_permission("DonkeyJJLove/ai_platform", "actor", "x")

    @mock.patch.object(mfw.http.client, "HTTPSConnection", _FakeHTTPSConnection)
    def test_permission_lookup_rejects_malformed_response(self) -> None:
        _FakeHTTPSConnection.response = _FakeResponse(status=200, payload=b"not-json")
        with self.assertRaisesRegex(RuntimeError, "unable to resolve actor permission"):
            mfw._github_permission("DonkeyJJLove/ai_platform", "actor", "x")

    @mock.patch.object(mfw.http.client, "HTTPSConnection", _FakeHTTPSConnection)
    def test_permission_lookup_transport_failure_fails_closed(self) -> None:
        _FakeHTTPSConnection.request_error = OSError("network down")
        with self.assertRaisesRegex(RuntimeError, "unable to resolve actor permission"):
            mfw._github_permission("DonkeyJJLove/ai_platform", "actor", "x")

    def test_permission_lookup_rejects_repository_injection(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "invalid repository"):
            mfw._github_permission("DonkeyJJLove/ai_platform?x=1", "actor", "x")

    def test_execute_rejects_wrong_runner(self) -> None:
        event = {
            "issue": {"number": 144},
            "comment": {"body": _body("/home/d2j3/probe.txt")},
            "sender": {"login": "DonkeyJJLove"},
        }
        with mock.patch.object(mfw, "_github_permission", return_value="admin"):
            with self.assertRaisesRegex(RuntimeError, "unexpected MOON runner"):
                mfw.execute(event, repository="DonkeyJJLove/ai_platform", token="x", runner_name="wrong")

    def test_execute_rejects_untrusted_actor(self) -> None:
        event = {
            "issue": {"number": 144},
            "comment": {"body": _body("/home/d2j3/probe.txt")},
            "sender": {"login": "intruder"},
        }
        with mock.patch.object(mfw, "_github_permission", return_value="read"):
            with self.assertRaisesRegex(RuntimeError, "actor permission is not trusted"):
                mfw.execute(
                    event,
                    repository="DonkeyJJLove/ai_platform",
                    token="x",
                    runner_name="lion-moon-r9d8-test",
                )

    def test_execute_reconciles_exact_digest(self) -> None:
        event = {
            "issue": {"number": 144},
            "comment": {"body": _body("/home/d2j3/probe.txt")},
            "sender": {"login": "DonkeyJJLove"},
        }
        with mock.patch.object(mfw, "_github_permission", return_value="admin"), mock.patch.object(
            mfw,
            "_atomic_write",
            side_effect=lambda name, data: hashlib.sha256(data).hexdigest(),
        ):
            receipt = mfw.execute(
                event,
                repository="DonkeyJJLove/ai_platform",
                token="x",
                runner_name="lion-moon-r9d8-test",
            )
        self.assertEqual(receipt["effect"], "RECONCILED")
        self.assertEqual(receipt["path"], "/home/d2j3/probe.txt")
        self.assertEqual(receipt["sha256"], hashlib.sha256(b"AAAA").hexdigest())

    def test_execute_rejects_content_digest_mismatch(self) -> None:
        body = _body("/home/d2j3/probe.txt", b"AAAA").replace(
            hashlib.sha256(b"AAAA").hexdigest(),
            hashlib.sha256(b"BBBB").hexdigest(),
        )
        event = {
            "issue": {"number": 144},
            "comment": {"body": body},
            "sender": {"login": "DonkeyJJLove"},
        }
        with mock.patch.object(mfw, "_github_permission", return_value="admin"), mock.patch.object(
            mfw, "_atomic_write"
        ) as atomic_write:
            with self.assertRaisesRegex(RuntimeError, "pre-write content digest mismatch"):
                mfw.execute(
                    event,
                    repository="DonkeyJJLove/ai_platform",
                    token="x",
                    runner_name="lion-moon-r9d8-test",
                )
            atomic_write.assert_not_called()

    def test_execute_rejects_post_write_digest_mismatch(self) -> None:
        event = {
            "issue": {"number": 144},
            "comment": {"body": _body("/home/d2j3/probe.txt")},
            "sender": {"login": "DonkeyJJLove"},
        }
        with mock.patch.object(mfw, "_github_permission", return_value="admin"), mock.patch.object(
            mfw,
            "_atomic_write",
            return_value=hashlib.sha256(b"different").hexdigest(),
        ):
            with self.assertRaisesRegex(RuntimeError, "post-write digest mismatch"):
                mfw.execute(
                    event,
                    repository="DonkeyJJLove/ai_platform",
                    token="x",
                    runner_name="lion-moon-r9d8-test",
                )


if __name__ == "__main__":
    unittest.main()
