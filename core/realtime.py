"""
ANTIVYRE — Real-time File System Monitor
Watches high-risk folders for new/modified files and scans them instantly.

Uses watchdog. Install with: pip install watchdog
Falls back silently if not installed.

Monitored paths (all high-risk for malware entry):
  - Downloads, Desktop, Documents
  - %TEMP%, %APPDATA%, %LOCALAPPDATA%
  - Startup folder
  - C:/Windows/Temp
"""

import threading
import time
from pathlib import Path
from typing import Callable, Optional

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

import os

# ── Paths to monitor ─────────────────────────────────────────────────────
def _get_watch_paths() -> list[Path]:
    home = Path.home()
    paths = [
        home / "Downloads",
        home / "Desktop",
        home / "Documents",
        Path(os.path.expandvars(r"%TEMP%")),
        Path(os.path.expandvars(r"%APPDATA%")),
        Path(os.path.expandvars(r"%LOCALAPPDATA%")),
        Path(os.path.expandvars(
            r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
        )),
        Path(r"C:\Windows\Temp"),
        Path(r"C:\Users\Public\Downloads"),
    ]
    return [p for p in paths if p.exists()]


# ── High-risk file extensions ─────────────────────────────────────────────
HIGH_RISK_EXTENSIONS = {
    ".exe", ".dll", ".sys", ".scr", ".com", ".cpl",
    ".bat", ".cmd", ".ps1", ".psm1", ".psd1",
    ".vbs", ".vbe", ".js", ".jse",
    ".wsf", ".wsh", ".hta",
    ".jar", ".apk",
    ".msi", ".msp", ".msc",
    ".reg",
}


class _ThreatHandler(FileSystemEventHandler):
    """
    Watchdog event handler — inherits properly from FileSystemEventHandler.
    Called by watchdog on every filesystem event in monitored folders.
    """

    def __init__(self, scan_callback: Callable[[str], None]):
        super().__init__()
        self._scan_cb  = scan_callback
        self._pending:  set[str] = set()
        self._lock      = threading.Lock()
        # Small debounce: wait 500ms before scanning a file
        # (avoids scanning half-written files)
        self._debounce_ms = 500

    def on_created(self, event):
        if not event.is_directory:
            self._schedule(event.src_path)

    def on_moved(self, event):
        # File renamed/moved in — the dest is the new file
        if not event.is_directory:
            self._schedule(event.dest_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._schedule(event.src_path)

    def _schedule(self, path: str):
        ext = Path(path).suffix.lower()
        if ext not in HIGH_RISK_EXTENSIONS:
            return
        with self._lock:
            if path in self._pending:
                return              # already queued
            self._pending.add(path)

        # Debounce: scan after short delay so file is fully written
        def delayed_scan():
            time.sleep(self._debounce_ms / 1000)
            with self._lock:
                self._pending.discard(path)
            try:
                if Path(path).exists():
                    self._scan_cb(path)
            except Exception:
                pass

        t = threading.Thread(target=delayed_scan, daemon=True)
        t.start()


class RealTimeMonitor:
    """
    Manages watchdog observers across all high-risk paths.

    Usage:
        monitor = RealTimeMonitor(callback=my_scan_fn)
        monitor.start()   # non-blocking, runs in background
        monitor.stop()    # clean shutdown
    """

    def __init__(self, scan_callback: Callable[[str], None]):
        self._callback  = scan_callback
        self._observer = None  # type: ignore
        self._running   = False
        self._watched_paths: list[str] = []

    @property
    def available(self) -> bool:
        return WATCHDOG_AVAILABLE

    @property
    def running(self) -> bool:
        return self._running

    @property
    def watched_paths(self) -> list[str]:
        return list(self._watched_paths)

    def start(self) -> bool:
        """
        Start monitoring. Non-blocking — observer runs in its own thread.
        Pre-tests each folder for permission before scheduling.
        Skips folders with Access Denied (e.g. C:\Windows\Temp without admin).
        Returns True if at least one folder is monitored successfully.
        """
        if not WATCHDOG_AVAILABLE:
            return False
        if self._running:
            return True

        handler  = _ThreatHandler(self._callback)
        observer = Observer()
        scheduled = 0

        for path in _get_watch_paths():
            # Pre-check permission with a Windows API call before scheduling.
            # This prevents observer.start() from failing due to one denied folder.
            try:
                import ctypes
                GENERIC_READ     = 0x80000000
                FILE_SHARE_ALL   = 0x07
                OPEN_EXISTING    = 3
                FILE_FLAG_BACKUP = 0x02000000
                INVALID_HANDLE   = ctypes.c_void_p(-1).value
                h = ctypes.windll.kernel32.CreateFileW(
                    str(path), GENERIC_READ, FILE_SHARE_ALL,
                    None, OPEN_EXISTING, FILE_FLAG_BACKUP, None
                )
                if h == INVALID_HANDLE:
                    continue  # Access denied — skip this folder silently
                ctypes.windll.kernel32.CloseHandle(h)
            except Exception:
                pass  # Not on Windows or ctypes unavailable — try anyway

            try:
                observer.schedule(handler, str(path), recursive=False)
                self._watched_paths.append(str(path))
                scheduled += 1
            except Exception:
                pass

        if scheduled == 0:
            return False

        try:
            observer.start()
            self._observer = observer
            self._running  = True
            return True
        except Exception:
            return False

    def stop(self):
        """Cleanly stop the observer."""
        if self._observer and self._running:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                pass
        self._running        = False
        self._observer       = None
        self._watched_paths  = []

    def add_path(self, path: str) -> bool:
        """Add a new path to monitor at runtime (e.g. USB drive inserted)."""
        if not self._observer or not self._running:
            return False
        p = Path(path)
        if not p.exists() or str(path) in self._watched_paths:
            return False
        try:
            handler = _ThreatHandler(self._callback)
            self._observer.schedule(handler, str(path), recursive=False)
            self._watched_paths.append(str(path))
            return True
        except Exception:
            return False