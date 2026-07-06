# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/utils/viewport.py
"""Viewport classification and browser-primitive detection for zRaven."""

from __future__ import annotations

# Step keys that require a live browser (Playwright) — not WS primitives.
BROWSER_PRIMITIVES = frozenset({
    "zType", "zClick", "zWait", "zShot", "zDrag", "zOpen", "zViewport",
})

# Step keys that require a live WebSocket (zBifrost) connection.
# zBoot is WS only when it has no `url` (a zBoot with url is a browser goto).
WS_PRIMITIVES = frozenset({"zExecute", "zSubmit"})

# Width thresholds for screenshot subdirectory routing ([w, h] viewport form)
_VIEWPORT_MOBILE_MAX = 480
_VIEWPORT_TABLET_MAX = 1024

# Named-viewport pixel sizes (SSOT — the WS runner imports these instead of
# re-declaring desktop/tablet/mobile dimensions).
VIEWPORT_SIZES   = {
    "desktop": (1280, 720),
    "tablet":  (768, 1024),
    "mobile":  (390, 844),
}
VIEWPORT_DEFAULT = VIEWPORT_SIZES["desktop"]
VIEWPORT_MOBILE_FALLBACK = VIEWPORT_SIZES["mobile"]

# Playwright device name fragments — used to classify named devices
_MOBILE_KEYWORDS = frozenset({"iphone", "pixel", "galaxy s", "nexus", "mobile", "android"})
_TABLET_KEYWORDS = frozenset({"ipad", "galaxy tab", "tablet", "kindle"})


def viewport_size(spec) -> tuple:
    """Return the (width, height) for a named viewport spec, default desktop."""
    return VIEWPORT_SIZES.get(str(spec).lower(), VIEWPORT_DEFAULT)


def classify_viewport(spec) -> str:
    """Return 'mobile', 'tablet', or 'desktop' for a zViewport value."""
    if isinstance(spec, str):
        low = spec.lower()
        if low in ("mobile",):
            return "mobile"
        if low in ("tablet",):
            return "tablet"
        if low in ("desktop",):
            return "desktop"
        if any(k in low for k in _MOBILE_KEYWORDS):
            return "mobile"
        if any(k in low for k in _TABLET_KEYWORDS):
            return "tablet"
        return "desktop"
    if isinstance(spec, (list, tuple)) and len(spec) >= 2:
        w = int(spec[0])
        if w <= _VIEWPORT_MOBILE_MAX:
            return "mobile"
        if w <= _VIEWPORT_TABLET_MAX:
            return "tablet"
        return "desktop"
    return "desktop"


def is_browser_block(block_steps: dict) -> bool:
    """True if the block uses any browser-only primitives."""
    for step_cfg in block_steps.values():
        if not isinstance(step_cfg, dict):
            continue
        if any(p in step_cfg for p in BROWSER_PRIMITIVES):
            return True
        if "zBoot" in step_cfg and isinstance(step_cfg["zBoot"], dict) and "url" in step_cfg["zBoot"]:
            return True
    return False


def is_ws_block(block_steps: dict) -> bool:
    """True if the block needs a live WebSocket connection.

    HTTP-only blocks (zFetch / zClean / zLogger) return False so the runner can
    execute them without opening a bifrost WS session.
    """
    for step_cfg in block_steps.values():
        if not isinstance(step_cfg, dict):
            continue
        if any(p in step_cfg for p in WS_PRIMITIVES):
            return True
        boot = step_cfg.get("zBoot")
        if isinstance(boot, dict) and "url" not in boot:
            return True
    return False
