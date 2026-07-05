"""Self-contained validation of the core modules (no pytest needed):
    python tests/test_core.py
Includes an independent VTF header parser and DXT1/DXT5 decoder so the
encoder is verified by round-trip PSNR, not just by "it didn't crash".
"""

import math
import os
import struct
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import audio, objector, spray, vtf  # noqa: E402


# --------------------------- reference DXT decoder -------------------------

def _expand565(c):
    r, g, b = (c >> 11) & 31, (c >> 5) & 63, c & 31
    return np.array([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)],
                    dtype=np.int32)


def decode_dxt(data: bytes, w: int, h: int, fmt: int) -> np.ndarray:
    """Minimal DXT1/DXT5 decoder returning (h, w, 4) uint8."""
    bs = 8 if fmt == vtf.IMAGE_FORMAT_DXT1 else 16
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    out = np.zeros((bh * 4, bw * 4, 4), dtype=np.uint8)
    out[:, :, 3] = 255
    pos = 0
    for by in range(bh):
        for bx in range(bw):
            block = data[pos:pos + bs]
            pos += bs
            if fmt == vtf.IMAGE_FORMAT_DXT5:
                a0, a1 = block[0], block[1]
                abits = int.from_bytes(block[2:8], "little")
                apal = [a0, a1] + (
                    [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
                    if a0 > a1 else
                    [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]
                )
                cblock = block[8:]
            else:
                cblock = block
            c0, c1 = struct.unpack_from("<HH", cblock, 0)
            bits = struct.unpack_from("<I", cblock, 4)[0]
            p0, p1 = _expand565(c0), _expand565(c1)
            if c0 > c1:
                pal = [p0, p1, (2 * p0 + p1) // 3, (p0 + 2 * p1) // 3]
            else:
                pal = [p0, p1, (p0 + p1) // 2, np.zeros(3, dtype=np.int32)]
            for i in range(16):
                px, py = bx * 4 + i % 4, by * 4 + i // 4
                out[py, px, :3] = pal[(bits >> (2 * i)) & 3]
                if fmt == vtf.IMAGE_FORMAT_DXT5:
                    out[py, px, 3] = apal[(abits >> (3 * i)) & 7]
    return out[:h, :w]


def parse_vtf(path: str) -> dict:
    with open(path, "rb") as fh:
        raw = fh.read()
    (sig, vmaj, vmin, hsize, w, h, flags, frames, first) = struct.unpack_from(
        "<4sIIIHHIHH", raw, 0)
    refl = struct.unpack_from("<3f", raw, 32)
    fmt, mips = struct.unpack_from("<IB", raw, 52)
    lofmt, low, loh = struct.unpack_from("<IBB", raw, 57)
    assert sig == b"VTF\0", "kotu imza"
    assert (vmaj, vmin) == (7, 1)
    assert hsize == 64
    info = dict(w=w, h=h, flags=flags, frames=frames, fmt=fmt, mips=mips,
                lofmt=lofmt, low=low, loh=loh, refl=refl, total=len(raw))
    # structural size check
    expected = 64 + vtf.dxt_data_size(low, loh, vtf.IMAGE_FORMAT_DXT1)
    for mw, mh in vtf.mip_chain(w, h):
        expected += vtf.dxt_data_size(mw, mh, fmt) * frames
    assert expected == len(raw), f"boyut uyusmadi: {expected} != {len(raw)}"
    # largest mip of frame 0 starts at: header + thumb + all smaller mips
    offset = 64 + vtf.dxt_data_size(low, loh, vtf.IMAGE_FORMAT_DXT1)
    for mw, mh in reversed(vtf.mip_chain(w, h)[1:]):
        offset += vtf.dxt_data_size(mw, mh, fmt) * frames
    info["top_mip_offset"] = offset
    return info


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    return 99.0 if mse == 0 else 10 * math.log10(255.0 ** 2 / mse)


# --------------------------------- tests -----------------------------------

def make_test_photo(w, h):
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        for x in range(0, w, 4):
            d.rectangle([x, y, x + 3, y], fill=(x * 255 // w, y * 255 // h, 128))
    d.ellipse([w // 4, h // 4, 3 * w // 4, 3 * h // 4], fill=(255, 40, 40))
    return img


def test_dxt_roundtrip(tmp):
    img = make_test_photo(128, 128).convert("RGBA")
    arr = np.asarray(img)
    enc1 = vtf.encode_dxt1(arr)
    dec1 = decode_dxt(enc1, 128, 128, vtf.IMAGE_FORMAT_DXT1)
    q1 = psnr(arr[:, :, :3], dec1[:, :, :3])
    arr2 = arr.copy()
    arr2[:, :, 3] = np.linspace(0, 255, 128).astype(np.uint8)[None, :]
    enc5 = vtf.encode_dxt5(arr2)
    dec5 = decode_dxt(enc5, 128, 128, vtf.IMAGE_FORMAT_DXT5)
    q5 = psnr(arr2[:, :, :3], dec5[:, :, :3])
    qa = psnr(arr2[:, :, 3], dec5[:, :, 3])
    print(f"  DXT1 PSNR={q1:.1f}dB  DXT5 renk={q5:.1f}dB alfa={qa:.1f}dB")
    assert q1 > 25 and q5 > 25 and qa > 30, "DXT kalitesi cok dusuk"
    # vectorized decoders in vtf.py must agree with this reference decoder
    assert np.array_equal(vtf.decode_dxt1(enc1, 128, 128), dec1)
    assert np.array_equal(vtf.decode_dxt5(enc5, 128, 128), dec5)


def test_preview(tmp):
    from core import preview
    frames = []
    for i in range(12):
        f = Image.new("RGBA", (200, 150), (i * 20 % 255, 90, 160, 255))
        frames.append(f)
    decoded, info = preview.spray_game_preview(frames, max_dim=256)
    assert len(decoded) == info["frames"] >= 4
    assert decoded[0].size == (info["width"], info["height"])
    assert info["format"] in ("DXT1", "DXT5")
    assert info["est_size"] <= spray.MAX_FILE_SIZE
    wall = preview.compose_on_wall(decoded[0], 260)
    assert wall.size == (260, 260)
    sign = preview.objector_sign_mockup(
        make_test_photo(128, 128).convert("RGBA"), (190, 220))
    assert sign.size == (190, 220)
    print(f"  onizleme: {info['width']}x{info['height']} {info['format']} "
          f"{info['frames']} kare, tabela {sign.size}")


def test_static_spray(tmp):
    src = os.path.join(tmp, "photo.jpg")
    make_test_photo(640, 480).save(src, quality=90)
    info = spray.generate_spray(src, os.path.join(tmp, "out1"))
    print(f"  statik: {info['width']}x{info['height']} {info['format']} "
          f"{info['file_size']//1024}KB mips={info['mips']}")
    meta = parse_vtf(info["vtf_path"])
    assert info["file_size"] <= spray.MAX_FILE_SIZE
    assert meta["frames"] == 1
    assert (meta["w"], meta["h"]) == (512, 512)  # 480->512 pad
    # decode top mip, compare with an independent resize of the source
    with open(info["vtf_path"], "rb") as fh:
        raw = fh.read()
    dec = decode_dxt(raw[meta["top_mip_offset"]:], meta["w"], meta["h"], meta["fmt"])
    ref = np.asarray(spray.fit_to_pow2(Image.open(src).convert("RGBA"), 512))
    q = psnr(ref[:, :, :3][ref[:, :, 3] > 0], dec[:, :, :3][ref[:, :, 3] > 0])
    print(f"  statik roundtrip PSNR={q:.1f}dB")
    assert q > 25
    assert os.path.isfile(info["vmt_path"])
    content = open(info["vmt_path"]).read()
    assert '"$basetexture" "vgui/logos/photo"' in content
    assert '"$translucent" 1' in content


def test_animated_spray(tmp):
    frames = []
    for i in range(40):
        f = Image.new("RGB", (300, 300), (i * 6 % 255, 30, 200))
        d = ImageDraw.Draw(f)
        d.ellipse([i * 3, i * 3, i * 3 + 80, i * 3 + 80], fill=(255, 255, 0))
        frames.append(f)
    src = os.path.join(tmp, "anim.gif")
    frames[0].save(src, save_all=True, append_images=frames[1:], duration=50)
    info = spray.generate_spray(src, os.path.join(tmp, "out2"))
    print(f"  gif: {info['width']}x{info['height']} {info['format']} "
          f"kare={info['frames']}/{info['source_frames']} "
          f"{info['file_size']//1024}KB")
    meta = parse_vtf(info["vtf_path"])
    assert info["file_size"] <= spray.MAX_FILE_SIZE
    assert meta["frames"] == info["frames"] > 1


def test_size_planner(tmp):
    for (w, h, n, alpha) in [(4000, 3000, 1, False), (500, 500, 200, True),
                             (128, 128, 10, True), (1920, 1080, 60, False),
                             (300, 300, 1, False), (512, 8, 5, False)]:
        dim, fr = spray.plan_output(w, h, n, alpha)
        pw, ph, padded = spray._padded_dims(w, h, dim)
        fmt = (vtf.IMAGE_FORMAT_DXT5 if (alpha or padded)
               else vtf.IMAGE_FORMAT_DXT1)
        est = vtf.estimate_vtf_size(pw, ph, fr, fmt)
        print(f"  plan {w}x{h}x{n} -> {dim}px {fr} kare ~{est//1024}KB")
        assert est <= spray.MAX_FILE_SIZE


def test_objector(tmp):
    src = os.path.join(tmp, "art.png")
    make_test_photo(500, 300).save(src)
    out = objector.make_paper_overlay(src, os.path.join(tmp, "mod"))
    # correct decal-replacement path: scripts/items/... (NOT materials/...)
    expected = os.path.join(tmp, "mod", "scripts", "items",
                            "custom_texture_blend_layers", "paper_overlay.png")
    assert os.path.normpath(out["output_path"]) == os.path.normpath(expected)
    assert not os.path.exists(os.path.join(tmp, "mod", "materials"))
    img = Image.open(expected)
    assert img.size == (256, 256) and img.mode == "RGBA"  # default size
    assert "icc_profile" not in img.info and "gamma" not in img.info
    # each allowed size round-trips to a square PNG of that size
    for i, sz in enumerate(objector.ALLOWED_SIZES):
        o = objector.make_paper_overlay(src, os.path.join(tmp, f"s{i}"),
                                        size=sz)
        assert Image.open(o["output_path"]).size == (sz, sz)
        assert o["output_path"].endswith(
            os.path.join("scripts", "items",
                         "custom_texture_blend_layers", "paper_overlay.png"))
    # unknown size falls back to the default, not a crash
    o = objector.make_paper_overlay(src, os.path.join(tmp, "sx"), size=999)
    assert Image.open(o["output_path"]).size == (objector.DEFAULT_SIZE,
                                                 objector.DEFAULT_SIZE)
    # custom crop box
    out2 = objector.make_paper_overlay(src, os.path.join(tmp, "mod2"),
                                       crop_box=(10, 10, 210, 210), size=128)
    assert Image.open(out2["output_path"]).size == (128, 128)
    print(f"  objector: {out['output_path']}")


def test_path_dedup(tmp):
    """Selecting a folder that already contains (part of) the subpath must
    not duplicate the chain."""
    from core.paths import resolve_target_dir
    rel = objector.RELATIVE_DIR  # scripts/items/custom_texture_blend_layers
    leaf = os.path.join("scripts", "items", "custom_texture_blend_layers")

    cases = {
        # plain custom folder -> full chain appended
        os.path.join("C:\\", "tf", "custom", "Mod"):
            os.path.join("C:\\", "tf", "custom", "Mod", leaf),
        # already the full deep folder -> no duplication
        os.path.join("C:\\", "tf", "custom", "Mod", leaf):
            os.path.join("C:\\", "tf", "custom", "Mod", leaf),
        # partial: ends with scripts/items -> only leaf part added
        os.path.join("C:\\", "tf", "custom", "Mod", "scripts", "items"):
            os.path.join("C:\\", "tf", "custom", "Mod", leaf),
        # partial: ends with scripts -> rest added
        os.path.join("C:\\", "tf", "custom", "Mod", "scripts"):
            os.path.join("C:\\", "tf", "custom", "Mod", leaf),
    }
    for given, expect in cases.items():
        got = resolve_target_dir(given, rel)
        assert os.path.normpath(got) == os.path.normpath(expect), \
            f"{given} -> {got} (beklenen {expect})"

    # case-insensitive tail match (Windows)
    upper = os.path.join("C:\\", "tf", "custom", "Mod", "Scripts", "Items",
                         "Custom_Texture_Blend_Layers")
    assert resolve_target_dir(upper, rel).lower().count("custom_texture_blend_layers") == 1

    # end-to-end: real save into an already-deep folder writes exactly one file
    src = os.path.join(tmp, "p.png")
    make_test_photo(200, 200).save(src)
    deep = os.path.join(tmp, "ModX", leaf)
    os.makedirs(deep, exist_ok=True)
    info = objector.make_paper_overlay(src, deep, size=128)
    assert os.path.normpath(info["output_path"]) == \
        os.path.normpath(os.path.join(deep, "paper_overlay.png"))
    # no nested duplicate anywhere under ModX
    nested = os.path.join(deep, "scripts")
    assert not os.path.exists(nested), "alt yol tekrar kopyalanmis!"

    # audio module shares the same logic
    import numpy as np
    import soundfile as sf
    tone = (np.sin(np.linspace(0, 100, 44100)) * 0.3).astype(np.float32)[:, None]
    wav = os.path.join(tmp, "t.wav")
    sf.write(wav, tone, 44100)
    data, sr = audio.load_audio(wav)
    deep_snd = os.path.join(tmp, "ModS", "sound", "ui")
    os.makedirs(deep_snd, exist_ok=True)
    sinfo = audio.export_sound(data, sr, 0.0, 0.5, deep_snd, "hitsound")
    assert os.path.normpath(sinfo["output_path"]) == \
        os.path.normpath(os.path.join(deep_snd, "hitsound.wav"))
    assert not os.path.exists(os.path.join(deep_snd, "sound"))
    print("  yol tekrarlama korumasi: OK (objector + ses)")


def test_audio(tmp):
    import soundfile as sf
    sr = 48000
    t = np.linspace(0, 2.0, 2 * sr, endpoint=False)
    wave = np.stack([np.sin(2 * np.pi * 440 * t) * 0.5,
                     np.sin(2 * np.pi * 660 * t) * 0.5], axis=1)
    src = os.path.join(tmp, "tone.wav")
    sf.write(src, wave, sr)

    data, rate = audio.load_audio(src)
    assert rate == sr and data.shape[1] == 2
    env = audio.waveform_envelope(data, 400)
    assert env.shape == (400, 2)

    info = audio.export_sound(data, rate, 0.25, 1.0, os.path.join(tmp, "mod"),
                              "hitsound")
    out = info["output_path"]
    assert out.endswith(os.path.join("sound", "ui", "hitsound.wav"))
    meta = sf.info(out)
    assert meta.samplerate == 44100, meta.samplerate
    assert meta.subtype == "PCM_16", meta.subtype
    assert abs(meta.duration - 0.75) < 0.01, meta.duration
    info2 = audio.export_sound(data, rate, 0.0, 0.5, os.path.join(tmp, "mod"),
                               "killsound")
    assert info2["output_path"].endswith("killsound.wav")
    print(f"  ses: {meta.samplerate}Hz {meta.subtype} {meta.duration:.2f}s "
          f"{meta.channels}ch")
    # mp3 support check (libsndfile >= 1.1)
    formats = sf.available_formats()
    print(f"  mp3 destegi: {'MPEG' in formats or 'MP3' in formats}")


def test_sinc_resample(tmp):
    """The scipy-free fallback must be near-transparent for audible content."""
    sr_in, sr_out = 48000, 44100
    t = np.linspace(0, 1.0, sr_in, endpoint=False)
    sig = np.stack([np.sin(2 * np.pi * 1000 * t) * 0.5,
                    np.sin(2 * np.pi * 5000 * t) * 0.3], axis=1)
    ours = audio._sinc_resample(sig, sr_in, sr_out)
    assert ours.shape[0] == sr_out
    # reference: ideal sines sampled directly at 44100 Hz
    t2 = np.linspace(0, 1.0, sr_out, endpoint=False)
    ref = np.stack([np.sin(2 * np.pi * 1000 * t2) * 0.5,
                    np.sin(2 * np.pi * 5000 * t2) * 0.3], axis=1)
    cut = 200  # ignore filter edge effects
    err = ours[cut:-cut] - ref[cut:-cut]
    snr = 10 * math.log10((ref[cut:-cut] ** 2).mean() / (err ** 2).mean())
    print(f"  sinc resample SNR={snr:.1f}dB")
    assert snr > 40, f"fallback kalitesi dusuk: {snr:.1f}dB"


def main():
    tests = [test_dxt_roundtrip, test_static_spray, test_animated_spray,
             test_size_planner, test_objector, test_audio, test_preview,
             test_sinc_resample, test_path_dedup]
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for t in tests:
            name = t.__name__
            try:
                print(f"* {name}")
                t(tmp)
                print(f"  OK")
            except Exception as exc:
                failed += 1
                import traceback
                traceback.print_exc()
                print(f"  FAIL: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} test gecti")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
