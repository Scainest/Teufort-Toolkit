"""Auto-detection of the Team Fortress 2 `tf` folder.

Order: Steam install path from the Windows registry, every library listed in
steamapps/libraryfolders.vdf, then a handful of common fallback locations.
"""

from __future__ import annotations

import os
import re
from typing import List, Optional

_TF2_SUFFIX = os.path.join("steamapps", "common", "Team Fortress 2", "tf")

_COMMON_STEAM_ROOTS = [
    r"C:\Program Files (x86)\Steam",
    r"C:\Program Files\Steam",
    r"C:\Steam",
    r"D:\Steam",
    r"D:\SteamLibrary",
    r"E:\Steam",
    r"E:\SteamLibrary",
]


def _registry_steam_paths() -> List[str]:
    paths = []
    try:
        import winreg
    except ImportError:
        return paths
    candidates = [
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    ]
    for hive, subkey, value_name in candidates:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
                if value:
                    paths.append(os.path.normpath(str(value)))
        except OSError:
            continue
    return paths


def _library_folders(steam_root: str) -> List[str]:
    """Extra Steam libraries from libraryfolders.vdf (best-effort regex parse)."""
    vdf = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
    libs = []
    try:
        with open(vdf, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        for match in re.finditer(r'"path"\s+"([^"]+)"', content):
            libs.append(os.path.normpath(match.group(1).replace("\\\\", "\\")))
    except OSError:
        pass
    return libs


def find_tf2_path() -> Optional[str]:
    """Absolute path of .../Team Fortress 2/tf, or None."""
    roots: List[str] = []
    for root in _registry_steam_paths() + _COMMON_STEAM_ROOTS:
        if root not in roots:
            roots.append(root)
    for root in list(roots):
        for lib in _library_folders(root):
            if lib not in roots:
                roots.append(lib)

    for root in roots:
        candidate = os.path.join(root, _TF2_SUFFIX)
        if os.path.isdir(candidate):
            return candidate
    return None


def suggested_paths(tf_path: str) -> dict:
    """Sensible per-module default export folders for a given tf directory."""
    return {
        "spray_export_path": os.path.join(tf_path, "materials", "vgui", "logos"),
        "objector_export_path": os.path.join(tf_path, "custom", "MyCustomStuff"),
        "sound_export_path": os.path.join(tf_path, "custom", "MyCustomStuff"),
    }
