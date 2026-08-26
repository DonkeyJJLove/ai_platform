from __future__ import annotations

import base64
import hashlib

import pytest

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


def test_parse_accepts_exact_envelope():
    values = mfw._parse_envelope(_body("/home/d2j3/probe.txt"))
    assert values["path"] == "/home/d2j3/probe.txt"
    assert values["content_b64"] == "QUFBQQ=="


@pytest.mark.parametrize(
    "path",
    [
        "/home/d2j3/../escape.txt",
        "/home/d2j3/subdir/file.txt",
        "/tmp/file.txt",
        "relative.txt",
        "/home/d2j3/",
    ],
)
def test_target_rejects_non_direct_child(path: str):
    with pytest.raises(RuntimeError):
        mfw._target_name(path)


def test_decode_rejects_noncanonical_base64():
    with pytest.raises(RuntimeError):
        mfw._decode_content("QUFBQQ")


def test_decode_rejects_oversized_payload():
    encoded = base64.b64encode(b"A" * (mfw.MAX_CONTENT_BYTES + 1)).decode("ascii")
    with pytest.raises(RuntimeError):
        mfw._decode_content(encoded)


def test_execute_rejects_wrong_runner(monkeypatch):
    event = {
        "issue": {"number": 144},
        "comment": {"body": _body("/home/d2j3/probe.txt")},
        "sender": {"login": "DonkeyJJLove"},
    }
    monkeypatch.setattr(mfw, "_github_permission", lambda *args: "admin")
    with pytest.raises(RuntimeError, match="unexpected MOON runner"):
        mfw.execute(event, repository="DonkeyJJLove/ai_platform", token="x", runner_name="wrong")


def test_execute_rejects_untrusted_actor(monkeypatch):
    event = {
        "issue": {"number": 144},
        "comment": {"body": _body("/home/d2j3/probe.txt")},
        "sender": {"login": "intruder"},
    }
    monkeypatch.setattr(mfw, "_github_permission", lambda *args: "read")
    with pytest.raises(RuntimeError, match="actor permission is not trusted"):
        mfw.execute(
            event,
            repository="DonkeyJJLove/ai_platform",
            token="x",
            runner_name="lion-moon-r9d8-test",
        )


def test_execute_reconciles_exact_digest(monkeypatch):
    event = {
        "issue": {"number": 144},
        "comment": {"body": _body("/home/d2j3/probe.txt")},
        "sender": {"login": "DonkeyJJLove"},
    }
    monkeypatch.setattr(mfw, "_github_permission", lambda *args: "admin")
    monkeypatch.setattr(
        mfw,
        "_atomic_write",
        lambda name, data: hashlib.sha256(data).hexdigest(),
    )
    receipt = mfw.execute(
        event,
        repository="DonkeyJJLove/ai_platform",
        token="x",
        runner_name="lion-moon-r9d8-test",
    )
    assert receipt["effect"] == "RECONCILED"
    assert receipt["path"] == "/home/d2j3/probe.txt"
    assert receipt["sha256"] == hashlib.sha256(b"AAAA").hexdigest()
