"""Resolve an existing release tag or verify this run's complete artifact set."""

import argparse
import json
import os
import subprocess
from pathlib import Path

from common import ROOT, TARGETS, artifact_names, file_record, validate_commit, validate_version


def resolve_tag(tag: str) -> tuple[str, str]:
    if not tag.startswith("v"):
        raise ValueError("Release tags must start with v")
    version = validate_version(tag[1:])
    commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"], cwd=ROOT, text=True
    ).strip()
    return version, validate_commit(commit)


def verify_artifacts(directory: Path, version: str, commit: str) -> dict:
    validate_version(version)
    validate_commit(commit)
    builds = []
    files = []
    expected = set()
    for host, arch in TARGETS:
        manifest_name = f"manifest-{host}-{arch}.json"
        expected.add(manifest_name)
        manifest = json.loads((directory / manifest_name).read_text(encoding="utf-8"))
        identity = (manifest["platform"], manifest["arch"], manifest["version"], manifest["commit"])
        if identity != (host, arch, version, commit) or manifest.get("source_dirty") is not False:
            raise ValueError(f"Build identity mismatch or dirty source: {manifest_name}")
        names = artifact_names(version, host, arch)
        if [item["name"] for item in manifest["files"]] != names:
            raise ValueError(f"Unexpected artifact names: {manifest_name}")
        for record in manifest["files"]:
            actual = file_record(directory / record["name"])
            if actual != record or actual["size"] == 0:
                raise ValueError(f"Artifact checksum/size mismatch: {record['name']}")
            expected.add(record["name"])
            files.append(record)
        builds.append(manifest)
    actual_names = {path.name for path in directory.iterdir()}
    if actual_names != expected:
        raise ValueError(f"Unexpected files in release directory: {actual_names ^ expected}")
    return {"version": version, "commit": commit, "builds": builds, "files": files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--tag", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--directory", type=Path, required=True)
    verify.add_argument("--version", required=True)
    verify.add_argument("--commit", required=True)
    verify.add_argument(
        "--tag", help="Also ensure the release tag still points to the built commit"
    )
    args = parser.parse_args()
    if args.command == "prepare":
        version, commit = resolve_tag(args.tag)
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
                stream.write(f"version={version}\ncommit={commit}\n")
        print(json.dumps({"version": version, "commit": commit}))
    else:
        if args.tag and resolve_tag(args.tag) != (args.version, args.commit):
            raise ValueError("Release tag moved since the build started")
        manifest = verify_artifacts(args.directory, args.version, args.commit)
        (args.directory / "build-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        # Include both the platform manifests and combined manifest in the checksum list.
        records = [file_record(path) for path in sorted(args.directory.iterdir())]
        (args.directory / "SHA256SUMS.txt").write_text(
            "".join(f"{item['sha256']}  {item['name']}\n" for item in records), encoding="utf-8"
        )
        print(f"Verified {len(manifest['files'])} distributables from {args.commit}")


if __name__ == "__main__":
    main()
