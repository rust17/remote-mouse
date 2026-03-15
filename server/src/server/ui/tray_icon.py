import threading
import time
from typing import Callable, Optional, Tuple

import pystray
from loguru import logger
from PIL import Image, ImageDraw, ImageFont

from server.config import APP_NAME, get_asset_path
from server.core.metrics import metrics


def create_image() -> Image.Image:
    """Load the base tray icon image."""
    icon_path = get_asset_path("tray_icon.png")
    return Image.open(icon_path)


class TrayIcon:
    """System tray icon manager with real-time metrics display."""

    instance = None

    def __init__(
        self,
        port: int,
        ip_address: str,
        on_exit_callback: Callable[[], None],
        restart_callback: Callable[[], None],
        on_log_toggle_callback: Callable[[bool], None],
        initial_logging_state: bool = False,
    ):
        TrayIcon.instance = self
        self.port = port
        self.ip_address = ip_address
        self.on_exit_callback = on_exit_callback
        self.restart_callback = restart_callback
        self.on_log_toggle_callback = on_log_toggle_callback

        self.icon: Optional[pystray.Icon] = None
        self.logging_enabled = initial_logging_state
        self.show_rate = False

        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._base_image = create_image()

        # Calculate appropriate font size based on icon resolution
        _, height = self._base_image.size
        # Font size ~1/2.5 of height to remain visible when scaled
        self.font_size = max(12, int(height / 2.5))
        self.font = self._load_best_font(self.font_size)
        self.padding = max(1, height // 20)
        self.halo_width = max(1, self.font_size // 15)

    @staticmethod
    def _load_best_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """Attempt to load a system font, falling back to default."""
        font_names = [
            "arial.ttf",
            "consola.ttf",
            "msyh.ttc",  # Windows
            "Arial.ttf",
            "Menlo.ttc",
            "Courier.dfont",  # macOS
            "DejaVuSans.ttf",
            "FreeSans.ttf",  # Linux
        ]
        for name in font_names:
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _on_restart(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        logger.info("Restart requested from tray icon...")
        if self.restart_callback:
            self.restart_callback()

    def _on_quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        logger.info("Stopping from tray icon...")
        self._stop_event.set()
        if self.on_exit_callback:
            self.on_exit_callback()
        icon.stop()

    def _on_toggle_logging(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        self.logging_enabled = not self.logging_enabled
        logger.info(f"Tray toggled logging to {self.logging_enabled}")
        if self.on_log_toggle_callback:
            self.on_log_toggle_callback(self.logging_enabled)

    def set_show_rate(self, enabled: bool) -> None:
        if self.show_rate == enabled:
            return
        self.show_rate = enabled
        logger.info(f"Tray toggled rate display to {self.show_rate}")

        if self.show_rate:
            self._stop_event.clear()  # Ensure thread can run
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()
        else:
            self._stop_event.set()
            if self.icon:
                self.icon.icon = self._base_image

    def _monitor_loop(self) -> None:
        """Background loop to update icon with real-time metrics."""
        while not self._stop_event.is_set():
            if self.icon and self.show_rate:
                pps, bps = metrics.get_current()
                self.icon.icon = self._create_rate_image(pps, bps)

            # Sleep in small increments for better responsiveness to stop event
            for _ in range(10):
                if self._stop_event.is_set():
                    break
                time.sleep(0.1)

    def _draw_text_with_halo(
        self,
        draw: ImageDraw.ImageDraw,
        pos: Tuple[int, int],
        text: str,
        color: Tuple[int, int, int, int],
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    ) -> None:
        """Draw text with a black halo/outline for better contrast."""
        x, y = pos
        halo = self.halo_width
        # Draw thick black outline
        for dx in range(-halo, halo + 1):
            for dy in range(-halo, halo + 1):
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y + dy), text, fill=(0, 0, 0, 255), font=font)
        # Draw main text
        draw.text((x, y), text, fill=color, font=font)

    def _create_rate_image(self, pps: int, bps: float) -> Image.Image:
        """Overlay rate metrics on the base icon."""
        img = self._base_image.copy().convert("RGBA")
        draw = ImageDraw.Draw(img)
        width, height = img.size

        pps_text = str(pps)
        bps_text = self._format_bps(bps)
        pad = self.padding

        # PPS (Top Left)
        self._draw_text_with_halo(draw, (pad, pad), pps_text, (255, 255, 255, 255), self.font)

        # BPS (Bottom Right)
        try:
            tw = draw.textlength(bps_text, font=self.font)
            pos = (width - tw - pad, height - self.font_size - pad)
        except AttributeError:
            # Fallback if textlength is not available
            pos = (pad, height // 2)

        self._draw_text_with_halo(draw, pos, bps_text, (0, 255, 0, 255), self.font)
        return img

    @staticmethod
    def _format_bps(bps: float) -> str:
        """Format bits-per-second into human readable string."""
        if bps < 1024:
            return f"{int(bps)}B"
        if bps < 1024 * 1024:
            return f"{bps / 1024:.0f}K"
        return f"{bps / 1024 / 1024:.1f}M"

    def run(self) -> None:
        """Initialize and run the system tray icon."""
        menu = pystray.Menu(
            pystray.MenuItem(
                f"Address: http://{self.ip_address}:{self.port}",
                lambda: None,
                enabled=False,
            ),
            pystray.MenuItem(
                lambda _: "Disable Logs" if self.logging_enabled else "Enable Logs",
                self._on_toggle_logging,
            ),
            pystray.MenuItem("Restart", self._on_restart),
            pystray.MenuItem("Exit", self._on_quit),
        )

        self.icon = pystray.Icon(APP_NAME, self._base_image, APP_NAME, menu)
        logger.info("Application minimized to tray.")
        self.icon.run()
