**[← Back to zPhilosophy](../zPhilosophy.md) | [Home](../../README.md) | [Next: zConfig →](../L1_Foundation/zConfig_GUIDE.md)**

---

# zOS Installation

Everything you need, **from zero to a working zOS installation**

**About zOS:**  
`zOS` is a **Python package**. Because zOS is more than a coding framework — with
**zShell** it behaves like a **near-declarative OS** — we recommend installing it as
a **standalone tool** so the `z` / `zolo` commands are available across every project
and terminal, rather than as a project-local dependency.

The recommended installer is **[uv](https://github.com/astral-sh/uv)**'s
`uv tool install`. zOS has a large dependency tree, and uv gives it an isolated,
reproducible runtime without polluting your system Python. `pip` still works.

> **zGuard (closed-core runtime).** The open-source `zOS-OpenCore` ships with a
> **compiled `zGuard` binary** that powers the zWizard engine and zBifrost. It is
> bundled automatically — you don't install it separately — but note that the
> wizard/bifrost layers require it (the source for those internals is private).

## Requirements Checklist

- [ ] Python **3.9+** (3.11 / 3.12 recommended; the uv tool pins its own interpreter)
- [ ] **uv** installed (recommended) — or `pip` / `pip3` as an alternative

## 1. Install Python (macOS & Windows)

**Why Python Setup Instructions?**

zOS is not only a powerful framework—it's a **wonderful entry point for computer science** in general. Whether you're **13+ starting your coding journey**, or an **experienced developer**, Zolo wants to meet you where you are.

> **Never used a terminal before?** If words like "command line" or "terminal" are completely new to you, start with our **[Terminal Basics Guide](../BASICS_GUIDE.md)**—it will get you comfortable in just a few minutes.

This section helps novice developers get Python installed from scratch. If you're already set up, feel free to skip ahead.

*Note: We assume Linux users already know how to install Python* 😉

---

### 1a. macOS

```bash
# Install Homebrew (if missing)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3
brew install python@3.11

# Verify
python3 --version
pip3 --version
```

---

### 1b. Windows

1. Download from https://www.python.org/downloads/windows/
2. **Important:** enable "Add Python to PATH" during installation
3. Verify in PowerShell:
   ```powershell
   python --version
   py --version
   ```
4. If `python` fails but `py` works, use `py -m pip install ...`

---

### 1c. Troubleshoots

### Which Python command should I use?
**Common confusion: `python`, `python3`, or `py`**

It depends on your OS and Python installation:

- **macOS/Linux**: Usually `python3` and `pip3`
- **Windows**: Usually `python` or `py` and `pip`
- **Test yours**: Run each command with `--version` and use whichever reports Python 3.9+

**Best practice (works everywhere):**
```bash
# Instead of: pip install ...
# Use this:
python3 -m pip install ...

# This ensures pip matches your Python interpreter
```

> **Note:** For simplicity, the rest of this guide uses `pip` in examples.  
> If you encounter issues, substitute with `python3 -m pip` or `py -m pip` as needed.

## 2. Installing zOS

### 2a. Pick your zOS package

- **Basic** – SQLite only (fastest install)
- **CSV** – Basic + CSV tooling (`pandas`)
- **PostgreSQL** – Basic + PostgreSQL tooling (`psycopg2-binary`)
- **Monitoring** – Basic + Prometheus metrics (`prometheus_client`)
- **All** – Basic + CSV + PostgreSQL + Monitoring. All optional backends (`[all]`)

### 2b. Install as a tool (recommended — uv)

**Open your terminal** (macOS/Linux) or **Command Prompt/PowerShell** (Windows).
The distribution name is **`zolo-os`**, and it installs the `z`, `zolo`, `zraven`,
and `zagents` commands.

```bash
# Recommended: isolated tool install (provides z / zolo / zraven / zagents)
uv tool install zolo-os

# With optional backends
uv tool install "zolo-os[all]"        # csv + postgresql + monitoring
```

**Alternative: pip**

```bash
# Basic (SQLite only)
pip install zolo-os

# Optional backends
pip install "zolo-os[csv]"
pip install "zolo-os[postgresql]"
pip install "zolo-os[monitoring]"
pip install "zolo-os[all]"
```

### 2c. Install specific version

```bash
uv tool install zolo-os==1.6.6        # specific version
pip install "zolo-os>=1.6.0"          # minimum version or later
```

### 2d. Editable install (contributors)

**zOS is open source!** You can clone the entire repository, modify the code, and contribute back to the project.

An **editable install** (`-e`) means changes you make to the source code are immediately reflected without reinstalling. Perfect for:
- Contributing new features or bug fixes
- Experimenting with subsystem modifications
- Learning how zOS works under the hood

```bash
# Clone the open-core repo
git clone https://github.com/ZoloAi/zOS-OpenCore.git
cd zOS-OpenCore

# Editable tool install (gives you z / zolo / zraven / zagents)
uv tool install --editable .
```

After making source edits, run **`z patch`** to sync the editable packages into the
uv tool environment (it also clears stale `.pyc`/`.so` caches):

```bash
z patch
```

> **Working on zGuard too?** Export `ZGUARD_DEV_PATH=/path/to/zGuard` and install it
> editable as well; `z patch` then keeps both `zolo-os` and `zguard` in sync and
> purges any stale compiled `.so` files so your local source wins over the binary.

---

### 2e. UV workflow (modern package management)

**What is UV?**

[UV](https://github.com/astral-sh/uv) is an ultra-fast Python package manager from Astral (makers of `ruff`). It's 10-100x faster than pip and provides:
- Lightning-fast dependency resolution
- Reproducible builds via lock files
- Better conflict handling
- Zero-install execution (`uvx`)

**When to use UV:**
- **Developers**: Faster development workflow, especially with large dependency trees
- **CI/CD**: Dramatically faster build times
- **Users**: One-off execution without installation (`uvx`)

**Installing UV:**

```bash
# Method 1: Official installer (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Method 2: Via pip
pip install uv

# Method 3: Via Homebrew (macOS)
brew install uv
```

After installation, restart your terminal for the `uv` command to be available.

**Using UV as a user (no setup required):**

```bash
# One-off execution (no install needed!)
uvx zolo-os shell
uvx zolo-os --version

# Traditional install via UV
uv pip install zolo-os

# With optional dependencies
uv pip install "zolo-os[all]"
```

**Quick comparison:**

| Operation | pip | uv |
|-----------|-----|-----|
| Install dependencies | ~30-60s | ~3-5s ⚡ |
| Lock file support | ❌ | ✅ `uv.lock` |
| Reproducible builds | ⚠️ Drift possible | ✅ Guaranteed |
| Zero-install execution | ❌ | ✅ `uvx` |

---

### 2f. UV + Editable install (contributors)

**For contributors using UV** - the fastest development workflow:

```bash
# 1. Clone the repository
git clone https://github.com/ZoloAi/zOS-OpenCore.git
cd zOS-OpenCore

# 2. Install dependencies from lock file (uses uv.lock)
uv sync --all-extras

# 3. Your changes take effect immediately (editable mode)
uv run zolo --version
uv run zolo shell
```

**Common UV commands for development:**

```bash
# Install dependencies from lock file
uv sync

# Install with all extras (csv, postgresql, etc.)
uv sync --all-extras

# Add a new dependency
uv add requests

# Add a development dependency
uv add --dev pytest

# Update all dependencies
uv lock --upgrade
uv sync

# Run commands
uv run zolo shell
uv run pytest
```

**Why UV for development:**
- ⚡ **10-100x faster** than pip for dependency installation
- 🔒 **Reproducible** - `uv.lock` ensures identical environments
- 🚀 **Hot reload** - Changes immediately reflected (editable install)
- 🎯 **Better DX** - Smarter conflict resolution, clearer error messages

**Resources:**
- UV Documentation: https://docs.astral.sh/uv/
- UV GitHub: https://github.com/astral-sh/uv

---

## 3. Verify Installation

After installation completes, **test that zOS is working** by running these commands in your terminal:

```bash
z --version        # or: zolo --version
```

You should see the version number (e.g., `v1.6.6`). This confirms zOS is installed and accessible.


## 4. Updating

To update zOS to a newer version:

```bash
# uv tool install
uv tool upgrade zolo-os

# pip
pip install --upgrade zolo-os
```

**Check your current version:**

```bash
z --version
```

## 5. Uninstall & cleanup

### Option 1: Interactive uninstall (recommended)

Run this command in your terminal:

```bash
z uninstall        # or: zolo uninstall
```

This launches an **interactive menu** where you can choose:

1. **Framework Only** (default) - Removes the package, keeps your data and optional dependencies
2. **Clean Uninstall** - Removes package AND all user data (configs, databases, cache)
3. **Dependencies Only** - Removes optional dependencies (pandas, psycopg2) but keeps zOS

Each option shows you exactly what will be removed and asks for confirmation before proceeding.

### Option 2: Traditional pip uninstall

If you prefer the standard approach:

```bash
uv tool uninstall zolo-os    # if installed via uv tool
pip uninstall zolo-os        # if installed via pip
```

This removes the package only. Your data (configs, databases, cache) will remain on disk. See "Manual cleanup paths" below if you want to remove that data too.

### Manual cleanup paths

If you want to manually remove user data (or if you uninstalled via `pip uninstall zolo-os`):

> **Note:** Everything is stored in a single directory per platform for simplicity. No scattered files across multiple OS directories.

```bash
# macOS
rm -rf ~/Library/Application\ Support/zOS

# Linux
rm -rf ~/.local/share/zOS

# Windows (PowerShell)
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\zolo\zOS"
```

This removes all zOS data including:
- **Configuration files**: `zConfig.machine.zolo`, `zConfig.environment.zolo` (in `zConfigs/`)
- **UI customizations**: User-defined UI files (in `zUIs/`)
- **Application logs**: All log files (in `logs/`)
- **User data**: All `zMachine.*` folders containing databases, CSVs, test files, etc.

> **What are zMachine directories?** See [zConfig Guide](../L1_Foundation/zConfig_GUIDE.md) for details on how zOS manages cross-platform paths.

## What's next?

Now that **zOS** is installed, you have three paths forward:

**1. New to Zolo?**  
Start with **[The zPhilosophy](../zPhilosophy.md)**. It introduces the core concepts of **zOS** and smoothly leads into the layer-by-layer guides with ready-made demos.

**2. Comfortable with zPhilosophy?**  
Jump straight into learning with **[zConfig Guide](../L1_Foundation/zConfig_GUIDE.md)**. The cornerstone of zOS and the first declerative subsystem you'll master.

**3. Need a specific capability?**  
Review to the **[zArchitecture](../../README.md#architecture)** and jump directly to the subsystem guide you need (zConfig, zComm, zData, etc.).
