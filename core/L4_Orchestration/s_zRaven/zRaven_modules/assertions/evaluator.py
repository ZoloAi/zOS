# zOS/core/L4_Orchestration/s_zRaven/zRaven_modules/assertions/evaluator.py
"""zRaven assertion evaluator — WS, DOM, and style assertions.

evaluate_assert() is the single entry point; it routes to the appropriate
sub-evaluator based on the assertion config keys.
"""

from __future__ import annotations

import re as _re
from typing import Any

from ..constants import ASSERT_CONTEXT_CHARS as _ASSERT_CONTEXT_CHARS
from ..utils.parser import strip_sel as _strip_sel


# ── DOM assertions ────────────────────────────────────────────────────────────

async def _evaluate_dom_assert(dom_cfg: dict, page: Any) -> tuple[bool, str]:
    if page is None:
        return False, "zAssert.dom requires an active browser session (add zOpen: zSpark before assertions)"

    selector = _strip_sel(dom_cfg.get("selector", "body"))
    prop     = dom_cfg.get("property", "innerText")
    contains = dom_cfg.get("contains")
    equals   = dom_cfg.get("equals")
    matches  = dom_cfg.get("matches")

    # ── Element-count assertions ───────────────────────────────────────────────
    # count / min_count / max_count operate on how MANY nodes match the selector,
    # not on a property of the first one. This is the SSOT tool for "rendered
    # exactly once" (double-render regressions): dom: {selector: ..., count: 1}.
    count     = dom_cfg.get("count")
    min_count = dom_cfg.get("min_count")
    max_count = dom_cfg.get("max_count")
    if count is not None or min_count is not None or max_count is not None:
        try:
            actual_n = await page.eval_on_selector_all(
                selector, "els => els.length"
            )
        except Exception as exc:  # pylint: disable=broad-except
            return False, f"DOM count query failed ({selector}): {exc}"
        if count is not None and int(actual_n) != int(count):
            return False, (
                f"expected {int(count)} node(s) matching {selector!r}, "
                f"got {int(actual_n)}"
            )
        if min_count is not None and int(actual_n) < int(min_count):
            return False, (
                f"expected >= {int(min_count)} node(s) matching {selector!r}, "
                f"got {int(actual_n)}"
            )
        if max_count is not None and int(actual_n) > int(max_count):
            return False, (
                f"expected <= {int(max_count)} node(s) matching {selector!r}, "
                f"got {int(actual_n)}"
            )
        # Count assertions stand alone — no property comparison follows.
        return True, ""

    try:
        raw = await page.eval_on_selector(selector, f"el => el.{prop}")
        value = str(raw) if raw is not None else ""
    except Exception as exc:  # pylint: disable=broad-except
        return False, f"DOM query failed ({selector}.{prop}): {exc}"

    if contains is not None and str(contains) not in value:
        snippet = value[:_ASSERT_CONTEXT_CHARS]
        return False, f"expected {prop} to contain {contains!r}\n    got: {snippet!r}"

    if equals is not None and value != str(equals):
        return False, f"expected {prop} == {equals!r}, got {value!r}"

    if matches is not None:
        if not _re.search(str(matches), value):
            return False, f"expected {prop} to match /{matches}/, got {value!r}"

    return True, ""


# ── Style assertions ──────────────────────────────────────────────────────────

async def _evaluate_style_assert(style_cfg: dict, page: Any) -> tuple[bool, str]:
    if page is None:
        return False, "zAssert.style requires an active browser session (add zOpen: zSpark before assertions)"

    selector = _strip_sel(style_cfg.get("selector", "body"))
    prop     = style_cfg.get("property", "")
    expected = style_cfg.get("value", "")

    try:
        actual = await page.eval_on_selector(
            selector,
            f"el => window.getComputedStyle(el).getPropertyValue('{prop}')",
        )
    except Exception as exc:  # pylint: disable=broad-except
        return False, f"Style query failed ({selector}): {exc}"

    if str(expected) not in str(actual):
        return False, f"expected style.{prop} to contain {expected!r}, got {actual!r}"

    return True, ""


# ── zLogger assertion ─────────────────────────────────────────────────────────

def evaluate_logger_assert(logger_cfg: Any, log_buffer: list) -> tuple[bool, str]:
    """Assert an app-level log event was emitted.

    Shorthand:  zLogger: "message"       → message substring match, any level
    Nested:     zLogger: {message: ..., level: WARNING}
    """
    if isinstance(logger_cfg, str):
        expected_msg   = logger_cfg
        expected_level = None
    elif isinstance(logger_cfg, dict):
        expected_msg   = str(logger_cfg.get("message", ""))
        expected_level = str(logger_cfg["level"]).upper() if logger_cfg.get("level") else None
    else:
        return False, f"zLogger: unsupported format {logger_cfg!r}"

    for entry in log_buffer:
        if expected_msg in str(entry.get("message", "")):
            if expected_level and str(entry.get("level", "")).upper() != expected_level:
                continue
            return True, ""

    level_hint = f" at level {expected_level}" if expected_level else ""
    return False, f"expected app log{level_hint}: {expected_msg!r}\n    buffer: {log_buffer}"


# ── Top-level evaluator ───────────────────────────────────────────────────────

def _evaluate_api_assert(api_cfg: dict, api_response: dict) -> tuple[bool, str]:
    """
    Assert on the last zFetch HTTP response.

    zAssert:
      api:
        status: 200            # exact HTTP status code (int or string)
        status_not: 500        # status must NOT equal this
        json_contains: ok      # response JSON string-repr contains substring
        json_key:              # nested key check
          key: data            # top-level key (or dot-path: data.0.name)
          contains: alice
          equals: 3
          not_null: true
        body_contains: error   # raw body string contains substring
    """
    if not api_response:
        return False, "zAssert.api: no HTTP response captured — add a zFetch step before this assertion"

    status  = api_response.get("status", 0)
    body    = api_response.get("body",   "")
    parsed  = api_response.get("json")

    # status: exact match
    if "status" in api_cfg:
        expected = int(api_cfg["status"])
        if status != expected:
            return False, f"expected HTTP {expected}, got {status}\n  body: {body[:300]}"

    # status_not: must differ
    if "status_not" in api_cfg:
        bad = int(api_cfg["status_not"])
        if status == bad:
            return False, f"expected HTTP status != {bad}, got {status}\n  body: {body[:300]}"

    # body_contains: raw body
    if "body_contains" in api_cfg:
        needle = str(api_cfg["body_contains"])
        if needle not in body:
            return False, f"expected response body to contain {needle!r}\n  body: {body[:300]}"

    # json_contains: check raw JSON body (not Python repr, preserves true/false/null casing)
    if "json_contains" in api_cfg:
        needle    = str(api_cfg["json_contains"])
        json_str  = body  # raw response body — matches JSON lowercase true/false/null
        if needle not in json_str:
            return False, f"expected JSON body to contain {needle!r}\n  body: {json_str[:300]}"

    def _check_json_key(jk: dict) -> tuple[bool, str]:
        """Evaluate a single json_key check dict against `parsed`."""
        if not isinstance(jk, dict):
            return False, "zAssert.api.json_key must be a dict"
        key_path = str(jk.get("key", ""))
        parts    = key_path.split(".")

        val = parsed
        for part in parts:
            if val is None:
                break
            if isinstance(val, dict):
                val = val.get(part)
            elif isinstance(val, list):
                try:
                    val = val[int(part)]
                except (ValueError, IndexError):
                    val = None
            else:
                val = None

        if jk.get("not_null") and val is None:
            return False, f"expected json[{key_path!r}] to be non-null, got None"
        if "contains" in jk:
            needle = str(jk["contains"])
            if needle not in str(val):
                return False, f"expected json[{key_path!r}] to contain {needle!r}, got {val!r}"
        if "equals" in jk:
            expected_val = jk["equals"]
            if str(val) != str(expected_val) and val != expected_val:
                return False, f"expected json[{key_path!r}] == {expected_val!r}, got {val!r}"
        if "min_length" in jk and isinstance(val, (list, str)):
            min_len = int(jk["min_length"])
            if len(val) < min_len:
                return False, f"expected json[{key_path!r}] length >= {min_len}, got {len(val)}"
        return True, ""

    # json_key (single dict) or json_keys (list of dicts)
    for jk_cfg in (
        ([api_cfg["json_key"]] if "json_key" in api_cfg else [])
        + (api_cfg["json_keys"] if isinstance(api_cfg.get("json_keys"), list) else [])
    ):
        ok, reason = _check_json_key(jk_cfg)
        if not ok:
            return False, reason

    return True, ""


async def evaluate_assert(
    assert_cfg: dict,
    last_response: dict,
    page: Any = None,
    api_response: dict | None = None,
) -> tuple[bool, str]:
    """
    Evaluate a zAssert block.  Returns (passed, reason).

    Supported forms:
      zAssert:
        result:      completed       — check last WS response result field
        contains:    text            — check last WS response string contains text
        success:     true            — no ERROR: in response
        not_contains: text           — inverse of contains
        dom:                         — live DOM inspection via Playwright
          selector: css
          property: innerText
          contains: text
          count:    1               — assert exactly N nodes match the selector
          min_count: 1              — assert at least N match (max_count: at most)
        style:                       — computed style assertion
          selector: css
          property: color
          value:    rgb(...)
        api:                         — HTTP response assertion (requires prior zFetch)
          status: 200
          json_contains: ok
          json_key: {key: data, not_null: true}
    """
    if not assert_cfg:
        return True, ""

    # ── API (HTTP fetch) assertion ─────────────────────────────────────────────
    if "api" in assert_cfg:
        return _evaluate_api_assert(assert_cfg["api"], api_response or {})

    # ── DOM assertion ─────────────────────────────────────────────────────────
    if "dom" in assert_cfg:
        return await _evaluate_dom_assert(assert_cfg["dom"], page)

    # ── Style assertion ───────────────────────────────────────────────────────
    if "style" in assert_cfg:
        return await _evaluate_style_assert(assert_cfg["style"], page)

    # ── WS / text assertions ──────────────────────────────────────────────────
    response_str = str(last_response)

    if "result" in assert_cfg:
        expected = str(assert_cfg["result"])
        actual   = str(last_response.get("result", ""))
        if actual != expected:
            return False, f"expected result={expected!r}, got {actual!r}"

    if "contains" in assert_cfg:
        needle = str(assert_cfg["contains"])
        if needle not in response_str:
            snippet = response_str[:_ASSERT_CONTEXT_CHARS]
            return False, f"expected response to contain {needle!r}\n    got: {snippet!r}"

    if "not_contains" in assert_cfg:
        needle = str(assert_cfg["not_contains"])
        if needle in response_str:
            return False, f"expected response NOT to contain {needle!r}"

    if "success" in assert_cfg:
        if str(assert_cfg["success"]).lower() in ("true", "1", "yes"):
            if "ERROR:" in response_str:
                return False, f"expected success but found ERROR in response"

    return True, ""
