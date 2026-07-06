# zSys Formatting — Colors Guide

> **Module:** `core/zSys/formatting/colors.py`
> **Purpose:** The single source of truth for ANSI color/attribute codes in zOS. Pure constants, no logic, no dependencies.

**[← Back to Formatting Guide](../formatting_GUIDE.md) | [Home](../../../README.md)**

---

## Overview

`Colors` is a flat class of ANSI escape strings. It is a **leaf** — it imports nothing — so every other module (logger formatters, the banner printer, the zTheme mapper, zDisplay) can depend on it without a cycle. The rule across zOS: **ANSI escapes are defined here and nowhere else** (logger **U2**, formatting **F1**); logic references `Colors.*`, never raw `\033[…]`.

```
Colors  (no imports)
  ← zSys.logger.formats         (LEVEL_COLORS)
  ← zSys.formatting.terminal    (banner title)
  ← zSys.formatting.ztheme_to_ansi  (every map value)
  ← zSys.L2_Handling.e_zDisplay (rendering)
```

---

## The palettes

| Group | Examples | Use |
|-------|----------|-----|
| Subsystem colors (bg) | `ZDATA`, `ZFUNC`, `ZDIALOG`, `ZWIZARD`, `ZDISPLAY`, `PARSER`, `CONFIG`, `ZOPEN`, `ZCOMM`, `ZAUTH`, `EXTERNAL` | per-subsystem log/banner tags |
| Walker colors (bg) | `MAIN`, `SUB`, `MENU`, `DISPATCH`, `ZLINK`, `ZCRUMB`, `LOADER`, `SUBLOADER` | UI / navigation rendering |
| Standard (fg) | `GREEN`, `YELLOW`, `MAGENTA`, `CYAN`, `RED`, `PEACH`, `RESET` | general output |
| Status (bg) | `ERROR`, `WARNING`, `RETURN` | status states |
| Semantic (fg) | `zInfo`, `zSuccess`, `zWarning`, `zError` | **CSS-aligned** (`--color-info/success/warning/error`) |
| Brand (fg) | `PRIMARY`, `SECONDARY` | `--color-primary` (intention) / `--color-secondary` (validation) |
| Text attributes | `BOLD`, `NORMAL_WEIGHT`, `ITALIC`, `NORMAL_STYLE`, `DIM` | SGR weight/style |
| Extra fg/bg | `BRIGHT_WHITE`, `DARK_GRAY`, `BG_SUCCESS`, `BG_INFO`, `BG_LIGHT`, `BG_DARK` | the zTheme mapper's needs |

> **Text-attribute + extra fg/bg block (F1):** these were added so `ztheme_to_ansi.py` could stop hardcoding raw escapes (`\033[1m`, `\033[2m`, `\033[42m`, …). Every zTheme map value is now a `Colors.*` attribute — the ANSI home stays single.

---

## CSS alignment

The semantic + brand colors deliberately **mirror the zTheme CSS variables** so terminal and web stay visually consistent:

```
--color-info:    #5CA9FF   → zInfo     (256-color 75)
--color-success: #52B788   → zSuccess  (78)
--color-warning: #FFB347   → zWarning  (215)
--color-error:   #E63946   → zError    (203)
--color-primary:   #A2D46E → PRIMARY   (150)
--color-secondary: #9370DB → SECONDARY (98)
```

256-color codes are used (not truecolor `38;2;r;g;b`) for broad terminal compatibility — truecolor can be flattened by some terminals/themes.

---

## Aliases

A back-compat layer maps UPPER/lower variants onto the canonical lowercase semantic names — the value is single-sourced, only the name is duplicated:

```
ZINFO = INFO = zInfo      ZSUCCESS = SUCCESS = zSuccess
ZWARNING = zWarning       ZERROR = zError
DEFAULT = RESET           primary = PRIMARY   secondary = SECONDARY   default = DEFAULT
```

---

## Trust notes

- **Pure constants** — no logic, no imports, no I/O. Nothing to exploit.
- **The SSOT property is the point** — keeping ANSI in one leaf class is what lets every other module avoid raw escapes (auditable: a `grep '\\033\['` outside `colors.py` should stay empty in logic).

**[← Back to Formatting Guide](../formatting_GUIDE.md) | [Home](../../../README.md)**
