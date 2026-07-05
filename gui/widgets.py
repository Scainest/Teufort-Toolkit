"""Shared GUI widgets: per-module export path selector, square crop canvas
and an interactive waveform canvas with draggable trim markers. Also hosts
the thread-safe UI dispatch queue used by all background workers."""

from __future__ import annotations

import queue
import tkinter as tk
from tkinter import filedialog
from typing import Callable, Optional, Tuple

import customtkinter as ctk
from PIL import Image, ImageTk

# Worker threads must not touch tkinter directly; they enqueue callables
# here and the main window drains the queue on its own after()-timer.
_ui_queue: "queue.Queue[Callable[[], None]]" = queue.Queue()


def ui_call(fn: Callable[[], None]) -> None:
    """Schedule `fn` to run on the UI thread (safe from any thread)."""
    _ui_queue.put(fn)


def drain_ui_queue() -> None:
    while True:
        try:
            fn = _ui_queue.get_nowait()
        except queue.Empty:
            return
        fn()

CANVAS_BG = "#12141a"
ACCENT = "#e8842c"       # TF2 orange
ACCENT_DIM = "#7a4616"
WAVE_COLOR = "#4da3ff"


class PathSelector(ctk.CTkFrame):
    """Label + editable entry + Browse button, write-through to config."""

    def __init__(self, master, config, config_key: str, label: str,
                 on_change: Optional[Callable[[str], None]] = None):
        super().__init__(master, fg_color="transparent")
        self._config = config
        self._key = config_key
        self._on_change = on_change

        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=label, anchor="w").grid(
            row=0, column=0, padx=(0, 8), sticky="w")
        self._var = tk.StringVar(value=config.get(config_key))
        self._entry = ctk.CTkEntry(self, textvariable=self._var)
        self._entry.grid(row=0, column=1, sticky="ew")
        self._entry.bind("<FocusOut>", lambda e: self._commit())
        self._entry.bind("<Return>", lambda e: self._commit())
        ctk.CTkButton(self, text="Göz At...", width=90,
                      command=self._browse).grid(row=0, column=2, padx=(8, 0))

    def _browse(self):
        initial = self._var.get() or self._config.get("last_browse_dir")
        chosen = filedialog.askdirectory(
            initialdir=initial or None, title="Kayıt dizini seç")
        if chosen:
            self._var.set(chosen.replace("/", "\\"))
            self._config.set("last_browse_dir", chosen)
            self._commit()

    def _commit(self):
        value = self._var.get().strip()
        if value != self._config.get(self._key):
            self._config.set(self._key, value)
            if self._on_change:
                self._on_change(value)

    def get(self) -> str:
        return self._var.get().strip()

    def set(self, value: str, persist: bool = True):
        self._var.set(value)
        if persist:
            self._config.set(self._key, value)


class CropCanvas(tk.Canvas):
    """Shows an image with a draggable/resizable square crop selection."""

    HANDLE = 14
    MIN_SIDE = 24

    def __init__(self, master, width=460, height=340,
                 on_change: Optional[Callable[[], None]] = None):
        super().__init__(master, width=width, height=height, bg=CANVAS_BG,
                         highlightthickness=0, cursor="crosshair")
        self._cw, self._ch = width, height
        self._on_change = on_change
        self._img: Optional[Image.Image] = None
        self._photo = None
        self._scale = 1.0
        self._ox = self._oy = 0          # image top-left on canvas
        self._dw = self._dh = 0          # displayed image size
        self._sel = [0, 0, 0]            # x, y, side (canvas coords)
        self._mode = None
        self._grab = (0, 0)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)

    def set_image(self, img: Image.Image):
        self._img = img.convert("RGBA")
        self._scale = min(self._cw / img.width, self._ch / img.height)
        self._dw = max(1, int(img.width * self._scale))
        self._dh = max(1, int(img.height * self._scale))
        self._ox = (self._cw - self._dw) // 2
        self._oy = (self._ch - self._dh) // 2
        display = self._img.resize((self._dw, self._dh), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(display)
        side = min(self._dw, self._dh)
        self._sel = [self._ox + (self._dw - side) // 2,
                     self._oy + (self._dh - side) // 2, side]
        self._redraw()
        self._notify()

    def _notify(self):
        if self._on_change:
            self._on_change()

    def get_crop_box(self) -> Optional[Tuple[int, int, int, int]]:
        """Selection in original image coordinates."""
        if self._img is None:
            return None
        x, y, side = self._sel
        left = int(round((x - self._ox) / self._scale))
        top = int(round((y - self._oy) / self._scale))
        s = max(1, int(round(side / self._scale)))  # single rounding: square
        return (left, top, left + s, top + s)

    # -- interaction ---------------------------------------------------------

    def _on_press(self, ev):
        if self._img is None:
            return
        x, y, side = self._sel
        hx, hy = x + side, y + side
        if abs(ev.x - hx) < self.HANDLE and abs(ev.y - hy) < self.HANDLE:
            self._mode = "resize"
        elif x <= ev.x <= x + side and y <= ev.y <= y + side:
            self._mode = "move"
            self._grab = (ev.x - x, ev.y - y)
        else:
            self._mode = "move"
            self._grab = (side // 2, side // 2)
            self._apply_move(ev.x, ev.y)

    def _on_drag(self, ev):
        if self._img is None or self._mode is None:
            return
        if self._mode == "move":
            self._apply_move(ev.x, ev.y)
        else:
            x, y, _ = self._sel
            side = max(self.MIN_SIDE, min(ev.x - x, ev.y - y))
            side = min(side, self._ox + self._dw - x, self._oy + self._dh - y)
            self._sel[2] = int(side)
            self._redraw()
            self._notify()

    def _apply_move(self, px, py):
        side = self._sel[2]
        x = min(max(px - self._grab[0], self._ox), self._ox + self._dw - side)
        y = min(max(py - self._grab[1], self._oy), self._oy + self._dh - side)
        self._sel[0], self._sel[1] = int(x), int(y)
        self._redraw()
        self._notify()

    def _redraw(self):
        self.delete("all")
        if self._photo is None:
            return
        self.create_image(self._ox, self._oy, image=self._photo, anchor="nw")
        x, y, side = self._sel
        # dim everything outside the selection
        for box in ((self._ox, self._oy, self._ox + self._dw, y),
                    (self._ox, y + side, self._ox + self._dw, self._oy + self._dh),
                    (self._ox, y, x, y + side),
                    (x + side, y, self._ox + self._dw, y + side)):
            if box[2] > box[0] and box[3] > box[1]:
                self.create_rectangle(*box, fill="black", stipple="gray50",
                                      outline="")
        self.create_rectangle(x, y, x + side, y + side, outline=ACCENT, width=2)
        h = self.HANDLE // 2
        self.create_rectangle(x + side - h, y + side - h, x + side + h,
                              y + side + h, fill=ACCENT, outline="")
        # rule-of-thirds guides
        for i in (1, 2):
            t = side * i // 3
            self.create_line(x + t, y, x + t, y + side, fill=ACCENT_DIM)
            self.create_line(x, y + t, x + side, y + t, fill=ACCENT_DIM)


class WaveformCanvas(tk.Canvas):
    """Waveform display with draggable start/end trim markers."""

    PAD = 10

    def __init__(self, master, width=720, height=180,
                 on_change: Optional[Callable[[float, float], None]] = None):
        super().__init__(master, width=width, height=height, bg=CANVAS_BG,
                         highlightthickness=0)
        self._cw, self._chh = width, height
        self._on_change = on_change
        self._env = None            # (N, 2) min/max envelope
        self._duration = 0.0
        self._start = 0.0
        self._end = 0.0
        self._dragging: Optional[str] = None
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", lambda e: self._release())

    def set_audio(self, envelope, duration: float):
        self._env = envelope
        self._duration = duration
        self._start, self._end = 0.0, duration
        self._redraw()

    def set_selection(self, start: float, end: float):
        if self._duration <= 0:
            return
        self._start = max(0.0, min(start, self._duration))
        self._end = max(self._start + 0.001, min(end, self._duration))
        self._redraw()

    def get_selection(self) -> Tuple[float, float]:
        return self._start, self._end

    def _t2x(self, t: float) -> float:
        usable = self._cw - 2 * self.PAD
        return self.PAD + (t / self._duration) * usable if self._duration else 0

    def _x2t(self, x: float) -> float:
        usable = self._cw - 2 * self.PAD
        return max(0.0, min(1.0, (x - self.PAD) / usable)) * self._duration

    def _on_press(self, ev):
        if self._duration <= 0:
            return
        xs, xe = self._t2x(self._start), self._t2x(self._end)
        if abs(ev.x - xs) <= abs(ev.x - xe) and abs(ev.x - xs) < 14:
            self._dragging = "start"
        elif abs(ev.x - xe) < 14:
            self._dragging = "end"
        else:  # jump the nearest marker to the click position
            self._dragging = "start" if abs(ev.x - xs) < abs(ev.x - xe) else "end"
            self._on_drag(ev)
            return
        self._on_drag(ev)

    def _on_drag(self, ev):
        if not self._dragging or self._duration <= 0:
            return
        t = self._x2t(ev.x)
        if self._dragging == "start":
            self._start = min(t, self._end - 0.01)
        else:
            self._end = max(t, self._start + 0.01)
        self._redraw()
        if self._on_change:
            self._on_change(self._start, self._end)

    def _release(self):
        self._dragging = None

    def _redraw(self):
        self.delete("all")
        if self._env is None or self._duration <= 0:
            self.create_text(self._cw // 2, self._chh // 2, fill="#666",
                             text="Ses dosyası yükleyin",
                             font=("Segoe UI", 12))
            return
        cy = self._chh / 2
        gain = (self._chh / 2 - 12)
        usable = self._cw - 2 * self.PAD
        n = len(self._env)
        for px in range(int(usable)):
            i = min(n - 1, int(px * n / usable))
            lo, hi = self._env[i]
            x = self.PAD + px
            self.create_line(x, cy - hi * gain, x, cy - lo * gain + 1,
                             fill=WAVE_COLOR)
        xs, xe = self._t2x(self._start), self._t2x(self._end)
        # dim the deselected regions
        if xs > self.PAD:
            self.create_rectangle(self.PAD, 0, xs, self._chh, fill="black",
                                  stipple="gray50", outline="")
        if xe < self._cw - self.PAD:
            self.create_rectangle(xe, 0, self._cw - self.PAD, self._chh,
                                  fill="black", stipple="gray50", outline="")
        for x, tag in ((xs, "start"), (xe, "end")):
            self.create_line(x, 0, x, self._chh, fill=ACCENT, width=2)
            self.create_polygon(x - 6, 0, x + 6, 0, x, 10, fill=ACCENT)
            self.create_polygon(x - 6, self._chh, x + 6, self._chh, x, self._chh - 10,
                                fill=ACCENT)
        self.create_line(self.PAD, cy, self._cw - self.PAD, cy,
                         fill="#333d4d")
