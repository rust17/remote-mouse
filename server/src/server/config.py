import sys
import shutil
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
    # 1. PyInstaller environment
    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys._MEIPASS)
        source_static = bundle_dir / "web_dist"
        
        # Target: ~/.remote-mouse/web_dist (Persistent storage to avoid /tmp cleanup)
        target_static = get_share_dir() / "web_dist"
        
        try:
            # Sync files to persistent directory
            if target_static.exists():
                shutil.rmtree(target_static)
            shutil.copytree(source_static, target_static)
            logger.info(f"Static files synced to: {target_static}")
            return target_static
        except Exception as e:
            logger.error(f"Failed to sync static files to persistent storage: {e}")
            return source_static  # Fallback to temporary one
    else:
        # 2. Dev environment: points to ../../../web-client/dist
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
    """
    Configures loguru logger.
    If debug=True: Logs to file (DEBUG level) and stderr.
    If debug=False: Logs to stderr only (INFO level).
    """
    logger.remove()  # Clear all existing handlers

    if debug:
        # File Handler
        log_file = get_share_dir() / "logs" / "server.log"
        logger.add(
            log_file,
            level="DEBUG",
            rotation="06:00",
            retention="10 days",
            enqueue=True,  # Thread-safe
        )
        # Console Handler (keep it for immediate feedback if run in console)

        if sys.stderr:
            logger.add(sys.stderr, level="DEBUG")

    else:
        # Default Console Handler

        if sys.stderr:
            logger.add(sys.stderr, level="INFO")
