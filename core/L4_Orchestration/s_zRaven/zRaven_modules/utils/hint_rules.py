# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/utils/hint_rules.py
"""
Agent-level hint rules for z raven --hint.

Each rule takes a HintData dict and returns a list of Hint namedtuples.
Rules read from runs.csv — no log-text parsing needed.

HintData keys:
    runs        list[dict]  — rows from zRaven/runs.csv (newest last, max 20)
    last        dict | None — last row in runs (convenience)
    raven_lines int         — line count of active raven file
    raven_name  str         — e.g. "hello" or "crm_cli"
    ui_versions list[str]   — distinct ui_versions in runs (chronological)
    archived    dict        — {ui_ver: list[rev_name]} archived raven revisions
"""

from __future__ import annotations

from collections import Counter
from typing import NamedTuple


class Hint(NamedTuple):
    message:  str
    command:  str = ""   # optional ready-to-run command shown with the hint


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _runs(data: dict) -> list[dict]:
    return data.get("runs") or []


def _last(data: dict) -> dict:
    return data.get("last") or {}


def _failed_steps(row: dict) -> list[str]:
    raw = row.get("failed_steps") or ""
    if isinstance(raw, list):
        return raw
    return [s.strip() for s in str(raw).split("|") if s.strip()]


def _is_fail(row: dict) -> bool:
    total = int(row.get("steps_total") or 0)
    failed = int(row.get("steps_failed") or 0)
    return failed > 0 and total > 0


# ─────────────────────────────────────────────────────────────────────────────
# Rules
# ─────────────────────────────────────────────────────────────────────────────

def rule_no_data(data: dict) -> list[Hint]:
    if not _runs(data):
        return [Hint("No run data yet — run `z raven --run` first to generate results",
                     "z raven --run")]
    return []


def rule_cross_mode(data: dict) -> list[Hint]:
    """Bifrost failing while CLI passing → rendering/selector issue, not logic."""
    runs = _runs(data)
    if len(runs) < 2:
        return []

    recent = runs[-10:]
    cli_pass     = any(r.get("mode") == "cli"     and not _is_fail(r) for r in recent)
    bifrost_fail = any(r.get("mode") == "bifrost" and _is_fail(r)     for r in recent)

    if cli_pass and bifrost_fail:
        return [Hint(
            "CLI runs pass but Bifrost runs fail → this is a selector/rendering issue, "
            "not a logic bug; check zbifrost-client version or button data-zkey selectors"
        )]
    return []


def rule_rollback_suggestion(data: dict) -> list[Hint]:
    """There is a known-good revision at the same UI version — offer the rollback command."""
    runs    = _runs(data)
    last    = _last(data)
    archived = data.get("archived") or {}

    if not last or not _is_fail(last):
        return []

    current_ui_ver = last.get("ui_version") or ""
    if not current_ui_ver:
        return []

    # Find the highest revision of the current UI version that was a clean run
    green_revs = []
    for r in runs:
        if r.get("ui_version") != current_ui_ver:
            continue
        rev = r.get("raven_rev") or "active"
        if not _is_fail(r) and rev != "active":
            green_revs.append(rev)

    # Also check archived: if we have many revisions and none are recent-green,
    # the last archived clean version could be an older UI version
    if not green_revs:
        # Look for the most recent pass from a different UI version
        for r in reversed(runs):
            if r.get("ui_version") != current_ui_ver and not _is_fail(r):
                prev_ui  = r.get("ui_version", "")
                prev_rev = r.get("raven_rev", "active")
                if prev_ui and prev_rev != "active":
                    return [Hint(
                        f"Last green run was at UI {prev_ui} raven {prev_rev} — "
                        f"roll back to test against a known baseline",
                        f"z raven --run --v {prev_ui} --r {prev_rev.lstrip('r')}",
                    )]
        return []

    latest_green = sorted(green_revs)[-1]
    rev_num = latest_green.lstrip("r")
    return [Hint(
        f"Revision {latest_green} was green at UI {current_ui_ver} — "
        f"roll back to confirm it's still reproducible",
        f"z raven --run --v {current_ui_ver} --r {rev_num}",
    )]


def rule_narrow_block(data: dict) -> list[Hint]:
    """
    All failures cluster in a subset of steps → suggest narrowing zBlock in zSpark
    to the failing section for faster iteration.
    """
    runs  = _runs(data)
    last  = _last(data)
    if not last or not _is_fail(last):
        return []

    steps = _failed_steps(last)
    if not steps:
        return []

    # Try to detect a common prefix group (e.g. "Dash_Pick_Health*")
    prefixes = Counter()
    for s in steps:
        parts = s.split("_")
        if len(parts) >= 2:
            prefixes["_".join(parts[:2])] += 1

    if not prefixes:
        return []

    dominant, count = prefixes.most_common(1)[0]
    if count >= 2 or len(steps) > 4:
        return [Hint(
            f"{len(steps)} steps failing, many around `{dominant}` — "
            f"set zBlock in zSpark to the failing section for a focused smoke test"
        )]
    return []


def rule_narrow_to_cli(data: dict) -> list[Hint]:
    """Only Bifrost runs exist and all are failing → suggest switching to zCLI."""
    runs = _runs(data)
    if not runs:
        return []

    recent = runs[-6:]
    only_bifrost   = all(r.get("mode") == "bifrost" for r in recent)
    all_recent_fail = all(_is_fail(r) for r in recent)

    if only_bifrost and all_recent_fail:
        return [Hint(
            "All recent runs are Bifrost and all failing — switch zMode to zCLI "
            "in zSpark to confirm the logic layer is sound (terminal is truth)",
            "# In zSpark: zMode: zCLI  →  then  z raven --run",
        )]
    return []


def rule_streak(data: dict) -> list[Hint]:
    """3+ consecutive failures → suggest regenerating."""
    runs = _runs(data)
    streak = 0
    for r in reversed(runs):
        if _is_fail(r):
            streak += 1
        else:
            break

    if streak >= 3:
        return [Hint(
            f"{streak} consecutive failing runs — if you've edited the zUI, "
            f"regenerate the raven to resync structural keys",
            "z raven --gen",
        )]
    return []


def rule_repeated_step(data: dict) -> list[Hint]:
    """Same step failed 3+ times across recent runs."""
    runs = _runs(data)
    if len(runs) < 3:
        return []

    counter: Counter = Counter()
    for r in runs[-8:]:
        for step in _failed_steps(r):
            counter[step] += 1

    hints = []
    for step, count in counter.most_common(2):
        if count >= 3:
            hints.append(Hint(
                f"Step `{step}` failed in {count} of the last {min(8, len(runs))} runs — "
                f"consistent, not flaky: fix the zUI source (or the step's expectation) directly"
            ))
    return hints


def rule_error_class_pattern(data: dict) -> list[Hint]:
    """Consistent error_class across recent failures → targeted suggestion."""
    runs = _runs(data)
    if not runs:
        return []

    recent_fails = [r for r in runs[-6:] if _is_fail(r)]
    if len(recent_fails) < 2:
        return []

    classes = Counter(r.get("error_class", "") for r in recent_fails)
    dominant, count = classes.most_common(1)[0]

    if count < 2:
        return []

    messages = {
        "timeout": (
            "Recurring timeout failures — add `timeout:` to zMeta in your zRaven file "
            "or check that the target element appears within the wait window"
        ),
        "selector": (
            "Recurring selector failures in Bifrost — verify `button[data-zkey]` "
            "matches the rendered element; the zolo block key IS the data-zkey"
        ),
        "assertion": (
            "Recurring assertion failures — the app renders but the expected content "
            "isn't matching; check zText content or plugin return values"
        ),
    }
    msg = messages.get(dominant)
    if msg:
        return [Hint(msg)]
    return []


def rule_large_raven_file(data: dict) -> list[Hint]:
    lines = data.get("raven_lines", 0)
    if lines >= 500:
        return [Hint(
            f"zRaven file is {lines} lines — isolate the deepest flow into its own "
            f"_zSpark.<flow>.zolo dev spark (own zRaven/zRaven.<flow>.zolo, own history)"
        )]
    return []


def rule_check_demos(data: dict) -> list[Hint]:
    """After 2+ straight fails, suggest cross-referencing the known-green baseline."""
    runs = _runs(data)
    streak = 0
    for r in reversed(runs):
        if _is_fail(r):
            streak += 1
        else:
            break
    if streak >= 2:
        return [Hint(
            "Cross-reference `zDemos/zHello` — it's a known-green Bifrost baseline "
            "to confirm zOS + zbifrost-client are healthy",
            "z hello  (in a separate terminal)",
        )]
    return []


def rule_dashboard_session_bleed(data: dict) -> list[Hint]:
    """
    Dashboard assertions (Assert_Sidebar_Structure, Assert_Dashboard_Loaded) failing
    while form-level steps pass → classic sign of zspark_obj being mutated by a
    dashboard panel load (_renderTarget), causing the HTTP server to serve the wrong
    zui-config on subsequent browser connections.

    Root cause confirmed in session [zRaven viewport/cache investigation]:
      the bifrost walker was updating zspark_obj even for panel (_renderTarget) loads,
      so the second HTTP request served the panel block instead of the root block.
    """
    runs = _runs(data)
    last = _last(data)
    if not last or not _is_fail(last):
        return []

    steps = _failed_steps(last)
    dashboard_steps = [s for s in steps if any(
        kw in s.lower() for kw in ("sidebar", "dashboard", "zdash", "panel", "assert_dash")
    )]
    form_steps = [s for s in steps if any(
        kw in s.lower() for kw in ("fill_", "submit", "type", "click")
    )]

    # Dashboard assertions failing, but NOT form steps → structure not built
    if dashboard_steps and not form_steps:
        # Confirm the pattern appeared on a multi-device run (tablet/mobile steps present)
        all_steps_in_run = last.get("steps_total", 0)
        if int(all_steps_in_run or 0) > 5:
            return [Hint(
                "Dashboard structure assertions failing while form steps pass → "
                "suspect zspark_obj session bleed from a _renderTarget panel load; "
                "the HTTP server may be serving the panel block instead of the root block "
                "on 2nd+ page loads — check the bifrost walker's panel-load guard"
            )]
    return []


def rule_bifrost_cdn_unavailable(data: dict) -> list[Hint]:
    """
    If last run has 0/N passes and the raven file has Open steps for multiple
    viewports — suspect the zbifrost-client CDN tag doesn't exist yet.
    This happened when bumping to v1.7.29 before jsdelivr propagated the tag.
    """
    last = _last(data)
    if not last:
        return []

    total  = int(last.get("steps_total",  0) or 0)
    passed = int(last.get("steps_passed", 0) or 0)
    mode   = last.get("mode", "")

    # Only applies to Bifrost mode; very low pass rate on first steps
    if mode != "bifrost" or total < 3 or passed > 2:
        return []

    # First 1-2 steps (Set_Desktop, Open_Desktop) might pass, rest fail
    failed_n = int(last.get("steps_failed", 0) or 0)
    if failed_n >= (total - 2):
        return [Hint(
            "Nearly all Bifrost steps failing from the first Open step — "
            "suspect zbifrost-client CDN tag doesn't exist yet (404); "
            "verify the version in zVaF.html is live: "
            "curl -o /dev/null -w '%{http_code}' <cdn_url>/bifrost_client.js",
            "# In zVaF.html: confirm @v<X.Y.Z> tag is pushed and available on jsdelivr",
        )]
    return []


def rule_multidevice_first_only(data: dict) -> list[Hint]:
    """
    Pattern: first viewport (desktop) passes structural assertions, subsequent
    viewports (tablet, mobile) fail them. Classic sign that every zViewport change
    reuses the same browser page/context rather than creating a fresh one — the WS
    server never re-sends the zDash init on the 2nd+ connections.

    Confirmed root cause (session [viewport isolation fix]):
      Playwright viewport resize on the same page doesn't reset the WS handshake;
      zOS serves the last active panel instead of the root block on reconnect.
    Fix: zRaven now always creates a fresh browser context per zViewport change.
    If this hint fires, ensure ws_runner.py _run_viewport always creates new_context.
    """
    runs = _runs(data)
    last = _last(data)
    if not last or not _is_fail(last):
        return []

    steps = _failed_steps(last)

    # Tablet/mobile step names contain "Tablet" / "Mobile" / "tablet" / "mobile"
    device_fails = [s for s in steps if any(
        kw in s for kw in ("Tablet", "Mobile", "tablet", "mobile")
    )]
    desktop_fails = [s for s in steps if any(
        kw in s for kw in ("Desktop", "desktop")
    )]

    # Multi-device failures but desktop is clean
    if len(device_fails) >= 2 and not desktop_fails:
        return [Hint(
            "Tablet/mobile steps failing while desktop passes — "
            "viewport changes may be reusing the same browser context; "
            "each zViewport should create a fresh Playwright context so the WS "
            "server re-sends the full init sequence (zDash wrapper) on reconnect"
        )]
    return []


def rule_screenshots_without_dom_inspection(data: dict) -> list[Hint]:
    """
    Green run with screenshot steps but no DOM structure assertions.

    Screenshots prove the page rendered — they cannot catch CSS class mismatches,
    wrong element nesting, or text-align failures that look subtle at thumbnail size.
    Classic example: a _zClass on a semantic element (zH2) gets silently dropped;
    tests pass, screenshots pass, but the title is visually left-aligned on desktop.

    Fires when:
      - Last run is green (all steps passed)
      - The raven file has ≥ 2 zShot steps (screenshot-heavy test)
      - The raven file has 0 DOM structure assertions (className / tagName / style)
    """
    last        = _last(data)
    shot_count  = data.get("shot_count", 0)
    dom_count   = data.get("dom_assert_count", 0)
    has_browser = data.get("has_browser_steps", False)

    if not last or _is_fail(last):
        return []
    if not has_browser or shot_count < 2:
        return []
    if dom_count > 0:
        return []

    return [Hint(
        f"Run is green and has {shot_count} screenshot step(s) but 0 DOM structure checks — "
        f"screenshots can miss subtle layout bugs (wrong class, missing text-align, "
        f"_zClass silently dropped on semantic elements). "
        f"Add a `zAssert: dom: selector: .your-class  property: className  contains: your-class` "
        f"to verify CSS classes are actually applied to the rendered DOM.",
        "# Example: zAssert: dom: selector: '.section-title'  property: tagName  contains: DIV",
    )]


def rule_screenshot_pixel_diff_suggestion(data: dict) -> list[Hint]:
    """
    After 5+ consecutive green runs with screenshots, suggest establishing a pixel
    diff baseline so regressions surface automatically rather than via visual review.

    Fires when:
      - Last 5 runs are all green
      - The raven file has ≥ 2 zShot steps
    """
    runs       = _runs(data)
    shot_count = data.get("shot_count", 0)

    if len(runs) < 5 or shot_count < 2:
        return []

    recent_5 = runs[-5:]
    if not all(not _is_fail(r) for r in recent_5):
        return []

    return [Hint(
        f"5 consecutive green runs with {shot_count} screenshot step(s) — "
        f"this is a stable visual baseline. Consider adding `zAssert: screenshot: compare_to_baseline` "
        f"steps so pixel-level regressions surface without manual review of each shot.",
    )]


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────

ALL_RULES = [
    rule_no_data,
    rule_cross_mode,
    rule_rollback_suggestion,
    rule_narrow_block,
    rule_narrow_to_cli,
    rule_streak,
    rule_repeated_step,
    rule_error_class_pattern,
    rule_large_raven_file,
    rule_check_demos,
    rule_dashboard_session_bleed,
    rule_bifrost_cdn_unavailable,
    rule_multidevice_first_only,
    rule_screenshots_without_dom_inspection,
    rule_screenshot_pixel_diff_suggestion,
]


def apply_all(data: dict) -> list[Hint]:
    """Run all rules. Returns deduplicated Hint list."""
    hints: list[Hint] = []
    seen: set[str] = set()
    for rule in ALL_RULES:
        try:
            for h in rule(data):
                if h.message not in seen:
                    hints.append(h)
                    seen.add(h.message)
        except Exception:  # pylint: disable=broad-except
            pass
    return hints
