"""Ingress unit tests — config resolution, naming, child env, Caddy route upsert.

The Caddy admin API is exercised against a stub HTTP handler (no real Caddy);
these tests pin the SEAM: env → IngressConfig, slug → hostname/urls, and the
publish/unpublish route calls the module makes.
"""

import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from zos_plugin.ingress import IngressConfig, ingress_child_env, slugify  # noqa: E402


class _CaddyStub(BaseHTTPRequestHandler):
    """Minimal Caddy-admin lookalike recording every request it serves."""

    calls = []  # (method, path, body) — class-level; reset per test

    def _reply(self, code=200, payload=None):
        body = json.dumps(payload).encode() if payload is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _record(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode() if length else ""
        _CaddyStub.calls.append((self.command, self.path, body))

    def do_GET(self):
        self._record()
        if self.path == "/config/apps/http/servers":
            self._reply(payload={
                "srv0": {"listen": [":443"]},
                "srv1": {"listen": ["172.31.22.143:8765"]},
            })
        else:
            self._reply(404)

    def do_POST(self):
        self._record()
        self._reply()

    def do_DELETE(self):
        self._record()
        # First-publish path: nothing to delete yet.
        self._reply(404)

    def log_message(self, *args):  # silence
        pass


class IngressTests(unittest.TestCase):
    def setUp(self):
        for key in ("ZHOST_INGRESS_DOMAIN", "ZHOST_INGRESS_WS_PORT", "ZHOST_CADDY_ADMIN"):
            os.environ.pop(key, None)
        _CaddyStub.calls = []

    def test_not_configured_returns_none(self):
        self.assertIsNone(IngressConfig.from_env())
        self.assertEqual(ingress_child_env("zhello"), {})

    def test_slugify(self):
        self.assertEqual(slugify("zHello"), "zhello")
        self.assertEqual(slugify("My App_2"), "my-app-2")
        with self.assertRaises(ValueError):
            slugify("---")

    def test_naming_and_child_env(self):
        os.environ["ZHOST_INGRESS_DOMAIN"] = "zolo.media"
        cfg = IngressConfig.from_env()
        self.assertEqual(cfg.public_url("zHello"), "https://zhello.zolo.media")
        self.assertEqual(cfg.public_ws_url("zHello"), "wss://zhello.zolo.media:8765")
        env = cfg.child_env("zHello")
        self.assertEqual(env["WEBSOCKET_ADVERTISED_PORT"], "8765")
        self.assertEqual(env["WEBSOCKET_SSL_ENABLED"], "true")
        self.assertEqual(env["WEBSOCKET_ALLOWED_ORIGINS"], "https://zhello.zolo.media")

    def test_publish_upserts_both_routes(self):
        server = HTTPServer(("127.0.0.1", 0), _CaddyStub)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            os.environ["ZHOST_INGRESS_DOMAIN"] = "zolo.media"
            os.environ["ZHOST_CADDY_ADMIN"] = f"http://127.0.0.1:{server.server_port}"
            cfg = IngressConfig.from_env()
            url = cfg.publish("zhello", http_port=41000, ws_port=42000)
            self.assertEqual(url, "https://zhello.zolo.media")

            posts = [(p, json.loads(b)) for (m, p, b) in _CaddyStub.calls if m == "POST"]
            self.assertEqual(len(posts), 2)
            by_server = {p: body for p, body in posts}
            http_route = by_server["/config/apps/http/servers/srv0/routes"]
            ws_route = by_server["/config/apps/http/servers/srv1/routes"]
            self.assertEqual(http_route["match"], [{"host": ["zhello.zolo.media"]}])
            self.assertEqual(http_route["handle"][0]["upstreams"], [{"dial": "localhost:41000"}])
            self.assertEqual(ws_route["handle"][0]["upstreams"], [{"dial": "localhost:42000"}])

            _CaddyStub.calls = []
            cfg.unpublish("zhello")
            deletes = [p for (m, p, _) in _CaddyStub.calls if m == "DELETE"]
            self.assertEqual(sorted(deletes), ["/id/zhost_zhello_http", "/id/zhost_zhello_ws"])
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
