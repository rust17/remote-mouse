import sys
from pathlib import Path

import pytest

from server import config


def test_get_share_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    share_dir = config.get_share_dir()
    assert isinstance(share_dir, Path)
    assert share_dir.name == ".remote-mouse"
    # Ensure it creates the directory
    assert share_dir.exists()


def test_development_resources_ignore_working_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.chdir(tmp_path)
    root = Path(config.__file__).resolve().parents[3]
    assert config.get_static_dir() == root / "web-client/dist"
    expected_icon = Path(config.__file__).parent / "assets/tray_icon.png"
    assert config.get_asset_path("tray_icon.png") == expected_icon


@pytest.mark.parametrize("bundle_name", ["_internal", "Contents/Frameworks"])
def test_frozen_resources_are_read_without_copying(tmp_path, monkeypatch, bundle_name):
    bundle = tmp_path / bundle_name
    (bundle / "web_dist").mkdir(parents=True)
    (bundle / "web_dist/index.html").write_text("bundled page")
    (bundle / "assets").mkdir()
    (bundle / "assets/tray_icon.png").write_bytes(b"icon")
    home = tmp_path / "home"
    cache = home / ".remote-mouse/web_dist"
    cache.mkdir(parents=True)
    (cache / "index.html").write_text("old cached page")
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.chdir(home)

    def unexpected_share_access():
        pytest.fail("Reading bundled resources must not access writable user storage")

    monkeypatch.setattr(config, "get_share_dir", unexpected_share_access)
    for _ in range(2):
        assert config.get_static_dir() == bundle / "web_dist"
        assert (config.get_static_dir() / "index.html").read_text() == "bundled page"
        assert config.get_asset_path("tray_icon.png").read_bytes() == b"icon"
    assert (cache / "index.html").read_text() == "old cached page"
