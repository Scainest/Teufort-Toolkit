"""Module 3 tab — Hitsound / Killsound trimmer."""

from __future__ import annotations

import os
import threading
from tkinter import filedialog

import customtkinter as ctk

from core import audio
from .widgets import PathSelector, WaveformCanvas, ui_call


class SoundTab(ctk.CTkFrame):
    def __init__(self, master, config):
        super().__init__(master, fg_color="transparent")
        self._config = config
        self._data = None
        self._rate = 0
        self._duration = 0.0

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text="Ses dosyasını (.mp3/.wav/.ogg) kırpar ve TF2 "
                       "standardında (44100 Hz, 16-bit PCM) hitsound/killsound "
                       "olarak kaydeder. Turuncu tutamaçları sürükleyin.",
            anchor="w", text_color="#9aa4b0").grid(
            row=0, column=0, sticky="ew", padx=16, pady=(12, 4))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkButton(bar, text="📂 Ses Dosyası Seç", command=self._pick_file
                      ).pack(side="left")
        self._info = ctk.CTkLabel(bar, text="", text_color="#9aa4b0")
        self._info.pack(side="left", padx=12)

        wave_frame = ctk.CTkFrame(self)
        wave_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=8)
        wave_frame.grid_columnconfigure(0, weight=1)
        self._wave = WaveformCanvas(wave_frame, width=860, height=190,
                                    on_change=self._on_marker_drag)
        self._wave.grid(row=0, column=0, padx=10, pady=10)
        self._wave._redraw()

        # --- trim controls ---
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=3, column=0, sticky="ew", padx=16, pady=4)
        ctk.CTkLabel(controls, text="Başlangıç (sn):").pack(side="left")
        self._start_var = ctk.StringVar(value="0.00")
        self._end_var = ctk.StringVar(value="0.00")
        start_entry = ctk.CTkEntry(controls, textvariable=self._start_var,
                                   width=80)
        start_entry.pack(side="left", padx=(6, 16))
        ctk.CTkLabel(controls, text="Bitiş (sn):").pack(side="left")
        end_entry = ctk.CTkEntry(controls, textvariable=self._end_var,
                                 width=80)
        end_entry.pack(side="left", padx=(6, 16))
        for entry in (start_entry, end_entry):
            entry.bind("<Return>", lambda e: self._apply_entries())
            entry.bind("<FocusOut>", lambda e: self._apply_entries())
        self._sel_label = ctk.CTkLabel(controls, text="",
                                       text_color="#9aa4b0")
        self._sel_label.pack(side="left", padx=8)

        ctk.CTkButton(controls, text="⏹ Durdur", width=90,
                      fg_color="#3a3f47", hover_color="#4a505a",
                      command=self._stop_preview).pack(side="right", padx=4)
        ctk.CTkButton(controls, text="▶ Önizle", width=90,
                      command=self._preview).pack(side="right", padx=4)

        self._path_sel = PathSelector(
            self, config, "sound_export_path",
            "Kayıt Dizini (custom klasörü):")
        self._path_sel.grid(row=4, column=0, sticky="ew", padx=16, pady=8)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=5, column=0, sticky="ew", padx=16, pady=(4, 16))
        self._hit_btn = ctk.CTkButton(
            bottom, text="🎯 Hitsound Olarak Aktar", height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: self._export("hitsound"))
        self._hit_btn.pack(side="left")
        self._kill_btn = ctk.CTkButton(
            bottom, text="💀 Killsound Olarak Aktar", height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#8c3b3b", hover_color="#a34848",
            command=lambda: self._export("killsound"))
        self._kill_btn.pack(side="left", padx=12)
        self._status = ctk.CTkLabel(bottom, text="", wraplength=460,
                                    justify="left")
        self._status.pack(side="left", padx=8)

    # ------------------------------------------------------------------

    def _pick_file(self):
        path = filedialog.askopenfilename(
            title="Ses dosyası seç",
            filetypes=[("Ses dosyaları", "*.mp3 *.wav *.ogg *.flac"),
                       ("Tümü", "*.*")])
        if not path:
            return
        self._info.configure(text="⏳ Yükleniyor...")

        def work():
            try:
                data, rate = audio.load_audio(path)
                env = audio.waveform_envelope(data, 840)
            except Exception as exc:
                ui_call(lambda exc=exc: self._load_done(path, error=str(exc)))
            else:
                ui_call(lambda: self._load_done(path, data=data,
                                                rate=rate, env=env))

        threading.Thread(target=work, daemon=True).start()

    def _load_done(self, path, data=None, rate=0, env=None, error=None):
        if error:
            self._info.configure(text="")
            self._set_status(f"❌ {error}", error=True)
            return
        self._data, self._rate = data, rate
        self._duration = audio.duration_seconds(data, rate)
        self._wave.set_audio(env, self._duration)
        self._start_var.set("0.00")
        self._end_var.set(f"{self._duration:.2f}")
        ch = {1: "mono", 2: "stereo"}.get(data.shape[1],
                                          f"{data.shape[1]} kanal")
        self._info.configure(
            text=f"{os.path.basename(path)} — {self._duration:.2f} sn, "
                 f"{rate} Hz, {ch}")
        self._update_sel_label()
        self._set_status("")

    def _on_marker_drag(self, start, end):
        self._start_var.set(f"{start:.2f}")
        self._end_var.set(f"{end:.2f}")
        self._update_sel_label()

    def _apply_entries(self):
        if self._data is None:
            return
        try:
            start = float(self._start_var.get().replace(",", "."))
            end = float(self._end_var.get().replace(",", "."))
        except ValueError:
            return
        self._wave.set_selection(start, end)
        start, end = self._wave.get_selection()
        self._start_var.set(f"{start:.2f}")
        self._end_var.set(f"{end:.2f}")
        self._update_sel_label()

    def _update_sel_label(self):
        start, end = self._wave.get_selection()
        self._sel_label.configure(text=f"Seçim: {end - start:.2f} sn")

    def _selection(self):
        start, end = self._wave.get_selection()
        return start, end

    def _preview(self):
        if self._data is None:
            self._set_status("❌ Önce bir ses dosyası yükleyin.", error=True)
            return
        try:
            import sounddevice as sd
            start, end = self._selection()
            segment = audio.process_selection(self._data, self._rate,
                                              start, end)
            sd.stop()
            sd.play(segment, audio.TARGET_SAMPLE_RATE)
        except Exception as exc:
            self._set_status(f"❌ Önizleme hatası: {exc}", error=True)

    def _stop_preview(self):
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass

    def _export(self, kind: str):
        if self._data is None:
            self._set_status("❌ Önce bir ses dosyası yükleyin.", error=True)
            return
        export_dir = self._path_sel.get()
        if not export_dir:
            self._set_status("❌ Kayıt dizini seçin "
                             "(örn: ...\\tf\\custom\\ModKlasorum).", error=True)
            return
        start, end = self._selection()
        for btn in (self._hit_btn, self._kill_btn):
            btn.configure(state="disabled")
        self._set_status("⏳ Dışa aktarılıyor...")

        def work():
            try:
                info = audio.export_sound(self._data, self._rate, start, end,
                                          export_dir, kind)
            except Exception as exc:
                ui_call(lambda exc=exc: self._export_done(error=str(exc)))
            else:
                ui_call(lambda: self._export_done(info=info))

        threading.Thread(target=work, daemon=True).start()

    def _export_done(self, info=None, error=None):
        for btn in (self._hit_btn, self._kill_btn):
            btn.configure(state="normal")
        if error:
            self._set_status(f"❌ {error}", error=True)
            return
        ch = "mono" if info["channels"] == 1 else "stereo"
        self._set_status(
            f"✅ Kaydedildi: {info['duration']:.2f} sn, 44100 Hz 16-bit {ch}\n"
            f"{info['output_path']}")

    def _set_status(self, text, error=False):
        self._status.configure(
            text=text, text_color="#e05b5b" if error else "#7fca6a")
