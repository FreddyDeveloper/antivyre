"""
ANTIVYRE — System Tray Module
Provides a system tray icon with right-click menu.
Menu items are fully translated via the i18n system.
"""

import math
import threading
from pathlib import Path
from typing import Callable, Optional

try:
    import pystray
    from PIL import Image as PILImage, ImageDraw as PILDraw
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False


class SystemTray:
    """
    Manages the ANTIVYRE system tray icon.
    Must be started after the main window is built.
    """

    def __init__(
        self,
        on_open:       Callable,
        on_quick_scan: Callable,
        on_exit:       Callable,
        t_func:        Callable,
        assets_dir:    Path,
    ):
        self._on_open       = on_open
        self._on_quick_scan = on_quick_scan
        self._on_exit       = on_exit
        self._t             = t_func
        self._assets_dir    = assets_dir
        self._icon: Optional["pystray.Icon"] = None
        self._thread: Optional[threading.Thread] = None
        self._status        = "protected"
        self._scan_angle    = 0
        self._scan_timer: Optional[threading.Timer] = None

    # ── Icon image ───────────────────────────────────────────────────────

    def _load_base(self) -> "PILImage.Image":
        tray_path = self._assets_dir / "icon_tray.png"
        if tray_path.exists():
            return PILImage.open(str(tray_path)).convert("RGBA").resize((64, 64))
        img = PILImage.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = PILDraw.Draw(img)
        draw.polygon([(32,4),(58,14),(58,38),(32,60),(6,38),(6,14)], fill="#e67e22")
        draw.polygon([(36,10),(24,34),(32,34),(28,54),(40,30),(32,30)], fill="white")
        return img

    def _load_image(self, status: str = "protected") -> "PILImage.Image":
        img = self._load_base()
        if status == "threat":
            import numpy as np
            arr = np.array(img, dtype=float)
            arr[..., 0] = np.clip(arr[..., 0] * 1.8, 0, 255)
            arr[..., 1] = np.clip(arr[..., 1] * 0.3, 0, 255)
            arr[..., 2] = np.clip(arr[..., 2] * 0.3, 0, 255)
            img = PILImage.fromarray(arr.astype("uint8"), "RGBA")
        return img

    def _build_scan_frame(self, angle: float) -> "PILImage.Image":
        base = self._load_base().copy()
        overlay = PILImage.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = PILDraw.Draw(overlay)

        cx, cy = 34, 34
        r = 11
        lw = 3
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     outline=(255, 255, 255, 230), width=lw)

        handle_len = 9
        hx = cx + int((r + 2) * math.cos(math.radians(angle)))
        hy = cy + int((r + 2) * math.sin(math.radians(angle)))
        ex = hx + int(handle_len * math.cos(math.radians(angle)))
        ey = hy + int(handle_len * math.sin(math.radians(angle)))
        draw.line([hx, hy, ex, ey], fill=(255, 255, 255, 230), width=lw)

        arc_start = angle - 90
        arc_end   = angle + 60
        draw.arc([cx - r, cy - r, cx + r, cy + r],
                 start=arc_start, end=arc_end,
                 fill=(230, 180, 0, 255), width=lw + 1)

        base = PILImage.alpha_composite(base, overlay)
        return base

    # ── Menu — uses t() for all labels ───────────────────────────────────

    def _build_menu(self) -> "pystray.Menu":
        t = self._t
        return pystray.Menu(
            pystray.MenuItem(
                t("tray_open"),
                self._action_open,
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                t("tray_quick_scan"),
                self._action_quick_scan,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                t("tray_exit"),
                self._action_exit,
            ),
        )

    # ── Actions ──────────────────────────────────────────────────────────

    def _action_open(self, icon, item):
        self._on_open()

    def _action_quick_scan(self, icon, item):
        self._on_quick_scan()

    def _action_exit(self, icon, item):
        self.stop()
        self._on_exit()

    # ── Public API ───────────────────────────────────────────────────────

    def start(self):
        if not PYSTRAY_AVAILABLE:
            return
        if self._thread and self._thread.is_alive():
            return

        def run():
            img = self._load_image("protected")
            self._icon = pystray.Icon(
                name="ANTIVYRE",
                icon=img,
                title="ANTIVYRE — " + self._t("dashboard_status_protected"),
                menu=self._build_menu(),
            )
            self._icon.run()

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def _start_scan_animation(self):
        if not self._icon:
            return
        self._scan_angle = (self._scan_angle + 20) % 360
        try:
            self._icon.icon = self._build_scan_frame(self._scan_angle)
        except Exception:
            pass
        if self._status == "scanning":
            self._scan_timer = threading.Timer(0.08, self._start_scan_animation)
            self._scan_timer.daemon = True
            self._scan_timer.start()

    def _stop_scan_animation(self):
        if self._scan_timer:
            self._scan_timer.cancel()
            self._scan_timer = None

    def update_status(self, status: str):
        prev = self._status
        self._status = status
        tooltips = {
            "protected": "ANTIVYRE — " + self._t("dashboard_status_protected"),
            "threat":    "ANTIVYRE — " + self._t("dashboard_status_threat"),
            "scanning":  "ANTIVYRE — " + self._t("dashboard_status_scanning"),
        }
        if not self._icon:
            return
        try:
            self._icon.title = tooltips.get(status, "ANTIVYRE")
            if status == "scanning":
                if prev != "scanning":
                    self._scan_angle = 0
                    self._start_scan_animation()
            else:
                self._stop_scan_animation()
                self._icon.icon = self._load_image(status)
        except Exception:
            pass

    def notify(self, title: str, message: str):
        if not self._icon:
            return
        try:
            display_title = f"ANTIVYRE — {title}" if not title.startswith("ANTIVYRE") else title
            self._icon.notify(message, display_title)
        except Exception:
            pass
