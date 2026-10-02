import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).parent
generated = Path(os.environ["REMOTE_MOUSE_GENERATED"])
version = os.environ["REMOTE_MOUSE_VERSION"]
numeric_version = version.split("-", 1)[0].split("+", 1)[0]
backend = {"darwin": "darwin", "win32": "win32", "linux": "xorg"}[sys.platform]
icon = str(generated / ("app.icns" if sys.platform == "darwin" else "app.ico"))

a = Analysis(
    [str(root / "server/src/server/main.py")],
    pathex=[str(root / "server/src")],
    binaries=[],
    datas=[
        (str(root / "web-client/dist"), "web_dist"),
        (str(root / "server/src/server/assets"), "assets"),
    ],
    hiddenimports=[f"pystray._{backend}"] + collect_submodules("uvicorn"),
    hookspath=[],
    runtime_hooks=[str(root / "packaging/runtime_hook.py")],
    # MouseInfo is an optional coordinate-inspection GUI. On Linux it calls
    # sys.exit() if tkinter is unavailable, even when only importing PyAutoGUI.
    excludes=["tkinter", "mouseinfo", "unittest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RemoteMouse",
    debug=False,
    strip=False,
    upx=False,
    console=sys.platform == "linux",
    icon=icon if sys.platform != "linux" else None,
    version=str(generated / "windows-version.txt") if sys.platform == "win32" else None,
    codesign_identity=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="RemoteMouse")
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="RemoteMouse.app",
        icon=icon,
        bundle_identifier="io.github.rust17.remote-mouse",
        info_plist={
            "CFBundleName": "Remote Mouse",
            "CFBundleDisplayName": "Remote Mouse",
            "CFBundleShortVersionString": numeric_version,
            "CFBundleVersion": numeric_version,
            "RemoteMouseBuildVersion": version,
            "LSUIElement": True,
        },
    )
