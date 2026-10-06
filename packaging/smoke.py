"""Validate shipped archives and start the real app without simulating input.

Windows installer checks must run in a disposable VM/CI runner: they register
the current-user installation and then uninstall it.
"""

import argparse
import json
import plistlib
import re
import socket
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from common import artifact_names, file_record


def run(*command):
    subprocess.run(list(map(str, command)), check=True)


def check_server(executable: Path, web: Path, cwd: Path):
    from websockets.sync.client import connect

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    log = cwd / "smoke.log"
    base = f"http://127.0.0.1:{port}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with log.open("wb") as stream:
        process = subprocess.Popen(
            [str(executable), "--port", str(port)], cwd=cwd, stdout=stream, stderr=stream
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"Application exited with {process.returncode}")
                try:
                    with opener.open(base + "/", timeout=1) as response:
                        homepage = response.read()
                    break
                except (OSError, urllib.error.URLError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("HTTP server did not start within 30 seconds") from None
                    time.sleep(0.25)
            if homepage != (web / "index.html").read_bytes():
                raise ValueError("Homepage differs from the bundled web client")
            paths = re.findall(r'(?:src|href)="(/assets/[^"?#]+\.(?:js|css))"', homepage.decode())
            if not paths:
                raise ValueError("Homepage does not reference compiled JS/CSS")
            for path in [
                *paths,
                "/registerSW.js",
                "/debug/eruda.js",
                "/manifest.webmanifest",
                "/sw.js",
            ]:
                with opener.open(base + path, timeout=5) as response:
                    allowed_types = {
                        ".js": {"text/javascript", "application/javascript"},
                        ".css": {"text/css"},
                        ".webmanifest": {"application/manifest+json"},
                    }[Path(path).suffix]
                    if response.headers.get_content_type() not in allowed_types:
                        raise ValueError(f"Incorrect Content-Type for {path}: {response.headers}")
                    if response.read() != (web / path.lstrip("/")).read_bytes():
                        raise ValueError(f"Bundled resource mismatch: {path}")
            with connect(f"ws://127.0.0.1:{port}/ws", open_timeout=5, proxy=None) as websocket:
                # Empty payload is a protocol no-op; no mouse/keyboard instruction is sent.
                websocket.send(b"")
                if not websocket.ping().wait(timeout=5):
                    raise TimeoutError("WebSocket ping timed out")
            print(f"HTTP, static resources and WebSocket passed: {executable}", flush=True)
        except Exception:
            stream.flush()
            print(log.read_text(errors="replace"), flush=True)
            raise
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def check_directory(app: Path, cwd: Path, windows=False):
    executable = app / ("RemoteMouse.exe" if windows else "RemoteMouse")
    web = app / "_internal/web_dist"
    if not (app / "_internal/assets/tray_icon.png").is_file():
        raise ValueError("Missing bundled tray icon")
    check_server(executable, web, cwd)


def check_macos(image: Path, version: str, cwd: Path):
    mount = cwd / "mounted"
    mount.mkdir()
    run("hdiutil", "attach", "-readonly", "-nobrowse", "-mountpoint", mount, image)
    try:
        app = mount / "RemoteMouse.app"
        with (app / "Contents/Info.plist").open("rb") as stream:
            info = plistlib.load(stream)
        if (info["CFBundleIdentifier"], info["RemoteMouseBuildVersion"], info["LSUIElement"]) != (
            "io.github.rust17.remote-mouse",
            version,
            True,
        ):
            raise ValueError("Incorrect app identity/version/menu-bar metadata")
        if (mount / "Applications").readlink() != Path("/Applications"):
            raise ValueError("Missing Applications link")
        run("codesign", "--verify", "--deep", "--strict", app)
        web = app / "Contents/Resources/web_dist"
        if not (app / "Contents/Resources/assets/tray_icon.png").is_file():
            raise ValueError("Missing bundled tray icon")
        # Read-only mounted DMG proves resources do not require writable installation paths.
        check_server(app / "Contents/MacOS/RemoteMouse", web, cwd)
        # Check the normal drag-to-Applications equivalent, including symlinks.
        installed = cwd / "Applications/RemoteMouse.app"
        installed.parent.mkdir()
        run("ditto", app, installed)
        check_server(
            installed / "Contents/MacOS/RemoteMouse", installed / "Contents/Resources/web_dist", cwd
        )
    finally:
        run("hdiutil", "detach", mount)


def uninstall_windows(installed: Path, cwd: Path):
    """Inno's launcher can exit before its temporary uninstaller finishes."""
    uninstaller = installed / "unins000.exe"
    log = cwd / "uninstall.log"
    try:
        run(uninstaller, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/LOG={log}")
        deadline = time.monotonic() + 30
        while (installed / "RemoteMouse.exe").exists() or uninstaller.exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("Windows uninstall did not finish within 30 seconds")
            time.sleep(0.25)
    except Exception:
        if log.exists():
            print(log.read_text(errors="replace"), flush=True)
        raise


def check_windows(products: Path, names: list[str], cwd: Path):
    portable = cwd / "portable"
    with zipfile.ZipFile(products / names[1]) as archive:
        archive.extractall(portable)
    check_directory(portable / "RemoteMouse", cwd, windows=True)
    installed = cwd / "installed"
    installer = products / names[0]
    uninstaller = installed / "unins000.exe"
    # The install is current-user and deliberately requires no elevation.
    user_data = Path.home() / ".remote-mouse"
    user_data.mkdir(exist_ok=True)
    sentinel = user_data / "installer-smoke-sentinel.txt"
    if sentinel.exists():
        raise ValueError("Installer smoke sentinel already exists; use a clean CI runner")
    sentinel.write_text("preserve user data", encoding="utf-8")
    uninstall_started = False
    try:
        for _ in range(2):
            run(installer, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/DIR={installed}")
            if not uninstaller.is_file():
                raise ValueError("Installer did not create an uninstaller")
            check_directory(installed, cwd, windows=True)
        uninstall_started = True
        uninstall_windows(installed, cwd)
        if not sentinel.exists():
            raise ValueError("Uninstall removed user data")
    finally:
        if not uninstall_started and uninstaller.exists():
            try:
                uninstall_windows(installed, cwd)
            except Exception as error:
                # Keep the original install/startup failure visible.
                print(f"Windows cleanup also failed: {error}", flush=True)
        sentinel.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products", type=Path, required=True)
    args = parser.parse_args()
    products = args.products.resolve()
    manifests = list(products.glob("manifest-*.json"))
    if len(manifests) != 1:
        parser.error("Expected exactly one platform build manifest")
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    names = artifact_names(manifest["version"], manifest["platform"], manifest["arch"])
    if [record["name"] for record in manifest["files"]] != names:
        raise ValueError("Manifest artifact names do not match build identity")
    for record in manifest["files"]:
        if file_record(products / record["name"]) != record:
            raise ValueError(f"Checksum mismatch: {record['name']}")
    with tempfile.TemporaryDirectory(prefix="remote-mouse-smoke-") as temporary:
        cwd = Path(temporary)
        # All launches use an unrelated working directory and the shipped artifacts.
        match manifest["platform"]:
            case "macos":
                check_macos(products / names[0], manifest["version"], cwd)
            case "windows":
                check_windows(products, names, cwd)
            case "linux":
                with tarfile.open(products / names[0]) as archive:
                    archive.extractall(cwd, filter="data")
                app = cwd / "RemoteMouse"
                if (
                    not (app / "README.txt").is_file()
                    or not (app / "RemoteMouse.desktop").is_file()
                ):
                    raise ValueError("Missing Linux installation instructions")
                check_directory(app, cwd)
    print("Shipped artifact smoke checks passed", flush=True)


if __name__ == "__main__":
    main()
