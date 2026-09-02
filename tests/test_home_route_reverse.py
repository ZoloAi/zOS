# tests/test_home_route_reverse.py
"""zOS#66 — the implicit '/' anchor must carry the spark's file coordinates.

The auto-injected home route used to be a bare `{type: zWalker}` with no
zVaFile, so reverse_route could never match the HOME file — a zURL back to a
root-level home shipped the raw zPath to the browser (`/@/zViews/…` → 404).
The anchor is now injected as `type: zSpark` and normalized with the spark's
zVaFolder/zVaFile/zBlock, making home reverse-resolvable like any other page.

Also pins the zRaven structure-checker path fix: a multi-segment dotted
zVaFolder (@.zViews.Home) must resolve to zViews/Home/, not "zViews.Home/".
"""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

from L4_Orchestration.r_zServer.zServer_modules.core.route_manager import RouteManager


class _Log:
    def debug(self, *a, **k): pass
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass


class _Logger(_Log):
    def __init__(self):
        self.framework = _Log()
        self.session_framework = _Log()


class _Loader:
    def handle_absolute_path(self, fpath):
        return None


class _Zos:
    def __init__(self):
        self.spark = {
            "zVaFolder": "@.zViews",
            "zVaFile": "zUI.Home",
            "zBlock": "Home",
        }
        self.session = {}
        self.loader = _Loader()
        self.logger = _Logger()
        self.auth = None


class TestImplicitAnchorCarriesSparkIdentity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "zViews", "Sub"))
        Path(self.tmp, "zViews", "zUI.Home.zolo").write_text("Home:\n    zText: hi\n")
        Path(self.tmp, "zViews", "Sub", "zUI.Sub.zolo").write_text("Sub:\n    zText: hi\n")
        self.rm = RouteManager(self.tmp, _Zos(), _Logger())

    def test_injected_anchor_has_spark_coordinates(self):
        router, count, _ = self.rm._build_router([])
        self.assertIsNotNone(router)
        home = router.route_map["/"]
        self.assertEqual(home.get("zVaFile"), "zUI.Home")
        self.assertEqual(home.get("zVaFolder"), "@.zViews")
        self.assertEqual(home.get("zBlock"), "Home")
        self.assertEqual(home.get("type"), "zWalker")
        self.assertTrue(home.get("auto_discover_blocks"))

    def test_home_file_reverse_resolves_to_root(self):
        router, _, _ = self.rm._build_router([])
        url = router.reverse_route("zUI.Home", "Home", zVaFolder="@.zViews")
        self.assertEqual(url, "/")

    def test_subfolder_page_still_reverse_resolves(self):
        router, _, _ = self.rm._build_router([])
        url = router.reverse_route("zUI.Sub", "Sub", zVaFolder="@.zViews.Sub")
        self.assertEqual(url, "/Sub/Sub")


class TestValidatorDottedFolder(unittest.TestCase):
    def test_multi_segment_folder_is_found(self):
        from L4_Orchestration.s_zRaven.zRaven_modules.utils.validator import validate_structure

        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, "zViews", "Home"))
        Path(tmp, "zViews", "Home", "zUI.Home.zolo").write_text("Home:\n    zText: hi\n")
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                ok = validate_structure(
                    Path("zRaven.x.zolo"), {"Tests": {}},
                    "@.zViews.Home", "zUI.Home", "Home",
                )
            self.assertTrue(ok)
            self.assertNotIn("not found", buf.getvalue())
        finally:
            os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
