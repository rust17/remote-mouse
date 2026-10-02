import json
import subprocess
import sys
from pathlib import Path

import pytest
import release
from common import TARGETS, artifact_names, file_record, validate_version

VERSION = "1.2.3-rc.1"
COMMIT = "a" * 40


@pytest.fixture
def products(tmp_path):
    for host, arch in TARGETS:
        names = artifact_names(VERSION, host, arch)
        for name in names:
            (tmp_path / name).write_bytes(f"payload for {host}/{arch}".encode())
        manifest = {
            "platform": host,
            "arch": arch,
            "version": VERSION,
            "commit": COMMIT,
            "source_dirty": False,
            "files": [file_record(tmp_path / name) for name in names],
        }
        (tmp_path / f"manifest-{host}-{arch}.json").write_text(json.dumps(manifest))
    return tmp_path


def test_verify_complete_same_commit_release(products):
    manifest = release.verify_artifacts(products, VERSION, COMMIT)
    assert len(manifest["builds"]) == 4
    assert len(manifest["files"]) == 5


def test_release_cli_writes_manifest_and_download_checksums(products):
    subprocess.run(
        [
            sys.executable,
            str(Path(release.__file__)),
            "verify",
            "--directory",
            str(products),
            "--version",
            VERSION,
            "--commit",
            COMMIT,
        ],
        check=True,
        capture_output=True,
    )
    manifest = json.loads((products / "build-manifest.json").read_text())
    assert (manifest["version"], manifest["commit"]) == (VERSION, COMMIT)
    records = (products / "SHA256SUMS.txt").read_text().splitlines()
    assert len(records) == 10  # Five packages, four platform manifests, one combined manifest.
    for line in records:
        digest, filename = line.split("  ", 1)
        assert file_record(products / filename)["sha256"] == digest


@pytest.mark.parametrize(
    "field,value",
    [("commit", "b" * 40), ("version", "9.9.9"), ("arch", "arm64"), ("source_dirty", True)],
)
def test_reject_mixed_build_identity(products, field, value):
    path = products / "manifest-linux-x86_64.json"
    manifest = json.loads(path.read_text())
    manifest[field] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="identity mismatch"):
        release.verify_artifacts(products, VERSION, COMMIT)


def test_reject_corrupted_artifact(products):
    (products / artifact_names(VERSION, "linux", "x86_64")[0]).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum"):
        release.verify_artifacts(products, VERSION, COMMIT)


def test_reject_missing_platform(products):
    (products / "manifest-macos-arm64.json").unlink()
    with pytest.raises(FileNotFoundError):
        release.verify_artifacts(products, VERSION, COMMIT)


def test_reject_extra_payload(products):
    (products / "unexpected.exe").write_bytes(b"extra")
    with pytest.raises(ValueError, match="Unexpected files"):
        release.verify_artifacts(products, VERSION, COMMIT)


def test_reject_unsafe_manifest_filename(products):
    path = products / "manifest-linux-x86_64.json"
    manifest = json.loads(path.read_text())
    manifest["files"][0]["name"] = "../outside"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="artifact names"):
        release.verify_artifacts(products, VERSION, COMMIT)


@pytest.mark.parametrize(
    "version", ["1.2", "v1.2.3", "01.2.3", "1.2.3-", "1.2.3-01", "1.2.3;bad", "65536.0.0"]
)
def test_invalid_versions(version):
    with pytest.raises(ValueError):
        validate_version(version)


def test_existing_annotated_and_lightweight_tags(tmp_path, monkeypatch):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    for key, value in [("user.email", "test@example.invalid"), ("user.name", "Packaging Test")]:
        subprocess.run(["git", "-C", str(tmp_path), "config", key, value], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "--allow-empty", "-m", "test"],
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "-C", str(tmp_path), "tag", "v1.2.3"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "tag", "-a", "v1.2.3-rc.1", "-m", "rc"], check=True)
    monkeypatch.setattr(release, "ROOT", tmp_path)
    stable_version, stable_commit = release.resolve_tag("v1.2.3")
    rc_version, rc_commit = release.resolve_tag("v1.2.3-rc.1")
    assert (stable_version, rc_version) == ("1.2.3", "1.2.3-rc.1")
    assert stable_commit == rc_commit
    with pytest.raises(subprocess.CalledProcessError):
        release.resolve_tag("v9.9.9")
    with pytest.raises(ValueError):
        release.resolve_tag("master")
