# tests/test_zvar_cookie_writethrough.py
"""zOS#94 wiring — the zVar write SSOT must write-through to the zsid store.

Exercises the REAL CommandLauncher._handle_zvar (not a re-implementation) with
a stub session carrying _zsid, and asserts the vars land in the cookie-keyed
session store so a later HTTP request can rehydrate them. Also pins the zCLI
no-op (no _zsid → no store write).
"""
# pylint: disable=protected-access
import logging
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from zOS.L1_Foundation.a_zConfig.zConfig_modules.session import session_cookie as sc
from zOS.L2_Handling.g_zDispatch.dispatch_modules.dispatch_launcher import CommandLauncher


class FakeStore:
    def __init__(self):
        self.blobs = {}

    def get(self, sid):
        return self.blobs.get(sid)

    def set(self, sid, blob):
        self.blobs[sid] = blob


def _launcher(session):
    launcher = CommandLauncher.__new__(CommandLauncher)  # skip heavy __init__
    log = logging.getLogger("test_zvar_writethrough")
    launcher.zos = SimpleNamespace(session=session, logger=log)
    launcher.logger = SimpleNamespace(framework=log)
    return launcher


class TestZVarWriteThrough(unittest.TestCase):
    def test_ws_unit_with_zsid_persists_vars(self):
        store = FakeStore()
        session = {"_zsid": "sidX", "zVars": {}}
        with patch.object(sc, "_store", return_value=store):
            _launcher(session)._handle_zvar({"zVar": {"venture": "acme", "quarter": "Q3"}}, None)
        self.assertEqual(session["zVars"], {"venture": "acme", "quarter": "Q3"})
        self.assertEqual(store.blobs.get("sidX", {}).get("zVars"),
                         {"venture": "acme", "quarter": "Q3"})

    def test_cli_session_without_zsid_is_a_noop_on_store(self):
        store = FakeStore()
        session = {"zVars": {}}
        with patch.object(sc, "_store", return_value=store):
            _launcher(session)._handle_zvar({"zVar": {"venture": "acme"}}, None)
        self.assertEqual(session["zVars"], {"venture": "acme"})
        self.assertEqual(store.blobs, {})


if __name__ == "__main__":
    unittest.main()
