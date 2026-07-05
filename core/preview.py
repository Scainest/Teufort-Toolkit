"""In-app "how will it look in game" renderers.

Spray: runs the real pipeline (power-of-two resize + DXT encode + decode)
so the preview shows genuine compression artifacts, then composes the
result on a concrete-wall background.

Objector: renders the 128x128 decal onto a wooden picket-sign mockup.
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw

from . import spray as spray_mod
from .vtf import (
    IMAGE_FORMAT_DXT1,
    IMAGE_FORMAT_DXT5,
    decode_dxt1,
    decode_dxt5,
    encode_dxt1,
    encode_dxt5,
    estimate_vtf_size,
)

_wall_cache: dict = {}


def spray_game_preview(frames: List[Image.Image],
                       max_dim: int = 512) -> Tuple[List[Image.Image], dict]:
    """Apply the exact spray pipeline (plan -> resize -> DXT round-trip) and
    return the decoded frames plus an info dict with the estimated file size."""
    src_w, src_h = frames[0].size
    has_alpha = any(f.getextrema()[3][0] < 250 for f in frames[:3])
    dim, budget = spray_mod.plan_output(src_w, src_h, len(frames),
                                        has_alpha, max_dim)
    used = spray_mod._sample_evenly(frames, budget)
    sized = [spray_mod.fit_to_pow2(f, dim) for f in used]
    arrs = [np.asarray(f.convert("RGBA"), dtype=np.uint8) for f in sized]

    alpha = any((a[:, :, 3] < 250).any() for a in arrs)
    w, h = sized[0].size
    if alpha:
        decoded = [decode_dxt5(encode_dxt5(a), w, h) for a in arrs]
        fmt_name, fmt = "DXT5", IMAGE_FORMAT_DXT5
    else:
        decoded = [decode_dxt1(encode_dxt1(a), w, h) for a in arrs]
        fmt_name, fmt = "DXT1", IMAGE_FORMAT_DXT1

    info = {
        "width": w,
        "height": h,
        "format": fmt_name,
        "frames": len(decoded),
        "est_size": estimate_vtf_size(w, h, len(decoded), fmt),
    }
    return [Image.fromarray(a) for a in decoded], info


def _wall(size: int) -> Image.Image:
    """Flat concrete wall with subtle noise and panel seams."""
    if size in _wall_cache:
        return _wall_cache[size]
    rng = np.random.default_rng(42)
    base = np.full((size, size, 3), (126, 122, 112), dtype=np.float32)
    base += rng.normal(0.0, 4.5, (size, size, 1))
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(img)
    for y in (size // 3, 2 * size // 3):
        d.line([(0, y), (size, y)], fill=(104, 100, 92), width=2)
    d.line([(size // 2, 0), (size // 2, size // 3)], fill=(104, 100, 92), width=2)
    d.line([(size // 4, size // 3), (size // 4, 2 * size // 3)],
           fill=(104, 100, 92), width=2)
    _wall_cache[size] = img
    return img


def compose_on_wall(spray_img: Image.Image, size: int = 260) -> Image.Image:
    """Spray pasted (with alpha) on the concrete wall, like in game."""
    wall = _wall(size).copy()
    decal = spray_img.convert("RGBA").copy()
    decal.thumbnail((size - 24, size - 24), Image.LANCZOS)
    wall.paste(decal, ((size - decal.width) // 2,
                       (size - decal.height) // 2), decal)
    return wall.convert("RGBA")


def objector_sign_mockup(decal_128: Image.Image,
                         out_size: Tuple[int, int] = (190, 220)) -> Image.Image:
    """Conscientious Objector-style picket sign holding the decal.
    Rendered at 2x and downscaled for clean edges."""
    W, H = out_size[0] * 2, out_size[1] * 2
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    board = int(W * 0.79)
    bx0, by0 = (W - board) // 2, int(H * 0.05)
    stick_w = max(14, W // 13)
    sx = W // 2
    d.rounded_rectangle(
        [sx - stick_w // 2, by0 + board - 8, sx + stick_w // 2, H - 10],
        radius=6, fill=(122, 89, 55, 255), outline=(74, 54, 32, 255), width=3)

    d.rectangle([bx0, by0, bx0 + board, by0 + board],
                fill=(232, 220, 196, 255), outline=(74, 54, 32, 255), width=8)
    inset = 16
    decal = decal_128.convert("RGBA").resize(
        (board - 2 * inset, board - 2 * inset), Image.LANCZOS)
    img.paste(decal, (bx0 + inset, by0 + inset), decal)

    r = 5
    for nx, ny in ((bx0 + 14, by0 + 14), (bx0 + board - 14, by0 + 14),
                   (bx0 + 14, by0 + board - 14),
                   (bx0 + board - 14, by0 + board - 14)):
        d.ellipse([nx - r, ny - r, nx + r, ny + r], fill=(78, 66, 52, 255))

    rot = img.rotate(-5, resample=Image.BICUBIC, expand=True)
    canvas = Image.new("RGBA", (rot.width + 14, rot.height + 16), (0, 0, 0, 0))
    shadow = Image.new("RGBA", rot.size, (0, 0, 0, 255))
    shadow.putalpha(rot.split()[3].point(lambda a: a * 30 // 100))
    canvas.paste(shadow, (10, 14), shadow)
    canvas.paste(rot, (0, 0), rot)
    return canvas.resize(out_size, Image.LANCZOS)
