# zOS/tests/test_zselect_spool_options.py
"""Page zSelect live_options — zOS#57 was dialog-only; page shipped a string."""

import logging
import unittest

from zOS.L3_Abstraction.n_zLoom.zLoom import zLoom
from zOS.L3_Abstraction.n_zLoom.zLoom_modules.binding_ops import BindingOps

_LOGGER = logging.getLogger("test_zselect_spool_options")


class _FakeZos:
    def __init__(self, session=None):
        self.session = session if session is not None else {}
        self.logger = _LOGGER


class TestSelectOptionLabels(unittest.TestCase):
    def test_rows_use_name(self):
        labels = BindingOps.select_option_labels([
            {"id": 1, "name": "Gal's zPlan"},
            {"id": 2, "name": "Studio"},
        ])
        self.assertEqual(labels, ["Gal's zPlan", "Studio"])

    def test_miss_is_empty(self):
        self.assertEqual(BindingOps.select_option_labels(None), [])

    def test_qualified_name(self):
        labels = BindingOps.select_option_labels([{"Plans.name": "Home", "Plans.id": 1}])
        self.assertEqual(labels, ["Home"])


class TestResolveSelectOptions(unittest.TestCase):
    def test_page_zselect_bakes_spool(self):
        zos = _FakeZos({
            "_current_block_data": {
                "plan_selector": [
                    {"id": 1, "name": "Gal's zPlan"},
                    {"id": 2, "name": "Studio"},
                ]
            }
        })
        loom = zLoom(zos)
        block = {
            "PlanPick": {
                "zSelect": {
                    "options": "%data.plan_selector",
                    "default": "%data.plan_selector.0.name",
                }
            }
        }
        loom._resolve_select_options(block)
        pick = block["PlanPick"]["zSelect"]
        self.assertEqual(pick["options"], ["Gal's zPlan", "Studio"])
        self.assertEqual(pick["default"], "Gal's zPlan")

    def test_miss_ships_empty_list(self):
        loom = zLoom(_FakeZos())
        block = {"zSelect": {"options": "%data.ghost"}}
        loom._resolve_select_options(block)
        self.assertEqual(block["zSelect"]["options"], [])


if __name__ == "__main__":
    unittest.main()
