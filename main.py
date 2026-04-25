"""
ANTIVYRE — Free, AI-powered Antivirus
Copyright (c) 2019–2025 FreddyDeveloper (https://www.freddydeveloper.com)
License: GNU GPL v3 — Free forever. Donations welcome: https://paypal.me/freddydeveloper
"""

import sys
import os
import traceback
from pathlib import Path
# test phylaris review
# ── Hide the black CMD window on Windows ─────────────────────────────────
if sys.platform == "win32":
    import ctypes
    ctypes.windll.user32.ShowWindow(
        ctypes.windll.kernel32.GetConsoleWindow(), 0
    )

# ── Single instance enforcement ───────────────────────────────────────────
if sys.platform == "win32":
    import ctypes
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "AntivyreSingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:
        # Already running — bring the existing window to front instead of showing error
        HWND_BROADCAST = 0xFFFF
        WM_USER        = 0x0400
        ANTIVYRE_SHOW  = WM_USER + 1
        ctypes.windll.user32.PostMessageW(HWND_BROADCAST, ANTIVYRE_SHOW, 0, 0)
        sys.exit(0)

# Ensure bundled libs are importable when running as exe
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --startup flag is passed by the Windows registry autostart entry.
# When present, the app starts silently in the tray (no window shown).
STARTUP_MODE = "--startup" in sys.argv

def main():
    try:
        from ui.app import AntivyreApp
        app = AntivyreApp(silent_start=STARTUP_MODE)
        app.run()
    except Exception as e:
        # Write crash log so we can diagnose instead of silent close
        log_path = Path.home() / ".antivyre" / "crash.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w") as f:
            f.write(traceback.format_exc())
        # Show error in a simple dialog if tkinter is available
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "ANTIVYRE — Startup Error",
                f"ANTIVYRE failed to start.\n\nError: {e}\n\nCrash log saved to:\n{log_path}"
            )
            root.destroy()
        except Exception:
            pass

if __name__ == "__main__":
    main()
