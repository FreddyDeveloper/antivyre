"""
ANTIVYRE — Auto-Updater v1.1
Handles three independent update channels:

1. MALWARE HASHES   — community-maintained MD5 hash database (GitHub)
2. MAGIKA ENGINE    — pip upgrade of the Magika library itself
3. APP VERSION      — checks GitHub for a new ANTIVYRE release

All updates run in background threads, never block the UI.
All network calls validate HTTPS + trusted host before executing.
Atomic file writes — no corrupt states if process is killed mid-update.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Optional, Callable

# ── URLs & trust ──────────────────────────────────────────────────────────
TRUSTED_HOST       = "raw.githubusercontent.com"
MANIFEST_URL       = "https://raw.githubusercontent.com/FreddyDeveloper/antivyre/main/updates/manifest.json"
HASHES_URL         = "https://raw.githubusercontent.com/FreddyDeveloper/antivyre/main/db/malicious_hashes.txt"

DB_PATH = Path(__file__).parent.parent / "db" / "malicious_hashes.txt"


# ── URL validation (only HTTPS from trusted host) ─────────────────────────
def _validate_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme == "https" and parsed.netloc == TRUSTED_HOST


def _fetch(url: str, timeout: int = 15) -> Optional[bytes]:
    if not _validate_url(url):
        raise ValueError(f"Untrusted URL blocked: {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ANTIVYRE/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (urllib.error.URLError, OSError):
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  1. MALWARE HASH DATABASE UPDATE
# ═══════════════════════════════════════════════════════════════════════════

def update_hash_database(
    on_progress: Optional[Callable[[str], None]] = None
) -> bool:
    """
    Download the latest malware hash database from GitHub.
    Uses atomic write (temp → verify → rename) — safe on crash.
    Returns True on success.
    """
    if on_progress:
        on_progress("Fetching latest malware signatures…")

    data = _fetch(HASHES_URL)
    if not data:
        if on_progress:
            on_progress("Could not reach signature server.")
        return False

    # Sanity check — must be a text file with at least one hash
    try:
        text = data.decode("utf-8")
        valid_lines = [
            l.strip() for l in text.splitlines()
            if l.strip() and not l.startswith("#") and len(l.strip()) == 32
        ]
        if not valid_lines:
            if on_progress:
                on_progress("Signature file appears empty or corrupt.")
            return False
    except UnicodeDecodeError:
        return False

    # Atomic write
    try:
        dir_ = str(DB_PATH.parent)
        os.makedirs(dir_, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=dir_, prefix=".hashes_", suffix=".tmp")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp_path, str(DB_PATH))   # atomic rename
        if on_progress:
            on_progress(f"Signatures updated — {len(valid_lines)} hashes loaded.")
        return True
    except OSError as e:
        if on_progress:
            on_progress(f"Write error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════
#  2. MAGIKA ENGINE UPDATE
# ═══════════════════════════════════════════════════════════════════════════

def get_magika_version() -> Optional[str]:
    """Return the currently installed Magika version string."""
    try:
        import magika
        return getattr(magika, "__version__", None)
    except ImportError:
        return None


def update_magika(
    on_progress: Optional[Callable[[str], None]] = None
) -> bool:
    """
    Upgrade Magika to the latest version via pip.
    Runs pip in a subprocess — never in-process (avoids import conflicts).
    Returns True if upgrade succeeded or was already up to date.
    """
    current = get_magika_version()
    if on_progress:
        on_progress(f"Checking Magika (current: {current or 'unknown'})…")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "magika",
             "--quiet", "--no-color"],
            capture_output=True,
            text=True,
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if result.returncode == 0:
            new_ver = get_magika_version()
            if on_progress:
                if new_ver and new_ver != current:
                    on_progress(f"Magika updated: {current} → {new_ver}. Restart to apply.")
                else:
                    on_progress(f"Magika is up to date ({new_ver}).")
            return True
        else:
            if on_progress:
                on_progress(f"Magika update failed: {result.stderr[:200]}")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        if on_progress:
            on_progress(f"Magika update error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════
#  3. APP VERSION CHECK
# ═══════════════════════════════════════════════════════════════════════════

def check_for_app_update(current_version: str) -> Optional[dict]:
    """
    Fetch the GitHub release manifest and return info if a newer version exists.
    Returns None if already up to date or on network error.

    manifest.json format:
    {
      "latest_version": "1.1.0",
      "download_url": "https://github.com/FreddyDeveloper/antivyre/releases/...",
      "release_notes": "Bug fixes and improvements",
      "required": false
    }
    """
    data = _fetch(MANIFEST_URL)
    if not data:
        return None
    try:
        manifest = json.loads(data)
        latest   = manifest.get("latest_version", "")
        if _version_gt(latest, current_version):
            return manifest
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def _version_gt(v1: str, v2: str) -> bool:
    try:
        def parse(v):
            return tuple(int(x) for x in v.lstrip("v").split("."))
        return parse(v1) > parse(v2)
    except (ValueError, AttributeError):
        return False


# ═══════════════════════════════════════════════════════════════════════════
#  COMBINED ASYNC UPDATER — runs all three in sequence, background thread
# ═══════════════════════════════════════════════════════════════════════════

class AutoUpdater:
    """
    Runs all update checks silently in a background thread.
    The UI receives progress via callbacks — never blocks.

    Usage:
        updater = AutoUpdater(
            current_version="1.0.0",
            on_progress=lambda msg: print(msg),
            on_app_update=lambda info: show_update_dialog(info),
            on_magika_updated=lambda: notify_restart_needed(),
        )
        updater.start()          # fire and forget
        updater.run_now()        # force immediate check
    """

    # Check interval: every 6 hours
    CHECK_INTERVAL_HOURS = 6

    def __init__(
        self,
        current_version:   str,
        on_progress:       Optional[Callable[[str], None]] = None,
        on_app_update:     Optional[Callable[[dict], None]] = None,
        on_magika_updated: Optional[Callable[[], None]]    = None,
    ):
        self._version          = current_version
        self._on_progress      = on_progress
        self._on_app_update    = on_app_update
        self._on_magika_updated = on_magika_updated
        self._stop_event       = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _progress(self, msg: str):
        if self._on_progress:
            try:
                self._on_progress(msg)
            except Exception:
                pass

    def _run_all_checks(self):
        """Run all three update channels sequentially."""

        # 1. Hash database (fast, safe, always)
        self._progress("🔄 Updating malware signatures…")
        update_hash_database(on_progress=self._progress)

        if self._stop_event.is_set():
            return

        # 2. Magika engine
        self._progress("🔄 Checking Magika AI engine…")
        current_magika = get_magika_version()
        updated = update_magika(on_progress=self._progress)
        new_magika = get_magika_version()
        if updated and new_magika and new_magika != current_magika:
            if self._on_magika_updated:
                self._on_magika_updated()

        if self._stop_event.is_set():
            return

        # 3. App version
        self._progress("🔄 Checking for ANTIVYRE updates…")
        update_info = check_for_app_update(self._version)
        if update_info and self._on_app_update:
            self._on_app_update(update_info)
        elif not update_info:
            self._progress("✓ ANTIVYRE is up to date.")

    def run_now(self):
        """Trigger an immediate update check in background."""
        t = threading.Thread(target=self._run_all_checks, daemon=True)
        t.start()

    def start(self):
        """
        Start the periodic update scheduler.
        First check runs after 30 seconds (not at startup to avoid slowing launch).
        Subsequent checks every CHECK_INTERVAL_HOURS.
        """
        if self._thread and self._thread.is_alive():
            return

        def loop():
            # Initial delay — let the app finish loading
            self._stop_event.wait(timeout=30)
            if self._stop_event.is_set():
                return
            while not self._stop_event.is_set():
                try:
                    self._run_all_checks()
                except Exception:
                    pass
                # Wait for next interval (or until stopped)
                self._stop_event.wait(
                    timeout=self.CHECK_INTERVAL_HOURS * 3600
                )

        self._thread = threading.Thread(target=loop, daemon=True, name="HSUpdater")
        self._thread.start()

    def stop(self):
        self._stop_event.set()
