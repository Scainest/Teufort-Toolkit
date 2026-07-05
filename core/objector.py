"""Module 2 — Full-Color Conscientious Objector maker.

Crops the chosen square region, resizes to a square power-of-two size and
saves it as paper_overlay.png inside the correct decal-replacement path:

    <custom folder>/scripts/items/custom_texture_blend_layers/paper_overlay.png

This is the path the game actually reads for the Conscientious Objector's
decal layer — the earlier `materials/...` path did NOT work (the image never
became full color). The PNG is written as a clean 8-bit RGBA file with no
ICC/gamma/EXIF chunks so the engine picks it up unmodified.

Resolution: the classic guides use 128x128 (the original template size, the
safest for the async-load exploit). Higher sizes (256/512) look noticeably
less pixelated and work on most setups, so they are offered as options with
128 kept as the guaranteed-compatible fallback.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

from PIL import Image

from .paths import resolve_target_dir

DEFAULT_SIZE = 256
COMPATIBLE_SIZE = 128
ALLOWED_SIZES = (128, 256, 512)
# Correct decal-replacement path for the CO (relative to the custom folder).
RELATIVE_DIR = os.path.join("scripts", "items", "custom_texture_blend_layers")
OUTPUT_NAME = "paper_overlay.png"
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif")


def default_crop_box(width: int, height: int) -> Tuple[int, int, int, int]:
    """Centered maximal square crop (left, top, right, bottom)."""
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return (left, top, left + side, top + side)


def clamp_square_box(
    width: int, height: int, box: Tuple[int, int, int, int]
) -> Tuple[int, int, int, int]:
    """Clamp a crop box into the image and force it exactly square."""
    left, top, right, bottom = (int(round(v)) for v in box)
    left = max(0, min(left, width - 1))
    top = max(0, min(top, height - 1))
    right = max(left + 1, min(right, width))
    bottom = max(top + 1, min(bottom, height))
    if (right - left) != (bottom - top):
        side = min(right - left, bottom - top)
        right, bottom = left + side, top + side
    return left, top, right, bottom


def crop_to_overlay(
    img: Image.Image,
    crop_box: Optional[Tuple[int, int, int, int]] = None,
    size: int = DEFAULT_SIZE,
) -> Image.Image:
    """Crop + resize to the final square RGBA decal (used by the live preview
    and by the exporter)."""
    img = img.convert("RGBA")
    box = clamp_square_box(img.width, img.height,
                           crop_box or default_crop_box(*img.size))
    return img.crop(box).resize((size, size), Image.LANCZOS)


def make_paper_overlay(
    image_path: str,
    export_dir: str,
    crop_box: Optional[Tuple[int, int, int, int]] = None,
    size: int = DEFAULT_SIZE,
) -> dict:
    """Crop + resize + save. `export_dir` is the user's custom mod folder
    (e.g. .../tf/custom/MyMod); subfolders are created automatically."""
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Görsel bulunamadı: {image_path}")
    if size not in ALLOWED_SIZES:
        size = DEFAULT_SIZE

    img = Image.open(image_path)
    img.load()
    img = img.convert("RGBA")

    left, top, right, bottom = clamp_square_box(
        img.width, img.height, crop_box or default_crop_box(*img.size))
    final = crop_to_overlay(img, (left, top, right, bottom), size)

    # Re-create the image from raw pixels: guarantees a plain 8-bit RGBA PNG
    # with no inherited ICC profile, gamma or EXIF chunks.
    clean = Image.new("RGBA", final.size)
    clean.putdata(list(final.getdata()))

    # If the user already browsed into (part of) scripts/items/... don't
    # duplicate the chain — write straight into the correct folder.
    target_dir = resolve_target_dir(export_dir, RELATIVE_DIR)
    os.makedirs(target_dir, exist_ok=True)
    out_path = os.path.join(target_dir, OUTPUT_NAME)
    clean.save(out_path, format="PNG", optimize=True)

    return {
        "output_path": out_path,
        "crop_box": (left, top, right, bottom),
        "size": (size, size),
    }
