import inspect
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from cyber_lion.enterprise import actions_dispatch_temporal_compat as compat


class _Headers(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class _HTTPError302(urllib.error.HTTPError):
    def __init__(self, location: str):
        super().__init__(
            url="https://api.github.com/example",
            code=302,
            msg="Found",
            hdrs=_Headers({"Location": location}),
            fp=None,
        )


class _Api:
    repository = "DonkeyJJLove/ai_platform"
    api_url = "https://api.github.com"
    def _headers(self):
        return {"Authorization": "Bearer SECRET", "Accept": "application/vnd.github+json"}


class _NoRedirectOpener:
    def __init__(self, location): self.location = location; self.request = None
    def open(self, request, timeout):
        self.request = request
        raise _HTTPError302(self.location)


class _ArchiveResponse:
    status = 200
    def __init__(self, data): self.data = data
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit): return self.data


class ArtifactRedirectCompatibilityTests(unittest.TestCase):
    def test_redirect_host_and_scheme_are_fail_closed(self):
        good = "https://productionresultssa0.blob.core.windows.net/actions-results/x?sig=y"
        self.assertEqual(compat._validate_archive_location(good), good)
        for bad in (
            "http://productionresultssa0.blob.core.windows.net/x",
            "https://evil.example/x",
            "https://user:pass@productionresultssa0.blob.core.windows.net/x",
            "file:///tmp/x",
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(RuntimeError):
                    compat._validate_archive_location(bad)

    def test_api_hop_is_authenticated_and_requires_redirect(self):
        location = "https://productionresultssa0.blob.core.windows.net/actions-results/x?sig=y"
        opener = _NoRedirectOpener(location)
        with patch("urllib.request.build_opener", return_value=opener):
            result = compat._artifact_redirect(_Api(), 123)
        self.assertEqual(result, location)
        self.assertEqual(opener.request.get_header("Authorization"), "Bearer SECRET")
        self.assertTrue(opener.request.full_url.endswith("/actions/artifacts/123/zip"))

    def test_signed_archive_hop_never_forwards_authorization(self):
        location = "https://productionresultssa0.blob.core.windows.net/actions-results/x?sig=y"
        captured = {}
        def fake_urlopen(request, timeout):
            captured["request"] = request
            return _ArchiveResponse(b"zip-bytes")
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            data = compat._download_signed_archive(location)
        self.assertEqual(data, b"zip-bytes")
        self.assertIsNone(captured["request"].get_header("Authorization"))
        self.assertIsNone(captured["request"].get_header("Cookie"))

    def test_download_is_bounded_and_empty_denied(self):
        location = "https://productionresultssa0.blob.core.windows.net/actions-results/x?sig=y"
        with patch("urllib.request.urlopen", return_value=_ArchiveResponse(b"")):
            with self.assertRaisesRegex(RuntimeError, "empty"):
                compat._download_signed_archive(location)
        oversized = b"x" * (compat.MAX_ARTIFACT_BYTES + 1)
        with patch("urllib.request.urlopen", return_value=_ArchiveResponse(oversized)):
            with self.assertRaisesRegex(RuntimeError, "size limit"):
                compat._download_signed_archive(location)

    def test_compat_module_has_no_dispatch_call(self):
        source = inspect.getsource(compat)
        self.assertNotIn("api.dispatch(", source)
        self.assertIn("bridge.GitHubApi.download_artifact = _download_artifact_compat", source)


if __name__ == "__main__":
    unittest.main()
