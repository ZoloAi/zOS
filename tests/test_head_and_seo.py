"""HEAD-method + SEO-meta seam tests.

Pins the two reachability fixes:

1. HEAD = GET minus body through the WSGI bridge (was: AttributeError → 500 on
   EVERY path in prod, because the inherited SimpleHTTPRequestHandler.do_HEAD
   read ``self.directory`` which the bridge never sets). Verified as GET/HEAD
   parity on the reserved /zhealth probe: same status, same Content-Length,
   empty HEAD body.

2. _inject_seo_meta — the zMeta-driven head stamp that gives plain-GET
   consumers (crawlers, link-preview bots) something to read in the hydration
   shell: description, OpenGraph set, canonical, twitter card.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from L4_Orchestration.r_zServer.zServer_modules.routing.wsgi_bridge import (  # noqa: E402
    WSGIBridgeHandler,
)
from L4_Orchestration.r_zServer.zServer_modules.routing.html_injectors import (  # noqa: E402
    _inject_seo_meta,
)


class _FakeRouter:
    """Just enough router for _serve_health to report ready."""

    routes = {"/": {}, "/a": {}}


def _environ(method, path):
    return {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "SERVER_PROTOCOL": "HTTP/1.1",
        "REMOTE_ADDR": "127.0.0.1",
    }


def _build(method, path, router=_FakeRouter()):
    return WSGIBridgeHandler(
        _environ(method, path),
        logger=None,
        router=router,
        mount_manager=None,
        cache_manager=None,
        config=None,
    )


def _dispatch(method, path, router=_FakeRouter()):
    handler = _build(method, path, router)
    handler.dispatch()
    return handler


class TestHeadMethod(unittest.TestCase):
    def test_head_health_matches_get_minus_body(self):
        get = _dispatch("GET", "/zhealth")
        head = _dispatch("HEAD", "/zhealth")

        self.assertTrue(get.status_line.startswith("200"))
        self.assertTrue(head.status_line.startswith("200"))
        self.assertGreater(len(get.body), 0)
        self.assertEqual(head.body, b"")

        get_len = dict(get.response_headers).get("Content-Length")
        head_len = dict(head.response_headers).get("Content-Length")
        self.assertEqual(get_len, head_len)

    def test_head_error_page_has_status_but_no_body(self):
        """Styled error pages honor HEAD: same status as GET, empty body.

        Driven through send_error directly (full routing needs a live zos); the
        seam under test is the end_headers body-discard swap, which every error
        response goes through.
        """
        get = _build("GET", "/x")
        head = _build("HEAD", "/x")
        get.send_error(404, "Not found")
        head.send_error(404, "Not found")
        self.assertTrue(get.status_line.startswith("404"))
        self.assertTrue(head.status_line.startswith("404"))
        self.assertGreater(len(get.body), 0)
        self.assertEqual(head.body, b"")

    def test_head_restores_response_buffer(self):
        """After a HEAD, wfile is the original (empty) buffer, not the discard sink."""
        head = _dispatch("HEAD", "/zhealth")
        self.assertEqual(head.wfile.getvalue(), b"")


_SHELL = "<html><head><title></title></head><body><zVaF></zVaF></body></html>"


class TestSeoMeta(unittest.TestCase):
    def test_full_meta_set(self):
        out = _inject_seo_meta(
            _SHELL,
            page_title="zCloud - Home",
            app_brand="zCloud",
            zVaFile_meta={"zDescription": "Build & host zOS apps.", "zImage": "/static/og.png"},
            request_host="zolo.media",
            request_path="/?utm=x",
            request_proto="https",
        )
        self.assertIn('<meta name="description" content="Build &amp; host zOS apps.">', out)
        self.assertIn('<meta property="og:title" content="zCloud - Home">', out)
        self.assertIn('<meta property="og:site_name" content="zCloud">', out)
        # canonical strips the query string; relative zImage absolutized
        self.assertIn('<link rel="canonical" href="https://zolo.media/">', out)
        self.assertIn('<meta property="og:url" content="https://zolo.media/">', out)
        self.assertIn('<meta property="og:image" content="https://zolo.media/static/og.png">', out)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', out)

    def test_minimal_page_gets_baseline_tags_only(self):
        out = _inject_seo_meta(
            _SHELL, page_title="Hello", app_brand=None, zVaFile_meta={},
            request_host=None, request_path="/", request_proto=None,
        )
        self.assertIn('<meta property="og:title" content="Hello">', out)
        self.assertIn('<meta name="twitter:card" content="summary">', out)
        self.assertNotIn('name="description"', out)
        self.assertNotIn('rel="canonical"', out)
        self.assertNotIn('og:image', out)

    def test_attribute_escaping(self):
        out = _inject_seo_meta(
            _SHELL, page_title='A "quoted" <title>', app_brand=None,
            zVaFile_meta={"zDescription": 'x"y<z>'},
            request_host="h", request_path="/", request_proto="https",
        )
        self.assertIn('content="A &quot;quoted&quot; &lt;title&gt;"', out)
        self.assertIn('content="x&quot;y&lt;z&gt;"', out)

    def test_no_head_is_a_noop(self):
        self.assertEqual(_inject_seo_meta("no head here", "t", "b", {}), "no head here")


if __name__ == "__main__":
    unittest.main()
