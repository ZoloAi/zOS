# zRaven Guide

**[← Back to zServer Guide](zServer_GUIDE.md) | [Home](../../README.md) | [L4 Overview](README.md)**

> **Automated End-to-End Test Subsystem**
> Drives the same declarative `.zolo` apps under test — over the CLI (subprocess stdin/stdout) and over the browser + WebSocket (Playwright + zBifrost) — from one declarative test file. Off by default; activated only by the operator.

---

## What It Does

**zRaven** (`z.raven`) is the L4 test subsystem: a first-class subsystem that mirrors the zServer lifecycle (created at boot, run when activated) and exercises `zWalker` + `zServer` + `zBifrost` end-to-end.

- ✅ **Two transports, one grammar** — a CLI runner (drives a zCLI app via stdin/stdout) and a WS/browser runner (Playwright + bifrost WebSocket), sharing the same `.zolo` test vocabulary
- ✅ **Declarative test files** — `zRaven/zRaven.<suite>.zolo`: blocks of steps with primitives + assertions, no Python
- ✅ **Mode-aware blocks/steps** — one file can target CLI, browser, or both (block-name prefixes + `zCLI:`/`zBifrost:` step keys)
- ✅ **Rich assertions** — `zAssert` over WS responses, live DOM, computed style, HTTP/JSON (`zFetch`), and app logs (`zLogger`)
- ✅ **Isolated, idempotent runs** — `Data/` is swapped out for a fresh copy and restored after the run
- ✅ **Result history + hints** — `runs.csv` + `.last_raven_result` + `z raven --hint` failure analysis
- ✅ **Safe by default** — connects out only; same-origin `zFetch`/`zOpen`; fail-closed cleanup; secret redaction in logs

**Status:** ✅ Audited + hardened — test-input-trust baseline (a hostile `.zolo` cannot weaponize the harness)

> This is a **facade overview**. For deep dives into each module cluster, see the [`zRaven_Guides/`](#architecture-overview) folder linked below.

---

## Architecture Overview

zRaven is a thin facade (`z.raven`) over `ZRavenRunner`, which selects a transport-specific runner and drives a single `.zolo` suite. Each cluster has its own guide:

| Cluster | Modules | Responsibility | Guide |
|---------|---------|----------------|-------|
| **runner** | `zRaven.py`, `runner.py`, `base_runner.py`, `entry.py`, `constants.py` | Activation, mode detection + dispatch, shared step state, the test-file format | [runner_GUIDE](zRaven_Guides/runner_GUIDE.md) |
| **cli** | `cli/cli_runner.py` | Subprocess stdin/stdout driver + CLI primitives (`zSubmit`/`zPick`/`zFill`/`zExpect`/`zCapture`/`zMarker`) | [cli_GUIDE](zRaven_Guides/cli_GUIDE.md) |
| **browser** | `ws/ws_runner.py` | Playwright + bifrost WS driver + browser/WS/HTTP primitives (`zOpen`/`zType`/`zClick`/`zWait`/`zShot`/`zFetch`/…) | [browser_GUIDE](zRaven_Guides/browser_GUIDE.md) |
| **assertions** | `assertions/evaluator.py` | `zAssert` (ws/dom/style/api) + `zLogger` evaluation | [assertions_GUIDE](zRaven_Guides/assertions_GUIDE.md) |
| **reporting** | `utils/` (`reporter`, `validator`, `data_manager`, `viewport`, `hint_*`, `parser`, `colors`) | Run log + result CSV, hints, zUI↔zRaven structure check, data isolation, viewport | [reporting_GUIDE](zRaven_Guides/reporting_GUIDE.md) |
| **flow lifecycle** | `utils/` (`commit_manager`, `clear_manager`, `revive_manager`) | `z raven --commit / --clear / --revive` — milestone snapshots, safe scratch cleanup, flow-file restore (see below) | [runner_GUIDE](zRaven_Guides/runner_GUIDE.md) |

```
z.raven (facade)
│
└── ZRavenRunner ── detect mode (zSpark zMode) ──┬── CLIRunner       (cli/)        stdin/stdout
                                                 └── ZRaven (async)  (ws/)         Playwright + WS

shared: BaseStepRunner (counters/recording) · constants (vocabulary SSOT)
utils:  parser (.zolo + extraction) · validator (zUI↔zRaven) · data_manager (Data/ swap)
        reporter (Tee log + runs.csv) · viewport · hint_analyzer/hint_rules · colors
assertions: evaluator (zAssert/zLogger)

Drives under test: z.walker · z.server · z.bifrost
```

**One grammar, two transports:** the same step keys mean the same thing in both runners; a step or block can be scoped to a single transport when needed (see [runner_GUIDE → Modes](zRaven_Guides/runner_GUIDE.md#modes-blocks--steps)).

---

## Flow lifecycle — zCommit / zClear / zRevive

Milestone management for a flow (spark + raven pair). **NOT git** — a commit
is a plain numbered folder (`c1`, `c2`, …) under `zVersions/commits/<flow>/`,
written once, never mutated. Ledger: `zVersions/commits.csv` (one row per
commit, project-wide).

| Command | Nature | What it does |
|---|---|---|
| `z raven --commit 'label'` | purely additive | Snapshot the flow's own files (spark + active raven) **and** the project's shared text-source state (schemas, spools, zUI, routes) + shots + last run log + a unified diff vs the previous commit. `--force` commits even when the last run didn't pass. |
| `z raven --clear` | purely subtractive | Remove dev-flow scratch (`_zSpark.<flow>.zolo` + its raven) **only** when a commit exists and the snapshot is byte-identical (`--force` skips the identity check, never the a-commit-must-exist check). Canonical `zSpark.<name>.zolo` is never touched. `zShots/` is disposable proof output and is wiped unconditionally. |
| `z raven --revive` | flow-owned restore | Copy a commit's **flow-owned** files back into the working tree (any `cN`, not just latest). Shared project files are *never* written back — they're historical record only. A diverging working file is a refusal by default; `--force` overwrites. |

The `manifest.json` in each commit records which snapshot paths are flow-owned
(restorable) vs shared (read-only history) — that split is the whole safety
model.

---

## Quick Start

### 1. Activate via zSpark

zRaven is dormant unless the `zRaven` key names a suite:

```yaml
# zSpark.myapp.zolo
zApp: myapp
zRaven: login        # runs zRaven/zRaven.login.zolo   (false / absent = disabled)
```

### 2. Write a suite

```yaml
# zRaven/zRaven.login.zolo
zConnect: { ws: ws://127.0.0.1:8765, http: http://127.0.0.1:8080 }
zRavenOptions: { stop_on_error: true }

Login_Flow:
  open:    { zOpen: zSpark }
  email:   { zType: { selector: input[name=email], value: ~email } }
  pw:      { zType: { selector: input[name=password], value: secret123 } }
  submit:  { zClick: { selector: button[type=submit] } }
  landed:  { zWait: { selector: .zDash-container }, zAssert: { contains: Dashboard } }
```

The boot/run is automatic: when the engine is ready, `z.raven.start()` runs the suite in a daemon thread and requests shutdown with the pass/fail exit code.

### 3. (Optional) run a file directly

```bash
zraven zRaven/zRaven.login.zolo --mode ws  --http http://127.0.0.1:8080
zraven zRaven/zRaven.login.zolo --mode cli --spark myapp
```

> The full `.zolo` test-file format (blocks, modes, `zConnect`/`zRavenOptions`/`zMeta`) is in [runner_GUIDE](zRaven_Guides/runner_GUIDE.md).

---

## Public API (facade)

| Member | Description |
|--------|-------------|
| `z.raven.is_enabled` | `True` when `zRaven: <suite>` is set in zSpark |
| `z.raven.start()` | Run the suite in a daemon thread (no-op if disabled); call after zServer + zBifrost are ready |
| `z.raven.wait(timeout=None)` | Block until the run completes; returns `True` if all passed |
| `z.raven.shutdown()` | Terminate the run |

```python
if z.raven.is_enabled:
    z.raven.start()
    ok = z.raven.wait(timeout=120)
```

The transport runner (`CLIRunner` / `ZRaven`) is selected automatically from the session `zMode`.

---

## Trust posture — test-input-trust

zRaven is **fully open-core** and **off by default**: nothing runs unless the operator sets `zRaven: <suite>`. The spawned CLI test-target subprocess self-disables (`ZRAVEN_TARGET`) so a run never recurses.

- **Connects out only** — bifrost WS client + HTTP client (`zFetch`) + Playwright; it **never binds/listens**, so it adds no network surface.
- **No code-exec** — no `eval`/`exec`/`compile`/`pickle`/`os.system`/`shell=True`; the only subprocess is `["z", <spark>]` (`shell=False`) and a `playwright install chromium` browser fetch.
- **Hostile-`.zolo` containment** — `zFetch`/`zOpen` are **same-origin by default** (opt-in `allow_external`); `zClean` is **fail-closed + path-contained** to `Data/`; secret-named values are redacted in logs; `zWait` passes selectors as Playwright args (no JS injection).

> **Auth & production:** sending a WebSocket auth token (when bifrost `require_auth=true`) is a **V3 / Track-3** concern — owned by the zGuard-sealed runtime + zCloud, not re-derived here. zRaven connects out and exposes nothing, so an enforced-auth server simply yields a connect failure (fail-safe), never a bypass.

---

## Summary

zRaven is a declarative end-to-end harness: **two transports, one grammar**, **isolated runs**, **rich assertions**, **result history + hints**, and a **safe-by-default** posture — driven by a single `.zolo` suite the operator opts into.

| Go deeper | Guide |
|-----------|-------|
| Activation, modes, the `.zolo` test-file format, data isolation | [runner_GUIDE](zRaven_Guides/runner_GUIDE.md) |
| CLI runner + CLI primitives | [cli_GUIDE](zRaven_Guides/cli_GUIDE.md) |
| Browser/WS runner + primitives | [browser_GUIDE](zRaven_Guides/browser_GUIDE.md) |
| `zAssert` + `zLogger` | [assertions_GUIDE](zRaven_Guides/assertions_GUIDE.md) |
| Results, hints, structure check, isolation utils | [reporting_GUIDE](zRaven_Guides/reporting_GUIDE.md) |

**Architecture:** facade → `ZRavenRunner` → transport runner (CLI | WS/browser), shared step state + vocabulary
**Status:** ✅ Audited + hardened (open-core, test-input-trust)

---

**[← Back to zServer Guide](zServer_GUIDE.md) | [Home](../../README.md) | [L4 Overview](README.md)**
