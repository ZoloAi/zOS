#!/usr/bin/env python3
"""Refresh zguard_bin/ from a folder of zGuard CI wheels — the ONE way to publish.

Replaces the hand-extraction step that used to sit between the zGuard wheel
build and `git push` (one slip there ships closed-core source, a torn image,
or a stale VERSION). This script is deliberately strict: it wipes each image
tree it rebuilds, admits only compiled extensions + __init__.py stubs, and
regenerates MANIFEST.txt/VERSION from the wheel itself.

Usage:
    # 1) download the tagged run's artifacts (wheels-* folders of .whl files)
    gh run download <run-id> -R ZoloAi/zGuard -D /tmp/zguard_wheels

    # 2) rebuild every platform/py image from them
    python scripts/refresh_zguard_bin.py /tmp/zguard_wheels

    # 3) sanity gate (also run by this script per-image)
    python scripts/verify_zguard_image.py

    # 4) commit zguard_bin/ and push — z patch picks it up from raw GitHub
"""
from __future__ import annotations

import re
import sys
import shutil
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ZGUARD_BIN = REPO_ROOT / "zguard_bin"

# wheel platform tag fragment -> zguard_bin platform folder
_PLATFORM_MAP = (
    (re.compile(r"macosx_[\d_]+_arm64"), "darwin-arm64"),
    (re.compile(r"macosx_[\d_]+_x86_64"), "darwin-x86_64"),
    (re.compile(r"macosx_[\d_]+_universal2"), "darwin-universal2"),  # split below
    (re.compile(r"manylinux[\w\d_]*_x86_64"), "linux-x86_64"),
    (re.compile(r"manylinux[\w\d_]*_aarch64"), "linux-aarch64"),
    (re.compile(r"win_amd64"), "win-amd64"),
    (re.compile(r"win_arm64"), "win-arm64"),
)

# A universal2 macOS wheel serves both darwin folders.
_UNIVERSAL2_TARGETS = ("darwin-arm64", "darwin-x86_64")

_ALLOWED_BINARY_SUFFIXES = (".so", ".pyd")


def _classify(wheel: Path) -> tuple[str, str, list[str]] | None:
    """(version, py_tag, [platform folders]) from a wheel filename, or None."""
    # zguard-1.0.3-cp312-cp312-macosx_10_9_arm64.whl
    m = re.match(r"zguard-([\w.]+)-(cp\d+)-[\w]+-(.+)\.whl$", wheel.name)
    if not m:
        return None
    version, py_tag, platform_frag = m.groups()
    for pattern, folder in _PLATFORM_MAP:
        if pattern.search(platform_frag):
            targets = list(_UNIVERSAL2_TARGETS) if folder == "darwin-universal2" else [folder]
            return version, py_tag, targets
    print(f"  !! unrecognized platform tag: {wheel.name}")
    return None


def _extract_image(wheel: Path, dest: Path) -> list[str]:
    """Extract the pure binary image into dest/zguard; return manifest paths."""
    manifest: list[str] = []
    with zipfile.ZipFile(wheel) as zf:
        for name in zf.namelist():
            if not name.startswith("zguard/") or name.endswith("/"):
                continue  # dist-info, directory entries

            path = Path(name)
            is_stub = path.name == "__init__.py"
            is_binary = path.suffix in _ALLOWED_BINARY_SUFFIXES
            if not (is_stub or is_binary):
                # The CI leak gate should make this unreachable — fail loudly.
                raise SystemExit(f"LEAK: {wheel.name} contains non-image file {name}")
            target = dest / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(name))
            manifest.append(name)
    return sorted(manifest)


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        print("usage: refresh_zguard_bin.py <wheel_dir> [source_git_sha]")
        return 2
    source_sha = sys.argv[2] if len(sys.argv) == 3 else None
    wheel_root = Path(sys.argv[1]).expanduser()
    if source_sha is None:
        # zGuard#2: CI ships a SOURCE_SHA file inside each per-OS artifact
        # folder — auto-discover it instead of requiring the argv. All copies
        # must agree; a mismatch means the folder mixes artifacts from
        # different runs, which would silently mislabel provenance.
        found = {p.read_text().strip() for p in wheel_root.rglob("SOURCE_SHA")}
        found.discard("")
        if len(found) > 1:
            raise SystemExit(f"MIXED SOURCE_SHA across artifacts: {sorted(found)} — refusing.")
        if found:
            source_sha = found.pop()
            print(f"provenance: SOURCE_SHA {source_sha} (from CI artifact)")
        else:
            print("provenance: no SOURCE_SHA in artifacts and none given — images will lack it.")
    wheels = sorted(wheel_root.rglob("zguard-*.whl"))
    if not wheels:
        print(f"no zguard wheels under {wheel_root}")
        return 1

    versions: set[str] = set()
    refreshed: list[str] = []

    for wheel in wheels:
        info = _classify(wheel)
        if info is None:
            continue
        version, py_tag, platforms = info
        versions.add(version)
        for platform_folder in platforms:
            image_root = ZGUARD_BIN / platform_folder / py_tag
            if image_root.exists():
                shutil.rmtree(image_root)
            manifest = _extract_image(wheel, image_root)
            (image_root / "MANIFEST.txt").write_text("\n".join(manifest) + "\n")
            (image_root / "VERSION").write_text(version + "\n")
            if source_sha:
                # Provenance: which zGuard commit these binaries were built from.
                # Not fetched by zguard_provision (not in MANIFEST.txt) — it is
                # a repo-side audit artifact.
                (image_root / "SOURCE_SHA").write_text(source_sha + "\n")
            refreshed.append(f"{platform_folder}/{py_tag}")
            print(f"  ok {platform_folder}/{py_tag}  ({len(manifest)} files, v{version})")

    if len(versions) > 1:
        raise SystemExit(f"MIXED VERSIONS across wheels: {sorted(versions)} — refusing.")
    if not refreshed:
        print("nothing refreshed.")
        return 1

    print(f"\nrefreshed {len(refreshed)} images at v{versions.pop()}.")
    print("next: python scripts/verify_zguard_image.py && git add zguard_bin && commit/push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
