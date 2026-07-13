# tests/test_vafile_server_routes.py
"""Hand-declared route keys must survive parse_server_file (SSOT, no whitelist).

Regression for the /api/apps/push 405: the per-route extraction rebuilt each
route_entry from a fixed key list, silently dropping method:, kind:,
zapi_config: (and any future key). zapi_handler then fell back to
method=GET / kind=zData — a hand-declared `method: POST, kind: zFunc` zAPI
route answered 405 to its own POST. Auto-scanned routes carry kind/method
explicitly and were unaffected, which is why raven suites never caught it.
"""

import importlib.util
import logging
import sys
from pathlib import Path

_CORE = Path(__file__).resolve().parent.parent / "core"
sys.path.insert(0, str(_CORE))

if "zOS" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "zOS", _CORE / "__init__.py", submodule_search_locations=[str(_CORE)]
    )
    _module = importlib.util.module_from_spec(_spec)
    sys.modules["zOS"] = _module
    _spec.loader.exec_module(_module)

from zOS.L2_Handling.d_zParser.parser_modules.vafile.vafile_server import parse_server_file  # noqa: E402

_LOGGER = logging.getLogger("test_vafile_server_routes")


def _parse(routes, meta=None):
    data = {"zMeta": meta or {}, "routes": routes}
    return parse_server_file(data, _LOGGER, "zServer.test.yaml")


def test_hand_declared_zapi_route_keeps_method_kind_and_configs():
    """The exact shape of zCloud's /api/apps/push route."""
    result = _parse({
        "/api/apps/push": {
            "type": "zAPI",
            "kind": "zFunc",
            "method": "POST",
            "handler": "@.plugins.push_receiver.receive_push",
            "zapi_config": {"auth": "pat"},
        }
    })
    route = result["routes"]["/api/apps/push"]
    assert route["type"] == "zAPI"
    assert route["kind"] == "zFunc"
    assert route["method"] == "POST"
    assert route["handler"] == "@.plugins.push_receiver.receive_push"
    assert route["zapi_config"] == {"auth": "pat"}


def test_unknown_future_keys_survive():
    result = _parse({"/x": {"type": "zAPI", "zdata_config": {"t": 1}, "flow_config": {}, "custom": "y"}})
    route = result["routes"]["/x"]
    assert route["zdata_config"] == {"t": 1}
    assert route["flow_config"] == {}
    assert route["custom"] == "y"


def test_defaults_and_rbac_normalization_unchanged():
    result = _parse({"/plain": {"file": "index.html"}})
    route = result["routes"]["/plain"]
    assert route["type"] == "static"       # type default
    assert route["zRBAC"] is None          # rbac normalized to None when absent
    assert route["file"] == "index.html"


def test_zui_alias_canonicalized_to_zvafile():
    result = _parse({"/page": {"type": "zLoom", "zUI": "zUI.Profile"}})
    route = result["routes"]["/page"]
    assert route["zVaFile"] == "zUI.Profile"
    assert "zUI" not in route              # one canonical key only
    assert route["zBlock"] == "Profile"    # SSOT block derivation still runs


def test_full_zpath_zui_still_splits_folder_file_block():
    result = _parse({"/p": {"type": "zLoom", "zUI": "@.zViews.zUI.PublicProfile.Hero"}})
    route = result["routes"]["/p"]
    assert route["zVaFile"] == "zUI.PublicProfile"
    assert route["zVaFolder"] == "@.zViews"
    assert route["zBlock"] == "Hero"
