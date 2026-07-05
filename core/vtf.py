"""Pure-Python VTF (Valve Texture Format) writer with numpy-accelerated
DXT1/DXT5 compression. Produces VTF 7.1 files compatible with TF2 sprays.

File layout: 64-byte header, DXT1 low-res thumbnail, then high-res image
data ordered mip-smallest-first, frames in order inside each mip level.
"""

from __future__ import annotations

import struct
from typing import List, Tuple

import numpy as np
from PIL import Image

# --- VTF image format enums ---
IMAGE_FORMAT_DXT1 = 13
IMAGE_FORMAT_DXT5 = 15
IMAGE_FORMAT_BGRA8888 = 12

# --- VTF texture flags ---
FLAG_CLAMPS = 0x0004
FLAG_CLAMPT = 0x0008
FLAG_NOLOD = 0x0200
FLAG_EIGHTBITALPHA = 0x2000

_HEADER_SIZE = 64


# ---------------------------------------------------------------------------
# DXT block compression (vectorized over all 4x4 blocks at once)
# ---------------------------------------------------------------------------

def _to_blocks(img: np.ndarray) -> np.ndarray:
    """(H, W, C) uint8 -> (n_blocks, 16, C) with 4x4 blocks in row-major order.
    Pads dimensions up to a multiple of 4 by edge replication."""
    h, w, c = img.shape
    ph, pw = (-h) % 4, (-w) % 4
    if ph or pw:
        img = np.pad(img, ((0, ph), (0, pw), (0, 0)), mode="edge")
        h, w = img.shape[:2]
    bh, bw = h // 4, w // 4
    return (
        img.reshape(bh, 4, bw, 4, c)
        .transpose(0, 2, 1, 3, 4)
        .reshape(bh * bw, 16, c)
    )


def _pack_565(rgb: np.ndarray) -> np.ndarray:
    """(N, 3) uint8 -> (N,) uint16 RGB565."""
    r = (rgb[:, 0].astype(np.uint16) * 31 + 127) // 255
    g = (rgb[:, 1].astype(np.uint16) * 63 + 127) // 255
    b = (rgb[:, 2].astype(np.uint16) * 31 + 127) // 255
    return (r << 11) | (g << 5) | b


def _unpack_565(c: np.ndarray) -> np.ndarray:
    """(N,) uint16 -> (N, 3) uint8 expanded back to 888."""
    r = ((c >> 11) & 31).astype(np.uint16)
    g = ((c >> 5) & 63).astype(np.uint16)
    b = (c & 31).astype(np.uint16)
    return np.stack(
        [(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], axis=1
    ).astype(np.uint8)


def _encode_color_blocks(rgb_blocks: np.ndarray) -> np.ndarray:
    """(N, 16, 3) uint8 -> (N, 8) uint8: the DXT1 color portion (range fit)."""
    n = rgb_blocks.shape[0]
    lo = rgb_blocks.min(axis=1)  # (N, 3)
    hi = rgb_blocks.max(axis=1)

    c0 = _pack_565(hi)
    c1 = _pack_565(lo)
    # Four-color mode requires c0 > c1; swap where needed.
    swap = c0 < c1
    c0s, c1s = np.where(swap, c1, c0), np.where(swap, c0, c1)

    p0 = _unpack_565(c0s).astype(np.int32)
    p1 = _unpack_565(c1s).astype(np.int32)
    palette = np.stack(
        [p0, p1, (2 * p0 + p1) // 3, (p0 + 2 * p1) // 3], axis=1
    )  # (N, 4, 3)

    diff = rgb_blocks[:, :, None, :].astype(np.int32) - palette[:, None, :, :]
    idx = (diff * diff).sum(axis=3).argmin(axis=2).astype(np.uint32)  # (N, 16)
    idx[c0s == c1s] = 0

    shifts = (2 * np.arange(16, dtype=np.uint32))[None, :]
    bits = (idx << shifts).sum(axis=1, dtype=np.uint32)

    out = np.empty((n, 8), dtype=np.uint8)
    out[:, 0] = c0s & 0xFF
    out[:, 1] = c0s >> 8
    out[:, 2] = c1s & 0xFF
    out[:, 3] = c1s >> 8
    for i in range(4):
        out[:, 4 + i] = (bits >> (8 * i)) & 0xFF
    return out


def _encode_alpha_blocks(a_blocks: np.ndarray) -> np.ndarray:
    """(N, 16) uint8 alpha -> (N, 8) uint8: the DXT5 alpha portion."""
    n = a_blocks.shape[0]
    a0 = a_blocks.max(axis=1).astype(np.int32)  # alpha0 > alpha1 => 8-step mode
    a1 = a_blocks.min(axis=1).astype(np.int32)

    # 8-entry palette: [a0, a1, then 6 interpolated steps]
    steps = np.arange(1, 7, dtype=np.int32)
    interp = ((7 - steps)[None, :] * a0[:, None] + steps[None, :] * a1[:, None]) // 7
    palette = np.concatenate([a0[:, None], a1[:, None], interp], axis=1)  # (N, 8)

    diff = a_blocks[:, :, None].astype(np.int32) - palette[:, None, :]
    codes = np.abs(diff).argmin(axis=2).astype(np.uint64)  # (N, 16)
    codes[a0 == a1] = 0

    shifts = (3 * np.arange(16, dtype=np.uint64))[None, :]
    bits = (codes << shifts).sum(axis=1, dtype=np.uint64)  # 48 bits used

    out = np.empty((n, 8), dtype=np.uint8)
    out[:, 0] = a0.astype(np.uint8)
    out[:, 1] = a1.astype(np.uint8)
    for i in range(6):
        out[:, 2 + i] = ((bits >> np.uint64(8 * i)) & np.uint64(0xFF)).astype(np.uint8)
    return out


def encode_dxt1(rgba: np.ndarray) -> bytes:
    """Compress an (H, W, 4) uint8 array to DXT1 (alpha ignored)."""
    blocks = _to_blocks(rgba[:, :, :3])
    return _encode_color_blocks(blocks).tobytes()


def encode_dxt5(rgba: np.ndarray) -> bytes:
    """Compress an (H, W, 4) uint8 array to DXT5."""
    blocks = _to_blocks(rgba)
    alpha = _encode_alpha_blocks(blocks[:, :, 3])
    color = _encode_color_blocks(blocks[:, :, :3])
    return np.concatenate([alpha, color], axis=1).tobytes()


# ---------------------------------------------------------------------------
# DXT decompression (used for game-accurate previews in the GUI)
# ---------------------------------------------------------------------------

def _from_blocks(blocks: np.ndarray, width: int, height: int) -> np.ndarray:
    """(n_blocks, 16, C) -> (height, width, C), inverse of _to_blocks."""
    bw, bh = max(1, (width + 3) // 4), max(1, (height + 3) // 4)
    c = blocks.shape[2]
    img = (
        blocks.reshape(bh, bw, 4, 4, c)
        .transpose(0, 2, 1, 3, 4)
        .reshape(bh * 4, bw * 4, c)
    )
    return img[:height, :width]


def _decode_color_blocks(arr: np.ndarray):
    """(N, 8) uint8 color blocks -> ((N, 16, 3) uint8 rgb, (N, 16) bool opaque)."""
    n = arr.shape[0]
    c0 = arr[:, 0].astype(np.uint16) | (arr[:, 1].astype(np.uint16) << 8)
    c1 = arr[:, 2].astype(np.uint16) | (arr[:, 3].astype(np.uint16) << 8)
    bits = (arr[:, 4].astype(np.uint32)
            | (arr[:, 5].astype(np.uint32) << 8)
            | (arr[:, 6].astype(np.uint32) << 16)
            | (arr[:, 7].astype(np.uint32) << 24))
    p0 = _unpack_565(c0).astype(np.int32)
    p1 = _unpack_565(c1).astype(np.int32)
    four = (c0 > c1)[:, None]  # (N, 1), broadcasts against (N, 3) palettes
    p2 = np.where(four, (2 * p0 + p1) // 3, (p0 + p1) // 2)
    p3 = np.where(four, (p0 + 2 * p1) // 3, 0)
    palette = np.stack([p0, p1, p2, p3], axis=1).astype(np.uint8)
    shifts = (2 * np.arange(16, dtype=np.uint32))[None, :]
    idx = ((bits[:, None] >> shifts) & 3).astype(np.int64)
    rgb = palette[np.arange(n)[:, None], idx]
    opaque = four | (idx != 3)  # 3-color mode: index 3 means transparent
    return rgb, opaque


def decode_dxt1(data: bytes, width: int, height: int) -> np.ndarray:
    """DXT1 bytes -> (height, width, 4) uint8 RGBA."""
    n = max(1, (width + 3) // 4) * max(1, (height + 3) // 4)
    arr = np.frombuffer(data, dtype=np.uint8, count=n * 8).reshape(n, 8)
    rgb, opaque = _decode_color_blocks(arr)
    alpha = np.where(opaque, 255, 0).astype(np.uint8)[:, :, None]
    return _from_blocks(np.concatenate([rgb, alpha], axis=2), width, height)


def decode_dxt5(data: bytes, width: int, height: int) -> np.ndarray:
    """DXT5 bytes -> (height, width, 4) uint8 RGBA."""
    n = max(1, (width + 3) // 4) * max(1, (height + 3) // 4)
    arr = np.frombuffer(data, dtype=np.uint8, count=n * 16).reshape(n, 16)

    a0 = arr[:, 0].astype(np.int32)
    a1 = arr[:, 1].astype(np.int32)
    abits = np.zeros(n, dtype=np.uint64)
    for i in range(6):
        abits |= arr[:, 2 + i].astype(np.uint64) << np.uint64(8 * i)
    shifts = (3 * np.arange(16, dtype=np.uint64))[None, :]
    codes = ((abits[:, None] >> shifts) & np.uint64(7)).astype(np.int64)

    steps8 = [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
    pal8 = np.stack([a0, a1] + steps8, axis=1)
    steps4 = [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)]
    pal4 = np.stack([a0, a1] + steps4
                    + [np.zeros(n, np.int32), np.full(n, 255, np.int32)], axis=1)
    apal = np.where((a0 > a1)[:, None], pal8, pal4).astype(np.uint8)
    alpha = apal[np.arange(n)[:, None], codes][:, :, None]

    rgb, _ = _decode_color_blocks(arr[:, 8:])
    return _from_blocks(np.concatenate([rgb, alpha], axis=2), width, height)


# ---------------------------------------------------------------------------
# Size math (used by the spray optimizer before any encoding happens)
# ---------------------------------------------------------------------------

def dxt_data_size(width: int, height: int, fmt: int) -> int:
    block = 8 if fmt == IMAGE_FORMAT_DXT1 else 16
    return max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * block


def mip_chain(width: int, height: int) -> List[Tuple[int, int]]:
    """Largest-to-smallest mip dimensions down to 1x1."""
    mips = [(width, height)]
    while width > 1 or height > 1:
        width, height = max(1, width // 2), max(1, height // 2)
        mips.append((width, height))
    return mips


def estimate_vtf_size(width: int, height: int, frame_count: int, fmt: int) -> int:
    thumb_w, thumb_h = min(16, width), min(16, height)
    total = _HEADER_SIZE + dxt_data_size(thumb_w, thumb_h, IMAGE_FORMAT_DXT1)
    for mw, mh in mip_chain(width, height):
        total += dxt_data_size(mw, mh, fmt) * frame_count
    return total


# ---------------------------------------------------------------------------
# VTF writer
# ---------------------------------------------------------------------------

def _build_header(
    width: int,
    height: int,
    frame_count: int,
    fmt: int,
    mip_count: int,
    reflectivity: Tuple[float, float, float],
    thumb_w: int,
    thumb_h: int,
) -> bytes:
    flags = FLAG_CLAMPS | FLAG_CLAMPT | FLAG_NOLOD
    if fmt == IMAGE_FORMAT_DXT5:
        flags |= FLAG_EIGHTBITALPHA

    header = struct.pack(
        "<4sIIIHHIHH4x3f4xfIBIBBx",
        b"VTF\0",
        7, 1,                # version 7.1
        _HEADER_SIZE,
        width, height,
        flags,
        frame_count, 0,      # frames, first frame
        *reflectivity,
        0.0,                 # bumpmap scale
        fmt,
        mip_count,
        IMAGE_FORMAT_DXT1,   # low-res (thumbnail) format
        thumb_w, thumb_h,
    )
    assert len(header) == _HEADER_SIZE
    return header


def write_vtf(frames: List[Image.Image], out_path: str) -> dict:
    """Write RGBA PIL frames (all same power-of-two size) as an animated or
    static VTF. Picks DXT5 when meaningful alpha exists, DXT1 otherwise.
    Returns an info dict (format, size, mip count)."""
    if not frames:
        raise ValueError("En az bir kare gerekli")

    width, height = frames[0].size
    if width & (width - 1) or height & (height - 1):
        raise ValueError(f"Boyutlar 2'nin kuvveti olmali, gelen: {width}x{height}")

    rgba_frames = [
        np.asarray(f.convert("RGBA"), dtype=np.uint8) for f in frames
    ]
    has_alpha = any((arr[:, :, 3] < 250).any() for arr in rgba_frames)
    fmt = IMAGE_FORMAT_DXT5 if has_alpha else IMAGE_FORMAT_DXT1
    encode = encode_dxt5 if has_alpha else encode_dxt1

    mips = mip_chain(width, height)
    mean = rgba_frames[0][:, :, :3].mean(axis=(0, 1)) / 255.0
    reflectivity = (float(mean[0]), float(mean[1]), float(mean[2]))

    thumb_w, thumb_h = min(16, width), min(16, height)
    thumb = frames[0].convert("RGBA").resize((thumb_w, thumb_h), Image.LANCZOS)
    thumb_data = encode_dxt1(np.asarray(thumb, dtype=np.uint8))

    # Pre-resize every frame at every mip level (smallest mip written first).
    pil_frames = [f.convert("RGBA") for f in frames]
    chunks = [
        _build_header(width, height, len(frames), fmt, len(mips),
                      reflectivity, thumb_w, thumb_h),
        thumb_data,
    ]
    for mw, mh in reversed(mips):
        for frame in pil_frames:
            level = frame if (mw, mh) == (width, height) else frame.resize(
                (mw, mh), Image.LANCZOS
            )
            chunks.append(encode(np.asarray(level, dtype=np.uint8)))

    data = b"".join(chunks)
    with open(out_path, "wb") as fh:
        fh.write(data)

    return {
        "format": "DXT5" if has_alpha else "DXT1",
        "width": width,
        "height": height,
        "frames": len(frames),
        "mips": len(mips),
        "file_size": len(data),
    }
