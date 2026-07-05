"""Main window: TF2 detection banner + three module tabs."""

from __future__ import annotations

import os
import threading
from tkinter import filedialog

import customtkinter as ctk

from config import ConfigManager
from tf2_locator import find_tf2_path, suggested_paths
from .objector_tab import ObjectorTab
from .sound_tab import SoundTab
from .spray_tab import SprayTab
from .widgets import drain_ui_queue, ui_call


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TF2 Swiss Army Knife")
        self.geometry("960x760")
        self.minsize(900, 700)
        ctk.set_appearance_mode("dark")

        self.config_mgr = ConfigManager()

        # --- top bar: TF2 folder status ---
        top = ctk.CTkFrame(self, corner_radius=0)
        top.pack(fill="x")
        ctk.CTkLabel(top, text="🔧 TF2 Swiss Army Knife",
                     font=ctk.CTkFont(size=17, weight="bold")
                     ).pack(side="left", padx=16, pady=10)
        ctk.CTkButton(top, text="📁 El ile Seç", width=100,
                      fg_color="#3a3f47", hover_color="#4a505a",
                      command=self._pick_tf2).pack(side="right", padx=(4, 16))
        ctk.CTkButton(top, text="🔍 Yeniden Tara", width=110,
                      command=self._detect_tf2).pack(side="right", padx=4)
        self._tf2_label = ctk.CTkLabel(top, text="TF2 aranıyor...",
                                       text_color="#9aa4b0")
        self._tf2_label.pack(side="right", padx=12)

        # --- tabs ---
        self._tabs = ctk.CTkTabview(self, anchor="nw")
        self._tabs.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        tab1 = self._tabs.add("  🎨 Sprey Oluşturucu  ")
        tab2 = self._tabs.add("  🖼️ Objector Maker  ")
        tab3 = self._tabs.add("  🔊 Hitsound Kesici  ")
        for tab in (tab1, tab2, tab3):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        self.spray_tab = SprayTab(tab1, self.config_mgr)
        self.spray_tab.grid(row=0, column=0, sticky="nsew")
        self.objector_tab = ObjectorTab(tab2, self.config_mgr)
        self.objector_tab.grid(row=0, column=0, sticky="nsew")
        self.sound_tab = SoundTab(tab3, self.config_mgr)
        self.sound_tab.grid(row=0, column=0, sticky="nsew")

        self.after(100, self._detect_tf2)
        self.after(30, self._poll_ui_queue)

    def _poll_ui_queue(self):
        """Runs callables queued by worker threads (thread-safe UI updates)."""
        drain_ui_queue()
        self.after(30, self._poll_ui_queue)

    # ------------------------------------------------------------------

    def _detect_tf2(self):
        self._tf2_label.configure(text="TF2 aranıyor...",
                                  text_color="#9aa4b0")

        def work():
            path = self.config_mgr.get("tf2_path")
            if not path or not os.path.isdir(path):
                path = find_tf2_path() or ""
            ui_call(lambda: self._apply_tf2(path))

        threading.Thread(target=work, daemon=True).start()

    def _pick_tf2(self):
        chosen = filedialog.askdirectory(
            title="Team Fortress 2\\tf klasörünü seç")
        if chosen:
            self._apply_tf2(chosen.replace("/", "\\"))

    def _apply_tf2(self, path: str):
        if path and os.path.isdir(path):
            self.config_mgr.set("tf2_path", path)
            self._tf2_label.configure(text=f"✅ {path}",
                                      text_color="#7fca6a")
            # Prefill only module paths the user hasn't set yet.
            for key, value in suggested_paths(path).items():
                if not self.config_mgr.get(key):
                    self.config_mgr.set(key, value)
            self.spray_tab._path_sel.set(
                self.config_mgr.get("spray_export_path"), persist=False)
            self.objector_tab._path_sel.set(
                self.config_mgr.get("objector_export_path"), persist=False)
            self.sound_tab._path_sel.set(
                self.config_mgr.get("sound_export_path"), persist=False)
        else:
            self._tf2_label.configure(
                text="⚠️ TF2 bulunamadı — dizinleri el ile seçin",
                text_color="#e0a95b")


def run():
    app = App()
    app.mainloop()
