import threading
import uvicorn
from loguru import logger

from server.services.mdns import MDNSResponder
from server.services.web import create_app


class ServiceManager:
    """
    Manages the lifecycle of background services (HTTP server and mDNS).
    Provides methods for clean startup, shutdown, and soft restart.
    """

    def __init__(self, port: int, debug: bool = False):
        self.port = port
        self.debug = debug
        self.mdns = None
        self.server = None
        self.server_thread = None

    def set_debug(self, debug: bool):
        self.debug = debug
        # Note: Changing this doesn't affect currently running service until restart.

    def start(self):
        logger.info(f"Starting services (Debug: {self.debug})...")
        try:
            # 1. Start mDNS
            self.mdns = MDNSResponder(port=self.port)
            self.mdns.register()

            # 2. Start Uvicorn
            # Determine Uvicorn log level based on debug state
            log_level = "debug" if self.debug else "info"

            config = uvicorn.Config(
                create_app(),
                host="0.0.0.0",
                port=self.port,
                log_level=log_level,
                log_config=None,  # Delegate logging to loguru (via global intercept if configured)
            )
            self.server = uvicorn.Server(config)
            self.server_thread = threading.Thread(target=self.server.run, daemon=True)
            self.server_thread.start()
            logger.info(f"Server started on port {self.port} with log level '{log_level}'")

        except Exception as e:
            logger.error(f"Failed to start services: {e}")
            self.stop()

    def stop(self):
        logger.info("Stopping services...")
        # Stop mDNS
        if self.mdns:
            try:
                self.mdns.unregister()
            except Exception as e:
                logger.error(f"Error stopping mDNS: {e}")
            finally:
                self.mdns = None

        # Stop Uvicorn
        if self.server:
            self.server.should_exit = True
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=5)
            self.server = None
            self.server_thread = None

        logger.info("Services stopped.")

    def restart(self):
        logger.info("Restarting services...")
        self.stop()
        self.start()
