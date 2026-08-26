from __future__ import annotations

import base64
import hashlib
import unittest
from unittest import mock

from cyber_lion.enterprise import moon_file_write as mfw


def _body(path: str, data: bytes=b"AAAA", request_id: str="test-1", *, mode: str="CREATE_ONLY", previous: str="-") -> str:
    return "\n".join([
        mfw.PREFIX,
        f"path={path}",
        f"operation_mode={mode}",
        f"expected_previous_state={'ABSENT' if mode == 'CREATE_ONLY' else 'PRESENT_EXACT'}",
        f"expected_previous_sha256={previous}",
        f"content_b64={base64.b64encode(data).decode('ascii')}",
        f"expected_sha256={hashlib.sha256(data).hexdigest()}",
        f"request_id={request_id}",
    ])


class _FakeResponse:
    def __init__(self,status=200,payload=b'{"permission":"admin"}'):
        self.status=status; self._payload=payload; self.read_limit=None
    def read(self,limit): self.read_limit=limit; return self._payload[:limit]


class _FakeHTTPSConnection:
    instances=[]; response=_FakeResponse(); request_error=None
    def __init__(self,host,port,timeout): self.host=host; self.port=port; self.timeout=timeout; self.calls=[]; self.closed=False; type(self).instances.append(self)
    def request(self,method,path,*,headers):
        if type(self).request_error: raise type(self).request_error
        self.calls.append((method,path,headers))
    def getresponse(self): return type(self).response
    def close(self): self.closed=True


class MoonFileWriteTests(unittest.TestCase):
    def setUp(self):
        _FakeHTTPSConnection.instances=[]; _FakeHTTPSConnection.response=_FakeResponse(); _FakeHTTPSConnection.request_error=None

    def test_parse_accepts_exact_v2_envelope(self):
        values=mfw._parse_envelope(_body("/home/d2j3/probe.txt"))
        self.assertEqual(values["operation_mode"],"CREATE_ONLY"); self.assertEqual(values["expected_previous_sha256"],"-")

    def test_parser_rejects_old_or_reordered_envelope(self):
        with self.assertRaises(RuntimeError): mfw._parse_envelope("MOON-FILE-WRITE v1\npath=/home/d2j3/x")
        lines=_body("/home/d2j3/probe.txt").splitlines(); lines[1],lines[2]=lines[2],lines[1]
        with self.assertRaises(RuntimeError): mfw._parse_envelope("\n".join(lines))

    def test_target_rejects_non_direct_child_and_fence_file(self):
        for path in ("/home/d2j3/../escape.txt","/home/d2j3/sub/file.txt","/tmp/file.txt","relative.txt",mfw.FENCE_PATH):
            with self.subTest(path=path):
                with self.assertRaises(RuntimeError): mfw._target_name(path)

    def test_decode_rejects_noncanonical_and_oversized(self):
        with self.assertRaises(RuntimeError): mfw._decode_content("QUFBQQ")
        with self.assertRaises(RuntimeError): mfw._decode_content(base64.b64encode(b"A"*(mfw.MAX_CONTENT_BYTES+1)).decode())

    @mock.patch.object(mfw.http.client,"HTTPSConnection",_FakeHTTPSConnection)
    def test_permission_lookup_is_fixed_origin_get(self):
        self.assertEqual(mfw._github_permission("DonkeyJJLove/ai_platform","actor/name?x=1","secret"),"admin")
        c=_FakeHTTPSConnection.instances[0]
        self.assertEqual((c.host,c.port,c.timeout),("api.github.com",443,20)); self.assertTrue(c.closed)
        method,path,headers=c.calls[0]
        self.assertEqual(method,"GET"); self.assertEqual(path,"/repos/DonkeyJJLove/ai_platform/collaborators/actor%2Fname%3Fx%3D1/permission")
        self.assertIn("Authorization",headers)

    @mock.patch.object(mfw.http.client,"HTTPSConnection",_FakeHTTPSConnection)
    def test_permission_lookup_fail_closed(self):
        _FakeHTTPSConnection.response=_FakeResponse(status=302,payload=b"")
        with self.assertRaises(RuntimeError): mfw._github_permission("DonkeyJJLove/ai_platform","actor","x")

    def test_execute_rejects_wrong_runner_before_effect(self):
        event={"issue":{"number":144},"comment":{"body":_body("/home/d2j3/probe.txt")},"sender":{"login":"DonkeyJJLove"}}
        with self.assertRaisesRegex(RuntimeError,"unexpected MOON runner"):
            mfw.execute(event,repository="DonkeyJJLove/ai_platform",token="x",runner_name="wrong")

    def test_execute_rejects_content_digest_mismatch_before_mediator(self):
        body=_body("/home/d2j3/probe.txt").replace(hashlib.sha256(b"AAAA").hexdigest(),hashlib.sha256(b"BBBB").hexdigest())
        event={"issue":{"number":144},"comment":{"body":body},"sender":{"login":"DonkeyJJLove"}}
        with self.assertRaisesRegex(RuntimeError,"pre-write content digest mismatch"):
            mfw.execute(event,repository="DonkeyJJLove/ai_platform",token="x",runner_name="lion-moon-r9d8-test")


if __name__ == "__main__": unittest.main()
