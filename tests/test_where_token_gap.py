"""zPlanner#20 — where-clause session tokens: nested resolution + zIfSet.

TWO gaps, one family (found building zPlanner's My Work / board filters):

GAP A — a token inside an OPERATOR DICT never resolved. zLoom's WHERE
interpolation only looked at top-level string values, so
``stage: {zIN: %stages}`` shipped the literal '%stages' to the adapter and
silently matched nothing (Opus, #4, 2026-09-05). Fixed by recursing into
dicts/lists in query_ops._resolve_where_value.

GAP B — no way to say "unset = match all". An unresolved token becomes None
and matches NOTHING — the right SECURE default (a %session.user_id filter must
never widen to everyone's rows), which is exactly why match-all needs an
explicit spelling. ``zIfSet`` is that spelling: set scalar → equality, set
list → IN, unset (None/''/[]) → the condition is DROPPED. False/0 are values,
not emptiness. This unblocks zPlanner #21 (My Work scope toggle) and #22
(board runner filter): first paint with no session var shows everything.
"""
import logging
from types import SimpleNamespace

from zOS.L3_Abstraction.m_zData.zData_modules.shared.operations.crud_read import (
    _build_where_from_filters,
)
from zOS.L3_Abstraction.m_zData.zData_modules.shared.operations.request_extract import (
    _normalize_rule_dialect,
)
from zOS.L3_Abstraction.n_zLoom.zLoom_modules.query_ops import QueryOps


# ── GAP B: zIfSet in the zFilters compiler ──────────────────────────────────

def test_ifset_scalar_is_equality():
    assert _build_where_from_filters({"runner": {"zIfSet": "cursor"}}) == {"runner": "cursor"}


def test_ifset_list_is_in():
    out = _build_where_from_filters({"stage": {"zIfSet": ["todo", "in_progress"]}})
    assert out == {"stage": ["todo", "in_progress"]}


def test_ifset_unset_drops_the_condition():
    for unset in (None, "", []):
        out = _build_where_from_filters({"runner": {"zIfSet": unset}, "stage": "todo"})
        assert out == {"stage": "todo"}, f"zIfSet {unset!r} must drop the condition"


def test_ifset_false_and_zero_are_set_values():
    assert _build_where_from_filters({"active": {"zIfSet": False}}) == {"active": False}
    assert _build_where_from_filters({"count": {"zIfSet": 0}}) == {"count": 0}


def test_ifset_is_recognized_rule_dialect():
    """where: {runner: {zIfSet: x}} must compile, never compare by equality."""
    ops = SimpleNamespace(logger=logging.getLogger("ztest"))
    out = _normalize_rule_dialect({"runner": {"zIfSet": "cursor"}}, ops)
    assert out == {"runner": "cursor"}
    out = _normalize_rule_dialect({"runner": {"zIfSet": None}}, ops)
    assert out == {}


# ── GAP A: token resolution recurses into operator dicts and lists ──────────

class _LoomStub(QueryOps):
    """QueryOps is a mixin — supply the two navigators + zos it expects."""

    def __init__(self, session_vars, route_vars=None):
        base = logging.getLogger("ztest.loom")
        self.zos = SimpleNamespace(
            logger=SimpleNamespace(framework=base),
        )
        self._vars = dict(session_vars)
        self._routes = dict(route_vars or {})

    def _zsession_path(self, path):
        return self._vars.get(path)

    def resolve_value(self, token):
        name = token.lstrip("%")
        if name.startswith("route."):
            return self._routes.get(name[6:])
        return self._vars.get(name)


def test_token_inside_zin_resolves_to_the_list():
    loom = _LoomStub({"stages": ["todo", "in_progress"]})
    out = loom._interpolate_session_values({"stage": {"zIN": "%stages"}})
    assert out == {"stage": {"zIN": ["todo", "in_progress"]}}


def test_tokens_inside_list_operands_resolve():
    loom = _LoomStub({"lo": 10, "hi": 90})
    out = loom._interpolate_session_values({"score": {"zBetween": ["%lo", "%hi"]}})
    assert out == {"score": {"zBetween": [10, 90]}}


def test_ifset_token_unset_reaches_compiler_as_none_and_drops():
    """The full #22 story: %board_runner never seeded → zIfSet None → no filter."""
    loom = _LoomStub({})
    interpolated = loom._interpolate_session_values({"runner": {"zIfSet": "%board_runner"}})
    assert interpolated == {"runner": {"zIfSet": None}}
    assert _build_where_from_filters(interpolated) == {}


def test_ifset_token_set_reaches_compiler_and_filters():
    loom = _LoomStub({"board_runner": "claude-code"})
    interpolated = loom._interpolate_session_values({"runner": {"zIfSet": "%board_runner"}})
    assert _build_where_from_filters(interpolated) == {"runner": "claude-code"}


def test_top_level_behavior_unchanged():
    """The pre-fix contract holds: top-level tokens resolve, literals pass,
    a missing token is None (matches nothing — the secure default)."""
    loom = _LoomStub({"me": "cursor"}, route_vars={"slug": "zos-174"})
    out = loom._interpolate_session_values({
        "runner": "%me",
        "board": "%route.slug",
        "stage": "todo",
        "ghost": "%never_set",
    })
    assert out == {"runner": "cursor", "board": "zos-174", "stage": "todo", "ghost": None}


def test_data_tokens_stay_untouched():
    loom = _LoomStub({"data.x": "should-not-resolve"})
    out = loom._interpolate_session_values({"col": "%data.x"})
    assert out == {"col": "%data.x"}


def test_like_patterns_are_not_tokens():
    """The recursion hazard the token-shape guard exists for: a raw IR LIKE
    pattern starts with % but is NOT a token — resolving it would break the
    filter. Only %identifier(.identifier)* resolves."""
    loom = _LoomStub({"John": "MANGLED", "off": "MANGLED"})
    out = loom._interpolate_session_values({
        "name": {"$like": "%John%"},
        "label": "50% off",
        "note": "%",
    })
    assert out == {"name": {"$like": "%John%"}, "label": "50% off", "note": "%"}
