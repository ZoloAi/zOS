"""CLI zBtn label must bake %data.* the same way zText does."""

import types

from zOS.L2_Handling.e_zDisplay.zDisplay_modules.compounds.inputs.display_event_inputs import (
    InteractiveInputs,
)


class _Prim:
    def is_bifrost_mode(self):
        return False


class _Display:
    def __init__(self, session=None):
        self.zPrimitives = _Prim()
        self.zColors = None
        self.zos = types.SimpleNamespace(session=session if session is not None else {})
        self.mode = "zCLI"


def _button(label, context=None, session=None):
    inst = InteractiveInputs(_Display(session))
    seen = {}

    def _capture(cli_label, *a, **k):
        seen["label"] = cli_label
        return False

    inst.SelectionCollector.collect_button_confirmation = _capture
    inst.button(label=label, _context=context)
    return seen.get("label")


def test_cli_zbtn_label_resolves_data_index():
    ctx = {
        "_resolved_data": {
            "plan_selector": [{"id": 1, "name": "Demo1"}],
        }
    }
    assert _button("%data.plan_selector.0.name", context=ctx) == "Demo1"


def test_cli_zbtn_label_resolves_from_session_stash():
    session = {
        "_current_block_data": {
            "plan_selector": [{"id": 1, "name": "Demo1"}],
        }
    }
    assert _button("%data.plan_selector.0.name", session=session) == "Demo1"


def test_cli_zbtn_label_keeps_literal_on_miss():
    assert _button("%data.plan_selector.0.name") == "%data.plan_selector.0.name"
