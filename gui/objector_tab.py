"""Module 2 tab — Full-Color Conscientious Objector maker."""

from __future__ import annotations

from tkinter import filedialog

import customtkinter as ctk
from PIL import Image

from core import objector, preview
from .widgets import CropCanvas, PathSelector

SIGN_SIZE = (190, 220)


class ObjectorTab(ctk.CTkFrame):
    def __init__(self, master, config):
        super().__init__(master, fg_color="transparent")
        self._config = config
        self._image_path = ""
        self._src_img = None
        self._preview_job = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            self, text="Conscientious Objector için tam renkli paper_overlay.png "
                       "üretir. Dosya, custom klasörünün içine doğru yola "
                       "(scripts\\items\\custom_texture_blend_layers) yazılır. "
                       "Kare alanı sürükleyerek taşıyın, sağ alt köşeden "
                       "boyutlandırın — önizleme anında güncellenir.",
            anchor="w", text_color="#9aa4b0", wraplength=820, justify="left").grid(
            row=0, column=0, sticky="ew", padx=16, pady=(12, 4))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkButton(bar, text="📂 Görsel Seç", command=self._pick_file
                      ).pack(side="left")
        ctk.CTkButton(bar, text="↺ Kırpmayı Sıfırla", width=140,
                      fg_color="#3a3f47", hover_color="#4a505a",
                      command=self._reset_crop).pack(side="left", padx=8)
        ctk.CTkLabel(bar, text="Çözünürlük:").pack(side="left", padx=(12, 4))
        self._size_menu = ctk.CTkOptionMenu(
            bar, width=150, command=self._on_size_change,
            values=["256 (önerilen)", "128 (en uyumlu)", "512 (en keskin)"])
        self._size_menu.set("256 (önerilen)")
        self._size_menu.pack(side="left")
        self._info = ctk.CTkLabel(bar, text="", text_color="#9aa4b0")
        self._info.pack(side="left", padx=12)

        center = ctk.CTkFrame(self)
        center.grid(row=2, column=0, sticky="nsew", padx=16, pady=8)
        center.grid_columnconfigure(0, weight=1)
        center.grid_rowconfigure(0, weight=1)
        self._canvas = CropCanvas(center, width=470, height=360,
                                  on_change=self._schedule_preview)
        self._canvas.grid(row=0, column=0, padx=(12, 6), pady=12)

        side = ctk.CTkFrame(center, fg_color="transparent")
        side.grid(row=0, column=1, padx=(6, 12), pady=8, sticky="n")
        self._out_caption = ctk.CTkLabel(side, text="Çıktı (256x256)",
                                         text_color="#9aa4b0")
        self._out_caption.pack(pady=(4, 2))
        self._out_preview = ctk.CTkLabel(side, text="—", width=132, height=132)
        self._out_preview.pack()
        ctk.CTkLabel(side, text="Oyun içi görünüm",
                     text_color="#9aa4b0").pack(pady=(10, 2))
        self._sign_preview = ctk.CTkLabel(side, text="—", width=SIGN_SIZE[0],
                                          height=SIGN_SIZE[1])
        self._sign_preview.pack()

        self._path_sel = PathSelector(
            self, config, "objector_export_path",
            "Kayıt Dizini (custom klasörü):")
        self._path_sel.grid(row=3, column=0, sticky="ew", padx=16, pady=4)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 16))
        self._export_btn = ctk.CTkButton(
            bottom, text="🖼️  paper_overlay.png Olarak Kaydet", height=40,
            font=ctk.CTkFont(size=14, weight="bold"), command=self._export)
        self._export_btn.pack(side="left")
        self._status = ctk.CTkLabel(bottom, text="", wraplength=520,
                                    justify="left")
        self._status.pack(side="left", padx=16)

    # ------------------------------------------------------------------

    def _pick_file(self):
        path = filedialog.askopenfilename(
            title="Görsel seç",
            filetypes=[("Görseller", "*.png *.jpg *.jpeg *.bmp *.webp *.gif"),
                       ("Tümü", "*.*")])
        if not path:
            return
        try:
            img = Image.open(path)
            img.load()
        except Exception as exc:
            self._set_status(f"❌ Görsel açılamadı: {exc}", error=True)
            return
        self._image_path = path
        self._src_img = img.convert("RGBA")
        self._canvas.set_image(img)  # triggers the preview via on_change
        self._info.configure(text=f"{img.width}x{img.height}")
        self._set_status("")

    def _reset_crop(self):
        if self._src_img is not None:
            self._canvas.set_image(self._src_img)

    def _selected_size(self) -> int:
        return int(self._size_menu.get().split()[0])

    def _on_size_change(self, _value):
        self._out_caption.configure(
            text=f"Çıktı ({self._selected_size()}px)")
        self._schedule_preview()

    # -- live preview ----------------------------------------------------

    def _schedule_preview(self):
        """Debounced: crop drags fire many events, render at most ~8/s."""
        if self._preview_job:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(120, self._update_preview)

    def _update_preview(self):
        self._preview_job = None
        if self._src_img is None:
            return
        decal = objector.crop_to_overlay(self._src_img,
                                         self._canvas.get_crop_box(),
                                         self._selected_size())
        out_img = ctk.CTkImage(light_image=decal, dark_image=decal,
                               size=(128, 128))
        self._out_preview.configure(image=out_img, text="")
        sign = preview.objector_sign_mockup(decal, SIGN_SIZE)
        sign_img = ctk.CTkImage(light_image=sign, dark_image=sign,
                                size=sign.size)
        self._sign_preview.configure(image=sign_img, text="")

    # -- export ------------------------------------------------------------

    def _export(self):
        if not self._image_path:
            self._set_status("❌ Önce bir görsel seçin.", error=True)
            return
        export_dir = self._path_sel.get()
        if not export_dir:
            self._set_status("❌ Kayıt dizini seçin "
                             "(örn: ...\\tf\\custom\\ModKlasorum).", error=True)
            return
        size = self._selected_size()
        try:
            result = objector.make_paper_overlay(
                self._image_path, export_dir,
                crop_box=self._canvas.get_crop_box(), size=size)
        except Exception as exc:
            self._set_status(f"❌ {exc}", error=True)
            return
        w, h = result["size"]
        note = ("\nOyunda görünmezse Çözünürlük'ü 128'e alıp tekrar deneyin."
                if size != objector.COMPATIBLE_SIZE else "")
        self._set_status(
            f"✅ Kaydedildi ({w}x{h}):\n{result['output_path']}{note}")

    def _set_status(self, text, error=False):
        self._status.configure(
            text=text, text_color="#e05b5b" if error else "#7fca6a")
