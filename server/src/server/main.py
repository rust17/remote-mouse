import threading
import uvicorn
import pystray
from PIL import Image, ImageDraw
import logging
import os
import signal
import sys
from pathlib import Path
from loguru import logger

from server.mdns import MDNSResponder
from server.web_server import app


def enable_logging(debug: bool = False) -> None:
    if debug:
        logger.remove()  # Remove default stderr handler
        logger.add(
            get_share_dir() / "logs" / "server.log",
            # FIXME: configure level for different modules
            level="TRACE" if debug else "INFO",
            rotation="06:00",
            retention="10 days",
        )


def get_share_dir() -> Path:
    share_dir = Path.home() / ".remote-mouse"
    share_dir.mkdir(parents=True, exist_ok=True)
    return share_dir


PORT = 9997
mdns = MDNSResponder(port=PORT)


def create_image():
    width = 64
    height = 64
    color1 = "blue"
    color2 = "white"
    image = Image.new("RGB", (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle((width // 4, height // 4, width * 3 // 4, height * 3 // 4), fill=color2)
    return image


def run_server():
    logger.info(f"Starting server on port {PORT}")
    try:
        # 在打包环境下，uvicorn 的默认日志配置可能会报错 "Unable to configure formatter 'default'"
        # 设置 log_config=None 让 uvicorn 使用我们已经在 main 中配置好的 logging
        uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info", log_config=None)
    except Exception as e:
        logger.error(f"Server crashed: {e}")


def on_quit(icon, item):
    logger.info("Stopping...")
    mdns.unregister()
    icon.stop()
    os._exit(0)


def main():
    enable_logging(False)

    logger.info("Application starting...")
    try:
        # 1. 启动 mDNS
        mdns.register()

        # 2. 在线程中启动 FastAPI/Uvicorn
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        # 3. 启动系统托盘 (主线程)
        menu = pystray.Menu(
            pystray.MenuItem(f"Listening on port {PORT}", lambda: None, enabled=False),
            pystray.MenuItem("Exit", on_quit),
        )
        icon = pystray.Icon("RemoteMouse", create_image(), "Remote Mouse", menu)

        logger.info("Application started. Minimalized to tray.")
        icon.run()
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}", exc_info=True)
        # Optional: Show a message box if possible, but logging is key
        raise


if __name__ == "__main__":
    main()
