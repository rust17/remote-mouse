import argparse
import sys
from loguru import logger

from server.config import DEFAULT_PORT, configure_logging
from server.services.mdns import MDNSResponder
from server.services.manager import ServiceManager
from server.ui.tray_icon import TrayIcon


def parse_args():
    parser = argparse.ArgumentParser(description="Remote Mouse Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on")
    parser.add_argument("--log", action="store_true", help="Enable file logging")
    return parser.parse_args()


def main():
    args = parse_args()

    # Initial logging configuration
    configure_logging(args.log)
    logger.info(f"Application starting... (Port: {args.port}, Log: {args.log})")

    # 1. Initialize Service Manager
    # Pass initial debug state
    service_manager = ServiceManager(port=args.port, debug=args.log)

    # 2. Helper to handle logging toggle from Tray
    def on_log_toggle(enabled: bool):
        # Update global logging configuration
        configure_logging(enabled)
        # Update ServiceManager state (will take effect on next restart)
        service_manager.set_debug(enabled)

    # 3. Get Local IP for Tray (using a temporary mDNS instance)
    temp_mdns = MDNSResponder(port=args.port)
    local_ip = temp_mdns.get_local_ip()
    # No need to register, just need the IP logic.

    # 4. Initialize Tray Icon
    tray = TrayIcon(
        port=args.port,
        ip_address=local_ip,
        on_exit_callback=service_manager.stop,
        restart_callback=service_manager.restart,
        on_log_toggle_callback=on_log_toggle,
        initial_logging_state=args.log,
    )

    try:
        # 5. Start Services (mDNS + Web Server)
        service_manager.start()

        # 6. Start Tray Icon (Main Thread Blocking)
        tray.run()

        # When tray.run() returns (after Stop/Exit clicked)
        logger.info("Application exited gracefully.")
        sys.exit(0)

    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}", exc_info=True)
        service_manager.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
