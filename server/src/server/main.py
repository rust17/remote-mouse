import threading
import uvicorn
import sys
import os
import subprocess
import argparse
from loguru import logger

from server.config import DEFAULT_PORT, configure_logging
from server.services.mdns import MDNSResponder
from server.services.web import create_app
from server.ui.tray_icon import TrayIcon


def parse_args():
    parser = argparse.ArgumentParser(description="Remote Mouse Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on")
    parser.add_argument("--log", action="store_true", help="Enable file logging")
    return parser.parse_args()


def main():
    args = parse_args()

    # Configure logging based on args
    configure_logging(args.log)
    logger.info(f"Application starting... (Port: {args.port}, Log: {args.log})")

    # 1. Initialize Services
    mdns = MDNSResponder(port=args.port)

    def run_server_thread():
        app = create_app()
        logger.info(f"Starting server on port {args.port}")
        try:
            # 设置 log_config=None 让 uvicorn 使用我们已经在 main 中配置好的 logging
            uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info", log_config=None)
        except Exception as e:
            logger.error(f"Server crashed: {e}")

    def on_exit():
        logger.info("Cleaning up...")
        mdns.unregister()

    tray = TrayIcon(
        port=args.port,
        ip_address=mdns.get_local_ip(),
        on_exit_callback=on_exit,
        initial_logging_state=args.log,
    )

    try:
        # 2. Start mDNS
        mdns.register()

        # 3. Start FastAPI in a thread
        server_thread = threading.Thread(target=run_server_thread, daemon=True)
        server_thread.start()

        # 4. Start Tray Icon (Main Thread)
        tray.run()

        # 5. Handle Exit or Restart
        on_exit()
        if tray.should_restart:
            logger.info("Restarting application...")

            # Construct new command args
            if getattr(sys, 'frozen', False):
                # If packaged with PyInstaller, sys.executable is the exe itself
                # and we don't need "-m server.main"
                new_args = [sys.executable, "--port", str(args.port)]
            else:
                # If running from source, use python executable with module flag
                new_args = [sys.executable, "-m", "server.main", "--port", str(args.port)]

            # Use the logging state from tray
            if tray.logging_enabled:
                new_args.append("--log")

            logger.info(f"Restart command: {new_args}")
            # Spawn a new process and exit the current one
            subprocess.Popen(new_args)
            sys.exit(0)
        else:
            logger.info("Application exited gracefully.")
            sys.exit(0)

    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
