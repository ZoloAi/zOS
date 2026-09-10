"""zModal CALL yields to a REPLACE hop staged inside it.

Default remains resume-the-caller (MODAL_COMPLETED). A hop fired from
onSuccess OR a raw in-modal zLink / zDelta / zURL (zURL compiles to the
first two) must escape the detour untouched — otherwise the opening
button's walk resumes into stale siblings.
"""

import sys
import types
from pathlib import Path

ZOS_ROOT = Path(__file__).resolve().parents[1]
if str(ZOS_ROOT) not in sys.path:
    sys.path.insert(0, str(ZOS_ROOT))


class _Logger:
    def __init__(self):
        self.framework = self

    def debug(self, *a, **k): pass
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass


def _make_detour():
    from zOS.L2_Handling.h_zNavigation.navigation_modules.navigation_detour import (
        Detour,
    )

    logger = _Logger()
    zos = types.SimpleNamespace(
        session={"zMode": "zCLI"},
        logger=logger,
        display=types.SimpleNamespace(text=lambda *a, **k: None),
    )
    navigation = types.SimpleNamespace(zos=zos, logger=logger)
    return Detour(navigation)


def _run(inner_result, block=None):
    detour = _make_detour()
    walker = types.SimpleNamespace(
        execute_loop=lambda **k: inner_result,
    )
    return detour.run_modal(block or {"zDialog": {}}, walker)


def test_detour_passthrough_navigate():
    assert _run("navigate") == "navigate"


def test_detour_passthrough_exit():
    assert _run("exit") == "exit"


def test_detour_passthrough_zlink_dict():
    hop = {"zLink": "@.zViews.zUI.zPlanner.zPlanner"}
    assert _run(hop) == hop


def test_detour_passthrough_zdelta_dict():
    hop = {"zDelta": "$zPlanner"}
    assert _run(hop) == hop


def test_detour_passthrough_delta_pick():
    assert _run("$Details") == "$Details"


def test_detour_zback_is_dismiss():
    from zOS.zVocabulary import CONTROL_RETURN_ZBACK

    assert _run(CONTROL_RETURN_ZBACK) == {"zModal": "completed"}


def test_detour_plain_completion_resumes():
    assert _run(None) == {"zModal": "completed"}
