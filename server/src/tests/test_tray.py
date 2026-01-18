import pytest
from unittest.mock import MagicMock, patch
from server.ui.tray_icon import TrayIcon


def test_tray_initialization():
    """Test the initial state of the TrayIcon."""
    tray = TrayIcon(port=8000, ip_address="127.0.0.1", on_exit_callback=lambda: None)

    assert tray.port == 8000
    assert tray.ip_address == "127.0.0.1"
    assert tray.should_restart is False
    assert tray.icon is None


def test_on_restart():
    """Test that _on_restart sets the flag and stops the icon loop."""
    tray = TrayIcon(port=8000, ip_address="127.0.0.1", on_exit_callback=lambda: None)
    mock_icon = MagicMock()

    # Simulate clicking "Restart"
    tray._on_restart(mock_icon, None)

    # Verify state change and method call
    assert tray.should_restart is True
    mock_icon.stop.assert_called_once()


def test_on_quit():
    """Test that _on_quit keeps flag False and stops the icon loop."""
    tray = TrayIcon(port=8000, ip_address="127.0.0.1", on_exit_callback=lambda: None)
    mock_icon = MagicMock()

    # Simulate clicking "Exit"
    tray._on_quit(mock_icon, None)

    # Verify state change and method call
    assert tray.should_restart is False
    mock_icon.stop.assert_called_once()
