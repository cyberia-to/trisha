"""Snapshot local source inputs without committing or changing their repositories."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

EXCLUDED = {".git", ".vendor", ".cache", "node_modules", "__pycache__"}


def is_artifact(root, relative):
    if any(part in EXCLUDED for part in relative.parts):
        return True
    for index, part in enumerate(relative.parts):
        # `src/config/target` is compiler source, not Cargo output. A nested
        # target directory is build output only beneath a Cargo project root.
        if part == "target" and (index == 0 or
                (root.joinpath(*relative.parts[:index]) / "Cargo.toml").is_file()):
            return True
        if part == "cache" and index == 0:
            return True
    return False


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def changes(root):
    paths = git(root, "diff", "--name-only", "HEAD", "-z")
    paths += git(root, "ls-files", "--others", "--exclude-standard", "-z")
    return [name for name in sorted(set(paths.decode().split("\0")) - {""})
            if not is_artifact(root, Path(name))]


def identity(path, relative):
    digest = hashlib.sha256()
    if path.is_symlink():
        target = os.readlink(path)
        content = (target.replace('\\', '/') if os.name == 'nt' else target).encode()
        digest.update(content)
        size = len(content)
        kind = "symlink"
    else:
        size = 0
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        kind = "file"
    return {"path": relative.as_posix(), "type": kind,
            "sha256": digest.hexdigest(), "bytes": size}


def snapshot(root, destination):
    paths = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    files = []
    for name in sorted(set(paths.decode().split("\0")) - {""}):
        relative = Path(name)
        if is_artifact(root, relative):
            continue
        source = root / relative
        if not source.is_file() and not source.is_symlink():
            continue  # Deleted tracked files are recorded in dirty status.
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)
        files.append(identity(target, relative))
    return {"repository": root.name, "commit": git(root, "rev-parse", "HEAD").decode().strip(),
            "mode": "working-tree-snapshot",
            "dirty": git(root, "status", "--porcelain=v1", "--untracked-files=all").decode().splitlines(),
            "files": files}


def inventory(root):
    return [identity(path, path.relative_to(root)) for path in sorted(root.rglob("*"))
            if path.is_file() or path.is_symlink()]


if __name__ == "__main__":
    if sys.argv[1] == "--inventory":
        result = inventory(Path(sys.argv[2]))
    elif sys.argv[1] == "--changes":
        result = changes(Path(sys.argv[2]).resolve())
    else:
        result = snapshot(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
    print(json.dumps(result, indent=2))
