import os
import pystray
from pathlib import Path
from PIL import Image, ImageDraw
from loguru import logger

from server.config import (
    APP_NAME,
    TRAY_ICON_SIZE,
    TRAY_ICON_BG_COLOR,
    TRAY_ICON_FG_COLOR,
    get_asset_path,
)


def create_image():
    icon_path = get_asset_path("tray_icon.png")

    return Image.open(icon_path)


class TrayIcon:
    def __init__(self, port: int, ip_address: str, on_exit_callback):
        self.port = port
        self.ip_address = ip_address
        self.on_exit_callback = on_exit_callback
        self.icon = None
        self.should_restart = False

    def _on_restart(self, icon, item):
        logger.info("Restart requested from tray icon...")
        self.should_restart = True
        icon.stop()

    def _on_quit(self, icon, item):
        logger.info("Stopping from tray icon...")
        self.should_restart = False
        icon.stop()
        # Control returns to main.py after icon.stop()

    def run(self):
        menu = pystray.Menu(
            pystray.MenuItem(
                f"Address: http://{self.ip_address}:{self.port}", lambda: None, enabled=False
            ),
            pystray.MenuItem("Restart", self._on_restart),
            pystray.MenuItem("Exit", self._on_quit),
        )
        self.icon = pystray.Icon(APP_NAME, create_image(), APP_NAME, menu)

        logger.info("Application minimalized to tray.")
        self.icon.run()

    def stop(self):
        if self.icon:
            self.icon.stop()
