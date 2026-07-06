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

IMAGE_ROOT = Path(__file__).resolve().parent.parent / "zguard"

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


def main() -> int:
    if not IMAGE_ROOT.is_dir():
        print(f"verify-image: no image at {IMAGE_ROOT} — nothing to check.")
        return 0

    orphans: list[Path] = []
    intermediates: list[Path] = []

    for path in IMAGE_ROOT.rglob("*"):
        if "__pycache__" in path.parts or not path.is_file():
            continue
        if path.suffix in FORBIDDEN_SUFFIXES:
            intermediates.append(path)
        elif path.suffix == ".py" and path.name not in ALLOWED_SOURCE_NAMES:
            if not _so_sibling(path):
                orphans.append(path)

    leaks = orphans + intermediates
    if not leaks:
        print(f"verify-image: OK — {IMAGE_ROOT.name}/ is a pure binary image.")
        return 0

    print("verify-image: LEAK DETECTED — do NOT publish.\n")
    for p in orphans:
        print(f"  [orphan source] {p.relative_to(IMAGE_ROOT.parent)}  (no .so sibling)")
    for p in intermediates:
        print(f"  [cython source] {p.relative_to(IMAGE_ROOT.parent)}")
    print(
        "\nFix: regenerate the image by copying the WHOLE build output\n"
        "  zGuard/build/lib.*/zguard/  →  zOS-OpenCore/zguard/\n"
        "(do not hand-copy individual modules — that is how source leaks in)."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
