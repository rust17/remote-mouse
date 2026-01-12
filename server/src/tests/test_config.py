from pathlib import Path
from server.config import get_share_dir, get_static_dir


def test_get_share_dir():
    share_dir = get_share_dir()
    assert isinstance(share_dir, Path)
    assert share_dir.name == ".remote-mouse"
    # Ensure it creates the directory
    assert share_dir.exists()


def test_get_static_dir():
    static_dir = get_static_dir()
    assert isinstance(static_dir, Path)
    # The actual path depends on environment, but we can check if it returns a Path
    # In development, it should end with web-client/dist
    if "site-packages" not in str(static_dir):
        assert static_dir.parts[-2:] == ("web-client", "dist")
