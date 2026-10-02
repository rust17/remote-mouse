from fastapi.testclient import TestClient
from server.services import web


def test_static_files_and_websocket(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text('<html><script src="/assets/app.js"></script></html>')
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/app.js").write_text("console.log('remote mouse');")
    monkeypatch.setattr(web, "get_static_dir", lambda: tmp_path)
    commands = []
    monkeypatch.setattr(web, "process_binary_command", commands.append)
    with TestClient(web.create_app()) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.text == (tmp_path / "index.html").read_text()
        resource = client.get("/assets/app.js")
        assert resource.status_code == 200
        assert resource.text == (tmp_path / "assets/app.js").read_text()
        assert client.get("/assets/missing.js").status_code == 404
        with client.websocket_connect("/ws") as websocket:
            websocket.send_bytes(b"")
    assert commands == [b""]


def test_websocket_endpoint_connect(client):
    with client.websocket_connect("/ws") as websocket:
        # Just test connection establishment
        assert websocket
