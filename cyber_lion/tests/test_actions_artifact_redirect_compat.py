import inspect
import unittest
from unittest.mock import patch
import urllib.error

from cyber_lion.enterprise import actions_dispatch_temporal_compat as compat


class _Headers(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class _HTTPErrorRedirect(urllib.error.HTTPError):
    def __init__(self, code: int, location: str):
        super().__init__(
            url="https://api.github.com/example",
            code=code,
            msg="Redirect",
            hdrs=_Headers({"Location": location}),
            fp=None,
        )


class _Api:
    repository = "DonkeyJJLove/ai_platform"
    api_url = "https://api.github.com"

    def _headers(self):
        return {"Authorization": "Bearer SECRET", "Accept": "application/vnd.github+json"}


class _NoRedirectOpener:
    def __init__(self, *, location=None, code=302, response=None):
        self.location = location
        self.code = code
        self.response = response
        self.request = None

    def open(self, request, timeout):
        self.request = request
        if self.location is not None:
            raise _HTTPErrorRedirect(self.code, self.location)
        return self.response


class _ArchiveResponse:
    status = 200

    def __init__(self, data, *, status=200):
        self.data = data
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.data


GOOD = "https://productionresultssa0.blob.core.windows.net/actions-results/x?sig=y"


class ArtifactRedirectCompatibilityTests(unittest.TestCase):
    def test_known_github_actions_archive_host_is_accepted(self):
        self.assertEqual(compat._validate_archive_location(GOOD), GOOD)
        other_known_pattern = (
            "https://productionresultssa17.blob.core.windows.net/actions-results/abc?sig=z"
        )
        self.assertEqual(
            compat._validate_archive_location(other_known_pattern),
            other_known_pattern,
        )

    def test_unknown_or_generic_azure_blob_hosts_are_denied(self):
        for bad in (
            "https://evil.blob.core.windows.net/actions-results/x?sig=y",
            "https://myaccount.blob.core.windows.net/actions-results/x?sig=y",
            "https://productionresults.blob.core.windows.net/actions-results/x?sig=y",
            "https://productionresultssa0.evil.example/actions-results/x?sig=y",
        ):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(RuntimeError, "allowlisted GitHub Actions"):
                    compat._validate_archive_location(bad)

    def test_redirect_scheme_port_path_and_signed_query_are_fail_closed(self):
        for bad in (
            "http://productionresultssa0.blob.core.windows.net/actions-results/x?sig=y",
            "https://user:pass@productionresultssa0.blob.core.windows.net/actions-results/x?sig=y",
            "https://productionresultssa0.blob.core.windows.net:8443/actions-results/x?sig=y",
            "https://productionresultssa0.blob.core.windows.net/not-actions/x?sig=y",
            "https://productionresultssa0.blob.core.windows.net/actions-results/x",
            "file:///tmp/x",
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(RuntimeError):
                    compat._validate_archive_location(bad)

    def test_signed_query_requires_exactly_one_nonempty_sig(self):
        valid = (
            "https://productionresultssa0.blob.core.windows.net/actions-results/x"
            "?sv=2023-11-03&sig=abc%2Fdef%3D&se=2026-08-23T21%3A00%3A00Z"
        )
        self.assertEqual(compat._validate_archive_location(valid), valid)
        for bad in (
            "https://productionresultssa0.blob.core.windows.net/actions-results/x?foo=bar",
            "https://productionresultssa0.blob.core.windows.net/actions-results/x?sig=",
            "https://productionresultssa0.blob.core.windows.net/actions-results/x?sig=a&sig=b",
            "https://productionresultssa0.blob.core.windows.net/actions-results/x?foo=bar&sig=",
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(RuntimeError):
                    compat._validate_archive_location(bad)

    def test_malformed_signed_query_is_denied(self):
        bad = "https://productionresultssa0.blob.core.windows.net/actions-results/x?sig"
        with self.assertRaisesRegex(RuntimeError, "malformed"):
            compat._validate_archive_location(bad)

    def test_api_hop_is_authenticated_and_requires_exact_artifact_redirect(self):
        opener = _NoRedirectOpener(location=GOOD, code=302)
        with patch("urllib.request.build_opener", return_value=opener):
            result = compat._artifact_redirect(_Api(), 123)
        self.assertEqual(result, GOOD)
        self.assertEqual(opener.request.get_header("Authorization"), "Bearer SECRET")
        self.assertTrue(opener.request.full_url.endswith("/actions/artifacts/123/zip"))
        with self.assertRaisesRegex(RuntimeError, "artifact id invalid"):
            compat._artifact_redirect(_Api(), 0)

    def test_second_hop_never_forwards_authorization_or_cookie(self):
        response = _ArchiveResponse(b"zip-bytes")
        opener = _NoRedirectOpener(response=response)
        with patch("urllib.request.build_opener", return_value=opener):
            data = compat._download_signed_archive(GOOD)
        self.assertEqual(data, b"zip-bytes")
        self.assertIsNone(opener.request.get_header("Authorization"))
        self.assertIsNone(opener.request.get_header("Cookie"))

    def test_second_hop_302_and_307_are_denied_without_following(self):
        for code in (302, 307):
            with self.subTest(code=code):
                opener = _NoRedirectOpener(
                    location="https://evil.example/archive.zip",
                    code=code,
                )
                with patch("urllib.request.build_opener", return_value=opener):
                    with self.assertRaisesRegex(RuntimeError, "second redirect"):
                        compat._download_signed_archive(GOOD)

    def test_redirect_chain_and_loop_are_unrepresentable(self):
        for location in (GOOD, "https://evil.example/archive.zip"):
            opener = _NoRedirectOpener(location=location, code=302)
            with patch("urllib.request.build_opener", return_value=opener):
                with self.assertRaisesRegex(RuntimeError, "second redirect"):
                    compat._download_signed_archive(GOOD)

    def test_second_hop_requires_terminal_200(self):
        opener = _NoRedirectOpener(response=_ArchiveResponse(b"x", status=206))
        with patch("urllib.request.build_opener", return_value=opener):
            with self.assertRaisesRegex(RuntimeError, "non-terminal status"):
                compat._download_signed_archive(GOOD)

    def test_download_is_bounded_and_empty_denied(self):
        with patch(
            "urllib.request.build_opener",
            return_value=_NoRedirectOpener(response=_ArchiveResponse(b"")),
        ):
            with self.assertRaisesRegex(RuntimeError, "empty"):
                compat._download_signed_archive(GOOD)
        oversized = b"x" * (compat.MAX_ARTIFACT_BYTES + 1)
        with patch(
            "urllib.request.build_opener",
            return_value=_NoRedirectOpener(response=_ArchiveResponse(oversized)),
        ):
            with self.assertRaisesRegex(RuntimeError, "size limit"):
                compat._download_signed_archive(GOOD)

    def test_legacy_temporal_window_and_no_dispatch_are_preserved(self):
        source = inspect.getsource(compat)
        self.assertEqual(compat.LEGACY_LOOKBACK_SECONDS, 60)
        self.assertNotIn("api.dispatch(", source)
        self.assertIn("bridge._matching_runs = _matching_runs_compat", source)
        self.assertIn("bridge.GitHubApi.download_artifact = _download_artifact_compat", source)


if __name__ == "__main__":
    unittest.main()
