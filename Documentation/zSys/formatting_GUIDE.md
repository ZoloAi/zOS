# zSys Formatting Guide

**[Home](../../README.md) | [zSys Overview](README.md)**

> **Terminal color + banner SSOT — Layer 0**
> The single home for ANSI color codes, the pre-zDisplay "Ready" banner printer, and the zTheme-class → ANSI bridge. Pure string constants + width math — it executes no foreign content and adds no network surface.

---

## What It Does

`zSys.formatting` is the runtime's **terminal-style floor**: one `Colors` class every layer reads from, a width-safe banner printer used before `zDisplay` exists, and a bounded mapper that turns zTheme CSS classes into ANSI.

- ✅ **ANSI SSOT** — `Colors` is the one place ANSI escapes are defined; no other module hardcodes raw `\033[…]` in logic (logger **U2**, formatting **F1**)
- ✅ **Pre-zDisplay banners** — `print_ready_message` detects terminal width (`COLUMNS` → `get_terminal_size` → `tput cols`), clamps to `[60,120]`, and prints a single ASCII-safe line before `zDisplay` is initialised
- ✅ **Deployment-aware** — banners **self-suppress in Production/Testing**, resolving the mode from the live zSpark via the logger deployment SSOT (**F6**); explicit flags still override (the `--verbose` force-show path)
- ✅ **zTheme → ANSI bridge** — `map_ztheme_classes_to_ansi` converts web styling classes (`zText-error`, `zLink-info`, `zFont-bold`, `zBg-*`) into terminal codes for the zDisplay markdown renderer
- ✅ **Mapper = allowlist** — unknown classes return `''`, so foreign content can't inject arbitrary escape sequences

**Status:** ✅ Audited + fixed — open-core, CLEAN (no zGuard seam). Findings F1–F6 resolved (Colors ANSI SSOT extended + maps repointed, dead import/`hasattr` branches removed, `zLink-*` vocabulary added, facade completed, banner deployment-suppression wired).

> This is a **facade overview**. For the color palette, the banner printer, and the zTheme mapper, see the [`formatting_Guides/`](formatting_Guides/) folder.

---

## Architecture Overview

Three modules, with `colors.py` as the leaf SSOT both siblings depend on:

| Cluster | Module | Responsibility | Guide |
|---------|--------|----------------|-------|
| **colors** | `colors.py` | `Colors` — the ANSI code SSOT (subsystem/walker/status/semantic/brand palettes + text attributes + aliases) | [colors_GUIDE](formatting_Guides/colors_GUIDE.md) |
| **terminal** | `terminal.py` | `print_ready_message(...)` — width-safe pre-zDisplay banner, deployment-suppressed | [terminal_GUIDE](formatting_Guides/terminal_GUIDE.md) |
| **ztheme→ansi** | `ztheme_to_ansi.py` | `map_ztheme_classes_to_ansi` / `get_reset_code` / `colorize_with_class` — zTheme CSS class → ANSI | [ztheme_to_ansi_GUIDE](formatting_Guides/ztheme_to_ansi_GUIDE.md) |

```
colors.Colors                          ← ANSI SSOT (leaf, no deps)
   ├── terminal.print_ready_message     (getattr(Colors, color) for the title)
   └── ztheme_to_ansi.*MAP*             (every value is a Colors.* attribute)
                                          consumed by e_zDisplay markdown
                                          (html_processor, inline_transformer)

print_ready_message:
   COLUMNS / get_terminal_size / tput cols → clamp [60,120] → ASCII separator line
   suppress if (is_production | is_testing)  ← resolved from live zSpark when not passed
```

---

## Quick Start

```python
from zSys.formatting import (
    Colors,                       # ANSI SSOT
    print_ready_message,          # pre-zDisplay banner
    map_ztheme_classes_to_ansi,   # zTheme classes → ANSI
    get_reset_code,
)

print(f"{Colors.zSuccess}done{Colors.RESET}")

# Banner — auto-suppressed in Production/Testing (resolved from the live zSpark)
print_ready_message("zComm Ready", color="CONFIG")

# zTheme → ANSI (used by the markdown renderer)
codes = map_ztheme_classes_to_ansi(["zText-error", "zFont-bold"])
print(f"{codes}Error!{get_reset_code()}")
```

---

## Public API (facade)

| Member | Description |
|--------|-------------|
| `Colors` | ANSI code SSOT — palettes + text attributes (`BOLD`, `DIM`, `ITALIC`, …) + back-compat aliases |
| `print_ready_message(label, color=…, char=…, log_level=…, is_production=None, is_testing=None)` | Width-safe banner; self-suppresses in Prod/Test (flags override) |
| `map_ztheme_class_to_ansi(class_name)` | One zTheme class → ANSI (or `''`) |
| `map_ztheme_classes_to_ansi(classes)` | Many classes → combined ANSI |
| `get_reset_code()` | `Colors.RESET` |
| `colorize_with_class(text, class_name)` | Wrap text in a class's ANSI + reset |

---

## Trust posture — CLEAN, terminal-only

`zSys.formatting` is **fully open-core** and needs **no zGuard seam**.

- **No code-exec / no network / no file-write** — no `eval`/`exec`/`compile`/`pickle`/`os.system`, no socket/bind. The one subprocess call, `subprocess.run(["tput","cols"])`, uses **fixed argv** (`shell=False`), takes **no user input**, runs `check=False`, and its output is validated with `.isdigit()` before `int()`; width is clamped to `[60,120]`.
- **`getattr(Colors, color, Colors.RESET)`** — `color` is an internal constant at every call site; even if foreign, `getattr` on the class can only return an attribute (an ANSI string) or `RESET` → no code-exec.
- **The zTheme mapper is its own allowlist** — `map_ztheme_class_to_ansi` emits a code only for **known** class names (unknown → `''`), so foreign zTheme/`.zolo` content cannot inject arbitrary escape sequences through this path. The bounded class→code table *is* the sanitizer.
- **Layer-0 discipline** — top-level imports are stdlib (`os`/`shutil`/`subprocess`/`typing`) + sibling `.colors`; the reaches to `zSys.logger.config` and `get_current_zos` (deployment resolution) are **lazy, inside the function**, and wrapped in try/except so banner logic never breaks a subsystem's init.

---

## Summary

`zSys.formatting` is the **terminal-style floor**: one ANSI SSOT (`Colors`), a width-safe deployment-aware banner printer, and a bounded zTheme→ANSI bridge that doubles as an escape-injection allowlist.

| Go deeper | Guide |
|-----------|-------|
| The `Colors` palettes, text attributes, and alias layer | [colors_GUIDE](formatting_Guides/colors_GUIDE.md) |
| `print_ready_message` — width detection, ASCII rules, deployment suppression | [terminal_GUIDE](formatting_Guides/terminal_GUIDE.md) |
| zTheme class → ANSI mapping, the three maps, the allowlist property | [ztheme_to_ansi_GUIDE](formatting_Guides/ztheme_to_ansi_GUIDE.md) |

**Architecture:** three modules over one `Colors` SSOT (colors ← terminal · ztheme→ansi), consumed across the runtime + the zDisplay markdown renderer
**Status:** ✅ Audited + fixed (open-core, CLEAN — no zGuard seam)

---

**[Home](../../README.md) | [zSys Overview](README.md)**
