"""Verify an extracted source archive against its complete recorded inventory.

The archive/manifests need an independently authenticated hash; these checks
bind a build to that supplied archive, not to an untrusted publisher identity.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    result = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
            size += len(block)
    return result.hexdigest(), size


def relative(value):
    require(isinstance(value, str) and value, 'invalid inventory path')
    path = PurePosixPath(value)
    require(not path.is_absolute() and all(p not in ('', '.', '..') for p in value.split('/')),
            'inventory path must be canonical and relative')
    return path


def regular(path):
    require(stat.S_ISREG(path.lstat().st_mode), f'expected regular file: {path}')


def link_bytes(target):
    # Windows stores a relative symlink using its native separator. Inventory
    # paths and link text use POSIX separators, preserving the same target.
    return (target.replace('\\', '/') if os.name == 'nt' else target).encode()


def load(path):
    regular(path)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate manifest key')
            result[key] = value
        return result
    with path.open() as stream:
        return json.load(stream, object_pairs_hook=unique)


def check_inventory(archive, base, entries, skip_vendor=False):
    require(isinstance(entries, list) and entries, f'complete inventory missing: {base.name}')
    expected = {}
    for entry in entries:
        require(isinstance(entry, dict), 'invalid inventory entry')
        name = str(relative(entry.get('path')))
        require(name not in expected, f'duplicate inventory path: {name}')
        require(entry.get('type') in ('file', 'symlink'), f'unsupported inventory type: {name}')
        require(type(entry.get('bytes')) is int and entry['bytes'] >= 0, f'invalid size: {name}')
        require(isinstance(entry.get('sha256'), str) and len(entry['sha256']) == 64,
                f'invalid digest: {name}')
        expected[name] = entry
    actual = {}
    def walk(folder):
        require(stat.S_ISDIR(folder.lstat().st_mode), f'expected real directory: {folder}')
        for path in sorted(folder.iterdir()):
            name = path.relative_to(base).as_posix()
            if skip_vendor and name == '.vendor':
                require(stat.S_ISDIR(path.lstat().st_mode), 'vendor root must be a real directory')
                continue
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode):
                walk(path)
                continue
            require(name in expected, f'unrecorded source: {path}')
            entry = expected[name]
            if stat.S_ISLNK(mode):
                target = os.readlink(path)
                require(not os.path.isabs(target), f'absolute source symlink: {path}')
                try:
                    resolved = path.resolve(strict=True)
                except (OSError, RuntimeError) as error:
                    raise ValueError(f'invalid source symlink: {path}') from error
                require(resolved.is_relative_to(archive), f'source symlink escapes archive: {path}')
                require(resolved.is_file(), f'source symlink must resolve to a file: {path}')
                raw = link_bytes(target)
                kind, sha, size = 'symlink', hashlib.sha256(raw).hexdigest(), len(raw)
            else:
                require(stat.S_ISREG(mode), f'special source file refused: {path}')
                kind = 'file'
                sha, size = digest(path)
            require((kind, sha, size) == (entry['type'], entry['sha256'], entry['bytes']),
                    f'source identity mismatch: {path}')
            actual[name] = (kind, sha, size)
    walk(base)
    require(set(actual) == set(expected), f'missing recorded source: {base}: {sorted(set(expected)-set(actual))[:3]}')
    return len(actual)


def verify(source, expected=None):
    source = Path(source).resolve(strict=True)
    sources = load(source / 'sources.json')
    vendor = load(source / 'vendor-sources.json')
    require(isinstance(sources, list) and sources, 'repository inventory missing')
    names = set()
    counts = {}
    for repository in sources:
        name = str(relative(repository.get('repository')))
        require('/' not in name and name not in names, 'invalid/duplicate repository name')
        names.add(name)
        counts[name] = check_inventory(source, source / name, repository.get('files'), name == 'trisha')
    require({'trident', 'trisha', 'joy'} <= names, 'coordinated product repository missing')
    for child in source.iterdir():
        require(child.name in names | {'sources.json', 'vendor-sources.json', 'BUILD.txt'},
                f'unrecorded archive root: {child.name}')
    vendor_count = check_inventory(source, source / 'trisha' / '.vendor', vendor)
    manifests = {}
    for name in ('sources.json', 'vendor-sources.json', 'BUILD.txt'):
        path = source / name
        if name != 'BUILD.txt' or path.exists():
            regular(path)
            manifests[name] = digest(path)[0]
    receipt = {'format': 'trisha-source-verification-v1', 'manifests': manifests,
               'repository_files': counts, 'vendor_files': vendor_count}
    if expected is not None:
        require(receipt == load(Path(expected)), 'source provenance changed during build')
    return receipt


def check_destination(source, destination):
    source = Path(source).resolve(strict=True)
    destination = Path(os.path.abspath(Path(destination).expanduser()))
    require(not os.path.lexists(destination), 'candidate prefix must not exist, including a dangling symlink')
    parent = destination.parent.resolve(strict=True)
    require(parent.is_dir(), 'candidate parent must be a directory')
    require(not any(os.path.samefile(ancestor, source) for ancestor in (parent, *parent.parents)),
            'candidate destination must be outside the source archive')
    return parent / destination.name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, nargs='?')
    parser.add_argument('--check-destination', type=Path, nargs=2)
    parser.add_argument('--check-contained', type=Path, nargs='+')
    parser.add_argument('--expect', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.check_contained:
        root, *paths = args.check_contained
        root = root.resolve(strict=True)
        for path in paths:
            require(path.resolve(strict=True).is_relative_to(root),
                    f'dependency escapes source archive: {path}')
        return
    if args.check_destination:
        print(check_destination(*args.check_destination))
        return
    require(args.source is not None, "source archive required")
    receipt = verify(args.source, args.expect)
    if args.output:
        with args.output.open('x') as stream:
            json.dump(receipt, stream, indent=2)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
