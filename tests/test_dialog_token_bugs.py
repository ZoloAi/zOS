# zOS/tests/test_dialog_token_bugs.py
"""Regression tests for the zDialog token-resolution bug family.

zOS#57 — options: %token shipped as a literal string (client forEach crash)
zOS#60 — unpicked optional select stored the literal 'zConv.<field>'
zOS#88 — default: %col over a NULL column rendered the raw token in the input
zOS#92 — bool interpolated into a field attr arrived as the truthy string "False"

One root: the render-string pass str()-flattens scalars and keeps miss/None/
container as the literal token — right for prose, wrong for STRUCTURAL field
properties. These tests pin the structural seams added for 1.7.3.
"""
# pylint: disable=protected-access

import logging
import unittest

from zOS.L3_Abstraction.n_zLoom.zLoom_modules.token_resolver import (
    LOOP_FRAME_KEY,
    resolve_whole_token,
)
from zOS.L3_Abstraction.n_zLoom.zLoom import zLoom
from zOS.L2_Handling.j_zDialog.zDialog import zDialog
from zOS.L2_Handling.j_zDialog.dialog_modules.dialog_context import inject_placeholders
from zOS.L2_Handling.e_zDisplay.zDisplay_modules.system.system_event_dialog import DialogEvents

_LOGGER = logging.getLogger("test_dialog_token_bugs")


class _FakeZos:
    """Minimal zos stand-in: token resolution only needs .session (+ .logger)."""

    def __init__(self, session=None):
        self.session = session if session is not None else {}
        self.logger = _LOGGER


class TestResolveWholeToken(unittest.TestCase):
    """The new type-preserving whole-value primitive."""

    def test_whole_token_list_survives(self):
        zos = _FakeZos({"zVars": {"names": ["a", "b"]}})
        is_whole, raw = resolve_whole_token("%names", zos)
        self.assertTrue(is_whole)
        self.assertEqual(raw, ["a", "b"])

    def test_whole_token_bool_false_survives(self):
        zos = _FakeZos({"zVars": {"locked": False}})
        is_whole, raw = resolve_whole_token("%locked", zos)
        self.assertTrue(is_whole)
        self.assertIs(raw, False)

    def test_embedded_token_is_not_whole(self):
        zos = _FakeZos({"zVars": {"n": 1}})
        is_whole, _ = resolve_whole_token("count is %n items", zos)
        self.assertFalse(is_whole)

    def test_non_string_is_not_whole(self):
        is_whole, _ = resolve_whole_token(42, _FakeZos())
        self.assertFalse(is_whole)

    def test_miss_is_whole_with_none(self):
        is_whole, raw = resolve_whole_token("%item.founded_year", _FakeZos())
        self.assertTrue(is_whole)
        self.assertIsNone(raw)

    def test_data_namespace_from_context(self):
        zos = _FakeZos()
        ctx = {"_resolved_data": {"tags": ["x", "y"]}}
        is_whole, raw = resolve_whole_token("%data.tags", zos, ctx)
        self.assertTrue(is_whole)
        self.assertEqual(raw, ["x", "y"])


class TestLoopBakeNativeTypes(unittest.TestCase):
    """zOS#92/#57 at the bake site: _resolve_item_tokens keeps native types."""

    def _loom(self, session=None):
        return zLoom(_FakeZos(session))

    def _ctx(self, row):
        return {LOOP_FRAME_KEY: [row]}

    def test_whole_item_bool_bakes_native(self):
        loom = self._loom()
        node = {"readonly": "%item.target_locked"}
        out = loom._resolve_item_tokens(node, self._ctx({"target_locked": False}))
        self.assertIs(out["readonly"], False)

    def test_whole_item_list_bakes_native(self):
        loom = self._loom()
        node = {"options": "%item.tags"}
        out = loom._resolve_item_tokens(node, self._ctx({"tags": ["a", "b"]}))
        self.assertEqual(out["options"], ["a", "b"])

    def test_whole_item_string_still_string(self):
        loom = self._loom()
        node = {"default": "%item.name"}
        out = loom._resolve_item_tokens(node, self._ctx({"name": "Ada"}))
        self.assertEqual(out["default"], "Ada")

    def test_embedded_token_still_interpolates(self):
        loom = self._loom()
        node = {"label": "Hello %item.name!"}
        out = loom._resolve_item_tokens(node, self._ctx({"name": "Ada"}))
        self.assertEqual(out["label"], "Hello Ada!")

    def test_miss_keeps_literal(self):
        loom = self._loom()
        node = {"default": "%item.founded_year"}
        out = loom._resolve_item_tokens(node, self._ctx({"name": "Ada"}))
        self.assertEqual(out["default"], "%item.founded_year")


class TestDialogFieldTokenPass(unittest.TestCase):
    """zOS#57/#88 at the dialog seam: _resolve_field_tokens."""

    def _dialog(self, session=None):
        dlg = object.__new__(zDialog)
        zcli = _FakeZos(session)
        zcli.zloom = zLoom(zcli)
        dlg.zcli = zcli
        dlg.logger = _LOGGER
        return dlg

    def test_options_token_resolves_to_native_list(self):
        dlg = self._dialog({"_current_block_data": {"item_names": ["Chair", "Desk"]}})
        fields = [{"name": "item", "type": "select", "options": "%data.item_names"}]
        out = dlg._resolve_field_tokens(fields)
        self.assertEqual(out[0]["options"], ["Chair", "Desk"])

    def test_options_miss_becomes_empty_list(self):
        dlg = self._dialog()
        fields = [{"name": "item", "type": "select", "options": "%data.item_names"}]
        out = dlg._resolve_field_tokens(fields)
        self.assertEqual(out[0]["options"], [])

    def test_default_miss_becomes_empty_string(self):
        dlg = self._dialog()
        fields = [{"name": "year", "default": "%item.founded_year"}]
        out = dlg._resolve_field_tokens(fields)
        self.assertEqual(out[0]["default"], "")

    def test_boolish_miss_drops_key(self):
        dlg = self._dialog()
        fields = [{"name": "x", "readonly": "%target_locked"}]
        out = dlg._resolve_field_tokens(fields)
        self.assertNotIn("readonly", out[0])

    def test_boolish_false_survives_native(self):
        dlg = self._dialog({"zVars": {"target_locked": False}})
        fields = [{"name": "x", "readonly": "%target_locked"}]
        out = dlg._resolve_field_tokens(fields)
        self.assertIs(out[0]["readonly"], False)

    def test_embedded_and_plain_values_untouched(self):
        dlg = self._dialog()
        fields = [{"name": "x", "placeholder": "e.g. 100% done", "default": "static"},
                  "bare_field"]
        out = dlg._resolve_field_tokens(fields)
        self.assertEqual(out[0]["placeholder"], "e.g. 100% done")
        self.assertEqual(out[0]["default"], "static")
        self.assertEqual(out[1], "bare_field")


class TestZConvMissingFieldNeverLeaks(unittest.TestCase):
    """zOS#60: a missing/None zConv field substitutes EMPTY, never the literal."""

    def test_plugin_host_missing_field_substitutes_empty_json(self):
        ctx = {"zConv": {"name": "Ada"}}
        host = '&.plugin.save(zConv.name, zConv.layer)'
        out = inject_placeholders(host, ctx, _LOGGER)
        self.assertNotIn("zConv.layer", out)
        self.assertEqual(out, '&.plugin.save("Ada", "")')

    def test_legacy_host_missing_field_substitutes_empty_quotes(self):
        ctx = {"zConv": {"user_id": 42}}
        host = "WHERE id = zConv.user_id AND layer = zConv.layer"
        out = inject_placeholders(host, ctx, _LOGGER)
        self.assertNotIn("zConv.layer", out)
        self.assertEqual(out, "WHERE id = 42 AND layer = ''")

    def test_whole_value_missing_field_is_none(self):
        ctx = {"zConv": {}}
        self.assertIsNone(inject_placeholders("zConv.layer", ctx, _LOGGER))


class TestBoolishAttrCoercion(unittest.TestCase):
    """zOS#92 belt: falsy bool-ish attrs never ship truthy."""

    def _events(self):
        return object.__new__(DialogEvents)

    def test_string_false_dropped(self):
        kwargs = self._events()._build_input_kwargs({"readonly": "False"}, "text")
        self.assertNotIn("readonly", kwargs)

    def test_native_false_dropped(self):
        kwargs = self._events()._build_input_kwargs({"readonly": False}, "text")
        self.assertNotIn("readonly", kwargs)

    def test_truthy_string_normalizes_to_true(self):
        kwargs = self._events()._build_input_kwargs({"readonly": "true"}, "text")
        self.assertIs(kwargs["readonly"], True)

    def test_non_boolish_attrs_pass_through(self):
        kwargs = self._events()._build_input_kwargs({"placeholder": "hi"}, "text")
        self.assertEqual(kwargs["placeholder"], "hi")

    def test_gui_ship_drops_falsy_and_normalizes_truthy(self):
        from zOS.L2_Handling.e_zDisplay.zDisplay_modules.io.display_primitives import (
            zPrimitives,
        )
        prims = object.__new__(zPrimitives)
        data = {"fields": [
            {"zConv": "a", "type": "text", "readonly": "False"},
            {"zConv": "b", "type": "text", "disabled": "true"},
        ]}
        out = prims._resolve_dialog_field_rules(data)
        self.assertNotIn("readonly", out["fields"][0])
        self.assertIs(out["fields"][1]["disabled"], True)


if __name__ == "__main__":
    unittest.main()
