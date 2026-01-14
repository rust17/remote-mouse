import sys
from pathlib import Path
from loguru import logger

# App Info
APP_NAME = "Remote Mouse"
APP_DIR_NAME = ".remote-mouse"

# Network Defaults
DEFAULT_PORT = 9997
MDNS_HOSTNAME = "remote-mouse.local."

# UI Defaults
TRAY_ICON_SIZE = (64, 64)
TRAY_ICON_BG_COLOR = "blue"
TRAY_ICON_FG_COLOR = "white"


def get_share_dir() -> Path:
    share_dir = Path.home() / APP_DIR_NAME
    share_dir.mkdir(parents=True, exist_ok=True)
    return share_dir


def get_static_dir() -> Path:
    # 1. 打包环境 (PyInstaller): 指向 sys._MEIPASS/web_dist
    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys._MEIPASS)
        static_dir = bundle_dir / "web_dist"
    else:
        # 2. 开发环境: 指向源码目录 ../../../web-client/dist
        # project_root is server/ (where pyproject.toml is)
        # __file__ is server/src/server/config.py
        project_root = Path(__file__).resolve().parents[3]
        static_dir = project_root / "web-client" / "dist"

    return static_dir


def get_asset_path(filename: str) -> Path:
    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys._MEIPASS)
        asset_path = bundle_dir / "assets" / filename
    else:
        current_dir = Path(__file__).resolve().parent
        asset_path = current_dir / "assets" / filename
    return asset_path


def configure_logging(debug: bool = False):
    if debug:
        logger.remove()  # Remove default stderr handler
        logger.add(
            get_share_dir() / "logs" / "server.log",
            level="TRACE" if debug else "INFO",
            rotation="06:00",
            retention="10 days",
        )
