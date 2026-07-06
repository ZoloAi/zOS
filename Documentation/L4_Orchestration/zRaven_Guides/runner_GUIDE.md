# zRaven Runner Guide

> **Modules:** `core/L4_Orchestration/r_zRaven/`
> (`zRaven.py`, `zRaven_modules/runner.py`, `base_runner.py`, `constants.py`, `entry.py`)
> **Purpose:** Activate the harness, detect the transport, dispatch a single `.zolo` suite to the right runner, and define the test-file format (blocks, modes, options) shared by both transports.

**[← Back to zRaven Guide](../zRaven_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

`z.raven` is a thin facade. `ZRavenRunner` does the orchestration: it resolves the suite file, reads the live `zos` for URLs/ports (SSOT — zRaven never hard-codes them), detects the session mode, and runs the suite **in-process** in a daemon thread (no subprocess for the runner itself).

```
z.raven.start()
   └─ ZRavenRunner._run()  (daemon thread)
        ├─ _is_cli_mode()?  → _run_cli()  → CLIRunner.run(blocks)        (cli/)
        └─ else             → _run_ws()   → asyncio.run(ZRaven.run(blocks))  (ws/)
        └─ _finish_run() → write result CSV → request_shutdown(exit_code)
```

---

## Activation (zSpark)

zRaven is **disabled by default**. The `zRaven` zSpark key names the suite:

```yaml
zRaven: login      # runs zRaven/zRaven.login.zolo
zRaven: false      # disabled (also: key absent)
```

| Mechanism | Effect |
|-----------|--------|
| `zRaven: <name>` | `config.raven.enabled = True`, `name = <name>` → suite `zRaven/zRaven.<name>.zolo` |
| `ZRAVEN_FILE` (env) | Overrides the resolved suite path |
| `ZRAVEN_TARGET` (env) | Set on the CLI test-target subprocess so it **never self-activates** zRaven (no recursion) |
| `zRavenTimeout` (zSpark) | Per-run hard timeout (default 120s) |

Config lives in `a_zConfig` (`config_raven.zRavenConfig`); the env-var names are single-sourced (`ENV_TARGET_KEY` there, re-exported by `zRaven_modules/constants.py`).

---

## URL/port resolution (SSOT)

`ZRavenRunner` reads the **live** objects rather than passing ports around:

- `ws_url` ← `z.bifrost.health_check()` (`host`/`port`), else `ws://127.0.0.1:8765`
- `http_url` ← `z.server.get_url()`, else `z.config.http_server` host/port, else the `config_http_server.DEFAULT_PORT`
- structured `zOpen` resolution uses the **live route table** (`z.server.route_manager`) so URLs match what the server actually serves

---

## Modes, blocks & steps

A suite is a set of **blocks**; each block is a set of **steps**; each step is a primitive (+ optional `zAssert`). Two transports run the same grammar:

| Mode | Runner | Driven |
|------|--------|--------|
| `cli` | `CLIRunner` | a zCLI app subprocess via stdin/stdout |
| `bifrost` | `ZRaven` | a browser (Playwright) + bifrost WebSocket |

The mode is the session `zMode` (`zCLI` → cli, else bifrost). Blocks and steps can be **scoped** to a transport:

```yaml
CLI_Only_Block:      { ... }    # block-name prefix CLI_      → CLI only
Browser_Only_Block:  { ... }    # prefix Browser_/Bifrost_/zBifrost_ → bifrost only
Shared_Block:                   # no prefix → runs in both modes
  step:
    zCLI:     { zSubmit: yes }          # step-level: run this in CLI mode
    zBifrost: { zClick: { selector: .ok } }  # …and this in bifrost mode
```

Prefixes (`CLI_`, `Browser_`/`Bifrost_`/`zBifrost_`) and the mode strings are SSOT in `constants.py`; the step-level `zCLI:`/`zBifrost:` split is resolved by `BaseStepRunner._resolve_mode_step`.

---

## Test-file format

```yaml
# zRavenVersion: v2.0.0                 # optional first-line stamp (recorded in runs.csv)
zConnect:       { ws: ws://…, http: http://… }   # optional transport overrides
zRavenOptions:  { stop_on_error: true, allow_external: false, timestamp_shots: false }
zMeta:          { timeout: 60 }          # per-run timeout override (seconds)

<Block_Name>:
  <step_name>: { <primitive>: <cfg>, zAssert: { … } }
  …
```

| Top-level key | Meaning |
|---------------|---------|
| `zConnect` | `ws` / `http` base URLs (CLI flags / live `zos` still win where applicable) |
| `zRavenOptions` | `stop_on_error` (halt on first failure), `allow_external` (permit cross-origin `zFetch`/`zOpen`), `timestamp_shots` (dated screenshots) |
| `zMeta` | `timeout` for the run |
| everything else | **test blocks** |

`parser.parse_raven_file()` is the single place that parses a suite and extracts `zConnect`/`zRavenOptions`/`zMeta`/`stop_on_error`/`timeout`/blocks — used by both `ZRavenRunner` and the `zraven` CLI so the rules never drift.

---

## Shared step state (`BaseStepRunner`)

Both runners subclass `BaseStepRunner`, which owns the counters and recording so the logic isn't copy-pasted:

- `passed` / `failed` / `failed_steps` / `stop_on_error`
- `_record_pass` / `_record_fail` / `_record_warn` → delegate to the reporter printers
- `_resolve_mode_step(cfg, mode)` → the `zCLI:`/`zBifrost:` step split
- `_run_logger_assert(...)` → shared `zLogger` evaluation
- `print_summary()` → the final pass/fail tally

`stop_on_error` defaults to `True` for both runners (aligned).

---

## Data isolation

Every run is idempotent: `data_manager.prepare_test_data()` renames `Data/` → `Data._zraven_bak/` and runs against a fresh copy; `teardown_test_data()` discards the copy and restores the original after the run (the CLI runner uses an in-memory snapshot/restore variant). Large SQLite DBs are handled safely (filesystem swap, no buffering). See [reporting_GUIDE → Data isolation](reporting_GUIDE.md#data-isolation).

---

## Direct CLI (`zraven`)

`entry.py` exposes the same runners as a standalone command (engine-less), driven by the shared parser:

```
zraven <zRaven.*.zolo> [--mode ws|cli] [--spark <name>] [--appdir <path>]
       [--ws ws://…] [--http http://…] [--vaFolder @.UI] [--vaFile zUI.foo] [--block MyBlock]
       [--timeout <seconds>]
```

---

## Troubleshooting

**zRaven does nothing** — `zRaven: <name>` not set in zSpark (default is disabled), or running inside a CLI test-target (`ZRAVEN_TARGET` self-disables).

**`File not found: zRaven/zRaven.<name>.zolo`** — the suite name must match the file; or set `ZRAVEN_FILE`.

**Wrong transport ran** — mode comes from session `zMode`; use block prefixes / `zCLI:`/`zBifrost:` to scope steps.

**Empty test blocks** — a `.zolo` parse error returns no blocks (treated as fatal, not silent success); check the `[zParse ERROR]` line.

---

## See Also

- [zRaven Main Guide](../zRaven_GUIDE.md) — facade overview
- [cli_GUIDE.md](cli_GUIDE.md) — the CLI runner + primitives
- [browser_GUIDE.md](browser_GUIDE.md) — the WS/browser runner + primitives
- [reporting_GUIDE.md](reporting_GUIDE.md) — results, hints, structure check, data isolation
