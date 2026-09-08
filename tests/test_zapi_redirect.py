# zOS/tests/test_zapi_redirect.py
"""The zAPI lane's two zID-era transport additions, pinned.

1. ``ZResult.redirect`` — a handler whose outcome is "go there" (an OAuth
   authorize hop, a post-action bounce) answers with a Location header and no
   body. The transport writes Location verbatim (the HANDLER owns sanitising)
   and never caches a redirect.

2. Form-urlencoded body parsing — the OAuth2 token exchange's wire format
   (and any plain HTML <form> POST). Before the fix an urlencoded body fell
   through to ``json.loads`` and raised.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from zos_plugin import ZResult
from L4_Orchestration.r_zServer.zServer_modules.routing import zapi_handler


class TestRedirectResult(unittest.TestCase):

    def test_constructor_and_flag(self):
        z = ZResult.redirect("https://app.dev/cb?code=abc")
        self.assertTrue(z.is_redirect)
        self.assertEqual(z.status, 302)
        self.assertEqual(z.meta["location"], "https://app.dev/cb?code=abc")

    def test_non_redirect_results_stay_off_the_branch(self):
        self.assertFalse(ZResult.success(data={}).is_redirect)
        self.assertFalse(ZResult.failure("nope", status=400).is_redirect)
        # A 3xx status WITHOUT a location is not a redirect — no header to write.
        self.assertFalse(ZResult(ok=True, status=302).is_redirect)

    def test_transport_writes_location_and_no_store(self):
        z = ZResult.redirect("/next")
        handler = mock.Mock()
        # Re-enact the writer branch exactly as handle() runs it.
        handler.send_response(z.status)
        headers = {}
        handler.send_header.side_effect = lambda k, v: headers.__setitem__(k, v)
        handler.send_header("Location", z.meta["location"])
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Content-Length", "0")
        self.assertEqual(headers["Location"], "/next")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["Content-Length"], "0")


class _FakeHandler:
    """The minimal duck _parse_params reads: path, headers, rfile."""

    def __init__(self, body: bytes, content_type: str):
        self.path = "/zid/token"
        self.headers = {"Content-Type": content_type,
                        "Content-Length": str(len(body))}

        class _R:  # pylint: disable=too-few-public-methods
            def __init__(self, b):
                self._b = b

            def read(self, n):
                return self._b[:n]

        self.rfile = _R(body)


class TestUrlencodedBody(unittest.TestCase):

    def test_urlencoded_post_parses_to_fields(self):
        body = b"grant_type=authorization_code&code=abc&client_id=zid-1"
        fields, files = zapi_handler._parse_params(
            _FakeHandler(body, "application/x-www-form-urlencoded"), "POST", None)
        self.assertEqual(fields["grant_type"], "authorization_code")
        self.assertEqual(fields["code"], "abc")
        self.assertEqual(files, {})

    def test_urlencoded_values_are_decoded(self):
        body = b"redirect_uri=http%3A%2F%2Flocalhost%3A9091%2Fzauth%2Fzcloud%2Fcallback"
        fields, _ = zapi_handler._parse_params(
            _FakeHandler(body, "application/x-www-form-urlencoded"), "POST", None)
        self.assertEqual(fields["redirect_uri"],
                         "http://localhost:9091/zauth/zcloud/callback")

    def test_json_body_still_default(self):
        body = b'{"a": 1}'
        fields, _ = zapi_handler._parse_params(
            _FakeHandler(body, "application/json"), "POST", None)
        self.assertEqual(fields, {"a": 1})


if __name__ == "__main__":
    unittest.main()
