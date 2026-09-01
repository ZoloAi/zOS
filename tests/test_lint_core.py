# pylint: disable=protected-access
"""
Unit tests for the z lint / strict boot fault checker (zOS#84).

Each fault class gets a red case (fault detected) and a green case (supported
grammar stays silent). The onSuccess verb set is pinned against the dispatch
constants SSOT.
"""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

from zSys.cli.lint_core import (  # noqa: E402
    _ONSUCCESS_VERBS,
    _check_onsuccess,
    _check_zclass,
    lint_app,
)
from zSys.cli.zspark_command import _run_strict_lint  # noqa: E402


def _app(tmp: str, files: dict) -> Path:
    root = Path(tmp)
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


CLEAN_UI = """Main:
    zH1:
        label: hello
    zText: welcome
    zText: again
"""


class TestParseFaults(unittest.TestCase):
    def test_clean_app_no_faults(self):
        with TemporaryDirectory() as tmp:
            root = _app(tmp, {"zViews/zUI.app.zolo": CLEAN_UI})
            self.assertEqual(lint_app(root), [])

    def test_duplicate_named_block_faults(self):
        src = "Main:\n    Card:\n        zText: one\n    Card:\n        zText: two\n"
        with TemporaryDirectory() as tmp:
            root = _app(tmp, {"zViews/zUI.app.zolo": src})
            faults = lint_app(root)
            self.assertEqual(len(faults), 1)
            self.assertEqual(faults[0].code, "parse")
            self.assertIn("Duplicate key 'Card'", faults[0].message)

    def test_unclosed_comment_faults(self):
        src = "Main:\n    #> forgot to close\n    zText: hello\n"
        with TemporaryDirectory() as tmp:
            root = _app(tmp, {"zViews/zUI.app.zolo": src})
            faults = lint_app(root)
            self.assertTrue(any(
                f.code == "parse" and "Unterminated" in f.message for f in faults
            ))

    def test_shorthand_repeats_are_silent(self):
        src = "Main:\n    zText: one\n    zText: two\n    zH2:\n        label: a\n    zH2:\n        label: b\n"
        with TemporaryDirectory() as tmp:
            root = _app(tmp, {"zViews/zUI.app.zolo": src})
            self.assertEqual(lint_app(root), [])

    def test_hosted_and_zversions_excluded(self):
        bad = "Main:\n    Card:\n        zText: a\n    Card:\n        zText: b\n"
        with TemporaryDirectory() as tmp:
            root = _app(tmp, {
                "zViews/zUI.app.zolo": CLEAN_UI,
                "_hosted/guest/zViews/zUI.guest.zolo": bad,
                "zVersions/commits/x/c1/snapshot/zUI.old.zolo": bad,
            })
            self.assertEqual(lint_app(root), [])


class TestShuttleFaults(unittest.TestCase):
    PATTERN = "card:\n    zText: %title\n"

    def test_shuttle_valid_is_silent(self):
        ui = (
            "zMeta:\n    zSpool: [products]\n\n"
            "Main:\n    Grid:\n        zShuttle:\n"
            "            zSpool: products\n            zPattern: card\n"
        )
        with TemporaryDirectory() as tmp:
            root = _app(tmp, {
                "zViews/zUI.app.zolo": ui,
                "zLoom/patterns/card.zolo": self.PATTERN,
            })
            self.assertEqual(lint_app(root), [])

    def test_shuttle_unknown_pattern_faults(self):
        ui = (
            "zMeta:\n    zSpool: [products]\n\n"
            "Main:\n    Grid:\n        zShuttle:\n"
            "            zSpool: products\n            zPattern: ghost\n"
        )
        with TemporaryDirectory() as tmp:
            root = _app(tmp, {"zViews/zUI.app.zolo": ui})
            faults = lint_app(root)
            self.assertTrue(any(
                f.code == "shuttle" and "'%ghost'" in f.message for f in faults
            ))

    def test_shuttle_undeclared_reel_faults(self):
        ui = (
            "Main:\n    Grid:\n        zShuttle:\n"
            "            zSpool: products\n            zPattern: card\n"
        )
        with TemporaryDirectory() as tmp:
            root = _app(tmp, {
                "zViews/zUI.app.zolo": ui,
                "zLoom/patterns/card.zolo": self.PATTERN,
            })
            faults = lint_app(root)
            self.assertTrue(any(
                f.code == "shuttle" and "reel 'products'" in f.message for f in faults
            ))


class TestPatternInvocationFaults(unittest.TestCase):
    def test_unknown_invocation_faults(self):
        ui = "Main:\n    %ghostCard:\n        title: hi\n"
        with TemporaryDirectory() as tmp:
            root = _app(tmp, {"zViews/zUI.app.zolo": ui})
            faults = lint_app(root)
            self.assertTrue(any(f.code == "pattern" for f in faults))

    def test_known_invocation_silent(self):
        ui = "Main:\n    %card:\n        title: hi\n"
        with TemporaryDirectory() as tmp:
            root = _app(tmp, {
                "zViews/zUI.app.zolo": ui,
                "zLoom/patterns/card.zolo": "card:\n    zText: %title\n",
            })
            self.assertEqual(lint_app(root), [])

    def test_dotted_percent_keys_are_gate_ir_not_invocations(self):
        ui = "Main:\n    zGate:\n        %item.in_stock: zSet\n"
        with TemporaryDirectory() as tmp:
            root = _app(tmp, {"zViews/zUI.app.zolo": ui})
            self.assertEqual([f for f in lint_app(root) if f.code == "pattern"], [])


class TestZClassFaults(unittest.TestCase):
    def test_data_token_faults(self):
        faults = []
        _check_zclass("f.zolo", "hero-%data.theme", faults)
        self.assertEqual(len(faults), 1)
        self.assertEqual(faults[0].code, "zclass-token")

    def test_bare_slot_faults_outside_patterns(self):
        faults = []
        _check_zclass("f.zolo", "card-%tone", faults)
        self.assertEqual(len(faults), 1)

    def test_item_token_is_loop_baked_and_silent(self):
        faults = []
        _check_zclass("f.zolo", "toggle-%item.done", faults)
        self.assertEqual(faults, [])

    def test_bare_slot_allowed_in_pattern_files(self):
        faults = []
        _check_zclass("zLoom/patterns/c.zolo", "card-%tone", faults, allow_bare_slots=True)
        self.assertEqual(faults, [])

    def test_plain_classes_silent(self):
        faults = []
        _check_zclass("f.zolo", ["ck-link", "hero big"], faults)
        self.assertEqual(faults, [])


class TestOnSuccessFaults(unittest.TestCase):
    def test_dict_with_known_verb_silent(self):
        faults = []
        _check_onsuccess("f.zolo", {"zLink": "@.zViews.zUI.app.Main"}, faults)
        self.assertEqual(faults, [])

    def test_call_string_with_known_verb_silent(self):
        faults = []
        _check_onsuccess("f.zolo", "zDelta($Main.Ledger)", faults)
        self.assertEqual(faults, [])

    def test_plugin_sigil_silent(self):
        faults = []
        _check_onsuccess("f.zolo", "&notify()", faults)
        self.assertEqual(faults, [])

    def test_unknown_verb_faults(self):
        faults = []
        _check_onsuccess("f.zolo", {"zTeleport": "x"}, faults)
        self.assertEqual(len(faults), 1)
        self.assertEqual(faults[0].code, "onsuccess")

    def test_unknown_call_string_faults(self):
        faults = []
        _check_onsuccess("f.zolo", "zTeleport($x)", faults)
        self.assertEqual(len(faults), 1)

    def test_verb_set_pinned_to_dispatch_constants(self):
        from zOS.L2_Handling.g_zDispatch.dispatch_modules import dispatch_constants
        declared = {
            getattr(dispatch_constants, name)
            for name in dir(dispatch_constants)
            if name.startswith("KEY_Z") and isinstance(getattr(dispatch_constants, name), str)
        }
        missing = _ONSUCCESS_VERBS - declared
        self.assertEqual(
            missing, set(),
            f"lint verb(s) {missing} not declared in dispatch_constants — "
            f"update _ONSUCCESS_VERBS to match the dispatch SSOT",
        )


class TestStrictGate(unittest.TestCase):
    BAD_UI = "Main:\n    Card:\n        zText: a\n    Card:\n        zText: b\n"

    def test_faults_refuse_by_default(self):
        with TemporaryDirectory() as tmp:
            root = _app(tmp, {"zViews/zUI.app.zolo": self.BAD_UI,
                              "zSpark.app.zolo": "zSpark:\n    zMode: zCLI\n"})
            exit_code = _run_strict_lint({}, root / "zSpark.app.zolo")
            self.assertEqual(exit_code, 1)

    def test_strict_false_boots_with_warnings(self):
        with TemporaryDirectory() as tmp:
            root = _app(tmp, {"zViews/zUI.app.zolo": self.BAD_UI,
                              "zSpark.app.zolo": "zSpark:\n    zMode: zCLI\n"})
            exit_code = _run_strict_lint({"strict": False}, root / "zSpark.app.zolo")
            self.assertEqual(exit_code, 0)

    def test_strict_false_string_form(self):
        with TemporaryDirectory() as tmp:
            root = _app(tmp, {"zViews/zUI.app.zolo": self.BAD_UI,
                              "zSpark.app.zolo": "zSpark:\n    zMode: zCLI\n"})
            exit_code = _run_strict_lint({"strict": "false"}, root / "zSpark.app.zolo")
            self.assertEqual(exit_code, 0)

    def test_clean_app_boots(self):
        with TemporaryDirectory() as tmp:
            root = _app(tmp, {"zViews/zUI.app.zolo": CLEAN_UI,
                              "zSpark.app.zolo": "zSpark:\n    zMode: zCLI\n"})
            exit_code = _run_strict_lint({}, root / "zSpark.app.zolo")
            self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
