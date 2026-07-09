"""darkroom — real PIL transforms: grayscale, thumbnail, blur, rotate, sepia.

Same two-surface `photo` shape as zGallery's add_photo (zAgents/src/06_inputs.md
+ zDemos/zGallery/plugins/gallery.py):
  zCLI     — a validated, EXISTING absolute OS path.
  zBifrost — no local disk source, only bytes (base64 envelope or already-
             decoded `data` bytes — see zos_plugin._decode_zfile_kwargs).

Unlike zGallery (store ONE image, show it), every operation here genuinely
rewrites pixels (PIL, not a metadata copy) and every stat this app shows
(dimensions, KB, % smaller) is MEASURED from the real before/after bytes —
that measurement is the whole point of the app.

Declares its own dependency via zRequirements (zEnv.base.zolo: Pillow>=10.0)
instead of the root pyproject.toml — an app-scoped plugin dep, not a zOS
core one. `z requirements zSpark.zDarkroom.zolo` installs it; zSpark refuses
to boot until it's there (see zSys/cli/zspark_command.py).
"""

from pathlib import Path
from io import BytesIO
import base64

from PIL import Image, ImageFilter, ImageOps

from zos_plugin import zfunc

_TABLE = "Processed"
_ORIGINALS_DIR = Path(__file__).resolve().parent.parent / "static" / "originals"
_PROCESSED_DIR = Path(__file__).resolve().parent.parent / "static" / "processed"

# Every operation saves as JPEG regardless of source format/mode — keeps
# palette/CMYK/RGBA handling uniform across all five transforms.
_QUALITY = 88
_OPERATIONS = ("grayscale", "thumbnail", "blur", "rotate_90", "sepia")

# Classic luminosity-weighted sepia: a grayscale value mapped toward this
# warm per-channel tone (fixed tint, not user-tunable — keeps the dialog to
# one field).
_SEPIA_TINT = (255, 240, 192)


def _apply_operation(img: "Image.Image", operation: str) -> "Image.Image":
    if operation == "grayscale":
        return img.convert("L")
    if operation == "thumbnail":
        out = img.copy()
        out.thumbnail((480, 480), Image.Resampling.LANCZOS)
        return out
    if operation == "blur":
        return img.filter(ImageFilter.GaussianBlur(radius=6))
    if operation == "rotate_90":
        return img.rotate(-90, expand=True)
    if operation == "sepia":
        gray = img.convert("L")
        return Image.merge("RGB", tuple(
            gray.point(lambda p, c=channel: min(255, p * c // 255))
            for channel in _SEPIA_TINT
        ))
    raise ValueError(f"Unknown operation: {operation}")


def _read_upload_bytes(photo) -> bytes:
    """Normalize the two `photo` shapes (zCLI path / zBifrost dict) to raw bytes."""
    if isinstance(photo, dict):
        if "data_b64" in photo:
            return base64.b64decode(photo["data_b64"])
        return photo.get("data") or b""
    return Path(photo).read_bytes()


def _source_name(photo) -> str:
    if isinstance(photo, dict):
        return photo.get("filename") or "upload.jpg"
    return Path(photo).name


def _unique_name(directory: Path, stem: str, suffix: str = ".jpg") -> str:
    """Never clobber an existing static file sharing the same stem."""
    name = f"{stem}{suffix}"
    if not (directory / name).exists():
        return name
    n = 2
    while (directory / f"{stem}_{n}{suffix}").exists():
        n += 1
    return f"{stem}_{n}{suffix}"


@zfunc
def process_photo(title, operation, photo, data):
    """Upload + REAL transform in one step — see module docstring."""
    if operation not in _OPERATIONS:
        return "error"

    raw_bytes = _read_upload_bytes(photo)
    if not raw_bytes:
        return "error"

    source = Image.open(BytesIO(raw_bytes))
    source.load()
    source = ImageOps.exif_transpose(source) or source  # camera rotation, once, up front
    ow, oh = source.size

    stem = Path(_source_name(photo)).stem or "photo"
    _ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
    _PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    original_name = _unique_name(_ORIGINALS_DIR, stem)
    original_rgb = source if source.mode in ("RGB", "L") else source.convert("RGB")
    original_rgb.save(_ORIGINALS_DIR / original_name, "JPEG", quality=_QUALITY)
    original_kb = (_ORIGINALS_DIR / original_name).stat().st_size / 1024

    processed = _apply_operation(source, operation)
    if processed.mode not in ("RGB", "L"):
        processed = processed.convert("RGB")
    processed_name = _unique_name(_PROCESSED_DIR, f"{stem}_{operation}")
    processed.save(_PROCESSED_DIR / processed_name, "JPEG", quality=_QUALITY)
    pw, ph = processed.size
    processed_kb = (_PROCESSED_DIR / processed_name).stat().st_size / 1024

    data.insert(_TABLE, {
        "title": title,
        "operation": operation,
        "original_image": f"@.static.originals.{original_name}",
        "processed_image": f"@.static.processed.{processed_name}",
        "original_width": ow,
        "original_height": oh,
        "processed_width": pw,
        "processed_height": ph,
        "original_kb": round(original_kb, 1),
        "processed_kb": round(processed_kb, 1),
    })

    delta = round((1 - processed_kb / original_kb) * 100) if original_kb else 0
    return (
        f"Processed {title}: {ow}x{oh} ({original_kb:.0f}KB) -> "
        f"{pw}x{ph} ({processed_kb:.0f}KB), {delta}% smaller"
    )


@zfunc
def delete_processed(job_id, data):
    """Per-row delete (08_data_crud.md `per_row`) — cleans up BOTH static files."""
    row = data.first(_TABLE, where={"id": job_id})
    if row is None:
        return "error"

    for field, prefix, folder in (
        ("original_image", "@.static.originals.", _ORIGINALS_DIR),
        ("processed_image", "@.static.processed.", _PROCESSED_DIR),
    ):
        path = row.get(field) or ""
        if path.startswith(prefix):
            (folder / path[len(prefix):]).unlink(missing_ok=True)

    data.delete(_TABLE, where={"id": job_id})
    return f"Deleted {row.get('title')}"
