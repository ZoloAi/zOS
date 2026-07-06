# zOS/core/L4_Orchestration/r_zServer/zServer_modules/routing/zapi_scanner.py

"""
zAPI Scanner — discover zAPI endpoints from zUI files at startup.

Walks all .zolo files under {serve_path}/UI/, finds any event dict
(onSubmit, onClick, etc.) that contains both 'zAPI' and 'zData' as
sibling keys, and returns route descriptors ready for HTTPRouter
registration.

Route path format: {prefix}/{app_name}/{file_stem}/{block_key}
  e.g. /api/crm/Overview/Search_Contacts

HTTP method is inferred from zData.action:
  read / search → GET
  insert / create → POST
  update → PUT
  delete → DELETE
"""

import os
import glob

from ..utils.zserver_constants import FOLDER_UI

# Event keys that can expose a zAPI endpoint
_API_EVENT_KEYS = ("onSubmit", "onClick", "onLoad", "onChange")

# zData action → HTTP method
_ACTION_TO_METHOD = {
    "read":   "GET",
    "search": "GET",
    "insert": "POST",
    "create": "POST",
    "update": "PUT",
    "delete": "DELETE",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _file_stem(path: str) -> str:
    """
    zUI.Overview.zolo  →  Overview
    zUI.Contacts.zolo  →  Contacts
    """
    name = os.path.basename(path)
    if name.startswith("zUI."):
        name = name[4:]
    if "." in name:
        name = name.rsplit(".", 1)[0]
    return name


def _clean_block_key(key: str) -> str:
    """
    ^Add_Contact  →  Add_Contact
    ~Tabs*        →  Tabs
    """
    return key.lstrip("^~").rstrip("*")


def _infer_method(kind: str, inner_config, zapi_config: dict) -> str:
    if isinstance(zapi_config, dict) and "method" in zapi_config:
        return zapi_config["method"].upper()
    if kind == "zData" and isinstance(inner_config, dict):
        action = inner_config.get("action", "read").lower()
        return _ACTION_TO_METHOD.get(action, "POST")
    # zFunc (and uploads) default to POST.
    return "POST"


# ---------------------------------------------------------------------------
# Recursive block scanner
# ---------------------------------------------------------------------------

def _scan_block(block_key: str, block_val, file_stem: str, api_defaults: dict, out: list):
    """Scan one block dict for zAPI-enabled event dicts (recursive)."""
    if not isinstance(block_val, dict):
        return

    # Look inside zDialog for events, and directly in the block
    containers = [block_val]
    zdialog = block_val.get("zDialog")
    if isinstance(zdialog, dict):
        containers.append(zdialog)

    for container in containers:
        if not isinstance(container, dict):
            continue
        for event_key in _API_EVENT_KEYS:
            event = container.get(event_key)
            if not isinstance(event, dict):
                continue
            if "zAPI" not in event:
                continue

            # zAPI fronts any inner handler. Today: zData (CRUD/search) or
            # zFunc (&plugin.fn — custom Python, e.g. uploads).
            zdata_config = event.get("zData") if isinstance(event.get("zData"), dict) else None
            zfunc_handler = event.get("zFunc") if isinstance(event.get("zFunc"), str) else None
            if zdata_config is not None:
                kind, inner = "zData", zdata_config
            elif zfunc_handler:
                kind, inner = "zFunc", zfunc_handler
            else:
                continue  # zAPI present but no recognised inner handler

            # Merge defaults + per-event overrides
            if event["zAPI"] is True:
                zapi_config = dict(api_defaults)
            elif isinstance(event["zAPI"], dict):
                zapi_config = {**api_defaults, **event["zAPI"]}
            else:
                continue  # zAPI: false / 0 / invalid — skip

            # autoConnect: false means "WIP, don't register"
            if zapi_config.get("autoConnect") is False:
                continue

            out.append({
                "file_stem":    file_stem,
                "block_key":    _clean_block_key(block_key),
                "event_key":    event_key,
                "kind":         kind,
                "method":       _infer_method(kind, inner, zapi_config),
                "zdata_config": zdata_config or {},
                "handler":      zfunc_handler or "",
                "flow_config":  {},
                "zapi_config":  zapi_config,
            })

    # Flow-level zAPI — the SSOT cascade. A zLogin/zDialog flow can itself be
    # zAPI-fronted: the FLOW is the handler (no zData/zFunc sibling needed). zServer
    # owns zAPI; here it cascades onto the flow event it fronts. zLogin compiles to
    # zDialog, so both are recognised; the executor runs the canonical flow headless.
    for flow_key in ("zLogin", "zDialog"):
        flow = block_val.get(flow_key)
        if not isinstance(flow, dict) or "zAPI" not in flow:
            continue
        if flow["zAPI"] is True:
            flow_zapi = dict(api_defaults)
        elif isinstance(flow["zAPI"], dict):
            flow_zapi = {**api_defaults, **flow["zAPI"]}
        else:
            continue  # zAPI: false / invalid — skip
        if flow_zapi.get("autoConnect") is False:
            continue
        out.append({
            "file_stem":    file_stem,
            "block_key":    _clean_block_key(block_key),
            "event_key":    flow_key,
            "kind":         flow_key,            # "zLogin" | "zDialog"
            "method":       _infer_method(flow_key, flow, flow_zapi),
            "zdata_config": {},
            "handler":      "",
            "flow_config":  flow,                # whole flow dict (model, fields, onSubmit…)
            "zapi_config":  flow_zapi,
        })

    # Recurse into nested blocks (skip special primitive keys)
    _SKIP_KEYS = {"zAPI", "zData", "zFunc", "zInput", "zDialog", "zLogin", "zH1", "zH2", "zH3",
                  "zText", "zTable", "zBrush", "zScripts",
                  "onSubmit", "onClick", "onLoad", "onChange"}
    for child_key, child_val in block_val.items():
        if child_key in _SKIP_KEYS:
            continue
        if isinstance(child_val, dict):
            _scan_block(child_key, child_val, file_stem, api_defaults, out)


def _scan_ui_dict(ui_dict: dict, file_stem: str, api_defaults: dict) -> list:
    """Scan a fully loaded zUI file dict for zAPI endpoints."""
    endpoints = []
    if not isinstance(ui_dict, dict):
        return endpoints
    for top_key, top_val in ui_dict.items():
        _scan_block(top_key, top_val, file_stem, api_defaults, endpoints)
    return endpoints


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan(serve_path: str, zos, api_defaults: dict, prefix: str = "/api") -> list:
    """
    Scan all zUI.*.zolo files in {serve_path}/UI/ and return route descriptors.

    Args:
        serve_path:   App root directory (e.g. .../zCRM)
        zos:          zOS instance (provides loader, zspark_obj, logger)
        api_defaults: Default zAPI settings from meta.zAPI in routes file
        prefix:       URL prefix (default: /api)

    Returns:
        List of dicts:  {"path": "/api/crm/Overview/Search_Contacts",
                         "route_data": {...}}
    """
    ui_folder = os.path.join(serve_path, FOLDER_UI)
    if not os.path.isdir(ui_folder):
        return []

    # App identity from zSpark (SSOT: resolve_app_id) — derives from title;
    # zApp is a deprecated optional override. Serve-path basename is last resort.
    from zOS.L1_Foundation.a_zConfig.zConfig_modules.helpers.config_helpers import (  # pylint: disable=import-outside-toplevel
        resolve_app_id,
    )
    zspark = getattr(zos, "zspark_obj", None) or {}
    app_name = resolve_app_id(
        zspark,
        fallback=os.path.basename(serve_path).lstrip("z"),
    )

    registered = []

    pattern = os.path.join(ui_folder, "**", "zUI.*.zolo")
    for zolo_path in glob.glob(pattern, recursive=True):
        try:
            # Cheap text pre-filter (SSOT: zServer owns discovery, zLoader owns
            # loading). A zAPI endpoint requires a literal `zAPI` key in the file,
            # so a file without that string cannot expose one — skip it BEFORE the
            # expensive parse. Otherwise this scan force-feeds zLoader's system
            # cache every UI file at boot just to find endpoints in a handful,
            # saturating an LRU sized for live rendering. Only the few real
            # matches are delegated to the loader (and legitimately cached).
            try:
                with open(zolo_path, "r", encoding="utf-8") as _fh:
                    if "zAPI" not in _fh.read():
                        continue
            except OSError:
                continue

            ui_data = zos.loader.handle_absolute_path(zolo_path)
            if not isinstance(ui_data, dict):
                continue

            stem      = _file_stem(zolo_path)
            endpoints = _scan_ui_dict(ui_data, stem, api_defaults)

            for ep in endpoints:
                path = f"{prefix}/{app_name}/{ep['file_stem']}/{ep['block_key']}"
                registered.append({
                    "path": path,
                    "route_data": {
                        "type":         "zAPI",
                        "kind":         ep["kind"],
                        "method":       ep["method"],
                        "zdata_config": ep["zdata_config"],
                        "handler":      ep["handler"],
                        "flow_config":  ep.get("flow_config", {}),
                        "zapi_config":  ep["zapi_config"],
                        "file_stem":    ep["file_stem"],
                        "block_key":    ep["block_key"],
                        "event_key":    ep["event_key"],
                    },
                })
                zos.logger.info(
                    f"[zAPI] Registered {ep['method']:6s} {path}"
                    f"  (kind: {ep['kind']}, event: {ep['event_key']})"
                )

        except Exception as exc:
            zos.logger.error(f"[zAPI] Failed scanning {zolo_path}: {exc}")

    if registered:
        zos.logger.info(f"[zAPI] {len(registered)} endpoint(s) auto-registered")
    else:
        zos.logger.framework.debug("[zAPI] No zAPI endpoints found")

    return registered
