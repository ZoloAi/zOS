# tests/test_session_cookie_vars.py
"""zOS#94 — cookie-bound zVars bridge: WS-set session vars must be readable
by a plain HTTP request carrying the same zsid cookie.

Pins the new session_cookie surface: persist_vars/load_vars round-trip,
merge-preserving blob writes (identity + vars never clobber each other),
restore merge semantics (stored vars win over boot defaults), and that an
empty-dict persist propagates a clear.
"""
import unittest
from unittest.mock import patch

from zOS.L1_Foundation.a_zConfig.zConfig_modules.session import session_cookie as sc


class FakeStore:
    def __init__(self):
        self.blobs = {}

    def get(self, sid):
        return self.blobs.get(sid)

    def set(self, sid, blob):
        self.blobs[sid] = blob

    def delete(self, sid):
        self.blobs.pop(sid, None)


class TestVarsBridge(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self._patch = patch.object(sc, "_store", return_value=self.store)
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_persist_and_load_roundtrip(self):
        session = {"zVars": {"venture": "acme", "quarter": "Q3"}}
        sc.persist_vars(zos=None, sid="sid1", session=session)
        self.assertEqual(sc.load_vars(None, "sid1"), {"venture": "acme", "quarter": "Q3"})

    def test_identity_and_vars_never_clobber_each_other(self):
        sc.persist_identity(None, "sid1", {"zVisitor": {"authenticated": True, "role": "zAdmin"}})
        sc.persist_vars(None, "sid1", {"zVars": {"venture": "acme"}})
        self.assertEqual(sc.load_identity(None, "sid1"), {"authenticated": True, "role": "zAdmin"})
        self.assertEqual(sc.load_vars(None, "sid1"), {"venture": "acme"})
        # And the reverse write order.
        sc.persist_vars(None, "sid2", {"zVars": {"q": "Q3"}})
        sc.persist_identity(None, "sid2", {"zVisitor": {"authenticated": True}})
        self.assertEqual(sc.load_vars(None, "sid2"), {"q": "Q3"})
        self.assertEqual(sc.load_identity(None, "sid2"), {"authenticated": True})

    def test_restore_merges_with_stored_winning(self):
        unit = {"zVars": {"theme": "dark", "venture": "boot-default"}}
        applied = sc.restore_vars_into_unit(unit, {"venture": "acme"})
        self.assertTrue(applied)
        self.assertEqual(unit["zVars"], {"theme": "dark", "venture": "acme"})

    def test_restore_none_is_noop(self):
        unit = {"zVars": {"theme": "dark"}}
        self.assertFalse(sc.restore_vars_into_unit(unit, None))
        self.assertEqual(unit["zVars"], {"theme": "dark"})

    def test_empty_persist_propagates_a_clear(self):
        sc.persist_vars(None, "sid1", {"zVars": {"venture": "acme"}})
        sc.persist_vars(None, "sid1", {"zVars": {}})
        self.assertEqual(sc.load_vars(None, "sid1"), {})

    def test_deepcopy_isolation(self):
        live = {"venture": "acme"}
        sc.persist_vars(None, "sid1", {"zVars": live})
        live["venture"] = "mutated-later"
        self.assertEqual(sc.load_vars(None, "sid1"), {"venture": "acme"})


if __name__ == "__main__":
    unittest.main()
