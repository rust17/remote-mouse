import mimetypes

import pytest
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


@pytest.mark.parametrize("method", ["GET", "HEAD"])
@pytest.mark.parametrize(
    ("path", "media_type"),
    [
        ("index.html", "text/html"),
        ("assets/app.js", "text/javascript"),
        ("assets/module.mjs", "text/javascript"),
        ("registerSW.js", "text/javascript"),
        ("sw.js", "text/javascript"),
        ("assets/app.css", "text/css"),
        ("manifest.webmanifest", "application/manifest+json"),
    ],
)
def test_static_mime_types_ignore_system_associations(
    tmp_path, monkeypatch, path, media_type, method
):
    resource = tmp_path / path
    resource.parent.mkdir(parents=True, exist_ok=True)
    resource.write_bytes(b"bundled resource")
    mimetypes.init()
    monkeypatch.setitem(mimetypes.types_map, resource.suffix, "application/octet-stream")
    monkeypatch.setattr(web, "get_static_dir", lambda: tmp_path)
    with TestClient(web.create_app()) as client:
        url = "/" if path == "index.html" else f"/{path}"
        response = client.request(method, url)
    assert response.status_code == 200
    assert response.headers["content-type"].split(";", 1)[0] == media_type
    assert response.content == (resource.read_bytes() if method == "GET" else b"")


def test_javascript_plain_text_mapping_preserves_cache_and_range_requests(tmp_path, monkeypatch):
    (tmp_path / "app.js").write_bytes(b"console.log('remote mouse');")
    mimetypes.init()
    monkeypatch.setitem(mimetypes.types_map, ".js", "text/plain")
    monkeypatch.setattr(web, "get_static_dir", lambda: tmp_path)
    with TestClient(web.create_app()) as client:
        response = client.get("/app.js")
        assert response.headers["content-type"] == "text/javascript; charset=utf-8"
        cached = client.get("/app.js", headers={"If-None-Match": response.headers["etag"]})
        assert cached.status_code == 304
        assert cached.content == b""
        assert cached.headers["content-type"] == "text/javascript; charset=utf-8"
        partial = client.get("/app.js", headers={"Range": "bytes=0-6"})
        assert partial.status_code == 206
        assert partial.content == b"console"
        assert partial.headers["content-type"] == "text/javascript; charset=utf-8"
        assert client.get("/missing.js").status_code == 404
