"""
ANTIVYRE — Main Application UI
100% definitive version. All fixes in one file.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import os
import sys
import webbrowser
from pathlib import Path
from datetime import datetime

try:
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
except ImportError:
    pass

from core.scanner import Scanner, ThreatLevel, MAGIKA_AVAILABLE
from core.i18n import t, set_language, available_languages, _DEFAULT_LANG
from db.storage import (
    init_db, get_setting, set_setting, start_session, finish_session,
    save_detection, get_history, clear_history, quarantine_file,
)

try:
    from ui.tray import SystemTray, PYSTRAY_AVAILABLE
except Exception:
    PYSTRAY_AVAILABLE = False
    SystemTray = None

try:
    from core.realtime import RealTimeMonitor, WATCHDOG_AVAILABLE
except Exception:
    WATCHDOG_AVAILABLE = False
    RealTimeMonitor = None

try:
    from core.updater import AutoUpdater
    _HAS_UPDATER = True
except Exception:
    _HAS_UPDATER = False
    AutoUpdater = None

VERSION     = "1.2.1"
DONATE_URL  = "https://paypal.me/freddydeveloper"
GITHUB_URL  = "https://github.com/FreddyDeveloper/antivyre"
WEBSITE_URL    = "https://www.freddydeveloper.com"
ANTIVYRE_URL   = "https://www.antivyre.com"


def _get_magika_version() -> str:
    try:
        import magika as _m
        v = getattr(_m, "__version__", None)
        if v:
            return v
        import importlib.metadata
        return importlib.metadata.version("magika")
    except Exception:
        return "?"


# ── Palette ────────────────────────────────────────────────────────────────
_PALETTE_DARK = {
    "bg":       "#0d1117",
    "surface":  "#161b22",
    "surface2": "#21262d",
    "border":   "#30363d",
    "accent":   "#e67e22",
    "accent2":  "#d35400",
    "danger":   "#e74c3c",
    "success":  "#2ecc71",
    "warning":  "#f39c12",
    "info":     "#3498db",
    "text":     "#e6edf3",
    "text2":    "#8b949e",
    "text3":    "#6e7681",
    "white":    "#ffffff",
}

_PALETTE_LIGHT = {
    "bg":       "#f5f5f5",
    "surface":  "#ffffff",
    "surface2": "#ebebeb",
    "border":   "#d0d0d0",
    "accent":   "#e67e22",
    "accent2":  "#d35400",
    "danger":   "#c0392b",
    "success":  "#27ae60",
    "warning":  "#d68910",
    "info":     "#2471a3",
    "text":     "#1a1a1a",
    "text2":    "#555555",
    "text3":    "#888888",
    "white":    "#ffffff",
}

C = dict(_PALETTE_DARK)


def _load_palette():
    from db.storage import get_setting as _gs
    theme = _gs("theme", "dark")
    C.update(_PALETTE_LIGHT if theme == "light" else _PALETTE_DARK)

FONT_TITLE = ("Segoe UI", 22, "bold")
FONT_H2    = ("Segoe UI", 14, "bold")
FONT_H3    = ("Segoe UI", 12, "bold")
FONT_BODY  = ("Segoe UI", 11)
FONT_SMALL = ("Segoe UI", 10)
FONT_MONO  = ("Consolas", 10)


class AntivyreApp:

    def __init__(self, silent_start: bool = False):
        init_db()
        self.scanner        = Scanner()
        self._scan_thread: threading.Thread | None = None
        self._scan_running  = False
        self._session_id: int | None = None
        self._scan_start    = 0.0
        self._files_scanned = 0
        self._threats_found = 0
        self._last_results: list = []   # results of the most recent scan
        self._all_results:  list = []
        self._resolved_paths: set = set()
        self._resolved_paths_labels: dict = {}
        self._assets_dir = Path(__file__).parent.parent / "assets"

        # Validate + load language
        saved = get_setting("language", "")
        valid = {l["code"] for l in available_languages()}
        if not saved or saved not in valid:
            saved = _DEFAULT_LANG
            set_setting("language", saved)
        set_language(saved)

        _load_palette()

        self._silent_start = silent_start

        self.root = tk.Tk()
        self._setup_window()
        self._build_ui()

        # Tray
        self._tray = None
        if PYSTRAY_AVAILABLE and SystemTray:
            self._tray = SystemTray(
                on_open=self._show_window,
                on_quick_scan=lambda: self._start_scan("quick"),
                on_exit=self._quit_app,
                t_func=t,
                assets_dir=self._assets_dir,
            )
            self._tray.start()

        # Real-time monitor
        self._realtime = None
        if WATCHDOG_AVAILABLE and RealTimeMonitor:
            self._realtime = RealTimeMonitor(scan_callback=self._on_realtime_detection)
            if self._realtime.start():
                self._update_rt_badge(True)

        # Auto-updater
        self._updater = None
        if _HAS_UPDATER and AutoUpdater:
            self._updater = AutoUpdater(
                current_version=VERSION,
                on_progress=self._on_update_progress,
                on_app_update=self._on_app_update_available,
                on_magika_updated=self._on_magika_updated,
            )
            self._updater.start()

    # ── Window setup ──────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title("ANTIVYRE by FreddyDeveloper")
        self.root.geometry("1100x720")
        self.root.minsize(900, 600)
        self.root.configure(bg=C["bg"])
        try:
            icon_path = self._assets_dir / "icon.png"
            if icon_path.exists():
                img = tk.PhotoImage(file=str(icon_path))
                self.root.iconphoto(True, img)
        except Exception:
            pass
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        # Listen for the show-window message sent by a second instance
        if sys.platform == "win32":
            self._register_show_listener()

    def _register_show_listener(self):
        WM_USER       = 0x0400
        ANTIVYRE_SHOW = WM_USER + 1
        def _poll():
            try:
                import ctypes
                msg = ctypes.wintypes.MSG()
                while ctypes.windll.user32.PeekMessageW(
                        ctypes.byref(msg), None, ANTIVYRE_SHOW,
                        ANTIVYRE_SHOW, 1):
                    self._show_window()
            except Exception:
                pass
            self.root.after(500, _poll)
        self.root.after(500, _poll)

    # ── Layout ────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.sidebar = tk.Frame(self.root, bg=C["surface"], width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.content = tk.Frame(self.root, bg=C["bg"])
        self.content.pack(side="left", fill="both", expand=True)
        self._build_sidebar()
        self._build_pages()
        self._show_page("dashboard")

    # ── Sidebar ───────────────────────────────────────────────────────────

    def _build_sidebar(self):
        logo = tk.Frame(self.sidebar, bg=C["surface"], pady=18)
        logo.pack(fill="x")

        try:
            from PIL import Image, ImageTk
            ip = self._assets_dir / "icon.png"
            if ip.exists():
                pil = Image.open(str(ip)).resize((48, 48), Image.LANCZOS)
                self._sidebar_icon = ImageTk.PhotoImage(pil)
                tk.Label(logo, image=self._sidebar_icon, bg=C["surface"]).pack()
            else:
                raise FileNotFoundError
        except Exception:
            tk.Label(logo, text="⚡", font=("Segoe UI", 28),
                     bg=C["surface"], fg=C["accent"]).pack()

        tk.Label(logo, text=t("app_title"),
                 font=("Segoe UI", 13, "bold"),
                 bg=C["surface"], fg=C["text"]).pack()

        by = tk.Label(logo, text=t("app_by_author"),
                      font=("Segoe UI", 9),
                      bg=C["surface"], fg=C["accent"], cursor="hand2")
        by.pack()
        by.bind("<Button-1>", lambda e: webbrowser.open(WEBSITE_URL))
        by.bind("<Enter>",    lambda e: by.configure(fg=C["white"]))
        by.bind("<Leave>",    lambda e: by.configure(fg=C["accent"]))

        tk.Frame(self.sidebar, bg=C["border"], height=1).pack(fill="x", padx=16, pady=(8, 0))

        # Nav — font NEVER changes (prevents layout shift)
        self._nav_buttons = {}
        nav_items = [
            ("dashboard",  "🛡️", "nav_dashboard"),
            ("scan",       "🔍", "nav_scan"),
            ("quarantine", "🔒", "nav_quarantine"),
            ("history",    "📋", "nav_history"),
            ("settings",   "⚙️", "nav_settings"),
            ("about",      "ℹ️", "nav_about"),
        ]
        nav_frame = tk.Frame(self.sidebar, bg=C["surface"], pady=10)
        nav_frame.pack(fill="x")

        for page_id, icon, label_key in nav_items:
            row = tk.Frame(nav_frame, bg=C["surface"])
            row.pack(fill="x")
            bar = tk.Frame(row, width=3, bg=C["surface"])
            bar.pack(side="left", fill="y")
            bar.pack_propagate(False)
            btn = tk.Button(
                row,
                text=f"  {icon}  {t(label_key)}",
                font=("Segoe UI Emoji", 11),
                bg=C["surface"], fg=C["text2"],
                activebackground=C["surface2"], activeforeground=C["text"],
                relief="flat", bd=0, anchor="w", padx=17, pady=10,
                cursor="hand2",
                command=lambda p=page_id: self._show_page(p)
            )
            btn.pack(side="left", fill="x", expand=True)
            self._nav_buttons[page_id] = (btn, bar, row)

        # Bottom badges
        bottom = tk.Frame(self.sidebar, bg=C["surface"])
        bottom.pack(side="bottom", fill="x", pady=14, padx=16)
        tk.Frame(bottom, bg=C["border"], height=1).pack(fill="x", pady=(0, 8))

        magika_text  = "● Heuristic + AI Engine" if MAGIKA_AVAILABLE else t("magika_missing")
        magika_color = C["success"] if MAGIKA_AVAILABLE else C["danger"]
        tk.Label(bottom, text=magika_text,
                 font=FONT_SMALL, bg=C["surface"], fg=magika_color).pack(anchor="w")

        self._rt_badge = tk.Label(bottom, text="● AI-powered Antivirus",
                                   font=FONT_SMALL, bg=C["surface"], fg=C["warning"])
        self._rt_badge.pack(anchor="w")

        tk.Label(bottom, text=f"v{VERSION}",
                 font=FONT_SMALL, bg=C["surface"], fg=C["text3"]).pack(anchor="w")

    # ── Pages ─────────────────────────────────────────────────────────────

    def _build_pages(self):
        self._pages = {}
        for name in ("dashboard", "scan", "quarantine", "history", "settings", "about"):
            self._pages[name] = tk.Frame(self.content, bg=C["bg"])
        self._build_dashboard(self._pages["dashboard"])
        self._build_scan(self._pages["scan"])
        self._build_quarantine(self._pages["quarantine"])
        self._build_history(self._pages["history"])
        self._build_settings(self._pages["settings"])
        self._build_about(self._pages["about"])

    def _show_page(self, name: str):
        for page in self._pages.values():
            page.pack_forget()
        self._pages[name].pack(fill="both", expand=True)
        for pid, (btn, bar, row) in self._nav_buttons.items():
            if pid == name:
                bar.configure(bg=C["accent"])
                row.configure(bg=C["surface2"])
                btn.configure(bg=C["surface2"], fg=C["accent"])
            else:
                bar.configure(bg=C["surface"])
                row.configure(bg=C["surface"])
                btn.configure(bg=C["surface"], fg=C["text2"])
        if name == "history":
            self._refresh_history()
        if name == "quarantine":
            self._quarantine_refresh()

    # ── Dashboard ─────────────────────────────────────────────────────────

    def _build_dashboard(self, parent):
        hdr = tk.Frame(parent, bg=C["bg"], pady=32, padx=40)
        hdr.pack(fill="x")
        tk.Label(hdr, text=t("nav_dashboard"), font=FONT_TITLE,
                 bg=C["bg"], fg=C["text"]).pack(anchor="w")
        tk.Label(hdr, text=t("app_tagline"), font=FONT_SMALL,
                 bg=C["bg"], fg=C["text3"]).pack(anchor="w")

        card = tk.Frame(parent, bg=C["surface"])
        card.pack(fill="x", padx=40, pady=(0, 24))
        inner = tk.Frame(card, bg=C["surface"], pady=28, padx=32)
        inner.pack(fill="x")
        self._status_icon = tk.Label(inner, text="🛡️", font=("Segoe UI", 40),
                                      bg=C["surface"], fg=C["success"])
        self._status_icon.pack(side="left")
        st = tk.Frame(inner, bg=C["surface"])
        st.pack(side="left", padx=20)
        self._status_label = tk.Label(st, text=t("dashboard_status_protected"),
                                       font=("Segoe UI", 16, "bold"),
                                       bg=C["surface"], fg=C["success"])
        self._status_label.pack(anchor="w")
        self._last_scan_label = tk.Label(st, text=t("dashboard_last_scan", time="—"),
                                          font=FONT_BODY, bg=C["surface"], fg=C["text2"])
        self._last_scan_label.pack(anchor="w")

        stats = tk.Frame(parent, bg=C["bg"])
        stats.pack(fill="x", padx=40, pady=(0, 24))
        stats.columnconfigure((0, 1, 2), weight=1)
        self._stat_threats = self._stat_card(stats, "0", t("dashboard_threats_found"), C["danger"],  0)
        self._stat_files   = self._stat_card(stats, "0", t("dashboard_files_scanned"), C["info"],    1)
        self._stat_time    = self._stat_card(stats, "—", t("dashboard_scan_duration"), C["accent"],  2)

        actions = tk.Frame(parent, bg=C["bg"])
        actions.pack(fill="x", padx=40)
        for label_key, stype, color in [
            ("scan_quick",  "quick",  C["accent"]),
            ("scan_full",   "full",   C["danger"]),
            ("scan_folder", "folder", C["info"]),
        ]:
            tk.Button(actions, text=t(label_key),
                      font=FONT_H3, bg=color, fg=C["white"],
                      activebackground=C["surface2"],
                      relief="flat", bd=0, padx=24, pady=12, cursor="hand2",
                      command=lambda st=stype: self._start_scan(st)
                      ).pack(side="left", padx=(0, 12))

    def _stat_card(self, parent, value, label, color, col):
        card = tk.Frame(parent, bg=C["surface"], pady=20, padx=24)
        card.grid(row=0, column=col, sticky="ew", padx=(0, 12) if col < 2 else 0)
        val = tk.Label(card, text=value, font=("Segoe UI", 28, "bold"),
                        bg=C["surface"], fg=color)
        val.pack(anchor="w")
        tk.Label(card, text=label, font=FONT_SMALL,
                 bg=C["surface"], fg=C["text2"]).pack(anchor="w")
        return val

    # ── Scan page ─────────────────────────────────────────────────────────

    def _build_scan(self, parent):
        hdr = tk.Frame(parent, bg=C["bg"], pady=28, padx=40)
        hdr.pack(fill="x")
        tk.Label(hdr, text=t("nav_scan"), font=FONT_TITLE,
                 bg=C["bg"], fg=C["text"]).pack(anchor="w")

        # 4 uniform cards via grid
        btns = tk.Frame(parent, bg=C["bg"], padx=40)
        btns.pack(fill="x", pady=(0, 20))
        btns.columnconfigure((0, 1, 2, 3), weight=1, uniform="card")

        scan_opts = [
            ("scan_quick",  "quick",  C["accent"], "⚡"),
            ("scan_full",   "full",   C["danger"],  "🔬"),
            ("scan_folder", "folder", C["info"],    "📁"),
            ("scan_file",   "file",   C["text2"],   "📄"),
        ]
        for col_idx, (key, stype, color, icon) in enumerate(scan_opts):
            card = tk.Frame(btns, bg=C["surface"], padx=16, pady=18)
            card.grid(row=0, column=col_idx, sticky="nsew",
                      padx=(0, 10) if col_idx < 3 else 0)
            card.columnconfigure(0, weight=1)
            card.rowconfigure(2, weight=0, minsize=52)  # fixed desc height

            tk.Label(card, text=icon, font=("Segoe UI", 22),
                     bg=C["surface"], fg=color).grid(row=0, column=0, pady=(0, 4))
            tk.Label(card, text=t(key), font=FONT_H3,
                     bg=C["surface"], fg=C["text"]).grid(row=1, column=0)
            tk.Label(card, text=t(key + "_desc"), font=FONT_SMALL,
                     bg=C["surface"], fg=C["text2"],
                     wraplength=140, justify="center",
                     height=3).grid(row=2, column=0, pady=(4, 6), sticky="n")
            tk.Button(card, text=t("scan_start"),
                      font=FONT_BODY, bg=color, fg=C["white"],
                      activebackground=C["surface2"],
                      relief="flat", bd=0, padx=12, pady=5, cursor="hand2",
                      command=lambda st=stype: self._start_scan(st)
                      ).grid(row=3, column=0, pady=(4, 2))

        # Progress area
        prog = tk.Frame(parent, bg=C["surface"], padx=32, pady=18)
        prog.pack(fill="x", padx=40, pady=(0, 14))

        self._prog_label = tk.Label(prog, text="—", font=FONT_BODY,
                                     bg=C["surface"], fg=C["text"])
        self._prog_label.pack(anchor="w")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("HS.Horizontal.TProgressbar",
                         troughcolor=C["surface2"], background=C["accent"],
                         borderwidth=0, relief="flat")
        self._progressbar = ttk.Progressbar(prog, mode="determinate",
                                             style="HS.Horizontal.TProgressbar")
        self._progressbar.pack(fill="x", pady=6)

        self._prog_file = tk.Label(prog, text="", font=FONT_MONO,
                                    bg=C["surface"], fg=C["text3"])
        self._prog_file.pack(anchor="w")

        self._cancel_btn = tk.Button(
            prog, text=t("scan_cancel"),
            font=FONT_BODY, bg=C["danger"], fg=C["white"],
            disabledforeground=C["white"],
            activebackground=C["accent2"],
            relief="flat", bd=0, padx=14, pady=6,
            cursor="hand2", state="normal",
            command=self._cancel_scan
        )

        # "View Results" — appears after scan with threats
        self._view_results_btn = tk.Button(
            prog, text=t("scan_view_results"),
            font=FONT_BODY, bg=C["success"], fg=C["white"],
            activebackground=C["success"],
            relief="flat", bd=0, padx=14, pady=6, cursor="hand2",
            command=self._toggle_results_screen
        )
        # hidden until scan completes with threats

        # Log label + area
        self._log_label = tk.Label(parent, text=t("log_title"), font=FONT_H3,
                                    bg=C["bg"], fg=C["text"])
        self._log_label.pack(anchor="w", padx=40, pady=(6, 4))

        self._log_outer = tk.Frame(parent, bg=C["bg"], padx=40)
        self._log_outer.pack(fill="both", expand=True, pady=(0, 4))

        self._log_text = tk.Text(
            self._log_outer, bg=C["surface"], fg=C["text"],
            font=FONT_MONO, relief="flat", bd=0,
            state="disabled", wrap="word",
            selectbackground=C["surface2"]
        )
        _sb = ttk.Scrollbar(self._log_outer, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=_sb.set)
        _sb.pack(side="right", fill="y")
        self._log_text.pack(fill="both", expand=True)
        self._log_text.tag_configure("threat",     foreground=C["danger"])
        self._log_text.tag_configure("suspicious", foreground=C["warning"])
        self._log_text.tag_configure("clean",      foreground=C["success"])
        self._log_text.tag_configure("info",       foreground=C["text2"])

        # Results screen frame (populated dynamically)
        self._results_outer = tk.Frame(parent, bg=C["bg"])

    # ── History ───────────────────────────────────────────────────────────


    # ── Quarantine page ───────────────────────────────────────────────────

    def _build_quarantine(self, parent):
        hdr = tk.Frame(parent, bg=C["bg"], pady=32, padx=40)
        hdr.pack(fill="x")
        tk.Label(hdr, text=t("nav_quarantine"), font=FONT_TITLE,
                 bg=C["bg"], fg=C["text"]).pack(side="left")

        style = ttk.Style()
        style.configure("QT.Treeview",
            background=C["surface"], foreground=C["text"],
            fieldbackground=C["surface"], rowheight=32, font=FONT_BODY)
        style.configure("QT.Treeview.Heading",
            background=C["surface2"], foreground=C["text2"], font=FONT_H3)
        style.map("QT.Treeview", background=[("selected", C["surface2"])])

        cols = ("name", "original", "date")
        self._quar_tree = ttk.Treeview(parent, columns=cols,
                                        show="headings", style="QT.Treeview")
        col_cfg = [
            ("name",     t("quarantine_name"),     180, True),
            ("original", t("quarantine_original"), 320, True),
            ("date",     t("quarantine_date"),     140, False),
        ]
        for col, heading, width, stretch in col_cfg:
            self._quar_tree.heading(col, text=heading)
            self._quar_tree.column(col, width=width, minwidth=80,
                                   stretch=stretch, anchor="w")

        sb = ttk.Scrollbar(parent, command=self._quar_tree.yview)
        self._quar_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 40))
        self._quar_tree.pack(fill="both", expand=True, padx=40, pady=(0, 12))

        # Action buttons
        btn_row = tk.Frame(parent, bg=C["bg"], padx=40)
        btn_row.pack(fill="x", pady=(0, 24))

        tk.Button(btn_row, text=t("quarantine_restore"),
                  font=FONT_BODY, bg=C["success"], fg=C["white"],
                  relief="flat", bd=0, padx=16, pady=8, cursor="hand2",
                  command=self._quarantine_restore).pack(side="left", padx=(0, 10))

        tk.Button(btn_row, text=t("quarantine_delete"),
                  font=FONT_BODY, bg=C["danger"], fg=C["white"],
                  relief="flat", bd=0, padx=16, pady=8, cursor="hand2",
                  command=self._quarantine_delete).pack(side="left", padx=(0, 10))

        tk.Button(btn_row, text=t("quarantine_refresh"),
                  font=FONT_BODY, bg=C["surface"], fg=C["text"],
                  relief="flat", bd=0, padx=16, pady=8, cursor="hand2",
                  command=self._quarantine_refresh).pack(side="left")

        self._quarantine_refresh()

    def _quarantine_refresh(self):
        """Reload quarantine list from disk."""
        for item in self._quar_tree.get_children():
            self._quar_tree.delete(item)

        qdir = Path.home() / ".antivyre" / "quarantine"
        if not qdir.exists():
            self._quar_tree.insert("", "end", values=(
                t("quarantine_empty"), "", ""))
            return

        files = sorted(qdir.glob("*.quarantined"), reverse=True)
        if not files:
            self._quar_tree.insert("", "end", values=(
                t("quarantine_empty"), "", ""))
            return

        # Also check DB for original paths
        try:
            from db.storage import _get_connection
            conn = _get_connection()
            rows = {r["quarantine_path"]: dict(r)
                    for r in conn.execute(
                        "SELECT * FROM quarantine").fetchall()}
            conn.close()
        except Exception:
            rows = {}

        for f in files:
            db_row = rows.get(str(f), {})
            original = db_row.get("original_path", t("quarantine_unknown"))
            date_raw = db_row.get("quarantined_at", "")
            date     = date_raw[:16].replace("T", " ") if date_raw else "—"
            # Display name: strip timestamp prefix and .quarantined suffix
            display_name = f.stem
            if len(display_name) > 16 and display_name[8] == "_":
                display_name = display_name[16:]  # remove YYYYMMDD_HHMMSS_
            self._quar_tree.insert("", "end",
                values=(display_name, original, date),
                tags=(str(f),))  # store full path in tag

    def _get_selected_quarantine_path(self) -> str | None:
        sel = self._quar_tree.selection()
        if not sel:
            messagebox.showinfo("ANTIVYRE", t("quarantine_select_first"))
            return None
        tags = self._quar_tree.item(sel[0], "tags")
        if not tags or tags[0] == "":
            return None
        return tags[0]

    def _quarantine_restore(self):
        path = self._get_selected_quarantine_path()
        if not path:
            return
        try:
            from db.storage import _get_connection
            conn = _get_connection()
            row = conn.execute(
                "SELECT original_path FROM quarantine WHERE quarantine_path=?",
                (path,)).fetchone()
            conn.close()
            original = row["original_path"] if row else None
        except Exception:
            original = None

        if not original:
            messagebox.showerror("ANTIVYRE", t("quarantine_no_original"))
            return

        if not messagebox.askyesno(t("confirm_title"),
                                   t("quarantine_confirm_restore",
                                     file=Path(path).stem)):
            return
        try:
            import shutil
            shutil.move(path, original)
            try:
                from db.storage import _get_connection
                conn = _get_connection()
                conn.execute("DELETE FROM quarantine WHERE quarantine_path=?", (path,))
                conn.commit()
                conn.close()
            except Exception:
                pass
            self._quarantine_refresh()
        except Exception as e:
            messagebox.showerror("ANTIVYRE", t("error_permission", path=str(e)))

    def _quarantine_delete(self):
        path = self._get_selected_quarantine_path()
        if not path:
            return
        if not messagebox.askyesno(t("confirm_title"),
                                   t("quarantine_confirm_delete",
                                     file=Path(path).stem)):
            return
        try:
            os.remove(path)
            try:
                from db.storage import _get_connection
                conn = _get_connection()
                conn.execute("DELETE FROM quarantine WHERE quarantine_path=?", (path,))
                conn.commit()
                conn.close()
            except Exception:
                pass
            self._quarantine_refresh()
        except Exception as e:
            messagebox.showerror("ANTIVYRE", t("error_permission", path=str(e)))

    def _build_history(self, parent):
        hdr = tk.Frame(parent, bg=C["bg"], pady=32, padx=40)
        hdr.pack(fill="x")
        tk.Label(hdr, text=t("history_title"), font=FONT_TITLE,
                 bg=C["bg"], fg=C["text"]).pack(side="left")
        tk.Button(hdr, text=t("history_clear"),
                  font=FONT_BODY, bg=C["danger"], fg=C["white"],
                  relief="flat", bd=0, padx=14, pady=6, cursor="hand2",
                  command=self._clear_history).pack(side="right")

        style = ttk.Style()
        style.configure("HS.Treeview",
            background=C["surface"], foreground=C["text"],
            fieldbackground=C["surface"], rowheight=32, font=FONT_BODY)
        style.configure("HS.Treeview.Heading",
            background=C["surface2"], foreground=C["text2"], font=FONT_H3)
        style.map("HS.Treeview", background=[("selected", C["surface2"])])

        cols = ("date", "type", "files", "threats", "duration")
        self._hist_tree = ttk.Treeview(parent, columns=cols,
                                        show="headings", style="HS.Treeview")
        col_widths = {"date": 160, "type": 120, "files": 130,
                      "threats": 100, "duration": 100}
        headers = ["history_date", "history_type", "history_files",
                   "history_threats", "history_duration"]
        for col, hkey in zip(cols, headers):
            self._hist_tree.heading(col, text=t(hkey))
            self._hist_tree.column(col, anchor="center",
                                   width=col_widths[col], minwidth=80, stretch=True)

        sb2 = ttk.Scrollbar(parent, command=self._hist_tree.yview)
        self._hist_tree.configure(yscrollcommand=sb2.set)
        sb2.pack(side="right", fill="y", padx=(0, 40))
        self._hist_tree.pack(fill="both", expand=True, padx=40, pady=(0, 24))

    def _refresh_history(self):
        for item in self._hist_tree.get_children():
            self._hist_tree.delete(item)
        rows = get_history(100)
        if not rows:
            self._hist_tree.insert("", "end", values=(t("history_empty"), "", "", "", ""))
            return
        for row in rows:
            started = row.get("started_at", "")[:16].replace("T", " ")
            threats = row.get("threats", 0)
            self._hist_tree.insert("", "end", values=(
                started, row.get("scan_type", ""),
                row.get("files_count", 0), threats,
                f"{row.get('duration_s', 0):.1f}s",
            ), tags=("threat" if threats > 0 else "clean",))
        self._hist_tree.tag_configure("threat", foreground=C["danger"])
        self._hist_tree.tag_configure("clean",  foreground=C["success"])

    def _clear_history(self):
        if messagebox.askyesno(t("confirm_title"), t("confirm_clear_history")):
            clear_history()
            self._refresh_history()

    # ── Settings ──────────────────────────────────────────────────────────

    def _build_settings(self, parent):
        hdr = tk.Frame(parent, bg=C["bg"], pady=28, padx=40)
        hdr.pack(fill="x")
        tk.Label(hdr, text=t("settings_title"), font=FONT_TITLE,
                 bg=C["bg"], fg=C["text"]).pack(anchor="w")

        # Scrollable canvas so Updates section always reachable
        outer = tk.Frame(parent, bg=C["bg"])
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=C["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        content = tk.Frame(canvas, bg=C["bg"], padx=40)
        cw = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cw, width=e.width))
        content.bind("<Configure>",
                     lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # Language
        self._section(content, t("settings_language"), t("settings_language_desc"))
        self._lang_var = tk.StringVar(value=get_setting("language", "en"))
        lf = tk.Frame(content, bg=C["bg"])
        lf.pack(fill="x", pady=(0, 6))
        for lang in available_languages():
            tk.Radiobutton(
                lf, text=f"{lang['flag']} {lang['name']}",
                variable=self._lang_var, value=lang["code"],
                font=FONT_BODY, bg=C["bg"], fg=C["text"],
                activebackground=C["bg"], activeforeground=C["accent"],
                selectcolor=C["bg"], command=self._on_language_change
            ).pack(anchor="w", pady=2)
        tk.Label(content, text=t("settings_language_contribute"),
                 font=FONT_SMALL, bg=C["bg"], fg=C["text3"]).pack(anchor="w", pady=(0, 16))

        # Theme
        self._section(content, t("settings_theme"), "")
        self._theme_var = tk.StringVar(value=get_setting("theme", "dark"))
        for val, key in [("dark", "settings_theme_dark"), ("light", "settings_theme_light")]:
            tk.Radiobutton(
                content, text=t(key),
                variable=self._theme_var, value=val,
                font=FONT_BODY, bg=C["bg"], fg=C["text"],
                activebackground=C["bg"], activeforeground=C["accent"],
                selectcolor=C["bg"]
            ).pack(anchor="w", pady=2)

        # Startup
        tk.Frame(content, bg=C["border"], height=1).pack(fill="x", pady=(8, 0))
        self._section(content, t("settings_startup"), t("settings_startup_desc"))
        self._startup_var = tk.BooleanVar(value=self._get_startup_enabled())
        tk.Checkbutton(
            content, text=t("settings_startup"),
            variable=self._startup_var,
            font=FONT_BODY, bg=C["bg"], fg=C["text"],
            activebackground=C["bg"], activeforeground=C["accent"],
            selectcolor=C["bg"]
        ).pack(anchor="w", pady=(0, 8))

        tk.Button(content, text=t("settings_save"),
                  font=FONT_H3, bg=C["accent"], fg=C["white"],
                  relief="flat", bd=0, padx=24, pady=10, cursor="hand2",
                  command=self._save_settings).pack(anchor="w", pady=20)

        self._settings_msg = tk.Label(content, text="",
                                       font=FONT_BODY, bg=C["bg"], fg=C["success"])
        self._settings_msg.pack(anchor="w")

        # Updates section
        tk.Frame(content, bg=C["border"], height=1).pack(fill="x", pady=(20, 0))
        self._section(content, t("settings_updates_title"), t("settings_updates_desc"))

        btn_row = tk.Frame(content, bg=C["bg"])
        btn_row.pack(fill="x", pady=(0, 10))
        tk.Button(btn_row, text=t("update_btn_all"),
                  font=FONT_BODY, bg=C["accent"], fg=C["white"],
                  relief="flat", bd=0, padx=18, pady=8, cursor="hand2",
                  command=self._manual_update_all).pack(side="left", padx=(0, 10))
        tk.Button(btn_row, text=t("update_btn_check_app"),
                  font=FONT_BODY, bg=C["surface"], fg=C["text"],
                  relief="flat", bd=0, padx=18, pady=8, cursor="hand2",
                  command=self._manual_check_app).pack(side="left")

        self._update_log = tk.Text(content, height=5,
                                   bg=C["surface"], fg=C["text2"],
                                   font=FONT_MONO, relief="flat", bd=0,
                                   state="disabled", wrap="word")
        self._update_log.pack(fill="x", pady=(4, 24))

    def _section(self, parent, title, desc):
        tk.Label(parent, text=title, font=FONT_H2,
                 bg=C["bg"], fg=C["text"]).pack(anchor="w", pady=(16, 2))
        if desc:
            tk.Label(parent, text=desc, font=FONT_SMALL,
                     bg=C["bg"], fg=C["text2"]).pack(anchor="w", pady=(0, 8))

    # ── About ─────────────────────────────────────────────────────────────

    def _build_about(self, parent):
        outer = tk.Frame(parent, bg=C["bg"], padx=60, pady=32)
        outer.pack(fill="both", expand=True)

        # Logo
        try:
            from PIL import Image, ImageTk
            lp = self._assets_dir / "logo.png"
            if lp.exists():
                pil = Image.open(str(lp)).resize((72, 72), Image.LANCZOS)
                self._about_logo = ImageTk.PhotoImage(pil)
                tk.Label(outer, image=self._about_logo, bg=C["bg"]).pack()
            else:
                raise FileNotFoundError
        except Exception:
            tk.Label(outer, text="⚡", font=("Segoe UI", 44),
                     bg=C["bg"], fg=C["accent"]).pack()

        tk.Label(outer, text=t("app_title"), font=("Segoe UI", 26, "bold"),
                 bg=C["bg"], fg=C["text"]).pack()

        # "by FreddyDeveloper" clickable
        by = tk.Label(outer, text=t("app_by_author"),
                      font=("Segoe UI", 10),
                      bg=C["bg"], fg=C["accent"], cursor="hand2")
        by.pack(pady=(2, 0))
        by.bind("<Button-1>", lambda e: webbrowser.open(WEBSITE_URL))
        by.bind("<Enter>",    lambda e: by.configure(fg=C["white"]))
        by.bind("<Leave>",    lambda e: by.configure(fg=C["accent"]))

        tk.Label(outer, text=t("about_version", version=VERSION),
                 font=FONT_BODY, bg=C["bg"], fg=C["text2"]).pack(pady=(4, 2))
        tk.Label(outer, text=t("about_license"),
                 font=FONT_SMALL, bg=C["bg"], fg=C["success"]).pack()

        tk.Frame(outer, bg=C["border"], height=1).pack(fill="x", pady=20)

        # Magika card with version
        _mv = _get_magika_version()
        mc = tk.Frame(outer, bg=C["surface"], pady=14, padx=20)
        mc.pack(fill="x", pady=(0, 14))
        ver_str = f"v{_mv}" if _mv != "?" else ""
        tk.Label(mc, text=f"File detection powered by Google Magika  {ver_str}".strip(), font=FONT_H3,
                 bg=C["surface"], fg=C["text"]).pack(anchor="w")
        tk.Label(mc, text=t("about_magika_accuracy"), font=FONT_SMALL,
                 bg=C["surface"], fg=C["info"]).pack(anchor="w")

        # Donate card
        dc = tk.Frame(outer, bg=C["surface2"], pady=18, padx=20)
        dc.pack(fill="x", pady=(0, 14))
        tk.Label(dc, text=t("about_donate_title"), font=FONT_H2,
                 bg=C["surface2"], fg=C["accent"]).pack(anchor="w")
        tk.Label(dc, text=t("about_donate_desc"), font=FONT_BODY,
                 bg=C["surface2"], fg=C["text"],
                 wraplength=700, justify="left").pack(anchor="w", pady=8)
        tk.Button(dc, text=f"💛  {t('about_donate_button')}",
                  font=FONT_H3, bg=C["warning"], fg=C["bg"],
                  relief="flat", bd=0, padx=20, pady=10, cursor="hand2",
                  command=lambda: webbrowser.open(DONATE_URL)).pack(anchor="w")

        # Links
        links = tk.Frame(outer, bg=C["bg"])
        links.pack(fill="x", pady=(0, 8))
        for label, url in [(t("about_github"), GITHUB_URL),
                           (t("about_antivyre"), ANTIVYRE_URL)]:
            tk.Button(links, text=label,
                      font=FONT_BODY, bg=C["surface"], fg=C["info"],
                      relief="flat", bd=0, padx=16, pady=8, cursor="hand2",
                      command=lambda u=url: webbrowser.open(u)
                      ).pack(side="left", padx=(0, 8))

        # Project history (replaces "Special thanks")
        tk.Label(outer, text=t("about_history"),
                 font=FONT_SMALL, bg=C["bg"], fg=C["text3"]).pack(pady=(14, 0))

    # ── Scan logic ────────────────────────────────────────────────────────

    def _start_scan(self, scan_type: str):
        if self._scan_running:
            return
        target = None
        if scan_type == "folder":
            target = filedialog.askdirectory(title=t("scan_folder"))
            if not target:
                return
        elif scan_type == "file":
            target = filedialog.askopenfilename(title=t("scan_file"))
            if not target:
                return

        self._scan_running  = True
        self._files_scanned = 0
        self._threats_found = 0
        self._scan_start    = time.time()
        self._resolved_paths = set()
        self._resolved_paths_labels = {}

        # Reset UI state
        self._results_outer.pack_forget()
        self._log_label.pack(anchor="w", padx=40, pady=(6, 4))
        self._log_outer.pack(fill="both", expand=True, pady=(0, 4))
        self._view_results_btn.pack_forget()
        self._cancel_btn.pack(anchor="w", pady=(8, 0))
        self._progressbar["value"] = 0
        self._clear_log()
        self._log(f"[{datetime.now().strftime('%H:%M:%S')}] Starting {scan_type} scan…", "info")

        self._session_id = start_session(scan_type)
        self._update_status("scanning")
        if self._tray:
            self._tray.update_status("scanning")
        self._show_page("scan")

        def run():
            results = []
            try:
                def progress(current, total, path):
                    self._files_scanned = current
                    pct = (current / total * 100) if total > 0 else 0
                    trunc = ("…" + path[-60:]) if len(path) > 63 else path
                    self.root.after(0, self._update_progress, current, total, pct, trunc)

                if scan_type == "quick":
                    results = self.scanner.scan_quick(progress)
                elif scan_type == "full":
                    results = self.scanner.scan_full(progress)
                elif scan_type == "file":
                    r = self.scanner.scan_file(target)
                    self._files_scanned = 1
                    if r.is_threat or r.is_suspicious:
                        results = [r]
                else:
                    results = self.scanner.scan_folder(target, progress)
            except Exception as e:
                self.root.after(0, self._log, f"Error: {e}", "threat")
            finally:
                self.root.after(0, self._on_scan_complete, results)

        self._scan_thread = threading.Thread(target=run, daemon=True)
        self._scan_thread.start()

    def _cancel_scan(self):
        self.scanner.stop()
        self._log(t("scan_paused"), "info")

    def _update_progress(self, current, total, pct, path_trunc):
        self._progressbar["maximum"] = 100
        self._progressbar["value"]   = pct
        self._prog_label.configure(text=t("scan_progress", current=current, total=total))
        self._prog_file.configure(text=path_trunc)

    def _on_scan_complete(self, results: list):
        self._scan_running  = False
        self._last_results  = results
        existing_paths = {r.file_path for r in self._all_results}
        self._all_results.extend(r for r in results if r.file_path not in existing_paths)
        duration = time.time() - self._scan_start
        self._threats_found = len(results)

        self._cancel_btn.pack_forget()
        if results:
            self._view_results_btn.pack(anchor="w", pady=(8, 0))

        self._prog_label.configure(text=t("scan_complete"))
        self._prog_file.configure(text="")
        self._progressbar["value"] = 100

        if self._session_id:
            finish_session(self._session_id, self._files_scanned,
                           self._threats_found, duration)

        for r in results:
            if self._session_id:
                save_detection(self._session_id, r)

        if not results:
            self._log(t("scan_no_threats"), "clean")
        self._log(t("scan_complete_msg",
                    threats=self._threats_found,
                    files=self._files_scanned,
                    duration=f"{duration:.1f}"), "info")

        self._stat_threats.configure(text=str(self._threats_found))
        self._stat_files.configure(text=str(self._files_scanned))
        self._stat_time.configure(text=f"{duration:.1f}s")
        self._last_scan_label.configure(
            text=t("dashboard_last_scan",
                   time=datetime.now().strftime("%Y-%m-%d %H:%M")))

        if results:
            self._update_status("threat")
            if self._tray:
                self._tray.update_status("threat")
                self._tray.notify(t("tray_threat_title"),
                                  t("tray_threat_msg", count=self._threats_found))
            self._show_results_screen(self._all_results, duration)
        else:
            self._update_status("protected")
            if self._tray:
                self._tray.update_status("protected")

    # ── Results screen ────────────────────────────────────────────────────

    def _toggle_results_screen(self):
        if self._results_outer.winfo_ismapped():
            self._results_outer.pack_forget()
            self._log_label.pack(anchor="w", padx=40, pady=(6, 4))
            self._log_outer.pack(fill="both", expand=True, pady=(0, 4))
            self._view_results_btn.configure(text=t("scan_view_results"))
        else:
            self._show_results_screen(self._all_results,
                                      time.time() - self._scan_start)

    def _show_results_screen(self, results: list, duration: float):
        self._log_label.pack_forget()
        self._log_outer.pack_forget()
        self._view_results_btn.configure(text=t("results_back"))

        for w in self._results_outer.winfo_children():
            w.destroy()

        # Header
        hdr = tk.Frame(self._results_outer, bg=C["surface2"], padx=32, pady=12)
        hdr.pack(fill="x")
        threat_c = sum(1 for r in results if r.is_threat)
        susp_c   = sum(1 for r in results if r.is_suspicious)
        tk.Label(hdr,
                 text=t("results_summary",
                         threats=threat_c, suspicious=susp_c,
                         files=self._files_scanned, duration=f"{duration:.1f}"),
                 font=FONT_H3, bg=C["surface2"], fg=C["text"]).pack(side="left")

        # Bulk action bar
        active_results = [r for r in results if r.file_path not in self._resolved_paths]
        if active_results:
            bulk = tk.Frame(self._results_outer, bg=C["surface"], padx=32, pady=10)
            bulk.pack(fill="x")
            tk.Label(bulk, text="Apply to all unresolved:",
                     font=FONT_SMALL, bg=C["surface"], fg=C["text2"]).pack(side="left", padx=(0, 14))

            def _bulk_quarantine():
                if messagebox.askyesno(t("confirm_title"),
                    f"Quarantine all {len(active_results)} unresolved threats?"):
                    for r in list(active_results):
                        dest = quarantine_file(r.file_path, r.threat_level.name)
                        if dest:
                            label = t("result_quarantine") + " ✓"
                            self._resolved_paths.add(r.file_path)
                            self._resolved_paths_labels[r.file_path] = label
                    self._show_results_screen(self._all_results, duration)
                    self._check_threats_resolved()

            def _bulk_delete():
                if messagebox.askyesno(t("confirm_title"),
                    f"Permanently delete all {len(active_results)} unresolved threats?"):
                    for r in list(active_results):
                        try:
                            os.remove(r.file_path)
                            label = t("result_delete") + " ✓"
                            self._resolved_paths.add(r.file_path)
                            self._resolved_paths_labels[r.file_path] = label
                        except OSError:
                            pass
                    self._show_results_screen(self._all_results, duration)
                    self._check_threats_resolved()

            def _bulk_ignore():
                if messagebox.askyesno(t("confirm_title"),
                    f"Ignore all {len(active_results)} unresolved threats?"):
                    for r in list(active_results):
                        label = t("result_ignore") + " ✓"
                        self._resolved_paths.add(r.file_path)
                        self._resolved_paths_labels[r.file_path] = label
                    self._show_results_screen(self._all_results, duration)
                    self._check_threats_resolved()

            tk.Button(bulk, text="⚠ Quarantine All",
                      font=FONT_SMALL, bg=C["warning"], fg=C["bg"],
                      relief="flat", bd=0, padx=14, pady=5, cursor="hand2",
                      command=_bulk_quarantine).pack(side="left", padx=(0, 6))
            tk.Button(bulk, text="✕ Delete All",
                      font=FONT_SMALL, bg=C["danger"], fg=C["white"],
                      relief="flat", bd=0, padx=14, pady=5, cursor="hand2",
                      command=_bulk_delete).pack(side="left", padx=(0, 6))
            tk.Button(bulk, text="— Ignore All",
                      font=FONT_SMALL, bg=C["surface2"], fg=C["text2"],
                      relief="flat", bd=0, padx=14, pady=5, cursor="hand2",
                      command=_bulk_ignore).pack(side="left")

        # Scrollable cards
        wrap = tk.Frame(self._results_outer, bg=C["bg"])
        wrap.pack(fill="both", expand=True)
        canvas = tk.Canvas(wrap, bg=C["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=C["bg"])
        cw = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cw, width=e.width))
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        self._results_frame = inner
        for idx, r in enumerate(results):
            self._build_result_card(inner, r, idx,
                                    resolved=r.file_path in self._resolved_paths)

        self._results_outer.pack(fill="both", expand=True)

    def _build_result_card(self, parent, r, idx: int, resolved: bool = False):
        bg = C["surface"] if idx % 2 == 0 else C["surface2"]
        card = tk.Frame(parent, bg=bg, pady=12, padx=20)
        card.pack(fill="x", pady=(0, 2))

        badge_color = C["danger"] if r.is_threat else C["warning"]
        badge_text  = t("result_threat") if r.is_threat else t("result_suspicious")

        tk.Label(card, text=badge_text, font=("Segoe UI", 9, "bold"),
                 bg=badge_color, fg=C["white"],
                 padx=8, pady=2).grid(row=0, column=0, sticky="nw",
                                       rowspan=3, padx=(0, 14))
        card.columnconfigure(1, weight=1)

        fp = r.file_path
        display = fp if len(fp) <= 78 else "…" + fp[-75:]
        tk.Label(card, text=display, font=FONT_MONO,
                 bg=bg, fg=C["text"], anchor="w").grid(row=0, column=1, sticky="ew")

        detail = (f"  {t('result_real_type')}: {r.real_type}"
                  f"   {t('result_confidence')}: {r.confidence:.0%}"
                  f"   {t('result_declared_type')}: {r.declared_type or '—'}")
        tk.Label(card, text=detail, font=FONT_SMALL,
                 bg=bg, fg=C["text2"], anchor="w").grid(row=1, column=1, sticky="ew")

        for reason_raw in r.reasons:
            tk.Label(card, text=f"  ↳ {self._fmt_reason(reason_raw)}",
                     font=FONT_SMALL, bg=bg, fg=badge_color,
                     anchor="w").grid(row=2, column=1, sticky="ew")

        acts = tk.Frame(card, bg=bg)
        acts.grid(row=0, column=2, rowspan=3, sticky="ne", padx=(14, 0))

        if resolved:
            action_label = self._resolved_paths_labels.get(r.file_path, t("result_ignore") + " ✓")
            resolved_color = (C["warning"] if "uarantine" in action_label
                              else C["danger"] if "elete" in action_label
                              else C["text3"])
            lbl = tk.Label(acts, text=action_label,
                           font=("Segoe UI", 9, "bold"),
                           bg=resolved_color, fg=C["white"] if "uarantine" in action_label or "elete" in action_label else C["text"],
                           padx=10, pady=4)
            lbl.pack(anchor="e", pady=4)
        else:
            for btn_text, btn_bg, btn_fg, btn_cmd in [
                ("⚠  " + t("result_quarantine"), C["warning"], C["bg"],
                 lambda p=r.file_path, lv=r.threat_level.name, c=card:
                     self._do_quarantine(p, lv, c)),
                ("✕  " + t("result_delete"), C["danger"], C["white"],
                 lambda p=r.file_path, c=card: self._do_delete(p, c)),
                ("—  " + t("result_ignore"), C["surface2"], C["text2"],
                 lambda p=r.file_path, c=card: self._do_ignore(p, c)),
            ]:
                b = tk.Button(acts, text=btn_text,
                              font=("Segoe UI", 9, "bold"),
                              bg=btn_bg, fg=btn_fg,
                              relief="flat", bd=0,
                              padx=12, pady=5,
                              cursor="hand2",
                              activebackground=btn_bg,
                              activeforeground=btn_fg,
                              command=btn_cmd)
                b.pack(fill="x", pady=(0, 3))

    @staticmethod
    def _fmt_reason(raw: str) -> str:
        if raw == "result_malicious_hash":
            return t("result_malicious_hash")
        if raw == "result_office_macro":
            return t("result_office_macro")
        if raw.startswith("result_spoofed|"):
            parts = dict(p.split("=", 1) for p in raw.split("|")[1:])
            return t("result_spoofed",
                     declared=parts.get("declared", "?"),
                     real=parts.get("real", "?"))
        return raw

    def _do_quarantine(self, path, level, card):
        if messagebox.askyesno(t("confirm_title"),
                               t("confirm_quarantine", file=Path(path).name)):
            dest = quarantine_file(path, level)
            if dest:
                label = t("result_quarantine") + " ✓"
                self._resolved_paths.add(path)
                self._resolved_paths_labels[path] = label
                self._dismiss_card(card, label, C["warning"])
                self._check_threats_resolved()
            else:
                messagebox.showerror("ANTIVYRE", t("error_permission", path=path))

    def _do_delete(self, path, card):
        if messagebox.askyesno(t("confirm_title"),
                               t("confirm_delete", file=Path(path).name)):
            try:
                os.remove(path)
                label = t("result_delete") + " ✓"
                self._resolved_paths.add(path)
                self._resolved_paths_labels[path] = label
                self._dismiss_card(card, label, C["danger"])
                self._check_threats_resolved()
            except OSError:
                messagebox.showerror("ANTIVYRE", t("error_permission", path=path))

    def _do_ignore(self, path, card):
        label = t("result_ignore") + " ✓"
        self._resolved_paths.add(path)
        self._resolved_paths_labels[path] = label
        self._dismiss_card(card, label, C["text3"])
        self._check_threats_resolved()

    @staticmethod
    def _dismiss_card(card, label, color):
        for w in card.winfo_children():
            w.destroy()
        tk.Label(card, text=f"✓  {label}", font=FONT_BODY,
                 bg=card["bg"], fg=color).pack(anchor="w")

    def _check_threats_resolved(self):
        if not hasattr(self, "_results_frame"):
            return
        active = 0
        for card in self._results_frame.winfo_children():
            for child in card.winfo_children():
                if isinstance(child, tk.Button):
                    active += 1
                    break
        if active == 0:
            self._update_status("protected")
            if self._tray:
                self._tray.update_status("protected")

    # ── Update section ────────────────────────────────────────────────────

    def _manual_update_all(self):
        self._upd_log_clear()
        if self._updater:
            self._updater.run_now()
        else:
            self._upd_log_append("Auto-updater not available.")

    def _manual_check_app(self):
        self._upd_log_clear()
        self._upd_log_append(t("update_checking"))
        def check():
            try:
                from core.updater import check_for_app_update
                info = check_for_app_update(VERSION)
                if info:
                    self.root.after(0, self._on_app_update_available, info)
                else:
                    self.root.after(0, self._upd_log_append, t("update_app_uptodate"))
            except Exception:
                self.root.after(0, self._upd_log_append, "Update check unavailable.")
        threading.Thread(target=check, daemon=True).start()

    def _upd_log_append(self, msg: str):
        try:
            self._update_log.configure(state="normal")
            self._update_log.insert("end", msg + "\n")
            self._update_log.see("end")
            self._update_log.configure(state="disabled")
        except Exception:
            pass

    def _upd_log_clear(self):
        try:
            self._update_log.configure(state="normal")
            self._update_log.delete("1.0", "end")
            self._update_log.configure(state="disabled")
        except Exception:
            pass

    # ── Updater callbacks ─────────────────────────────────────────────────

    def _on_update_progress(self, msg: str):
        try:
            self.root.after(0, self._upd_log_append, msg)
        except Exception:
            pass

    def _on_magika_updated(self):
        try:
            self.root.after(0, messagebox.showinfo,
                            "ANTIVYRE", t("update_magika_restart"))
        except Exception:
            pass

    def _on_app_update_available(self, info: dict):
        def show():
            ver  = info.get("latest_version", "")
            url  = info.get("download_url",
                            "https://github.com/FreddyDeveloper/antivyre")
            msg  = t("update_app_available", version=ver)
            notes = info.get("release_notes", "")
            if notes:
                msg += f"\n\n{notes}"
            if messagebox.askyesno("ANTIVYRE — " + t("update_title"), msg):
                webbrowser.open(url)
        try:
            self.root.after(0, show)
        except Exception:
            pass

    # ── Real-time callbacks ───────────────────────────────────────────────

    def _on_realtime_detection(self, file_path: str):
        try:
            result = self.scanner.scan_file(file_path)
            if result.is_threat or result.is_suspicious:
                self.root.after(0, self._handle_realtime_threat, result)
        except Exception:
            pass

    def _handle_realtime_threat(self, result):
        tag   = "threat" if result.is_threat else "suspicious"
        level = t("result_threat") if result.is_threat else t("result_suspicious")
        self._log(f"[{t('realtime_label')}] [{level}] {result.file_path}", tag)
        self._threats_found += 1
        self._stat_threats.configure(text=str(self._threats_found))
        existing_paths = {r.file_path for r in self._all_results}
        if result.file_path not in existing_paths:
            self._all_results.append(result)
        if self._results_outer.winfo_ismapped():
            self._show_results_screen(self._all_results,
                                      time.time() - self._scan_start)
        else:
            self._view_results_btn.pack(anchor="w", pady=(8, 0))
        self._update_status("threat")
        if self._tray:
            self._tray.update_status("threat")
            self._tray.notify(t("tray_threat_title"),
                              t("tray_threat_msg", count=1))

    def _update_rt_badge(self, active: bool):
        pass  # Badge is fixed as "AI-powered Antivirus"

    # ── Tray / window lifecycle ───────────────────────────────────────────

    def _show_window(self):
        self.root.after(0, lambda: (
            self.root.deiconify(), self.root.lift(), self.root.focus_force()))

    def _quit_app(self):
        if self._scan_running:
            self.scanner.stop()
        if self._realtime:
            self._realtime.stop()
        if self._tray:
            self._tray.stop()
        if self._updater:
            self._updater.stop()
        self.root.after(0, self.root.destroy)

    def _restart_app(self):
        if self._tray:
            self._tray.stop()
        if self._updater:
            self._updater.stop()
        self.root.destroy()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _on_close(self):
        """X → minimize to tray. Process stays alive in background."""
        if PYSTRAY_AVAILABLE and self._tray:
            self.root.withdraw()
            self._tray.notify("ANTIVYRE", t("tray_minimized_msg"))
        else:
            if self._scan_running:
                if not messagebox.askyesno("ANTIVYRE",
                                           t("confirm_exit_scanning")):
                    return
            self._quit_app()

    # ── Language / settings ───────────────────────────────────────────────

    def _on_language_change(self):
        set_setting("language", self._lang_var.get())
        if messagebox.askyesno("ANTIVYRE",
                               t("settings_restart_required"), icon="question"):
            self._restart_app()

    def _get_startup_enabled(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, "ANTIVYRE")
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    def _set_startup_enabled(self, enabled: bool):
        if sys.platform != "win32":
            return
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_SET_VALUE)
            if enabled:
                exe_path = sys.executable if not getattr(sys, "frozen", False)                            else sys.executable
                winreg.SetValueEx(key, "ANTIVYRE", 0, winreg.REG_SZ,
                                  f'"{exe_path}" --startup')
            else:
                try:
                    winreg.DeleteValue(key, "ANTIVYRE")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception:
            pass

    def _save_settings(self):
        prev_lang  = get_setting("language", "en")
        prev_theme = get_setting("theme", "dark")
        new_lang   = self._lang_var.get()
        new_theme  = self._theme_var.get()
        set_setting("language", new_lang)
        set_setting("theme",    new_theme)
        self._set_startup_enabled(self._startup_var.get())
        if new_lang != prev_lang or new_theme != prev_theme:
            if messagebox.askyesno("ANTIVYRE",
                                   t("settings_restart_required"), icon="question"):
                self._restart_app()
        else:
            self._settings_msg.configure(text=t("settings_saved"))
            self.root.after(2500, lambda: self._settings_msg.configure(text=""))

    # ── Status / log helpers ──────────────────────────────────────────────

    def _update_status(self, state: str):
        states = {
            "protected": (C["success"], "🛡️", "dashboard_status_protected"),
            "scanning":  (C["info"],    "🔍", "dashboard_status_scanning"),
            "threat":    (C["danger"],  "⚠️",  "dashboard_status_threat"),
        }
        color, icon, key = states.get(state, states["protected"])
        self._status_icon.configure(text=icon, fg=color)
        self._status_label.configure(text=t(key), fg=color)

    def _log(self, text: str, tag: str = "info"):
        self._log_text.configure(state="normal")
        self._log_text.insert("end", text + "\n", tag)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _clear_log(self):
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    def run(self):
        # Load hashes in background after window is shown — prevents startup freeze
        def _on_hashes_loaded():
            try:
                self._update_dashboard_stats()
            except Exception:
                pass
        self.root.after(100, lambda: self.scanner.load_hashes_async(_on_hashes_loaded))
        if self._silent_start:
            self.root.after(50, self.root.withdraw)
        self.root.mainloop()
