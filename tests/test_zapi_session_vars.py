# zOS/tests/test_zapi_session_vars.py
"""Regression tests for the zAPI zVars write-through (zOS#21).

Entry restores stored zVars (zOS#94); the WS path persists at the zVar-write
SSOT. The zAPI seam persists AFTER the handler, change-gated: a read-only hit
writes nothing, a mutation (including a clear) propagates under the zsid.
"""

import unittest
from unittest import mock

from zOS.L4_Orchestration.r_zServer.zServer_modules.routing import zapi_handler


class _Zos:
    def __init__(self, session):
        self.session = session


class TestSnapshotSessionVars(unittest.TestCase):

    def test_snapshot_is_deep_copy(self):
        zos = _Zos({"zVars": {"Target": "D5"}})
        snap = zapi_handler._snapshot_session_vars(zos)
        zos.session["zVars"]["Target"] = "mutated"
        self.assertEqual(snap, {"Target": "D5"})

    def test_absent_vars_snapshot_none(self):
        self.assertIsNone(zapi_handler._snapshot_session_vars(_Zos({})))


class TestPersistSessionVars(unittest.TestCase):

    def _persist_calls(self, session, vars_before):
        zos = _Zos(session)
        with mock.patch(
            "zOS.L1_Foundation.a_zConfig.zConfig_modules.session.session_cookie.persist_vars"
        ) as persist:
            zapi_handler._persist_session_vars(zos, vars_before)
        return persist

    def test_handler_write_persists(self):
        persist = self._persist_calls(
            {"_zsid": "sid1", "zVars": {"Target": "D5"}}, vars_before=None)
        persist.assert_called_once()

    def test_unchanged_vars_do_not_persist(self):
        persist = self._persist_calls(
            {"_zsid": "sid1", "zVars": {"Target": "D5"}},
            vars_before={"Target": "D5"})
        persist.assert_not_called()

    def test_clear_to_empty_persists(self):
        persist = self._persist_calls(
            {"_zsid": "sid1", "zVars": {}}, vars_before={"Target": "D5"})
        persist.assert_called_once()

    def test_no_zsid_never_persists(self):
        persist = self._persist_calls(
            {"zVars": {"Target": "D5"}}, vars_before=None)
        persist.assert_not_called()


if __name__ == "__main__":
    unittest.main()
