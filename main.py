"""Teufort Toolkit — entry point.

    python main.py
"""

import sys
import traceback


def main():
    try:
        from gui.app import run
        run()
    except Exception:
        traceback.print_exc()
        try:
            import tkinter.messagebox as mb
            mb.showerror("Teufort Toolkit — Hata",
                         "Uygulama başlatılamadı:\n\n"
                         + traceback.format_exc(limit=5))
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
