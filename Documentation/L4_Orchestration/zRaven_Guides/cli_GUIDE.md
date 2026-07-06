# zRaven CLI Runner Guide

> **Modules:** `core/L4_Orchestration/r_zRaven/zRaven_modules/cli/cli_runner.py`
> **Purpose:** Drive a **zCLI** zOS app as a subprocess over stdin/stdout, sending input and asserting on rendered console output — the same `.zolo` grammar as the browser runner.

**[← Back to zRaven Guide](../zRaven_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

`CLIRunner` (a `BaseStepRunner`) launches the app under test as a child process and talks to it like a user would:

```
CLIRunner.run(blocks)
  ├─ snapshot Data/          (restored on exit)
  ├─ open run-log Tee        (reporter.open_log_tee)
  ├─ Popen(["z", <spark>], shell=False, cwd=app_dir, env=+ZRAVEN_TARGET)
  ├─ reader thread → queue → _drain()  (settle-based output capture)
  └─ for each block → _run_steps(...)
```

The child is launched with `shell=False` and a fixed argv (`["z", <spark_name>]`) — no shell, no test-derived string on the command line. `ZRAVEN_TARGET=1` is set so the child never re-activates zRaven.

---

## How input/output works

The runner reads the child's stdout on a background thread, splits it into lines, and **settles**: a step's output is considered complete after a quiet interval (`_SETTLE_S`, longer on boot). Interactive prompts (`username:`, numbered menus) are detected so `zSubmit`/`zPick` send at the right moment.

App-emitted log lines tagged by the L1 `app_emit` wire format (`\x00ZLOG\x1f…`) are split off into an **app-log buffer** for `zLogger` assertions (parsed via `app_emit.parse_cli_log_line` — one SSOT for the format across L1 and L4).

---

## CLI primitives

| Primitive | Config | Effect |
|-----------|--------|--------|
| `zSubmit` | `value` (string; `$var` refs resolved) | Wait for the prompt to settle, then write `value\n` to stdin |
| `zPick` | menu option label (`^opt` ok) | Find the option in the rendered menu → send its index |
| `zExpect` | `deny` (+ companion `zPick`) | **Security probe:** PASS when the RBAC gate blocks the pick, FAIL if it doesn't |
| `zCapture` | `var`, `pattern` (regex) | Capture group 1 (ANSI-stripped) into `$var` for later steps |
| `zMarker` | label | Signal end of test → close stdin |
| `zVar` | name | Store the just-submitted value as `$name` |
| `zAllowError` | `true` | Permit an `ERROR:` line after this submit (otherwise a hard failure) |

Containers: `zWizard` / `zMenu` blocks recurse into their child steps. `zLogger` asserts against the app-log buffer (see [assertions_GUIDE](assertions_GUIDE.md#zlogger)).

```yaml
CLI_Login:
  user:   { zSubmit: alice,  zAssert: { contains: password } }
  pass:   { zSubmit: secret, zVar: pw }
  menu:   { zPick: Dashboard }
  who:    { zCapture: { var: uid, pattern: "user id: (\\d+)" } }
  done:   { zMarker: done }
```

---

## CLI `zAssert` keys

The CLI runner checks assertions against the **console output since the last submit**:

| Key | Meaning |
|-----|---------|
| `contains` | Output must contain the text — **case-insensitive**, and tries an `_`→space variant so `new_password` matches a rendered label "New Password" |
| `not_contains` | Output must **not** contain the text |
| `success: true` | No `ERROR:` line in the output |

> The CLI `contains` matching is intentionally **fuzzy** (rendered-label friendly) — this is why it stays distinct from the WS evaluator's exact substring check in [assertions_GUIDE](assertions_GUIDE.md).

---

## The `zSetup` block (soft)

A block named `zSetup` runs **before** the test blocks as a **soft** block: its step failures are ⚠ warnings (not counted), for fixtures / cleanup that shouldn't fail the suite.

```yaml
zSetup:
  seed: { zSubmit: seed-data }   # failures here warn, don't fail the run
```

---

## RBAC probing (`zExpect: deny`)

`zExpect: deny` + a companion `zPick` is a **security test**: it picks a gated menu option and PASSES only when the console shows an access-denied signal (`access denied`, `[rbac]`, `not authorized`, …). If the gate does **not** hold, it FAILs loudly ("gate did NOT hold (security gap!)"). This is a test signal over console text, not an authoritative RBAC check.

---

## Troubleshooting

**Hangs on boot** — the app never printed a prompt within the boot settle window; check the app actually starts under `z <spark>` and prints to stdout.

**`option '<x>' not found in menu`** — the label didn't match the rendered menu; the runner prints close matches / available options.

**Spurious `ERROR:` failure after submit** — the app logged `ERROR:`; add `zAllowError: true` to the step if that error is expected.

**`$var` not substituted** — the capture step didn't match (warns "variable $x not defined"); verify the `zCapture` pattern and that it ran first.

---

## See Also

- [zRaven Main Guide](../zRaven_GUIDE.md) — facade overview
- [runner_GUIDE.md](runner_GUIDE.md) — activation, modes, the `.zolo` format
- [browser_GUIDE.md](browser_GUIDE.md) — the WS/browser equivalent
- [assertions_GUIDE.md](assertions_GUIDE.md) — `zAssert` + `zLogger`
