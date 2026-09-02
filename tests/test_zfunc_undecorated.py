# zOS/tests/test_zfunc_undecorated.py
"""zOS#91 — the @zfunc decorator's absence must not fail silent.

Two shapes from the field report:
1. An undecorated handler's ``raise ZAbort(..., status=404)`` fell through the
   executor's generic wrap into a ValueError — the structured result (and its
   4xx) became a bare 500. Now the executor honors ZAbort regardless of
   decoration.
2. A refactor landed @zfunc on the helper ABOVE the intended function — the
   undecorated function dispatched, "succeeded", wrote nothing, zero evidence.
   Now the resolver warns loudly (once per function) at dispatch.
"""

import unittest

from zos_plugin import zfunc, ZAbort, ZResult
from zOS.L2_Handling.i_zFunc.zFunc_modules.plugin_executor import execute_plugin_function
from zOS.L2_Handling.i_zFunc.zFunc_modules import plugin_resolver


class _Log:
    def __init__(self):
        self.warnings = []

    def warning(self, msg):
        self.warnings.append(msg)

    def debug(self, msg):
        pass

    def error(self, msg):
        pass


class _Logger:
    def __init__(self):
        self.session_framework = _Log()
        self.framework = _Log()

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


class _Zos:
    def __init__(self):
        self.logger = _Logger()


class TestZAbortHonoredUndecorated(unittest.TestCase):
    """Executor returns the abort's ZResult even without @zfunc."""

    def test_undecorated_zabort_keeps_status(self):
        def handler():
            raise ZAbort("report not found", status=404)

        result = execute_plugin_function(handler, [], {}, "&.rep.get()", _Zos())
        self.assertIsInstance(result, ZResult)
        self.assertFalse(result.ok)
        self.assertEqual(result.status, 404)
        self.assertEqual(result.error, "report not found")

    def test_decorated_zabort_identical_shape(self):
        @zfunc
        def handler():
            raise ZAbort("report not found", status=404)

        result = execute_plugin_function(handler, [], {}, "&.rep.get()", _Zos())
        self.assertIsInstance(result, ZResult)
        self.assertEqual(result.status, 404)

    def test_other_exceptions_still_wrap(self):
        def handler():
            raise RuntimeError("boom")

        with self.assertRaises(ValueError):
            execute_plugin_function(handler, [], {}, "&.rep.get()", _Zos())


class TestUndecoratedDispatchWarns(unittest.TestCase):
    """The resolver says it loudly — once — when the target lacks @zfunc."""

    def setUp(self):
        plugin_resolver._WARNED_UNDECORATED.clear()  # pylint: disable=protected-access
        self.zos = _Zos()

    def test_undecorated_py_warns_once(self):
        def save_report():
            pass

        plugin_resolver.warn_if_undecorated(save_report, "/app/plugins/rep.py", "save_report", self.zos)
        plugin_resolver.warn_if_undecorated(save_report, "/app/plugins/rep.py", "save_report", self.zos)
        warnings = self.zos.logger.session_framework.warnings
        self.assertEqual(len(warnings), 1)
        self.assertIn("save_report", warnings[0])
        self.assertIn("NOT @zfunc-decorated", warnings[0])

    def test_decorated_py_silent(self):
        @zfunc
        def save_report():
            pass

        plugin_resolver.warn_if_undecorated(save_report, "/app/plugins/rep.py", "save_report", self.zos)
        self.assertEqual(self.zos.logger.session_framework.warnings, [])

    def test_js_target_silent(self):
        def js_shim():
            pass

        plugin_resolver.warn_if_undecorated(js_shim, "/app/plugins/fx.js", "fx", self.zos)
        self.assertEqual(self.zos.logger.session_framework.warnings, [])


if __name__ == "__main__":
    unittest.main()
