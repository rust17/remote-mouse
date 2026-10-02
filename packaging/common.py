"""Shared build identity and artifact naming; uses only the standard library."""

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
TARGETS = (("macos", "arm64"), ("macos", "x86_64"), ("windows", "x86_64"), ("linux", "x86_64"))


def validate_version(version: str) -> str:
    match = VERSION_PATTERN.fullmatch(version)
    if not match or any(int(part) > 65535 for part in match.groups()[:3]):
        raise ValueError(f"Invalid version: {version!r}; expected MAJOR.MINOR.PATCH[-prerelease]")
    prerelease = match.group(4)
    if prerelease and any(
        part.isdigit() and len(part) > 1 and part.startswith("0") for part in prerelease.split(".")
    ):
        raise ValueError("Numeric prerelease identifiers cannot have leading zeros")
    return version


def validate_commit(commit: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Expected a full 40-character commit SHA")
    return commit


def artifact_names(version: str, platform: str, arch: str) -> list[str]:
    validate_version(version)
    if (platform, arch) not in TARGETS:
        raise ValueError(f"Unsupported target: {platform}/{arch}")
    prefix = f"RemoteMouse-{version}-{platform}-{arch}"
    match platform:
        case "macos":
            return [f"{prefix}.dmg"]
        case "windows":
            return [f"{prefix}-setup.exe", f"{prefix}-portable.zip"]
        case "linux":
            return [f"{prefix}.tar.gz"]
    raise ValueError(platform)


def file_record(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"name": path.name, "size": path.stat().st_size, "sha256": digest.hexdigest()}
