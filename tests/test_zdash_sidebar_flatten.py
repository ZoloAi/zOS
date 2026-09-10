# zOS/tests/test_zdash_sidebar_flatten.py
"""zDash sidebar %token flatten — splice live reels, keep static names."""

import logging
import unittest

from zOS.L2_Handling.e_zDisplay.zDisplay_modules.system.system_event_dashboard import (
    flatten_zdash_sidebar,
)

_LOGGER = logging.getLogger("test_zdash_sidebar_flatten")


class _FakeZos:
    def __init__(self, session=None):
        self.session = session if session is not None else {}
        self.logger = _LOGGER
        self.zloom = None


class TestFlattenZdashSidebar(unittest.TestCase):
    def test_static_names_stay(self):
        keys, _ = flatten_zdash_sidebar(["new-plan", "new-element"], _FakeZos())
        self.assertEqual(keys, ["new-plan", "new-element"])

    def test_empty_reel_splices_nothing(self):
        zos = _FakeZos({"_current_block_data": {"plan_selector": []}})
        keys, _ = flatten_zdash_sidebar(
            ["new-plan", "%data.plan_selector", "new-element"], zos
        )
        self.assertEqual(keys, ["new-plan", "new-element"])

    def test_rows_splice_as_names(self):
        zos = _FakeZos({
            "_current_block_data": {
                "plan_selector": [{"id": 1, "name": "Gal's zPlan", "slug": "gals-zplan"}],
                "plan_elements": [
                    {"id": 1, "name": "Delivery"},
                    {"Panels.name": "Intake", "Panels.id": 2},
                ],
            }
        })
        keys, meta = flatten_zdash_sidebar(
            ["new-plan", "%data.plan_selector", "new-element", "%data.plan_elements"],
            zos,
        )
        self.assertEqual(
            keys, ["new-plan", "Gal's zPlan", "new-element", "Delivery", "Intake"]
        )
        self.assertEqual(meta["Gal's zPlan"]["title"], "Gal's zPlan")
        self.assertEqual(meta["Intake"]["title"], "Intake")

    def test_miss_splices_nothing(self):
        keys, _ = flatten_zdash_sidebar(["new-plan", "%data.ghost"], _FakeZos())
        self.assertEqual(keys, ["new-plan"])


if __name__ == "__main__":
    unittest.main()
