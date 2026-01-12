import pytest
import socket
from server.services.mdns import MDNSResponder


def test_initialization(mock_zeroconf):
    """Test that MDNSResponder initializes correctly."""
    responder = MDNSResponder(service_name="Test Service", port=1234, hostname="test.local.")

    assert responder.service_name_base == "Test Service"
    assert responder.port == 1234
    assert responder.hostname == "test.local."
    assert responder.zeroconf == mock_zeroconf


def test_get_local_ip(mock_zeroconf, mock_socket):
    """Test IP detection using the socket mock."""
    responder = MDNSResponder()
    ip = responder.get_local_ip()

    assert ip == "192.168.1.100"
    mock_socket.connect.assert_called_with(
        (MDNSResponder.TEST_CONN_IP, MDNSResponder.TEST_CONN_PORT)
    )


def test_register_service(mock_zeroconf, mock_socket):
    """Test that register creates the correct ServiceInfo and registers it."""
    responder = MDNSResponder(service_name="MyMouse", port=5555, hostname="mymouse.local.")

    responder.register()

    # Check if register_service was called on the zeroconf instance
    mock_zeroconf.register_service.assert_called_once()

    # Inspect the ServiceInfo object passed to register_service
    service_info_arg = mock_zeroconf.register_service.call_args[0][0]

    assert service_info_arg.name == f"MyMouse Service.{MDNSResponder.SERVICE_TYPE}"
    assert service_info_arg.server == "mymouse.local."
    assert service_info_arg.port == 5555
    # Verify IP address conversion
    assert service_info_arg.addresses == [socket.inet_aton("192.168.1.100")]


def test_unregister_service(mock_zeroconf, mock_socket):
    """Test that unregister properly removes the service and closes zeroconf."""
    responder = MDNSResponder()

    # Call register first to set up service_info
    responder.register()

    # Now unregister
    responder.unregister()

    mock_zeroconf.unregister_service.assert_called_once()
    mock_zeroconf.close.assert_called_once()


def test_unregister_without_register(mock_zeroconf):
    """Test unregistering before registering shouldn't crash."""
    responder = MDNSResponder()
    responder.unregister()

    mock_zeroconf.unregister_service.assert_not_called()
    mock_zeroconf.close.assert_called_once()
