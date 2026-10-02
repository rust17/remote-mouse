import subprocess
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest
import smoke


@pytest.fixture
def windows_build(tmp_path, monkeypatch):
    products = tmp_path / "products"
    products.mkdir()
    names = ["setup.exe", "portable.zip"]
    (products / names[0]).write_bytes(b"installer")
    with zipfile.ZipFile(products / names[1], "w") as archive:
        archive.writestr("RemoteMouse/RemoteMouse.exe", b"portable")
    cwd = tmp_path / "work"
    cwd.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    return products, names, cwd


def test_windows_uninstall_waits_and_runs_once(windows_build, monkeypatch):
    products, names, cwd = windows_build
    installed = cwd / "installed"
    uninstaller = installed / "unins000.exe"
    calls = []

    def fake_run(executable, *args):
        calls.append(Path(executable).name)
        if Path(executable).name == "setup.exe":
            installed.mkdir(exist_ok=True)
            (installed / "RemoteMouse.exe").write_bytes(b"app")
            uninstaller.write_bytes(b"uninstaller")
        else:
            (installed / "RemoteMouse.exe").unlink()
            # Launcher exits first; its file remains until the child finishes.

    monkeypatch.setattr(smoke, "run", fake_run)
    monkeypatch.setattr(smoke, "check_directory", Mock())
    wait = Mock(side_effect=lambda _: uninstaller.unlink())
    monkeypatch.setattr(smoke.time, "sleep", wait)
    smoke.check_windows(products, names, cwd)
    assert calls == ["setup.exe", "setup.exe", "unins000.exe"]
    wait.assert_called_once()
    assert not (Path.home() / ".remote-mouse/installer-smoke-sentinel.txt").exists()


def test_windows_cleanup_preserves_original_startup_error(windows_build, monkeypatch):
    products, names, cwd = windows_build
    installed = cwd / "installed"

    def fake_run(executable, *args):
        if Path(executable).name == "setup.exe":
            installed.mkdir()
            (installed / "unins000.exe").write_bytes(b"uninstaller")
        else:
            raise subprocess.CalledProcessError(1, [str(executable)])

    def fake_check(app, cwd, windows=False):
        if app == installed:
            raise RuntimeError("original startup failure")

    monkeypatch.setattr(smoke, "run", fake_run)
    monkeypatch.setattr(smoke, "check_directory", fake_check)
    with pytest.raises(RuntimeError, match="original startup failure"):
        smoke.check_windows(products, names, cwd)
