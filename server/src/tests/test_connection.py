import struct
from unittest.mock import Mock


def test_binary_command_delivery(client, monkeypatch):
    """Exercise the current WebSocket protocol without controlling the host."""
    processor = Mock()
    monkeypatch.setattr("server.services.web.process_binary_command", processor)
    command = struct.pack(">Bhh", 0x01, 100, -100)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_bytes(command)
    processor.assert_called_once_with(command)
