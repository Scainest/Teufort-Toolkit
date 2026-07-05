"""Module 1 tab — Spray Generator."""

from __future__ import annotations

import os
import threading
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from core import preview, spray
from .widgets import PathSelector, ui_call

PREVIEW_SIZE = 260
VIEW_ORIGINAL = "Orijinal"
VIEW_GAME = "Oyun İçi (VTF)"


class SprayTab(ctk.CTkFrame):
    def __init__(self, master, config):
        super().__init__(master, fg_color="transparent")
        self._config = config
        self._image_path = ""
        self._frames = []            # original RGBA frames of the loaded file
        self._game_cache = {}        # (path, max_dim) -> (ctk_images, info_line)
        self._base_info = ""
        self._anim_frames = []
        self._anim_index = 0
        self._anim_job = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkLabel(
            self, text="Görselleri (.png/.jpg/.gif) TF2 sprey formatına "
                       "(.vtf + .vmt) dönüştürür. Çıktı 512 KB sınırına göre "
                       "otomatik optimize edilir.",
            anchor="w", text_color="#9aa4b0")
        header.grid(row=0, column=0, columnspan=2, sticky="ew",
                    padx=16, pady=(12, 4))

        # --- left: preview ---
        left = ctk.CTkFrame(self)
        left.grid(row=1, column=0, sticky="nsew", padx=(16, 8), pady=8)
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)
        bar = ctk.CTkFrame(left, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        ctk.CTkButton(bar, text="📂 Görsel Seç", command=self._pick_file
                      ).pack(side="left")
        self._view_seg = ctk.CTkSegmentedButton(
            left, values=[VIEW_ORIGINAL, VIEW_GAME],
            command=self._on_view_change)
        self._view_seg.set(VIEW_ORIGINAL)
        self._view_seg.grid(row=1, column=0, padx=12, pady=(4, 6))
        self._preview = ctk.CTkLabel(left, text="Önizleme yok",
                                     width=PREVIEW_SIZE, height=PREVIEW_SIZE)
        self._preview.grid(row=2, column=0, padx=12, pady=(0, 8))
        self._info = ctk.CTkLabel(left, text="", text_color="#9aa4b0",
                                  justify="center")
        self._info.grid(row=3, column=0, padx=12, pady=(0, 12))

        # --- right: options ---
        right = ctk.CTkFrame(self)
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 16), pady=8)
        right.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(right, text="Sprey adı:").grid(
            row=0, column=0, padx=12, pady=(16, 6), sticky="w")
        self._name_entry = ctk.CTkEntry(right, placeholder_text="dosya adı")
        self._name_entry.grid(row=0, column=1, padx=(0, 12), pady=(16, 6),
                              sticky="ew")

        ctk.CTkLabel(right, text="Maks. çözünürlük:").grid(
            row=1, column=0, padx=12, pady=6, sticky="w")
        self._size_menu = ctk.CTkOptionMenu(
            right, values=["512", "256", "128"], width=110,
            command=self._on_size_change)
        self._size_menu.grid(row=1, column=1, padx=(0, 12), pady=6, sticky="w")

        self._generate_btn = ctk.CTkButton(
            right, text="⚙️  Sprey Oluştur", height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._generate)
        self._generate_btn.grid(row=2, column=0, columnspan=2,
                                padx=12, pady=(18, 6), sticky="ew")
        self._status = ctk.CTkLabel(right, text="", wraplength=380,
                                    justify="left")
        self._status.grid(row=3, column=0, columnspan=2, padx=12, pady=6,
                          sticky="w")
        hint = ctk.CTkLabel(
            right, text="İpucu: \"Oyun İçi (VTF)\" görünümü spreyi gerçek DXT\n"
                        "sıkıştırmasından geçirip duvar üzerinde gösterir.\n\n"
                        "Spreyin oyunda görünmesi için çıktıyı\n"
                        "tf\\materials\\vgui\\logos klasörüne kaydedin ve\n"
                        "oyun ayarlarından spreyi seçin.",
            text_color="#7a828d", justify="left")
        hint.grid(row=4, column=0, columnspan=2, padx=12, pady=(8, 12),
                  sticky="w")

        # --- bottom: export path ---
        self._path_sel = PathSelector(
            self, config, "spray_export_path", "Kayıt Dizini:")
        self._path_sel.grid(row=2, column=0, columnspan=2, sticky="ew",
                            padx=16, pady=(4, 16))

    # ------------------------------------------------------------------

    def _pick_file(self):
        path = filedialog.askopenfilename(
            title="Görsel seç",
            filetypes=[("Görseller", "*.png *.jpg *.jpeg *.gif"),
                       ("Tümü", "*.*")])
        if not path:
            return
        try:
            frames = spray.load_frames(path)
        except Exception as exc:
            self._set_status(f"❌ Görsel açılamadı: {exc}", error=True)
            return
        self._image_path = path
        self._frames = frames
        self._game_cache.clear()
        self._name_entry.delete(0, "end")
        self._name_entry.insert(
            0, spray.sanitize_spray_name(os.path.splitext(
                os.path.basename(path))[0]))
        w, h = frames[0].size
        kind = f"{len(frames)} kare (animasyonlu GIF)" if len(frames) > 1 \
            else "statik görsel"
        self._base_info = f"{w}x{h} — {kind}"
        self._set_status("")
        self._view_seg.set(VIEW_ORIGINAL)
        self._show_original()

    # -- preview handling ----------------------------------------------

    def _show_original(self):
        self._info.configure(text=self._base_info)
        ctk_frames = []
        step = max(1, len(self._frames) // 30)
        for frame in self._frames[::step][:30]:
            thumb = frame.copy()
            thumb.thumbnail((PREVIEW_SIZE, PREVIEW_SIZE), Image.LANCZOS)
            ctk_frames.append(ctk.CTkImage(light_image=thumb, dark_image=thumb,
                                           size=thumb.size))
        self._show_frames(ctk_frames)

    def _show_frames(self, ctk_frames):
        if self._anim_job:
            self.after_cancel(self._anim_job)
            self._anim_job = None
        self._anim_frames = ctk_frames
        self._anim_index = 0
        if not ctk_frames:
            return
        self._preview.configure(image=ctk_frames[0], text="")
        if len(ctk_frames) > 1:
            self._anim_job = self.after(80, self._tick_preview)

    def _tick_preview(self):
        self._anim_index = (self._anim_index + 1) % len(self._anim_frames)
        self._preview.configure(image=self._anim_frames[self._anim_index])
        self._anim_job = self.after(80, self._tick_preview)

    def _on_view_change(self, value):
        if not self._frames:
            self._view_seg.set(VIEW_ORIGINAL)
            return
        if value == VIEW_ORIGINAL:
            self._show_original()
        else:
            self._show_game_preview()

    def _on_size_change(self, _value):
        if self._frames and self._view_seg.get() == VIEW_GAME:
            self._show_game_preview()

    def _show_game_preview(self):
        key = (self._image_path, int(self._size_menu.get()))
        cached = self._game_cache.get(key)
        if cached:
            self._show_frames(cached[0])
            self._info.configure(text=f"{self._base_info}\n{cached[1]}")
            return
        self._info.configure(
            text=f"{self._base_info}\n⏳ VTF önizlemesi hesaplanıyor...")
        frames, max_dim = self._frames, key[1]

        def work():
            try:
                decoded, info = preview.spray_game_preview(frames, max_dim)
                composed = [preview.compose_on_wall(img, PREVIEW_SIZE)
                            for img in decoded]
            except Exception as exc:
                ui_call(lambda exc=exc: self._set_status(
                    f"❌ Önizleme hatası: {exc}", error=True))
            else:
                ui_call(lambda: self._game_preview_ready(key, composed, info))

        threading.Thread(target=work, daemon=True).start()

    def _game_preview_ready(self, key, composed, info):
        ctk_frames = [ctk.CTkImage(light_image=img, dark_image=img,
                                   size=img.size) for img in composed]
        frame_note = f" · {info['frames']} kare" if info["frames"] > 1 else ""
        line = (f"Oyun içi: {info['width']}x{info['height']} "
                f"{info['format']}{frame_note} · "
                f"~{info['est_size'] / 1024:.0f} KB")
        self._game_cache[key] = (ctk_frames, line)
        # Only apply if the user is still on this file + view + size.
        current = (self._image_path, int(self._size_menu.get()))
        if current == key and self._view_seg.get() == VIEW_GAME:
            self._show_frames(ctk_frames)
            self._info.configure(text=f"{self._base_info}\n{line}")

    # -- generation ------------------------------------------------------

    def _generate(self):
        if not self._image_path:
            self._set_status("❌ Önce bir görsel seçin.", error=True)
            return
        export_dir = self._path_sel.get()
        if not export_dir:
            self._set_status("❌ Kayıt dizini seçin.", error=True)
            return
        name = self._name_entry.get().strip()
        max_dim = int(self._size_menu.get())
        self._generate_btn.configure(state="disabled", text="Oluşturuluyor...")
        self._set_status("⏳ VTF kodlanıyor, lütfen bekleyin...")

        def work():
            try:
                info = spray.generate_spray(self._image_path, export_dir,
                                            name, max_dim)
            except Exception as exc:
                ui_call(lambda exc=exc: self._done(error=str(exc)))
            else:
                ui_call(lambda: self._done(info=info))

        threading.Thread(target=work, daemon=True).start()

    def _done(self, info=None, error=None):
        self._generate_btn.configure(state="normal", text="⚙️  Sprey Oluştur")
        if error:
            self._set_status(f"❌ {error}", error=True)
            return
        frame_note = (f", {info['frames']} kare" if info["frames"] > 1 else "")
        self._set_status(
            f"✅ Tamamlandı: {info['name']}.vtf + .vmt\n"
            f"{info['width']}x{info['height']} {info['format']}{frame_note} — "
            f"{info['file_size'] / 1024:.0f} KB\n{info['vtf_path']}")

    def _set_status(self, text, error=False):
        self._status.configure(
            text=text, text_color="#e05b5b" if error else "#7fca6a")
