# zSys/platform_identity.py
"""
platform_identity — the single source of truth for "what machine is this?".

Every subsystem that needs a platform identifier derives it from here so the
whole codebase speaks ONE vocabulary. Before this module existed there were
three parallel ones (zguard_provision's tags, zRaven's Playwright slugs, and
zMachine's raw ``platform.machine()`` string) which drifted independently —
e.g. Windows ARM64 silently mapped to None in one and to x64 in another.

Layer 0: stdlib-only, importable before anything else boots.

Vocabulary
----------
normalized_arch()   canonical CPU family:  "arm64" | "x86_64" | "i686" | raw
current_os()        canonical OS family:   "darwin" | "linux" | "windows" | raw
zguard_platform_tag()  the zguard_bin/<tag>/ folder name (wheel-style, per-OS
                       arch spelling matches Python wheel platform tags):
                           darwin-arm64   darwin-x86_64
                           linux-aarch64  linux-x86_64
                           win-amd64      win-arm64
                       Returns None for anything we do not build — callers
                       must treat None as UNSUPPORTED, never fall back to a
                       different arch's binary.
playwright_slug()   the folder suffix Playwright uses for browser builds:
                        mac-arm64  mac-x64  linux-arm64  linux-x64  win64
                    (Playwright ships no native win-arm64 browsers; Windows
                    ARM machines run the x64 build under emulation.)
"""

import platform
import sys

# ── arch normalization ────────────────────────────────────────────────────────
# platform.machine() is whatever the OS reports: "arm64" (macOS), "aarch64"
# (Linux), "AMD64" (Windows), "x86_64", "ARM64" (Windows-on-ARM), "i686"...
_ARM64_ALIASES = ("arm64", "aarch64")
_X86_64_ALIASES = ("x86_64", "amd64")
_I686_ALIASES = ("i386", "i486", "i586", "i686", "x86")


def normalized_arch(machine: str = "") -> str:
    """Canonical CPU family for the given (or current) ``platform.machine()``."""
    raw = (machine or platform.machine()).lower()
    if raw in _ARM64_ALIASES:
        return "arm64"
    if raw in _X86_64_ALIASES:
        return "x86_64"
    if raw in _I686_ALIASES:
        return "i686"
    return raw  # riscv64, ppc64le, s390x, ... — real but unbuilt-for


def current_os(system: str = "") -> str:
    """Canonical OS family: 'darwin' | 'linux' | 'windows' (or raw lowercase)."""
    return (system or platform.system()).lower()


# ── zguard binary tags ────────────────────────────────────────────────────────
# Folder names under zguard_bin/ and the zMachine cache. The per-OS arch
# spelling intentionally mirrors Python wheel platform tags (macosx_*_arm64,
# manylinux_*_aarch64, win_amd64/win_arm64) so CI wheel names map 1:1.
_ZGUARD_TAG_MATRIX = {
    ("darwin", "arm64"): "darwin-arm64",
    ("darwin", "x86_64"): "darwin-x86_64",
    ("linux", "arm64"): "linux-aarch64",
    ("linux", "x86_64"): "linux-x86_64",
    ("windows", "arm64"): "win-arm64",
    ("windows", "x86_64"): "win-amd64",
}

ZGUARD_PLATFORM_TAGS = tuple(sorted(set(_ZGUARD_TAG_MATRIX.values())))


def zguard_platform_tag(system: str = "", machine: str = ""):
    """The zguard_bin folder tag for this (or the given) OS/arch — or None.

    None means UNSUPPORTED: no silent nearest-neighbor fallback. A riscv64
    Linux box must fail provisioning loudly rather than fetch x86_64 `.so`
    files that can never import.
    """
    return _ZGUARD_TAG_MATRIX.get((current_os(system), normalized_arch(machine)))


# ── Playwright browser-build slugs ────────────────────────────────────────────
_PLAYWRIGHT_SLUG_MATRIX = {
    ("darwin", "arm64"): "mac-arm64",
    ("darwin", "x86_64"): "mac-x64",
    ("linux", "arm64"): "linux-arm64",
    ("linux", "x86_64"): "linux-x64",
    ("windows", "arm64"): "win64",  # emulated x64 — Playwright has no ARM build
    ("windows", "x86_64"): "win64",
}


def playwright_slug(system: str = "", machine: str = ""):
    """Playwright's browser-folder suffix for this (or the given) OS/arch — or None."""
    return _PLAYWRIGHT_SLUG_MATRIX.get((current_os(system), normalized_arch(machine)))


# ── Python ABI ────────────────────────────────────────────────────────────────
def current_py_tag() -> str:
    """CPython ABI tag, e.g. 'cp312'."""
    vi = sys.version_info
    return f"cp{vi.major}{vi.minor}"
