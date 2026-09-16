"""Create a deterministic source archive without following source symlinks."""
import argparse
import gzip
from pathlib import Path
import re
import tarfile
import zipfile


def zip_archive(root, output, prefix):
    """Portable binary ZIP with fixed metadata and exclusive output creation."""
    root = root.resolve()
    output = output.parent.resolve() / output.name
    if prefix in {'.', '..'} or re.fullmatch(r'[A-Za-z0-9._-]+', prefix) is None:
        raise ValueError('archive prefix must be one safe path component')
    if output.is_relative_to(root):
        raise ValueError('archive output must be outside the source tree')
    with output.open('xb') as destination:
        try:
            with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED,
                                 compresslevel=9) as target:
                for path in sorted(root.rglob('*')):
                    if path.is_symlink() or not (path.is_file() or path.is_dir()):
                        raise ValueError('binary ZIP requires regular files/directories')
                    if path.is_dir():
                        continue
                    info = zipfile.ZipInfo(prefix + '/' + path.relative_to(root).as_posix(),
                                           date_time=(1980, 1, 1, 0, 0, 0))
                    info.create_system = 3
                    executable = path.suffix == '.exe' or bool(path.stat().st_mode & 0o111)
                    info.external_attr = (0o100755 if executable else 0o100644) << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    target.writestr(info, path.read_bytes(), compresslevel=9)
        except BaseException:
            output.unlink()
            raise


def archive(root, output, epoch, prefix="cyber-source"):
    if output.suffix == '.zip':
        return zip_archive(root, output, prefix)
    root = root.resolve()
    # Resolve parent directory aliases without following/replacing an existing
    # output symlink; exclusive creation still rejects that filename.
    output = output.parent.resolve() / output.name
    if epoch < 0 or epoch > 0xFFFFFFFF:
        raise ValueError("archive epoch must fit the gzip timestamp")
    if prefix in {".", ".."} or re.fullmatch(r"[A-Za-z0-9._-]+", prefix) is None:
        raise ValueError("archive prefix must be one safe path component")
    if output.is_relative_to(root):
        raise ValueError("archive output must be outside the source tree")
    paths = [root, *sorted(root.rglob("*"))]
    with output.open("xb") as destination:
        try:
            with gzip.GzipFile(filename="", mode="wb", fileobj=destination, mtime=epoch) as compressed:
                with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as target:
                    for path in paths:
                        relative = path.relative_to(root)
                        name = prefix if path == root else prefix + "/" + relative.as_posix()
                        # A checkout's hardlink layout is not a source input.
                        target.inodes.clear()
                        info = target.gettarinfo(str(path), arcname=name)
                        if not (info.isfile() or info.isdir() or info.issym()):
                            raise ValueError(f"unsupported source entry: {relative}")
                        info.uid = info.gid = 0
                        info.uname = info.gname = ""
                        info.mtime = epoch
                        info.pax_headers = {}
                        info.mode = 0o777 if info.issym() else 0o755 if info.isdir() or info.mode & 0o111 else 0o644
                        if info.isfile():
                            with path.open("rb") as source:
                                target.addfile(info, source)
                        else:
                            target.addfile(info)
        except BaseException:
            output.unlink()
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--epoch", type=int, required=True)
    parser.add_argument("--prefix", default="cyber-source")
    args = parser.parse_args()
    archive(args.source, args.output, args.epoch, args.prefix)
