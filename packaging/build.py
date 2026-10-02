"""Build this host's complete distributables using the same entrypoint as CI."""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path

from common import ROOT, artifact_names, file_record, validate_commit, validate_version


def run(*command, cwd=ROOT, env=None):
    print("Running:", " ".join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), cwd=cwd, env=env, check=True)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def make_icons(generated):
    from PIL import Image

    with Image.open(ROOT / "server/src/server/assets/tray_icon.png") as source:
        image = source.convert("RGBA").resize((1024, 1024), Image.Resampling.LANCZOS)
        image.save(generated / "app.icns")
        image.resize((256, 256)).save(
            generated / "app.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)]
        )


def make_windows_version(generated, version):
    numbers = tuple(map(int, version.split("-", 1)[0].split("."))) + (0,)
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numbers!r}, prodvers={numbers!r}, mask=0x3f,
    flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('FileDescription', 'Remote Mouse'),
    StringStruct('FileVersion', {version!r}),
    StringStruct('ProductName', 'Remote Mouse'),
    StringStruct('ProductVersion', {version!r}),
    StringStruct('OriginalFilename', 'RemoteMouse.exe')
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)
"""
    (generated / "windows-version.txt").write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version", help="MAJOR.MINOR.PATCH[-prerelease]; defaults to a dev version"
    )
    parser.add_argument("--commit", help="Expected full source SHA; defaults to HEAD")
    parser.add_argument(
        "--skip-web", action="store_true", help="Use an already-built web-client/dist"
    )
    parser.add_argument("--iscc", help="Path to the Inno Setup compiler (Windows)")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 13):
        parser.error(
            "Run with Python 3.13: uv run --frozen --project server python packaging/build.py"
        )
    host = {"darwin": "macos", "win32": "windows", "linux": "linux"}.get(sys.platform)
    arch = {"arm64": "arm64", "aarch64": "arm64", "amd64": "x86_64", "x86_64": "x86_64"}.get(
        platform.machine().lower()
    )
    commit = validate_commit(args.commit or git("rev-parse", "HEAD"))
    if commit != git("rev-parse", "HEAD"):
        parser.error("--commit does not match the checked-out HEAD")
    project_version = tomllib.loads((ROOT / "server/pyproject.toml").read_text())["project"][
        "version"
    ]
    version = validate_version(args.version or f"{project_version}-dev.{commit[:12]}")
    names = artifact_names(version, host, arch)
    source_dirty = bool(git("status", "--porcelain"))
    node_major = subprocess.check_output(
        ["node", "-p", "process.versions.node.split('.')[0]"], text=True
    ).strip()
    if node_major != "22":
        parser.error("Node.js 22 is required")
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    if not args.skip_web:
        run(npm, "ci", cwd=ROOT / "web-client")
        run(npm, "run", "build", cwd=ROOT / "web-client")
    if not (ROOT / "web-client/dist/index.html").is_file():
        parser.error("Missing web-client/dist/index.html; build the web client first")

    output = ROOT / "packaging/out" / f"{host}-{arch}"
    if output.exists():
        shutil.rmtree(output)
    generated = output / "generated"
    products = output / "products"
    generated.mkdir(parents=True)
    products.mkdir()
    make_icons(generated)
    make_windows_version(generated, version)
    env = dict(os.environ, REMOTE_MOUSE_GENERATED=str(generated), REMOTE_MOUSE_VERSION=version)
    run(
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--distpath",
        output / "dist",
        "--workpath",
        output / "work",
        ROOT / "packaging/RemoteMouse.spec",
        env=env,
    )
    app_dir = output / "dist/RemoteMouse"
    if host == "macos":
        app = output / "dist/RemoteMouse.app"
        run("codesign", "--verify", "--deep", "--strict", app)
        stage = output / "dmg"
        stage.mkdir()
        # ditto preserves the bundle's framework/resource symlinks and executable modes.
        run("ditto", app, stage / app.name)
        (stage / "Applications").symlink_to("/Applications", target_is_directory=True)
        run(
            "hdiutil",
            "create",
            "-volname",
            "Remote Mouse",
            "-srcfolder",
            stage,
            "-format",
            "UDZO",
            "-ov",
            products / names[0],
        )
    elif host == "windows":
        compiler = (
            args.iscc
            or shutil.which("ISCC")
            or str(
                Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
                / "Inno Setup 6/ISCC.exe"
            )
        )
        run(
            compiler,
            f"/DAppVersion={version}",
            f"/DNumericVersion={version.split('-', 1)[0]}",
            f"/DSourceDir={app_dir}",
            f"/DOutputDir={products}",
            f"/DOutputName={Path(names[0]).stem}",
            f"/DIconFile={generated / 'app.ico'}",
            ROOT / "packaging/windows.iss",
        )
        shutil.make_archive(
            str(products / names[1].removesuffix(".zip")),
            "zip",
            root_dir=app_dir.parent,
            base_dir=app_dir.name,
        )
    else:
        shutil.copy2(ROOT / "packaging/LINUX_README.txt", app_dir / "README.txt")
        shutil.copy2(ROOT / "packaging/RemoteMouse.desktop", app_dir / "RemoteMouse.desktop")
        with tarfile.open(products / names[0], "w:gz") as archive:
            archive.add(app_dir, arcname="RemoteMouse")
    manifest = {
        "version": version,
        "commit": commit,
        "source_dirty": source_dirty,
        "platform": host,
        "arch": arch,
        "files": [file_record(products / name) for name in names],
    }
    (products / f"manifest-{host}-{arch}.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Distributables: {products}")


if __name__ == "__main__":
    main()
