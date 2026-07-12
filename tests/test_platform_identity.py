# tests/test_platform_identity.py
"""zSys.platform_identity — the one OS/arch vocabulary, exercised combinatorially.

Every (OS, reported-machine-string) pair a real interpreter can produce must
map to exactly the tag the zguard_bin/ tree and Playwright's browser folders
use — or to None, never to a neighboring arch's binary.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from zSys.platform_identity import (  # noqa: E402
    ZGUARD_PLATFORM_TAGS,
    current_py_tag,
    normalized_arch,
    playwright_slug,
    zguard_platform_tag,
)


# ── arch normalization ────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("arm64", "arm64"), ("aarch64", "arm64"), ("ARM64", "arm64"),
    ("x86_64", "x86_64"), ("AMD64", "x86_64"), ("amd64", "x86_64"),
    ("i686", "i686"), ("i386", "i686"), ("x86", "i686"),
    ("riscv64", "riscv64"), ("ppc64le", "ppc64le"), ("s390x", "s390x"),
])
def test_normalized_arch(raw, expected):
    assert normalized_arch(raw) == expected


# ── zguard tags: the full supported matrix ────────────────────────────────────

@pytest.mark.parametrize("system,machine,tag", [
    ("Darwin", "arm64", "darwin-arm64"),
    ("Darwin", "x86_64", "darwin-x86_64"),
    ("Linux", "aarch64", "linux-aarch64"),
    ("Linux", "arm64", "linux-aarch64"),
    ("Linux", "x86_64", "linux-x86_64"),
    ("Windows", "AMD64", "win-amd64"),
    ("Windows", "ARM64", "win-arm64"),
])
def test_zguard_tag_supported_matrix(system, machine, tag):
    assert zguard_platform_tag(system, machine) == tag
    assert tag in ZGUARD_PLATFORM_TAGS


@pytest.mark.parametrize("system,machine", [
    ("Linux", "riscv64"),     # must NOT silently fall back to linux-x86_64
    ("Linux", "ppc64le"),
    ("Linux", "s390x"),
    ("Linux", "i686"),
    ("Windows", "i686"),
    ("FreeBSD", "x86_64"),
    ("SunOS", "sparc"),
])
def test_zguard_tag_unsupported_is_none(system, machine):
    assert zguard_platform_tag(system, machine) is None


def test_current_machine_is_supported():
    """The machine running this suite must always resolve to a real tag."""
    assert zguard_platform_tag() in ZGUARD_PLATFORM_TAGS


# ── Playwright slugs ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("system,machine,slug", [
    ("Darwin", "arm64", "mac-arm64"),
    ("Darwin", "x86_64", "mac-x64"),
    ("Linux", "aarch64", "linux-arm64"),
    ("Linux", "x86_64", "linux-x64"),
    ("Windows", "AMD64", "win64"),
    ("Windows", "ARM64", "win64"),  # x64 build under emulation
])
def test_playwright_slug_matrix(system, machine, slug):
    assert playwright_slug(system, machine) == slug


# ── consumers stay in lockstep ────────────────────────────────────────────────

def test_zguard_provision_delegates_to_ssot():
    from zSys.cli import zguard_provision
    assert zguard_provision.SUPPORTED_PLATFORM_TAGS == ZGUARD_PLATFORM_TAGS
    assert zguard_provision.current_platform_tag() == zguard_platform_tag()


def test_refresh_script_covers_every_tag():
    """Every publishable tag must have a wheel-name pattern in the refresh script."""
    script = Path(__file__).resolve().parent.parent / "scripts" / "refresh_zguard_bin.py"
    text = script.read_text()
    for tag in ZGUARD_PLATFORM_TAGS:
        assert f'"{tag}"' in text, f"refresh_zguard_bin.py has no mapping for {tag}"


def test_py_tag_shape():
    assert re.fullmatch(r"cp3\d{1,2}", current_py_tag())
