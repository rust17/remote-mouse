import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from server.services.web import create_app
from server.services.mdns import MDNSResponder


@pytest.fixture
def mock_zeroconf():
    """Mock the Zeroconf class to avoid actual network calls."""
    with patch("server.services.mdns.Zeroconf") as mock_zc_class:
        mock_instance = MagicMock()
        mock_zc_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_socket():
    """Mock socket to return a predictable local IP."""
    with patch("socket.socket") as mock_sock_class:
        mock_sock_instance = MagicMock()
        mock_sock_class.return_value = mock_sock_instance

        # Setup the mock to return a fake IP when connect/getsockname are called
        mock_sock_instance.getsockname.return_value = ["192.168.1.100"]

        yield mock_sock_instance


@pytest.fixture
def client():
    """Create a TestClient for the FastAPI app."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_tray_deps():
    """Mock external dependencies for TrayIcon to avoid GUI interactions."""
    with (
        patch("server.ui.tray_icon.pystray") as mock_pystray,
        patch("server.ui.tray_icon.Image") as mock_image,
        patch("server.ui.tray_icon.get_asset_path") as mock_get_asset_path,
    ):
        # Setup the mock Icon instance returned by pystray.Icon(...)
        mock_icon_instance = MagicMock()
        mock_pystray.Icon.return_value = mock_icon_instance

        yield {
            "pystray": mock_pystray,
            "image": mock_image,
            "get_asset_path": mock_get_asset_path,
            "icon_instance": mock_icon_instance,
        }
