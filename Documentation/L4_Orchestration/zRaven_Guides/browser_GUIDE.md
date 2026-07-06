# zRaven Browser / WS Runner Guide

> **Modules:** `core/L4_Orchestration/r_zRaven/zRaven_modules/ws/ws_runner.py`
> **Purpose:** Drive a **zBifrost** app end-to-end with a real browser (Playwright) and the bifrost WebSocket — page navigation, DOM interaction, screenshots, live WS calls, and pure-HTTP requests — from the same `.zolo` grammar as the CLI runner.

**[← Back to zRaven Guide](../zRaven_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

`ZRaven` (async, a `BaseStepRunner`) is the bifrost-mode runner. It can use up to three drivers per suite, opened **lazily**:

```
ZRaven.run(blocks)
  ├─ split blocks → ws_blocks  vs  browser_blocks   (is_browser_block)
  ├─ WS connect      → only if a block actually needs it (is_ws_block)
  ├─ Playwright page → only if a browser primitive is used
  └─ HTTP (urllib)   → zFetch only (no browser, no WS)
```

So a **pure-HTTP suite** (`zFetch`/`zClean`/`zLogger`) runs with **no server connection at all**, and a WS-only suite never launches a browser.

---

## Browser primitives (Playwright)

| Primitive | Config | Effect |
|-----------|--------|--------|
| `zOpen` | route name / `zSpark` / URL | Navigate the page (route resolved against the live route table) |
| `zType` | `selector`, `value` | Fill an input (`~` generators + `$var` refs; secret-named values redacted in logs) |
| `zClick` | `selector` | Click an element |
| `zWait` | `selector` (+ `timeout`) | Wait until the element exists **and is enabled** (selector passed as a Playwright arg — no JS injection) |
| `zShot` | `true` / `{ name, full_page }` | Screenshot → `zShots/…` (per-viewport; dated if `timestamp_shots`) |
| `zUpload` | `selector`, `file` | Set a file input |
| `zDrag` | `source`, `target` | Drag-and-drop between selectors |
| `zViewport` | `desktop`/`tablet`/`mobile` or `{width,height}` | Resize the page (sizes are SSOT in `utils/viewport.py`) |

```yaml
Browser_Login:
  open:   { zOpen: zSpark }
  email:  { zType: { selector: input[name=email], value: ~email } }
  go:     { zClick: { selector: button[type=submit] } }
  ready:  { zWait:  { selector: .zDash, timeout: 8000 } }
  proof:  { zShot:  { name: dashboard, full_page: true } }
```

> A `zViewport` step makes the block a **browser block**; viewport classification + the WS-vs-browser split live in [reporting_GUIDE → Viewport](reporting_GUIDE.md#viewport).

---

## WebSocket primitives (bifrost)

| Primitive | Config | Effect |
|-----------|--------|--------|
| `zBoot` | spark/app id | Boot the app over the bridge (auto-injected once per block unless present) |
| `zExecute` | walker/zfunc call | Drive a walker step or invoke a registered function over WS |
| `zSubmit` | form/value payload | Submit a value over the live session (secret-named values redacted) |

Responses land in `self._last_response` for the step's `zAssert` (see [assertions_GUIDE → WS asserts](assertions_GUIDE.md#ws-result-asserts)). App logs streamed over WS (`app_log` events) feed `zLogger`.

---

## HTTP primitive — `zFetch` (no browser)

`zFetch` is a **pure-`urllib`** request (intentionally stdlib — zero-dependency API tests), populating `self._last_api_response` (`{status, body, json}`) for `api` asserts:

```yaml
API_Search:
  q: { zFetch: { url: /api/crm/Search_Contacts, params: { query: alice } },
       zAssert: { api: { status: 200, json_contains: alice } } }
```

- relative URLs resolve against the live `http_url`; `params` build the query string; `body` (dict) is JSON for POST/PUT/PATCH
- `$ref` values are resolved from captured test vars

---

## Web-safety (test-input trust)

A `.zolo` suite is **input** to the harness, so the browser runner is hardened so a hostile suite can't weaponize it:

| Guard | Behaviour |
|-------|-----------|
| **Origin guard** (`_origin_allowed`) | `zFetch` / `zOpen` to an **absolute** URL must be **same-origin** as the target; cross-origin is blocked unless `zRavenOptions.allow_external: true`. Blocks SSRF + arbitrary navigation. |
| **Secret redaction** (`_looks_secret`) | `zType` / `zSubmit` values whose label looks secret (`password`, `token`, `secret`, `api_key`, …) are masked in logs. |
| **No JS injection** (`zWait`) | The selector is passed as a Playwright `arg`, never interpolated into the evaluated JS string. |
| **`zClean` fail-closed** | CSV teardown validates the `model` name (regex) and confirms the resolved path stays **under `Data/`**; write errors return failure (never swallowed). |

```yaml
zRavenOptions: { allow_external: false }   # default — same-origin only
```

> Sending a WS **auth token** when the bifrost server enforces `require_auth` is a deferred **V3/Track-3** concern (config plumbing): zRaven connects out and exposes nothing, so an auth-required server fails the connect (fail-safe) rather than being bypassed.

---

## `zClean` — CSV teardown

`zClean` removes test-created rows from a CSV model after a run. It is path-contained to the app's `Data/` and fails closed on a bad model name or an out-of-tree path:

```yaml
Teardown:
  wipe: { zClean: { model: Contacts, where: { email: alice@example.com } } }
```

---

## Troubleshooting

**`Playwright not installed`** — the runner skips the browser fetch if the package is absent; install `playwright` then `python -m playwright install chromium`.

**`zFetch blocked external URL`** — the URL isn't same-origin; set `zRavenOptions.allow_external: true` only if you intend cross-origin.

**`zWait` times out** — the element never became enabled within `timeout`; verify the selector and that the app reached that state (check a `zShot`).

**WS never connects** — only WS-needing blocks open a connection; confirm a `zBoot`/`zExecute`/`zSubmit` step exists and the bifrost server is up at the resolved `ws_url`.

---

## See Also

- [zRaven Main Guide](../zRaven_GUIDE.md) — facade overview
- [runner_GUIDE.md](runner_GUIDE.md) — activation, modes, the `.zolo` format
- [cli_GUIDE.md](cli_GUIDE.md) — the CLI equivalent
- [assertions_GUIDE.md](assertions_GUIDE.md) — `zAssert` (dom/style/api) + `zLogger`
- [reporting_GUIDE.md](reporting_GUIDE.md) — screenshots, viewport, results
