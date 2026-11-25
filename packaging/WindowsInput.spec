# Standalone SYSTEM helper contains only the standard-library Win32 backend.
# ruff: noqa: F821
import os
from pathlib import Path

root = Path(SPECPATH).parent
analysis = Analysis(
    [str(root / "server/src/server/windows/helper.py")],
    pathex=[str(root / "server/src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pyautogui", "pystray", "fastapi", "uvicorn"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    name="RemoteMouseInput",
    console=False,
    upx=False,
    version=str(Path(os.environ["REMOTE_MOUSE_GENERATED"]) / "windows-version.txt"),
)
