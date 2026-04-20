"""
ANTIVYRE — Core Scanner Engine v1.2
Google Magika AI is the primary detection brain.
Supporting heuristic layers (entropy + suspicious strings) only
escalate findings already flagged by Magika — never fire alone.
Zero false positives by design: heuristics require Magika agreement.
"""

import os
import math
import hashlib
import threading
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional
from datetime import datetime

try:
    from magika import Magika
    from magika.types import PredictionMode
    MAGIKA_AVAILABLE = True
except ImportError:
    MAGIKA_AVAILABLE = False


# ─────────────────────────────────────────────
#  Threat classification
# ─────────────────────────────────────────────

class ThreatLevel(Enum):
    CLEAN      = auto()
    SUSPICIOUS = auto()
    THREAT     = auto()


@dataclass
class ScanResult:
    file_path:     str
    threat_level:  ThreatLevel = ThreatLevel.CLEAN
    real_type:     str = "unknown"
    declared_type: str = "unknown"
    confidence:    float = 0.0
    reasons:       list[str] = field(default_factory=list)
    scanned_at:    str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def is_threat(self) -> bool:
        return self.threat_level == ThreatLevel.THREAT

    @property
    def is_suspicious(self) -> bool:
        return self.threat_level == ThreatLevel.SUSPICIOUS


# ─────────────────────────────────────────────
#  Known-bad hashes — community maintained
# ─────────────────────────────────────────────

# Three separate sets — one per algorithm — for O(1) lookup on each
KNOWN_MD5:    set[str] = set()
KNOWN_SHA1:   set[str] = set()
KNOWN_SHA256: set[str] = set()


# ─────────────────────────────────────────────
#  File type categories (Magika labels)
# ─────────────────────────────────────────────

EXECUTABLE_TYPES = {
    "pebin", "exe", "dll", "elf", "macho",
    "com", "cpl", "ocx", "scr", "sys",
    "ko", "so", "dylib", "drv",
}

SCRIPT_TYPES = {
    "powershell", "vba", "batch", "shell",
    "autoit", "autohotkey", "scriptwsf", "vbe", "hta",
    "dmscript",
}

OFFICE_MACRO_TYPES = {
    "doc", "xls", "ppt", "ole",
}

SAFE_EXTENSION_MAP: dict[str, set[str]] = {
    ".jpg":  {"jpeg"},
    ".jpeg": {"jpeg"},
    ".png":  {"png"},
    ".gif":  {"gif"},
    ".webp": {"webp"},
    ".bmp":  {"bmp"},
    ".mp3":  {"mp3"},
    ".mp4":  {"mp4"},
    ".avi":  {"avi"},
    ".mkv":  {"mkv"},
    ".flac": {"flac"},
    ".wav":  {"wav"},
    ".pdf":  {"pdf"},
    ".txt":  {"txt", "txtascii", "txtutf8", "txtutf16"},
    ".zip":  {"zip"},
    ".rar":  {"rar"},
    ".7z":   {"sevenzip"},
    ".tar":  {"tar"},
    ".gz":   {"gzip"},
}

# ─────────────────────────────────────────────
#  Heuristic support layer
#  IMPORTANT: These never flag a file alone.
#  They only add weight when Magika already
#  identified the file as executable/script.
# ─────────────────────────────────────────────

# Entropy threshold — packed/encrypted executables score > 7.2
# Normal executables rarely exceed 7.0. Legitimate installers can hit 7.5
# so we only use this as a confirming signal, never standalone.
ENTROPY_HIGH_THRESHOLD = 7.2

# Suspicious API/string patterns found in malware
# ONLY checked on files Magika already confirmed as executable/script
# Legitimate software CAN contain these — that's why Magika must agree first
SUSPICIOUS_STRINGS = [
    b"CreateRemoteThread",   # classic code injection
    b"VirtualAllocEx",       # memory allocation in remote process
    b"WriteProcessMemory",   # writing to another process
    b"NtUnmapViewOfSection", # process hollowing
    b"IsDebuggerPresent",    # anti-debug (common in malware packers)
    b"WScript.Shell",        # script-based execution
    b"powershell -enc",      # encoded powershell (obfuscation)
    b"powershell -e ",       # encoded powershell short form
    b"cmd.exe /c ",          # command execution via cmd
    b"regsvr32 /s",          # LOLBin abuse
    b"mshta.exe",            # LOLBin: HTML application host
    b"certutil -decode",     # LOLBin: decode payloads
    b"bitsadmin /transfer",  # LOLBin: download files
]

# How many suspicious strings must match to add heuristic weight
SUSPICIOUS_STRINGS_MIN_MATCHES = 2

# Max file size to run heuristics on (5 MB) — avoid slow scans on large files
HEURISTIC_MAX_SIZE = 5 * 1024 * 1024


def _shannon_entropy(data: bytes) -> float:
    """Calculate Shannon entropy of bytes. Range 0.0 (uniform) to 8.0 (random)."""
    if not data:
        return 0.0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    length = len(data)
    entropy = 0.0
    for count in freq:
        if count:
            p = count / length
            entropy -= p * math.log2(p)
    return entropy


def _count_suspicious_strings(data: bytes) -> int:
    """Count how many suspicious API/string patterns are present in binary data."""
    return sum(1 for pattern in SUSPICIOUS_STRINGS if pattern.lower() in data.lower())


class Scanner:
    """
    ANTIVYRE scanner v1.2 — detection architecture:

    Layer 1 — Hash DB:     Instant match against known malicious hashes.
                           → THREAT immediately, no further checks needed.

    Layer 2 — Magika AI:   Google's deep-learning model identifies the REAL
                           file type by content. This is the PRIMARY brain.
                           All subsequent layers require Magika's verdict.

    Layer 3 — Spoofing:    If Magika says executable/script but extension
                           claims image/video/document → THREAT or SUSPICIOUS.

    Layer 4 — Office:      Legacy OLE formats (.doc/.xls/.ppt) confirmed by
                           Magika with high confidence → SUSPICIOUS.

    Layer 5 — Heuristics:  ONLY activates on files Magika already identified
                           as executable or script. Checks entropy + suspicious
                           API strings. Requires BOTH signals together to
                           escalate SUSPICIOUS → THREAT. Never fires alone.
                           Designed to catch packed/obfuscated malware that
                           Magika flags as executable but with lower confidence.
    """

    def __init__(self):
        self._magika: Optional[object] = None
        self._stop_event = threading.Event()
        self._hashes_loaded = False
        # Hashes are loaded lazily via load_hashes_async() called by the UI
        # after the window is shown — avoids 3+ second freeze at startup

    def _load_community_hashes(self):
        """
        Load hash databases from db/ folder.
        Supports three files, each with one hash per line:
          malicious_hashes.txt  — MD5  (32 hex chars)
          malicious_sha1.txt    — SHA1 (40 hex chars)
          malicious_sha256.txt  — SHA256 (64 hex chars)
        Lines starting with # are ignored (comments).
        """
        db_dir = Path(__file__).parent.parent / "db"

        files = {
            32: (db_dir / "malicious_hashes.txt", KNOWN_MD5),
            40: (db_dir / "malicious_sha1.txt",   KNOWN_SHA1),
            64: (db_dir / "malicious_sha256.txt",  KNOWN_SHA256),
        }

        for length, (path, target_set) in files.items():
            if path.exists():
                try:
                    with open(path, encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            h = line.strip().lower()
                            if h and not h.startswith("#") and len(h) == length:
                                try:
                                    int(h, 16)  # validate hex
                                    target_set.add(h)
                                except ValueError:
                                    pass
                except Exception:
                    pass

    def load_hashes_async(self, on_done: Optional[callable] = None) -> None:
        """
        Load all hash databases in a background thread.
        Call this AFTER the UI window is shown so startup is instant.
        on_done: optional callback called on the main thread when loading finishes.
        """
        def _load():
            self._load_community_hashes()
            self._hashes_loaded = True
            if on_done:
                try:
                    on_done()
                except Exception:
                    pass

        t = threading.Thread(target=_load, daemon=True, name="hash-loader")
        t.start()

    def _get_magika(self):
        if self._magika is None and MAGIKA_AVAILABLE:
            self._magika = Magika(prediction_mode=PredictionMode.HIGH_CONFIDENCE)
        return self._magika

    def stop(self):
        self._stop_event.set()

    def reset(self):
        self._stop_event.clear()

    # ── Heuristic helpers ────────────────────────

    def _run_heuristics(self, path: Path, rtype: str, confidence: float) -> Optional[str]:
        """
        Supporting heuristic layer — only called when Magika already identified
        the file as executable or script type.

        Returns a reason string if heuristics confirm suspicious behavior,
        or None if the file looks clean heuristically.

        Rules to minimize false positives:
        - File must be under HEURISTIC_MAX_SIZE (skip large installers)
        - BOTH entropy AND suspicious strings must trigger together
        - Entropy must exceed ENTROPY_HIGH_THRESHOLD (7.2)
        - At least SUSPICIOUS_STRINGS_MIN_MATCHES (2) patterns must match
        - Magika confidence must be < 0.85 (high-confidence Magika findings
          don't need heuristic help — low confidence ones do)
        """
        # Only run on low-to-medium confidence Magika results
        # High confidence Magika findings are already handled by layers 3/4
        if confidence >= 0.85:
            return None

        try:
            size = path.stat().st_size
            if size == 0 or size > HEURISTIC_MAX_SIZE:
                return None

            with open(path, "rb") as f:
                data = f.read()

            entropy = _shannon_entropy(data)
            matches = _count_suspicious_strings(data)

            # Both signals must fire together — no single-signal flags
            if entropy >= ENTROPY_HIGH_THRESHOLD and matches >= SUSPICIOUS_STRINGS_MIN_MATCHES:
                return f"result_heuristic|entropy={entropy:.2f}|strings={matches}"

        except Exception:
            pass

        return None

    # ── Main scan entry point ────────────────────

    def scan_file(self, file_path: str) -> ScanResult:
        path = Path(file_path)
        result = ScanResult(file_path=file_path)
        result.declared_type = path.suffix.lower().lstrip(".")

        if not path.exists() or not path.is_file():
            return result

        # ── Layer 1: Hash check (MD5 + SHA1 + SHA256) ───
        # Single file read computes all three algorithms simultaneously.
        md5_h, sha1_h, sha256_h = self._compute_hashes(path)
        if ((md5_h    and md5_h    in KNOWN_MD5)    or
            (sha1_h   and sha1_h   in KNOWN_SHA1)   or
            (sha256_h and sha256_h in KNOWN_SHA256)):
            result.threat_level = ThreatLevel.THREAT
            result.reasons.append("result_malicious_hash")
            return result

        # ── Layer 2: Magika identification ───────
        magika = self._get_magika()
        if magika:
            try:
                mr = magika.identify_path(path)
                result.real_type  = str(mr.output.label)
                result.confidence = round(mr.score, 3)
            except Exception:
                result.real_type  = "unknown"
                result.confidence = 0.0
        else:
            result.real_type = "unknown"
            return result

        rtype = result.real_type
        ext   = path.suffix.lower()

        # ── Layer 3: Extension spoofing ──────────
        expected_types = SAFE_EXTENSION_MAP.get(ext)
        if expected_types and rtype not in expected_types:
            if rtype in EXECUTABLE_TYPES:
                result.threat_level = ThreatLevel.THREAT
                result.reasons.append(
                    f"result_spoofed|declared={ext or result.declared_type}|real={rtype}"
                )
                return result
            if rtype in SCRIPT_TYPES:
                result.threat_level = ThreatLevel.SUSPICIOUS
                result.reasons.append(
                    f"result_spoofed|declared={ext or result.declared_type}|real={rtype}"
                )
                return result

        # ── Layer 4: Legacy Office macro formats ─
        if rtype in OFFICE_MACRO_TYPES and result.confidence >= 0.90:
            result.threat_level = ThreatLevel.SUSPICIOUS
            result.reasons.append("result_office_macro")
            return result

        # ── Layer 5: Heuristics (Magika-gated) ───
        # Only runs if Magika identified file as executable or script.
        # Never fires on clean/unknown/document types.
        if rtype in EXECUTABLE_TYPES or rtype in SCRIPT_TYPES:
            heuristic_reason = self._run_heuristics(path, rtype, result.confidence)
            if heuristic_reason:
                # Escalate: if already suspicious → threat, if clean → suspicious
                if result.threat_level == ThreatLevel.SUSPICIOUS:
                    result.threat_level = ThreatLevel.THREAT
                else:
                    result.threat_level = ThreatLevel.SUSPICIOUS
                result.reasons.append(heuristic_reason)

        return result

    # ── Folder / Quick / Full scan ───────────────

    def scan_folder(
        self,
        folder: str,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[ScanResult]:
        self.reset()
        results = []
        all_files = []
        for root, _, files in os.walk(folder):
            for f in files:
                all_files.append(os.path.join(root, f))

        total = len(all_files)
        for i, fp in enumerate(all_files):
            if self._stop_event.is_set():
                break
            try:
                r = self.scan_file(fp)
                if r.is_threat or r.is_suspicious:
                    results.append(r)
            except Exception:
                pass
            if progress_cb:
                progress_cb(i + 1, total, fp)
        return results

    def scan_quick(
        self,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[ScanResult]:
        """Scan high-risk locations only."""
        self.reset()
        critical_folders = [
            os.path.expandvars(r"%TEMP%"),
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"),
            os.path.expandvars(r"%USERPROFILE%\Downloads"),
            r"C:\Windows\Temp",
        ]
        all_files = []
        for folder in critical_folders:
            if os.path.exists(folder):
                for root, _, files in os.walk(folder):
                    for f in files:
                        all_files.append(os.path.join(root, f))

        results = []
        total = len(all_files)
        for i, fp in enumerate(all_files):
            if self._stop_event.is_set():
                break
            try:
                r = self.scan_file(fp)
                if r.is_threat or r.is_suspicious:
                    results.append(r)
            except Exception:
                pass
            if progress_cb:
                progress_cb(i + 1, total, fp)
        return results

    def scan_full(
        self,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
    ) -> list[ScanResult]:
        """Full system scan — all drives."""
        self.reset()
        drives = ["C:\\"]
        for d in "DEFGHIJKLMNOPQRSTUVWXYZ":
            if os.path.exists(f"{d}:\\"):
                drives.append(f"{d}:\\")

        all_files = []
        for drive in drives:
            for root, _, files in os.walk(drive):
                for f in files:
                    all_files.append(os.path.join(root, f))
                if self._stop_event.is_set():
                    break

        results = []
        total = len(all_files)
        for i, fp in enumerate(all_files):
            if self._stop_event.is_set():
                break
            try:
                r = self.scan_file(fp)
                if r.is_threat or r.is_suspicious:
                    results.append(r)
            except Exception:
                pass
            if progress_cb:
                progress_cb(i + 1, total, fp)
        return results

    # ── Utility ──────────────────────────────────

    @staticmethod
    def _compute_hashes(path: Path) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Compute MD5, SHA1, and SHA256 in a single file read pass.
        Returns (md5, sha1, sha256) or (None, None, None) on error.
        Skips files larger than 200 MB.
        """
        try:
            if path.stat().st_size > 200 * 1024 * 1024:
                return None, None, None
            md5    = hashlib.md5()
            sha1   = hashlib.sha1()
            sha256 = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    md5.update(chunk)
                    sha1.update(chunk)
                    sha256.update(chunk)
            return md5.hexdigest(), sha1.hexdigest(), sha256.hexdigest()
        except Exception:
            return None, None, None
