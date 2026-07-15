# tests/test_search_token_resolution.py
"""`search: %token` must resolve through the zLoom token SSOT before FTS runs.

Contract (Queries leaf + zRM Subscriptions): a declarative read may carry
`search: %subs_q` where the term lives in session zVars (stamped by a zfunc).
WHERE interpolation already resolves %tokens, but the FTS term travelled the
pipeline untouched, so the literal string "%subs_q" was scored against rows
(always zero hits → empty table). The fix resolves %-prefixed search terms at
the Phase 5c seam in crud_read.handle_read — ONE place all dispatch paths
(spool, inline block, dialog) travel through.

Fail-open on a miss is deliberate: an unset filter must show the FULL table
(first render happens before any term exists), unlike WHERE's fail-closed.
"""

import importlib.util
import logging
import sys
from pathlib import Path

_CORE = Path(__file__).resolve().parent.parent / "core"
sys.path.insert(0, str(_CORE))  # zSys

if "zOS" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "zOS", _CORE / "__init__.py", submodule_search_locations=[str(_CORE)]
    )
    _module = importlib.util.module_from_spec(_spec)
    sys.modules["zOS"] = _module
    _spec.loader.exec_module(_module)

from zOS.L3_Abstraction.m_zData.zData_modules.shared.operations.crud_read import handle_read  # noqa: E402

_LOGGER = logging.getLogger("test_search_token_resolution")

_ROWS = [
    {"id": 1, "name": "Maya Cohen", "email": "maya@example.com"},
    {"id": 2, "name": "Gal Nachshon", "email": "gal@zolo.media"},
    {"id": 3, "name": "QA Tester", "email": "qa@test.zolo"},
]


class _StubAdapter:
    def table_exists(self, _table):
        return True


class _StubZloom:
    """Mimics ValueOps.resolve_value: %<var> → zVars[var], miss → None."""

    def __init__(self, zvars):
        self._zvars = zvars

    def resolve_value(self, expr, context=None):
        if isinstance(expr, str) and expr.startswith("%"):
            return self._zvars.get(expr[1:])
        return None


class _StubZos:
    def __init__(self, zvars):
        self.session = {"zVars": dict(zvars)}
        self.zloom = _StubZloom(self.session["zVars"])


class _StubOps:
    def __init__(self, zvars=None):
        self.adapter = _StubAdapter()
        self.logger = _LOGGER
        self.schema = {}
        self.display = None  # silent reads never touch display
        self.zos = _StubZos(zvars or {})

    def select(self, *_args, **_kwargs):
        return [dict(r) for r in _ROWS]


def _read(ops, **extra):
    request = {"table": "zRegistrar", "silent": True, **extra}
    return handle_read(request, ops)


def test_plain_search_term_still_filters():
    rows = _read(_StubOps(), search="maya")
    assert [r["id"] for r in rows] == [1]


def test_token_search_resolves_from_zvars():
    rows = _read(_StubOps({"subs_q": "gal"}), search="%subs_q")
    assert [r["id"] for r in rows] == [2]


def test_unset_token_fails_open_to_full_table():
    rows = _read(_StubOps(), search="%subs_q")
    assert len(rows) == len(_ROWS)


def test_empty_token_value_fails_open_to_full_table():
    rows = _read(_StubOps({"subs_q": ""}), search="%subs_q")
    assert len(rows) == len(_ROWS)


def test_token_search_with_qualified_search_fields():
    ops = _StubOps({"subs_q": "test"})
    rows = _read(ops, search="%subs_q", search_fields=["name", "email"])
    assert [r["id"] for r in rows] == [3]


def test_missing_zloom_facade_fails_open():
    ops = _StubOps({"subs_q": "maya"})
    ops.zos.zloom = None
    rows = _read(ops, search="%subs_q")
    assert len(rows) == len(_ROWS)
