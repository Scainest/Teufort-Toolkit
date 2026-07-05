"""Module 1 — TF2 Spray Generator.

Converts static images / animated GIFs to a .vtf + .vmt pair. Handles
power-of-two sizing with preserved aspect ratio (transparent padding),
and keeps the .vtf under the 512 KB in-game limit by trading resolution
and (for GIFs) frame count.
"""

from __future__ import annotations

import os
import re
import unicodedata
from typing import List, Tuple

from PIL import Image, ImageSequence

from .vtf import (
    IMAGE_FORMAT_DXT1,
    IMAGE_FORMAT_DXT5,
    estimate_vtf_size,
    write_vtf,
)

MAX_FILE_SIZE = 512 * 1024
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif")
_MAX_GIF_FRAMES = 48
_MIN_GIF_FRAMES = 4

VMT_TEMPLATE = '''"LightmappedGeneric"
{{
    "$basetexture" "vgui/logos/{name}"
    "$translucent" 1
}}
'''


def sanitize_spray_name(raw: str) -> str:
    """Filesystem/engine-safe lowercase ascii name."""
    text = unicodedata.normalize("NFKD", raw)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9_\-]+", "_", text).strip("_").lower()
    return text or "spray"


def load_frames(path: str) -> List[Image.Image]:
    """All frames as RGBA (single item for static images)."""
    img = Image.open(path)
    if getattr(img, "is_animated", False):
        return [frame.convert("RGBA") for frame in ImageSequence.Iterator(img)]
    return [img.convert("RGBA")]


def _next_pow2(n: int) -> int:
    p = 1
    while p < n:
        p *= 2
    return p


def fit_to_pow2(img: Image.Image, max_dim: int) -> Image.Image:
    """Scale so the longest edge equals max_dim (aspect preserved), then pad
    each dimension up to the next power of two with transparent pixels."""
    w, h = img.size
    scale = max_dim / max(w, h)
    nw = max(1, round(w * scale))
    nh = max(1, round(h * scale))
    resized = img.resize((nw, nh), Image.LANCZOS)

    cw, ch = max(16, _next_pow2(nw)), max(16, _next_pow2(nh))
    if (cw, ch) == (nw, nh):
        return resized
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    canvas.paste(resized, ((cw - nw) // 2, (ch - nh) // 2))
    return canvas


def _padded_dims(w: int, h: int, max_dim: int) -> Tuple[int, int, bool]:
    """Padded power-of-two output dims and whether padding occurs (padding
    introduces transparent pixels, which forces DXT5)."""
    scale = max_dim / max(w, h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    pw, ph = max(16, _next_pow2(nw)), max(16, _next_pow2(nh))
    return pw, ph, (pw, ph) != (nw, nh)


def _sample_evenly(items: list, count: int) -> list:
    if count >= len(items):
        return items
    step = len(items) / count
    return [items[int(i * step)] for i in range(count)]


def plan_output(src_w: int, src_h: int, frame_count: int, has_alpha: bool,
                max_dim: int = 512) -> Tuple[int, int]:
    """Pick (max_dim, frames_used) so the estimated .vtf stays under 512 KB.
    Padding to power-of-two introduces transparent pixels, so padded outputs
    are costed as DXT5 even when the source itself has no alpha."""
    frames = min(frame_count, _MAX_GIF_FRAMES)

    for dim in (d for d in (512, 256, 128, 64) if d <= max_dim):
        w, h, padded = _padded_dims(src_w, src_h, dim)
        fmt = IMAGE_FORMAT_DXT5 if (has_alpha or padded) else IMAGE_FORMAT_DXT1
        if estimate_vtf_size(w, h, frames, fmt) <= MAX_FILE_SIZE:
            return dim, frames
        # Try shedding frames before dropping resolution.
        lo = _MIN_GIF_FRAMES if frame_count > 1 else 1
        for f in range(frames - 1, lo - 1, -1):
            if estimate_vtf_size(w, h, f, fmt) <= MAX_FILE_SIZE:
                # Only accept heavy frame loss at decent resolutions.
                if f >= min(frame_count, 8) or dim <= 128:
                    return dim, f
                break
    return 64, max(1, min(frames, _MIN_GIF_FRAMES))


def generate_spray(image_path: str, export_dir: str, spray_name: str = "",
                   max_dim: int = 512) -> dict:
    """Full pipeline: load -> plan -> resize -> encode VTF -> write VMT.
    Returns an info dict describing what was produced."""
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Görsel bulunamadı: {image_path}")
    ext = os.path.splitext(image_path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Desteklenmeyen format: {ext} "
                         f"(desteklenen: {', '.join(SUPPORTED_EXTENSIONS)})")

    name = sanitize_spray_name(
        spray_name or os.path.splitext(os.path.basename(image_path))[0]
    )
    frames = load_frames(image_path)

    src_w, src_h = frames[0].size
    has_alpha = any(frame.getextrema()[3][0] < 250 for frame in frames[:3])

    dim, frame_budget = plan_output(src_w, src_h, len(frames), has_alpha, max_dim)
    used = _sample_evenly(frames, frame_budget)
    sized = [fit_to_pow2(frame, dim) for frame in used]

    os.makedirs(export_dir, exist_ok=True)
    vtf_path = os.path.join(export_dir, f"{name}.vtf")
    vmt_path = os.path.join(export_dir, f"{name}.vmt")

    info = write_vtf(sized, vtf_path)
    if info["file_size"] > MAX_FILE_SIZE:  # safety net; should not trigger
        raise RuntimeError(
            f"Çıktı 512KB sınırını aştı ({info['file_size'] // 1024} KB)"
        )

    with open(vmt_path, "w", encoding="ascii") as fh:
        fh.write(VMT_TEMPLATE.format(name=name))

    info.update({
        "name": name,
        "vtf_path": vtf_path,
        "vmt_path": vmt_path,
        "source_frames": len(frames),
    })
    return info
