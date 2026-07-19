#!/usr/bin/env bash
# zOS installer — macOS & Linux
#
#   curl -fsSL https://raw.githubusercontent.com/ZoloAi/zOS/main/install.sh | bash
#
# What it does (and nothing more):
#   1. Confirms this OS/arch is a supported zOS platform
#   2. Finds a CPython 3.10–3.12 (the range zGuard ships binaries for)
#   3. Creates an isolated venv at ~/.zolo/venv
#   4. Installs zolo-os from PyPI into it
#   5. Links the `z` CLI into ~/.local/bin
#
# Re-running is safe: the venv is reused and zolo-os is upgraded in place.

set -euo pipefail

ZOLO_HOME="${ZOLO_HOME:-$HOME/.zolo}"
VENV="$ZOLO_HOME/venv"
BIN_DIR="$HOME/.local/bin"

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# ── 1. platform check ─────────────────────────────────────────────────────────
OS="$(uname -s)"; ARCH="$(uname -m)"
case "$OS/$ARCH" in
    Darwin/arm64|Darwin/x86_64) ;;
    Linux/x86_64|Linux/aarch64|Linux/arm64) ;;
    *) fail "unsupported platform: $OS/$ARCH (zOS alpha supports macOS/Linux/Windows on arm64 + x86_64)" ;;
esac
say "→ platform: $OS/$ARCH — supported"

# ── 2. find CPython 3.10–3.12 ────────────────────────────────────────────────
PY=""
for cand in python3.12 python3.11 python3.10 python3; do
    if command -v "$cand" >/dev/null 2>&1; then
        if "$cand" -c 'import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,12) else 1)' 2>/dev/null; then
            PY="$(command -v "$cand")"
            break
        fi
    fi
done
# No suitable CPython? Provision one with uv (standalone builds, no admin, no
# Xcode) — this is the path a fresh Mac takes: Apple's CLT python3 is 3.9,
# below zGuard's floor, and "go install Python" is exactly the wall the
# desktop installer exists to remove.
if [ -z "$PY" ]; then
    say "→ no CPython 3.10–3.12 found — provisioning Python 3.12 via uv"
    if ! command -v "$HOME/.local/bin/uv" >/dev/null 2>&1 && ! command -v uv >/dev/null 2>&1; then
        curl -fsSL https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 \
            || fail "could not install uv. Install Python 3.10–3.12 manually (https://www.python.org/downloads/) and re-run."
    fi
    UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
    "$UV" python install 3.12 >/dev/null 2>&1 || fail "uv could not install Python 3.12 — re-run, or install Python manually and re-run."
    PY="$("$UV" python find 3.12 2>/dev/null)"
    [ -n "$PY" ] && [ -x "$PY" ] || fail "uv installed Python 3.12 but it can't be located — re-run this installer."
fi
say "→ python: $PY ($("$PY" -V 2>&1))"

# ── 3. venv ───────────────────────────────────────────────────────────────────
# Debian/Ubuntu ship python3 WITHOUT ensurepip — venv creation fails until the
# python3.X-venv apt package is installed. Cloud/default users usually have
# passwordless sudo (sudo -n); use it, otherwise print the exact command.
ensure_venv_support() {
    "$PY" -c 'import ensurepip' 2>/dev/null && return 0
    PYMM="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    if command -v apt-get >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
        say "→ installing python${PYMM}-venv (apt)"
        sudo apt-get update -qq && sudo apt-get install -y -qq "python${PYMM}-venv" >/dev/null
    else
        fail "python venv support is missing. Run:  sudo apt install python${PYMM}-venv  — then re-run this installer."
    fi
}

if [ ! -x "$VENV/bin/pip" ]; then
    ensure_venv_support
    say "→ creating venv: $VENV"
    rm -rf "$VENV"          # clear any half-created venv from a failed attempt
    "$PY" -m venv "$VENV"
else
    say "→ reusing venv: $VENV"
fi

# ── 4. install ────────────────────────────────────────────────────────────────
say "→ installing zolo-os from PyPI"
"$VENV/bin/pip" install --quiet --upgrade pip zolo-os

# ── 5. link the CLI ───────────────────────────────────────────────────────────
mkdir -p "$BIN_DIR"
ln -sf "$VENV/bin/z" "$BIN_DIR/z"
ln -sf "$VENV/bin/zolo" "$BIN_DIR/zolo" 2>/dev/null || true

# ── 6. git courtesy bootstrap ─────────────────────────────────────────────────
# zOS itself never needs git — but the golden path is "paste a prompt into
# Claude Code / Cursor", and those partners assume it. On a fresh Mac the first
# `git` call pops the Command Line Tools dialog; on Linux it may be absent.
# Bootstrap it here, NON-FATALLY: a git hiccup must never fail a zOS install.
case "$OS" in
    Darwin)
        if ! xcode-select -p >/dev/null 2>&1; then
            say "→ git: macOS Command Line Tools not installed — opening Apple's installer"
            say "  (one dialog; zOS is already installed either way)"
            xcode-select --install >/dev/null 2>&1 || true
        fi
        ;;
    Linux)
        if ! command -v git >/dev/null 2>&1; then
            if command -v apt-get >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
                say "→ installing git (apt)"
                sudo apt-get install -y -qq git >/dev/null 2>&1 || true
            else
                say "⚠ git not found — your AI partner will want it: sudo apt install git"
            fi
        fi
        ;;
esac

VERSION="$("$VENV/bin/z" --version 2>/dev/null || true)"
say ""
say "✓ installed: ${VERSION:-zolo-os}"
say ""
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) say "⚠ add ~/.local/bin to your PATH, e.g.:"
       say "    echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc && exec zsh"
       say "" ;;
esac
say "Get started:"
say "    z --version"
say "    git clone https://github.com/ZoloAi/zOS.git && cd zOS/zDemos/zHello && z zSpark.zhello.zolo"
