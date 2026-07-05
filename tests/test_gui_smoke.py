"""GUI smoke test: builds the real window, drives all three tabs
programmatically (no dialogs) and verifies the produced files.
    python tests/test_gui_smoke.py
"""

import os
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Keep the test's config writes away from the real config.json.
import config as config_module  # noqa: E402
_tmp_cfg = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
_tmp_cfg.close()
os.unlink(_tmp_cfg.name)
config_module.CONFIG_PATH = _tmp_cfg.name
config_module.ConfigManager.__init__.__defaults__ = (_tmp_cfg.name,)

from core import audio  # noqa: E402
from gui.app import App  # noqa: E402


def pump(app, seconds):
    end = time.time() + seconds
    while time.time() < end:
        app.update()
        time.sleep(0.01)


def main():
    tmp = tempfile.mkdtemp(prefix="tf2sak_gui_")
    photo = os.path.join(tmp, "img.png")
    im = Image.new("RGB", (400, 260), (30, 60, 120))
    ImageDraw.Draw(im).ellipse([60, 30, 340, 230], fill=(240, 80, 40))
    im.save(photo)

    app = App()
    pump(app, 1.5)  # let TF2 detection finish
    print("TF2 durumu:", app._tf2_label.cget("text")[:80])

    # --- Tab 1: spray ---
    t = app.spray_tab
    t._image_path = photo
    t._name_entry.delete(0, "end")
    t._name_entry.insert(0, "smoke_test")
    t._path_sel.set(os.path.join(tmp, "spray_out"))
    t._generate()
    for _ in range(200):
        pump(app, 0.05)
        if "✅" in t._status.cget("text") or "❌" in t._status.cget("text"):
            break
    status = t._status.cget("text")
    print("Sprey:", status.replace("\n", " | ")[:120])
    assert "✅" in status, status
    assert os.path.isfile(os.path.join(tmp, "spray_out", "smoke_test.vtf"))
    assert os.path.isfile(os.path.join(tmp, "spray_out", "smoke_test.vmt"))

    # --- Tab 1b: game-accurate preview (DXT round-trip on a wall) ---
    t._frames = [Image.open(photo).convert("RGBA")]
    t._base_info = "test"
    from gui.spray_tab import VIEW_GAME
    t._view_seg.set(VIEW_GAME)
    t._on_view_change(VIEW_GAME)
    for _ in range(200):
        pump(app, 0.05)
        if "Oyun içi" in t._info.cget("text"):
            break
    print("Oyun önizl.:", t._info.cget("text").split("\n")[-1])
    assert "Oyun içi" in t._info.cget("text"), t._info.cget("text")
    assert t._anim_frames, "oyun önizleme karesi yok"

    # --- Tab 2: objector ---
    t2 = app.objector_tab
    t2._image_path = photo
    t2._src_img = Image.open(photo).convert("RGBA")
    t2._canvas.set_image(Image.open(photo))
    t2._path_sel.set(os.path.join(tmp, "mod"))
    pump(app, 0.5)  # let the debounced live preview render
    assert t2._out_preview.cget("image") is not None, "çıktı önizleme yok"
    assert t2._sign_preview.cget("image") is not None, "tabela önizleme yok"
    print("Objector önizleme: OK (çıktı + tabela)")
    t2._size_menu.set("128 (en uyumlu)")  # exercise the resolution selector
    t2._export()
    pump(app, 0.2)
    status = t2._status.cget("text")
    print("Objector:", status.replace("\n", " | ")[:120])
    assert "✅" in status, status
    out_png = os.path.join(tmp, "mod", "scripts", "items",
                           "custom_texture_blend_layers", "paper_overlay.png")
    assert Image.open(out_png).size == (128, 128)
    assert not os.path.exists(os.path.join(tmp, "mod", "materials"))

    # --- Tab 3: sound ---
    t3 = app.sound_tab
    sr = 22050
    tt = np.linspace(0, 1.5, int(1.5 * sr), endpoint=False)
    data = (np.sin(2 * np.pi * 500 * tt) * 0.4).astype(np.float32)[:, None]
    env = audio.waveform_envelope(data, 840)
    t3._load_done("smoke.wav", data=data, rate=sr, env=env)
    t3._wave.set_selection(0.2, 1.0)
    t3._on_marker_drag(0.2, 1.0)
    t3._path_sel.set(os.path.join(tmp, "mod"))
    pump(app, 0.2)
    t3._export("hitsound")
    for _ in range(100):
        pump(app, 0.05)
        if "✅" in t3._status.cget("text") or "❌" in t3._status.cget("text"):
            break
    status = t3._status.cget("text")
    print("Ses:", status.replace("\n", " | ")[:120])
    assert "✅" in status, status
    import soundfile as sf
    meta = sf.info(os.path.join(tmp, "mod", "sound", "ui", "hitsound.wav"))
    assert meta.samplerate == 44100 and meta.subtype == "PCM_16"

    # crop canvas interaction sanity
    box = t2._canvas.get_crop_box()
    assert box and box[2] - box[0] == box[3] - box[1] > 0

    app.destroy()
    print("\nGUI duman testi: TAMAM")


if __name__ == "__main__":
    main()
