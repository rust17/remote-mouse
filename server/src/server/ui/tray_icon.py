import os
import pystray
from PIL import Image, ImageDraw
from loguru import logger

from server.config import APP_NAME, TRAY_ICON_SIZE, TRAY_ICON_BG_COLOR, TRAY_ICON_FG_COLOR


def create_image():
    width, height = TRAY_ICON_SIZE
    image = Image.new("RGB", (width, height), TRAY_ICON_BG_COLOR)
    dc = ImageDraw.Draw(image)
    dc.rectangle(
        (width // 4, height // 4, width * 3 // 4, height * 3 // 4), fill=TRAY_ICON_FG_COLOR
    )
    return image


class TrayIcon:
    def __init__(self, port: int, on_exit_callback):
        self.port = port
        self.on_exit_callback = on_exit_callback
        self.icon = None

    def _on_quit(self, icon, item):
        logger.info("Stopping from tray icon...")
        icon.stop()
        if self.on_exit_callback:
            self.on_exit_callback()
        # Ensure process exits if not handled by callback completely
        os._exit(0)

    def run(self):
        menu = pystray.Menu(
            pystray.MenuItem(f"Listening on port {self.port}", lambda: None, enabled=False),
            pystray.MenuItem("Exit", self._on_quit),
        )
        self.icon = pystray.Icon(APP_NAME, create_image(), APP_NAME, menu)

        logger.info("Application minimalized to tray.")
        self.icon.run()

    def stop(self):
        if self.icon:
            self.icon.stop()
