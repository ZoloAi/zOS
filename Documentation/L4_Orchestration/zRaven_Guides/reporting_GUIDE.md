# zRaven Reporting & Utils Guide

> **Modules:** `core/L4_Orchestration/s_zRaven/zRaven_modules/utils/`
> (`reporter.py`, `hint_analyzer.py`, `hint_rules.py`, `validator.py`, `data_manager.py`, `viewport.py`, `parser.py`, `colors.py`)
> **Purpose:** Everything around a run — the live console output + run log, the result history, failure **hints**, the zUI↔zRaven structure check, `Data/` isolation, viewport classification, and shared parsing.

**[← Back to zRaven Guide](../zRaven_GUIDE.md) | [Home](../../../README.md)**

---

## Reporting (`reporter.py`)

The reporter is the **single source** for run output (used by both runners):

- **Step printers** — `pass_step` / `fail_step` / `warn_step` / `info` (colored ✓/✗/⚠/→), plus `print_summary`.
- **Run-log Tee** — `open_log_tee()` / `close_log_tee()` mirror stdout/stderr to `zRaven/output/zRaven.last_run.log` while still printing live. (One implementation; the orchestrator and CLI runner share it — no duplicate tee logic.)
- **Result writer** — `write_result(...)` writes two artifacts after every run.

### Result artifacts

| Artifact | Purpose |
|----------|---------|
| `zRaven/output/.last_raven_result` | last-run JSON; read by `handler_ui_version.py` on next boot to attach the result to the UI version |
| `zRaven/runs.csv` | append-only, one row per run; the data source for `z raven --hint` |

`runs.csv` columns:

```
id, timestamp, mode, raven_file, ui_version, raven_rev,
steps_total, steps_passed, steps_failed, failed_steps, duration_sec, error_class
```

### `error_class` heuristic

Each run is bucketed from the failed step names + mode (so hints can pattern-match):

| Class | Meaning |
|-------|---------|
| `clean` | all steps passed |
| `structure_mismatch` | zRaven keys out of sync with zUI (flagged before the run) |
| `timeout` | `zWait`/timeout steps failed (state never reached) |
| `selector` | bifrost `zClick`/`zOpen` steps failed (element not found) |
| `assertion` | assertion failures (catch-all) |

---

## Results & hints (`hint_analyzer.py` + `hint_rules.py`)

`z raven --hint` reads the last ~20 rows of `runs.csv` (falling back to `.last_raven_result`) and runs a set of **rules** to surface agent-level, actionable suggestions — e.g. a consistent `error_class` across recent failures (`rule_error_class_pattern`) maps to a targeted fix hint. Rules read **structured columns**, not log text, so the analysis is deterministic and cheap.

```bash
z raven --hint        # analyze recent runs → printed hints
```

This is how the harness "explains itself" to an agent debugging a flaky suite, without re-parsing console logs.

---

## Structure check (`validator.py`)

The validator compares **structural keys** between a zUI file (the **source of truth**) and its zRaven suite, and prints exactly what diverged — so a UI rename surfaces as a `structure_mismatch` instead of a confusing mid-run failure.

`ZOLO_EVENT_KEYS` is the SSOT set of zolo vocabulary keys (event/primitive/property names that are **not** user-defined test paths); `is_browser_block` is reused from `viewport.py`. The same set is imported by `raven_generator.py`, so generation and validation agree.

---

## Data isolation (`data_manager.py`)

Runs are idempotent — they never mutate the app's real data:

| Function | Effect |
|----------|--------|
| `prepare_test_data(app_dir)` | rename `Data/` → `Data._zraven_bak/`, run against a fresh copy |
| `teardown_test_data(app_dir)` | discard the copy, restore the original |

The swap is filesystem-level (safe for large SQLite DBs — no buffering). The CLI runner uses a snapshot/restore variant around its subprocess. `zClean` (browser runner) is the **in-run** teardown for CSV rows and is path-contained to `Data/` (see [browser_GUIDE → zClean](browser_GUIDE.md#zclean--csv-teardown)).

---

## Viewport (`viewport.py`)

SSOT for viewport dimensions and the WS-vs-browser block split:

| Helper | Purpose |
|--------|---------|
| `VIEWPORT_SIZES` | `desktop 1280×720`, `tablet 768×1024`, `mobile 390×844` |
| `viewport_size(spec)` | dimensions for a named/`{w,h}` spec (default desktop) |
| `classify_viewport(spec)` | normalize a spec to a viewport label (screenshot foldering) |
| `is_browser_block(steps)` | block uses a Playwright primitive → needs a browser |
| `is_ws_block(steps)` | block uses `WS_PRIMITIVES` (`zExecute`/`zSubmit`) → needs a WS connection |

`is_ws_block` is what lets a **pure-HTTP** suite run with no server connection at all (see [browser_GUIDE → Overview](browser_GUIDE.md#overview)).

---

## Parsing (`parser.py`)

Shared `.zolo` parsing so the rules never drift across entry points:

| Function | Purpose |
|----------|---------|
| `zparse(text, path)` | parse a `.zolo`/`.yaml`/`.json` suite |
| `parse_raven_file(text, path, timeout)` | extract `data`/`connect`/`options`/`blocks`/`timeout`/`stop_on_error` in one place (used by `ZRavenRunner` **and** the `zraven` CLI) |
| `strip_sel(selector)` | strip stray quotes off a selector (one source; used by the WS runner + evaluator) |

`strip_ansi(...)` (ANSI escape stripping) is single-sourced in `reporter.py` and reused by the CLI runner — no duplicate regex.

---

## Console colors (`colors.py`)

ANSI constants (`GREEN`/`RED`/`YELLOW`/`CYAN`/`BOLD`/`RESET`, …) used by every printer — the one place the palette is defined.

---

## Troubleshooting

**No hints printed** — `runs.csv` doesn't exist yet (no run has completed); run a suite first, or check `.last_raven_result`.

**`structure_mismatch` before a run** — the zRaven suite references keys the zUI no longer has; update the suite to match the UI (the SSOT), or regenerate it.

**`Data._zraven_bak/` left behind** — a run crashed before teardown; it holds your **original** data — rename it back to `Data/`.

**Screenshots missing** — only `zShot` steps write images (under `zShots/`); confirm the step ran and Playwright is installed.

---

## See Also

- [zRaven Main Guide](../zRaven_GUIDE.md) — facade overview
- [runner_GUIDE.md](runner_GUIDE.md) — activation, modes, data isolation overview
- [browser_GUIDE.md](browser_GUIDE.md) — primitives that produce screenshots / WS / API state
- [assertions_GUIDE.md](assertions_GUIDE.md) — how a failure's reason becomes an `error_class`
