"""Retain exact hosted logs, deduplicating identical bytes with TAR hard links."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifacts', type=Path)
    parser.add_argument('archive', type=Path)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    assert args.manifest.name.endswith('.json.gz')
    root = args.artifacts.resolve()
    assert not args.archive.resolve().is_relative_to(root)
    binaries = set()
    for receipt in root.glob('*/receipt.json'):
        value = json.loads(receipt.read_text())
        binaries.add((receipt.parent / value['joy_binary']['path']).relative_to(root).as_posix())
    assert len(binaries) == 6
    files = {}
    first = {}
    with args.archive.open('xb') as destination:
        with gzip.GzipFile(fileobj=destination, mode='wb', filename='', mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as archive:
                for path in sorted(root.rglob('*')):
                    assert not path.is_symlink()
                    if path.is_dir():
                        continue
                    assert path.is_file()
                    relative = path.relative_to(root).as_posix()
                    data = path.read_bytes()
                    digest = sha(data)
                    row = dict(bytes=len(data), sha256=digest)
                    files[relative] = row
                    if relative in binaries:
                        row['storage'] = 'native binary retained in original Actions artifact and local download'
                        continue
                    name = 'hosted/' + relative
                    member = tarfile.TarInfo(name)
                    member.mode = 0o644
                    key = (digest, len(data))
                    if key in first:
                        member.type = tarfile.LNKTYPE
                        member.linkname = first[key]
                        row['storage'] = 'hardlink:' + first[key]
                        archive.addfile(member)
                    else:
                        member.size = len(data)
                        row['storage'] = 'file'
                        first[key] = name
                        archive.addfile(member, io.BytesIO(data))
    with tarfile.open(args.archive) as archive:
        retained = set()
        for member in archive.getmembers():
            relative = member.name.removeprefix('hosted/')
            data = archive.extractfile(member).read()
            assert sha(data) == files[relative]['sha256']
            assert len(data) == files[relative]['bytes']
            retained.add(relative)
        assert retained == set(files) - binaries
    manifest = dict(archive=args.archive.name, bytes=args.archive.stat().st_size,
        sha256=sha(args.archive.read_bytes()), files=files,
        all_retained_bytes_verified=True, omitted_native_binaries=sorted(binaries))
    with args.manifest.open('xb') as output:
        with gzip.GzipFile(fileobj=output, mode='wb', filename='', mtime=0) as compressed:
            compressed.write((json.dumps(manifest, indent=2) + '\n').encode())
    print(len(files), 'original files;', len(retained), 'retained files;',
          args.archive.stat().st_size, 'archive bytes; all retained bytes verified')


if __name__ == '__main__':
    main()
