"""
ANTIVYRE — Storage / Database layer
Uses SQLite with WAL mode and atomic writes.
Pattern borrowed from git-lrc's storage/files.go — safe even on crashes.
"""

import sqlite3
import json
import os
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional

DB_PATH = Path.home() / ".antivyre" / "data.db"


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5000)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist. Safe to call multiple times."""
    conn = _get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scan_sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_type   TEXT    NOT NULL,
            started_at  TEXT    NOT NULL,
            finished_at TEXT,
            files_count INTEGER DEFAULT 0,
            threats     INTEGER DEFAULT 0,
            duration_s  REAL    DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS detections (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   INTEGER REFERENCES scan_sessions(id),
            file_path    TEXT    NOT NULL,
            threat_level TEXT    NOT NULL,
            real_type    TEXT,
            declared_type TEXT,
            confidence   REAL,
            reasons      TEXT,
            detected_at  TEXT    NOT NULL,
            action_taken TEXT    DEFAULT 'none'
        );

        CREATE TABLE IF NOT EXISTS malicious_hashes (
            hash        TEXT PRIMARY KEY,
            added_at    TEXT NOT NULL,
            source      TEXT DEFAULT 'builtin'
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS quarantine (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            original_path TEXT NOT NULL,
            quarantine_path TEXT NOT NULL,
            quarantined_at TEXT NOT NULL,
            threat_level TEXT
        );
    """)
    conn.commit()
    conn.close()


# ── Settings ──────────────────────────────────

def get_setting(key: str, default: str = "") -> str:
    try:
        conn = _get_connection()
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        conn.close()
        return row["value"] if row else default
    except Exception:
        return default


def set_setting(key: str, value: str):
    try:
        conn = _get_connection()
        conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── Scan sessions ─────────────────────────────

def start_session(scan_type: str) -> int:
    conn = _get_connection()
    cur = conn.execute(
        "INSERT INTO scan_sessions(scan_type, started_at) VALUES(?,?)",
        (scan_type, datetime.now().isoformat())
    )
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid


def finish_session(session_id: int, files_count: int, threats: int, duration_s: float):
    conn = _get_connection()
    conn.execute(
        """UPDATE scan_sessions
           SET finished_at=?, files_count=?, threats=?, duration_s=?
           WHERE id=?""",
        (datetime.now().isoformat(), files_count, threats, round(duration_s, 2), session_id)
    )
    conn.commit()
    conn.close()


def get_history(limit: int = 50) -> list[dict]:
    try:
        conn = _get_connection()
        rows = conn.execute(
            "SELECT * FROM scan_sessions ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def clear_history():
    conn = _get_connection()
    conn.execute("DELETE FROM detections")
    conn.execute("DELETE FROM scan_sessions")
    conn.commit()
    conn.close()


# ── Detections ────────────────────────────────

def save_detection(session_id: int, result) -> int:
    """Save a ScanResult to the detections table."""
    conn = _get_connection()
    cur = conn.execute(
        """INSERT INTO detections
           (session_id, file_path, threat_level, real_type, declared_type,
            confidence, reasons, detected_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            session_id,
            result.file_path,
            result.threat_level.name,
            result.real_type,
            result.declared_type,
            result.confidence,
            json.dumps(result.reasons),
            result.scanned_at,
        )
    )
    did = cur.lastrowid
    conn.commit()
    conn.close()
    return did


def update_detection_action(detection_id: int, action: str):
    conn = _get_connection()
    conn.execute(
        "UPDATE detections SET action_taken=? WHERE id=?", (action, detection_id)
    )
    conn.commit()
    conn.close()


def get_recent_detections(limit: int = 100) -> list[dict]:
    try:
        conn = _get_connection()
        rows = conn.execute(
            """SELECT d.*, s.scan_type FROM detections d
               LEFT JOIN scan_sessions s ON d.session_id=s.id
               ORDER BY d.detected_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ── Quarantine ────────────────────────────────

def quarantine_file(original_path: str, threat_level: str) -> Optional[str]:
    """
    Move a file to quarantine (atomic rename — inspired by git-lrc WriteFileAtomically).
    Returns quarantine path or None on failure.
    """
    quarantine_dir = Path.home() / ".antivyre" / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = Path(original_path).name
    dest = quarantine_dir / f"{ts}_{fname}.quarantined"

    try:
        os.rename(original_path, str(dest))  # Atomic on same filesystem
        conn = _get_connection()
        conn.execute(
            "INSERT INTO quarantine(original_path,quarantine_path,quarantined_at,threat_level) VALUES(?,?,?,?)",
            (original_path, str(dest), datetime.now().isoformat(), threat_level)
        )
        conn.commit()
        conn.close()
        return str(dest)
    except Exception:
        return None
