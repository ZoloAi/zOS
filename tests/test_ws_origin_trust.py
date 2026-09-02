# zOS/tests/test_ws_origin_trust.py
"""zOS#62 — first-party WS origins are auto-trusted; rejection names the fix.

Default allowed_origins is localhost-only, so a phone on the LAN or a freshly
assigned zCloud hosted domain hit '[WebSocketAuth] Origin rejected' on their
FIRST visit — HTTP shell loads, WS dies, blank page, zero client signal.
An Origin whose hostname equals the request's own Host hostname is the
first-party case CSWSH protection exists to protect, not block.
"""

import unittest

from zOS.L1_Foundation.b_zComm.zComm_modules.comm_websocket_auth import WebSocketAuth


class _FW:
    def debug(self, msg):
        pass


class _Log:
    def __init__(self):
        self.framework = _FW()
        self.warnings = []

    def warning(self, msg):
        self.warnings.append(msg)


class _Config:
    def __init__(self, allowed_origins=None):
        self.allowed_origins = allowed_origins or []


class _Request:
    def __init__(self, headers):
        self.headers = headers


class _WS:
    def __init__(self, origin=None, host=None):
        headers = {}
        if origin is not None:
            headers["Origin"] = origin
        if host is not None:
            headers["Host"] = host
        self.request = _Request(headers)


class TestFirstPartyAutoTrust(unittest.TestCase):

    def _auth(self, allowed=None):
        return WebSocketAuth(_Config(allowed), _Log())

    def test_lan_ip_same_host_different_port_allowed(self):
        ws = _WS(origin="http://192.168.1.7:8080", host="192.168.1.7:8865")
        self.assertTrue(self._auth().validate_origin(ws))

    def test_hosted_domain_first_visit_allowed(self):
        ws = _WS(origin="https://myapp.zolo.media", host="myapp.zolo.media")
        self.assertTrue(self._auth().validate_origin(ws))

    def test_cross_origin_still_rejected(self):
        ws = _WS(origin="https://evil.com", host="myapp.zolo.media")
        auth = self._auth()
        self.assertFalse(auth.validate_origin(ws))
        self.assertEqual(len(auth.logger.warnings), 1)
        self.assertIn("allowed_origins", auth.logger.warnings[0])  # names the fix

    def test_subdomain_is_not_first_party(self):
        ws = _WS(origin="https://sub.myapp.zolo.media", host="myapp.zolo.media")
        self.assertFalse(self._auth().validate_origin(ws))

    def test_ipv6_bracket_host_allowed(self):
        ws = _WS(origin="http://[::1]:8080", host="[::1]:8865")
        self.assertTrue(self._auth().validate_origin(ws))

    def test_localhost_default_still_allowed(self):
        ws = _WS(origin="http://localhost:8080", host="somewhere.else:8865")
        self.assertTrue(self._auth().validate_origin(ws))

    def test_explicit_allowlist_entry_still_works(self):
        ws = _WS(origin="https://embedder.example", host="myapp.zolo.media")
        self.assertTrue(self._auth(["https://embedder.example"]).validate_origin(ws))

    def test_no_origin_header_allowed(self):
        ws = _WS(origin=None, host="myapp.zolo.media")
        self.assertTrue(self._auth().validate_origin(ws))

    def test_hostname_compare_case_insensitive(self):
        ws = _WS(origin="https://MyApp.Zolo.Media", host="myapp.zolo.media")
        self.assertTrue(self._auth().validate_origin(ws))


if __name__ == "__main__":
    unittest.main()
