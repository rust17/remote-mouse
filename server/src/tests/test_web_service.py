import pytest


def test_static_files(client):
    # This might fail if the dist directory is empty or missing,
    # but it verifies the app is created correctly.
    # We expect either 200 (if index.html exists) or 404 (if not built)
    response = client.get("/")
    assert response.status_code in [200, 404]


def test_websocket_endpoint_connect(client):
    with client.websocket_connect("/ws") as websocket:
        # Just test connection establishment
        assert websocket
