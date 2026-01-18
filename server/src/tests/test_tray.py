import pytest
from unittest.mock import MagicMock
from server.ui.tray_icon import TrayIcon


def test_tray_initialization():
    """Test the initial state of the TrayIcon."""
    tray = TrayIcon(
        port=8000,
        ip_address="127.0.0.1",
        on_exit_callback=lambda: None,
        initial_logging_state=True,
    )

    assert tray.port == 8000
    assert tray.ip_address == "127.0.0.1"
    assert tray.should_restart is False
    assert tray.logging_enabled is True
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


def test_toggle_logging(mock_tray_deps):
    """Test toggling logging state."""
    mock_deps = mock_tray_deps
    tray = TrayIcon(
        port=8000,
        ip_address="127.0.0.1",
        on_exit_callback=lambda: None,
        initial_logging_state=False,
    )

    # Toggle On
    tray._on_toggle_logging(None, None)
    assert tray.logging_enabled is True
    mock_deps["configure_logging"].assert_called_with(True)

    # Toggle Off
    tray._on_toggle_logging(None, None)
    assert tray.logging_enabled is False
    mock_deps["configure_logging"].assert_called_with(False)


def test_run_constructs_ui_correctly(mock_tray_deps):
    """Test that run() creates the menu with correct items and starts the icon."""
    mock_deps = mock_tray_deps
    tray = TrayIcon(port=9999, ip_address="192.168.1.5", on_exit_callback=lambda: None)

    tray.run()

    # 1. Verify Image Loading
    mock_deps["get_asset_path"].assert_called_with("tray_icon.png")
    mock_deps["image"].open.assert_called_once()

    # 2. Verify Menu Construction
    # We expect 4 MenuItems: Address Info, Log Toggle, Restart, Exit
    assert mock_deps["pystray"].MenuItem.call_count == 4

    # Inspect the calls
    calls = mock_deps["pystray"].MenuItem.call_args_list
    labels = []
    for call in calls:
        arg = call.args[0]
        # Handle callable labels (like get_log_label)
        if callable(arg):
            labels.append(arg(None))
        else:
            labels.append(str(arg))

    assert "Enable Logs" in labels  # Default is False
    assert "Restart" in labels
    assert "Exit" in labels
    assert any("9999" in label for label in labels)

    # 3. Verify Icon creation and running
    mock_deps["pystray"].Icon.assert_called_once()
    mock_deps["icon_instance"].run.assert_called_once()
