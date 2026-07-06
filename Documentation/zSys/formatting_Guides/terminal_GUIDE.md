# zSys Formatting — Terminal Guide

> **Module:** `core/zSys/formatting/terminal.py`
> **Purpose:** Print a width-safe "Ready" banner **before zDisplay exists**, suppressed in Production/Testing.

**[← Back to Formatting Guide](../formatting_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

`print_ready_message(label, color="CONFIG", char="═", log_level=None, is_production=None, is_testing=None)` is the only public function. Subsystems call it during Layer-0/early init to print a single banner line (e.g. `═══ zComm Ready ═══`) — at a point where `zDisplay` doesn't exist yet, so it must be self-contained and width-safe.

```
print_ready_message(label, color)
  ├─ resolve deployment (if flags not passed) → suppress in Prod/Test
  ├─ deprecated log_level=="PROD" fallback     → suppress
  ├─ detect width: COLUMNS → get_terminal_size → tput cols → 80
  ├─ clamp width to [60,120]
  ├─ pick ASCII separator (= - _ * ; default =)
  ├─ fit + optionally color the title (getattr(Colors, color))
  └─ center if it fits, else left-align → print one line
```

---

## Deployment suppression (F6)

Banners are **noise in Production/Testing** — they should only show in Development/Debug. Resolution order:

1. **Explicit flags win.** If the caller passes `is_production` / `is_testing`, those are honored (used by the `--verbose` force-show path).
2. **Otherwise self-resolve.** When both flags are `None`, the deployment mode is read from the **live zSpark** via the logger SSOT:

```python
from zOS.zCLI import get_current_zos
from zSys.logger.config import is_production_from_zspark, is_testing_from_zspark
zspark = getattr(get_current_zos(), "zspark_obj", None)
is_production = is_production_from_zspark(zspark)
is_testing    = is_testing_from_zspark(zspark)
```

This is why the ~6 unconditional callers (`zConfig`, `zComm`, `config_session`, …) now suppress correctly without each re-deriving the mode. The `zspark_obj` is set on the engine **before** config init, so it's available when these banners print. The whole block is wrapped in `try/except: pass` — banner resolution must never break a subsystem's init.

> **Layer-0 note:** `get_current_zos` / `zSys.logger.config` are imported **lazily inside the function** (the module must not import `zOS.*` at top level). Mirrors the `zSys.errors` lazy-reach pattern.
>
> **Deprecated path:** `log_level == "PROD"` (via `should_suppress_init_prints`) is kept as a backward-compat fallback; new code uses deployment mode.

---

## Width safety (pre-zDisplay banner rules)

Because there is no `zDisplay` yet, the function follows strict terminal rules:

| Rule | Behavior |
|------|----------|
| Detect width at print time | `COLUMNS` env → `shutil.get_terminal_size` → `tput cols` → fallback `80` |
| Clamp | width forced into `[60, 120]` |
| ASCII separators only | `char` must be one of `= - _ *` (else defaults to `=`) |
| Single line | never wraps; title truncated to `width-2` |
| Center or left | centered if ≥1 separator fits each side, else left-aligned |
| Color is optional | title wrapped in `getattr(Colors, color)` + `RESET`; plain version determines visual width so color never breaks alignment |

An empty label prints a full separator line; a title is rendered as ` title ` padded with the separator char.

---

## Trust notes

- **`subprocess.run(["tput","cols"])` is safe** — fixed argv (`shell=False`), no user input, `check=False`, output validated with `.isdigit()` before `int()`.
- **No exec / no network / no file-write.** Just width math + a `print`.
- **`getattr(Colors, color, Colors.RESET)`** can only return a `Colors` attribute (ANSI string) or the reset default — no code-exec even with a foreign `color`.
- The deployment self-resolution and the `tput` call are both fail-safe (try/except / `check=False`) — they degrade to "print the banner at width 80" rather than raising.

**[← Back to Formatting Guide](../formatting_GUIDE.md) | [Home](../../../README.md)**
