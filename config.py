"""Persistent settings stored in config.json. Each module keeps its own
independent export path.

Source runs keep config.json next to the code; frozen (PyInstaller) builds
use %APPDATA%\\TeufortToolkit instead — a onefile exe unpacks itself to a
throwaway temp dir, so "next to __file__" would be wiped on every launch."""

from __future__ import annotations

import json
import os
import sys
import threading


def _config_dir() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "TeufortToolkit")
        os.makedirs(base, exist_ok=True)
        return base
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = _config_dir()
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

DEFAULTS = {
    "tf2_path": "",             # detected/chosen .../Team Fortress 2/tf
    "spray_export_path": "",    # module 1
    "objector_export_path": "", # module 2
    "sound_export_path": "",    # module 3
    "last_browse_dir": "",
    "language": "",             # UI language code (empty = auto-detect)
}


class ConfigManager:
    """Thread-safe get/set with write-through persistence to config.json."""

    def __init__(self, path: str = CONFIG_PATH):
        self._path = path
        self._lock = threading.Lock()
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                stored = json.load(fh)
            if isinstance(stored, dict):
                for key in DEFAULTS:
                    if key in stored and isinstance(stored[key], str):
                        self._data[key] = stored[key]
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, OSError):
            # Corrupt config: keep defaults, it will be rewritten on next set().
            pass

    def _save(self) -> None:
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self._path)

    def get(self, key: str) -> str:
        with self._lock:
            return self._data.get(key, "")

    def set(self, key: str, value: str) -> None:
        if key not in DEFAULTS:
            raise KeyError(f"Bilinmeyen ayar: {key}")
        with self._lock:
            self._data[key] = value
            try:
                self._save()
            except OSError:
                pass  # read-only location; keep the in-memory value
