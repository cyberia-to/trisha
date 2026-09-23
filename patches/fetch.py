"""Extract a checksum-pinned registry archive, never a mutable source cache."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
import urllib.request

MAX_ARCHIVE = 64 * 1024 * 1024


def source_bytes(name, version, expected, cargo_home):
    filename = f"{name}-{version}.crate"
    for path in sorted((cargo_home / "registry/cache").glob(f"*/{filename}")):
        if path.stat().st_size <= MAX_ARCHIVE:
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() == expected:
                return data
    url = f"https://static.crates.io/crates/{name}/{filename}"
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(MAX_ARCHIVE + 1)
    if len(data) > MAX_ARCHIVE or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"upstream checksum mismatch: {filename}")
    return data


def install(data, name, version, expected, destination):
    # Verify again at the extraction boundary, including callers outside the CLI.
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"upstream checksum mismatch: {name}-{version}")
    prefix = f"{name}-{version}"
    destination = destination.absolute()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".upstream-", dir=destination.parent) as directory:
        staging = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive:
                relative = PurePosixPath(member.name)
                if (relative.is_absolute() or ".." in relative.parts
                        or not relative.parts or relative.parts[0] != prefix
                        or not (member.isdir() or member.isfile())):
                    raise ValueError(f"unsupported upstream archive entry: {member.name}")
                path = staging.joinpath(*relative.parts)
                if member.isdir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open("xb") as output:
                        shutil.copyfileobj(archive.extractfile(member), output)
                    path.chmod(0o755 if member.mode & 0o111 else 0o644)
        source = staging / prefix
        if not (source / "Cargo.toml").is_file():
            raise ValueError(f"upstream manifest is missing: {prefix}")
        # Preserve the existing installation until validation and extraction pass.
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        elif destination.exists():
            shutil.rmtree(destination)
        source.rename(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("version")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    pins = json.loads(Path(__file__).with_name("upstream.json").read_text())
    pin = pins[args.name]
    if pin["version"] != args.version:
        raise ValueError("requested version differs from reviewed upstream pin")
    cargo_home = Path(os.environ.get("CARGO_HOME", str(Path.home() / ".cargo")))
    data = source_bytes(args.name, args.version, pin["sha256"], cargo_home)
    install(data, args.name, args.version, pin["sha256"], args.destination)
    print(f"verified {args.name} {args.version} SHA256 {pin['sha256']}")
