# tests/test_zloom_ref_diagnostics.py
"""zOS#93 — Style-B zLoom ref misses must be LOUD and actionable.

A `zLoom:` route field (or zMeta.zSpool entry) carrying a full zPath ref that
fails to resolve used to fail silently (early return, no log line) — a zLoom
route gated on it 404'd every request with zero diagnostics. These tests pin
the three miss shapes: no zUI segment, ref stops at the file (missing spool
tail), and a wrong spool name (must list what IS in the file).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from L3_Abstraction.n_zLoom.zLoom_modules.binding_ops import BindingOps


class _Log:
    def __init__(self):
        self.warnings = []

    def warning(self, msg, *a):
        self.warnings.append(msg % a if a else msg)

    def debug(self, *a, **k):
        pass

    def error(self, msg, *a):
        self.warnings.append(msg % a if a else msg)


class _Logger:
    def __init__(self):
        self.framework = _Log()
        self.session_framework = _Log()


class _Loader:
    def __init__(self, files):
        self.files = files

    def handle_absolute_path(self, fpath):
        return self.files.get(fpath)


class _Zos:
    def __init__(self, zspace, files):
        self.session = {"zSpace": zspace}
        self.logger = _Logger()
        self.loader = _Loader(files)


class _Binding(BindingOps):
    def __init__(self, zspace, files):
        self.zos = _Zos(zspace, files)


class TestStyleBRefDiagnostics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        spool_dir = os.path.join(self.tmp, "zLoom", "spools")
        os.makedirs(spool_dir)
        self.fpath = os.path.join(spool_dir, "zUI.Report.zolo")
        with open(self.fpath, "w", encoding="utf-8") as f:
            f.write("by_id:\n    model: x\n")
        self.ops = _Binding(self.tmp, {
            self.fpath: {"by_id": {"model": "x"}, "zMeta": {}},
        })

    def _warnings(self):
        return self.ops.zos.logger.session_framework.warnings

    def test_file_level_ref_warns_and_returns_none(self):
        # The exact miss from the field report: ref stops at the spool FILE.
        result = self.ops._resolve_zloom_zpath("@.zLoom.spools.zUI.Report")
        self.assertIsNone(result)
        joined = "\n".join(self._warnings())
        self.assertIn("spool FILE", joined)
        self.assertIn("@.zLoom.spools.zUI.Report.<spool>", joined)

    def test_missing_zui_segment_warns(self):
        result = self.ops._resolve_zloom_zpath("@.zLoom.spools.Report.by_id")
        self.assertIsNone(result)
        self.assertIn("no zUI.<file> segment", "\n".join(self._warnings()))

    def test_wrong_spool_name_lists_available(self):
        result = self.ops._resolve_zloom_zpath("@.zLoom.spools.zUI.Report.by_slug")
        self.assertIsNone(result)
        joined = "\n".join(self._warnings())
        self.assertIn("no spool 'by_slug'", joined)
        self.assertIn("by_id", joined)

    def test_good_ref_resolves_silently(self):
        result = self.ops._resolve_zloom_zpath("@.zLoom.spools.zUI.Report.by_id")
        self.assertEqual(result, ("by_id", {"model": "x"}))
        self.assertEqual(self._warnings(), [])

    def test_unknown_alias_lists_registry(self):
        binding = self.ops.build_binding_block({"zMeta": {"zSpool": ["nope"]}})
        self.assertEqual(binding, {})
        joined = "\n".join(self._warnings())
        self.assertIn("Unknown spool 'nope'", joined)
        self.assertIn("by_id", joined)


if __name__ == "__main__":
    unittest.main()
