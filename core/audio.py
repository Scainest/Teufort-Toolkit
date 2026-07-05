"""Module 3 — Hitsound / Killsound trimmer.

Loads .mp3/.wav/.ogg (via libsndfile bundled with the soundfile package),
trims to a selection, resamples to exactly 44100 Hz 16-bit PCM (mono or
stereo preserved, >2 channels downmixed to stereo) and writes
sound/ui/hitsound.wav or sound/ui/killsound.wav under the chosen folder.
"""

from __future__ import annotations

import math
import os
from typing import Tuple

import numpy as np
import soundfile as sf

from .paths import resolve_target_dir

TARGET_SAMPLE_RATE = 44100
RELATIVE_DIR = os.path.join("sound", "ui")
SUPPORTED_EXTENSIONS = (".mp3", ".wav", ".ogg", ".flac")
EXPORT_NAMES = {"hitsound": "hitsound.wav", "killsound": "killsound.wav"}


def load_audio(path: str) -> Tuple[np.ndarray, int]:
    """Return (float32 samples shaped (n, channels), sample_rate)."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Ses dosyası bulunamadı: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Desteklenmeyen format: {ext} "
                         f"(desteklenen: {', '.join(SUPPORTED_EXTENSIONS)})")
    try:
        data, sr = sf.read(path, dtype="float32", always_2d=True)
    except Exception as exc:
        raise ValueError(f"Ses dosyası okunamadı ({os.path.basename(path)}): {exc}")
    if data.size == 0:
        raise ValueError("Ses dosyası boş")
    return data, sr


def duration_seconds(data: np.ndarray, sample_rate: int) -> float:
    return data.shape[0] / float(sample_rate)


def waveform_envelope(data: np.ndarray, columns: int) -> np.ndarray:
    """Per-pixel-column (min, max) envelope of the mono mix, shape (columns, 2).
    Used by the GUI to draw the waveform."""
    mono = data.mean(axis=1)
    n = len(mono)
    columns = max(1, min(columns, n))
    edges = np.linspace(0, n, columns + 1).astype(np.int64)
    env = np.empty((columns, 2), dtype=np.float32)
    for i in range(columns):
        chunk = mono[edges[i]:max(edges[i] + 1, edges[i + 1])]
        env[i, 0] = chunk.min()
        env[i, 1] = chunk.max()
    return env


def _sinc_resample(data: np.ndarray, src_rate: int, dst_rate: int,
                   taps: int = 32) -> np.ndarray:
    """Windowed-sinc (Hann) resampler in pure numpy. Quality is close to
    scipy's polyphase filter; used in the frozen build where scipy is
    excluded to keep the .exe small."""
    ratio = dst_rate / src_rate
    n_in = data.shape[0]
    n_out = int(round(n_in * ratio))
    half = taps // 2
    cutoff = min(1.0, ratio) * 0.945
    offsets = np.arange(-half + 1, half + 1)
    padded = np.pad(data.astype(np.float64), ((half, half), (0, 0)),
                    mode="edge")
    out = np.empty((n_out, data.shape[1]), dtype=np.float64)
    for start in range(0, n_out, 65536):  # chunked: bounds the temp matrices
        stop = min(start + 65536, n_out)
        pos = np.arange(start, stop) / ratio
        base = np.floor(pos).astype(np.int64)
        x = offsets[None, :] - (pos - base)[:, None]  # tap distances (m, taps)
        window = 0.5 * (1.0 + np.cos(np.pi * x / half))
        kernel = cutoff * np.sinc(cutoff * x) * window
        kernel /= kernel.sum(axis=1, keepdims=True)   # exact DC gain
        idx = base[:, None] + offsets[None, :] + half
        for c in range(data.shape[1]):
            out[start:stop, c] = (padded[idx, c] * kernel).sum(axis=1)
    return out


def _resample(data: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate:
        return data
    try:
        from scipy.signal import resample_poly
        g = math.gcd(src_rate, dst_rate)
        return resample_poly(data, dst_rate // g, src_rate // g, axis=0)
    except ImportError:
        return _sinc_resample(data, src_rate, dst_rate)


def process_selection(
    data: np.ndarray,
    sample_rate: int,
    start_s: float,
    end_s: float,
    fade_ms: float = 3.0,
) -> np.ndarray:
    """Trim, downmix >2ch to stereo, resample to 44100 Hz and return float32
    in [-1, 1]. A tiny fade at both edges avoids clicks at the cut points."""
    total = duration_seconds(data, sample_rate)
    start_s = max(0.0, min(start_s, total))
    end_s = max(start_s, min(end_s, total))
    i0, i1 = int(start_s * sample_rate), int(end_s * sample_rate)
    if i1 - i0 < 2:
        raise ValueError("Seçilen aralık çok kısa")
    segment = data[i0:i1].copy()

    if segment.shape[1] > 2:  # downmix surround to stereo
        left = segment[:, 0::2].mean(axis=1)
        right = segment[:, 1::2].mean(axis=1)
        segment = np.stack([left, right], axis=1)

    segment = _resample(segment, sample_rate, TARGET_SAMPLE_RATE)

    fade = int(TARGET_SAMPLE_RATE * fade_ms / 1000.0)
    if 0 < fade < segment.shape[0] // 2:
        ramp = np.linspace(0.0, 1.0, fade)[:, None]
        segment[:fade] *= ramp
        segment[-fade:] *= ramp[::-1]

    peak = np.abs(segment).max()
    if peak > 1.0:  # only prevent clipping, don't touch otherwise
        segment = segment / peak
    return segment.astype(np.float32)


def export_sound(
    data: np.ndarray,
    sample_rate: int,
    start_s: float,
    end_s: float,
    export_dir: str,
    kind: str,
) -> dict:
    """kind: 'hitsound' or 'killsound'. Writes 44100 Hz 16-bit PCM .wav."""
    if kind not in EXPORT_NAMES:
        raise ValueError(f"Geçersiz tür: {kind}")
    segment = process_selection(data, sample_rate, start_s, end_s)

    # Same anti-duplication logic as the objector: if the user browsed into
    # (part of) sound/ui already, don't append the chain twice.
    target_dir = resolve_target_dir(export_dir, RELATIVE_DIR)
    os.makedirs(target_dir, exist_ok=True)
    out_path = os.path.join(target_dir, EXPORT_NAMES[kind])
    sf.write(out_path, segment, TARGET_SAMPLE_RATE, subtype="PCM_16")

    return {
        "output_path": out_path,
        "duration": segment.shape[0] / TARGET_SAMPLE_RATE,
        "channels": segment.shape[1],
        "sample_rate": TARGET_SAMPLE_RATE,
    }
