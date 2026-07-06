# zRaven Assertions Guide

> **Modules:** `core/L4_Orchestration/r_zRaven/zRaven_modules/assertions/evaluator.py`
> **Purpose:** Evaluate a step's `zAssert` against whatever the step produced — a WS response, the live DOM, a computed style, or an HTTP/JSON response — plus `zLogger` checks against captured app logs.

**[← Back to zRaven Guide](../zRaven_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

Any step in a bifrost suite can carry a `zAssert` block; after the primitive runs, `evaluate_assert(...)` checks it and the result is recorded as pass/fail. The evaluator picks the assertion **kind** by which key is present, in this order: `api` → `dom` → `style` → top-level (`result`/`contains`/`not_contains`/`success`). `zLogger` is handled separately (shared by both runners).

```yaml
step: { zClick: { selector: .save }, zAssert: { dom: { selector: .toast, contains: Saved } } }
```

> The **CLI runner** uses its own (fuzzy, rendered-label) `contains`/`not_contains`/`success` matching — see [cli_GUIDE → CLI zAssert](cli_GUIDE.md#cli-zassert-keys). This guide covers the **bifrost** evaluator.

---

## WS result asserts

Checked against `self._last_response` (from `zBoot`/`zExecute`/`zSubmit`):

| Key | Pass when |
|-----|-----------|
| `result: <value>` | `last_response["result"]` equals the value (string compare) |
| `contains: <text>` | the response string contains the text |
| `not_contains: <text>` | the response string does **not** contain the text |
| `success: true` | no `ERROR:` in the response string |

```yaml
boot: { zBoot: myapp, zAssert: { result: completed } }
call: { zExecute: { fn: Search }, zAssert: { contains: results, not_contains: ERROR } }
```

---

## DOM asserts (`dom`)

Reads a property off a live element via Playwright:

| Field | Default | Meaning |
|-------|---------|---------|
| `selector` | `body` | element to read |
| `property` | `innerText` | property/attribute to read |
| `contains` / `equals` / `matches` | — | substring / exact / regex check on the value |

```yaml
check: { zAssert: { dom: { selector: .count, property: innerText, matches: "^\\d+ items$" } } }
```

---

## Style asserts (`style`)

Reads a **computed** style value:

```yaml
themed: { zAssert: { style: { selector: .btn, property: background-color, value: rgb(0, 122, 255) } } }
```

`selector` defaults to `body`; the check compares the computed `property` against `value`.

---

## API asserts (`api`)

Checked against `self._last_api_response` (`{status, body, json}`) from `zFetch`:

| Field | Meaning |
|-------|---------|
| `status` | response status must equal |
| `status_not` | response status must **not** equal |
| `body_contains` | raw body contains the substring |
| `json_contains` | raw JSON body contains the substring (preserves `true`/`false`/`null` casing) |
| `json_key` | a single nested-key check (dict, below) |
| `json_keys` | a list of nested-key checks |

**`json_key` / `json_keys`** check a dotted path into the parsed JSON:

```yaml
zAssert:
  api:
    status: 200
    json_key:  { key: data.id, not_null: true }
    json_keys:
      - { key: data.email, equals: alice@example.com }
      - { key: data.role,  contains: admin }
```

Each entry supports `not_null`, `contains`, `equals` on the resolved value.

---

## zLogger

`zLogger` asserts that the **app under test** emitted a log line — captured over WS (`app_log` events) or from the CLI app-log buffer (`\x00ZLOG` wire format, parsed via the L1 `app_emit` SSOT). It is evaluated by the shared `BaseStepRunner._run_logger_assert`, so it behaves identically in both runners.

```yaml
# string form — message substring
logged:  { zLogger: User logged in }

# dict form — message + level
leveled: { zLogger: { message: cache miss, level: WARNING } }
```

PASS when an entry's `message` contains the expected text (and, if given, `level` matches case-insensitively).

---

## Failure reporting

A failed assert records a **reason** (e.g. `expected dom .toast contains 'Saved', got '…'`) that flows into the run log and the per-run result row. The reason's shape feeds the `error_class` bucket (`assertion`, `selector`, …) used by hints — see [reporting_GUIDE → Results & hints](reporting_GUIDE.md#results--hints).

---

## Troubleshooting

**`json_key` always fails** — the path is dotted into the **parsed** JSON; confirm the response is valid JSON (not just a body string) and the key path is correct.

**`style` mismatch on colors** — browsers normalize to `rgb(...)`; compare against the computed `rgb()` value, not a hex string.

**`zLogger` never matches** — the app didn't emit the line, or the WS `app_log` stream wasn't connected (WS-only path); verify the app logs at that level.

---

## See Also

- [zRaven Main Guide](../zRaven_GUIDE.md) — facade overview
- [browser_GUIDE.md](browser_GUIDE.md) — the primitives that produce responses/DOM/API state
- [cli_GUIDE.md](cli_GUIDE.md) — the CLI runner's own `contains`/`success` matching
- [reporting_GUIDE.md](reporting_GUIDE.md) — how failures become results + hints
