#!/usr/bin/env python3
"""Pre-publish gate for the bundled zGuard binary image.

zOS-OpenCore is public and ships a COMPILED image of the private zGuard runtime
(`zguard/`). Only `.so` binaries + package `__init__.py` shims may live there.
Any module shipped as source (`.py` with no `.so`), or any Cython intermediate
(`.c`/`.pyx`/`.pxd`), is an IP leak — the open repo must never expose the
secret-sauce source (chunking / bifrost / wizard / auth).

Run before every image refresh / publish:

    python scripts/verify_zguard_image.py

Exit 0 = image is pure. Exit 1 = leak detected (do NOT publish).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Live layout: zguard_bin/<platform-tag>/<py-tag>/zguard/ (one image per ABI).
ZGUARD_BIN = Path(__file__).resolve().parent.parent / "zguard_bin"

# Source intermediates that must never ship in the public image.
FORBIDDEN_SUFFIXES = (".c", ".pyx", ".pxd", ".pyi")

# Package initializers are allowed as source (they only wire/re-export the
# compiled submodules). Everything else must be compiled to .so.
ALLOWED_SOURCE_NAMES = {"__init__.py"}


def _so_sibling(py_path: Path) -> bool:
    """True if a compiled sibling exists for this .py module (any ABI tag)."""
    stem = py_path.stem  # e.g. bridge_connection
    return any(p.name.startswith(stem + ".") and p.suffix == ".so"
               for p in py_path.parent.glob(f"{stem}.*.so"))


def _check_image(image_root: Path) -> list[str]:
    """Return leak descriptions for one <platform>/<py>/zguard image."""
    leaks: list[str] = []
    for path in image_root.rglob("*"):
        if "__pycache__" in path.parts or not path.is_file():
            continue
        rel = path.relative_to(image_root.parent)
        if path.suffix in FORBIDDEN_SUFFIXES:
            leaks.append(f"[cython source] {rel}")
        elif path.suffix == ".py" and path.name not in ALLOWED_SOURCE_NAMES:
            if not _so_sibling(path):
                leaks.append(f"[orphan source] {rel}  (no .so sibling)")
    return leaks


def main() -> int:
    images = sorted(ZGUARD_BIN.glob("*/*/zguard"))
    if not images:
        print(f"verify-image: no images under {ZGUARD_BIN} — nothing to check.")
        return 0

    all_leaks: list[str] = []
    for image in images:
        leaks = _check_image(image)
        tag = f"{image.parent.parent.name}/{image.parent.name}"
        if leaks:
            all_leaks.extend(f"{tag}: {leak}" for leak in leaks)
        else:
            print(f"verify-image: OK — {tag} is a pure binary image.")

    if not all_leaks:
        return 0

    print("\nverify-image: LEAK DETECTED — do NOT publish.\n")
    for leak in all_leaks:
        print(f"  {leak}")
    print(
        "\nFix: rebuild the images from CI wheels with\n"
        "  python scripts/refresh_zguard_bin.py <wheel-folder>\n"
        "(do not hand-copy individual modules — that is how source leaks in)."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
