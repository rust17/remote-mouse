import pystray
from PIL import Image
from loguru import logger
import threading
import time

from server.config import (
    APP_NAME,
    get_asset_path,
)
from server.core.metrics import metrics


def create_image():
    icon_path = get_asset_path("tray_icon.png")
    return Image.open(icon_path)


class TrayIcon:
    def __init__(
        self,
        port: int,
        ip_address: str,
        on_exit_callback,
        restart_callback,
        on_log_toggle_callback,
        initial_logging_state: bool = False,
    ):
        self.port = port
        self.ip_address = ip_address
        self.on_exit_callback = on_exit_callback
        self.restart_callback = restart_callback
        self.on_log_toggle_callback = on_log_toggle_callback
        self.icon = None
        self.logging_enabled = initial_logging_state
        self.show_rate = False
        self._monitor_thread = None
        self._stop_event = threading.Event()

    def _on_restart(self, icon, item):
        logger.info("Restart requested from tray icon...")
        if self.restart_callback:
            self.restart_callback()

    def _on_quit(self, icon, item):
        logger.info("Stopping from tray icon...")
        self._stop_event.set()
        if self.on_exit_callback:
            self.on_exit_callback()
        icon.stop()

    def _on_toggle_logging(self, icon, item):
        self.logging_enabled = not self.logging_enabled
        logger.info(f"Tray toggled logging to {self.logging_enabled}")

        if self.on_log_toggle_callback:
            self.on_log_toggle_callback(self.logging_enabled)

    def _on_toggle_rate(self, icon, item):
        self.show_rate = not self.show_rate
        logger.info(f"Tray toggled rate display to {self.show_rate}")

    def run(self):
        def get_log_label(item):
            return "Disable Logs" if self.logging_enabled else "Enable Logs"

        def get_rate_toggle_label(item):
            return "Hide Rate" if self.show_rate else "Show Rate"

        def get_current_rate_label(item):
            if not self.show_rate:
                return "Rate: Disabled"
            pps, bps = metrics.get_current()
            return f"Rate: {pps} pps, {self._format_bps(bps)}"

        menu = pystray.Menu(
            pystray.MenuItem(
                f"Address: http://{self.ip_address}:{self.port}", lambda: None, enabled=False
            ),
            pystray.MenuItem(get_current_rate_label, lambda: None, enabled=False),
            pystray.MenuItem(get_rate_toggle_label, self._on_toggle_rate),
            pystray.MenuItem(get_log_label, self._on_toggle_logging),
            pystray.MenuItem("Restart", self._on_restart),
            pystray.MenuItem("Exit", self._on_quit),
        )
        self.icon = pystray.Icon(APP_NAME, create_image(), APP_NAME, menu)

        # Start background monitor to update icon title
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        logger.info("Application minimalized to tray.")
        self.icon.run()

    def _monitor_loop(self):
        while not self._stop_event.is_set():
            if self.show_rate and self.icon:
                self.icon.update_menu()
            time.sleep(1)

    def _format_bps(self, bps):
        if bps < 1024:
            return f"{bps} B/s"
        elif bps < 1024 * 1024:
            return f"{bps / 1024:.1f} KB/s"
        else:
            return f"{bps / 1024 / 1024:.1f} MB/s"

    def stop(self):
        self._stop_event.set()
        if self.icon:
            self.icon.stop()
