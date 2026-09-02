# zOS/tests/test_zapi_error_surfacing.py
"""zOS#90 — a raised plugin exception surfaces its REAL type + message.

Before the fix the @zfunc wrapper contained any unhandled raise as the bare
``"error"`` sentinel and ``ZResult.coerce`` minted the actively-misleading
500 "Handler returned 'error'" — the handler didn't return, it RAISED, and
the message sent authors auditing return values. Now the wrapper stashes the
exception identity on the Invocation (transport adapters read it back), and
an ``"error: <detail>"`` return string keeps its sentence as a failure.
"""

import unittest

from zos_plugin import zfunc, ZResult, Invocation, set_env, reset_env


class TestWrapperStashesException(unittest.TestCase):
    """An unhandled raise still returns the sentinel — but records the truth."""

    def _run(self, fn, **kwargs):
        inv = Invocation(zos=None, params=dict(kwargs))
        token = set_env(inv)
        try:
            raw = fn(**kwargs)
        finally:
            reset_env(token)
        return raw, inv

    def test_raise_keeps_sentinel_and_stashes_identity(self):
        @zfunc
        def boom():
            raise TypeError("select() got an unexpected keyword argument 'order_by'")

        raw, inv = self._run(boom)
        self.assertEqual(raw, "error")
        exc = inv.meta.get("unhandled_exception")
        self.assertIsNotNone(exc)
        self.assertEqual(exc["type"], "TypeError")
        self.assertIn("order_by", exc["error"])
        self.assertIn("boom", exc["handler"])

    def test_positional_arg_mismatch_is_stashed_too(self):
        # The field-report edge: a POST handler declaring positional args —
        # zAPI fields arrive via injected params, so the CALL raises TypeError.
        @zfunc
        def create(title, body):  # pylint: disable=unused-argument
            return {"created": True}

        raw, inv = self._run(create)
        self.assertEqual(raw, "error")
        exc = inv.meta.get("unhandled_exception")
        self.assertEqual(exc["type"], "TypeError")
        self.assertIn("positional", exc["error"])

    def test_clean_return_leaves_no_stash(self):
        @zfunc
        def ok():
            return {"pong": True}

        raw, inv = self._run(ok)
        self.assertEqual(raw, {"pong": True})
        self.assertNotIn("unhandled_exception", inv.meta)


class TestCoerceErrorPrefix(unittest.TestCase):
    """An 'error: <detail>' string is a FAILURE that keeps its sentence."""

    def test_error_prefix_string_is_failure_with_detail(self):
        zr = ZResult.coerce("error: title is required")
        self.assertFalse(zr.ok)
        self.assertEqual(zr.error, "title is required")
        self.assertEqual(zr.status, 500)

    def test_bare_sentinel_unchanged(self):
        zr = ZResult.coerce("error")
        self.assertFalse(zr.ok)
        self.assertEqual(zr.error, "Handler returned 'error'")

    def test_plain_message_string_still_success(self):
        zr = ZResult.coerce("Saved 3 rows")
        self.assertTrue(zr.ok)
        self.assertEqual(zr.message, "Saved 3 rows")

    def test_prose_containing_error_word_not_hijacked(self):
        zr = ZResult.coerce("No errors found in the audit")
        self.assertTrue(zr.ok)


if __name__ == "__main__":
    unittest.main()
