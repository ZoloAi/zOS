# Setup — Installation

Everything required to go **from zero to a working zOS installation**. This is the entry point for installing the `z` / `zolo` toolchain before you touch any subsystem.

| Guide | Covers |
|-------|--------|
| [zInstall_GUIDE](zInstall_GUIDE.md) | Full install walkthrough: Python setup (macOS/Windows), `uv tool install` (recommended) / `pip`, verification, and first run |
| [zDesktop_GUIDE](zDesktop_GUIDE.md) | Native windows (`[webview]` extra, `zSpark.zDesktop`) and the macOS `Zolo.app` launcher (`ZOS_DESKTOP` seam, `.zolo` double-click) |

> **Onboarding order:** [zPhilosophy](../zPhilosophy.md) (why) → **Setup** (install) → [zConfig](../L1_Foundation/zConfig_GUIDE.md) (first subsystem). Concept primers and quickstarts are tracked separately.

---

## At a glance

- **zOS is a Python package.** Because zShell makes it behave like a near-declarative OS, install it as a **standalone tool** so `z` / `zolo` are available across every project and terminal — not as a project-local dependency.
- **Recommended installer:** [`uv tool install`](https://github.com/astral-sh/uv) — isolated, reproducible runtime for zOS's large dependency tree. `pip` also works.
- **Requirements:** Python **3.10–3.13** (3.13 recommended; the uv tool pins its own interpreter) and `uv` (or `pip`).
- **zGuard (closed-core runtime):** OpenCore ships a bundled compiled `zGuard` binary that powers the zWizard engine and zBifrost. It installs automatically — those layers require it, and their internals are private.

## After installing

- New to the terminal? a Terminal Basics primer is planned (referenced from the install guide).
- Ready to build? Start the layer-by-layer tour at [zConfig](../L1_Foundation/zConfig_GUIDE.md), the cornerstone subsystem.

**See also:** [Home](../../README.md) · [L1 Foundation docs](../L1_Foundation/README.md)
