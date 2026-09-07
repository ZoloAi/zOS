"""zOAuth pins (PROPOSAL.zOAuth.md) — the provider sign-in lane.

Covers the engine half (action_oauth) end to end with a faked provider via
the module's HTTP seam, plus the door's redirect discipline:

- start: refuses unconfigured providers; authorize URL carries the contract
  (client_id, redirect_uri, state, PKCE for Google); state is registered.
- callback: state is single-use, provider-bound, and zsid-bound; a provider
  decline is a coarse-code refusal.
- linking: ledger without the two oauth columns is refused with a clear log;
  a first sign-in creates the row (username from email local-part, LOCKED
  bcrypt password, role left to schema default) and stamps zVisitor; a
  second sign-in reuses the row.
- identity: google unverified email refused; facebook `id` normalizes to sub.
- next: same-origin path only.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from L2_Handling.f_zAuth.zAuth_modules.actions import action_oauth  # noqa: E402


# ── fakes ────────────────────────────────────────────────────────────────────

class _Logger:
    def __init__(self):
        self.lines = []

    def _log(self, level, msg):
        self.lines.append((level, msg))

    def info(self, msg, **kw): self._log("info", msg)
    def debug(self, msg, **kw): self._log("debug", msg)
    def warning(self, msg, **kw): self._log("warning", msg)
    def error(self, msg, **kw): self._log("error", msg)


class _Data:
    """Programmable ledger: select by (col tuple) → rows; insert records."""

    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.inserted = []
        self.loaded_schema = None

    def load_schema(self, schema):
        self.loaded_schema = schema

    def select(self, table, where=None):
        out = []
        for row in self.rows:
            if all(row.get(k) == v for k, v in (where or {}).items()):
                out.append(row)
        return out

    def insert(self, table, row):
        stored = dict(row)
        stored["id"] = len(self.rows) + 1
        self.rows.append(stored)
        self.inserted.append(stored)
        return type("Row", (), {"id": stored["id"]})()


class _Loader:
    def __init__(self, schema):
        self.schema = schema

    def handle(self, model=None, zPath=None):
        return self.schema


_SCHEMA = {
    "zMeta": {},
    "Users": {
        "id": {"type": "int", "pk": True},
        "username": {"type": "str"},
        "password": {"type": "str", "zHash": "bcrypt"},
        "role": {"type": "str", "default": "viewer"},
        "person": {"type": "str"},
        "oauth_provider": {"type": "str"},
        "oauth_subject": {"type": "str"},
    },
}

_SCHEMA_NO_OAUTH = {
    "zMeta": {},
    "Users": {
        "id": {"type": "int", "pk": True},
        "username": {"type": "str"},
        "password": {"type": "str", "zHash": "bcrypt"},
    },
}


class _Zos:
    def __init__(self, schema=_SCHEMA, rows=None, zsid="zsid-test"):
        self.logger = _Logger()
        self.session = {"_zsid": zsid}
        self.data = _Data(rows)
        self.loader = _Loader(schema)


def _fake_http(responses):
    """Return a _http_json stand-in that pops canned responses in order."""
    calls = []

    def fake(url, data=None, headers=None, timeout=10.0):
        calls.append({"url": url, "data": data, "headers": headers})
        return responses.pop(0) if responses else None
    fake.calls = calls
    return fake


class _ZOAuthCase(unittest.TestCase):
    """Env + state hygiene shared by every case."""

    def setUp(self):
        os.environ["ZOAUTH_GOOGLE_CLIENT_ID"] = "gid"
        os.environ["ZOAUTH_GOOGLE_SECRET"] = "gsecret"
        os.environ["ZOAUTH_FACEBOOK_CLIENT_ID"] = "fid"
        os.environ["ZOAUTH_FACEBOOK_SECRET"] = "fsecret"
        os.environ["ZAUTH_USER_MODEL"] = "@.models.zSchema.Users"
        action_oauth._states.clear()
        self._orig_http = action_oauth._http_json

    def tearDown(self):
        for key in ("ZOAUTH_GOOGLE_CLIENT_ID", "ZOAUTH_GOOGLE_SECRET",
                    "ZOAUTH_FACEBOOK_CLIENT_ID", "ZOAUTH_FACEBOOK_SECRET",
                    "ZAUTH_USER_MODEL"):
            os.environ.pop(key, None)
        action_oauth._states.clear()
        action_oauth._http_json = self._orig_http


REDIRECT = "http://localhost:9091/zauth/google/callback"


class TestStartHop(_ZOAuthCase):

    def test_unknown_provider_refused(self):
        self.assertIsNone(action_oauth.begin(_Zos(), "github", REDIRECT))

    def test_unconfigured_provider_refused(self):
        os.environ.pop("ZOAUTH_GOOGLE_SECRET")
        self.assertIsNone(action_oauth.begin(_Zos(), "google", REDIRECT))

    def test_authorize_url_contract_and_pkce(self):
        url = action_oauth.begin(_Zos(), "google", REDIRECT, next_path="/Settings")
        self.assertIsNotNone(url)
        self.assertIn("client_id=gid", url)
        self.assertIn("response_type=code", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("state=", url)
        # the state entry is registered, zsid-bound, and carries next + verifier
        self.assertEqual(len(action_oauth._states), 1)
        entry = list(action_oauth._states.values())[0]
        self.assertEqual(entry["next"], "/Settings")
        self.assertEqual(entry["zsid"], "zsid-test")
        self.assertIn("verifier", entry)

    def test_facebook_has_no_pkce(self):
        url = action_oauth.begin(_Zos(), "facebook",
                                 REDIRECT.replace("google", "facebook"))
        self.assertNotIn("code_challenge", url)

    def test_next_sanitized(self):
        for evil in ("https://evil.example", "//evil.example", "javascript:x", ""):
            self.assertEqual(action_oauth._sanitize_next(evil), "/")
        self.assertEqual(action_oauth._sanitize_next("/plan/x?tab=1"), "/plan/x?tab=1")


class TestCallbackStateDiscipline(_ZOAuthCase):

    def test_missing_or_unknown_state_refused(self):
        ok, code = action_oauth.complete(_Zos(), "google", {"code": "c"}, REDIRECT)
        self.assertFalse(ok)
        self.assertEqual(code, "state")
        ok, code = action_oauth.complete(
            _Zos(), "google", {"code": "c", "state": "forged"}, REDIRECT)
        self.assertFalse(ok)
        self.assertEqual(code, "state")

    def test_state_is_single_use(self):
        zos = _Zos()
        action_oauth.begin(zos, "google", REDIRECT)
        state = list(action_oauth._states.keys())[0]
        action_oauth._http_json = _fake_http([])  # exchange will fail — fine
        action_oauth.complete(zos, "google", {"code": "c", "state": state}, REDIRECT)
        ok, code = action_oauth.complete(
            zos, "google", {"code": "c", "state": state}, REDIRECT)
        self.assertFalse(ok)
        self.assertEqual(code, "state")

    def test_state_bound_to_zsid(self):
        starter = _Zos(zsid="browser-A")
        action_oauth.begin(starter, "google", REDIRECT)
        state = list(action_oauth._states.keys())[0]
        finisher = _Zos(zsid="browser-B")
        ok, code = action_oauth.complete(
            finisher, "google", {"code": "c", "state": state}, REDIRECT)
        self.assertFalse(ok)
        self.assertEqual(code, "state")

    def test_provider_decline_is_coarse(self):
        zos = _Zos()
        action_oauth.begin(zos, "google", REDIRECT)
        state = list(action_oauth._states.keys())[0]
        ok, code = action_oauth.complete(
            zos, "google", {"error": "access_denied", "state": state}, REDIRECT)
        self.assertFalse(ok)
        self.assertEqual(code, "declined")


class TestLinkingAndStamp(_ZOAuthCase):

    def _run_google_flow(self, zos, userinfo):
        action_oauth.begin(zos, "google", REDIRECT, next_path="/Settings")
        state = list(action_oauth._states.keys())[0]
        action_oauth._http_json = _fake_http([
            {"access_token": "tok-1"},   # token exchange
            userinfo,                    # userinfo
        ])
        return action_oauth.complete(
            zos, "google", {"code": "authcode", "state": state}, REDIRECT)

    def test_first_signin_creates_locked_row_and_stamps(self):
        zos = _Zos()
        ok, dest = self._run_google_flow(zos, {
            "sub": "g-123", "email": "ada@whitfield.dev",
            "email_verified": True, "name": "Ada Whitfield",
        })
        self.assertTrue(ok)
        self.assertEqual(dest, "/Settings")
        # row created: username from email local-part, linked, locked password
        self.assertEqual(len(zos.data.inserted), 1)
        row = zos.data.inserted[0]
        self.assertEqual(row["username"], "ada")
        self.assertEqual(row["oauth_provider"], "google")
        self.assertEqual(row["oauth_subject"], "g-123")
        self.assertTrue(row["password"].startswith("$2"))  # bcrypt, unguessable
        self.assertNotIn("role", row)  # least privilege: schema default decides
        # zVisitor stamped
        visitor = zos.session.get("zVisitor")
        self.assertIsNotNone(visitor)
        self.assertTrue(visitor.get("authenticated"))
        self.assertEqual(visitor.get("username"), "ada")

    def test_second_signin_reuses_row(self):
        existing = {"id": 7, "username": "ada", "role": "member",
                    "oauth_provider": "google", "oauth_subject": "g-123",
                    "password": "$2b$x"}
        zos = _Zos(rows=[existing])
        ok, _ = self._run_google_flow(zos, {
            "sub": "g-123", "email": "ada@whitfield.dev",
            "email_verified": True, "name": "Ada",
        })
        self.assertTrue(ok)
        self.assertEqual(zos.data.inserted, [])
        self.assertEqual(zos.session["zVisitor"].get("role"), "member")

    def test_ledger_without_oauth_columns_refused(self):
        zos = _Zos(schema=_SCHEMA_NO_OAUTH)
        ok, code = self._run_google_flow(zos, {
            "sub": "g-123", "email": "a@b.c", "email_verified": True,
        })
        self.assertFalse(ok)
        self.assertEqual(code, "ledger")
        self.assertTrue(any("lacks oauth_provider" in msg
                            for _lvl, msg in zos.logger.lines))

    def test_unverified_google_email_refused(self):
        zos = _Zos()
        ok, code = self._run_google_flow(zos, {
            "sub": "g-9", "email": "spoof@x.y", "email_verified": False,
        })
        self.assertFalse(ok)
        self.assertEqual(code, "identity")

    def test_username_collision_uniquified(self):
        taken = {"id": 1, "username": "ada", "oauth_provider": "facebook",
                 "oauth_subject": "f-1", "password": "$2b$x", "role": "viewer"}
        zos = _Zos(rows=[taken])
        ok, _ = self._run_google_flow(zos, {
            "sub": "g-2", "email": "ada@elsewhere.dev",
            "email_verified": True, "name": "Other Ada",
        })
        self.assertTrue(ok)
        self.assertEqual(zos.data.inserted[0]["username"], "ada.1")


class TestIdentityNormalization(_ZOAuthCase):

    def test_facebook_id_becomes_sub(self):
        action_oauth._http_json = _fake_http([
            {"id": "fb-42", "name": "Grace Wu", "email": "grace@wu.dev"},
        ])
        cfg = action_oauth.provider_config("facebook")
        info = action_oauth._fetch_identity("facebook", cfg, "tok", _Logger())
        self.assertEqual(info, {"sub": "fb-42", "name": "Grace Wu",
                                "email": "grace@wu.dev"})

    def test_token_travels_in_header_not_url(self):
        fake = _fake_http([{"sub": "g-1"}])
        action_oauth._http_json = fake
        cfg = action_oauth.provider_config("google")
        action_oauth._fetch_identity("google", cfg, "sekret-tok", _Logger())
        call = fake.calls[0]
        self.assertNotIn("sekret-tok", call["url"])
        self.assertEqual(call["headers"]["Authorization"], "Bearer sekret-tok")


class TestEndpointOverrides(_ZOAuthCase):

    def test_env_override_points_the_handshake_at_a_fake(self):
        os.environ["ZOAUTH_GOOGLE_AUTH_URL"] = "http://127.0.0.1:1/auth"
        try:
            url = action_oauth.begin(_Zos(), "google", REDIRECT)
            self.assertTrue(url.startswith("http://127.0.0.1:1/auth?"))
        finally:
            os.environ.pop("ZOAUTH_GOOGLE_AUTH_URL")


class TestZCloudProvider(_ZOAuthCase):
    """zolo's OWN provider — same lane, /zid/* contract, PKCE, verified email."""

    def test_inert_without_credentials(self):
        # setUp configures google+facebook only — zcloud must refuse like any
        # unconfigured provider (the landing's button stays 'soon' for free).
        self.assertFalse(action_oauth.is_configured("zcloud"))
        self.assertIsNone(action_oauth.begin(
            _Zos(), "zcloud", REDIRECT.replace("google", "zcloud")))

    def test_authorize_contract_pkce_and_zid_doors(self):
        os.environ["ZOAUTH_ZCLOUD_CLIENT_ID"] = "zc-id"
        os.environ["ZOAUTH_ZCLOUD_SECRET"] = "zc-secret"
        try:
            url = action_oauth.begin(
                _Zos(), "zcloud", REDIRECT.replace("google", "zcloud"))
            self.assertTrue(url.startswith("https://zolo.media/zid/authorize?"))
            self.assertIn("code_challenge_method=S256", url)
            self.assertIn("client_id=zc-id", url)
        finally:
            os.environ.pop("ZOAUTH_ZCLOUD_CLIENT_ID")
            os.environ.pop("ZOAUTH_ZCLOUD_SECRET")

    def test_unverified_zcloud_email_refused(self):
        # We hold our own provider to the rule we hold google to.
        action_oauth._http_json = _fake_http([
            {"sub": "zc-7", "email": "new@user.dev", "email_verified": False},
        ])
        cfg = action_oauth.provider_config("zcloud")
        info = action_oauth._fetch_identity("zcloud", cfg, "tok", _Logger())
        self.assertIsNone(info)


if __name__ == "__main__":
    unittest.main()
