import threading
import uvicorn
from loguru import logger

from server.config import DEFAULT_PORT, configure_logging
from server.services.mdns import MDNSResponder
from server.services.web import create_app
from server.ui.tray_icon import TrayIcon


def main():
    configure_logging(True)
    logger.info("Application starting...")

    # 1. Initialize Services
    mdns = MDNSResponder(port=DEFAULT_PORT)

    def run_server_thread():
        app = create_app()
        logger.info(f"Starting server on port {DEFAULT_PORT}")
        try:
            # 设置 log_config=None 让 uvicorn 使用我们已经在 main 中配置好的 logging
            uvicorn.run(app, host="0.0.0.0", port=DEFAULT_PORT, log_level="info", log_config=None)
        except Exception as e:
            logger.error(f"Server crashed: {e}")

    def on_exit():
        logger.info("Cleaning up...")
        mdns.unregister()

    tray = TrayIcon(port=DEFAULT_PORT, ip_address=mdns.get_local_ip(), on_exit_callback=on_exit)

    try:
        # 2. Start mDNS
        mdns.register()

        # 3. Start FastAPI in a thread
        server_thread = threading.Thread(target=run_server_thread, daemon=True)
        server_thread.start()

        # 4. Start Tray Icon (Main Thread)
        tray.run()

    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
